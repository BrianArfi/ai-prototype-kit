# Styles for `/mockup`

Seventeen looks a prototype can wear. The user picks one from the style gallery
(`KIT/assets/style-gallery.html`), and the page you build uses that style's recipe from this file.
The same keys are used by the `explainer-video` and `animated-readme` skills, so one pick can carry
across a prototype, a video and a README.

## How to use a recipe

1. Copy the style's token block into the page's `:root` (or `[data-style]`), unchanged.
2. Build every component from the tokens: `--bg`, `--surface`, `--ink`, `--muted`, `--a`, `--b`,
   `--c`, `--radius`, `--stroke`, `--shadow`, `--head`, `--body`, `--ease`. Never hard-code a colour
   that is not in the block.
3. Apply the style's **moves**. They are what makes it read as that style and not as "a page with
   different colours". A mockup that only swaps the palette has not used the style.
4. Respect the kit rules from `commands/mockup.md`: one self-contained file, system fonts only (the
   stacks below), no external CSS, font or image. Honour `prefers-reduced-motion`.
5. One style per prototype. The presenter bar and the comment buttons stay neutral, outside the style.

**Light and dark.** A style is its own theme. Light-native styles may keep the kit's `[data-theme]`
toggle: dark is the same tokens with `--bg` and `--surface` swapped for the style's darkest tones and
`--ink` for its lightest. Dark-native styles (`terminal`, `blueprint`, `liquid`, `holo`, `glass`,
`pixel`, `artdeco`) ship without a light mode unless the user asks for one.

## Font stacks (system fonts only)

```css
--sans:  ui-sans-serif, system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
--mono:  ui-monospace, "SF Mono", Consolas, "DejaVu Sans Mono", monospace;
--serif: Georgia, "DejaVu Serif", "Times New Roman", serif;
--round: ui-rounded, "SF Pro Rounded", "Segoe UI", system-ui, sans-serif;
```

## Choosing, when the user does not know

| The prototype is | Offer first |
| :--- | :--- |
| A serious business or finance flow | `typographic`, `artdeco`, `glass` |
| A developer or AI tool | `terminal`, `holo`, `blueprint`, `ascii` |
| A friendly consumer app, onboarding | `clay`, `cutpaper`, `brutalist` |
| A launch, a promo, "X vs Y" | `brutalist`, `riso`, `liquid` |
| Something technical to explain | `isometric`, `blueprint`, `math` |
| A game, a nostalgic or indie product | `pixel`, `riso` |
| No strong preference | `typographic` (neutral, very readable) |

Say why in one line, then let them decide. Never pick silently unless they said "you choose".

---

## math
Cream paper, ink outlines, one red accent. The safe default.
```css
:root{--bg:#F4EFE6;--surface:#fff;--ink:#17140F;--muted:#6b645a;--a:#D8492B;--b:#2B6CB0;--c:#2B6CB0;
--radius:8px;--stroke:2px solid var(--ink);--shadow:none;--head:var(--sans);--body:var(--mono);--ease:cubic-bezier(.16,1,.3,1)}
```
- Cards: `border:var(--stroke)`, fill is the accent at 14% (`color-mix(in srgb,var(--a) 14%,transparent)`).
- Headings bold sans with a short accent underline (`::after`, 3px, 60% wide).
- Labels and numbers in `--mono`. Buttons solid `--a`, 8px radius, no shadow.
- Motion: ease-out-expo entrances, a small overshoot pop on the primary action.

## typographic
Swiss mono: type is the picture. Hairlines, one accent.
```css
:root{--bg:#FAFAF7;--surface:#FAFAF7;--ink:#111;--muted:#777;--a:#FF3B1F;--b:#111;--c:#111;
--radius:0;--stroke:1px solid rgba(17,17,17,.25);--shadow:none;--head:var(--sans);--body:var(--mono);--ease:cubic-bezier(.65,0,.35,1)}
```
- Cards are a hairline box with a heavy top rule: `border:var(--stroke);border-top:6px solid var(--ink)`, plus a small `--a` square chip in the corner. No fills, no icons, no charts unless asked.
- Headings very large, weight 800-900, letter-spacing `-.04em`, line-height `.95`.
- Buttons solid `--ink`, white text, square. Links are underlined, never coloured.
- Motion: in-out ease, no overshoot, opacity and 8px translate only.

