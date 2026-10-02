# Changelog

All notable changes to the AI Prototype Kit are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- README reorganised around the problem: a concrete scenario, who it is for and not for, a before/after table, and a four-step how-it-works. New explainer GIFs `docs/hero.gif`, `docs/before-after.gif` and `docs/how-it-works.gif` (illustrations, built from the real before/after screenshots), rendered with `docs/src/render_gifs.py`. The real-run `docs/demo.gif` and `docs/revise-loop.gif` are unchanged.

## [0.1.2] - 2026-10-01

### Changed
- README visuals. `docs/demo.gif` now starts on the Oat latte screen, pins Dina's comment on Large, shows the report row a real `/revise-from-comments` run printed, and ends on the same link with Large selected at $5.10. It is recorded with `docs/src/record_demo.py`. `docs/hero.png` uses real before and after screenshots from that run, plain paper and the shared eyebrow mark.
- Bundled artifact-comments updated to v1.0.3 (README visuals only).

### Fixed
- `examples/coffee-order.html` shows the price for the selected default size on load. Before, a page whose default size was not Medium still showed the Medium price until the reader clicked a size.

## [0.1.1] - 2026-10-01

### Changed
- README rewritten to open with the problem; reference moved to docs/ ([how-it-works.md](docs/how-it-works.md), [setup.md](docs/setup.md), [publish-script.md](docs/publish-script.md), [faq.md](docs/faq.md)). No code changes.
- The tagline now says it is a Claude Code kit. The quick start adds the revise step.
- New hero GIF, `docs/revise-loop.gif`: a comment pinned on the coffee-order prototype, `/revise-from-comments`, and the same link reloaded with the change.
- Bundled artifact-comments updated to v1.0.2 (README only).
- New README visuals: `docs/hero.png` (rendered from `docs/src/hero.html` with `docs/src/render.py`, using real screenshots of the example) and `docs/demo.gif` (a real click-through and comment on the served example). `docs/revise-loop.gif` moves to the Example section.

## [0.1.0] - 2026-09-30

First release.

### Added
- `/mockup`: a clickable HTML prototype of a flow, with presenter controls (number keys, arrows, autoplay, hide bar) and a required comment adapter.
- `/deck`: a keyboard-driven slide deck in one HTML file, with a comment adapter.
- `/artifact`: a one-page explainer, proposal or report in one HTML file, readable on a phone.
- `/publish` and `scripts/publish.py`: one command from an HTML file to a stable link on Cloudflare Pages. Config in `kit.json`. `build` assembles the site with clean page slugs, adds the comment script to each page, copies the comment client and Pages Function, and writes an index page. `deploy` creates the Pages project and the comment store on the first run, then uploads with `wrangler pages deploy`. `deploy --dry-run` builds and prints the links without uploading. `serve` runs the site locally with the self-hosted comments server. All subprocess output is decoded as UTF-8, so a Windows console does not crash on wrangler's output.
- `/revise-from-comments`: reads the comments on a page, groups them per thread, edits the source HTML, and reports per comment what changed or why not. Comment text is treated as data, never as instructions.
- `artifact-comments` v1.0.0, vendored with `scripts/vendor_comments.py` (the source version is in `artifact-comments/VENDORED.json`).
- `examples/coffee-order.html`: a four-screen order-ahead prototype with presenter controls and a comment adapter, plus `examples/kit.json`.
- `scripts/install.py`: installs the kit and its commands into a Claude Code project.
- `tests/test_example.py`: the publish build (tag injected, function copied, dry run), and the example in a real browser on the Node backend: post a comment on screen 2, reload, jump back to it from the list.
- `SKILL.md`, `LICENSE` (Apache-2.0) and `NOTICE`.
