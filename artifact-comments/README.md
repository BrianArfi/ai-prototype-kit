# artifact-comments

**Get feedback pinned to the exact spot on the HTML pages you share, not scattered across chat screenshots.**

For anyone who shares AI-built HTML pages (Claude artifacts, v0, Lovable exports, slide decks) and wants feedback on the exact spot.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version 1.0.2](https://img.shields.io/badge/version-1.0.2-green.svg)](CHANGELOG.md)

![A reader pins a comment on a part of the page, a second reader replies in the thread, and the comment list jumps to a part on another tab](docs/demo.gif)

## Why

- AI builds an explainer, a prototype or a slide deck in minutes, but a shared HTML page has no comment button.
- So feedback comes back as chat screenshots with red circles, and "the top left one" on a slide nobody can name.
- Your replies land in one chat, and the other reviewers never see them.

## What it does

- **Comments pinned to the spot.** Readers click any part of the page and write a note there.
- **Threads everyone sees.** Replies sit under the comment, for anyone who opens the link.
- **A list that jumps.** Click a comment and the page goes to its part, even on another tab or slide.
- **No accounts.** Reviewers type a name once.
- **Your data stays yours.** Run it on your own server or a free Cloudflare account. No third-party service.

## Quick start

You need Node 22.13 or later. Nothing is installed from npm.

```bash
git clone https://github.com/BrianArfi/artifact-comments
cd artifact-comments
node server/node/server.mjs --static examples
```

Open <http://127.0.0.1:8787/demo>, press **Comment** at the bottom right, and click anything. To use it on your own pages, add this line before `</body>` and point `--static` at their folder:

```html
<script src="/artifact-comments.js" data-slug="my-page" defer></script>
```

## Example

![A thread pinned on a paragraph: Dina asks a question and Sam replies under it](docs/thread.png)

Dina pins a question on a paragraph. Sam replies. Everyone who opens the link sees the thread.

---

## Documentation

- [How it works](docs/how-it-works.md): the review loop, every feature, screenshots and the architecture.
- [Backends](docs/backends.md): choose between Cloudflare Pages + KV, self-hosted Node + SQLite, and Docker, with setup steps and server flags.
- [The adapter](docs/adapter.md): make tabs, slide decks and walkthroughs bring back the right view for each comment.
- [Owner CLI](docs/owner-cli.md): list, delete, restore and repair comments.
- [API, data model and storage](docs/api.md): the HTTP contract both backends implement.
- [How it compares](docs/comparison.md): against Pastel, Markup.io, Hypothesis and Vercel preview comments.
- [Testing](docs/testing.md): the end-to-end suite on either backend.

artifact-comments is part of the [AI Prototype Kit](https://github.com/BrianArfi/ai-prototype-kit), where it is the comment layer on every page the kit publishes. It also works on its own, on any static page.

## Read comments from the terminal (Python 3)

You can read the whole round from the terminal with the [owner CLI](docs/owner-cli.md). It needs Python 3.8 or later:

```
$ python scripts/comments_cli.py list --base http://127.0.0.1:8787 --slug offer

offer  (offer)  1 threads, 2 comments
  #1 Dina · 01 Oct 17:07 · Tab: Overview
     on "The overview explains the offer in one paragraph."
     Can we lead with the price here?
     ↳ Sam · 01 Oct 17:07: Agreed, moving it up in the next version.
     id mupdemw1xwcec5

2 comments across 1 pages
```

The backends are a single Node file on SQLite or Cloudflare Pages with Workers KV. See [Backends](docs/backends.md).

## Who it is for

Anyone who sends HTML pages out for feedback: PMs, founders, consultants, designers and team leads who share explainers, mockups, clickable prototypes, slide decks or reports. It suits unlisted review links sent to people who should not need to sign up for anything. If you need verified identity, roles or tracker integrations, a hosted review tool is a better fit (see [How it compares](docs/comparison.md)).

## Script options

| Attribute | Default | Meaning |
| :--- | :--- | :--- |
| `data-slug` | the file name | Which comment list the page uses |
| `data-api` | `/api/comments` | The endpoint URL |
| `data-position` | `right` | `left` puts the buttons and the list at the bottom left, for pages that already use the right corner |
| `data-changelog` | the project changelog on GitHub | Where the "What's new" link in the Comments panel footer points |

The same keys (`slug`, `api`, `position`, `changelog`) can also be set on `window.ArtifactComments`. The client's version is in its `VERSION` constant, shown in the panel footer and exposed as `window.__artifactComments.version`.

## Requirements

- **Any static HTML page**: an explainer, mockup, prototype, deck or report. The client needs a current Chrome, Edge, Firefox or Safari, on desktop or mobile.
- **A place to store comments**, one of:
  - **Node 22.13 or later** for the self-hosted server. No npm packages.
  - **A Cloudflare account** with Pages and Workers KV.
  - **Docker**, optional, to run the Node server in a container.
- **Python 3.8 or later** for the owner CLI. Standard library only.
- To run the tests: `pip install playwright && python -m playwright install chromium`, plus `npx wrangler` for the Cloudflare suite.

## Security and limits

- **No login.** Anyone who can open the page can comment and give any name. The pages are meant to be unlisted review links. Do not use this for anything that needs identity.
- **Moderation** is owner-only, through the CLI. There is no delete or edit button in the page.
- **Text only.** All comment content is rendered as text, never as HTML.
- **Owner endpoints** on the Node server are off until a token is set, need `Authorization: Bearer <token>`, and never send CORS headers.
- **CORS is opt-in** on both backends. Unset, only same-origin pages can post.
- Caps: 1,000 comments per page, 8 KB per request, and the field limits in the [API](docs/api.md).
- **No export or import yet.** Comments cannot be moved between backends in 1.0.0. The server sets `id` and `at` on every post, so re-posting records would not keep them.
- **The keyboard shield has one gap.** A page listener registered on `window` in the capture phase before this script loads still sees the keys. That setup is rare.
- Browsers: current Chrome, Edge, Firefox and Safari, on desktop and mobile. It needs Shadow DOM and `fetch`.

## Files

```
client/artifact-comments.js      the browser script
functions/api/comments.js        the Cloudflare Pages Function
server/node/server.mjs           the self-hosted Node server (plus package.json, Dockerfile)
scripts/comments_cli.py          list, delete, restore, repair, setup
examples/demo.html               a page with an adapter
tests/e2e_test.py                end-to-end tests, on either backend
docs/                            reference guides, the demo GIF and screenshots
CHANGELOG.md                     what changed in each version
LICENSE, NOTICE                  Apache-2.0
SKILL.md                         instructions for Claude Code
```

## FAQ

**Do reviewers need to sign up?**
No. A reader types a name once, and the browser remembers it. The trade-off is that names are not verified, so use unlisted review links and nothing that needs identity. See [Security and limits](#security-and-limits).

**Will it change or break my page?**
No. It adds one host element to `<html>` and draws inside its Shadow DOM. Your DOM, CSS and event handlers stay as they are, and the picking click and typed keys never reach the page.

**Can a reader delete or edit a comment?**
No. Only the owner can, with the [owner CLI](docs/owner-cli.md). Deletes are soft on both backends and can be undone with `restore`.

**Does it work on a slide deck, a single-page app or a prototype?**
Yes. Without an adapter, pins still land on the right element when it is on screen. Add the [adapter](docs/adapter.md) so the list can bring back the right slide, tab or screen.

**What does it cost, and where does my data go?**
The code is free under Apache-2.0. On Cloudflare, the free Workers plan covers roughly 500 comments a day across all pages; on Node, it costs whatever your server costs. The comments stay in your own KV namespace or SQLite file. Nothing is sent anywhere else.

## Changelog

The full history is in [CHANGELOG.md](CHANGELOG.md), in Keep a Changelog format.

**Latest: [1.0.2] - 2026-10-01.** README rewritten to open with the problem; reference moved to docs/. No code changes. **Before that, [1.0.0] - 2026-09-30.** The backend is now swappable: a self-hosted Node server on SQLite joins the Cloudflare function, with token-protected owner endpoints, a Dockerfile and opt-in CORS.

## Contributing

Issues and pull requests are welcome.

- Run `python tests/e2e_test.py --backend both` (see [Testing](docs/testing.md)) before you open a pull request. Every check must pass.
- Keep it dependency-free: no npm packages in the client or the servers, standard library only in the CLI.
- Keep `functions/api/comments.js` one self-contained file. Publishers copy it on its own.
- A behaviour change on one backend needs the same change on the other, so the [API](docs/api.md) stays one contract.
- A release bumps the version in three places together: `VERSION` in `client/artifact-comments.js`, `server/node/package.json`, and a new section in `CHANGELOG.md`.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). The [AI Prototype Kit](https://github.com/BrianArfi/ai-prototype-kit) bundles this project under the same license.

More AI skills: [BrianArfi.com/skills](https://BrianArfi.com/skills)
