/*!
 * artifact-comments: Figma-style comments for any static HTML page.
 *
 * Drop one tag into a page served next to the /api/comments endpoint:
 *   <script src="/artifact-comments.js" data-slug="my-page" defer></script>
 *
 * Readers click "Comment", click any part of the page, type a name and a
 * comment. Everyone who opens the page sees the numbered pin on that exact
 * spot, can open the thread and reply. See README.md for the full contract.
 *
 * Design notes, each one a bug that happened before it was a rule:
 * - All UI lives in a closed-off Shadow DOM hung off <html>, not <body>. Page
 *   CSS cannot restyle it, and redrawing it never trips the page's own
 *   MutationObserver, nor ours (we observe <body> only).
 * - Keys typed into the comment UI are stopped at window capture, so a page
 *   that plays or pauses on the space bar never sees them.
 * - The pick-mode hover is an overlay box, not a CSS :hover outline, which
 *   would outline every ancestor of the hovered element at once.
 * - Re-rendering after a background refresh never rebuilds a textarea, so
 *   text being typed is never wiped.
 * - A comment whose part cannot be found says so. It never fails silently.
 */
(function () {
  'use strict';
  if (window.__artifactCommentsLoaded) return;
  window.__artifactCommentsLoaded = true;

  // ---------------------------------------------------------------- config
  var VERSION = '1.0.3';    // keep in step with CHANGELOG.md and server/node/package.json
  var script = document.currentScript || {};
  var ds = script.dataset || {};
  function A() { return window.ArtifactComments || {}; } // read late: a page may register after us
  var API = ds.api || A().api || '/api/comments';
  var SLUG = ds.slug || A().slug || slugFromPath();
  var POSITION = ds.position || A().position || 'right'; // 'right' | 'left'
  var CHANGELOG = ds.changelog || A().changelog ||
    'https://github.com/BrianArfi/artifact-comments/blob/main/CHANGELOG.md';
  var ICON_CHAT = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/></svg>';
  var ICON_PLUS = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z"/></svg>';
  var POLL_MS = 30000;
  var NAME_KEY = 'artifact-comments:name';
  var PINS_KEY = 'artifact-comments:pins-hidden:' + SLUG; // per page: hiding pins on one page must not hide them on the next
  var PENDING_KEY = 'artifact-comments:pending:' + SLUG;

  function slugFromPath() {
    var last = location.pathname.split('/').filter(Boolean).pop() || 'index';
    return last.replace(/\.html?$/i, '').toLowerCase()
      .replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'index';
  }

  // ---------------------------------------------------------------- state
  var server = [];          // comments as the server last returned them
  var mine = {};            // id -> comment I posted this session (covers a stale read)
  var pending = loadPending(); // not yet accepted by the server
  var threads = [];         // derived: [{root, replies, n}]
  var picking = false;
  var panelOpen = false;
  var pinsHidden = localStorage.getItem(PINS_KEY) === '1';
  var openId = null;        // thread shown in the bubble
  var composer = null;      // {anchor, state, where, x, y} while writing a new comment
  var hoverEl = null;
  var flashEl = null, flashUntil = 0;
  var lastFetch = 0, lastSig = '';

  function loadPending() {
    try { return JSON.parse(localStorage.getItem(PENDING_KEY) || '[]'); } catch (e) { return []; }
  }
  function savePending() {
    try { localStorage.setItem(PENDING_KEY, JSON.stringify(pending)); } catch (e) {}
  }
  function getName() { try { return localStorage.getItem(NAME_KEY) || ''; } catch (e) { return ''; } }
  function setName(v) { try { localStorage.setItem(NAME_KEY, v); } catch (e) {} }

  // Older records carry {sel, ctx, flow}; normalise them to the current shape.
  function norm(c) {
    var a = c.anchor || {};
    return {
      id: c.id, parent: c.parent || null, name: c.name || 'anonymous', text: c.text || '',
      at: c.at || new Date().toISOString(),
      where: c.where || c.ctx || '',
      anchor: { sel: a.sel || c.sel || '', text: a.text || '', tag: a.tag || '',
                fx: num(a.fx, 0.5), fy: num(a.fy, 0.5) },
      state: c.state || (c.flow ? { flow: c.flow } : null),
      status: c.status || null
    };
  }
  function num(v, d) { return typeof v === 'number' && isFinite(v) ? Math.min(1, Math.max(0, v)) : d; }

  function allComments() {
    var byId = {};
    server.forEach(function (c) { byId[c.id] = norm(c); });
    Object.keys(mine).forEach(function (id) { if (!byId[id]) byId[id] = norm(mine[id]); });
    pending.forEach(function (c) { byId[c.id] = norm(c); });
    return Object.keys(byId).map(function (k) { return byId[k]; })
      .sort(function (a, b) { return a.at < b.at ? -1 : a.at > b.at ? 1 : 0; });
  }

  // A reply joins the thread of its top comment. A reply whose parent has not
  // arrived yet (another region, not replicated) waits, hidden: shown as a
  // thread of its own it would be a pin-less phantom that points nowhere.
  function rebuildThreads() {
    var list = allComments(), roots = [], byId = {};
    list.forEach(function (c) { byId[c.id] = c; });
    function topOf(c) {
      for (var hops = 0; c && c.parent && hops < 20; hops++) c = byId[c.parent];
      return c && !c.parent ? c : null;
    }
    list.forEach(function (c) { if (!c.parent) roots.push({ root: c, replies: [] }); });
    var index = {};
    roots.forEach(function (t, i) { t.n = i + 1; index[t.root.id] = t; });
    list.forEach(function (c) {
      if (!c.parent) return;
      var top = topOf(c);
      if (top && index[top.id]) index[top.id].replies.push(c);
    });
    threads = roots;
  }
  function threadById(id) {
    for (var i = 0; i < threads.length; i++) if (threads[i].root.id === id) return threads[i];
    return null;
  }

  // ---------------------------------------------------------------- network
  function refresh() {
    lastFetch = Date.now();
    return fetch(API + '?slug=' + encodeURIComponent(SLUG), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !Array.isArray(d.comments)) return;
        var sig = JSON.stringify(d.comments);
        if (sig === lastSig && !Object.keys(mine).length) return; // nothing new: no re-render
        lastSig = sig;
        server = d.comments;
        var now = Date.now();
        Object.keys(mine).forEach(function (id) {   // the server has caught up, or 5 min passed
          if (server.some(function (c) { return c.id === id; }) ||
              now - Date.parse(mine[id].at) > 300000) delete mine[id];
        });
        changed();
      })
      .catch(function () {});
  }

  function send(c) {
    if (c.parent && /^tmp-/.test(c.parent)) {   // its thread is not saved yet
      c.status = pending.some(function (p) { return p.id === c.parent; }) ? 'waiting' : 'failed';
      savePending();
      changed();
      return Promise.resolve();
    }
    c.status = 'sending';
    changed();
    var body = { slug: SLUG, parent: c.parent, name: c.name, text: c.text,
                 where: c.where, anchor: c.anchor, state: c.state };
    return fetch(API, { method: 'POST', headers: { 'content-type': 'application/json' },
                        body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok || !d.comment) throw new Error(d.error || ('HTTP ' + r.status));
          return d.comment;
        });
      })
      .then(function (saved) {
        pending = pending.filter(function (p) { return p.id !== c.id; });
        savePending();
        mine[saved.id] = saved;
        if (openId === c.id) { openId = saved.id; if (bubbleFor === c.id) bubbleFor = saved.id; }
        if (pinNodes[c.id]) { pinNodes[saved.id] = pinNodes[c.id]; delete pinNodes[c.id]; }
        pending.forEach(function (p) {           // replies that waited for this thread
          if (p.parent === c.id) { p.parent = saved.id; send(p); }
        });
        savePending();
        changed();
      })
      .catch(function (err) {
        c.status = 'failed';
        c.error = String(err && err.message || err);
        savePending();
        changed();
      });
  }

  function queue(c) {
    c.id = 'tmp-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    c.at = new Date().toISOString();
    pending.push(c);
    savePending();
    send(c);
    return c.id;
  }

  function retryFailed() {
    pending.forEach(function (c) { if (c.status !== 'sending') send(c); });
  }

  // ---------------------------------------------------------------- anchors
  function cssPath(el) {
    if (!(el instanceof Element)) return '';
    var parts = [];
    while (el && el.nodeType === 1 && el !== document.documentElement) {
      if (el.id && document.querySelectorAll('#' + cssEscape(el.id)).length === 1) {
        parts.unshift('#' + cssEscape(el.id));
        break;
      }
      var tag = el.tagName.toLowerCase();
      if (el === document.body) { parts.unshift('body'); break; }
      var parent = el.parentElement, seg = tag;
      if (parent) {
        var same = [];
        for (var i = 0; i < parent.children.length; i++)
          if (parent.children[i].tagName === el.tagName) same.push(parent.children[i]);
        if (same.length > 1) seg += ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
      }
      parts.unshift(seg);
      el = parent;
    }
    return parts.join(' > ');
  }
  function cssEscape(s) {
    return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }
  function snippet(el) {
    var t = (el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('alt'))) ||
            el.textContent || el.getAttribute && el.getAttribute('placeholder') || '';
    return String(t).replace(/\s+/g, ' ').trim().slice(0, 80);
  }
  function sameText(a, b) {
    a = (a || '').slice(0, 60); b = (b || '').slice(0, 60);
    return !!a && a === b;
  }

  // strict: the selector resolves and, if we stored text, the text still matches.
  // loose: the selector resolves (text may differ, e.g. the page switched language).
  function resolve(anchor, strict) {
    var el = null;
    if (anchor.sel) { try { el = document.querySelector(anchor.sel); } catch (e) { el = null; } }
    if (el && anchor.text && !sameText(snippet(el), anchor.text)) {
      if (strict) el = byText(anchor) || null;
    }
    if (!el && anchor.text) el = byText(anchor);
    return el;
  }
  function byText(anchor) {
    if (!anchor.tag) return null;
    var list;
    try { list = document.body.getElementsByTagName(anchor.tag); } catch (e) { return null; }
    for (var i = 0; i < list.length; i++) if (sameText(snippet(list[i]), anchor.text)) return list[i];
    return null;
  }

  // The on-screen point of an anchor, or null when the part is not visible:
  // not rendered, scrolled out of its scroll box, or outside the viewport.
  // Is the page showing the state this comment was left in? true, false, or
  // undefined when the page has no isCurrent() and cannot tell. Pages that
  // reuse the same elements for different content (a walkthrough redrawing
  // one phone screen after another) need it, or a pin would sit on every
  // screen's version of the element.
  function onItsState(c) {
    try { return A().isCurrent && c.state ? A().isCurrent(c.state) : undefined; } catch (e) { return undefined; }
  }
  // The element a pin sits on right now, or null. The text must still match,
  // unless the page confirms it is the comment's own state (the same screen in
  // another language, a field still being typed).
  function anchorEl(c) {
    var cur = onItsState(c);
    if (cur === false) return null;
    var e = resolve(c.anchor, true);
    if (!e && cur === true) e = resolve(c.anchor, false);
    return e;
  }

  function pointOf(anchor, el) {
    if (!el || !el.getBoundingClientRect) return null;
    var r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return null;
    var x = r.left + anchor.fx * r.width, y = r.top + anchor.fy * r.height;
    for (var p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      var cs = styleOf(p);
      if (cs.display === 'none' || cs.visibility === 'hidden') return null;
      if (/(auto|scroll|hidden|clip)/.test(cs.overflow + cs.overflowX + cs.overflowY)) {
        var pr = p.getBoundingClientRect();
        if (x < pr.left - 1 || x > pr.right + 1 || y < pr.top - 1 || y > pr.bottom + 1) return null;
      }
    }
    var own = styleOf(el);
    if (own.visibility === 'hidden' || own.display === 'none') return null;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return null;
    return { x: x, y: y, rect: r };
  }

  // Nearest heading above the element, as a readable "where" for plain pages.
  function headingFor(el) {
    var hs = document.querySelectorAll('h1,h2,h3,h4'), best = null;
    for (var i = 0; i < hs.length; i++) {
      var pos = hs[i].compareDocumentPosition(el);
      if (hs[i] === el || hs[i].contains(el) || (pos & Node.DOCUMENT_POSITION_FOLLOWING)) best = hs[i];
    }
    return best ? snippet(best) : '';
  }
  function whereFor(el) {
    var label = '';
    try { label = A().label ? A().label(el) : ''; } catch (e) {}
    return String(label || headingFor(el) || document.title || '').slice(0, 200);
  }
  function stateNow() {
    var s = null;
    try { s = A().state ? A().state() : null; } catch (e) {}
    if (!s && location.hash) s = { hash: location.hash };
    return s;
  }
  function pausePage() { try { if (A().pause) A().pause(); } catch (e) {} }

  // ---------------------------------------------------------------- DOM
  var host = document.createElement('artifact-comments');
  host.setAttribute('data-artifact-comments', '');
  var root = host.attachShadow({ mode: 'open' });
  root.innerHTML = '<style>' + CSS_TEXT() + '</style>' +
    '<div class="layer" part="layer">' +
    '  <div class="pins"></div>' +
    '  <div class="catchers"></div>' +
    '  <div class="hover"></div>' +
    '  <div class="flash"></div>' +
    '  <aside class="panel" hidden></aside>' +
    '  <div class="fab ' + (POSITION === 'left' ? 'left' : 'right') + '">' +
    '    <button class="fab-list" type="button" title="All comments">' + ICON_CHAT + '<span>Comments</span><b class="count">0</b></button>' +
    '    <button class="fab-add" type="button" title="Comment on a part of the page">' + ICON_PLUS + '<span>Comment</span></button>' +
    '  </div>' +
    '  <div class="banner" hidden>Click any part of the page to comment' +
    '    <button class="banner-x" type="button">Cancel</button><span class="kbd">Esc</span></div>' +
    '  <div class="bubble" hidden></div>' +
    '  <div class="compose" hidden></div>' +
    '  <div class="peek" hidden></div>' +
    '</div>';
  var $ = function (s) { return root.querySelector(s); };
  var pinsEl = $('.pins'), hoverBox = $('.hover'), flashBox = $('.flash'), banner = $('.banner'),
      bubble = $('.bubble'), compose = $('.compose'), panel = $('.panel'), peek = $('.peek'),
      catchers = $('.catchers'), countEl = $('.count'), addBtn = $('.fab-add');

  function mount() {
    if (!document.documentElement.contains(host)) document.documentElement.appendChild(host);
  }

  // ---------------------------------------------------------------- render
  function changed() {
    rebuildThreads();
    countEl.textContent = threads.length;
    if (openId && !threadById(openId)) openId = null;
    renderPanel();
    renderBubble();
    schedule();
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function ago(iso) {
    var s = (Date.now() - Date.parse(iso)) / 1000;
    if (!isFinite(s)) return '';
    if (s < 45) return 'just now';
    if (s < 3600) return Math.round(s / 60) + 'm ago';
    if (s < 86400) return Math.round(s / 3600) + 'h ago';
    if (s < 604800) return Math.round(s / 86400) + 'd ago';
    return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  }
  function statusLine(c) {
    if (c.status === 'sending') return el('div', 'status', 'Sending…');
    if (c.status === 'waiting') return el('div', 'status', 'Waiting for the comment above to save…');
    if (c.status === 'failed') {
      var s = el('div', 'status failed', 'Not sent. ');
      var b = el('button', 'link', 'Retry');
      b.type = 'button';
      b.onclick = function (e) { e.stopPropagation(); send(c); };
      s.appendChild(b);
      return s;
    }
    return null;
  }
  function messageNode(c) {
    var m = el('div', 'msg');
    var h = el('div', 'msg-head');
    h.appendChild(el('span', 'avatar', (c.name || '?').trim().charAt(0).toUpperCase() || '?'));
    h.appendChild(el('b', 'who', c.name));
    h.appendChild(el('span', 'when', ago(c.at)));
    m.appendChild(h);
    var t = el('div', 'txt', c.text);
    t.dir = 'auto';
    m.appendChild(t);
    var st = statusLine(c);
    if (st) m.appendChild(st);
    return m;
  }

  function renderPanel() {
    panel.hidden = !panelOpen;
    if (!panelOpen) return;
    var oldRows = panel.querySelector('.rows'), keep = oldRows ? oldRows.scrollTop : 0;
    panel.textContent = '';
    var head = el('div', 'panel-head');
    head.appendChild(el('b', null, 'Comments (' + threads.length + ')'));
    var tools = el('div', 'panel-tools');
    var eye = el('button', 'link', pinsHidden ? 'Show pins' : 'Hide pins');
    eye.type = 'button';
    eye.onclick = function () {
      pinsHidden = !pinsHidden;
      try { localStorage.setItem(PINS_KEY, pinsHidden ? '1' : '0'); } catch (e) {}
      renderPanel(); schedule();
    };
    var x = el('button', 'x', '×');
    x.type = 'button'; x.title = 'Close';
    x.onclick = function () { panelOpen = false; renderPanel(); };
    tools.appendChild(eye); tools.appendChild(x);
    head.appendChild(tools);
    panel.appendChild(head);
    if (!threads.length) {
      panel.appendChild(el('p', 'empty',
        'No comments yet. Press Comment, click any part of the page, and write. ' +
        'Everyone who opens this page sees it, and can reply.'));
      panel.appendChild(panelFoot());
      return;
    }
    var list = el('div', 'rows');
    threads.forEach(function (t) {
      var row = el('button', 'row' + (t.root.id === openId ? ' on' : ''));
      row.type = 'button';
      var top = el('div', 'row-head');
      top.appendChild(el('span', 'num', String(t.n)));
      top.appendChild(el('b', 'who', t.root.name));
      top.appendChild(el('span', 'when', ago(t.root.at)));
      row.appendChild(top);
      if (t.root.where) row.appendChild(el('div', 'where', t.root.where));
      var tx = el('div', 'txt clamp', t.root.text);
      tx.dir = 'auto';
      row.appendChild(tx);
      var foot = [];
      if (t.replies.length) foot.push(t.replies.length + (t.replies.length === 1 ? ' reply' : ' replies'));
      if (t.root.status === 'failed' || t.replies.some(function (r) { return r.status === 'failed'; }))
        foot.push('not sent');
      if (foot.length) row.appendChild(el('div', 'meta', foot.join(' · ')));
      row.onclick = function () { openThread(t.root.id, true); };
      list.appendChild(row);
    });
    panel.appendChild(list);
    panel.appendChild(panelFoot());
    list.scrollTop = keep;
    var on = list.querySelector('.row.on');   // bring the open thread into the list's view,
    if (on) {                                 // without scrolling the page itself
      if (on.offsetTop < list.scrollTop) list.scrollTop = on.offsetTop - 4;
      else if (on.offsetTop + on.offsetHeight > list.scrollTop + list.clientHeight)
        list.scrollTop = on.offsetTop + on.offsetHeight - list.clientHeight + 4;
    }
  }

  // Version line under the list, with a link to what changed.
  function panelFoot() {
    var f = el('div', 'panel-foot');
    f.appendChild(el('span', 'ver', 'artifact-comments v' + VERSION));
    f.appendChild(document.createTextNode(' · '));
    var a = el('a', 'foot-link', "What's new");
    a.href = CHANGELOG;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    f.appendChild(a);
    return f;
  }

  // The bubble is built once per opened thread; a refresh only swaps the
  // message list, so a half-typed reply survives it.
  var bubbleFor = null;
  function renderBubble(note) {
    var t = openId && threadById(openId);
    if (!t) { bubble.hidden = true; bubbleFor = null; return; }
    if (bubbleFor !== openId) {
      bubbleFor = openId;
      bubble.textContent = '';
      var head = el('div', 'bubble-head');
      head.appendChild(el('span', 'num'));
      head.appendChild(el('span', 'where'));
      var x = el('button', 'x', '×');
      x.type = 'button'; x.title = 'Close (Esc)';
      x.onclick = closeThread;
      head.appendChild(x);
      bubble.appendChild(head);
      var nt = el('div', 'note');
      nt.hidden = true;
      bubble.appendChild(nt);
      bubble.appendChild(el('div', 'quote'));
      bubble.appendChild(el('div', 'msgs'));
      bubble.appendChild(replyForm());
    }
    bubble.querySelector('.num').textContent = String(t.n);
    bubble.querySelector('.where').textContent = t.root.where || '';
    var q = bubble.querySelector('.quote');
    q.textContent = t.root.anchor.text ? '“' + t.root.anchor.text + '”' : '';
    q.hidden = !t.root.anchor.text;
    q.dir = 'auto';
    var n = bubble.querySelector('.note');
    if (note !== undefined) { n.textContent = note || ''; n.hidden = !note; }
    var msgs = bubble.querySelector('.msgs');
    var atBottom = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 8, keepTop = msgs.scrollTop;
    msgs.textContent = '';
    msgs.appendChild(messageNode(t.root));
    t.replies.forEach(function (r) { msgs.appendChild(messageNode(r)); });
    msgs.scrollTop = atBottom ? msgs.scrollHeight : keepTop;
    bubble.hidden = false;
  }

  function nameField(form) {
    var saved = getName();
    var wrap = el('div', 'name-wrap');
    var input = el('input', 'name');
    input.placeholder = 'Your name';
    input.maxLength = 60;
    input.value = saved;
    input.autocomplete = 'name';
    var as = el('div', 'as');
    as.appendChild(document.createTextNode('as '));
    var who = el('b', null, saved);
    as.appendChild(who);
    var change = el('button', 'link', 'change');
    change.type = 'button';
    change.onclick = function () { as.hidden = true; input.hidden = false; input.focus(); input.select(); };
    as.appendChild(document.createTextNode(' · '));
    as.appendChild(change);
    input.hidden = !!saved;
    as.hidden = !saved;
    wrap.appendChild(as);
    wrap.appendChild(input);
    form._name = input;
    return wrap;
  }

  function replyForm() {
    var f = el('form', 'form reply');
    f.appendChild(nameField(f));
    var ta = el('textarea', 'text');
    ta.rows = 2; ta.maxLength = 1000; ta.placeholder = 'Reply'; ta.dir = 'auto';
    f.appendChild(ta);
    var row = el('div', 'actions');
    row.appendChild(el('span', 'hint', 'Ctrl + Enter to send'));
    var go = el('button', 'primary', 'Reply');
    go.type = 'submit';
    row.appendChild(go);
    f.appendChild(row);
    f.onsubmit = function (e) {
      e.preventDefault();
      var name = f._name.value.trim(), text = ta.value.trim();
      if (!name) { f._name.hidden = false; f._name.parentNode.querySelector('.as').hidden = true; f._name.focus(); return; }
      if (!text) { ta.focus(); return; }
      setName(name);
      queue({ parent: openId, name: name, text: text });
      ta.value = '';
      syncNameFields();
    };
    return f;
  }
  function syncNameFields() {
    var saved = getName();
    root.querySelectorAll('.name-wrap').forEach(function (w) {
      var input = w.querySelector('input.name'), as = w.querySelector('.as');
      if (!saved) return;
      if (document.activeElement === host && root.activeElement === input) return;
      input.value = saved;
      as.querySelector('b').textContent = saved;
      input.hidden = true; as.hidden = false;
    });
  }

  function openComposer(target, x, y) {
    var r = target.getBoundingClientRect();
    composer = {
      anchor: {
        sel: cssPath(target), text: snippet(target), tag: target.tagName.toLowerCase(),
        fx: r.width ? Math.min(1, Math.max(0, (x - r.left) / r.width)) : 0.5,
        fy: r.height ? Math.min(1, Math.max(0, (y - r.top) / r.height)) : 0.5
      },
      where: whereFor(target), state: stateNow(), el: target
    };
    compose.textContent = '';
    var f = el('form', 'form');
    var head = el('div', 'bubble-head');
    head.appendChild(el('b', null, 'New comment'));
    var x2 = el('button', 'x', '×');
    x2.type = 'button'; x2.title = 'Cancel (Esc)';
    x2.onclick = closeComposer;
    head.appendChild(x2);
    f.appendChild(head);
    if (composer.where) f.appendChild(el('div', 'where', composer.where));
    f.appendChild(nameField(f));
    var ta = el('textarea', 'text');
    ta.rows = 3; ta.maxLength = 1000; ta.placeholder = 'Write a comment'; ta.dir = 'auto';
    f.appendChild(ta);
    var row = el('div', 'actions');
    row.appendChild(el('span', 'hint', 'Ctrl + Enter to post'));
    var go = el('button', 'primary', 'Post');
    go.type = 'submit';
    row.appendChild(go);
    f.appendChild(row);
    f.onsubmit = function (e) {
      e.preventDefault();
      var name = f._name.value.trim(), text = ta.value.trim();
      if (!name) { f._name.hidden = false; f.querySelector('.as').hidden = true; f._name.focus(); return; }
      if (!text) { ta.focus(); return; }
      setName(name);
      var c = composer;
      var id = queue({ parent: null, name: name, text: text, where: c.where,
                       anchor: { sel: c.anchor.sel, text: c.anchor.text, tag: c.anchor.tag,
                                 fx: c.anchor.fx, fy: c.anchor.fy },
                       state: c.state });
      closeComposer();
      setPicking(false);
      openId = id;
      bubble._placed = false;
      changed();
      renderBubble('');
    };
    compose.appendChild(f);
    compose.hidden = false;
    placeNear(compose, x, y);
    (f._name.hidden ? ta : f._name).focus();
    hoverBox.style.display = 'none';
  }
  function closeComposer() {
    composer = null;
    compose.hidden = true;
    compose.textContent = '';
  }
  function replyDirty() {
    var ta = bubble.querySelector('textarea');
    return !!(ta && ta.value.trim());
  }
  function composerDirty() {
    if (!composer) return false;
    var ta = compose.querySelector('textarea'), nm = compose.querySelector('input.name');
    return !!((ta && ta.value.trim()) || (nm && !nm.hidden && nm.value.trim() && nm.value.trim() !== getName()));
  }

  // Beside (x, y), inside the viewport, and never over the Comment buttons:
  // a box that reaches their strip at the bottom stops above it.
  function placeNear(box, x, y) {
    var w = box.offsetWidth || 300, h = box.offsetHeight || 200, m = 8;
    var left = x + 16 + w < innerWidth - m ? x + 16 : x - 16 - w;
    left = Math.max(m, Math.min(left, innerWidth - w - m));
    var fab = root.querySelector('.fab').getBoundingClientRect();
    var overFab = left < fab.right + m && left + w > fab.left - m;
    var floor = overFab ? fab.top - m : innerHeight - m;
    var top = Math.max(m, Math.min(y - 24, floor - h));
    box.style.left = left + 'px';
    box.style.top = top + 'px';
  }

  // ---------------------------------------------------------------- pins
  // Redraw on the next frame, and keep redrawing for `ms` to follow page
  // animations. `lazy` is for page mutations: an autoplaying walkthrough types
  // text every 45 ms, and pins only need about 30 redraws a second for that.
  // Scrolling and our own actions redraw on every frame, so pins never lag.
  var raf = 0, busyUntil = 0, smoothUntil = 0, lastDraw = 0, owed = false;
  function schedule(ms, lazy) {
    var until = Date.now() + (ms || 0);
    busyUntil = Math.max(busyUntil, until);
    if (!lazy) smoothUntil = Math.max(smoothUntil, until + 50);
    if (!raf) raf = requestAnimationFrame(frame);
  }
  function frame() {
    raf = 0;
    var now = Date.now();
    if (now <= smoothUntil || now - lastDraw >= 32) { lastDraw = now; owed = false; drawPins(); }
    else owed = true;
    if (now < busyUntil || owed) raf = requestAnimationFrame(frame);
  }

  // One getComputedStyle per element per redraw, shared by every pin.
  var styleCache = null;
  function styleOf(n) {
    if (!styleCache) return getComputedStyle(n);
    var s = styleCache.get(n);
    if (!s) { s = getComputedStyle(n); styleCache.set(n, s); }
    return s;
  }

  var pinNodes = {};
  function drawPins() {
    styleCache = new Map();
    try { drawPinsNow(); } finally { styleCache = null; }
  }
  function drawPinsNow() {
    var seen = {};
    threads.forEach(function (t) {
      var id = t.root.id, p = pinsHidden ? null : pointOf(t.root.anchor, anchorEl(t.root));
      var node = pinNodes[id];
      if (!p) { if (node) node.style.display = 'none'; return; }
      if (!node) {
        node = pinNodes[id] = el('button', 'pin');
        node.type = 'button';
        node.onclick = function (e) { e.stopPropagation(); openThread(node._id, false); };
        node.onmouseenter = function () { showPeek(node._id, node); };
        node.onmouseleave = function () { peek.hidden = true; };
        pinsEl.appendChild(node);
      }
      node._id = id;   // read at click time: a pin outlives the temporary id of an unsaved comment
      node.textContent = String(t.n);
      node.setAttribute('data-n', String(t.n));
      node.classList.toggle('on', id === openId);
      node.classList.toggle('failed', t.root.status === 'failed');
      node.style.display = '';
      node.style.left = Math.round(p.x) + 'px';
      node.style.top = Math.round(p.y) + 'px';
      seen[id] = true;
    });
    Object.keys(pinNodes).forEach(function (id) {
      if (!seen[id] && !threadById(id)) { pinNodes[id].remove(); delete pinNodes[id]; }
    });
    // keep the bubble beside its pin while the page scrolls or animates
    if (openId && !bubble.hidden) {
      var n = pinNodes[openId];
      if (n && n.style.display !== 'none') {
        var r = n.getBoundingClientRect();
        placeNear(bubble, r.right, r.top + 4);
      } else if (!bubble._placed) {
        bubble.style.left = Math.max(8, (innerWidth - bubble.offsetWidth) / 2) + 'px';
        bubble.style.top = '72px';
      }
      bubble._placed = true;
    }
    if (composer && !compose.hidden) {
      var cp = composer.el && composer.el.isConnected ? pointOf(composer.anchor, composer.el) : null;
      if (cp) placeNear(compose, cp.x, cp.y);
    }
    if (flashEl && Date.now() < flashUntil && flashEl.isConnected) {
      var fr = flashEl.getBoundingClientRect();
      setBox(flashBox, fr, 4);
      flashBox.style.display = 'block';
    } else { flashBox.style.display = 'none'; flashEl = null; }
    if (picking) drawCatchers();
  }
  function setBox(box, r, pad) {
    box.style.left = (r.left - pad) + 'px';
    box.style.top = (r.top - pad) + 'px';
    box.style.width = (r.width + pad * 2) + 'px';
    box.style.height = (r.height + pad * 2) + 'px';
  }
  function showPeek(id, node) {
    var t = threadById(id);
    if (!t || id === openId) return;
    peek.textContent = '';
    peek.appendChild(el('b', null, t.root.name));
    var tx = el('div', 'txt clamp', t.root.text);
    tx.dir = 'auto';
    peek.appendChild(tx);
    if (t.replies.length)
      peek.appendChild(el('div', 'meta', t.replies.length + (t.replies.length === 1 ? ' reply' : ' replies')));
    peek.hidden = false;
    var r = node.getBoundingClientRect();
    placeNear(peek, r.right, r.top);
  }

  // Clicks inside an iframe (a map, a video) never reach this window, so in
  // pick mode each visible iframe gets a transparent catcher on top of it.
  function drawCatchers() {
    catchers.textContent = '';
    var frames = document.querySelectorAll('iframe, embed, object');
    for (var i = 0; i < frames.length; i++) {
      var r = frames[i].getBoundingClientRect();
      if (!r.width || !r.height || r.bottom < 0 || r.top > innerHeight) continue;
      var c = el('div', 'catcher');
      setBox(c, r, 0);
      c._target = frames[i];
      catchers.appendChild(c);
    }
  }

  // ---------------------------------------------------------------- threads
  function openThread(id, jump) {
    peek.hidden = true;
    if (composer && !composerDirty()) closeComposer();
    openId = id;
    bubble._placed = false;
    pausePage();
    var t = threadById(id);
    if (!t) return;
    renderBubble('');
    renderPanel();
    schedule(400);
    if (!jump) return;
    locate(t.root).then(function (found) {
      if (openId !== id) return;
      if (found) {
        try { found.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' }); } catch (e) { found.scrollIntoView(); }
        flashEl = found; flashUntil = Date.now() + 1800;
        bubble._placed = false;
        renderBubble('');
        schedule(1900);
      } else {
        bubble._placed = false;
        renderBubble('This part is not on the page any more, or the page changed since. The comment is below.');
        schedule(100);
      }
    });
  }
  function closeThread() {
    openId = null;
    bubble.hidden = true;
    bubbleFor = null;
    renderPanel();
    schedule();
  }

  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function visibleEl(c, strict) {
    if (onItsState(c) === false) return null;
    var e = resolve(c.anchor, strict);
    return e && e.getBoundingClientRect && (e.getBoundingClientRect().width || e.getBoundingClientRect().height) ? e : null;
  }

  // Find the commented part, bringing it back on screen when the page has
  // state (a walkthrough, slides, tabs): 1) already there, 2) the adapter
  // restores the saved state, 3) the adapter searches every state, 4) the
  // saved #hash. Resolves to the element, or null.
  function locate(c) {
    var e = visibleEl(c, true);
    if (e) return Promise.resolve(e);
    return Promise.resolve()
      .then(function () {
        if (A().restore && c.state) return Promise.resolve(A().restore(c.state)).then(function () { return wait(60); });
      })
      .then(function () {
        var e2 = visibleEl(c, true);
        if (e2) return e2;
        if (A().search) {
          var hit = null;
          return Promise.resolve(A().search(function () { return !!(hit = visibleEl(c, true)); }))
            .then(function () {
              if (hit) return hit;
              return Promise.resolve(A().search(function () { return !!(hit = visibleEl(c, false)); }))
                .then(function () { return hit; });
            });
        }
        if (c.state && c.state.hash && c.state.hash !== location.hash) {
          location.hash = c.state.hash;
          return wait(350).then(function () { return visibleEl(c, true) || visibleEl(c, false); });
        }
        return visibleEl(c, false);
      })
      .catch(function () { return null; });
  }

  // ---------------------------------------------------------------- pick mode
  function setPicking(on) {
    picking = on;
    banner.hidden = !on;
    addBtn.classList.toggle('on', on);
    addBtn.querySelector('span').textContent = on ? 'Cancel' : 'Comment';
    document.documentElement.style.cursor = on ? 'crosshair' : '';
    if (on) { pausePage(); closeThread(); drawCatchers(); }
    else { hoverBox.style.display = 'none'; catchers.textContent = ''; hoverEl = null; }
  }

  function fromUi(e) { return e.target === host || (e.composedPath && e.composedPath().indexOf(host) !== -1); }
  function pageTarget(e) {
    if (fromUi(e)) {
      var path = e.composedPath ? e.composedPath() : [];
      for (var i = 0; i < path.length; i++) if (path[i] && path[i]._target) return path[i]._target;
      return null;
    }
    var t = e.target;
    return t && t.nodeType === 1 ? t : (t && t.parentElement) || null;
  }

  function onPointerMove(e) {
    if (!picking || composer) return;
    var t = pageTarget(e);
    if (!t || t === document.documentElement || t === document.body) { hoverBox.style.display = 'none'; hoverEl = null; return; }
    hoverEl = t;
    setBox(hoverBox, t.getBoundingClientRect(), 2);
    hoverBox.style.display = 'block';
  }

  // Swallow the press so the page does not act on it (no button fires, no
  // focus moves) while the reader is only pointing at the part.
  function onPress(e) {
    if (!picking) return;
    var t = pageTarget(e);
    if (!t) return;           // our own UI handles its own clicks
    e.preventDefault();
    e.stopImmediatePropagation();
  }
  function onClick(e) {
    if (!picking) {
      if (openId && !fromUi(e) && !replyDirty()) closeThread(); // click outside closes the bubble
      return;
    }
    var t = pageTarget(e);
    if (!t) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (composer) {
      if (composerDirty()) { var ta = compose.querySelector('textarea'); ta.focus(); shake(compose); return; }
      closeComposer();
    }
    openComposer(t, e.clientX, e.clientY);
  }
  function shake(node) {
    node.classList.remove('shake'); void node.offsetWidth; node.classList.add('shake');
  }

  // Keys typed in the comment UI never reach the page. In pick mode the
  // page's playback keys are off too. Our own shortcuts are handled here,
  // because stopping the event at window capture also hides it from us.
  function onKey(e) {
    var ours = fromUi(e);
    if (e.type === 'keydown' && e.key === 'Escape' && (ours || picking || openId || panelOpen)) {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (composer) { if (!composerDirty() || confirmDrop()) closeComposer(); return; }
      if (picking) { setPicking(false); return; }
      if (openId) { if (!replyDirty() || confirmDrop()) closeThread(); return; }
      if (panelOpen) { panelOpen = false; renderPanel(); }
      return;
    }
    if (ours) {
      if (e.type === 'keydown' && e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        var path = e.composedPath ? e.composedPath() : [];
        for (var i = 0; i < path.length; i++) {
          if (path[i] && path[i].tagName === 'FORM') { e.preventDefault(); path[i].requestSubmit ? path[i].requestSubmit() : path[i].onsubmit(e); break; }
        }
      }
      e.stopImmediatePropagation();
      return;
    }
    if (picking && /^( |Spacebar|Arrow(Left|Right|Up|Down)|Enter|PageUp|PageDown)$/.test(e.key)) {
      e.stopImmediatePropagation();
    }
  }
  function confirmDrop() { return window.confirm('Discard this comment?'); }

  // ---------------------------------------------------------------- wiring
  $('.fab-list').onclick = function () {
    panelOpen = !panelOpen;
    renderPanel();
    if (panelOpen && Date.now() - lastFetch > 5000) refresh();
  };
  addBtn.onclick = function () {
    if (composer && composerDirty() && !confirmDrop()) return;
    closeComposer();
    setPicking(!picking);
  };
  $('.banner-x').onclick = function () { closeComposer(); setPicking(false); };

  window.addEventListener('keydown', onKey, true);
  window.addEventListener('keyup', onKey, true);
  window.addEventListener('keypress', onKey, true);
  window.addEventListener('pointerdown', onPress, true);
  window.addEventListener('mousedown', onPress, true);
  window.addEventListener('mouseup', onPress, true);
  window.addEventListener('pointerup', onPress, true);
  window.addEventListener('click', onClick, true);
  window.addEventListener('pointermove', onPointerMove, { capture: true, passive: true });
  window.addEventListener('scroll', function () { schedule(120); }, { capture: true, passive: true });
  window.addEventListener('resize', function () { schedule(120); });
  window.addEventListener('transitionend', function () { schedule(50); }, true);
  window.addEventListener('animationend', function () { schedule(50); }, true);
  window.addEventListener('hashchange', function () { schedule(600); });
  window.addEventListener('online', retryFailed);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible' && Date.now() - lastFetch > 5000) refresh();
  });
  setInterval(function () { if (document.visibilityState === 'visible') refresh(); }, POLL_MS);
  setInterval(function () { refreshTimes(); }, 60000);
  function refreshTimes() { if (panelOpen) renderPanel(); if (openId) renderBubble(); }

  // Events that start inside the comment UI end at its edge. Without this, a
  // click on "Comment" or into the text box bubbles on to the page, and a deck
  // that turns the slide on any click (or swipe, or wheel) moves under the
  // reader. Our own handlers have already run by then: they sit inside the
  // shadow root, or on window in the capture phase.
  function shield() {
    var stop = function (e) { e.stopPropagation(); };
    ['click', 'dblclick', 'auxclick', 'contextmenu', 'mousedown', 'mouseup', 'pointerdown', 'pointerup',
     'input', 'change', 'focusin', 'focusout'].forEach(function (t) { host.addEventListener(t, stop); });
    ['touchstart', 'touchmove', 'touchend', 'wheel'].forEach(function (t) {
      host.addEventListener(t, stop, { passive: true });
    });
  }

  function start() {
    mount();
    shield();
    new MutationObserver(function () {
      if (threads.length || picking || composer) schedule(700, true); // nothing on screen, nothing to redraw
    }).observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
    pending.forEach(function (c) { if (c.status === 'sending') c.status = 'failed'; });
    changed();
    refresh().then(retryFailed);
  }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);

  // test and console hook; not part of the page contract
  window.__artifactComments = { refresh: refresh, slug: SLUG, version: VERSION,
                                threads: function () { return threads; } };

  // ---------------------------------------------------------------- style
  function CSS_TEXT() {
    return [
      ':host{all:initial}',
      '.layer{position:fixed;inset:0;pointer-events:none;z-index:2147483000;font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#1f2328;direction:ltr;text-align:left}',
      '.layer *{box-sizing:border-box}',
      '[hidden]{display:none!important}',
      'button{font:inherit;color:inherit;cursor:pointer}',
      '.fab{position:fixed;bottom:18px;display:flex;gap:8px;pointer-events:auto}',
      '.fab.right{right:18px}.fab.left{left:18px}',
      '.fab button{display:flex;align-items:center;gap:6px;border:1px solid #d0d7de;background:#fff;border-radius:999px;padding:8px 14px;box-shadow:0 2px 10px rgba(0,0,0,.14)}',
      '.fab button:hover{background:#f6f8fa}',
      '.fab .count{background:#1c6e4f;color:#fff;border-radius:999px;padding:0 7px;font-size:12px;line-height:18px}',
      '.fab-add.on{background:#1c6e4f;border-color:#1c6e4f;color:#fff}.fab-add.on:hover{background:#145239}',
      '.banner{position:fixed;top:12px;left:50%;transform:translateX(-50%);background:#1c6e4f;color:#fff;border-radius:999px;padding:8px 10px 8px 16px;display:flex;gap:10px;align-items:center;pointer-events:auto;box-shadow:0 4px 16px rgba(0,0,0,.2);white-space:nowrap;max-width:calc(100vw - 24px)}',
      '.banner-x{background:rgba(255,255,255,.18);border:0;border-radius:999px;padding:3px 10px;color:#fff}',
      '.kbd{font-size:11px;opacity:.8;border:1px solid rgba(255,255,255,.5);border-radius:4px;padding:0 5px}',
      '.hover{position:fixed;display:none;border:2px solid #1c6e4f;background:rgba(28,110,79,.06);border-radius:4px;pointer-events:none}',
      '.flash{position:fixed;display:none;border:3px solid #e0a52e;border-radius:6px;pointer-events:none;animation:ac-flash 1.8s ease-out}',
      '@keyframes ac-flash{0%,40%{opacity:1}100%{opacity:0}}',
      '.catcher{position:fixed;pointer-events:auto;cursor:crosshair;background:transparent}',
      '.pin{position:fixed;pointer-events:auto;width:28px;height:28px;margin:-28px 0 0 0;border-radius:14px 14px 14px 3px;border:2px solid #fff;background:#1c6e4f;color:#fff;font:700 12px/24px system-ui,sans-serif;text-align:center;padding:0;box-shadow:0 2px 8px rgba(0,0,0,.35);transition:transform .12s}',
      '.pin:hover{transform:scale(1.12);transform-origin:bottom left}',
      '.pin.on{background:#0d3b2a;transform:scale(1.15);transform-origin:bottom left}',
      '.pin.failed{background:#b42318}',
      '.bubble,.compose,.peek,.panel{position:fixed;pointer-events:auto;background:#fff;border:1px solid #d0d7de;border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,.22)}',
      '.bubble,.compose{width:min(320px,calc(100vw - 16px));padding:12px;max-height:calc(100vh - 84px);display:flex;flex-direction:column}',
      '.peek{width:min(240px,calc(100vw - 16px));padding:8px 10px;font-size:13px;pointer-events:none}',
      '.bubble-head{display:flex;align-items:center;gap:8px;margin-bottom:6px}',
      '.bubble-head .where{flex:1;color:#57606a;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.bubble-head b{flex:1}',
      '.num{flex:none;display:inline-block;min-width:22px;height:22px;border-radius:11px 11px 11px 3px;background:#1c6e4f;color:#fff;font-size:11px;font-weight:700;line-height:22px;text-align:center;padding:0 5px}',
      '.x{border:0;background:none;font-size:20px;line-height:1;color:#57606a;padding:0 4px;border-radius:6px}.x:hover{background:#f3f4f6;color:#1f2328}',
      '.note{background:#fff8e6;border:1px solid #f0d9a0;border-radius:8px;padding:6px 8px;font-size:12px;margin-bottom:6px}',
      '.quote{color:#57606a;font-size:12px;border-left:3px solid #d0d7de;padding-left:8px;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.msgs{overflow:auto;min-height:0;flex:1 1 auto;margin:0 -4px;padding:0 4px}',
      '.msg{padding:6px 0;border-top:1px solid #eef0f2}.msg:first-child{border-top:0}',
      '.msg-head{display:flex;align-items:center;gap:6px}',
      '.avatar{flex:none;width:20px;height:20px;border-radius:50%;background:#e7f2ed;color:#1c6e4f;font-size:11px;font-weight:700;line-height:20px;text-align:center}',
      '.who{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:60%}',
      '.when{color:#8c959f;font-size:12px;margin-left:auto;white-space:nowrap}',
      '.txt{white-space:pre-wrap;overflow-wrap:anywhere;margin-top:2px}',
      '.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}',
      '.status{font-size:12px;color:#8c959f;margin-top:2px}.status.failed{color:#b42318}',
      '.link{border:0;background:none;padding:0;color:#1c6e4f;text-decoration:underline;font-size:12px}',
      '.form{display:flex;flex-direction:column;gap:6px;margin-top:8px}',
      '.compose .form{margin-top:0}',
      '.where{color:#57606a;font-size:12px}',
      '.as{font-size:12px;color:#57606a}',
      'input.name,textarea.text{width:100%;border:1px solid #d0d7de;border-radius:8px;padding:7px 9px;font:inherit;color:inherit;background:#fff;resize:vertical}',
      'input.name:focus,textarea.text:focus{outline:2px solid #1c6e4f;outline-offset:-1px;border-color:#1c6e4f}',
      '.actions{display:flex;align-items:center;justify-content:flex-end;gap:8px}',
      '.hint{color:#8c959f;font-size:11px;margin-right:auto}',
      '.primary{border:0;border-radius:8px;background:#1c6e4f;color:#fff;padding:7px 14px;font-weight:600}.primary:hover{background:#145239}',
      '.panel{bottom:66px;width:min(360px,calc(100vw - 24px));max-height:min(70vh,calc(100vh - 90px));display:flex;flex-direction:column;overflow:hidden}',
      '.panel{right:18px}',
      '.panel-head{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid #eef0f2}',
      '.panel-tools{display:flex;align-items:center;gap:8px}',
      '.rows{overflow:auto;padding:4px}',
      '.row{display:block;width:100%;text-align:left;border:0;background:none;border-radius:8px;padding:8px 10px}',
      '.row:hover{background:#f6f8fa}.row.on{background:#e7f2ed}',
      '.row-head{display:flex;align-items:center;gap:8px;margin-bottom:2px}',
      '.meta{color:#1c6e4f;font-size:12px;margin-top:2px}',
      '.empty{padding:12px;margin:0;color:#57606a}',
      '.panel-foot{flex:none;padding:6px 12px;border-top:1px solid #eef0f2;color:#8c959f;font-size:11px}',
      '.foot-link{color:#1c6e4f;text-decoration:underline}.foot-link:hover{color:#145239}',
      '.shake{animation:ac-shake .3s}',
      '@keyframes ac-shake{25%{transform:translateX(-4px)}75%{transform:translateX(4px)}}',
      '@media print{.layer{display:none}}'
    ].join('\n') + (POSITION === 'left' ? '\n.panel{right:auto;left:18px}' : '');
  }
})();
