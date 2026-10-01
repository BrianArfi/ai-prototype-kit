# Setup

[Back to the README](../README.md)

## 1. Install into your project

Any folder you open with Claude Code.

```bash
git clone https://github.com/BrianArfi/ai-prototype-kit
python ai-prototype-kit/scripts/install.py /path/to/your-project
```

This copies the kit to `.claude/skills/ai-prototype-kit/`, the five commands to `.claude/commands/`, and adds `.kit-build/` to `.gitignore`. To do it by hand, copy the five files in `commands/` into `.claude/commands/` and the whole kit into `.claude/skills/ai-prototype-kit/`.

## 2. Build a prototype

In Claude Code, in that project:

```
/mockup an order-ahead flow for a coffee shop: menu, customise the drink, pay, pick-up status
```

It writes the step list first, then the HTML file.

## 3. Publish it

You need a free Cloudflare account. Create an API token at <https://dash.cloudflare.com/profile/api-tokens> with **Account > Cloudflare Pages > Edit** and **Account > Workers KV Storage > Edit**, then set it in your shell:

```bash
export CLOUDFLARE_API_TOKEN=...      # PowerShell: $env:CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_ACCOUNT_ID=...
```

Then run `/publish`. It asks before anything goes online, and prints a link like `https://my-prototypes.pages.dev/coffee-order`.

## 4. Share the link

Reviewers open it, press **Comment** at the bottom right, and click the part they mean.

## 5. Revise

Run `/revise-from-comments`. Read its per-comment report, then `/publish` again. Same link, new version.

## Try it first, on your machine

No Cloudflare account needed. From the kit folder, with Node 22.13 or later:

```bash
python scripts/publish.py --config examples/kit.json serve
```

Open <http://127.0.0.1:8787/coffee-order>. Press `1` to `4` to jump between screens and space to play the flow. Press **Comment** and click anything. Open the page in a second browser to see the comment arrive.

## Requirements

- **Claude Code**, or another AI coding tool that can follow markdown instructions and edit files.
- **Python 3.8 or later.** The scripts use the standard library only.
- **Node.js.** `npx` runs Cloudflare's `wrangler` for uploads. Node 22.13 or later for `serve` and self-hosting.
- **A free Cloudflare account** for public links, or your own server.
- To run the tests: `pip install playwright && python -m playwright install chromium`, then `python tests/test_example.py`.
