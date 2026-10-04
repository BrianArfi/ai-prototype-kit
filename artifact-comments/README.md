# artifact-comments

**Get feedback pinned to the exact spot on the HTML pages you share, not scattered across chat screenshots.**

For anyone who shares AI-built HTML pages (Claude artifacts, v0 or Lovable exports, slide decks, prototypes) and wants comments like in Figma, with no accounts.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version 1.0.3](https://img.shields.io/badge/version-1.0.3-green.svg)](CHANGELOG.md)

![Animated hero, "Feedback, pinned to the spot." First, scribbled screenshots from Dina, Maya and Sam pile up over a proposal page with "lead with this one?", "is the number real??" and "which button? the top left one?". They are swept away, three numbered pins pop onto the exact parts of the page, and the thread opens with Dina's question and Sam's reply. The page and the thread are real screenshots of the client; the chat cards and the pin animation are an illustration](docs/hero.gif)

## The problem

Maya asks Claude for a one-page proposal: "A shorter onboarding flow", with three stats, the new steps and a "Start the pilot" button. It takes ten minutes. She sends the link to Dina and Sam. Then the feedback arrives:

- Dina sends a screenshot with a red circle and "lead with this one?". Which part, the title or the paragraph?
- Sam asks "which button? the top left one?" in a different chat, and nobody knows which screenshot he means.
- Maya answers Dina in a DM. Sam never sees the answer and asks the same thing again.
- By the next draft, nobody can tell which notes were handled. The page has no comment button, so there is no shared place to look.

The faster AI builds the page, the more of this you get. artifact-comments adds the missing comment button: one script tag, and every reader can click any part of the page and leave a note there.

## Who it is for

**Good fit if you:**

- share HTML pages for review: explainers, mockups, clickable prototypes, slide decks, reports, often built with AI
- send unlisted review links to clients, bosses or outside reviewers who should not have to sign up for anything
- want the comments stored on your own server or your own Cloudflare account
- are fine adding one `<script>` line to the page (or asking your AI to)

**Not for you if you:**

- need verified identity, roles or permissions. Anyone with the link can comment under any name
- need statuses, assignees or sync to Jira or Linear. A hosted review tool fits better (see [How it compares](docs/comparison.md))
- cannot add a script tag to the page, or cannot run a small server or a Cloudflare Pages project
- want readers to edit their comments. Readers can delete their own, but nobody can edit

## Before and after

| Before | After |
| :--- | :--- |
| Feedback arrives as scribbled screenshots in several chats | Every comment lives on the page itself |
| "The top left one" and nobody knows which part | Each comment is a numbered pin on the exact spot that was clicked |
| Your reply reaches one reviewer | Replies sit under the comment, for everyone who opens the link |
| Reviewers are asked to create an account | Reviewers type a name once |
| A comment about slide 7 lands on slide 1 | The list brings back the right tab, slide or screen ([adapter](docs/adapter.md)) |
| Feedback sits in someone else's tool | Comments stay in your KV namespace or SQLite file |

![Illustration of before and after. Left, "Before": a team chat with Dina's and Maya's scribbled screenshots, Sam asking "which button? the top left one?" and you promising to copy a DM reply later. A slider wipes across to "After": the same proposal page with three numbered pins and an open thread under the first one. The page on the right is a real screenshot of the client](docs/before-after.gif)

## How it works

1. **Add one script tag** to any static HTML page, before `</body>`.
2. **Readers click a part.** They press **Comment**, click anything, type a name once and write. A numbered pin lands on that spot.
3. **Others reply** in the pin's thread. Everyone who opens the link sees it. Open tabs check for new comments every 30 seconds.
4. **Comments are saved on your backend**: a Cloudflare Pages Function with Workers KV, or one Node file with SQLite. Same API on both.
5. **You read and moderate** from the same link, or from the terminal with the owner CLI: `list`, `delete`, `restore`. Readers delete their own comments in the page, and you delete any comment there in owner mode (`?ac-owner=<owner key>`).

![Illustration of the flow in five cards that draw in one by one, with a lime dot moving along each arrow: 1 Add one script tag, 2 Readers click a part and a pin lands, 3 Others reply in one thread, 4 Saved on your backend (Cloudflare Pages + KV, or Node 22.13+ + SQLite), 5 You read and moderate with comments_cli.py. A side note lists what you do not need: reviewer accounts, npm packages or a build step, a third-party comment service](docs/how-it-works.gif)

The UI draws inside a Shadow DOM, so your CSS cannot break it and it cannot break your page. Clicks and keys used for commenting never reach the page, so decks and prototypes do not turn the slide while someone types. More in [How it works](docs/how-it-works.md).

## See it run

A real session on the Node server: Dina pins a question to the title, Sam switches the name and replies in the same thread, then the comment list jumps to Maya's comment on the other tab.

![The real UI in a browser window: Dina presses Comment, pins a note next to the page title, then Sam switches the name and replies in the thread. The comment list opens, and a click on Maya's comment switches to the Rollout plan tab and flashes the part it is pinned on](docs/demo.gif)

The owner side, also real: Dina adds a comment in the browser, then the owner CLI lists every thread on the page from the same server and deletes a spam post. The terminal text is the CLI's actual output from that run.

![A real run. In the browser, Dina presses Comment, clicks the intro paragraph and posts "Can we lead with the time saved?" as pin 3, next to Maya's and a spam post's pins. Then a terminal runs python scripts/comments_cli.py --backend node --base (the local server) list, which prints the three threads with who, where, the quoted part and each id, and then delete on the spam post, which prints "deleted 1 comment(s) from onboarding: Cheap followers, visit my site"](docs/owner-demo.gif)

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

For Cloudflare Pages or Docker, see [Backends](docs/backends.md).

## Example

![A thread pinned on a paragraph: Dina asks a question and Sam replies under it](docs/thread.png)

Dina pins a question on a paragraph. Sam replies. Everyone who opens the link sees the thread, and you read the whole round from the terminal with the [owner CLI](docs/owner-cli.md) (Python 3.8 or later): `python scripts/comments_cli.py list --base http://127.0.0.1:8787 --slug my-page`.

<details>
<summary><b>Script options</b></summary>

| Attribute | Default | Meaning |
| :--- | :--- | :--- |
| `data-slug` | the file name | Which comment list the page uses |
| `data-api` | `/api/comments` | The endpoint URL |
| `data-position` | `right` | `left` puts the buttons and the list at the bottom left, for pages that already use the right corner |
| `data-changelog` | the project changelog on GitHub | Where the "What's new" link in the Comments panel footer points |

The same keys (`slug`, `api`, `position`, `changelog`) can also be set on `window.ArtifactComments`. The client's version is in its `VERSION` constant, shown in the panel footer and exposed as `window.__artifactComments.version`.

</details>

<details>
<summary><b>Requirements</b></summary>

- **Any static HTML page.** The client needs a current Chrome, Edge, Firefox or Safari, on desktop or mobile.
- **A place to store comments**, one of: **Node 22.13 or later** for the self-hosted server (no npm packages), **a Cloudflare account** with Pages and Workers KV, or **Docker** to run the Node server in a container.
- **Python 3.8 or later** for the owner CLI. Standard library only.
- To run the tests: `pip install playwright && python -m playwright install chromium`, plus `npx wrangler` for the Cloudflare suite.

</details>

<details>
<summary><b>Security and limits</b></summary>

- **No login.** Anyone who can open the page can comment and give any name. The pages are meant to be unlisted review links. Do not use this for anything that needs identity.
- **Deleting** happens in the page. Authors delete their own comments, with a key their browser kept when they posted. The owner deletes any comment in owner mode (`?ac-owner=<owner key>`). There is no edit. The CLI lists, restores and repairs.
- **Text only.** All comment content is rendered as text, never as HTML.
- **Owner endpoints** on the Node server are off until a token is set, need `Authorization: Bearer <token>`, and never send CORS headers.
- **CORS is opt-in** on both backends. Unset, only same-origin pages can post.
- Caps: 1,000 comments per page, 8 KB per request, and the field limits in the [API](docs/api.md).
- **No export or import yet.** Comments cannot be moved between backends. The server sets `id` and `at` on every post, so re-posting records would not keep them.
- **The keyboard shield has one gap.** A page listener registered on `window` in the capture phase before this script loads still sees the keys. That setup is rare.
- It needs Shadow DOM and `fetch`.

</details>

<details>
<summary><b>Files</b></summary>

```
client/artifact-comments.js      the browser script
functions/api/comments.js        the Cloudflare Pages Function
server/node/server.mjs           the self-hosted Node server (plus package.json, Dockerfile)
scripts/comments_cli.py          list, delete, restore, repair, setup
examples/demo.html               a page with an adapter
tests/e2e_test.py                end-to-end tests, on either backend
docs/                            reference guides, GIFs and screenshots
docs/src/                        sources for every README image (render.py re-renders them)
CHANGELOG.md                     what changed in each version
LICENSE, NOTICE                  Apache-2.0
SKILL.md                         instructions for Claude Code
```

</details>

## Documentation

- [How it works](docs/how-it-works.md): the review loop, every feature, screenshots and the architecture.
- [Backends](docs/backends.md): Cloudflare Pages + KV, self-hosted Node + SQLite, and Docker, with setup steps and server flags.
- [The adapter](docs/adapter.md): make tabs, slide decks and walkthroughs bring back the right view for each comment.
- [Owner CLI](docs/owner-cli.md): list, delete, restore and repair comments.
- [API, data model and storage](docs/api.md): the HTTP contract both backends implement.
- [How it compares](docs/comparison.md): against Pastel, Markup.io, Hypothesis and Vercel preview comments.
- [Testing](docs/testing.md): the end-to-end suite on either backend.

artifact-comments is part of the [AI Prototype Kit](https://github.com/BrianArfi/ai-prototype-kit), where it is the comment layer on every page the kit publishes. It also works on its own, on any static page.

## FAQ

**Do reviewers need to sign up?**
No. A reader types a name once, and the browser remembers it. The trade-off is that names are not verified, so use unlisted review links and nothing that needs identity.

**Will it change or break my page?**
No. It adds one host element to `<html>` and draws inside its Shadow DOM. Your DOM, CSS and event handlers stay as they are, and the picking click and typed keys never reach the page.

**What happens to the pins when I edit the page?**
Each comment saves a CSS selector for the clicked element and the start of its text. If the selector no longer matches, the pin looks for an element of the same tag with the same text. If neither is found, no pin is drawn, but the thread stays in the Comments list.

**Does it work on a slide deck, a single-page app or a prototype?**
Yes. Without an adapter, pins still land on the right element when it is on screen. Add the [adapter](docs/adapter.md) so the list can bring back the right slide, tab or screen.

**Can I host the pages somewhere else, like GitHub Pages?**
Yes. Point `data-api` at your comments server and allow the page's origin on the server: `--allow-origin` on Node, `ALLOWED_ORIGINS` on Cloudflare. CORS is off until you set it. See [Backends](docs/backends.md).

**What if a reviewer's connection drops?**
The comment stays on screen as "Not sent" with a Retry button. It survives a reload and is sent again when the browser is back online.

**Can a reader delete or edit a comment?**
A reader can delete their own comments, from the browser they posted them in. Nobody can edit. The owner can delete any comment, in the page with owner mode or with the [owner CLI](docs/owner-cli.md). Deletes are soft on both backends and can be undone with `restore`.

**What does it cost, and where does my data go?**
The code is free under Apache-2.0. On Cloudflare, the free Workers plan covers roughly 500 comments a day across all pages; on Node, it costs whatever your server costs. The comments stay in your own KV namespace or SQLite file. Nothing is sent anywhere else.

## Changelog

The full history is in [CHANGELOG.md](CHANGELOG.md), in Keep a Changelog format. **Latest: [1.1.0] - 2026-10-04.** Delete from the page: authors delete their own comments, the owner deletes any comment in owner mode, and an unsent comment can be discarded. **Before that, [1.0.0] - 2026-09-30.** The backend is now swappable: a self-hosted Node server on SQLite joins the Cloudflare function, with token-protected owner endpoints, a Dockerfile and opt-in CORS.

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
