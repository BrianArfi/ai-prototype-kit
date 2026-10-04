#!/usr/bin/env node
// artifact-comments: self-hosted server. Node 22.13 or later, no npm packages.
//
//   node server.mjs --static ../../examples            # try it: http://127.0.0.1:8787/demo
//   node server.mjs --port 8787 --db comments.db --static ./site \
//        --allow-origin https://docs.example.com --token "$ARTIFACT_COMMENTS_TOKEN"
//
// Public endpoints (the contract the browser client uses):
//
//   GET     /api/comments?slug=<slug>   -> {"comments":[...]}   oldest first
//   POST    /api/comments  {slug, name, text, parent?, where?, anchor?, state?}
//                                       -> {"comment":{...}, "key":"..."}
//   DELETE  /api/comments  {slug, id, key?}  -> {"deleted":[ids]}
//           with the comment's own key (returned once to its author), or
//           "Authorization: Bearer <token>" for the owner. A top comment goes
//           with its replies, into the trash (restore undoes it).
//   OPTIONS /api/comments               CORS preflight, when --allow-origin is set
//
// Owner endpoints, only when a token is set (--token or ARTIFACT_COMMENTS_TOKEN),
// called with "Authorization: Bearer <token>":
//
//   GET  /api/comments/admin[?slug=S]       -> {"pages":{slug:{"comments":[...],"deleted":[...]}}}
//   POST /api/comments/admin/delete  {slug, id}   soft delete, with its replies
//   POST /api/comments/admin/restore {slug, id}   undo a delete, with its replies
//
// Storage is one SQLite file (node:sqlite). Every POST runs in one transaction.
//
// CONTRACT: functions/api/comments.js (the Cloudflare Pages Function) implements
// the same public contract and the same validation: SLUG_RE, ID_RE, the caps,
// clean, frac, cleanAnchor, cleanState, one-hop reply flattening. A change to
// one must be made in the other. tests/e2e_test.py runs one suite against both
// (--backend wrangler | node).

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLIENT_JS = path.resolve(HERE, '..', '..', 'client', 'artifact-comments.js');

// ---------------------------------------------------------------- contract
// Keep this block identical in meaning to functions/api/comments.js.
const MAX_PER_SLUG = 1000;
const MAX_BODY_BYTES = 8192;
const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
const ID_RE = /^[a-z0-9]{6,24}$/;
const KEY_RE = /^[a-f0-9]{32,64}$/;

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

// Page state is whatever the page's adapter returns. Kept opaque, only size-capped.
function cleanState(s) {
  if (!s || typeof s !== 'object' || Array.isArray(s)) return null;
  const txt = JSON.stringify(s);
  return txt.length <= 600 ? JSON.parse(txt) : null;
}

function newKey() {
  return crypto.randomBytes(24).toString('hex');
}

function sha256(s) {
  return crypto.createHash('sha256').update(String(s)).digest('hex');
}

function newId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

// ---------------------------------------------------------------- options
const { values: opt } = parseArgs({
  options: {
    port: { type: 'string', default: process.env.PORT || '8787' },
    host: { type: 'string', default: process.env.HOST || '127.0.0.1' },
    db: { type: 'string', default: process.env.ARTIFACT_COMMENTS_DB || 'comments.db' },
    static: { type: 'string' },
    'allow-origin': { type: 'string', multiple: true },
    token: { type: 'string' },
    help: { type: 'boolean', short: 'h' },
  },
});

if (opt.help) {
  console.log(`artifact-comments server

  --port N            listen port (default 8787, or $PORT)
  --host H            listen address (default 127.0.0.1; 0.0.0.0 in a container)
  --db FILE           SQLite file (default comments.db)
  --static DIR        also serve a folder of pages, with clean URLs (/demo -> demo.html)
  --allow-origin O    let pages on origin O call the API (repeat, comma list, or *)
  --token T           enable the owner endpoints (or set ARTIFACT_COMMENTS_TOKEN)`);
  process.exit(0);
}

const TOKEN = opt.token || process.env.ARTIFACT_COMMENTS_TOKEN || '';
const ORIGINS = [...(opt['allow-origin'] || []), process.env.ALLOWED_ORIGINS || '']
  .flatMap((s) => s.split(',')).map((s) => s.trim()).filter(Boolean);
const STATIC_DIR = opt.static ? path.resolve(opt.static) : null;
if (STATIC_DIR && !fs.existsSync(STATIC_DIR)) {
  console.error(`--static ${STATIC_DIR} does not exist`);
  process.exit(2);
}

