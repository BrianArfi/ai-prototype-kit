"""Record docs/demo.gif from a real run of the kit, in three parts.

Run it from a scratch project where the kit is installed and the example is served:

    python scripts/install.py <scratch>            # then copy examples/coffee-order.html and kit.json there
    python .claude/skills/ai-prototype-kit/scripts/publish.py serve --port 8792

1. Dina pins a comment on Large (real UI, real comments server):
       python docs/src/record_demo.py comment --base http://127.0.0.1:8792
2. Run /revise-from-comments in Claude Code on that project, and restart `serve` so it rebuilds.
3. The same link after the revision, plus the report line Claude printed:
       python docs/src/record_demo.py after --base http://127.0.0.1:8792 --report "<the Done line>"
   This also joins the parts into docs/demo.gif.

Needs Playwright with Chromium, and ffmpeg. Nothing leaves 127.0.0.1.
"""
import argparse
import html
import shutil
import subprocess
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent / 'demo.gif'
WORK = Path(tempfile.gettempdir()) / 'ai-prototype-kit-demo'
UI = 'artifact-comments'
W, H = 560, 760
FPS = 12

# Shared cursor for the family's GIFs: an ink dot with a lime ring.
CURSOR = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;left:0;top:0;width:20px;height:20px;border-radius:50%;background:#072B27;border:4px solid #C8F751;box-shadow:0 0 0 1.5px #072B27,0 2px 6px rgba(0,0,0,.25);z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);transition:transform .03s linear;box-sizing:border-box';
  document.documentElement.appendChild(c);
  window.addEventListener('mousemove', e => { c.style.transform = `translate(${e.clientX - 10}px,${e.clientY - 10}px)`; }, true);
});
"""

TERMINAL = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0}
  html,body{width:%(w)dpx;height:%(h)dpx;background:#F1F3EE;display:grid;place-items:center;font-family:'JetBrains Mono',Consolas,monospace}
  .win{width:%(ww)dpx;background:#072B27;border:3px solid #072B27;border-radius:12px;box-shadow:7px 7px 0 #0D453E;overflow:hidden}
  .chrome{height:32px;background:#0A3833;display:flex;align-items:center;gap:8px;padding:0 14px}
  .chrome i{width:12px;height:12px;border-radius:50%%;background:#2C5C55;display:block}
  .chrome span{margin-left:10px;color:#9DB7AF;font-size:13px}
  .chrome b{margin-left:auto;font:800 13px Archivo,sans-serif;color:#072B27;background:#C8F751;padding:3px 9px;border-radius:5px}
  .s{padding:16px 16px 18px;color:#DDE7E2;font-size:15px;line-height:1.5}
  .p{color:#C8F751}.c{color:#fff}
  .done{margin-top:10px;white-space:pre-wrap}
  .done b{background:#C8F751;color:#072B27;padding:0 4px;border-radius:3px}
</style></head><body>
<div class="win"><div class="chrome"><i></i><i></i><i></i><span>Claude Code</span><b>real output</b></div>
<div class="s"><div><span class="p">&gt; </span><span class="c">/revise-from-comments coffee-order</span></div>
<div class="done">%(report)s</div></div></div></body></html>"""


async def new_ctx(b, name):
    vid = WORK / name
    shutil.rmtree(vid, ignore_errors=True)
    ctx = await b.new_context(viewport={'width': W, 'height': H}, record_video_dir=str(vid),
                              record_video_size={'width': W, 'height': H})
    await ctx.add_init_script(CURSOR)
    return ctx, vid


