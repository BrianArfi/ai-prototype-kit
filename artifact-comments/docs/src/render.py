"""Re-render the README visuals from the real UI.

    python docs/src/render.py            # hero.png and demo.gif
    python docs/src/render.py hero       # only docs/hero.png
    python docs/src/render.py gif        # only docs/demo.gif
    python docs/src/render.py owner      # only docs/owner-demo.gif
    python docs/src/render.py anim       # hero.gif, before-after.gif, how-it-works.gif

Starts the Node server on docs/src with a throwaway SQLite file, drives the real
client with Playwright, then:
  hero: screenshots the page with three pins and an open thread (docs/src/shot.png)
        and renders docs/src/hero.html around it to docs/hero.png at 2x.
  gif:  records a real session (pin, comment, reply, jump from the list) and
        converts it with ffmpeg to docs/demo.gif.
  owner: a real reader comment in the browser, then the real output of the owner
        CLI (list, then delete the spam) against the same server, typed out in a
        terminal frame, joined into docs/owner-demo.gif. Uses port 8787 when it is free.
  anim: renders the illustrated hero-anim.html, before-after.html and
        how-it-works.html with record_html.py (run `hero` first: they use
        clean.png and shot.png).
Needs Node 22.13+, `pip install playwright` + chromium, and ffmpeg for the GIF.
Nothing leaves 127.0.0.1.
"""
import asyncio, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

SRC = Path(__file__).resolve().parent
DOCS = SRC.parent
ROOT = DOCS.parent
UI = 'artifact-comments'

CURSOR = """
window.addEventListener('DOMContentLoaded', () => {
  // Shared cursor for the family's GIFs: an ink dot with a lime ring.
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;left:0;top:0;width:20px;height:20px;border-radius:50%;background:#072B27;border:4px solid #C8F751;box-shadow:0 0 0 1.5px #072B27,0 2px 6px rgba(0,0,0,.25);z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);transition:transform .03s linear;box-sizing:border-box';
  document.documentElement.appendChild(c);
  window.addEventListener('mousemove', e => { c.style.transform = `translate(${e.clientX - 10}px,${e.clientY - 10}px)`; }, true);
});
"""

# The browser window the GIF is recorded into: same ink frame and field shadow as the hero.
FRAME = """<!doctype html><html><head><meta charset="utf-8">
<style>
  *{box-sizing:border-box;margin:0}
  html,body{width:%(cw)dpx;height:%(ch)dpx;background:transparent;overflow:hidden}
  .hole{position:absolute;left:%(x)dpx;top:%(y)dpx;width:%(w)dpx;height:%(h)dpx;border-radius:0 0 12px 12px;box-shadow:0 0 0 3000px #F1F3EE}
  .win{position:absolute;left:%(wx)dpx;top:%(wy)dpx;width:%(ww)dpx;height:%(wh)dpx;border:3px solid #072B27;border-radius:15px;box-shadow:10px 10px 0 #0D453E}
  .bar{position:absolute;left:%(x)dpx;top:%(wy2)dpx;width:%(w)dpx;height:%(bar)dpx;background:#072B27;border-radius:12px 12px 0 0;display:flex;align-items:center;gap:8px;padding:0 14px}
  .bar span{width:11px;height:11px;border-radius:50%%;background:#2c5a53}
  .bar .url{margin-left:14px;flex:1;height:24px;border-radius:7px;background:#123c37;color:#a9c3bd;font:500 13px/24px "JetBrains Mono",Consolas,monospace;padding:0 12px}
</style></head><body>
<div class="hole"></div><div class="win"></div>
<div class="bar"><span></span><span></span><span></span><div class="url">%(url)s</div></div>
</body></html>"""


def free_port(prefer=0):
    if prefer:
        # Windows lets two sockets bind one port, so test for a listener by connecting.
        with socket.socket() as c:
            c.settimeout(0.3)
            if c.connect_ex(('127.0.0.1', prefer)) != 0: return prefer
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


class Server:
    def __init__(self, port=None, token=None):
        self.want_port, self.token = port, token

    def __enter__(self):
        self.tmp = tempfile.mkdtemp()
        self.port = self.want_port or free_port()
        self.base = f'http://127.0.0.1:{self.port}'
        extra = ['--token', self.token] if self.token else []
        self.proc = subprocess.Popen(
            ['node', str(ROOT / 'server/node/server.mjs'), '--port', str(self.port),
             '--db', os.path.join(self.tmp, 'c.db'), '--static', str(SRC)] + extra,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.base + '/api/comments?slug=x'); return self
            except Exception:
                time.sleep(0.1)
        raise SystemExit('server did not start')

    def __exit__(self, *a):
        self.proc.terminate(); self.proc.wait()
        shutil.rmtree(self.tmp, ignore_errors=True)


