---
description: Prototype - Publish an HTML prototype, deck or explainer as a shareable link with pinned comments
argument-hint: "<path to the HTML file, or blank to republish everything>"
---

Turn an HTML file into a link anyone can open on a phone or laptop, with pinned comments.

The kit lives at `.claude/skills/ai-prototype-kit/`. Below, `KIT` means that folder. Run every
command from the project root.

## 1. First time only: the config

If there is no `kit.json` in the project root, create one. Pick a project name in lowercase with
dashes. It becomes the subdomain, so `team-prototypes` gives `https://team-prototypes.pages.dev`.

```
python KIT/scripts/publish.py init --project <name> --title "<index page heading>"
```

Add `.kit-build/` to `.gitignore`. It holds the built site and local state.

## 2. Add the page

```
python KIT/scripts/publish.py add "<Page name>" <path/to/file.html>
```

The page name makes the slug: "Checkout flow v2" becomes `/checkout-flow-v2`. Adding a page with
the same name replaces it and keeps the link. Pass `--slug` to fix the link when the name changes,
and `--no-comments` for a page that must not take comments.

## 3. Check it, then ask

```
python KIT/scripts/publish.py deploy --dry-run
```

This builds `.kit-build/_site/`, adds the comment script to each page, and prints the links it
would publish. Nothing is uploaded.

**Publishing puts the page on the public internet**, at an unlisted link. Show the user the links
from the dry run and ask before step 4. Never publish a page with secrets, customer data, or
anything the user has not approved for sharing.

## 4. Publish

```
python KIT/scripts/publish.py deploy
```

It needs `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in the environment. If they are
missing, the script says how to create them. Never ask the user to paste a token into the chat:
they set it in their own shell. The first deploy creates the Pages project and the comment store
(Workers KV). Later deploys only upload.

Hand over the page links it prints, one per line. The same links work after every re-publish.

## Other ways to host

- **On this machine, with comments:** `python KIT/scripts/publish.py serve`, then open
  `http://127.0.0.1:8787/<slug>`. Needs Node 22.13 or later.
- **On your own server:** run `KIT/artifact-comments/server/node/server.mjs --static .kit-build/_site`
  there, or use its Dockerfile. See `KIT/artifact-comments/README.md`, "Choose your backend".

## Reading comments

`python KIT/scripts/publish.py comments [slug]` prints every thread. To act on them, use
`/revise-from-comments`.

Page: $ARGUMENTS
