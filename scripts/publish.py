#!/usr/bin/env python3
"""Publish HTML prototypes, decks and explainers as shareable links, with comments.

    python publish.py init --project my-prototypes     write kit.json
    python publish.py add "Coffee order" examples/coffee-order.html
    python publish.py build                            assemble the site, no upload
    python publish.py deploy                           build, then upload to Cloudflare Pages
    python publish.py deploy --dry-run                 build and show the upload command only
    python publish.py serve                            the built site on your machine, with comments
    python publish.py list                             pages and their links
    python publish.py comments [slug]                  read the comments on the live site

Every page gets a stable link, https://<project>.pages.dev/<slug>. Publishing again
replaces the page and keeps the link, so a shared link always shows the latest version.

Config: kit.json, found in the current folder or given with --config. Paths in it
are relative to kit.json.

    {
      "project": "my-prototypes",          Cloudflare Pages project name, also the subdomain
      "title": "Prototypes",               heading of the index page
      "comments": true,                    pinned comments on every page (default true)
      "index": true,                       publish an index page at / (default true)
      "pages": [
        {"name": "Coffee order", "source": "examples/coffee-order.html",
         "description": "optional, shown on the index",
         "slug": "optional, default: the name in lowercase with dashes",
         "comments": true}
      ]
    }

Output goes to .kit-build/ next to kit.json: _site/ is what is uploaded, and
functions/api/comments.js is the comment endpoint. Add .kit-build/ to .gitignore.

Credentials for deploy, from the environment only:
    CLOUDFLARE_API_TOKEN   (Account > Cloudflare Pages > Edit, Account > Workers KV Storage > Edit)
    CLOUDFLARE_ACCOUNT_ID

Needs Python 3.8+ and Node.js (npx runs wrangler; serve needs Node 22.13+).
Standard library only.
"""
import argparse
import glob
import hashlib
import html as htmllib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

# Wrangler prints box-drawing characters. On a Windows console that defaults to
# cp1252, printing them crashed the script after a successful upload. Force UTF-8
# on our own output, and decode every subprocess as UTF-8 as well (see run()).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMENTS = os.path.join(KIT, 'artifact-comments')
COMMENTS_CLIENT = os.path.join(COMMENTS, 'client', 'artifact-comments.js')
COMMENTS_FUNCTION = os.path.join(COMMENTS, 'functions', 'api', 'comments.js')
COMMENTS_CLI = os.path.join(COMMENTS, 'scripts', 'comments_cli.py')
COMMENTS_SERVER = os.path.join(COMMENTS, 'server', 'node', 'server.mjs')
CONFIG_NAME = 'kit.json'
BUILD_DIR = '.kit-build'


# ---------------------------------------------------------------- helpers
def run(cmd, cwd, env=None, timeout=600):
    """Run a command and capture its output, always decoded as UTF-8."""
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout)


def slugify(name):
    out = ''.join(c.lower() if c.isascii() and c.isalnum() else '-' for c in name)
    while '--' in out:
        out = out.replace('--', '-')
    return out.strip('-')[:80] or 'page'


def find_config(path):
    if path:
        p = os.path.abspath(os.path.expanduser(path))
        if os.path.isdir(p):
            p = os.path.join(p, CONFIG_NAME)
        return p
    here = os.getcwd()
    while True:
        cand = os.path.join(here, CONFIG_NAME)
        if os.path.isfile(cand):
            return cand
        up = os.path.dirname(here)
        if up == here:
            return os.path.join(os.getcwd(), CONFIG_NAME)
        here = up


def load_config(path):
    if not os.path.isfile(path):
        sys.exit(f'No {CONFIG_NAME} at {path}.\nCreate one: python publish.py init --project my-prototypes')
    with open(path, encoding='utf-8') as fh:
        cfg = json.load(fh)
    project = cfg.get('project', '')
    if not project or slugify(project) != project:
        sys.exit(f'"project" in {path} must be lowercase letters, digits and dashes (got {project!r}).')
    seen = {}
    for p in cfg.get('pages', []):
        if not p.get('name') or not p.get('source'):
            sys.exit(f'Every page in {path} needs "name" and "source": {p}')
        p['slug'] = slugify(p.get('slug') or p['name'])
        if p['slug'] in ('index', 'artifact-comments', 'api', 'functions'):
            sys.exit(f'Slug "{p["slug"]}" is reserved. Give the page another name or a "slug".')
        if p['slug'] in seen:
            sys.exit(f'Two pages share the slug "{p["slug"]}": {seen[p["slug"]]} and {p["name"]}.')
        seen[p['slug']] = p['name']
    return cfg


