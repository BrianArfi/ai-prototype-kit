---
description: Prototype - Clickable HTML prototype of a flow, built to be shown live, shared as a link and commented on
argument-hint: "<the flow to prototype>"
---

Build a working clickable prototype of a flow, in one HTML file, for showing on a call and sharing for comments.

This is screens a person can drive. For an explainer page use `/artifact`. For slides use `/deck`.

The kit lives at `.claude/skills/ai-prototype-kit/`. Below, `KIT` means that folder.

## 1. Get the flow right before the pixels

Write the step list out in plain sentences first and check it against the source: who acts, what
they see, what changes, and what happens when it fails. Show the list to the user, then build.

A convincing prototype of the wrong flow costs more than no prototype, because people approve what
they see. If a step is genuinely undecided, build the recommended path and mark the alternative
visibly on the screen. Do not quietly pick one.

## 2. Build it

- **One file, fully self-contained.** No external CSS, font, script or image. Inline SVG for icons.
- **A device frame** when it is a phone journey, so the reader can tell app from web.
- **Every screen reachable, no dead buttons.** A control that does nothing must look disabled.
- **Presenter controls**, because this gets driven live: number keys jump to a screen, arrow keys
  step, space plays, one key hides the presenter bar for a clean recording. Print the key map on screen.
  Keep the bar clear of the bottom-right corner, where the comment buttons sit.
- **A self-playing option**, so the presenter can talk over it instead of clicking.
- **Realistic content.** Plausible names, prices, the right currency and language. Lorem ipsum
  reads as unfinished and turns the review into a discussion about the copy.
- Light and dark via `:root` custom properties plus a `[data-theme]` override. Honour
  `prefers-reduced-motion`.
- **A comment adapter.** Required, see the next section.

## 3. The comment adapter (required)

The published link has pinned comments (artifact-comments, docs in `KIT/artifact-comments/README.md`). A
prototype shows different screens in the same place, so the comment layer needs to know which
screen is showing. Without the adapter, a comment made on screen 3 cannot be found from the list,
and its pin can land on the wrong screen.

Define `window.ArtifactComments` in the page's own script. Every key is optional, but a prototype
needs at least `state`, `restore` and `isCurrent`:

```js
window.ArtifactComments = {
  state: () => ({ screen: current }),              // saved with each new comment
  restore: (s) => { pause(); show(s.screen); },    // bring that screen back
  isCurrent: (s) => s.screen === current,          // pin shows only on its own screen
  search: (test) => {                              // fallback for comments without a state
    const from = current;
    for (let n = 1; n <= total; n++) { show(n); if (test()) return true; }
    show(from); return false;
  },
  label: (el) => 'Screen ' + current + ': ' + titleOf(current),  // "where" in the list
  pause: () => pause(),                            // stop autoplay while someone comments
};
```

Rules that keep it working:

- Keep the current screen in one variable, and change screens through one `show(n)` function.
- Hide inactive screens with `hidden` or `display: none`, so their pins hide too.
- Stable `id`s on the parts people will comment on (a card, a button, a form group).
- `KIT/examples/coffee-order.html` is a complete working example. Copy its pattern.

## 4. Verify

```
grep -nE 'https?://|@import|fetch\(|XMLHttpRequest|<img|src=' <file>.html
```

Only internal SVG references may match. Then walk every screen yourself and confirm each control
does what it claims. Press every presenter key once.

## 5. Publish and share

Hand over the **absolute** path first. When the user wants a link, follow `/publish`:

```
python KIT/scripts/publish.py add "<Prototype name>" <file>.html
python KIT/scripts/publish.py deploy
```

The link is `https://<project>.pages.dev/<slug>` and stays the same on every re-publish. Publishing
puts the page on the internet, so ask before running `deploy`. When comments come in, use
`/revise-from-comments`.

Flow: $ARGUMENTS