## cutpaper
Layered torn paper, warm and human.
```css
:root{--bg:#EFE3CF;--surface:#F7EEDD;--ink:#2B2A33;--muted:#6e6a62;--a:#F2542D;--b:#0E9594;--c:#F5BB00;
--radius:2px;--stroke:0;--shadow:drop-shadow(.4rem .5rem 0 rgba(0,0,0,.08)) drop-shadow(.8rem 1rem 0 rgba(0,0,0,.07));--head:var(--sans);--body:var(--serif);--ease:cubic-bezier(.34,1.56,.64,1)}
```
- Cards use a jagged `clip-path: polygon(...)` with 12-14 points and `filter:var(--shadow)` (a clipped element cannot use `box-shadow`).
- Colour blocks `--a`, `--b`, `--c` as paper layers; tilt some by 1-2 degrees. Body text in `--serif`.
- Buttons are a torn strip in `--a`. Dividers are dashed 3px lines.
- Motion: slide in with a rotation settle (`rotate(-8deg)` to 0) and overshoot easing.

## sketchbook
Pencil on paper, hatching, hand-wobble.
```css
:root{--bg:#F7F4EC;--surface:#FBF9F2;--ink:#2A2620;--muted:#7a746a;--a:#2F6FB0;--b:#C0562B;--c:#2F6FB0;
--radius:6px;--stroke:2px solid var(--ink);--shadow:none;--head:var(--serif);--body:var(--mono);--ease:steps(12,end)}
```
- Inline SVG filter once: `feTurbulence baseFrequency=.03` into `feDisplacementMap scale=3`, applied to boxes and buttons (`filter:url(#wob)`; give the filter region extra margin so edges are not clipped). Skip it on body text.
- Fill shapes with hatching: `repeating-linear-gradient(135deg, color-mix(in srgb,var(--a) 55%,transparent) 0 2px, transparent 2px 10px)`.
- A second, lighter outline offset by 3px and rotated .6deg on cards (pencil double line). Italic serif headings.
- Motion: stepped (`steps(12)`) so it feels drawn "on twos".

## riso
Two-ink print: overprint, misregistration, halftone.
```css
:root{--bg:#F3EEE3;--surface:#F3EEE3;--ink:#1B1B2F;--muted:#5b5a6b;--a:#FF5A36;--b:#2B44FF;--c:#00A878;
--radius:0;--stroke:3px solid var(--b);--shadow:4px 3px 0 var(--b);--head:var(--sans);--body:var(--mono);--ease:steps(1,end)}
```
- Flat fills with `mix-blend-mode:multiply`; a second outline in `--b` offset by (5px, 3px) via `::after`.
- Halftone on the lower half of cards: `radial-gradient(circle,rgba(43,68,255,.55) 0 2px,transparent 2.5px) 0 0/9px 9px`.
- Text is ALL CAPS with `text-shadow:3px 2px 0` in `--b` at 70%. Buttons `--a` with the offset shadow.
- Motion: no easing at all. Screens and cards land instantly (`steps(1)`), on a beat.

## terminal
Phosphor on near-black, windows with title bars.
```css
:root{--bg:#0D1117;--surface:#0D1117;--ink:#3FB950;--muted:#2f7a3d;--a:#D29922;--b:#58A6FF;--c:#3FB950;
--radius:0;--stroke:1px solid var(--ink);--shadow:none;--head:var(--mono);--body:var(--mono);--ease:steps(1,end)}
```
- Everything `--mono`. Cards are windows: 1px `--ink` border, 24px title bar filled `--a` or `--b` with dark text (`o o o  ./name`).
- Prompt prefixes (`$ `, `> `) on buttons and headings, a blinking block caret (`animation:caret 1s steps(1) infinite`, period 1s).
- Scanlines + vignette as a fixed `::after` overlay: `repeating-linear-gradient(0deg,rgba(0,0,0,.18) 0 1px,transparent 1px 4px)`, `pointer-events:none`.
- Motion: instant. Typed text appears with `steps()`; no fades.

