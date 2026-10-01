# How it compares

[Back to the README](../README.md)

Hosted review tools are good products. artifact-comments exists for a narrower case: a page you control, shared with people who should not need to sign up for anything. This table reflects each product's public documentation at the time of writing (September 2026). Check their docs for current plans.

| | artifact-comments | Pastel, Markup.io | Hypothesis | Vercel preview comments |
| :--- | :--- | :--- | :--- | :--- |
| Reviewer needs an account | No, a name only | Guests can comment; the owner needs a plan | Yes, a Hypothesis account | Yes, a Vercel account |
| Setup | One script tag | None on the page: reviewers open your URL inside their app | A script tag or a browser extension | Built into Vercel preview deployments |
| Self-hostable | Yes: one Node file, or your own Cloudflare account | No | Possible, as a larger multi-service stack | No |
| Works on any static page | Yes, on any host | Most public URLs, through their app | Yes | Vercel deployments only |
| Comments attach to | A point on any element, plus page state (tab, slide) | A point on the page | A text selection | A point on the page |
| Your data lives | In your KV namespace or SQLite file | Their servers | Their servers, or yours if self-hosted | Vercel |

Where the others do more: Pastel and Markup.io add screenshots, statuses and team workflows. Hypothesis is built for text annotation, groups and public discussion. Vercel ties comments to deploys and syncs them to issue trackers. If you need logins, roles or integrations, use one of them.