def save_config(path, cfg):
    clean = dict(cfg)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(clean, fh, indent=2, ensure_ascii=False)
        fh.write('\n')


def dirs(cfg_path):
    base = os.path.dirname(cfg_path)
    build = os.path.join(base, BUILD_DIR)
    return base, build, os.path.join(build, '_site')


def site_url(cfg):
    return f'https://{cfg["project"]}.pages.dev'


def with_comments(page_html, slug):
    """Add the comment script before the last </body>, once."""
    if 'artifact-comments.js' in page_html:
        return page_html
    tag = f'<script src="/artifact-comments.js" data-slug="{slug}" defer></script>\n'
    at = page_html.lower().rfind('</body>')
    return page_html[:at] + tag + page_html[at:] if at != -1 else page_html + '\n' + tag


def build_index(cfg, entries):
    title = htmllib.escape(cfg.get('title') or 'Prototypes')
    cards = []
    for e in entries:
        desc = f'<p>{htmllib.escape(e["description"])}</p>' if e.get('description') else ''
        cards.append(f'<a class="card" href="/{e["slug"]}"><div><h2>{htmllib.escape(e["name"])}</h2>{desc}</div>'
                     f'<span class="upd">{e["updated"]}</span></a>')
    stamp = datetime.now(timezone.utc).strftime('%d %B %Y')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{title}</title>