## isometric
Blocks on a 30 degree grid. Good for systems and flows.
```css
:root{--bg:#EAF0F6;--surface:#fff;--ink:#1E2A3A;--muted:#64748b;--a:#FF7A59;--b:#4C7BE0;--c:#3FB68B;
--radius:6px;--stroke:2px solid var(--ink);--shadow:5px 7px 0 color-mix(in srgb,var(--a) 60%,#000);--head:var(--sans);--body:var(--mono);--ease:cubic-bezier(.16,1,.3,1)}
```
- Background grid: two `repeating-linear-gradient` at `30deg` and `-30deg`, lines at 7% opacity so text stays readable.
- Feature tiles are 3-face blocks: three child layers with `clip-path` (top 100% lighter via `color-mix(... #fff 22%)`, left 78%, right 56% darker). Use them for hero tiles and key metrics, not for every card.
- Buttons get a hard offset shadow like a block's side face.
- Motion: blocks rise (`translateY(5%)` to 0) with expo easing.

## blueprint
White linework on navy, dimension lines, mono caps.
```css
:root{--bg:#0B3A66;--surface:#0B3A66;--ink:#E8F1FA;--muted:#9fc0de;--a:#FFD166;--b:#7FB7E6;--c:#E8F1FA;
--radius:0;--stroke:2px solid var(--ink);--shadow:none;--head:var(--mono);--body:var(--mono);--ease:linear}
```
- Background: 20px minor grid at 7% and 100px major grid at 16% (`linear-gradient` pairs) and a 2px frame inset 12px.
- Cards: 2px outline, an inner 1px frame inset 8px at 50% opacity, and four 7px `--a` squares on the corners (one background layer each).
- Text ALL CAPS, letter-spacing `.04em`. Dimension line under key widths: `|<-- 240 MM -->|` in 11px.
- Buttons are outlined `--a`, square. Motion: linear, outlines trace themselves with a `clip-path` reveal. No bounce.

## brutalist (neo brutalism)
Thick black borders, hard offset shadows, flat loud colour.
```css
:root{--bg:#FFF4D6;--surface:#fff;--ink:#000;--muted:#4a4a4a;--a:#FF5C8A;--b:#3DDC97;--c:#4D7CFE;
--radius:0;--stroke:3px solid #000;--shadow:6px 6px 0 #000;--head:var(--sans);--body:var(--sans);--ease:cubic-bezier(.34,1.7,.64,1)}
```
- Every box: `border:var(--stroke); box-shadow:var(--shadow)`. Fills are flat `--a`, `--b`, `--c`, white for reading surfaces.
- Dot-grid background: `radial-gradient(rgba(0,0,0,.2) 0 1px,transparent 1.5px) 0 0/18px 18px`.
- Headings and buttons ALL CAPS, weight 900, `letter-spacing:-.02em`. Tags tilted -4 degrees on yellow `#FFE14D`.
- Pressed state: translate by the shadow offset and drop the shadow. Motion: bouncy pop-ins.

## whiteboard
Marker on a whiteboard: rounded, drawn, friendly.
```css
:root{--bg:#FBFBF9;--surface:#FBFBF9;--ink:#22303C;--muted:#6b7886;--a:#E4572E;--b:#2E86AB;--c:#3BA55D;
--radius:14px;--stroke:4px solid var(--b);--shadow:none;--head:var(--sans);--body:var(--sans);--ease:cubic-bezier(.65,0,.35,1)}
```
- Same wobble filter as `sketchbook` (region padded), on borders and arrows only.
- Boxes have 4px marker outlines in `--a`, `--b`, `--c`; arrows are 4px round-capped lines. Faint ruled lines in the background (`repeating-linear-gradient`, 10% blue).
- Emphasis is a hand-drawn wavy underline or a circle, not bold. Buttons are outlined pills.
- Motion: in-out ease; things are drawn around their perimeter (`clip-path` reveal).

