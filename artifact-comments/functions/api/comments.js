// artifact-comments: Cloudflare Pages Function, the whole backend.
//
//   GET  /api/comments?slug=<slug>   -> {"comments":[...]}   oldest first
//   POST /api/comments  {slug, name, text, parent?, where?, anchor?, state?}
//                                    -> {"comment":{...}}   the stored record
//
// Storage is one Workers KV namespace bound as COMMENTS. Three kinds of key:
//
//   c:<slug>:<id>       one per comment. Written once, never rewritten, so two
//                       people posting at the same moment can never overwrite
//                       each other. This is the record of truth.
//   comments:<slug>     the summary: every comment of the page in one array.
//                       GET reads only this key, so a page view costs one KV
//                       read. Rebuilt on every POST from the per-comment keys
//                       plus its own previous content, which also heals it if
//                       an earlier rebuild ever missed a comment.
//   deleted:<slug>      ids removed by the owner (comments_cli.py delete), so
//                       a rebuild never brings a deleted comment back.
//
// KV is eventually consistent: another region can see a new comment up to
// about 60 seconds late. The client keeps the comments its own reader posted
// until the server shows them, so nobody ever sees their own comment vanish.
//
// No auth, by design: the pages are unlisted and the payload is capped. The
// owner moderates with comments_cli.py, which talks to the KV API directly.
//
// Cross-origin is opt-in. Set the Pages environment variable ALLOWED_ORIGINS
// to a comma-separated list of origins (or "*") whose pages may call this
// endpoint. Unset, the endpoint answers same-origin pages only.
//
// CONTRACT: server/node/server.mjs implements the same HTTP contract and the
// same validation (SLUG_RE, ID_RE, caps, clean, frac, cleanAnchor, cleanState,
// one-hop reply flattening). A change to one must be made in the other, and
// tests/e2e_test.py runs the same suite against both. This file stays a single
// self-contained module: publishers copy it on its own.

const MAX_PER_SLUG = 1000;
const MAX_BODY_BYTES = 8192;
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
const ID_RE = /^[a-z0-9]{6,24}$/;

function json(data, status = 200, cors = null) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...(cors || {}) },
  });
}

