# Pages with state: the adapter

[Back to the README](../README.md)

A plain document needs nothing: every element is always there, and the list scrolls to it. A page that shows different content in the same place does need an adapter: tabs, a slide deck, a walkthrough that plays one screen after another, a prototype. Without an adapter the list cannot bring back a part that is on another slide, and a pin could land on the wrong slide's version of an element.

Define `window.ArtifactComments` before the script runs. Every key is optional:

```js
window.ArtifactComments = {
  // What the page is showing now. Saved with each new comment, as JSON, 600 characters at most.
  state: () => ({ slide: current }),

  // Bring a saved state back. May return a Promise.
  restore: (s) => showSlide(s.slide),

  // Is the page showing this comment's state right now? Return true, false,
  // or undefined when it cannot tell. With it, a pin shows only on its own
  // slide, and it still shows when the slide's text changed (another language).
  isCurrent: (s) => s.slide === current,

  // Last resort for comments without a usable state: show each state in turn
  // and call test() after each one. Stop and return true when test() is true.
  search: (test) => {
    for (const n of allSlides) { showSlide(n); if (test()) return true; }
    return false;
  },

  // Readable "where" for the list, e.g. "Pricing > slide 4". Gets the clicked element.
  // Return '' to fall back to the nearest heading above the element.
  label: (el) => `Slide ${current + 1}: ${titleOf(current)}`,

  // Stop autoplay or animation. Called on entering comment mode and on opening a thread.
  pause: () => player.pause(),
};
```

How the list finds a part, in order: it is already on screen; `restore(state)`; `search(test)`, first requiring the saved text to match and then without; the saved `#hash` for pages that keep state in the URL. If all of these fail, the thread still opens, with a note that the part is no longer on the page.

[`examples/demo.html`](../examples/demo.html) is a complete working example with tabs, a scroll box and an iframe.

