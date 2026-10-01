# Testing

[Back to the README](../README.md)

```bash
pip install playwright && python -m playwright install chromium
python tests/e2e_test.py                  # Cloudflare function, on wrangler pages dev
python tests/e2e_test.py --backend node   # the same suite on the Node server
python tests/e2e_test.py --backend both
```

`--backend wrangler` (the default) starts `wrangler pages dev` with a fresh local KV; `--backend node` starts `server/node/server.mjs` on a fresh SQLite file. Either way the suite drives the demo page in Chromium. The core 65 checks cover picking, pins, threads, replies, the list jump across tabs, scroll boxes, iframes, clicks and keys that must not reach the page, a second reader, offline and failed posts, markup in comments, a phone-sized screen, records from the first version, and 12 simultaneous posts. On top of those: the panel footer version, a page on another origin posting through CORS, preflight and origin checks, the byte-accurate size limit, and `comments_cli.py list` through the public API (72 checks). The Node run adds the owner CLI round trip, post, list, delete and restore, with a wrong token and `repair` refused (78 checks). Nothing touches your Cloudflare account.

