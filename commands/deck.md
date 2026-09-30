---
description: Prototype - Slide deck as one self-contained HTML file, keyboard driven, shared as a link and commented on
argument-hint: "<topic and audience>"
---

Build a slide deck as a single HTML file, presentable from a browser and shareable for comments.

The kit lives at `.claude/skills/ai-prototype-kit/`. Below, `KIT` means that folder.

## 1. The argument comes before the slides

Write the spine first, one line per slide, and show that list before building anything. A deck is
an argument in a fixed order, so the order IS the work. Building twenty slides and then looking
for the argument wastes the expensive part.

Ask who is in the room. A deck for a decision-maker is status and the decision: what, when, who.
A deck for a team can carry the reasoning.

## 2. One idea per slide

- The title states the takeaway, not the topic. "Integration is not the blocker" beats "Integration status".
- If a slide needs a paragraph, it is two slides, or it is a talk track.
- Numbers get a chart, not a table, unless exact values matter.
- A system gets a diagram, with the prose as its caption.

## 3. Build it

- **One file, self-contained.** No external CSS, font, script or image.
- **16:9**, scaling to the viewport, readable from the back of a room. Body text no smaller than
  20px at 1280 wide.
- **Keyboard driven**: arrows or space to advance, `Esc` for a grid overview, `F` for fullscreen.
  Print the key map on the title slide.
- **Slide numbers and a thin progress bar.** A presenter needs to know where they are.
- **Speaker notes** behind a key or in a `<details>` block, never on the slide.
- Light and dark via `:root` custom properties plus `[data-theme]`. Honour `prefers-reduced-motion`.
- **A comment adapter.** Required, see the next section.

## 4. The comment adapter (required)

The published link has pinned comments (artifact-comments, docs in `KIT/artifact-comments/README.md`).
Every slide sits in the same place on screen, so the comment layer needs to know which slide is
showing. Without the adapter, a comment on slide 7 cannot be found from the list.

Define `window.ArtifactComments` in the deck's own script:

```js
window.ArtifactComments = {
  state: () => ({ slide: current }),                 // saved with each new comment
  restore: (s) => go(s.slide),                       // bring that slide back
  isCurrent: (s) => s.slide === current,             // pin shows only on its own slide
  search: (test) => {                                // fallback for comments without a state
    const from = current;
    for (let n = 0; n < slides.length; n++) { go(n); if (test()) return true; }
    go(from); return false;
  },
  label: () => 'Slide ' + (current + 1) + ': ' + slides[current].querySelector('h1,h2').textContent,
  pause: () => stopAutoAdvance(),                    // if the deck auto-advances
};
```

Keep the current slide in one variable and move through one `go(n)` function. The comment layer
already stops arrow and space keys typed into a comment from reaching the deck. The grid overview
must not count as a slide state: `state()` returns the slide that was open before it.

## 5. Verify

```
grep -nE 'https?://|@import|fetch\(|XMLHttpRequest|<img|src=' <file>.html
```

## 6. Publish and share

Hand over the **absolute** path first. When the user wants a link, follow `/publish`:

```
python KIT/scripts/publish.py add "<Deck name>" <file>.html
python KIT/scripts/publish.py deploy
```

The link stays the same on every re-publish. Publishing puts the deck on the internet, so ask
before running `deploy`. When comments come in, use `/revise-from-comments`.

Deck: $ARGUMENTS
