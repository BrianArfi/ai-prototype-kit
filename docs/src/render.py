"""Render hero.html to ../hero.png at 1600x800 CSS px, 2x.

Usage: python docs/src/render.py   (needs: pip install playwright && playwright install chromium)
"""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'hero.html')
OUT = os.path.join(HERE, '..', 'hero.png')

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1600, 'height': 800}, device_scale_factor=2)
    page.goto('file:///' + SRC.replace(os.sep, '/'))
    page.wait_for_load_state('networkidle')
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(300)
    page.screenshot(path=OUT, full_page=False)
    browser.close()
print('wrote', os.path.normpath(OUT))
