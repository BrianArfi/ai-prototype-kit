#!/usr/bin/env python3
"""Owner tools for artifact-comments. Python 3.8+, standard library only.

  list    [--slug S ...] [--base URL]   read comments as threads, with replies
  delete  --slug S --id ID              remove a comment (and its replies), into the trash
  restore --slug S --id ID              undo a delete
  repair  [--slug S]                    Cloudflare only: rebuild the per-page summary
                                        from the per-comment keys; also migrates
                                        records written by older versions
  setup   --project P                   Cloudflare only: create the KV namespace if
                                        missing and bind it to a Pages project

Two backends, picked with --backend:

  cloudflare (default)  the Pages Function in functions/api/comments.js.
      Reading one page through --base needs nothing: it calls the public GET.
      Everything else talks to the Cloudflare API and needs credentials, taken
      from --creds <file.json> ({"api_token", "account_id", "kv_namespace_id"})
      or from the environment (CF_API_TOKEN, CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID).
      Without a namespace id, the namespace is looked up by --namespace-title.
      Token permissions: Account > Workers KV Storage > Edit, plus
      Account > Cloudflare Pages > Edit for `setup`.

  node  the self-hosted server in server/node/server.mjs. Pass --base (the
      server URL) and --token (or ARTIFACT_COMMENTS_TOKEN): list, delete and
      restore go through its owner endpoints. `list --base --slug` without a
      token reads through the public GET, as on Cloudflare.

Examples:
  comments_cli.py list --base https://site.example --slug my-page
  comments_cli.py --backend node --base http://127.0.0.1:8787 --token T list
  comments_cli.py --backend node --base http://127.0.0.1:8787 --token T delete --slug my-page --id ID
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

API = 'https://api.cloudflare.com/client/v4'
UA = {'User-Agent': 'artifact-comments-cli/1.0'}  # Cloudflare refuses Python's default UA
DEFAULT_TITLE = 'artifact-comments'

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # Windows consoles default to cp1252
except Exception:
    pass


# ---------------------------------------------------------------- plumbing
class Cf:
    def __init__(self, token, account, ns=None, title=DEFAULT_TITLE):
        self.token, self.account, self._ns, self.title = token, account, ns, title

    def call(self, method, path, body=None, raw=False, ctype='application/json'):
        headers = dict(UA, Authorization='Bearer ' + self.token)
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
            headers['Content-Type'] = ctype
        req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = r.read()
        except urllib.error.HTTPError as e:
            if raw and e.code == 404:
                return None
            detail = e.read().decode('utf-8', 'replace')[:400]
            sys.exit(f'Cloudflare API {method} {path} failed: HTTP {e.code} {detail}')
        if raw:
            return payload
        d = json.loads(payload or b'{}')
        if not d.get('success', True):
            sys.exit(f'Cloudflare API {method} {path} failed: {d.get("errors")}')
        return d

    @property
    def ns(self):
        if not self._ns:
            for n in self.namespaces():
                if n['title'] == self.title:
                    self._ns = n['id']
                    break
            else:
                sys.exit(f'No KV namespace titled "{self.title}". Run `setup` first, '
                         'or pass --namespace-id.')
        return self._ns

    def namespaces(self):
        out, page = [], 1
        while True:
            d = self.call('GET', f'/accounts/{self.account}/storage/kv/namespaces?per_page=100&page={page}')
            out += d['result']
            if len(d['result']) < 100:
                return out
            page += 1

    def _k(self, key):
        return f'/accounts/{self.account}/storage/kv/namespaces/{self.ns}/values/' + urllib.parse.quote(key, safe='')

    def get(self, key):
        raw = self.call('GET', self._k(key), raw=True)
        return None if raw is None else raw.decode('utf-8')

    def get_json(self, key, default):
        raw = self.get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except ValueError:
            return default

    def put(self, key, value):
        self.call('PUT', self._k(key), body=value.encode('utf-8'), ctype='text/plain')

    def delete(self, key):
        self.call('DELETE', self._k(key))

    def keys(self, prefix):
        out, cursor = [], ''
        while True:
            q = urllib.parse.urlencode({'prefix': prefix, 'limit': 1000, **({'cursor': cursor} if cursor else {})})
            d = self.call('GET', f'/accounts/{self.account}/storage/kv/namespaces/{self.ns}/keys?{q}')
            out += [k['name'] for k in d['result']]
            cursor = (d.get('result_info') or {}).get('cursor') or ''
            if not cursor:
                return out


def creds(args):
    c = {}
    if args.creds:
        with open(args.creds, encoding='utf-8') as fh:
            c = json.load(fh)
    token = c.get('api_token') or os.environ.get('CF_API_TOKEN')
    account = c.get('account_id') or os.environ.get('CF_ACCOUNT_ID')
    ns = args.namespace_id or c.get('kv_namespace_id') or os.environ.get('CF_KV_NAMESPACE_ID')
    if not token or not account:
        sys.exit('Missing credentials: pass --creds <file.json> or set CF_API_TOKEN and CF_ACCOUNT_ID.')
    return Cf(token, account, ns, args.namespace_title)


class NodeAdmin:
    """The owner endpoints of server/node/server.mjs."""

    def __init__(self, base, token):
        self.base, self.token = base.rstrip('/'), token

    def call(self, method, path, body=None):
        headers = dict(UA, Authorization='Bearer ' + self.token)
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read() or b'{}').get('error') or ''
            except ValueError:
                detail = ''
            sys.exit(f'{method} {self.base}{path} failed: HTTP {e.code} {detail}'.rstrip())
        except urllib.error.URLError as e:
            sys.exit(f'Cannot reach {self.base}: {e.reason}')

    def pages(self, slug=None):
        q = '?slug=' + urllib.parse.quote(slug) if slug else ''
        return self.call('GET', '/api/comments/admin' + q).get('pages', {})


def node_token(args):
    return getattr(args, 'token', None) or os.environ.get('ARTIFACT_COMMENTS_TOKEN')


def node_admin(args):
    token = node_token(args)
    if not getattr(args, 'base', None) or not token:
        sys.exit('--backend node needs --base <server URL> and --token (or ARTIFACT_COMMENTS_TOKEN).')
    return NodeAdmin(args.base, token)


def check_backend(args):
    """Refuse flags that belong to the other backend, instead of silently ignoring them."""
    if args.backend == 'node':
        if args.cmd in ('repair', 'setup'):
            sys.exit(f'`{args.cmd}` is Cloudflare only: it manages Workers KV. The node server keeps '
                     'its comments in one SQLite table, so there is no summary to rebuild and '
                     'nothing to bind. Use --backend cloudflare.')
        stray = [f for f, v in (('--creds', args.creds), ('--namespace-id', args.namespace_id),
                                ('--namespace-title', args.namespace_title != DEFAULT_TITLE)) if v]
        if stray:
            sys.exit(f'{", ".join(stray)} only apply to --backend cloudflare.')
        return
    if getattr(args, 'token', None):
        sys.exit('--token only applies to --backend node. Cloudflare uses --creds or CF_API_TOKEN.')
    if getattr(args, 'base', None) and args.cmd != 'list':
        sys.exit(f'--base with `{args.cmd}` only applies to --backend node. On Cloudflare, '
                 '--base is for `list` through the public API.')
    if args.cmd == 'list' and getattr(args, 'base', None) and not args.slug:
        sys.exit('list --base needs at least one --slug on Cloudflare: the public API reads one page '
                 'at a time. Drop --base to list every page through the Cloudflare API.')


def public_get(base, slug):
    url = base.rstrip('/') + '/api/comments?slug=' + urllib.parse.quote(slug)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r).get('comments', [])


# ---------------------------------------------------------------- output
def when(iso):
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone().strftime('%d %b %H:%M')
    except Exception:
        return iso or ''


def threads(comments):
    ids = {c['id'] for c in comments}
    roots = [c for c in comments if not c.get('parent') or c['parent'] not in ids]
    replies = {}
    for c in comments:
        if c.get('parent') in ids:
            replies.setdefault(c['parent'], []).append(c)
    return roots, replies


def print_page(slug, comments, title=None):
    roots, replies = threads(comments)
    print(f'\n{title or slug}  ({slug})  {len(roots)} threads, {len(comments)} comments')
    for n, c in enumerate(roots, 1):
        where = c.get('where') or c.get('ctx') or ''
        quote = ((c.get('anchor') or {}).get('text') or '')[:60]
        print(f'  #{n} {c.get("name", "?")} · {when(c.get("at"))}' + (f' · {where}' if where else ''))
        if quote:
            print(f'     on "{quote}"')
        for line in (c.get('text') or '').splitlines() or ['']:
            print(f'     {line}')
        for r in replies.get(c['id'], []):
            print(f'     ↳ {r.get("name", "?")} · {when(r.get("at"))}: {r.get("text", "")}')
        print(f'     id {c["id"]}')


# ---------------------------------------------------------------- commands
def cmd_list(args):
    titles = dict(t.split('=', 1) for t in (args.title or []))
    if args.backend == 'node' and (node_token(args) or not args.slug):
        admin = node_admin(args)
        slugs = args.slug or sorted(admin.pages())
        total = 0
        for slug in slugs:
            cs = admin.pages(slug).get(slug, {}).get('comments', [])
            total += len(cs)
            if cs or len(slugs) == 1:
                print_page(slug, cs, titles.get(slug))
        print(f'\n{total} comments across {len(slugs)} pages')
        return 0
    if getattr(args, 'base', None) and args.slug:
        total = 0
        for slug in args.slug:
            try:
                cs = public_get(args.base, slug)
            except Exception as e:
                print(f'  {slug}: read failed ({e})')
                continue
            total += len(cs)
            if cs or len(args.slug) == 1:
                print_page(slug, cs, titles.get(slug))
        print(f'\n{total} comments across {len(args.slug)} pages')
        return 0
    cf = creds(args)
    slugs = args.slug or sorted(k[len('comments:'):] for k in cf.keys('comments:'))
    total = 0
    for slug in slugs:
        cs = cf.get_json(f'comments:{slug}', [])
        total += len(cs)
        if cs:
            print_page(slug, cs, titles.get(slug))
    print(f'\n{total} comments across {len(slugs)} pages')
    return 0


def cmd_delete(args):
    if args.backend == 'node':
        d = node_admin(args).call('POST', '/api/comments/admin/delete', {'slug': args.slug, 'id': args.id})
        gone, target = d.get('deleted', []), d.get('comment') or {}
        print(f'deleted {len(gone)} comment(s) from {args.slug}: "{target.get("text", "")[:60]}"'
              + (f' and {len(gone) - 1} repl{"y" if len(gone) == 2 else "ies"}' if len(gone) > 1 else ''))
        return 0
    cf = creds(args)
    slug, cid = args.slug, args.id
    summary = cf.get_json(f'comments:{slug}', [])
    target = next((c for c in summary if c.get('id') == cid), None) or cf.get_json(f'c:{slug}:{cid}', None)
    if not target:
        sys.exit(f'No comment {cid} on {slug}.')
    # every record of the page: the summary plus any per-comment key it lacks
    records = {c['id']: c for c in summary if c.get('id')}
    for k in cf.keys(f'c:{slug}:'):
        kid = k.split(':', 2)[2]
        if kid not in records:
            records[kid] = cf.get_json(k, {'id': kid})
    gone = {cid} | {r['id'] for r in records.values() if r.get('parent') == cid}
    deleted = cf.get_json(f'deleted:{slug}', [])
    for g in gone:                                   # kept in the trash, so `restore` can undo this
        cf.put(f'trash:{slug}:{g}', json.dumps(records.get(g) or target))
    cf.put(f'deleted:{slug}', json.dumps(sorted(set(deleted) | gone)))
    for g in gone:
        cf.delete(f'c:{slug}:{g}')
    cf.put(f'comments:{slug}', json.dumps([c for c in summary if c.get('id') not in gone]))
    print(f'deleted {len(gone)} comment(s) from {slug}: "{target.get("text", "")[:60]}"'
          + (f' and {len(gone) - 1} repl{"y" if len(gone) == 2 else "ies"}' if len(gone) > 1 else ''))
    return 0


def cmd_restore(args):
    """Undo a delete: bring a comment back from the trash, with its replies."""
    if args.backend == 'node':
        d = node_admin(args).call('POST', '/api/comments/admin/restore', {'slug': args.slug, 'id': args.id})
        print(f'restored {len(d.get("restored", []))} comment(s) on {args.slug}: '
              f'"{(d.get("comment") or {}).get("text", "")[:60]}"')
        return 0
    cf = creds(args)
    slug, cid = args.slug, args.id
    trashed = {k.split(':', 2)[2]: cf.get_json(k, None) for k in cf.keys(f'trash:{slug}:')}
    back = {i: c for i, c in trashed.items() if c and (i == cid or c.get('parent') == cid)}
    if cid not in back:
        sys.exit(f'No comment {cid} in the trash of {slug}.')
    for i, c in back.items():
        cf.put(f'c:{slug}:{i}', json.dumps(c))
    cf.put(f'deleted:{slug}', json.dumps(sorted(set(cf.get_json(f'deleted:{slug}', [])) - set(back))))
    summary = {c['id']: c for c in cf.get_json(f'comments:{slug}', []) if c.get('id')}
    summary.update(back)
    cf.put(f'comments:{slug}', json.dumps(sorted(summary.values(), key=lambda c: c.get('at', ''))))
    for i in back:
        cf.delete(f'trash:{slug}:{i}')
    print(f'restored {len(back)} comment(s) on {slug}: "{back[cid].get("text", "")[:60]}"')
    return 0


def cmd_repair(args):
    cf = creds(args)
    slugs = args.slug or sorted(k[len('comments:'):] for k in cf.keys('comments:'))
    for slug in slugs:
        summary = cf.get_json(f'comments:{slug}', [])
        deleted = set(cf.get_json(f'deleted:{slug}', []))
        keyed = {k.split(':', 2)[2] for k in cf.keys(f'c:{slug}:')}
        by_id = {c['id']: c for c in summary if c.get('id')}
        for cid in keyed - set(by_id):
            rec = cf.get_json(f'c:{slug}:{cid}', None)
            if rec:
                by_id[cid] = rec
        migrated = 0
        for cid, c in by_id.items():                  # records from older versions
            if cid not in keyed and cid not in deleted:
                cf.put(f'c:{slug}:{cid}', json.dumps(c))
                migrated += 1
        final = sorted((c for c in by_id.values() if c['id'] not in deleted), key=lambda c: c.get('at', ''))
        cf.put(f'comments:{slug}', json.dumps(final))
        print(f'{slug}: {len(final)} comments in the summary, {migrated} migrated to per-comment keys')
    return 0


def cmd_setup(args):
    cf = creds(args)
    ns = cf._ns
    if not ns:
        found = [n for n in cf.namespaces() if n['title'] == cf.title]
        if found:
            ns = found[0]['id']
            print(f'KV namespace "{cf.title}" exists: {ns}')
        else:
            ns = cf.call('POST', f'/accounts/{cf.account}/storage/kv/namespaces', {'title': cf.title})['result']['id']
            print(f'KV namespace "{cf.title}" created: {ns}')
    proj = cf.call('GET', f'/accounts/{cf.account}/pages/projects/{args.project}')['result']
    configs = {}
    for env_name in ('production', 'preview'):
        current = ((proj.get('deployment_configs') or {}).get(env_name) or {}).get('kv_namespaces') or {}
        merged = {k: {'namespace_id': v['namespace_id']} for k, v in current.items()}
        merged['COMMENTS'] = {'namespace_id': ns}
        configs[env_name] = {'kv_namespaces': merged}
    cf.call('PATCH', f'/accounts/{cf.account}/pages/projects/{args.project}', {'deployment_configs': configs})
    print(f'Pages project "{args.project}": COMMENTS bound to {ns} (production and preview).')
    print('Deploy once more so the binding reaches the running Function.')
    return 0


def main():
    ap = argparse.ArgumentParser(description='Owner tools for artifact-comments',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--backend', choices=('cloudflare', 'node'), default='cloudflare',
                    help='which server holds the comments (default: cloudflare)')
    ap.add_argument('--creds', help='cloudflare: JSON file with api_token, account_id, kv_namespace_id')
    ap.add_argument('--namespace-id', default=None, help='cloudflare: KV namespace id')
    ap.add_argument('--namespace-title', default=DEFAULT_TITLE, help='cloudflare: KV namespace title')
    ap.add_argument('--base', default=None, help='site or server URL (also accepted after the command)')
    ap.add_argument('--token', default=None, help='node: owner token (or ARTIFACT_COMMENTS_TOKEN)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    # Repeated on each command. SUPPRESS keeps a value given before the command.
    def base_token(p):
        p.add_argument('--base', default=argparse.SUPPRESS, help='site or server URL')
        p.add_argument('--token', default=argparse.SUPPRESS, help='node: owner token')

    p = sub.add_parser('list', help='print comments as threads')
    p.add_argument('--slug', action='append',
                   help='page slug; repeat for several; omit for all (needs creds, or a token on node)')
    base_token(p)
    p.add_argument('--title', action='append', help='slug=Readable title, for nicer headings')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('delete', help='remove a comment and its replies')
    p.add_argument('--slug', required=True)
    p.add_argument('--id', required=True)
    base_token(p)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser('restore', help='undo a delete, from the trash')
    p.add_argument('--slug', required=True)
    p.add_argument('--id', required=True)
    base_token(p)
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser('repair', help='rebuild summaries from per-comment keys')
    p.add_argument('--slug', action='append')
    p.set_defaults(func=cmd_repair)

    p = sub.add_parser('setup', help='create the namespace and bind it to a Pages project')
    p.add_argument('--project', required=True)
    p.set_defaults(func=cmd_setup)

    a = ap.parse_args()
    check_backend(a)
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
