# Changelog

All notable changes to artifact-comments are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-10-04

### Added
- Delete from the page. Each new comment comes back with a delete key, sent once to its author; the browser keeps it and shows **Delete** on that comment. The server stores only the key's SHA-256.
- Owner mode. Open any page once with `?ac-owner=<owner key>` to get **Delete** on every comment of the site. The key leaves the address bar at once; "exit" in the list footer turns owner mode off. The owner key is the `OWNER_KEY` Pages secret on Cloudflare and `--token` on Node.
- `DELETE /api/comments {slug, id, key?}` on both backends, with `Authorization: Bearer` for the owner. A top comment goes with its replies. Deletes are soft, so `comments_cli.py restore` undoes them.
- **Discard** next to Retry on a comment that was not sent.

### Changed
- CORS preflight now allows `DELETE` and the `authorization` header.
- The Node server adds a `key_hash` column to an existing database on start.
- README only: a concrete problem scenario, who it is for and not for, a before/after table, and four new GIFs. `docs/hero.gif`, `docs/before-after.gif` and `docs/how-it-works.gif` are illustrations built on real screenshots of the client; `docs/owner-demo.gif` is a real run of a reader comment and the owner CLI (`list`, then `delete`). Script options, requirements, limits and files move into collapsed sections. `python docs/src/render.py owner` and `anim` re-render the new GIFs. No behaviour changes.

## [1.0.3] - 2026-10-01

### Changed
- README visuals only. The hero gives the page screenshot more room and uses the shared family eyebrow and plain paper. The demo GIF is recorded inside the same browser frame as the hero, with a larger cursor. It shows a reply under a different name and a jump from the list to a comment on another tab (`docs/src/sample.html` now has tabs and an adapter). The client's version constant moves to 1.0.3. No behaviour changes.

## [1.0.2] - 2026-10-01

### Changed
- README rewritten to open with the problem; reference moved to docs/. No code changes.
- The README top follows the shape of popular open-source READMEs: one line on the problem and who it is for, the demo GIF, Why, What it does, Quick start and a screenshot example. The reference sections move into `docs/` ([how-it-works.md](docs/how-it-works.md), [backends.md](docs/backends.md), [adapter.md](docs/adapter.md), [owner-cli.md](docs/owner-cli.md), [api.md](docs/api.md), [comparison.md](docs/comparison.md), [testing.md](docs/testing.md)), linked from a Documentation list. The stars badge is dropped.

## [1.0.1] - 2026-10-01

### Changed
- The README is rewritten around the problem it solves: the shift, the gap, the fix, the loop and a capability table come first. Every technical section is kept. No code changes.

## [1.0.0] - 2026-09-30
<!-- source: git log of the private source repo, commit "feat(artifact-comments): v1.0.0 standalone, swappable backend" (2026-09-30), exported as tag v1.0.0 by publish_skill_repo.py -->

### Added
- A self-hosted backend, `server/node/server.mjs`. It needs Node 22.13 or later and no npm packages: storage is one SQLite file through the built-in `node:sqlite`. It serves the same `/api/comments` contract and validation as the Cloudflare function, runs every POST in one transaction, and can serve a folder of pages with clean URLs (`--static`).
- Owner endpoints on the node server, protected by a token (`--token` or `ARTIFACT_COMMENTS_TOKEN`): list every page, soft delete a comment with its replies, and restore it.
- `server/node/package.json` (engines `node >=22.13`) and a `Dockerfile`.
- Opt-in CORS on both backends: `ALLOWED_ORIGINS` (a comma list, or `*`) on Cloudflare, `--allow-origin` on the node server. Preflight requests from an allowed origin are answered, and any other origin gets no CORS headers.
- `comments_cli.py --backend cloudflare|node`. On `node`, `list`, `delete` and `restore` go through the owner endpoints with `--base` and `--token`. `repair` and `setup` stay Cloudflare only and refuse clearly on `node`.
- A version line in the Comments panel ("artifact-comments v1.0.0 · What's new") that links to this changelog. `data-changelog` points it somewhere else.
- `tests/e2e_test.py --backend wrangler|node|both` runs the one browser suite against either backend, plus checks for CORS, byte-accurate size limits, and the owner CLI round trip (post, list, delete, restore) on the node server.
- `LICENSE` (Apache-2.0) and `NOTICE`, so the skill can ship as a standalone repository.

### Changed
- The backend is swappable. The browser client still talks to one URL (`GET ?slug=`, `POST` JSON), set with `data-api`, and both backends implement that contract.

### Fixed
- Cross-origin pages could not use a comments endpoint on another origin: the server answered the preflight with a bare `204` and no CORS headers, although the README said it could.
- The 8 KB request limit counted characters, not bytes, so a body of multi-byte text sent without a `Content-Length` could pass it. It now counts UTF-8 bytes.

## [0.2.0] - 2026-09-30
<!-- source: git log of the private source repo, commits 82593b3bd (2026-09-29, "v2 comment layer - Figma-style pins, jump-to-part list, safe keys"), 10f240093 (2026-09-29, "comment jump survives a wrong stored flow") and 77256d3bc (2026-09-30, "shareable Figma-style comment skill on every artifact"). No git tag existed; the version label was assigned when v1.0.0 was prepared. -->

### Added
- Figma-style pins: each thread is a numbered pin at the exact point that was clicked, and clicking a pin opens its thread.
- A Comments list where every row jumps to its part: it restores the page state, scrolls to the part, flashes it and opens the thread.
- Replies, one level deep. A reply to a reply joins the top thread.
- The adapter API (`window.ArtifactComments`: `state`, `restore`, `isCurrent`, `search`, `label`, `pause`) for pages with tabs, slides or walkthroughs.
- Hide pins, "Not sent" with Retry for failed or offline posts, `Ctrl` + `Enter` to post and `Esc` to close.
- Storage of one key per comment plus a rebuilt per-page summary, so simultaneous posts are never lost and a page view costs one read.
- `comments_cli.py` with `list`, `delete` (to a trash), `restore`, `repair` and `setup`.
- `tests/e2e_test.py`, 65 browser checks against `wrangler pages dev`.
- The first standalone packaging as a skill, with a README and a demo page.
- The UI lives in a Shadow DOM attached to `<html>`, so page CSS cannot restyle it.

### Fixed
- The space bar and arrow keys no longer reach the page while a comment is typed or while comment mode is on.
- A jump to a comment whose recorded page state was wrong now searches the other states until the part is found.
- The comment form flips above the part when opening below it would push the Save button off screen.

## [0.1.0] - 2026-09-29
<!-- source: git log of the private source repo, commits f630b1a0e (2026-09-29, "click-to-comment layer on the customer journey artifact") and 20cb2d9be (2026-09-29, "shared comments, stored with the artifact"). No git tag existed; the version label was assigned when v1.0.0 was prepared. -->

### Added
- An inline click-to-comment layer on one published page: comment mode pauses playback, a click on any element places a numbered marker and asks for a name and a comment.
- Comments were first kept in the reader's browser, with a Copy all button to send them back.
- The same day, shared storage replaced that: a Cloudflare Pages Function (`/api/comments`) on Workers KV, so everyone who opens the page sees every comment, and a command to read them back.