<style>
:root{{--bg:#fafaf8;--ink:#1b1f1d;--muted:#5f6763;--line:#e3e5e1;--card:#fff;--accent:#2f6fde}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111413;--ink:#e8ebe9;--muted:#98a19c;--line:#262b29;--card:#181c1a;--accent:#7aa7ff}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:64px 20px}}
.wrap{{max-width:760px;margin:0 auto}}
h1{{font-size:34px;line-height:1.2;margin:0 0 8px}}
.sub{{color:var(--muted);margin:0 0 36px}}
.card{{display:flex;justify-content:space-between;gap:20px;align-items:center;background:var(--card);
border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:12px;color:inherit;text-decoration:none}}
.card:hover{{border-color:var(--accent)}}
.card h2{{font-size:18px;margin:0 0 4px}}
.card p{{margin:0;color:var(--muted);font-size:14px}}
.upd{{color:var(--muted);font:12px ui-monospace,Menlo,monospace;white-space:nowrap}}
footer{{margin-top:40px;color:var(--muted);font-size:13px}}
</style></head><body><div class="wrap">
<h1>{title}</h1>
<p class="sub">Open a page, press <b>Comment</b> at the bottom right, and click the part you mean.</p>
{chr(10).join(cards)}
<footer>Published {stamp}. Links are unlisted and not indexed by search engines.</footer>
</div></body></html>
'''


# ---------------------------------------------------------------- commands
def cmd_init(a):
    path = find_config(a.config) if a.config else os.path.join(os.getcwd(), CONFIG_NAME)
    if os.path.exists(path) and not a.force:
        sys.exit(f'{path} exists. Pass --force to overwrite it.')
    project = slugify(a.project)
    cfg = {'project': project, 'title': a.title or 'Prototypes', 'comments': True, 'index': True, 'pages': []}
    save_config(path, cfg)
    print(f'wrote {path}\nNext: python publish.py add "Page name" path/to/page.html')
    return 0


def cmd_add(a):
    path = find_config(a.config)
    cfg = load_config(path)            # validates the file as it is now
    with open(path, encoding='utf-8') as fh:
        raw = json.load(fh)            # edited and saved as the user wrote it
    src = os.path.abspath(a.source)
    if not os.path.isfile(src):
        sys.exit(f'{a.source} does not exist.')
    rel = os.path.relpath(src, os.path.dirname(path)).replace(os.sep, '/')
    slug = slugify(a.slug or a.name)
    entry = {'name': a.name, 'source': rel}
    if a.slug:
        entry['slug'] = slug
    if a.description:
        entry['description'] = a.description
    if a.no_comments:
        entry['comments'] = False
    pages = raw.setdefault('pages', [])
    hit = [i for i, p in enumerate(pages) if slugify(p.get('slug') or p.get('name', '')) == slug]
    if hit:
        pages[hit[0]] = entry          # same slug: replace in place, the link stays
    else:
        pages.append(entry)
    save_config(path, raw)
    print(f'{"updated" if hit else "added"} "{a.name}" -> {site_url(cfg)}/{slug}')
    return 0


def cmd_build(a, cfg_path=None, quiet=False):
    cfg_path = cfg_path or find_config(a.config)
    cfg = load_config(cfg_path)
    base, build, site = dirs(cfg_path)
    comments_on = cfg.get('comments', True)

    if os.path.isdir(site):
        shutil.rmtree(site)
    os.makedirs(site)
    func_dir = os.path.join(build, 'functions')
    if os.path.isdir(func_dir):
        shutil.rmtree(func_dir)

    entries = []
    for p in cfg.get('pages', []):
        src = os.path.join(base, p['source'])
        if not os.path.isfile(src):
            print(f'  SKIP (missing): {p["source"]}')
            continue
        with open(src, encoding='utf-8') as fh:
            page = fh.read()
        on = comments_on and p.get('comments', True)
        if on:
            page = with_comments(page, p['slug'])
        with open(os.path.join(site, p['slug'] + '.html'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(page)
        mtime = datetime.fromtimestamp(os.path.getmtime(src), timezone.utc)
        entries.append({'name': p['name'], 'slug': p['slug'], 'source': p['source'],
                        'description': p.get('description', ''), 'comments': on,
                        'updated': mtime.strftime('%d %b %Y'),
                        'sha256_16': hashlib.sha256(page.encode('utf-8')).hexdigest()[:16]})
        if not quiet:
            print(f'  /{p["slug"]:<32} <- {p["source"]}{"" if on else "  (no comments)"}')
    if not entries:
        sys.exit('Nothing to build: add a page first (python publish.py add "Name" page.html).')

    if any(e['comments'] for e in entries):
        if not (os.path.isfile(COMMENTS_CLIENT) and os.path.isfile(COMMENTS_FUNCTION)):
            sys.exit(f'artifact-comments not found at {COMMENTS}. Run scripts/vendor_comments.py.')
        shutil.copyfile(COMMENTS_CLIENT, os.path.join(site, 'artifact-comments.js'))
        os.makedirs(os.path.join(func_dir, 'api'))
        with open(COMMENTS_FUNCTION, encoding='utf-8') as fh:
            body = fh.read()
        with open(os.path.join(func_dir, 'api', 'comments.js'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('// GENERATED COPY of artifact-comments/functions/api/comments.js, written by\n'
                     '// publish.py build. Edit the source, not this file.\n' + body)

    if cfg.get('index', True):
        with open(os.path.join(site, 'index.html'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(build_index(cfg, entries))

    state = {'project': cfg['project'], 'url': site_url(cfg),
             'built': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'pages': entries}
    old = read_state(build)
    for k in ('deployed', 'comments_bound'):
        if k in old:
            state[k] = old[k]
    write_state(build, state)
    if not quiet:
        print(f'\nbuilt {len(entries)} page(s) into {site}')
    return 0


def read_state(build):
    p = os.path.join(build, 'state.json')
    if os.path.isfile(p):
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    return {}


def write_state(build, state):
    os.makedirs(build, exist_ok=True)
    with open(os.path.join(build, 'state.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(state, fh, indent=2)
        fh.write('\n')


def find_npx():
    for name in ('npx', 'npx.cmd'):
        found = shutil.which(name)
        if found:
            return found
    cands = ['/opt/homebrew/bin/npx', '/usr/local/bin/npx', os.path.expanduser('~/.volta/bin/npx')]
    cands += sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/npx')), reverse=True)
    for c in cands:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    sys.exit('npx not found. Install Node.js (https://nodejs.org), then run deploy again.\n'
             'The site is already built; only the upload needs Node.')


def wrangler_cmd(npx):
    """Prefer a wrangler that npx already downloaded: it starts at once, where
    `npx --yes wrangler@4` asks the registry first and can hang on a slow link."""
    node = shutil.which('node') or shutil.which('node.exe')
    if node:
        roots = [os.path.expanduser('~/.npm/_npx')]
        if os.environ.get('LOCALAPPDATA'):
            roots.append(os.path.join(os.environ['LOCALAPPDATA'], 'npm-cache', '_npx'))
        best = None
        for root in roots:
            for entry in glob.glob(os.path.join(root, '*', 'node_modules', 'wrangler', 'bin', 'wrangler.js')):
                try:
                    with open(os.path.join(os.path.dirname(os.path.dirname(entry)), 'package.json'),
                              encoding='utf-8') as fh:
                        ver = json.load(fh).get('version', '')
                except Exception:
                    continue
                parts = ver.split('.')
                if parts and parts[0] == '4':
                    key = [int(x) for x in parts if x.isdigit()]
                    if best is None or key > best[0]:
                        best = (key, entry)
        if best:
            return [node, best[1]]
    return [npx, '--yes', 'wrangler@4']


def credentials():
    tok = os.environ.get('CLOUDFLARE_API_TOKEN') or os.environ.get('CF_API_TOKEN')
    acct = os.environ.get('CLOUDFLARE_ACCOUNT_ID') or os.environ.get('CF_ACCOUNT_ID')
    return tok, acct


def cmd_deploy(a):
    cfg_path = find_config(a.config)
    cmd_build(a, cfg_path)
    cfg = load_config(cfg_path)
    base, build, site = dirs(cfg_path)
    project = cfg['project']
    state = read_state(build)
    comments = any(p.get('comments') for p in state.get('pages', []))

    if a.dry_run:
        print('\n--dry-run: nothing uploaded. Deploy would run, from ' + build + ':')
        print(f'  wrangler pages deploy _site --project-name {project} --branch main --commit-dirty=true')
        if comments and not state.get('comments_bound'):
            print(f'  and first: comments_cli.py --namespace-title {project}-comments setup --project {project}')
        for e in state['pages']:
            print(f'  {site_url(cfg)}/{e["slug"]}')
        return 0

    tok, acct = credentials()
    if not tok or not acct:
        sys.exit('Missing Cloudflare credentials. Set these in your shell, not in a file you commit:\n'
                 '  CLOUDFLARE_API_TOKEN   token from https://dash.cloudflare.com/profile/api-tokens\n'
                 '                         with Account > Cloudflare Pages > Edit and Account > Workers KV Storage > Edit\n'
                 '  CLOUDFLARE_ACCOUNT_ID  shown on the right of the Cloudflare dashboard home page')

    npx = find_npx()
    wrangler = wrangler_cmd(npx)
    env = dict(os.environ)
    env.update({'CLOUDFLARE_API_TOKEN': tok, 'CLOUDFLARE_ACCOUNT_ID': acct,
                'CF_API_TOKEN': tok, 'CF_ACCOUNT_ID': acct})
    env['PATH'] = os.path.dirname(npx) + os.pathsep + env.get('PATH', '')

    # 1. The project must exist before the first upload.
    probe = run(wrangler + ['pages', 'project', 'list'], build, env, 300)
    if project not in (probe.stdout or ''):
        print(f"creating Cloudflare Pages project '{project}' ...")
        mk = run(wrangler + ['pages', 'project', 'create', project, '--production-branch', 'main'], build, env, 300)
        out = (mk.stdout or '') + (mk.stderr or '')
        # A token without Pages:Read lists no projects, so create reports an
        # existing project as a conflict (code 8000002). That is fine.
        if mk.returncode != 0 and 'already exists' not in out and '8000002' not in out:
            sys.exit('Could not create the Pages project:\n' + out.strip()[-1500:])

    # 2. Comments need a KV store bound to the project. Once per project.
    if comments and not state.get('comments_bound') and not a.skip_comments_setup:
        print('connecting the comment store (Workers KV) to the project ...')
        r = run([sys.executable, COMMENTS_CLI, '--namespace-title', f'{project}-comments',
                 'setup', '--project', project], build, env, 300)
        print((r.stdout or '').strip())
        if r.returncode != 0:
            sys.exit('Comment store setup failed:\n' + ((r.stdout or '') + (r.stderr or '')).strip()[-1500:]
                     + '\nCheck the token has Workers KV Storage > Edit, or rerun with --skip-comments-setup.')
        state['comments_bound'] = True
        write_state(build, state)

    # 3. Upload. functions/ is picked up from the working directory.
    print(f"\nuploading to Cloudflare Pages project '{project}' ...")
    proc = run(wrangler + ['pages', 'deploy', '_site', '--project-name', project,
                           '--branch', 'main', '--commit-dirty=true'], build, env, 900)
    out = (proc.stdout or '') + (proc.stderr or '')
    print(out.strip()[-2000:])
    if proc.returncode != 0:
        sys.exit(f'\nwrangler failed (exit {proc.returncode}).')

    state = read_state(build)
    state['deployed'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    write_state(build, state)
    print('\n' + '=' * 60)
    print(f'LIVE  {site_url(cfg)}')
    for e in state['pages']:
        print(f'  {e["name"]}\n    {site_url(cfg)}/{e["slug"]}')
    print('=' * 60)
    print('These links stay the same when you publish again.')
    return 0


def cmd_serve(a):
    cfg_path = find_config(a.config)
    cmd_build(a, cfg_path)
    base, build, site = dirs(cfg_path)
    node = shutil.which('node') or shutil.which('node.exe')
    if not node:
        sys.exit('node not found. serve needs Node.js 22.13 or later.')
    cmd = [node, '--no-warnings=ExperimentalWarning', COMMENTS_SERVER, '--static', site,
           '--db', os.path.join(build, 'comments.db'), '--port', str(a.port)]
    if a.token:
        cmd += ['--token', a.token]
    print(f'\nserving on http://127.0.0.1:{a.port}/  (Ctrl+C to stop)')
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 0


def cmd_list(a):
    cfg_path = find_config(a.config)
    cfg = load_config(cfg_path)
    base, build, site = dirs(cfg_path)
    state = read_state(build)
    print(f'{cfg["project"]}  ->  {site_url(cfg)}'
          + (f'   (last deploy {state["deployed"]})' if state.get('deployed') else '   (not deployed yet)'))
    for p in cfg.get('pages', []):
        print(f'  {p["name"]}\n    {site_url(cfg)}/{p["slug"]}   <- {p["source"]}')
    return 0


def cmd_comments(a):
    cfg_path = find_config(a.config)
    cfg = load_config(cfg_path)
    slugs = [a.slug] if a.slug else [p['slug'] for p in cfg.get('pages', [])]
    base_url = a.base or site_url(cfg)
    cmd = [sys.executable, COMMENTS_CLI]
    if a.backend == 'node':
        cmd += ['--backend', 'node']
    cmd += ['list', '--base', base_url]
    for s in slugs:
        cmd += ['--slug', s]
    for p in cfg.get('pages', []):
        cmd += ['--title', f'{p["slug"]}={p["name"]}']
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser(description='Publish HTML pages as shareable links with pinned comments.',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--config', help=f'path to {CONFIG_NAME} (default: search upward from here)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('init', help=f'write a new {CONFIG_NAME}')
    p.add_argument('--project', required=True, help='Cloudflare Pages project name, e.g. my-prototypes')
    p.add_argument('--title', help='index page heading')
    p.add_argument('--force', action='store_true')
    p.set_defaults(func=cmd_init)

    p = sub.add_parser('add', help='add or update a page')
    p.add_argument('name')
    p.add_argument('source')
    p.add_argument('--slug')
    p.add_argument('--description')
    p.add_argument('--no-comments', action='store_true')
    p.set_defaults(func=cmd_add)

    p = sub.add_parser('build', help='assemble .kit-build/_site, upload nothing')
    p.set_defaults(func=cmd_build)

    p = sub.add_parser('deploy', help='build and upload to Cloudflare Pages')
    p.add_argument('--dry-run', action='store_true', help='build, print what would be uploaded, stop')
    p.add_argument('--skip-comments-setup', action='store_true', help='do not create or bind the KV store')
    p.set_defaults(func=cmd_deploy)

    p = sub.add_parser('serve', help='build and serve locally with the Node comments server')
    p.add_argument('--port', type=int, default=8787)
    p.add_argument('--token', help='owner token, turns on delete/restore through comments_cli.py')
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser('list', help='pages and their links')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('comments', help='read the comments on the published pages')
    p.add_argument('slug', nargs='?')
    p.add_argument('--base', help='site URL (default: https://<project>.pages.dev)')
    p.add_argument('--backend', choices=('cloudflare', 'node'), default='cloudflare')
    p.set_defaults(func=cmd_comments)

    a = ap.parse_args()
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