async def pick(page, target, text, name=None, fx=0.5, fy=0.5, slow=False):
    await page.locator(f'{UI} .fab-add').click()
    box = await page.locator(target).first.bounding_box()
    x, y = box['x'] + box['width'] * fx, box['y'] + box['height'] * fy
    await page.mouse.move(x, y, steps=18 if slow else 1)
    if slow: await page.wait_for_timeout(500)
    await page.mouse.click(x, y)
    await page.wait_for_selector(f'{UI} .compose:not([hidden]) textarea')
    nb = page.locator(f'{UI} .compose input.name')
    if name and await nb.is_visible():
        if slow: await nb.press_sequentially(name, delay=70)
        else: await nb.fill(name)
    ta = page.locator(f'{UI} .compose textarea')
    if slow:
        await ta.click(); await ta.press_sequentially(text, delay=45); await page.wait_for_timeout(300)
    else:
        await ta.fill(text)
    await page.locator(f'{UI} .compose .primary').click()
    await page.wait_for_timeout(700)


async def reply(page, text, slow=False):
    ta = page.locator(f'{UI} .bubble textarea')
    await ta.click()
    if slow: await ta.press_sequentially(text, delay=45); await page.wait_for_timeout(300)
    else: await ta.fill(text)
    await ta.press('Control+Enter')
    await page.wait_for_timeout(700)


async def hero(pw, srv):
    b = await pw.chromium.launch()
    # Three readers, each in their own browser profile, through the real UI.
    async def reader(name):
        ctx = await b.new_context(viewport={'width': 1060, 'height': 640}, device_scale_factor=2)
        p = await ctx.new_page(); await p.goto(srv.base + '/sample'); await p.wait_for_selector(f'{UI} .fab-add', state='attached')
        await p.wait_for_timeout(300)
        return ctx, p
    ctx, p = await reader('Dina')
    # The page before anyone comments: the start frame of the animated hero.
    await p.mouse.move(5, 5)
    await p.screenshot(path=str(SRC / 'clean.png'))
    await pick(p, '#lead', 'Can we lead with the time saved? It is the strongest point.', 'Dina', 0.97, 0.25)
    await ctx.close()
    ctx, p = await reader('Maya')
    await pick(p, '#s2', 'Is this measured, or a target?', 'Maya', 0.85, 0.3)
    await pick(p, '#cta', 'Name the pilot size on the button too.', 'Maya', 0.85, 0.3)
    await ctx.close()
    ctx, p = await reader('Sam')
    await p.locator(f'{UI} .pin').first.click()
    await p.wait_for_selector(f'{UI} .bubble:not([hidden])')
    await p.locator(f'{UI} .bubble input.name').fill('Sam') if await p.locator(f'{UI} .bubble input.name').is_visible() else None
    await reply(p, 'Agreed. Moving "2 min" into the title.')
    await p.mouse.move(5, 5)
    await p.wait_for_timeout(500)
    await p.screenshot(path=str(SRC / 'shot.png'))
    # Where the real pins and thread sit in shot.png, so the animated hero lines up with it.
    boxes = await p.evaluate(f"""() => {{
      const r = document.querySelector('{UI}').shadowRoot;
      const b = e => {{ const x = e.getBoundingClientRect(); return {{x: x.x, y: x.y, w: x.width, h: x.height}}; }};
      return {{pins: [...r.querySelectorAll('.pin')].map(b), bubble: b(r.querySelector('.bubble'))}};
    }}""")
    (SRC / 'pins.json').write_text(json.dumps(boxes, indent=1))
    await ctx.close()
    ctx = await b.new_context(viewport={'width': 1600, 'height': 800}, device_scale_factor=2)
    p = await ctx.new_page()
    await p.goto((SRC / 'hero.html').as_uri(), wait_until='networkidle')
    await p.wait_for_timeout(400)
    await p.screenshot(path=str(DOCS / 'hero.png'))
    await b.close()
    print('wrote', DOCS / 'hero.png')


