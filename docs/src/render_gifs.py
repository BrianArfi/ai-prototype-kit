"""Render the README explainer GIFs: docs/hero.gif, docs/before-after.gif, docs/how-it-works.gif.

Usage: python docs/src/render_gifs.py [hero|before-after|how-it-works ...]
Needs: pip install playwright && playwright install chromium; ffmpeg on PATH.
Each GIF is rendered frame by frame from an animated HTML page by record_html.py (deterministic).
The static still docs/hero.png comes from hero.html via render.py.
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
JOBS = {
    'hero': ('hero-anim.html', 'hero.gif', ['--w', '1600', '--h', '800', '--dur', '9']),
    'before-after': ('before-after.html', 'before-after.gif', ['--w', '1100', '--h', '620', '--dur', '9']),
    'how-it-works': ('how-it-works.html', 'how-it-works.gif', ['--w', '1200', '--h', '600', '--dur', '10']),
}

for name in sys.argv[1:] or JOBS:
    html, gif, args = JOBS[name]
    subprocess.run([sys.executable, str(SRC / 'record_html.py'), str(SRC / html), str(SRC.parent / gif),
                    *args, '--fps', '12', '--colors', '128'], check=True)
