"""Re-render the README visuals from the real UI.

    python docs/src/render.py            # hero.png and demo.gif
    python docs/src/render.py hero       # only docs/hero.png
    python docs/src/render.py gif        # only docs/demo.gif

Starts the Node server on docs/src with a throwaway SQLite file, drives the real
client with Playwright, then:
  hero: screenshots the page with three pins and an open thread (docs/src/shot.png)
        and renders docs/src/hero.html around it to docs/hero.png at 2x.
  gif:  records a real session (pin, comment, reply, jump from the list) and
        converts it with ffmpeg to docs/demo.gif.
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
<div class="bar"><span></span><span></span><span></span><div class="url">127.0.0.1:8787/onboarding</div></div>
</body></html>"""


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


class Server:
    def __enter__(self):
        self.tmp = tempfile.mkdtemp()
        self.port = free_port()
        self.base = f'http://127.0.0.1:{self.port}'
        self.proc = subprocess.Popen(
            ['node', str(ROOT / 'server/node/server.mjs'), '--port', str(self.port),
             '--db', os.path.join(self.tmp, 'c.db'), '--static', str(SRC)],
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
                                  'wx': M - 3, 'wy': M - 3, 'ww': W + 6, 'wh': H + BAR + 6, 'wy2': M})
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


async def main(which):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        if which in ('all', 'hero'):
            with Server() as srv: await hero(pw, srv)
        if which in ('all', 'gif'):
            with Server() as srv: await gif(pw, srv)


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else 'all'))
