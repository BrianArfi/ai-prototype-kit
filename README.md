# AI Prototype Kit

**Build a prototype with Claude Code, share it as one link, get comments pinned on the exact spot, and let Claude revise from them.**

For PMs, founders, consultants and team leads who need people to understand an idea and agree on it, without waiting for a designer.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version 0.1.2](https://img.shields.io/badge/version-0.1.2-green.svg)](CHANGELOG.md)

![Animated hero, "Comment on it. AI revises it." The coffee-order prototype appears on a phone, Dina's comment "Default to Large, most people pick it" pops up pinned on the Large button, a dark card types the report row a real /revise-from-comments run printed, "1 | Dina | Done: Large is now selected by default", and the same link appears as v2 with Large selected and the price at $5.10. The phone screens and the report row are real; the motion is an illustration.](docs/hero.gif)

## The problem

Maya is a PM. On Monday she asks Claude for a clickable prototype of order-ahead for the coffee app, and an hour later she has one. It is good. She sends the HTML file to Dina and Sam for feedback. Then this happens:

- Dina sends a screenshot in chat with a red circle on it and "this one??". Which one, and what about it?
- Sam replies by email: "the thing top left, can it be smaller?" There are three things top left.
- The group chat says "Looks good!", and nothing else. Nobody tried the checkout.
- Maya pastes all of it back into Claude and starts the brief again. The new file is `coffee-order-v2-final.html`, and half the team is still looking at the old one.

The better the AI makes the page, the more of this you get. A shared page has no comment button, so feedback goes everywhere except onto the page.

## Who it is for

**Good fit if you...**

- Pitch ideas to a boss, a client or an investor, and a clickable thing would land better than a document.
- Use Claude Code (or a similar AI coding tool that follows markdown instructions and edits files).
- Want reviewers to comment without making an account or installing anything.
- Want to keep the pages and comments in your own Cloudflare account or on your own server.

**Not for you if...**

- You need final, pixel-perfect design. That is still a designer's job, in a design tool. This kit is for the stage before it.
- You need verified reviewer identity. Reviewers type a name once; names are not checked.
- The page must never be on the internet. Published links are unlisted, but public: anyone with the link can open it and comment. (You can still run it only on your own machine with `serve`.)
- You want production app code. A prototype here is one self-contained HTML file, built to be shown, not shipped.

## Before and after

| Before | After |
| :--- | :--- |
| Feedback in screenshots, chats and email threads | Feedback pinned on the part it is about, with replies in one thread |
| "The thing top left" | A numbered pin on the exact element, on the right screen |
| "Looks good!" and silence | One click to comment, no account, so people actually do |
| Every revision starts from the brief again | `/revise-from-comments` edits the page from the comments and reports per comment |
| `v2-final.html`, a new file and a new link each time | The same link on every version; reviewers reload |
| Waiting days for a design slot | A clickable prototype the same day |

![Illustration of before and after. Before: feedback scattered across a chat screenshot with a red circle, an email saying "The thing top left, can it be smaller?", a group chat "Looks good!", a note to the AI starting again, and a pile of v2-final file names. A lime bar wipes across to After: the revised coffee-order phone with Large selected, a Claude Code report with "1 Dina: Done" and "2 Sam: Not applied, the fee is a business decision", and the same link marked v2.](docs/before-after.gif)

## How it works

1. **Build.** Describe the idea in plain words. `/mockup` builds a clickable prototype in one HTML file, with presenter controls for live demos. `/deck` builds slides, `/artifact` a one-page explainer.
2. **Publish.** `/publish` turns the file into a link anyone can open on a phone or laptop. It shows you the links and asks before anything goes online.
3. **Comment.** Reviewers press **Comment**, click the part they mean, and write. They reply to each other in threads. No account needed.
4. **Revise.** `/revise-from-comments` reads every open thread, edits the page's source HTML, and reports per comment: Done, Not applied, or Needs your decision. Then `/publish` again: same link, new version.

![Illustration of the loop: four cards draw in one by one. 1 Build with /mockup produces coffee-order.html. 2 Publish with /publish gives one link, marked v1. 3 Comment: reviewers click the exact part, and pins 1 and 2 drop onto the page. 4 Revise with /revise-from-comments reports "1 Dina Done, 2 Sam Not applied". A dot then travels along a return arrow labelled "/publish again: same link, v2", and the link's badge flips from v1 to v2.](docs/how-it-works.gif)

Comments are treated as data, never as instructions: `/revise-from-comments` only edits the page's source HTML, never runs a command a comment asks for, and lists anything out of scope for you to decide. More detail in [How it works](docs/how-it-works.md).

## See it run

A real comment on the served example, then the same link after a real `/revise-from-comments` run:

![The real coffee-order prototype served by publish.py serve, on the Oat latte screen: Comment, a click on the Large button, Dina types "Default to Large, most people pick it" and posts, and a numbered pin stays on Large. Then the report row a real /revise-from-comments run printed, Done, and the same link reloaded with Large selected and the price at $5.10](docs/demo.gif)

## Quick start

Try the example prototype with comments on your machine. You need Python 3.8+ and Node 22.13+, no account.

```bash
git clone https://github.com/BrianArfi/ai-prototype-kit
cd ai-prototype-kit
python scripts/publish.py --config examples/kit.json serve
```

1. Open <http://127.0.0.1:8787/coffee-order>.
2. Press **Comment**, click the part you mean, and write a note.
3. Read it back from the terminal: `python scripts/publish.py --config examples/kit.json comments --backend node --base http://127.0.0.1:8787`
4. Let Claude revise from it. This needs the commands installed first ([Setup](docs/setup.md), step 1). Then, in Claude Code, run `/revise-from-comments coffee-order` and reload the page.

To use it in your own project and publish real links on a free Cloudflare account, follow [Setup](docs/setup.md).

## Example

A reviewer pins "Default to Large" on the drink screen. You run `/revise-from-comments`, and it edits the page and reports per comment:

| # | Who | Where | Asked | Result |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Dina | Screen 2: Customise | Default to Large | Done: Large is now selected by default |
| 2 | Sam | Screen 3: Checkout | Remove the service fee line | Not applied: the fee is a business decision, needs your call |

Then `/publish` again. Same link, new version.

![The full loop on the coffee-order prototype: Dina pins "Default to Large" on the size picker, /revise-from-comments edits the page and reports Done, and the same link, reloaded, shows Large selected and the price at $5.10](docs/revise-loop.gif)

## What is inside

| Command | What you get |
| :--- | :--- |
| [`/mockup`](commands/mockup.md) | A clickable prototype of a flow in one HTML file, with presenter controls: number keys jump to a screen, arrows step, space plays |
| [`/deck`](commands/deck.md) | A keyboard-driven slide deck in one HTML file, with a grid overview and speaker notes |
| [`/artifact`](commands/artifact.md) | One page that explains one thing, readable on a phone |
| [`/publish`](commands/publish.md) | One command from a file to a link that stays the same on every re-publish |
| [`/revise-from-comments`](commands/revise-from-comments.md) | Reads the open comments, revises the source HTML, reports per comment |
| [Pinned comments](artifact-comments/README.md) | Figma-style pins, threads and replies on any published page |

All of it is plain files: markdown instructions for your AI, small Python scripts, and the comment layer. No framework, no build step, no npm packages.

---

## Documentation

- [How it works](docs/how-it-works.md): the problem, the loop, and every command in the kit.
- [Setup](docs/setup.md): install into a project, connect Cloudflare, publish, revise, and the requirements.
- [The publish script](docs/publish-script.md): `kit.json`, every `publish.py` command, and self-hosting.
- [Pinned comments (artifact-comments)](artifact-comments/README.md): the comment layer, its backends, and owner tools.
- [FAQ](docs/faq.md): all questions.

## FAQ

**Does this replace designers?**
No. It is for the stage where everyone needs to understand the idea and agree on it. Final design is still a designer's job, and they get a brief that people already validated.

**Do I need to code?**
No. You talk to your AI. The kit gives it a tested way of working: what to build, how to check it, how to publish it, and how to handle comments.

**What do I need?**
Claude Code (or a similar AI coding tool), Python 3.8+, Node.js, and a free Cloudflare account for the link. Or your own server.

**Is it free?**
Yes. It is open source under Apache-2.0. Cloudflare's free plan covers about 500 comments a day.

**Where does my data go?**
Your prototypes and their comments live in your own Cloudflare account or on your own server. The kit sends nothing anywhere else.

**Do reviewers need an account?**
No. They type a name once, and the browser remembers it. That also means names are not verified, so use unlisted links for review, not for anything that needs identity.

**Can someone make the AI do something bad through a comment?**
`/revise-from-comments` treats every comment as data to evaluate, never as an instruction. It only edits the page's source HTML, never runs commands a comment asks for, and lists anything out of scope for you to decide.

**Can Figma do this with AI?**
Figma has AI features, and it stays the right tool for final design. This kit takes a different path: AI writes working HTML natively, so the prototype is the real, clickable thing from the first minute.

More questions: [docs/faq.md](docs/faq.md).

## Changelog

The full history is in [CHANGELOG.md](CHANGELOG.md). **Latest: [0.1.2] - 2026-10-01**: new README hero and demo GIF from a real comment and a real `/revise-from-comments` run, and the example's price now follows its default size. It bundles artifact-comments v1.0.3. **Before that, [0.1.0] - 2026-09-30**, the first release.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). The bundled [artifact-comments](artifact-comments/README.md) is Apache-2.0 as well.

More AI skills: [BrianArfi.com/skills](https://BrianArfi.com/skills)