async def comment(base):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx, vid = await new_ctx(b, 'comment')
        p = await ctx.new_page()
        await p.goto(base + '/coffee-order#screen-2')
        await p.wait_for_selector(f'{UI} .fab-add', state='attached')
        await p.mouse.move(280, 250)
        await p.wait_for_timeout(700)
        fab = await p.locator(f'{UI} .fab-add').bounding_box()
        await p.mouse.move(fab['x'] + fab['width'] / 2, fab['y'] + fab['height'] / 2, steps=14)
        await p.mouse.click(fab['x'] + fab['width'] / 2, fab['y'] + fab['height'] / 2)
        await p.wait_for_timeout(600)
        # Click the Large button near its top-right corner, so the pin sits off the label.
        lg = await p.locator('[data-size=L]').bounding_box()
        x, y = lg['x'] + lg['width'] * 0.9, lg['y'] + lg['height'] * 0.18
        await p.mouse.move(x, y, steps=14)
        await p.wait_for_timeout(300)
        await p.mouse.click(x, y)
        await p.wait_for_selector(f'{UI} .compose:not([hidden]) textarea')
        nb = p.locator(f'{UI} .compose input.name')
        if await nb.is_visible():
            await nb.press_sequentially('Dina', delay=70)
        ta = p.locator(f'{UI} .compose textarea')
        await ta.click()
        await ta.press_sequentially('Default to Large, most people pick it', delay=40)
        await p.wait_for_timeout(300)
        await p.locator(f'{UI} .compose .primary').click()
        await p.wait_for_timeout(900)
        await p.keyboard.press('Escape')
        await p.mouse.move(280, 640, steps=8)
        await p.wait_for_timeout(900)
        await ctx.close()
        await b.close()
    print('recorded', next(vid.glob('*.webm')))


async def after(base, report):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        # The report Claude printed, as a still frame.
        tp = await (await b.new_context(viewport={'width': W, 'height': H})).new_page()
        await tp.set_content(TERMINAL % {'w': W, 'h': H, 'ww': W - 40, 'report': report})
        await tp.wait_for_timeout(600)
        await tp.screenshot(path=str(WORK / 'report.png'))
        # The same link again, after the revision.
        ctx, vid = await new_ctx(b, 'after')
        p = await ctx.new_page()
        await p.goto(base + '/coffee-order#screen-2')
        await p.wait_for_selector(f'{UI} .fab-add', state='attached')
        # A caption, so the reader knows this is the same link after the revision.
        await p.evaluate("""() => { const t = document.createElement('div');
          t.textContent = 'Same link, after /revise-from-comments';
          t.style.cssText = 'position:fixed;left:50%;top:18px;transform:translateX(-50%);z-index:2147483646;background:#C8F751;color:#072B27;border:2px solid #072B27;border-radius:8px;padding:5px 12px;font:700 14px/1.2 "JetBrains Mono",Consolas,monospace;white-space:nowrap';
          document.body.appendChild(t); }""")
        await p.mouse.move(280, 640)
        await p.wait_for_timeout(600)
        lg = await p.locator('[data-size=L]').bounding_box()
        await p.mouse.move(lg['x'] + lg['width'] / 2, lg['y'] + lg['height'] + 30, steps=10)
        pr = await p.locator('#add-btn').bounding_box()
        await p.wait_for_timeout(700)
        await p.mouse.move(pr['x'] + pr['width'] * 0.88, pr['y'] - 26, steps=12)
        await p.wait_for_timeout(2600)
        await ctx.close()
        await b.close()
    join()


def join():
    a = next((WORK / 'comment').glob('*.webm'))
    c = next((WORK / 'after').glob('*.webm'))
    still = WORK / 'report.png'
    fc = (f'[0:v]trim=start=0.4,setpts=PTS-STARTPTS,fps={FPS},format=yuv420p[a];'
          f'[1:v]fps={FPS},format=yuv420p,trim=duration=2.6[b];'
          f'[2:v]trim=start=0.5,setpts=PTS-STARTPTS,fps={FPS},format=yuv420p[c];'
          '[a][b][c]concat=n=3:v=1:a=0,split[x][y];'
          '[x]palettegen=max_colors=96:stats_mode=diff[p];[y][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(a), '-loop', '1', '-framerate', str(FPS),
                    '-i', str(still), '-i', str(c), '-filter_complex', fc, str(OUT)], check=True)
    print('wrote', OUT, round(OUT.stat().st_size / 1e6, 2), 'MB')


if __name__ == '__main__':
    import asyncio
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=('comment', 'after', 'join'))
    ap.add_argument('--base', default='http://127.0.0.1:8792')
    ap.add_argument('--report', default='', help='the Done line from /revise-from-comments, plain text')
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if a.step == 'comment':
        asyncio.run(comment(a.base))
    elif a.step == 'after':
        rep = html.escape(a.report).replace('Done', '<b>Done</b>', 1)
        asyncio.run(after(a.base, rep))
    else:
        join()
