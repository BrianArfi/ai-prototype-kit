# Backends: Cloudflare, Node, Docker

[Back to the README](../README.md)

## Choose your backend

The client talks to one URL, set with `data-api` (default `/api/comments`). Both backends implement the same [API](api.md) with the same validation code, so the choice is about where you want to run it.

| | Cloudflare Pages + KV | Self-hosted Node + SQLite | Docker |
| :--- | :--- | :--- | :--- |
| Best for | Pages you already deploy on Cloudflare Pages | Any server or laptop, pages on any host | A container platform |
| You run | Nothing: the function runs on Cloudflare | `node server/node/server.mjs` | The image from `server/node/Dockerfile` |
| Storage | Workers KV, one key per comment | One SQLite file | One SQLite file in the `/data` volume |
| Cost | Free plan covers about 500 comments a day | Your server | Your server |
| Consistency | Eventual, up to about 60 seconds between regions | Immediate | Immediate |
| 1,000-comment cap | Soft | Exact | Exact |
| Moderation | `comments_cli.py` through the Cloudflare API | `comments_cli.py --backend node` through owner endpoints | Same as Node |

### Cloudflare Pages + KV

You need a Cloudflare account and a Pages project that serves your HTML.

**1. Copy two files into the project you deploy.**

```
your-site/                        <- the directory you deploy
  artifact-comments.js            <- from client/
  my-page.html
functions/api/comments.js         <- from functions/api/, next to (not inside) your-site
```

`functions/` sits in the directory you run `wrangler pages deploy` from.

**2. Add the script to each page**, just before `</body>`:

```html
<script src="/artifact-comments.js" data-slug="my-page" defer></script>
```

`data-slug` names the page's comment list: lowercase letters, digits and dashes, up to 80 characters. Leave it out to use the file name.

**3. Create an API token** at <https://dash.cloudflare.com/profile/api-tokens>, custom token, with:

- Account > Workers KV Storage > Edit
- Account > Cloudflare Pages > Edit

**4. Create the store and connect it to the project:**

```bash
export CF_API_TOKEN=...  CF_ACCOUNT_ID=...
python scripts/comments_cli.py --namespace-title my-site-comments setup --project my-pages-project
```

This creates the KV namespace if it does not exist and binds it to the project as `COMMENTS`, for production and preview. It keeps any other KV bindings the project already has.

**5. Deploy** as usual, for example `npx wrangler pages deploy your-site --project-name my-pages-project`. Open the page. The two buttons are at the bottom right.

**Pages on another origin.** To let pages on other origins call this endpoint, set the Pages environment variable `ALLOWED_ORIGINS` to a comma-separated list of origins (for example `https://docs.example.com,https://review.example.com`), or `*` for any origin. Unset, the endpoint serves same-origin pages only.

### Self-hosted Node + SQLite

`server/node/server.mjs` serves the same API from one file. It needs Node 22.13 or later and nothing from npm.

```bash
node server/node/server.mjs --static examples      # then open http://127.0.0.1:8787/demo
```

| Flag | Default | Meaning |
| :--- | :--- | :--- |
| `--port` | `8787` (or `$PORT`) | Listen port |
| `--host` | `127.0.0.1` (or `$HOST`) | Listen address. Use `0.0.0.0` in a container |
| `--db` | `comments.db` | The SQLite file. Created on first start |
| `--static DIR` | none | Also serve a folder of pages, with clean URLs (`/demo` serves `demo.html`). `/artifact-comments.js` is served from `client/` when the folder does not have it |
| `--allow-origin O` | none | Let pages on origin `O` call the API through CORS. Repeat it, give a comma list, or `*`. `ALLOWED_ORIGINS` works too |
| `--token T` | none | Turn on the owner endpoints. `ARTIFACT_COMMENTS_TOKEN` works too |

Node prints an `ExperimentalWarning` for `node:sqlite`. `npm start` in `server/node/` passes `--no-warnings=ExperimentalWarning`, and `npm run demo` starts the server on the example page.

When the pages live on another host, run the server with `--allow-origin https://your.site` and point each page at it:

```html
<script src="https://comments.your.site/artifact-comments.js"
        data-api="https://comments.your.site/api/comments" data-slug="my-page" defer></script>
```

**Owner endpoints**, only when a token is set, called with `Authorization: Bearer <token>`. Without a token they answer `403`; with a wrong token, `401`.

| Request | Does |
| :--- | :--- |
| `GET /api/comments/admin?slug=S` | `{"pages": {slug: {"comments": [...], "deleted": [...]}}}` for one page, or every page when `slug` is left out |
| `POST /api/comments/admin/delete {slug, id}` | Soft delete a comment and its replies. They stay in the file, marked deleted |
| `POST /api/comments/admin/restore {slug, id}` | Undo that delete, with the replies |

`comments_cli.py --backend node` calls these for you (see [Owner CLI](owner-cli.md)).

### Docker

Build from the repository root, so the client script is in the image:

```bash
docker build -f server/node/Dockerfile -t artifact-comments .
docker run -p 8787:8787 -v ac-data:/data -e ARTIFACT_COMMENTS_TOKEN=change-me artifact-comments
```

The image runs the Node server on `0.0.0.0:8787` and keeps the database in the `/data` volume. Add `-e ALLOWED_ORIGINS=https://your.site` when the pages are served from another origin, and point each page at the server with `data-api="https://comments.your.site/api/comments"`. To serve pages from the container too, mount them at `/site` and add `--static /site` after the image name.