// ---------------------------------------------------------------- storage
const db = new DatabaseSync(opt.db);
db.exec(`
  PRAGMA journal_mode = WAL;
  PRAGMA busy_timeout = 5000;
  CREATE TABLE IF NOT EXISTS comments (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    slug       TEXT NOT NULL,
    id         TEXT NOT NULL,
    parent     TEXT,
    at         TEXT NOT NULL,
    record     TEXT NOT NULL,     -- the stored comment, exactly as returned by the API
    deleted_at TEXT,              -- set by the owner; NULL means visible
    UNIQUE (slug, id)
  );
  CREATE INDEX IF NOT EXISTS comments_by_slug ON comments (slug, deleted_at, at);
`);
// Added in 1.1.0: the SHA-256 of each comment's delete key. Older rows have none,
// so only the owner can delete them.
if (!db.prepare('PRAGMA table_info(comments)').all().some((c) => c.name === 'key_hash')) {
  db.exec('ALTER TABLE comments ADD COLUMN key_hash TEXT');
}

const q = {
  visible: db.prepare('SELECT record FROM comments WHERE slug = ? AND deleted_at IS NULL ORDER BY at, seq'),
  count: db.prepare('SELECT COUNT(*) AS n FROM comments WHERE slug = ? AND deleted_at IS NULL'),
  parentOf: db.prepare('SELECT parent FROM comments WHERE slug = ? AND id = ? AND deleted_at IS NULL'),
  insert: db.prepare('INSERT INTO comments (slug, id, parent, at, record, key_hash) VALUES (?, ?, ?, ?, ?, ?)'),
  one: db.prepare('SELECT record, deleted_at, key_hash FROM comments WHERE slug = ? AND id = ?'),
  slugs: db.prepare('SELECT DISTINCT slug FROM comments ORDER BY slug'),
  all: db.prepare('SELECT record, deleted_at FROM comments WHERE slug = ? ORDER BY at, seq'),
  softDelete: db.prepare(
    'UPDATE comments SET deleted_at = ? WHERE slug = ? AND deleted_at IS NULL AND (id = ? OR parent = ?) RETURNING id'),
  restore: db.prepare(
    'UPDATE comments SET deleted_at = NULL WHERE slug = ? AND deleted_at IS NOT NULL AND (id = ? OR parent = ?) RETURNING id'),
};

function tx(fn) {
  db.exec('BEGIN IMMEDIATE');
  try {
    const out = fn();
    db.exec('COMMIT');
    return out;
  } catch (e) {
    try { db.exec('ROLLBACK'); } catch (_) {}
    throw e;
  }
}

// ---------------------------------------------------------------- http helpers
function corsFor(req) {
  const origin = req.headers.origin;
  if (!origin || !ORIGINS.length) return null;
  if (ORIGINS.includes('*')) return { 'access-control-allow-origin': '*' };
  if (ORIGINS.includes(origin)) return { 'access-control-allow-origin': origin, vary: 'Origin' };
  return null;
}

function send(res, status, data, extra) {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'content-length': Buffer.byteLength(body),
    ...(extra || {}),
  });
  res.end(body);
}

// Read the body, at most `max` bytes. Resolves null when it is larger.
function readBody(req, max) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    let over = false;
    req.on('data', (c) => {
      if (over) return;
      size += c.length;
      if (size > max) { over = true; chunks.length = 0; resolve(null); } else chunks.push(c);
    });
    req.on('end', () => { if (!over) resolve(Buffer.concat(chunks)); });
    req.on('error', reject);
  });
}

async function readJson(req, res, cors) {
  const len = Number(req.headers['content-length'] || 0);
  const tooLarge = () => {
    send(res, 413, { error: 'comment too large' }, { ...(cors || {}), connection: 'close' });
    req.resume();
    return undefined;
  };
  if (len > MAX_BODY_BYTES) return tooLarge();
  const buf = await readBody(req, MAX_BODY_BYTES);
  if (buf === null) return tooLarge();
  let body;
  try {
    body = JSON.parse(new TextDecoder('utf-8').decode(buf));
  } catch (e) {
    send(res, 400, { error: 'bad json' }, cors);
    return undefined;
  }
  if (!body || typeof body !== 'object') {
    send(res, 400, { error: 'bad json' }, cors);
    return undefined;
  }
  return body;
}