// CORS headers for this request, or null when its origin is not allowed.
function corsFor(request, env) {
  const origin = request.headers.get('origin');
  const allowed = String((env && env.ALLOWED_ORIGINS) || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (!origin || !allowed.length) return null;
  if (allowed.includes('*')) return { 'access-control-allow-origin': '*' };
  if (allowed.includes(origin)) return { 'access-control-allow-origin': origin, vary: 'Origin' };
  return null;
}

function byteLength(s) {
  return new TextEncoder().encode(s).length;
}

// Strip control characters, keep newlines in the comment body.
function clean(s, max, keepNewlines = false) {
  const re = keepNewlines ? /[\u0000-\u0009\u000b-\u001f\u007f]/g : /[\u0000-\u001f\u007f]/g;
  return String(s == null ? '' : s).replace(re, ' ').trim().slice(0, max);
}

function frac(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(1, Math.max(0, Math.round(n * 1000) / 1000)) : 0.5;
}

function cleanAnchor(a) {
  if (!a || typeof a !== 'object') return null;
  return {
    sel: clean(a.sel, 400),
    text: clean(a.text, 120),
    tag: clean(a.tag, 20).toLowerCase().replace(/[^a-z0-9-]/g, ''),
    fx: frac(a.fx),
    fy: frac(a.fy),
  };
}

// Page state is whatever the page's adapter returns (a screen index, a slide,
// a #hash). Kept opaque, only size-capped.
function cleanState(s) {
  if (!s || typeof s !== 'object' || Array.isArray(s)) return null;
  const txt = JSON.stringify(s);
  return txt.length <= 600 ? JSON.parse(txt) : null;
}

async function readArray(env, key) {
  const raw = await env.COMMENTS.get(key);
  if (!raw) return [];
  try {
    const v = JSON.parse(raw);
    return Array.isArray(v) ? v : [];
  } catch (e) {
    return [];
  }
}

async function listIds(env, slug) {
  const prefix = `c:${slug}:`;
  const ids = [];
  let cursor;
  do {
    const page = await env.COMMENTS.list({ prefix, cursor });
    for (const k of page.keys) ids.push(k.name.slice(prefix.length));
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return ids;
}

function byTime(a, b) {
  return a.at < b.at ? -1 : a.at > b.at ? 1 : 0;
}

// Rebuild the summary: previous summary + every per-comment key + the new
// comment, minus anything the owner deleted. Two readers posting at the same
// moment both rebuild, and the one that writes last may have listed the keys
// before the other's comment existed. So after writing, list again, and go
// round once more if a comment appeared that the summary lacks.
async function rebuild(env, slug, fresh) {
  const deleted = new Set(await readArray(env, `deleted:${slug}`));
  let ids = await listIds(env, slug);
  for (let round = 0; round < 3; round++) {
    const summary = await readArray(env, `comments:${slug}`);
    const byId = new Map();
    for (const c of summary) if (c && c.id) byId.set(c.id, c);
    if (fresh) byId.set(fresh.id, fresh);
    const missing = ids.filter((id) => !byId.has(id) && !deleted.has(id));
    const got = await Promise.all(missing.map((id) => env.COMMENTS.get(`c:${slug}:${id}`)));
    got.forEach((raw) => {
      if (!raw) return;
      try {
        const c = JSON.parse(raw);
        if (c && c.id) byId.set(c.id, c);
      } catch (e) {}
    });
    const all = [...byId.values()].filter((c) => !deleted.has(c.id)).sort(byTime);
    await env.COMMENTS.put(`comments:${slug}`, JSON.stringify(all));
    const written = new Set(all.map((c) => c.id));
    ids = await listIds(env, slug);
    if (ids.every((id) => written.has(id) || deleted.has(id))) return all;
  }
}

export async function onRequest(context) {
  const { request, env } = context;
  const cors = corsFor(request, env);
  if (request.method === 'OPTIONS') {
    if (!cors) return new Response(null, { status: 204 });
    return new Response(null, {
      status: 204,
      headers: {
        ...cors,
        'access-control-allow-methods': 'GET, POST, OPTIONS',
        'access-control-allow-headers': 'content-type',
        'access-control-max-age': '86400',
      },
    });
  }
  const reply = (data, status = 200) => json(data, status, cors);
  if (!env.COMMENTS) return reply({ error: 'KV binding COMMENTS missing' }, 500);
  const url = new URL(request.url);

  if (request.method === 'GET') {
    const slug = url.searchParams.get('slug') || '';
    if (!SLUG_RE.test(slug)) return reply({ error: 'bad slug' }, 400);
    return reply({ comments: await readArray(env, `comments:${slug}`) });
  }

  if (request.method === 'POST') {
    const len = Number(request.headers.get('content-length') || 0);
    if (len > MAX_BODY_BYTES) return reply({ error: 'comment too large' }, 413);
    let body;
    try {
      const raw = await request.text();
      if (byteLength(raw) > MAX_BODY_BYTES) return reply({ error: 'comment too large' }, 413);
      body = JSON.parse(raw);
    } catch (e) {
      return reply({ error: 'bad json' }, 400);
    }
    if (!body || typeof body !== 'object') return reply({ error: 'bad json' }, 400);

    const slug = clean(body.slug, 80);
    if (!SLUG_RE.test(slug)) return reply({ error: 'bad slug' }, 400);
    const text = clean(body.text, 1000, true);
    if (!text) return reply({ error: 'empty comment' }, 400);
    const name = clean(body.name, 60);
    if (!name) return reply({ error: 'name required' }, 400);

    const summary = await readArray(env, `comments:${slug}`);
    if (summary.length >= MAX_PER_SLUG) return reply({ error: 'comment limit reached for this page' }, 429);

    // Replies are one level deep, as in Figma: a reply to a reply joins the
    // thread of the comment at the top.
    let parent = null;
    if (body.parent != null && body.parent !== '') {
      parent = clean(body.parent, 24);
      if (!ID_RE.test(parent)) return reply({ error: 'bad parent' }, 400);
      let p = summary.find((c) => c.id === parent);
      if (!p) {
        const raw = await env.COMMENTS.get(`c:${slug}:${parent}`);
        if (raw) { try { p = JSON.parse(raw); } catch (e) {} }
      }
      // Not found yet can simply be replication lag, so the reply is kept.
      if (p && p.parent) parent = p.parent;
    }

    const c = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
      parent,
      name,
      text,
      where: clean(body.where, 200),
      anchor: parent ? null : cleanAnchor(body.anchor),
      state: parent ? null : cleanState(body.state),
      at: new Date().toISOString(),
    };
    await env.COMMENTS.put(`c:${slug}:${c.id}`, JSON.stringify(c));
    try {
      await rebuild(env, slug, c);
    } catch (e) {
      // The comment is already safe in its own key; the next POST or
      // `comments_cli.py repair` folds it into the summary.
    }
    return reply({ comment: c });
  }

  return reply({ error: 'method not allowed' }, 405);
}
