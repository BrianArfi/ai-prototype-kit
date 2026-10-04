#!/usr/bin/env python3
"""End-to-end tests for artifact-comments, in a real browser against a real
backend. Nothing touches the cloud. The same suite runs on either backend:

  wrangler  the Cloudflare Pages Function on a local KV (wrangler pages dev)
  node      the self-hosted server (server/node/server.mjs) on a fresh SQLite file

  pip install playwright && python -m playwright install chromium
  python tests/e2e_test.py                    # the full suite, wrangler backend
  python tests/e2e_test.py --backend node     # the same suite on the node server
  python tests/e2e_test.py --backend both     # one after the other
  python tests/e2e_test.py --headed           # watch it run

Needs Node.js: npx for wrangler, Node 22.13 or later for the node server.
Exit code 0 means every check passed. Other suites (a page with its own
adapter) can reuse `Server` and `Checks`.
"""
import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


# ---------------------------------------------------------------- harness
def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def inject(html, slug):
    if 'artifact-comments.js' in html:
        return html
    tag = f'<script src="/artifact-comments.js" data-slug="{slug}" defer></script>\n'
    at = html.lower().rfind('</body>')
    return html[:at] + tag + html[at:] if at != -1 else html + tag


class Server:
    """A backend on a throwaway copy of the skill, with fresh storage every run.

    backend='wrangler' runs the Pages Function under `wrangler pages dev` with a
    local KV; backend='node' runs server/node/server.mjs on a new SQLite file.
    Both serve the same site folder and allow CORS for `allow_origin` (by
    default http://localhost:<port>, a second origin for the same server).
    `token` is the owner key on both: OWNER_KEY on wrangler, --token on node.
    """

    def __init__(self, pages=None, backend='wrangler', allow_origin=None, token='e2e-owner-token'):
        if backend not in ('wrangler', 'node'):
            raise ValueError(f'unknown backend {backend!r}')
        self.pages = pages or {}   # slug -> path of an extra html page to serve
        self.backend = backend
        self.port = free_port()
        self.base = f'http://127.0.0.1:{self.port}'
        self.allow_origin = allow_origin or f'http://localhost:{self.port}'
        self.token = token

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix='artifact-comments-e2e-')
        site = os.path.join(self.dir, 'site')
        os.makedirs(os.path.join(self.dir, 'functions', 'api'))
        os.makedirs(site)
        shutil.copyfile(os.path.join(SKILL, 'functions', 'api', 'comments.js'),
                        os.path.join(self.dir, 'functions', 'api', 'comments.js'))
        shutil.copyfile(os.path.join(SKILL, 'client', 'artifact-comments.js'),
                        os.path.join(site, 'artifact-comments.js'))
        shutil.copyfile(os.path.join(SKILL, 'examples', 'demo.html'), os.path.join(site, 'demo.html'))
        for slug, path in self.pages.items():
            with open(path, encoding='utf-8') as fh:
                html = inject(fh.read(), slug)
            with open(os.path.join(site, slug + '.html'), 'w', encoding='utf-8') as fh:
                fh.write(html)
        # Opened as http://localhost:<port>/xorigin, it is another origin than the
        # API at http://127.0.0.1:<port>, so its comments travel through CORS.
        with open(os.path.join(site, 'xorigin.html'), 'w', encoding='utf-8') as fh:
            fh.write('<!doctype html><html><body><main style="padding:160px 40px"><h1 id="x">Another origin</h1></main>'
                     f'<script src="{self.base}/artifact-comments.js" data-slug="xorigin" '
                     f'data-api="{self.base}/api/comments" defer></script></body></html>')
        self.log_path = os.path.join(self.dir, self.backend + '.log')
        self.log = open(self.log_path, 'w')
        if self.backend == 'wrangler':
            npx = shutil.which('npx') or shutil.which('npx.cmd')
            if not npx:
                sys.exit('npx not found: install Node.js to run wrangler')
            cmd = [npx, '--yes', 'wrangler@4', 'pages', 'dev', 'site', '--kv=COMMENTS',
                   '--binding', f'ALLOWED_ORIGINS={self.allow_origin}', f'OWNER_KEY={self.token}',
                   '--port', str(self.port), '--ip', '127.0.0.1', '--persist-to', 'state']
        else:
            node = shutil.which('node') or shutil.which('node.exe')
            if not node:
                sys.exit('node not found: install Node.js 22.13 or later')
            os.makedirs(os.path.join(self.dir, 'state'))
            cmd = [node, '--no-warnings=ExperimentalWarning',
                   os.path.join(SKILL, 'server', 'node', 'server.mjs'),
                   '--port', str(self.port), '--host', '127.0.0.1',
                   '--db', os.path.join(self.dir, 'state', 'comments.db'),
                   '--static', site, '--allow-origin', self.allow_origin, '--token', self.token]
        self.proc = subprocess.Popen(cmd, cwd=self.dir, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                urllib.request.urlopen(self.base + '/api/comments?slug=probe', timeout=2)
                return self
            except Exception:
                if self.proc.poll() is not None:
                    break
                time.sleep(0.5)
        self.log.flush()
        with open(self.log_path, encoding='utf-8', errors='replace') as fh:
            tail = fh.read()[-2000:]
        self.__exit__()
        sys.exit(f'the {self.backend} backend did not start:\n{tail}')

    def __exit__(self, *a):
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.proc.pid)], capture_output=True)
        else:
            self.proc.terminate()
        try:
            self.proc.wait(10)
        except Exception:
            pass
        self.log.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def post(self, body):
        req = urllib.request.Request(self.base + '/api/comments', method='POST',
                                     data=json.dumps(body).encode(), headers={'content-type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def delete(self, body, owner=None):
        headers = {'content-type': 'application/json'}
        if owner:
            headers['authorization'] = f'Bearer {owner}'
        st, _, raw = self.raw('DELETE', data=json.dumps(body).encode(), headers=headers)
        return st, json.loads(raw or b'{}')

    def get(self, slug):
        with urllib.request.urlopen(f'{self.base}/api/comments?slug={slug}', timeout=10) as r:
            return json.load(r)['comments']

    def raw(self, method, path='/api/comments', data=None, headers=None):
        """Any request; returns (status, headers with lowercase keys, body bytes)."""
        req = urllib.request.Request(self.base + path, method=method, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
        except urllib.error.HTTPError as e:
            return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()

    def cli(self, *args):
        """Run scripts/comments_cli.py; returns (exit code, stdout plus stderr)."""
        env = dict(os.environ)
        env.pop('ARTIFACT_COMMENTS_TOKEN', None)
        r = subprocess.run([sys.executable, os.path.join(SKILL, 'scripts', 'comments_cli.py'), *args],
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=env, timeout=60)
        return r.returncode, (r.stdout or '') + (r.stderr or '')


class Checks:
    def __init__(self):
        self.rows = []

    def ok(self, name, cond, detail=''):
        self.rows.append((bool(cond), name, detail))
        print(('  PASS  ' if cond else '  FAIL  ') + name + (f'  ({detail})' if detail and not cond else ''))
        return bool(cond)

    @property
    def failed(self):
        return [r for r in self.rows if not r[0]]

    def summary(self):
        print(f'\n{len(self.rows) - len(self.failed)}/{len(self.rows)} checks passed')
        return 0 if not self.failed else 1


# ---------------------------------------------------------------- page helpers
UI = 'artifact-comments'   # Playwright CSS selectors pierce the open shadow root


async def open_page(browser, url, **ctx):
    context = await browser.new_context(viewport=ctx.pop('viewport', {'width': 1280, 'height': 860}), **ctx)
    page = await context.new_page()
    page.errors = []
    page.on('pageerror', lambda e: page.errors.append(str(e)))
    page.accept_dialogs = False   # set True to answer confirm() with OK
    page.on('dialog', lambda d: asyncio.ensure_future(d.accept() if page.accept_dialogs else d.dismiss()))
    await page.goto(url, wait_until='domcontentloaded')
    await page.wait_for_selector(f'{UI} .fab-add', state='attached')
    await page.wait_for_timeout(400)
    return page


async def count(page):
    return int(await page.locator(f'{UI} .count').inner_text())


async def visible_pins(page):
    return await page.locator(f'{UI} .pin:visible').count()


async def pick_and_post(page, target, name, text, offset=None, submit='click'):
    await page.locator(f'{UI} .fab-add').click()
    box = await page.locator(target).first.bounding_box()
    ox, oy = offset or (box['width'] / 2, box['height'] / 2)
    x, y = box['x'] + ox, box['y'] + oy
    await page.mouse.move(x, y)
    await page.mouse.click(x, y)
    await page.wait_for_selector(f'{UI} .compose:not([hidden]) textarea')
    name_box = page.locator(f'{UI} .compose input.name')
    if name and await name_box.is_visible():
        await name_box.fill(name)
    await page.locator(f'{UI} .compose textarea').fill(text)
    if submit == 'keys':
        await page.locator(f'{UI} .compose textarea').press('Control+Enter')
    else:
        await page.locator(f'{UI} .compose .primary').click()
    await page.wait_for_timeout(700)
    return x, y


# ---------------------------------------------------------------- the suite
async def suite(srv, c, headed=False):
    from playwright.async_api import async_playwright
    url = srv.base + '/demo'
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        p = await open_page(browser, url)

        c.ok('loads with no script errors', not p.errors, p.errors)
        font = await p.locator(f'{UI} .fab-add').evaluate('b => getComputedStyle(b).fontFamily')
        c.ok('page CSS does not leak into the comment UI', 'Georgia' not in font, font)
        c.ok('starts with zero comments', await count(p) == 0)

        # clicks inside the comment UI never reach the page (a deck would turn the slide)
        await p.locator(f'{UI} .fab-list').click()
        await p.locator(f'{UI} .panel .x').click()
        await p.locator(f'{UI} .fab-add').click()
        await p.locator(f'{UI} .banner-x').click()
        await p.mouse.wheel(0, 0)
        c.ok('clicks on the comment buttons do not reach the page', await p.locator('#clicks').inner_text() == '0',
             await p.locator('#clicks').inner_text())

        # pick mode swallows the page's own click
        await p.locator(f'{UI} .fab-add').click()
        c.ok('pick mode shows the banner', await p.locator(f'{UI} .banner').is_visible())
        await p.locator('#last').hover()
        await p.wait_for_timeout(100)
        hb, lb = await p.locator(f'{UI} .hover').bounding_box(), await p.locator('#last').bounding_box()
        c.ok('hovering a part outlines exactly that part',
             hb and lb and abs(hb['x'] - (lb['x'] - 2)) <= 1 and abs(hb['width'] - (lb['width'] + 4)) <= 1, (hb, lb))
        await p.locator('#tabs button[data-tab="c"]').click()
        tab_now = await p.evaluate("document.querySelector('#tabs .on').dataset.tab")
        c.ok('a click in pick mode does not trigger the page (tab unchanged)', tab_now == 'a', tab_now)
        c.ok('...it opens the comment form instead', await p.locator(f'{UI} .compose').is_visible())

        # keys typed in the form never reach the page
        ta = p.locator(f'{UI} .compose textarea')
        await ta.click()
        await p.keyboard.type('space bar test ok')
        await p.keyboard.press('ArrowLeft')
        spaces = await p.locator('#spaces').inner_text()
        c.ok('typing spaces in a comment does not reach the page', spaces == '0', spaces)
        c.ok('...and the spaces land in the text', await ta.input_value() == 'space bar test ok')

        # a name is required and the form says so
        await p.locator(f'{UI} .compose .primary').click()
        await p.wait_for_timeout(300)
        focused = await p.evaluate("document.querySelector('artifact-comments').shadowRoot.activeElement?.className")
        c.ok('posting without a name asks for the name', focused == 'name' and await count(p) == 0, focused)
        await p.keyboard.press('Escape')   # dirty form: confirm() is dismissed, so the form stays
        c.ok('Esc on a form with text does not throw the text away', await ta.is_visible())
        await ta.fill('')
        await p.keyboard.press('Escape')
        c.ok('Esc on an empty form closes it', not await p.locator(f'{UI} .compose').is_visible())
        await p.keyboard.press('Escape')
        c.ok('Esc again leaves pick mode', not await p.locator(f'{UI} .banner').is_visible())

        # post a comment: Figma-style pin exactly where the click was
        x, y = await pick_and_post(p, '#title', 'Rina', 'Title is too long', offset=(40, 12))
        pin = await p.locator(f'{UI} .pin').first.bounding_box()
        c.ok('a pin appears at the clicked point', pin and abs(pin['x'] - x) <= 3 and abs(pin['y'] + pin['height'] - y) <= 3,
             f'pin {pin} click {(x, y)}')
        c.ok('the count shows one thread', await count(p) == 1)
        c.ok('posting leaves pick mode', not await p.locator(f'{UI} .banner').is_visible())
        c.ok('the new thread opens beside its pin', await p.locator(f'{UI} .bubble').is_visible())
        c.ok('the empty notice box is not shown', not await p.locator(f'{UI} .bubble .note').is_visible())

        # reply with Ctrl+Enter
        rta = p.locator(f'{UI} .bubble textarea')
        await rta.fill('Agreed, cut it to five words')
        await rta.press('Control+Enter')
        await p.wait_for_timeout(700)
        msgs = await p.locator(f'{UI} .bubble .msg').count()
        c.ok('Ctrl+Enter posts a reply into the thread', msgs == 2, msgs)
        c.ok('a reply does not add a pin or a thread', await count(p) == 1 and await visible_pins(p) == 1)
        c.ok('the saved name is reused for the reply', 'Rina' in await p.locator(f'{UI} .bubble .msg').nth(1).inner_text())
        await p.keyboard.press('Escape')
        c.ok('Esc closes the thread', not await p.locator(f'{UI} .bubble').is_visible())

        # clicking the pin opens the thread
        await p.locator(f'{UI} .pin').first.click()
        c.ok('clicking a pin opens its thread', await p.locator(f'{UI} .bubble').is_visible())
        # low on a short screen, the thread must stop above the Comment buttons
        await p.set_viewport_size({'width': 1280, 'height': 420})
        await p.wait_for_timeout(300)
        bb, fb = await p.locator(f'{UI} .bubble').bounding_box(), await p.locator(f'{UI} .fab').bounding_box()
        overlap = bb['x'] < fb['x'] + fb['width'] and bb['x'] + bb['width'] > fb['x'] and bb['y'] + bb['height'] > fb['y']
        c.ok('a thread never covers the Comment buttons', not overlap, (bb, fb))
        await p.set_viewport_size({'width': 1280, 'height': 860})
        await p.wait_for_timeout(200)
        clicks_before = await p.locator('#clicks').inner_text()
        await p.locator(f'{UI} .bubble textarea').click()
        await p.locator(f'{UI} .bubble textarea').fill('draft I am still writing')
        c.ok('clicks inside a thread do not reach the page', await p.locator('#clicks').inner_text() == clicks_before)
        await p.keyboard.press('Escape')      # confirm() is dismissed: keep the draft
        c.ok('Esc on a half-typed reply keeps the thread and the draft',
             await p.locator(f'{UI} .bubble').is_visible()
             and await p.locator(f'{UI} .bubble textarea').input_value() == 'draft I am still writing')
        await p.locator(f'{UI} .bubble textarea').fill('')
        await p.mouse.click(5, 400)
        c.ok('clicking the page closes the thread', not await p.locator(f'{UI} .bubble').is_visible())

        # a comment on another tab: hidden pin, then jump from the list
        await p.locator('#tabs button[data-tab="b"]').click()
        await pick_and_post(p, '.price', None, 'Show the yearly price too')
        await p.keyboard.press('Escape')
        await p.locator('#tabs button[data-tab="a"]').click()
        await p.wait_for_timeout(300)
        c.ok('a pin on a hidden tab is hidden', await visible_pins(p) == 1, await visible_pins(p))
        await p.locator(f'{UI} .fab-list').click()
        rows = p.locator(f'{UI} .panel .row')
        c.ok('the list shows both threads', await rows.count() == 2)
        c.ok('the list shows where each comment is', 'Tab: Pricing' in await rows.nth(1).inner_text())
        c.ok('the list shows the reply count', '1 reply' in await rows.nth(0).inner_text())
        foot = p.locator(f'{UI} .panel .panel-foot')
        foot_text = await foot.inner_text() if await foot.count() else ''
        href = await foot.locator('a').get_attribute('href') if await foot.count() else None
        version = await p.evaluate('window.__artifactComments.version')
        c.ok('the list footer shows the version and links to the changelog',
             f'artifact-comments v{version}' in foot_text and "What's new" in foot_text
             and bool(href) and href.endswith('CHANGELOG.md'), (version, foot_text, href))
        await rows.nth(1).click()
        await p.wait_for_timeout(900)
        tab_now = await p.evaluate("document.querySelector('#tabs .on').dataset.tab")
        c.ok('clicking a listed comment brings its tab back', tab_now == 'b', tab_now)
        c.ok('...shows its pin and opens its thread',
             await visible_pins(p) == 2 and await p.locator(f'{UI} .bubble').is_visible())
        c.ok('...and flashes the part', await p.locator(f'{UI} .flash').is_visible())

        # a part inside a scroll box: never drawn outside the box
        await p.keyboard.press('Escape')
        await p.locator('#deep').scroll_into_view_if_needed()
        await pick_and_post(p, '#deep', None, 'Deep line')
        await p.keyboard.press('Escape')
        await p.evaluate("document.getElementById('box').scrollTop = 0")
        await p.wait_for_timeout(300)
        n_pins = await visible_pins(p)
        c.ok('a pin scrolled out of its box is hidden, not drawn over the page', n_pins == 2, n_pins)
        await p.locator(f'{UI} .panel .row').nth(2).click()
        await p.wait_for_timeout(1200)
        box_top = await p.evaluate("document.getElementById('box').scrollTop")
        c.ok('jumping scrolls the box back to the part',
             box_top > 0 and await p.locator(f'{UI} .pin[data-n="3"]').is_visible(), box_top)

        # an iframe cannot be clicked into, so a catcher sits on it
        await p.keyboard.press('Escape')
        await p.locator('#frame').scroll_into_view_if_needed()
        await pick_and_post(p, '#frame', None, 'Frame note')
        c.ok('a part inside an iframe can be commented', await count(p) == 4)
        await p.keyboard.press('Escape')

        # the pin follows the page when it scrolls
        await p.evaluate('window.scrollTo(0, 0)')
        await p.wait_for_timeout(300)
        before = await p.locator(f'{UI} .pin').first.bounding_box()
        await p.evaluate('window.scrollBy(0, 60)')
        await p.wait_for_timeout(300)
        after = await p.locator(f'{UI} .pin').first.bounding_box()
        c.ok('pins move with the page on scroll', before and after and abs((before['y'] - after['y']) - 60) <= 2,
             f'{before} -> {after}')

        # hide pins, remembered across a reload
        await p.locator(f'{UI} .fab-list').click()
        if not await p.locator(f'{UI} .panel').is_visible():
            await p.locator(f'{UI} .fab-list').click()
        await p.locator(f'{UI} .panel .link').first.click()
        await p.wait_for_timeout(150)
        c.ok('Hide pins hides every pin', await visible_pins(p) == 0)
        await p.reload(wait_until='domcontentloaded')
        await p.wait_for_timeout(900)
        c.ok('...and stays hidden after a reload', await visible_pins(p) == 0)
        await p.locator(f'{UI} .fab-list').click()
        await p.locator(f'{UI} .panel .link').first.click()
        await p.locator(f'{UI} .fab-list').click()
        c.ok('Show pins brings them back', await visible_pins(p) >= 1)

        # a second reader sees everything and replies
        q = await open_page(browser, url)
        await q.wait_for_timeout(600)
        c.ok('another reader sees every thread', await count(q) == 4)
        await q.locator(f'{UI} .pin').first.click()
        c.ok('...and the replies', await q.locator(f'{UI} .bubble .msg').count() == 2)
        name_box = q.locator(f'{UI} .bubble input.name')
        c.ok('a new reader is asked for a name', await name_box.is_visible())
        await name_box.fill('Omar')
        await q.locator(f'{UI} .bubble textarea').fill('Fine by me')
        await q.locator(f'{UI} .bubble .primary').click()
        await q.wait_for_timeout(700)

        # the first reader is typing a reply while the refresh lands
        await p.locator(f'{UI} .pin').first.click()
        await p.locator(f'{UI} .bubble textarea').fill('half-typed reply')
        await p.evaluate('window.__artifactComments.refresh()')
        await p.wait_for_timeout(700)
        c.ok('a refresh shows the other reader\'s reply', await p.locator(f'{UI} .bubble .msg').count() == 3)
        c.ok('...without wiping the reply being typed',
             await p.locator(f'{UI} .bubble textarea').input_value() == 'half-typed reply')
        await p.mouse.click(5, 400)
        c.ok('a click outside keeps a thread with a half-typed reply open', await p.locator(f'{UI} .bubble').is_visible())
        await p.locator(f'{UI} .bubble .x').click()

        # hostile input renders as text
        await q.evaluate('window.__xss = 0')
        await q.locator(f'{UI} .bubble .x').click() if await q.locator(f'{UI} .bubble').is_visible() else None
        await q.locator(f'{UI} .fab-add').click()
        await q.mouse.click(300, 300)
        await q.locator(f'{UI} .compose textarea').fill('<img src=x onerror="window.__xss=1"> <b>bold?</b>')
        await q.locator(f'{UI} .compose .primary').click()
        await q.wait_for_timeout(800)
        shown = await q.locator(f'{UI} .bubble .msg .txt').first.inner_text()
        c.ok('markup in a comment is shown as text, never run',
             await q.evaluate('window.__xss') == 0 and '<b>bold?</b>' in shown, shown)

        # offline: the comment is kept, marked, and retried
        await q.keyboard.press('Escape')
        await q.context.set_offline(True)
        await q.locator(f'{UI} .fab-add').click()
        await q.mouse.click(300, 360)
        await q.locator(f'{UI} .compose textarea').fill('Written on a train')
        await q.locator(f'{UI} .compose .primary').click()
        await q.wait_for_timeout(700)
        c.ok('offline, the comment shows "Not sent" with Retry',
             'Not sent' in await q.locator(f'{UI} .bubble').inner_text())
        await q.context.set_offline(False)
        await q.wait_for_timeout(300)            # the browser's "online" event retries by itself
        retry = q.locator(f'{UI} .bubble .status .link', has_text='Retry')
        if await retry.count():
            await retry.click()
        await q.wait_for_timeout(900)
        c.ok('it is sent once back online', 'Not sent' not in await q.locator(f'{UI} .bubble').inner_text())
        c.ok('...and the server has it', any(x['text'] == 'Written on a train' for x in srv.get('demo')))

        # a server error: kept, marked, and the Retry button sends it
        await q.route('**/api/comments', lambda r: r.fulfill(status=500, body='{"error":"boom"}')
                      if r.request.method == 'POST' else r.continue_())
        await q.locator(f'{UI} .bubble textarea').fill('Retry me')
        await q.locator(f'{UI} .bubble .primary').click()
        await q.wait_for_timeout(600)
        failed = q.locator(f'{UI} .bubble .status.failed')
        c.ok('a server error marks the reply "Not sent"', await failed.count() == 1)
        await q.unroute('**/api/comments')
        await failed.locator('.link', has_text='Retry').click()
        await q.wait_for_timeout(900)
        c.ok('Retry sends it', await q.locator(f'{UI} .bubble .status.failed').count() == 0
             and any(x['text'] == 'Retry me' for x in srv.get('demo')))

        # small screen: forms and the list stay inside the viewport
        m = await open_page(browser, url, viewport={'width': 390, 'height': 740}, is_mobile=True, has_touch=True)
        await m.locator(f'{UI} .fab-add').click()
        await m.mouse.click(370, 200)
        box = await m.locator(f'{UI} .compose').bounding_box()
        c.ok('on a phone the form fits the screen', box and box['x'] >= 0 and box['x'] + box['width'] <= 390
             and box['y'] + box['height'] <= 740, box)
        await m.keyboard.press('Escape')
        await m.keyboard.press('Escape')
        await m.locator(f'{UI} .fab-list').click()
        box = await m.locator(f'{UI} .panel').bounding_box()
        c.ok('on a phone the list fits the screen', box and box['x'] >= 0 and box['x'] + box['width'] <= 390, box)

        # records written by the first version still show
        legacy = await browser.new_context(viewport={'width': 1280, 'height': 860})
        lp = await legacy.new_page()
        await lp.route('**/api/comments?slug=*', lambda r: r.fulfill(
            status=200, content_type='application/json',
            body=json.dumps({'comments': [
                {'id': 'old1abc', 'name': 'Legacy', 'text': 'from v1', 'ctx': 'screen: Title', 'sel': '#title',
                 'at': '2026-09-29T10:00:00Z'},
                {'id': 'orphan1', 'name': 'Late', 'text': 'reply whose thread has not arrived', 'parent': 'notyet1',
                 'at': '2026-09-29T10:01:00Z'}]})))
        await lp.goto(url, wait_until='domcontentloaded')
        await lp.wait_for_timeout(900)
        c.ok('comments stored by the first version still get a pin', await visible_pins(lp) == 1)
        c.ok('a reply whose thread has not arrived yet stays hidden, not a phantom thread',
             int(await lp.locator(f'{UI} .count').inner_text()) == 1)

        errors = p.errors + q.errors + m.errors
        c.ok('no script errors in any reader', not errors, errors)

        # a page on another origin posts through CORS (data-api points across origins)
        xp = await open_page(browser, srv.allow_origin.rstrip('/') + '/xorigin')
        await pick_and_post(xp, '#x', 'Cross', 'Posted from another origin')
        await xp.wait_for_timeout(500)
        c.ok('CORS: a page on an allowed origin posts and reads through data-api',
             any(x['text'] == 'Posted from another origin' for x in srv.get('xorigin'))
             and 'Not sent' not in await xp.locator(f'{UI} .bubble').inner_text())

        # deleting: authors delete their own comments, the owner deletes any
        await deleting(srv, c, browser, p, q, url)
        await browser.close()

    # ---- the API itself
    st, d = srv.post({'slug': 'del-api', 'name': 'a', 'text': 'mine'})
    key, cid = d.get('key', ''), d['comment']['id']
    c.ok('API: a new comment comes with a delete key, kept out of the stored record',
         len(key) >= 32 and 'key' not in d['comment'] and 'key' not in srv.get('del-api')[0], d)
    st, _ = srv.delete({'slug': 'del-api', 'id': cid})
    st2, _ = srv.delete({'slug': 'del-api', 'id': cid, 'key': 'f' * 48})
    st3, _ = srv.delete({'slug': 'del-api', 'id': cid}, owner='not-the-owner')
    c.ok('API: delete without the key, with a wrong key, or a wrong owner key is refused',
         (st, st2, st3) == (403, 403, 403) and len(srv.get('del-api')) == 1, (st, st2, st3))
    st, d = srv.delete({'slug': 'del-api', 'id': cid, 'key': key})
    c.ok('API: the author deletes with the key', st == 200 and d.get('deleted') == [cid] and srv.get('del-api') == [], d)
    st, _ = srv.delete({'slug': 'del-api', 'id': cid, 'key': key})
    c.ok('API: a deleted comment cannot be deleted again', st == 404, st)
    _, other = srv.post({'slug': 'del-api', 'name': 'b', 'text': 'theirs'})
    st, d = srv.delete({'slug': 'del-api', 'id': other['comment']['id'], 'key': key})
    c.ok("API: one comment's key cannot delete another comment", st == 403, (st, d))
    st, d = srv.delete({'slug': 'del-api', 'id': other['comment']['id']}, owner=srv.token)
    c.ok('API: the owner key deletes any comment', st == 200 and srv.get('del-api') == [], (st, d))
    _, root = srv.post({'slug': 'del-api', 'name': 'a', 'text': 'thread'})
    srv.post({'slug': 'del-api', 'name': 'b', 'text': 'reply', 'parent': root['comment']['id']})
    _, d = srv.post({'slug': 'del-api', 'name': 'c', 'text': 'still here'})
    st, d = srv.delete({'slug': 'del-api', 'id': root['comment']['id'], 'key': root['key']})
    left = [x['text'] for x in srv.get('del-api')]
    c.ok('API: deleting a top comment takes its replies, and nothing else',
         st == 200 and len(d.get('deleted', [])) == 2 and left == ['still here'], (d, left))
    _, rp = srv.post({'slug': 'del-api', 'name': 'a', 'text': 'reply only', 'parent': d['deleted'][0]})
    _, h, _ = srv.raw('OPTIONS', headers={'origin': srv.allow_origin, 'access-control-request-method': 'DELETE'})
    c.ok('CORS: the preflight allows DELETE and the authorization header',
         'DELETE' in h.get('access-control-allow-methods', '')
         and 'authorization' in h.get('access-control-allow-headers', '').lower(), h)

    st, d = srv.post({'slug': 'api-test', 'text': 'no name'})
    c.ok('API: a comment without a name is refused', st == 400, (st, d))
    st, d = srv.post({'slug': 'Bad Slug!', 'name': 'x', 'text': 'y'})
    c.ok('API: a bad slug is refused', st == 400, (st, d))
    st, d = srv.post({'slug': 'api-test', 'name': 'x', 'text': 'y' * 9000})
    c.ok('API: an oversized body is refused', st in (400, 413), (st, d))
    st, root = srv.post({'slug': 'api-test', 'name': 'a', 'text': 'root', 'anchor': {'sel': '#x', 'fx': 5}})
    c.ok('API: fractions are clamped into 0..1', st == 200 and root['comment']['anchor']['fx'] == 1, root)
    st, r1 = srv.post({'slug': 'api-test', 'name': 'b', 'text': 'reply', 'parent': root['comment']['id']})
    st, r2 = srv.post({'slug': 'api-test', 'name': 'c', 'text': 'reply to reply', 'parent': r1['comment']['id']})
    c.ok('API: a reply to a reply joins the top thread', r2['comment']['parent'] == root['comment']['id'], r2)

    # a body over 8 KB in UTF-8 bytes but under 8,192 characters, sent without a length
    big = json.dumps({'slug': 'api-test', 'name': 'x', 'text': '\u20ac' * 3000}, ensure_ascii=False).encode('utf-8')
    st, _, _ = srv.raw('POST', data=iter([big[:4000], big[4000:]]),
                       headers={'content-type': 'application/json', 'transfer-encoding': 'chunked'})
    c.ok('API: a body over 8 KB in bytes (not characters) is refused', st == 413, st)

    # CORS: opt-in, only for the allowed origin
    o = srv.allow_origin
    st, h, _ = srv.raw('OPTIONS', headers={'origin': o, 'access-control-request-method': 'POST',
                                           'access-control-request-headers': 'content-type'})
    c.ok('CORS: a preflight from an allowed origin is answered',
         st == 204 and h.get('access-control-allow-origin') == o
         and 'POST' in h.get('access-control-allow-methods', '')
         and 'content-type' in h.get('access-control-allow-headers', '').lower(), (st, h))
    st, h, _ = srv.raw('GET', '/api/comments?slug=api-test', headers={'origin': o})
    c.ok('CORS: GET from an allowed origin carries the header', h.get('access-control-allow-origin') == o, h)
    _, h, _ = srv.raw('OPTIONS', headers={'origin': 'http://not-allowed.test', 'access-control-request-method': 'POST'})
    _, h2, _ = srv.raw('GET', '/api/comments?slug=api-test', headers={'origin': 'http://not-allowed.test'})
    c.ok('CORS: any other origin gets no CORS headers',
         'access-control-allow-origin' not in h and 'access-control-allow-origin' not in h2, (h, h2))

    # the owner CLI: reading one page through the public API works on every backend
    code, out = srv.cli('list', '--base', srv.base, '--slug', 'api-test', '--title', 'api-test=API test')
    c.ok('CLI: list --base --slug reads a page through the public API',
         code == 0 and 'API test' in out and 'reply to reply' in out, out[-400:])
    if srv.backend == 'node':
        cli_node(srv, c)
    else:
        print('  SKIP  CLI owner round trip: on this backend delete and restore go through the'
              ' Cloudflare API, which a local run does not reach. --backend node covers it.')

    # many readers posting at once: nothing may be lost
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(12) as ex:
        list(ex.map(lambda n: srv.post({'slug': 'burst', 'name': f'p{n}', 'text': f'c{n}'}), range(12)))
    got = srv.get('burst')
    c.ok('API: 12 simultaneous posts, none lost', len(got) == 12, len(got))


async def deleting(srv, c, browser, p, q, url):
    """Delete from the page: the author's own comments, the owner's any comment."""
    # p is Rina (thread 1 plus a reply), q is Omar (one reply in thread 1)
    for page in (p, q):
        await page.reload(wait_until='domcontentloaded')
        await page.wait_for_timeout(900)
    await q.locator(f'{UI} .pin').first.click()
    msgs = q.locator(f'{UI} .bubble .msg')
    owns = [await msgs.nth(i).locator('.del').count() for i in range(await msgs.count())]
    c.ok("a reader sees Delete on their own comment only", owns == [0, 0, 1], owns)
    await msgs.nth(2).locator('.del').click()        # confirm() dismissed: nothing happens
    await q.wait_for_timeout(500)
    c.ok('cancelling the confirm keeps the comment', any(x['text'] == 'Fine by me' for x in srv.get('demo')))
    q.accept_dialogs = True
    await msgs.nth(2).locator('.del').click()
    await q.wait_for_timeout(800)
    c.ok('the author deletes their reply from the page',
         await msgs.count() == 2 and not any(x['text'] == 'Fine by me' for x in srv.get('demo')))
    q.accept_dialogs = False

    await p.evaluate('window.__artifactComments.refresh()')
    await p.wait_for_timeout(600)
    await p.locator(f'{UI} .pin').first.click()
    await p.wait_for_timeout(300)
    pm = p.locator(f'{UI} .bubble .msg')
    owns = [await pm.nth(i).locator('.del').count() for i in range(await pm.count())]
    c.ok('after a refresh, the other reader sees the reply gone and Delete on both of theirs', owns == [1, 1], owns)

    # a failed comment can be discarded instead of retried
    await q.keyboard.press('Escape')
    await q.route('**/api/comments', lambda r: r.fulfill(status=500, body='{"error":"boom"}')
                  if r.request.method == 'POST' else r.continue_())
    await q.locator(f'{UI} .pin').first.click()
    await q.locator(f'{UI} .bubble textarea').fill('Throw me away')
    await q.locator(f'{UI} .bubble .primary').click()
    await q.wait_for_timeout(600)
    q.accept_dialogs = True
    discard = q.locator(f'{UI} .bubble .status.failed .link', has_text='Discard')
    await discard.click()
    await q.wait_for_timeout(300)
    q.accept_dialogs = False
    await q.unroute('**/api/comments')
    c.ok('an unsent comment can be discarded',
         'Throw me away' not in await q.locator(f'{UI} .bubble').inner_text()
         and await q.evaluate("localStorage.getItem('artifact-comments:pending:demo')") == '[]')

    # the owner: ?ac-owner=<key> once, then Delete on every comment
    before = len(srv.get('demo'))
    o = await open_page(browser, url + '?ac-owner=' + srv.token + '#keep')
    c.ok('owner mode: the key leaves the address bar at once',
         'ac-owner' not in o.url and o.url.endswith('#keep') and await o.evaluate('window.__artifactComments.owner()'), o.url)
    await o.locator(f'{UI} .pin').first.click()
    om = o.locator(f'{UI} .bubble .msg')
    c.ok('owner mode: Delete on every comment', await om.locator('.del').count() == await om.count() == 2)
    o.accept_dialogs = True
    await om.first.locator('.del').click()
    await o.wait_for_timeout(900)
    c.ok('owner mode: deleting a thread removes it with its reply',
         len(srv.get('demo')) == before - 2 and not await o.locator(f'{UI} .bubble').is_visible()
         and not any(x['text'] == 'Title is too long' for x in srv.get('demo')))
    await o.reload(wait_until='domcontentloaded')
    await o.wait_for_timeout(600)
    c.ok('owner mode: remembered after a reload', await o.evaluate('window.__artifactComments.owner()'))
    await o.locator(f'{UI} .fab-list').click()
    await o.locator(f'{UI} .panel-foot .link', has_text='exit').click()
    c.ok('owner mode: exit turns it off', not await o.evaluate('window.__artifactComments.owner()'))
    c.ok('no script errors while deleting', not (q.errors + p.errors + o.errors), q.errors + p.errors + o.errors)


def cli_node(srv, c):
    """Owner round trip through the node server's owner endpoints: post, list, delete, restore."""
    import re
    _, root = srv.post({'slug': 'cli-test', 'name': 'Ana', 'text': 'CLI root comment'})
    _, reply = srv.post({'slug': 'cli-test', 'name': 'Ben', 'text': 'CLI reply', 'parent': root['comment']['id']})
    rid = root['comment']['id']
    node = ['--backend', 'node', '--base', srv.base, '--token', srv.token]

    code, out = srv.cli(*node, 'list', '--slug', 'cli-test')
    ids = re.findall(r'^\s+id (\S+)$', out, re.M)
    c.ok('CLI node: list shows the thread, the reply and the id',
         code == 0 and 'CLI root comment' in out and 'CLI reply' in out and ids == [rid], out[-400:])
    code, out = srv.cli(*node, 'list')
    c.ok('CLI node: list with no slug covers every page',
         code == 0 and '(cli-test)' in out and '(demo)' in out, out[-300:])
    code, out = srv.cli(*node, 'delete', '--slug', 'cli-test', '--id', rid)
    c.ok('CLI node: delete removes the comment and its reply',
         code == 0 and 'deleted 2 comment(s)' in out and srv.get('cli-test') == [], out)
    code, out = srv.cli(*node, 'restore', '--slug', 'cli-test', '--id', rid)
    back = srv.get('cli-test')
    c.ok('CLI node: restore brings both back, unchanged',
         code == 0 and [x['id'] for x in back] == [rid, reply['comment']['id']] and back[0] == root['comment'], out)
    _, mine = srv.post({'slug': 'cli-test', 'name': 'Cy', 'text': 'deleted from the page'})
    srv.delete({'slug': 'cli-test', 'id': mine['comment']['id'], 'key': mine['key']})
    code, out = srv.cli(*node, 'restore', '--slug', 'cli-test', '--id', mine['comment']['id'])
    c.ok('CLI node: restore undoes a delete made from the page',
         code == 0 and any(x['text'] == 'deleted from the page' for x in srv.get('cli-test')), out)
    code, out = srv.cli('--backend', 'node', '--base', srv.base, '--token', 'wrong-token', 'list')
    c.ok('CLI node: a wrong token is refused', code != 0 and '401' in out, out)
    code, out = srv.cli(*node, 'repair')
    c.ok('CLI node: repair refuses clearly (Cloudflare only)', code != 0 and 'Cloudflare only' in out, out)


def run(backend, headed=False):
    c = Checks()
    with Server(backend=backend) as srv:
        print(f'{backend} backend on {srv.base}\n')
        asyncio.run(suite(srv, c, headed))
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--headed', action='store_true')
    ap.add_argument('--backend', choices=('wrangler', 'node', 'both'), default='wrangler')
    a = ap.parse_args()
    code = 0
    for b in (['wrangler', 'node'] if a.backend == 'both' else [a.backend]):
        print(f'\n=== {b} ===')
        code |= run(b, a.headed).summary()
    return code


if __name__ == '__main__':
    sys.exit(main())