function authorized(req) {
  const m = /^Bearer\s+(.+)$/i.exec(req.headers.authorization || '');
  if (!TOKEN || !m) return false;
  const a = Buffer.from(m[1].trim());
  const b = Buffer.from(TOKEN);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// ---------------------------------------------------------------- public API
function getComments(slug) {
  return q.visible.all(slug).map((r) => JSON.parse(r.record));
}

async function postComment(req, res, cors) {
  const body = await readJson(req, res, cors);
  if (body === undefined) return;

  const slug = clean(body.slug, 80);
  if (!SLUG_RE.test(slug)) return send(res, 400, { error: 'bad slug' }, cors);
  const text = clean(body.text, 1000, true);
  if (!text) return send(res, 400, { error: 'empty comment' }, cors);
  const name = clean(body.name, 60);
  if (!name) return send(res, 400, { error: 'name required' }, cors);

  let parent = null;
  if (body.parent != null && body.parent !== '') {
    parent = clean(body.parent, 24);
    if (!ID_RE.test(parent)) return send(res, 400, { error: 'bad parent' }, cors);
  }

  const out = tx(() => {
    if (q.count.get(slug).n >= MAX_PER_SLUG) return { status: 429, data: { error: 'comment limit reached for this page' } };
    // Replies are one level deep, as in Figma: a reply to a reply joins the
    // thread of the comment at the top. An unknown parent is kept as given,
    // as the Cloudflare backend does (there it can be replication lag).
    if (parent) {
      const p = q.parentOf.get(slug, parent);
      if (p && p.parent) parent = p.parent;
    }
    const c = {
      id: newId(),
      parent,
      name,
      text,
      where: clean(body.where, 200),
      anchor: parent ? null : cleanAnchor(body.anchor),
      state: parent ? null : cleanState(body.state),
      at: new Date().toISOString(),
    };
    const key = newKey();
    q.insert.run(slug, c.id, c.parent, c.at, JSON.stringify(c), sha256(key));
    return { status: 200, data: { comment: c, key } };
  });
  return send(res, out.status, out.data, cors);
}

// Delete from the page: the author with the comment's key, or the owner with the token.
async function deleteComment(req, res, cors) {
  const body = await readJson(req, res, cors);
  if (body === undefined) return;
  const slug = clean(body.slug, 80);
  if (!SLUG_RE.test(slug)) return send(res, 400, { error: 'bad slug' }, cors);
  const id = clean(body.id, 24);
  if (!ID_RE.test(id)) return send(res, 400, { error: 'bad id' }, cors);
  const key = clean(body.key, 64);
  const out = tx(() => {
    const row = q.one.get(slug, id);
    const owner = authorized(req);
    const author = !!(row && row.key_hash && KEY_RE.test(key) &&
      crypto.timingSafeEqual(Buffer.from(sha256(key)), Buffer.from(row.key_hash)));
    if (!owner && !author) return { status: 403, data: { error: 'only the author or the page owner can delete this comment' } };
    if (!row || row.deleted_at) return { status: 404, data: { error: 'no such comment' } };
    const ids = q.softDelete.all(new Date().toISOString(), slug, id, id).map((r) => r.id);
    return { status: 200, data: { deleted: ids } };
  });
  return send(res, out.status, out.data, cors);
}

// ---------------------------------------------------------------- owner API
function adminList(slug) {
  const slugs = slug ? [slug] : q.slugs.all().map((r) => r.slug);
  const pages = {};
  for (const s of slugs) {
    const page = { comments: [], deleted: [] };
    for (const r of q.all.all(s)) {
      const c = JSON.parse(r.record);
      if (r.deleted_at) page.deleted.push({ ...c, deleted_at: r.deleted_at });
      else page.comments.push(c);
    }
    pages[s] = page;
  }
  return { pages };
}

async function adminAction(req, res, action) {
  const body = await readJson(req, res, null);
  if (body === undefined) return;
  const slug = clean(body.slug, 80);
  const id = clean(body.id, 24);
  if (!SLUG_RE.test(slug)) return send(res, 400, { error: 'bad slug' });
  if (!ID_RE.test(id)) return send(res, 400, { error: 'bad id' });
  const out = tx(() => {
    const row = q.one.get(slug, id);
    if (action === 'delete') {
      if (!row || row.deleted_at) return { status: 404, data: { error: `no comment ${id} on ${slug}` } };
      const ids = q.softDelete.all(new Date().toISOString(), slug, id, id).map((r) => r.id);
      return { status: 200, data: { deleted: ids, comment: JSON.parse(row.record) } };
    }
    if (!row || !row.deleted_at) return { status: 404, data: { error: `no comment ${id} in the trash of ${slug}` } };
    const ids = q.restore.all(slug, id, id).map((r) => r.id);
    return { status: 200, data: { restored: ids, comment: JSON.parse(row.record) } };
  });
  return send(res, out.status, out.data);
}

// ---------------------------------------------------------------- static files
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.htm': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8', '.md': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.ico': 'image/x-icon', '.avif': 'image/avif',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.mp4': 'video/mp4', '.webm': 'video/webm',
  '.mp3': 'audio/mpeg', '.pdf': 'application/pdf', '.map': 'application/json',
};

