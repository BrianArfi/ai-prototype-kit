#!/usr/bin/env python3
"""Tests for the kit: the example prototype with comments, and the publish build.

    pip install playwright && python -m playwright install chromium
    python tests/test_example.py            # both parts
    python tests/test_example.py --build    # only the publish build (no browser, no Node server)

The browser part runs the example on the self-hosted comments server
(artifact-comments/server/node, Node 22.13 or later) with a fresh SQLite file.
Nothing touches Cloudflare. Exit code 0 means every check passed.
"""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
EXAMPLE = os.path.join(KIT, 'examples', 'coffee-order.html')
sys.path.insert(0, os.path.join(KIT, 'artifact-comments', 'tests'))

from e2e_test import Server, Checks, UI, open_page, pick_and_post, count, visible_pins  # noqa: E402


async def screen(page):
    return await page.evaluate("document.querySelector('.screen:not([hidden])').dataset.screen")


async def browser_suite(srv, c, headed=False):
    from playwright.async_api import async_playwright
    url = srv.base + '/coffee-order'
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        p = await open_page(browser, url, viewport={'width': 1280, 'height': 900})
        c.ok('the example loads with no script errors', not p.errors, p.errors)
        c.ok('it opens on screen 1', await screen(p) == '1')

        await p.locator('#item-latte').click()
        c.ok('tapping a drink goes to screen 2', await screen(p) == '2')
        await p.keyboard.press('3')
        c.ok('presenter key 3 jumps to screen 3', await screen(p) == '3')
        await p.keyboard.press('ArrowLeft')
        c.ok('the left arrow steps back to screen 2', await screen(p) == '2')

        await pick_and_post(p, '#size-group', 'Dina', 'Default to Large here? Most people pick it.')
        c.ok('a comment posts on screen 2', await count(p) == 1)
        c.ok('...and its pin shows', await visible_pins(p) == 1)
        stored = srv.get('coffee-order')
        c.ok('the comment is saved with the screen it was made on',
             len(stored) == 1 and stored[0].get('state') == {'screen': 2}, stored)
        c.ok('...and a readable place for the list', 'Screen 2: Customise' in (stored[0].get('where') or ''), stored)

        # keys typed into a reply must not drive the presenter
        await p.locator(f'{UI} .bubble textarea').fill('')
        await p.locator(f'{UI} .bubble textarea').type('1 3 ')
        c.ok('typing digits and spaces in a reply does not change the screen', await screen(p) == '2')
        await p.keyboard.press('Escape')

        # reload on screen 1: the pin belongs to screen 2, so it stays hidden
        await p.goto(url, wait_until='domcontentloaded')
        await p.wait_for_selector(f'{UI} .fab-add', state='attached')
        await p.wait_for_timeout(900)
        c.ok('after a reload the page is on screen 1', await screen(p) == '1')
        c.ok('...the comment is still there', await count(p) == 1)
        c.ok('...and its pin is hidden on screen 1', await visible_pins(p) == 0, await visible_pins(p))

        await p.locator(f'{UI} .fab-list').click()
        rows = p.locator(f'{UI} .panel .row')
        c.ok('the list shows the comment with its screen', 'Screen 2' in await rows.first.inner_text())
        await rows.first.click()
        await p.wait_for_timeout(1000)
        c.ok('clicking it in the list jumps back to screen 2', await screen(p) == '2', await screen(p))
        c.ok('...shows the pin and opens the thread',
             await visible_pins(p) == 1 and await p.locator(f'{UI} .bubble').is_visible())
        c.ok('no script errors during the run', not p.errors, p.errors)
        await browser.close()


def build_suite(c):
    """publish.py build on a copy of the example: tag injected, runtime copied."""
    tmp = tempfile.mkdtemp(prefix='kit-build-')
    try:
        shutil.copyfile(EXAMPLE, os.path.join(tmp, 'coffee-order.html'))
        with open(os.path.join(tmp, 'kit.json'), 'w', encoding='utf-8') as fh:
            json.dump({'project': 'kit-test', 'title': 'Kit test', 'pages': [
                {'name': 'Coffee order', 'source': 'coffee-order.html', 'description': 'Example'},
                {'name': 'No comments page', 'source': 'coffee-order.html', 'comments': False},
            ]}, fh)
        publish = os.path.join(KIT, 'scripts', 'publish.py')
        r = subprocess.run([sys.executable, publish, '--config', os.path.join(tmp, 'kit.json'), 'build'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        c.ok('publish.py build exits 0', r.returncode == 0, r.stdout + r.stderr)
        site = os.path.join(tmp, '.kit-build', '_site')
        page = open(os.path.join(site, 'coffee-order.html'), encoding='utf-8').read()
        c.ok('the page has the comment script tag, once, before </body>',
             page.count('<script src="/artifact-comments.js" data-slug="coffee-order" defer></script>') == 1
             and page.rfind('artifact-comments.js') < page.lower().rfind('</body>'))
        plain = open(os.path.join(site, 'no-comments-page.html'), encoding='utf-8').read()
        c.ok('a page with "comments": false has no tag', 'artifact-comments.js' not in plain)
        c.ok('the comment client is copied to the site root',
             os.path.isfile(os.path.join(site, 'artifact-comments.js')))
        func = os.path.join(tmp, '.kit-build', 'functions', 'api', 'comments.js')
        c.ok('the Pages Function is copied to functions/api/', os.path.isfile(func))
        c.ok('...and the function is outside the uploaded _site folder',
             not os.path.exists(os.path.join(site, 'functions')))
        c.ok('an index page is generated', os.path.isfile(os.path.join(site, 'index.html')))
        r = subprocess.run([sys.executable, publish, '--config', os.path.join(tmp, 'kit.json'), 'deploy', '--dry-run'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        c.ok('deploy --dry-run uploads nothing and prints the stable links',
             r.returncode == 0 and 'https://kit-test.pages.dev/coffee-order' in r.stdout, r.stdout + r.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true', help='only the publish build checks')
    ap.add_argument('--headed', action='store_true')
    a = ap.parse_args()
    c = Checks()
    print('publish build')
    build_suite(c)
    if not a.build:
        print('\nexample prototype with comments (node backend)')
        with Server(pages={'coffee-order': EXAMPLE}, backend='node') as srv:
            asyncio.run(browser_suite(srv, c, a.headed))
    return c.summary()


if __name__ == '__main__':
    sys.exit(main())
