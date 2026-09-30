---
description: Prototype - Self-contained HTML explainer, report or proposal, shared as a link and commented on
argument-hint: "<what to explain, or a path to the source note>"
---

Build one HTML file that explains one thing well, and hand over its path.

Use this for an explainer, a technical response, a report, or a written proposal.
For clickable screens use `/mockup`. For slides use `/deck`.

The kit lives at `.claude/skills/ai-prototype-kit/`. Below, `KIT` means that folder.

## 1. Find the source before writing a word

Read the note, the meeting minutes, or the thread this is about. Never write an explainer from
memory of the conversation. Name the sources at the foot of the page so the reader can check you.

If the subject is a system, describe how it moves, not where the parts sit. A box diagram that
only names components tells the reader nothing a list would not.

## 2. One file, and it must survive being sent

- No external stylesheet, font, script, or image. Everything inline. Inline SVG for icons.
- `:root` CSS custom properties for colour, with BOTH a `prefers-color-scheme: dark` block and a
  `[data-theme]` attribute override, so it works in a dark room and in a screen share.
- System font stack for prose, `ui-monospace` for labels and metadata.
- Content column around `980px`, centred. Lead paragraph capped near `66ch`.
- A sticky table of contents once the page has more than three sections.
- Readable on a phone: nothing wider than the screen, tables scroll inside their own box.
- Honour `prefers-reduced-motion`. Keyboard operable.

A plain scrolling page needs no comment adapter. If the page has tabs or collapsible sections,
add one, as described in `/mockup` section 3.

## 3. Verify it is actually self-contained

```
grep -nE 'https?://|@import|fetch\(|XMLHttpRequest|<img|src=' <file>.html
```

Only internal SVG references such as `url(#fxA)` are acceptable. Anything else means the page
breaks the moment it leaves this machine, which defeats the format.

## 4. Hand it over

Save it next to the material it came from, and give the user the **absolute** path. A relative
path resolves against the workspace root, not the file's folder, so it usually fails to open.

When the user wants a link, follow `/publish`:

```
python KIT/scripts/publish.py add "<Page name>" <file>.html
python KIT/scripts/publish.py deploy
```

Publishing puts the page on the internet, so ask before running `deploy`.

Subject: $ARGUMENTS