function isFile(p) {
  try { return fs.statSync(p).isFile(); } catch (e) { return false; }
}

// Clean URLs, as Cloudflare Pages serves them: /demo -> demo.html, /dir/ -> dir/index.html.
function resolveStatic(pathname) {
  let p;
  try { p = decodeURIComponent(pathname); } catch (e) { return null; }
  if (p.includes('\0')) return null;
  if (STATIC_DIR) {
    const tries = p.endsWith('/') ? [p + 'index.html'] : [p, p + '.html', p + '/index.html'];
    for (const t of tries) {
      const full = path.resolve(STATIC_DIR, '.' + t);
      if (full !== STATIC_DIR && !full.startsWith(STATIC_DIR + path.sep)) return null;
      if (isFile(full)) return full;
    }
  }
  // The client script is served from the skill even when the static folder lacks it.
  if (p === '/artifact-comments.js' && isFile(CLIENT_JS)) return CLIENT_JS;
  return null;
}

function serveStatic(req, res, pathname) {
  const file = resolveStatic(pathname);
  if (!file) {
    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    return res.end('not found');
  }
  const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
  const size = fs.statSync(file).size;
  res.writeHead(200, { 'content-type': type, 'content-length': size, 'cache-control': 'no-cache' });
  if (req.method === 'HEAD') return res.end();
  fs.createReadStream(file).pipe(res);
}

// ---------------------------------------------------------------- router
async function handle(req, res) {
  const url = new URL(req.url, 'http://localhost');
  const p = url.pathname.replace(/\/+$/, '') || '/';

  if (p === '/api/comments') {
    const cors = corsFor(req);
    if (req.method === 'OPTIONS') {
      if (!cors) { res.writeHead(204); return res.end(); }
      res.writeHead(204, {
        ...cors,
        'access-control-allow-methods': 'GET, POST, DELETE, OPTIONS',
        'access-control-allow-headers': 'content-type, authorization',
        'access-control-max-age': '86400',
      });
      return res.end();
    }
    if (req.method === 'GET') {
      const slug = url.searchParams.get('slug') || '';
      if (!SLUG_RE.test(slug)) return send(res, 400, { error: 'bad slug' }, cors);
      return send(res, 200, { comments: getComments(slug) }, cors);
    }
    if (req.method === 'POST') return postComment(req, res, cors);
    if (req.method === 'DELETE') return deleteComment(req, res, cors);
    return send(res, 405, { error: 'method not allowed' }, cors);
  }

  if (p === '/api/comments/admin' || p.startsWith('/api/comments/admin/')) {
    if (!TOKEN) return send(res, 403, { error: 'owner endpoints are off: start the server with --token or ARTIFACT_COMMENTS_TOKEN' });
    if (!authorized(req)) return send(res, 401, { error: 'bad or missing token' });
    if (p === '/api/comments/admin' && req.method === 'GET') {
      const slug = url.searchParams.get('slug') || '';
      if (slug && !SLUG_RE.test(slug)) return send(res, 400, { error: 'bad slug' });
      return send(res, 200, adminList(slug));
    }
    if (p === '/api/comments/admin/delete' && req.method === 'POST') return adminAction(req, res, 'delete');
    if (p === '/api/comments/admin/restore' && req.method === 'POST') return adminAction(req, res, 'restore');
    return send(res, 404, { error: 'unknown owner endpoint' });
  }

  if (req.method === 'GET' || req.method === 'HEAD') return serveStatic(req, res, url.pathname);
  return send(res, 405, { error: 'method not allowed' });
}

const server = http.createServer((req, res) => {
  handle(req, res).catch((e) => {
    console.error(e);
    if (!res.headersSent) send(res, 500, { error: 'server error' });
    else res.end();
  });
});

server.listen(Number(opt.port), opt.host, () => {
  const where = `http://${opt.host.includes(':') ? `[${opt.host}]` : opt.host}:${server.address().port}`;
  console.log(`artifact-comments server on ${where}  (db ${path.resolve(opt.db)})`);
  if (STATIC_DIR) console.log(`  static pages from ${STATIC_DIR}`);
  if (ORIGINS.length) console.log(`  CORS allowed for ${ORIGINS.join(', ')}`);
  console.log(`  owner endpoints ${TOKEN ? 'on' : 'off (no token)'}`);
});

function shutdown() {
  server.close();
  try { db.close(); } catch (e) {}
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