## liquid
Gooey blobs, gradient light, springy morphing. Dark.
```css
:root{--bg:#0B0B1E;--surface:rgba(255,255,255,.06);--ink:#F4F1FF;--muted:#a9a4c9;--a:#FF4FD8;--b:#4F7CFF;--c:#22E3C4;
--radius:28px;--stroke:1px solid rgba(255,255,255,.14);--shadow:0 0 40px rgba(255,79,216,.35);--head:var(--sans);--body:var(--sans);--ease:cubic-bezier(.34,1.56,.64,1)}
```
- Hero and key areas sit on a blob layer: three gradient divs with `border-radius` keyframes between 4 values (period 7s) and one inline SVG `feGaussianBlur` + `feColorMatrix` ("goo", alpha `26 -11`) filter on the *background layer only*. Never put text inside a goo-filtered element.
- Large radius everywhere (28px+, pills for buttons). Headline in a gradient (`background-clip:text`).
- Buttons: gradient `--a` to `--b`, glow shadow, morphing radius on hover.
- Motion: spring easing with overshoot, slow sine drift on the ambient blobs.

## holo
Holographic neon: iridescent edges, glow, glitch. Dark.
```css
:root{--bg:#05030F;--surface:rgba(5,3,15,.82);--ink:#EAF8FF;--muted:#8fb3c4;--a:#00F0FF;--b:#FF2BD6;--c:#B6FF3B;
--radius:6px;--stroke:2px solid transparent;--shadow:0 0 22px rgba(0,240,255,.45),0 0 50px rgba(255,43,214,.25);--head:var(--mono);--body:var(--mono);--ease:cubic-bezier(.2,.9,.2,1)}
```
- Iridescent border: `background:linear-gradient(var(--surface),var(--surface)) padding-box, linear-gradient(120deg,var(--a),var(--b),var(--c)) border-box; border:var(--stroke)`.
- Perspective grid floor at the bottom: two `repeating-linear-gradient`s on a `transform:perspective(45vw) rotateX(64deg)` plane, masked to fade out upwards.
- Headings ALL CAPS with `text-shadow:0 0 12px var(--a),0 0 30px var(--b)`. A faint scan band sweeping down (6s period).
- Motion: fast ease-out, plus a 2-frame glitch (`skewX` jitter) on entrance of screens.

## glass
Frosted glass over drifting colour. Dark-ish, calm, premium.
```css
:root{--bg:#5B4BDB;--surface:rgba(255,255,255,.2);--ink:#fff;--muted:rgba(255,255,255,.72);--a:#FFD166;--b:#7DF9FF;--c:#FF8AC4;
--radius:24px;--stroke:1px solid rgba(255,255,255,.55);--shadow:0 20px 40px rgba(20,10,80,.28);--head:var(--sans);--body:var(--sans);--ease:cubic-bezier(.16,1,.3,1)}
```
- Background: 3 large blurred radial orbs (`#00B4D8`, `#FF8AC4`, `#FFD166`) on `--bg`, drifting slowly (`translate`, 10s).
- Panels: `background:linear-gradient(135deg,rgba(255,255,255,.34),rgba(255,255,255,.1)); backdrop-filter:blur(24px) saturate(1.5); border:var(--stroke); border-radius:var(--radius); box-shadow:var(--shadow)`, plus a soft white highlight strip along the top edge.
- Text white; keep a 4.5:1 contrast check on the frosted panels (darken the panel fill if the orb behind is light).
- Motion: float up 24px with a slight scale, expo ease.

