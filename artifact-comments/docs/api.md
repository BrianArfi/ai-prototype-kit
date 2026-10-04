# API, data model and storage

[Back to the README](../README.md)

## API

`GET /api/comments?slug=<slug>` returns `{"comments": [...]}`, oldest first.

`POST /api/comments` with a JSON body returns `{"comment": {...}, "key": "..."}`: the stored record, plus the comment's delete key. The key is sent once, to the author only, and the server keeps only its SHA-256. The browser client saves it in `localStorage`, so its author can delete the comment later.

| Field | Rules |
| :--- | :--- |
| `slug` | Required. `^[a-z0-9][a-z0-9-]{0,79}$` |
| `name` | Required, 60 characters at most |
| `text` | Required, 1,000 characters at most, line breaks kept |
| `parent` | Optional. The id of the comment this replies to. A reply to a reply joins the top comment's thread |
| `where` | Optional, 200 characters. Readable place, shown in the list |
| `anchor` | Optional, top-level comments only. `{sel, text, tag, fx, fy}`, where `fx` and `fy` are 0 to 1 |
| `state` | Optional, top-level comments only. Any JSON object up to 600 characters |

The server sets `id` and `at` (ISO time). Errors: `400` for invalid input, `413` for a body over 8 KB (8,192 bytes of UTF-8, not characters), `429` once a page holds 1,000 comments (on Cloudflare a soft cap: posts arriving in the same instant can pass it by a few; on Node it is exact).

`DELETE /api/comments` with `{"slug", "id", "key"}` deletes a comment and returns `{"deleted": [ids]}`. Two callers may delete:

- **The author**, with the comment's own `key`.
- **The page owner**, with `Authorization: Bearer <owner key>` and no `key`. The owner key is the `OWNER_KEY` secret of the Pages project on Cloudflare, and `--token` on Node. In the browser, the owner opens any page once with `?ac-owner=<owner key>`. The client stores the key for the site and removes it from the address bar. `?ac-owner=` (empty), or "exit" in the list footer, turns owner mode off.

Deleting a top comment also deletes its replies, as in Figma. Deletes are soft: the records go to the trash, and `comments_cli.py restore` undoes them. Errors: `403` with no valid key or owner key, `404` for a comment that does not exist or is already deleted. Comments posted before 1.1.0 have no key, so only the owner can delete them.

`OPTIONS /api/comments` answers a CORS preflight from an allowed origin (`ALLOWED_ORIGINS` on Cloudflare, `--allow-origin` on Node) with `Access-Control-Allow-Origin`, `-Methods: GET, POST, DELETE, OPTIONS` and `-Headers: content-type, authorization`. Any other origin gets no CORS headers.

Both backends implement this contract with the same validation code. `functions/api/comments.js` stays a single self-contained file, because publishers copy it on its own.

## Data model and storage

A stored comment is the cleaned fields plus `id` and `at`. The slug is the list it belongs to, not a field of the record:

```json
{
  "id": "mg1k2x9fa3",
  "parent": null,
  "name": "Dina",
  "text": "Can we lead with the price here?",
  "where": "Tab: Overview",
  "anchor": { "sel": "main > div:nth-of-type(2) > p", "text": "The overview explains the offer in one paragraph.", "tag": "p", "fx": 0.31, "fy": 0.5 },
  "state": { "tab": "a" },
  "at": "2026-09-30T08:12:44.120Z"
}
```

A reply carries the top comment's id in `parent`, and `null` for `anchor` and `state`.

On Node, everything is one `comments` table in the SQLite file: one row per comment, with the stored record, the SHA-256 of its delete key (`key_hash`), and a `deleted_at` mark set by a delete. The rest of this section is about Cloudflare.

Workers KV keys, all in one namespace:

| Key | Holds |
| :--- | :--- |
| `c:<slug>:<id>` | One comment. Written once, never changed |
| `comments:<slug>` | Every comment of the page, the only key a page view reads |
| `deleted:<slug>` | Ids removed by the owner or the author, so a rebuild never restores them |
| `k:<slug>:<id>` | SHA-256 of the comment's delete key. Never served |
| `trash:<slug>:<id>` | A deleted comment, kept so `restore` can undo the delete |

Per page view: 1 KV read, and 1 more every 30 seconds while the tab is visible. Per comment: 2 writes and 2 key listings. The free Workers plan allows 100,000 reads and 1,000 writes and listings a day, which is roughly 500 comments a day across all pages.

KV is eventually consistent. A comment can take up to about 60 seconds to reach a reader in another region. The person who posted it sees it at once, because the client keeps its own posts until the server returns them.