async def gif(pw, srv):
    # Maya left one earlier comment on the other tab, through the real UI, so the list has something to jump to.
    b0 = await pw.chromium.launch()
    mp = await (await b0.new_context(viewport={'width': 880, 'height': 540})).new_page()
    await mp.goto(srv.base + '/sample'); await mp.wait_for_selector(f'{UI} .fab-add', state='attached')
    await mp.click('#tabs [data-tab=rollout]')
    await pick(mp, '#pilot', 'Which week in November? Sales needs the date.', 'Maya', 0.13, 0.22)
    await b0.close()
    vid = Path(tempfile.mkdtemp())
    b = await pw.chromium.launch()
    W, H = 880, 540
    ctx = await b.new_context(viewport={'width': W, 'height': H}, record_video_dir=str(vid), record_video_size={'width': W, 'height': H})
    await ctx.add_init_script(CURSOR)
    p = await ctx.new_page()
    await p.goto(srv.base + '/sample'); await p.wait_for_selector(f'{UI} .fab-add', state='attached')
    await p.mouse.move(640, 160); await p.wait_for_timeout(700)
    fab = await p.locator(f'{UI} .fab-add').bounding_box()
    await p.mouse.move(fab['x'] + fab['width'] / 2, fab['y'] + fab['height'] / 2, steps=16)
    await p.wait_for_timeout(250)
    # Dina pins her comment to the title, in the empty space after the words.
    await pick(p, '#title', 'Can we lead with the time saved?', 'Dina', 0.9, 0.5, slow=True)
    await p.wait_for_timeout(800)
    # Sam answers in the same thread: switch the name, then reply.
    ch = p.locator(f'{UI} .bubble .as button.link')
    cb = await ch.bounding_box()
    await p.mouse.move(cb['x'] + cb['width'] / 2, cb['y'] + cb['height'] / 2, steps=12)
    await p.mouse.click(cb['x'] + cb['width'] / 2, cb['y'] + cb['height'] / 2)
    await p.locator(f'{UI} .bubble input.name').press_sequentially('Sam', delay=80)
    await p.locator(f'{UI} .bubble textarea').click()
    await reply(p, 'Yes, moving it into the title.', slow=True)
    await p.wait_for_timeout(1000)
    await p.keyboard.press('Escape')
    lb = await p.locator(f'{UI} .fab-list').bounding_box()
    lx, ly = lb['x'] + lb['width'] / 2, lb['y'] + lb['height'] / 2
    await p.mouse.move(lx, ly, steps=16)
    await p.mouse.click(lx, ly)
    await p.wait_for_timeout(1100)
    item = p.locator(f'{UI} .panel').get_by_text('Which week in November').first
    ib = await item.bounding_box()
    await p.mouse.move(ib['x'] + 40, ib['y'] + ib['height'] / 2, steps=16)
    await p.mouse.click(ib['x'] + 40, ib['y'] + ib['height'] / 2)
    await p.wait_for_timeout(500)
    # Close the list so the end frame shows only the restored tab and its thread.
    await p.mouse.move(lx, ly, steps=10)
    await p.mouse.click(lx, ly)
    await p.mouse.move(lx - 140, ly - 30, steps=8)
    await p.wait_for_timeout(2400)
    await ctx.close()
    webm = next(vid.glob('*.webm'))
    # Composite the recording into the browser frame.
    M, BAR, SH = 18, 40, 10
    cw, ch_ = W + 2 * M + SH, H + BAR + 2 * M + SH
    fctx = await b.new_context(viewport={'width': cw, 'height': ch_})
    fp = await fctx.new_page()
    await fp.set_content(FRAME % {'cw': cw, 'ch': ch_, 'x': M, 'y': M + BAR, 'w': W, 'h': H, 'bar': BAR,
                                  'wx': M - 3, 'wy': M - 3, 'ww': W + 6, 'wh': H + BAR + 6, 'wy2': M,
                                  'url': '127.0.0.1:8787/onboarding'})
    frame = vid / 'frame.png'
    await fp.screenshot(path=str(frame), omit_background=True)
    await b.close()
    out = DOCS / 'demo.gif'
    fc = (f'[0:v]fps=12,pad={cw}:{ch_}:{M}:{M + BAR}:color=0xF1F3EE[v];[v][1:v]overlay=0:0,'
          'split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '0.5', '-i', str(webm), '-i', str(frame),
                    '-filter_complex', fc, str(out)], check=True)
    shutil.rmtree(vid, ignore_errors=True)
    print('wrote', out, round(out.stat().st_size / 1e6, 2), 'MB')