## clay
Puffy pastel claymation. Light, friendly.
```css
:root{--bg:#F2E8DF;--surface:#F7EFE8;--ink:#4A3B47;--muted:#85747f;--a:#FF8FA3;--b:#7BC8F6;--c:#FFD27D;
--radius:28px;--stroke:0;--shadow:inset 6px 6px 12px rgba(255,255,255,.75),inset -7px -9px 14px rgba(74,59,71,.2),0 18px 22px -8px rgba(74,59,71,.32);--head:var(--round);--body:var(--round);--ease:ease-out}
```
- Every control and card: radial gradient fill (`radial-gradient(circle at 30% 24%, color-mix(in srgb,var(--f) 45%,#fff), var(--f) 62%)`), huge radius, and the layered `--shadow` (two inner, one drop) so it looks inflated.
- Headings weight 800 with a 3px white text-shadow below. Buttons are pill-shaped and puffier than cards.
- Motion: squash-and-stretch pop (`scale(1.16,.8)` then `(.92,1.09)` then settle), 0.6s.

## ascii
Line-printer paper; the interface is made of characters.
```css
:root{--bg:#F4F1E8;--surface:#F4F1E8;--ink:#1A1A1A;--muted:#6a665c;--a:#D6336C;--b:#1C7ED6;--c:#2F9E44;
--radius:0;--stroke:0;--shadow:none;--head:var(--mono);--body:var(--mono);--ease:steps(24,end)}
```
- Everything `--mono`, `white-space:pre` where alignment matters, `line-height:1.18`.
- Boxes are real text: `+---+` and `|` borders in a `<pre>`, fills from the density ramp (`:` `+` `#`) in `--a`, `--b`, `--c`. Buttons are `[ Label ]`, tags `<new/>`, headings prefixed `## `.
- Use `ch` units for spacing so the grid holds. Keep one `<pre>` per component; never mix a CSS border into a character box.
- Motion: typewriter reveal with `steps(n)` on `clip-path: inset(0 100% 0 0)`; fills resolve sparse to dense.

## pixel
Chunky 16-colour pixel art. Dark.
```css
:root{--bg:#1A1C2C;--surface:#29366f;--ink:#F4F4F4;--muted:#94a3c8;--a:#EF7D57;--b:#41A6F6;--c:#A7F070;
--radius:0;--stroke:0;--shadow:0 6px 0 #0d0e17;--head:var(--mono);--body:var(--mono);--ease:steps(6,end)}
```
- No `border-radius`, no gradients, no blur. Borders are pixel steps: stack `box-shadow` offsets of 4px on each side in the border colour, with a 4px light inner top-left and dark inner bottom-right bevel.
- Bold mono; render headings through a tiny canvas (about 10px type, alpha-thresholded, scaled with `image-rendering:pixelated`) when the heading is a hero. Body text stays real text.
- Checker dither at 3-4% for backgrounds: `conic-gradient(...)` at 8px.
- Motion: stepped, about 8 fps (`steps(6)` on 0.6s transitions). Icons drawn as inline SVG with `shape-rendering:crispEdges`.

## artdeco
Gold on deep navy, symmetric, geometric. Dark.
```css
:root{--bg:#0D1B24;--surface:#0D1B24;--ink:#F3E7C9;--muted:#b8ad8f;--a:#C9A24B;--b:#1F8A70;--c:#B5483A;
--radius:0;--stroke:1px solid var(--a);--shadow:none;--head:var(--serif);--body:var(--sans);--ease:cubic-bezier(.65,0,.35,1)}
```
- Headings serif ALL CAPS, `letter-spacing:.14em`, centred, framed above and below by a thin gold rule plus a second hairline.
- Cards have chamfered corners (`clip-path: polygon(7% 0,93% 0,100% 11%,100% 89%,93% 100%,7% 100%,0 89%,0 11%)`) built as two nested layers (gold outer, `--bg` inner inset 2px) plus an inner offset rule; buttons are gold-outlined hexagons.
- Sunburst behind the hero: `repeating-conic-gradient(from -90deg at 50% 118%, rgba(201,162,75,.16) 0 3deg, transparent 3deg 9deg)` with a radial mask.
- Motion: slow and symmetric: reveal from the centre outward (`scaleX(0)` to 1), lines draw to both ends.

---

## Adding a style

Add it to the `STYLES` array and a `.st-<key>` block in `assets/style-gallery.html`, add a section here
with a token block and its moves, and give it the same key in `explainer-video` and `animated-readme`.
Check the gallery in a browser before you ship it.