TERM = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0}
  html,body{width:%(cw)dpx;height:%(ch)dpx;background:#F1F3EE;overflow:hidden;font-family:'JetBrains Mono',Consolas,monospace}
  .win{position:absolute;left:15px;top:15px;width:%(ww)dpx;height:%(wh)dpx;background:#072B27;border:3px solid #072B27;border-radius:15px;box-shadow:10px 10px 0 #0D453E;overflow:hidden}
  .chrome{height:40px;background:#0A3833;display:flex;align-items:center;gap:8px;padding:0 14px}
  .chrome i{width:11px;height:11px;border-radius:50%%;background:#2C5C55;display:block}
  .chrome span{margin-left:10px;color:#9DB7AF;font-size:14px}
  .chrome b{margin-left:auto;font:800 14px Archivo,sans-serif;color:#072B27;background:#C8F751;padding:3px 9px;border-radius:5px}
  .s{padding:16px 18px;color:#DDE7E2;font-size:16px;line-height:1.5;white-space:pre-wrap}
  .cmd{display:block;color:#fff}
  .p{color:#C8F751}
  .ch{opacity:0}
  .ty{display:inline-block;vertical-align:top;overflow:hidden;white-space:pre;color:#fff;width:0}
  @keyframes type{to{width:calc(var(--n) * 1ch)}}
  .out{opacity:0;display:block}
  .hl{background:#C8F751;color:#072B27;border-radius:3px;padding:0 3px}
</style></head><body>
<div class="win"><div class="chrome"><i></i><i></i><i></i><span>Terminal</span><b>real output</b></div>
<div class="s">%(body)s</div></div></body></html>"""


def term_body(steps):
    """steps: [(command, output)] -> HTML with CSS animations: type each command, then show its output."""
    import html as h
    out, t = ['<style>@keyframes show{to{opacity:1}}</style>'], 0.4
    for k, (cmd, res) in enumerate(steps):
        # Type the command, wrapped like a terminal would (82 columns after the prompt).
        out.append(f'<span class="ch" style="animation:show .01s {t - 0.2:.2f}s both"><span class="p">$ </span></span>')
        for j in range(0, len(cmd), 82):
            seg = cmd[j:j + 82]
            d0 = t + j * 0.025
            out.append(f'<span class="ty" style="--n:{len(seg)};animation:type {len(seg) * 0.025:.3f}s steps({len(seg)}) {d0:.3f}s both">{h.escape(seg)}</span>')
            if j + 82 < len(cmd): out.append('\n')
        out.append('\n')
        t += len(cmd) * 0.025 + 0.4
        res = h.escape(res.rstrip('\n'))
        res = res.replace('deleted 1', '<span class="hl">deleted 1</span>')
        out.append(f'<span class="out" style="animation:show .01s {t:.2f}s both">{res}\n</span>')
        t += 2.6 if k == 0 else 2.0
    return ''.join(out), t + 1.0


async def owner(pw, srv, token):
    W, H = 880, 540
    M, BAR, SH = 18, 40, 10
    cw, ch_ = W + 2 * M + SH, H + BAR + 2 * M + SH
    b = await pw.chromium.launch()
    # Earlier comments, through the real UI: a fair question from Maya, and a spam post.
    for name, target, text in (('Maya', '#s2', 'Is this measured, or a target?'),
                               ('promo', '#s3', 'Cheap followers, visit my site')):
        sctx = await b.new_context(viewport={'width': W, 'height': H})
        sp = await sctx.new_page()
        await sp.goto(srv.base + '/sample'); await sp.wait_for_selector(f'{UI} .fab-add', state='attached')
        await pick(sp, target, text, name, 0.85, 0.3)
        await sctx.close()
    # Part 1, recorded: Dina adds her comment in the browser.
    vid = Path(tempfile.mkdtemp())
    ctx = await b.new_context(viewport={'width': W, 'height': H}, record_video_dir=str(vid), record_video_size={'width': W, 'height': H})
    await ctx.add_init_script(CURSOR)
    p = await ctx.new_page()
    await p.goto(srv.base + '/sample'); await p.wait_for_selector(f'{UI} .fab-add', state='attached')
    await p.mouse.move(640, 160); await p.wait_for_timeout(700)
    fab = await p.locator(f'{UI} .fab-add').bounding_box()
    await p.mouse.move(fab['x'] + fab['width'] / 2, fab['y'] + fab['height'] / 2, steps=16)
    await p.wait_for_timeout(250)
    await pick(p, '#lead', 'Can we lead with the time saved?', 'Dina', 0.97, 0.25, slow=True)
    await p.wait_for_timeout(900)
    await p.keyboard.press('Escape')
    await p.mouse.move(640, 300, steps=8)
    await p.wait_for_timeout(700)
    await ctx.close()
    webm = next(vid.glob('*.webm'))
    # Part 2: the owner CLI against the same server. Real commands, real output.
    env = dict(os.environ, ARTIFACT_COMMENTS_TOKEN=token, PYTHONIOENCODING='utf-8')
    cli = [sys.executable, str(ROOT / 'scripts/comments_cli.py'), '--backend', 'node', '--base', srv.base]

    def run(*args):
        return subprocess.run(cli + list(args), env=env, capture_output=True, text=True, encoding='utf-8', check=True).stdout
    listing = run('list')
    data = json.load(urllib.request.urlopen(srv.base + '/api/comments?slug=onboarding'))
    spam = next(c for c in data['comments'] if c['name'] == 'promo')
    deleted = run('delete', '--slug', 'onboarding', '--id', spam['id'])
    shown = f'python scripts/comments_cli.py --backend node --base {srv.base}'
    body, dur = term_body([(shown + ' list', listing.lstrip('\n')),
                           (f'{shown} delete --slug onboarding --id {spam["id"]}', deleted)])
    tctx = await b.new_context(viewport={'width': cw, 'height': ch_})
    tp = await tctx.new_page()
    await tp.set_content(TERM % {'cw': cw, 'ch': ch_, 'ww': W + 6, 'wh': H + BAR + 6, 'body': body})
    await tp.wait_for_load_state('networkidle'); await tp.evaluate('document.fonts.ready'); await tp.wait_for_timeout(300)
    tdir = vid / 'term'; tdir.mkdir()
    fps = 12
    for i in range(int(dur * fps)):
        await tp.evaluate("""ms => { for (const a of document.getAnimations()) { a.pause(); a.currentTime = ms; } }""", i * 1000 / fps)
        await tp.screenshot(path=str(tdir / f'f{i:05d}.png'))
    # Browser frame around part 1.
    fp = await (await b.new_context(viewport={'width': cw, 'height': ch_})).new_page()
    await fp.set_content(FRAME % {'cw': cw, 'ch': ch_, 'x': M, 'y': M + BAR, 'w': W, 'h': H, 'bar': BAR,
                                  'wx': M - 3, 'wy': M - 3, 'ww': W + 6, 'wh': H + BAR + 6, 'wy2': M,
                                  'url': srv.base.replace('http://', '') + '/sample'})
    frame = vid / 'frame.png'
    await fp.screenshot(path=str(frame), omit_background=True)
    await b.close()
    out = DOCS / 'owner-demo.gif'
    fc = (f'[0:v]fps={fps},pad={cw}:{ch_}:{M}:{M + BAR}:color=0xF1F3EE[v];[v][1:v]overlay=0:0,format=yuv420p,setsar=1[a];'
          f'[2:v]fps={fps},format=yuv420p,setsar=1[t];[a][t]concat=n=2:v=1:a=0,split[x][y];'
          '[x]palettegen=max_colors=96:stats_mode=diff[p];[y][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '0.5', '-i', str(webm), '-i', str(frame),
                    '-framerate', str(fps), '-i', str(tdir / 'f%05d.png'), '-filter_complex', fc, str(out)], check=True)
    shutil.rmtree(vid, ignore_errors=True)
    print('wrote', out, round(out.stat().st_size / 1e6, 2), 'MB')


def anim():
    rec = [sys.executable, str(SRC / 'record_html.py')]
    for page, gif_, w, h, colors in (('hero-anim.html', 'hero.gif', 1280, 640, 128),
                                     ('before-after.html', 'before-after.gif', 1200, 600, 128),
                                     ('how-it-works.html', 'how-it-works.gif', 1200, 620, 96)):
        subprocess.run(rec + [str(SRC / page), str(DOCS / gif_), '--w', str(w), '--h', str(h),
                              '--dur', '10', '--fps', '12', '--colors', str(colors)], check=True)


async def main(which):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        if which in ('all', 'hero'):
            with Server() as srv: await hero(pw, srv)
        if which in ('all', 'gif'):
            with Server() as srv: await gif(pw, srv)
        if which in ('all', 'owner'):
            with Server(port=free_port(8787), token='demo-owner-token') as srv: await owner(pw, srv, srv.token)
    if which in ('all', 'anim'):
        anim()


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else 'all'))
