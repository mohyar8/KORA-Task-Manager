# KORA — Web Frontend Design Language Reference

> **Purpose:** This file is a permanent implementation reference for any AI tool, frontend developer, or UI designer building a KORA website or web application.
>
> It is **not** a description of one existing website and **not** a page-by-page template. It defines the reusable visual language, composition rules, UI behavior, responsive logic, and implementation constraints that make a digital product feel unmistakably KORA while allowing each product to have its own information architecture and features.

---

## 0. How an AI tool must use this file

Treat this document as a **design-system directive**.

When creating a new KORA frontend:

1. Preserve the product requirements and information architecture of the new site.
2. Apply the visual grammar, typography, colors, geometry, patterns, spacing philosophy, motion behavior, and component styling defined here.
3. Do **not** clone the layout of an existing KORA page unless explicitly requested.
4. Do **not** turn KORA into a generic SaaS dashboard, generic football website, or generic corporate landing page.
5. Use the supplied official assets whenever they are available. Do not redraw the logo, invent a substitute pattern, or approximate an official brand asset with CSS if the actual asset exists.
6. Keep the interface usable first. Brand graphics support hierarchy; they must not damage readability, form completion, table scanning, or accessibility.
7. Interpret the system as a coherent visual language, not as a checklist requiring every color and pattern on every screen.

**Core rule:**  
**Reuse the design language, not the old page layout.**

---

# 1. Brand Character in Digital Interfaces

KORA should feel:

- editorial rather than corporate;
- energetic rather than playful;
- contemporary rather than futuristic;
- football-connected without relying on cliché football imagery;
- structured but visually expressive;
- Saudi in context without decorative cultural imitation;
- bold in composition while keeping functional UI calm and readable.

The visual tension is intentional:

**large editorial typography + disciplined whitespace + dark navy structure + selective bright accents + oversized/cropped geometric forms + thin organic line patterns.**

A KORA interface should not look like:

- a sports-score app;
- a gaming/esports interface;
- a neon cyberpunk product;
- a Bootstrap/admin template with brand colors added afterward;
- a page covered with football icons;
- a honeycomb UI;
- a glassmorphism showcase;
- a gradient-heavy AI-generated landing page.

---

# 2. Visual Hierarchy Philosophy

KORA uses **contrast of scale**, not visual clutter.

A page should normally contain:

- one dominant message or title;
- a clear supporting layer;
- strong section boundaries;
- a limited number of graphic gestures;
- quiet areas that let the branded moments breathe.

Prefer:

- very large headlines;
- short labels and indices;
- strong alignment;
- asymmetric compositions when appropriate;
- large empty spaces;
- controlled overlap;
- cropped brand geometry at boundaries;
- full-width editorial sections for storytelling;
- clean contained surfaces for functional workflows.

Avoid:

- equal visual weight everywhere;
- excessive cards;
- card-inside-card structures;
- decorative badges on everything;
- many small competing headings;
- random gradients;
- unnecessary shadows.

---

# 3. Color System

## 3.1 Core palette

Use these brand colors as the canonical digital palette:

| Token | Hex | Role |
|---|---|---|
| `kora-navy` | `#2D3B70` | Primary structural brand color |
| `kora-fuchsia` | `#944399` | Expressive secondary accent |
| `kora-coral` | `#F26557` | High-energy accent / emphasis |
| `kora-green` | `#4EA649` | Secondary accent / positive or thematic highlight |
| `kora-white` | `#FFFFFF` | Primary light field / reverse text |

> The source identity sometimes names the navy “Astronaut,” the purple “Dark Fuchsia,” and the coral “Chinese Rose.” Implementation should use the token names above for clarity.

## 3.2 Dominance

**Navy is the anchor.**  
The other three colors are accents, not equal competitors.

A typical KORA page should visually feel as though navy and neutral space own the composition, while fuchsia, coral, and green appear in intentional moments.

Do not distribute all four colors equally across every component.

## 3.3 Recommended semantic mapping

Brand and semantic meaning are separate concepts.

Use:

- navy for primary branded surfaces, navigation, strong text, major controls;
- fuchsia for editorial/thematic emphasis;
- coral for energetic highlights, active visual moments, or selected campaign emphasis;
- green for positive states when appropriate and for brand compositions;
- neutral system colors for warnings, errors, disabled states, borders, and dense data UI when forcing a brand color would create ambiguity.

Do not make `kora-coral` automatically mean “error” merely because it is reddish.  
Do not make `kora-green` the only success mechanism; success must also have text/icon semantics.

## 3.4 Light surfaces

The identity repeatedly works with white/light fields. Use white generously.

On light backgrounds:

- primary text: navy or a very dark neutral;
- secondary text: muted neutral;
- branded geometry: navy plus one or two accents;
- borders: low-contrast neutral/navy tint;
- avoid filling every container with a brand color.

## 3.5 Dark surfaces

Navy can become a full section background.

On navy:

- use white as the primary text;
- accents may use fuchsia/coral/green;
- patterns should be lower contrast than content;
- preserve large calm areas.

## 3.6 Gradients

The visual identity presentation uses atmospheric multi-color gradients in presentation backgrounds, but gradients are **not the default UI surface treatment**.

Use gradients only when a specific art-directed brand moment needs them, such as:

- a hero backdrop;
- campaign artwork;
- transition/ambient background.

Do not use gradients on ordinary buttons, inputs, cards, tables, modals, or navigation simply to make them “branded.”

---

# 4. Typography

## 4.1 Brand typeface

The identity defines **Ghroob / غروب** as the brand typeface and demonstrates:

- Light
- Regular
- Bold

Use the official font files when legally and technically available in the project assets.

Do not substitute a similar-looking condensed font when the official font exists.

## 4.2 Typography character

The typography is:

- narrow/condensed;
- tall;
- direct;
- editorial;
- effective at oversized display scale;
- suitable for Arabic and Latin brand expression.

Its power comes from **scale and spacing**, not from adding effects.

Do not add:

- text shadows;
- outlines;
- glow;
- faux italics;
- arbitrary letter distortion.

## 4.3 Hierarchy

### Display / Hero
Use Bold or Regular depending on visual density.

Characteristics:

- very large;
- compact line-height;
- short phrases;
- can break intentionally across lines;
- may become a compositional object.

### Section headings
Use Bold/Regular with strong contrast against body text.

### Eyebrows / indices
Examples: `01`, `02`, section labels, short metadata.

Use smaller sizes but maintain clear brand character. Numbering is a useful recurring editorial device.

### Body copy
Prioritize reading comfort. Do not make long paragraphs overly condensed or tiny.

### UI controls
Buttons, tabs, inputs, table labels, and menus must prioritize clarity over display drama.

## 4.4 Arabic

Arabic is a first-class layout, not a translated afterthought.

For Arabic pages:

- use `dir="rtl"` correctly;
- mirror layout logic where appropriate, not blindly;
- keep numerals/dates legible;
- ensure icon direction is semantically correct;
- test mixed Arabic/English strings;
- preserve intentional spacing around Latin terms;
- never fake RTL using text alignment alone.

## 4.5 English

Use the same typographic personality. English headings can be narrow and uppercase where suitable, but avoid turning all body/UI copy into uppercase.

## 4.6 Fallback policy

If Ghroob cannot be shipped:

1. clearly mark the fallback as temporary;
2. choose a legible Arabic/Latin sans-serif with relatively compact proportions;
3. do not claim the fallback is brand-authentic;
4. preserve the hierarchy, sizing philosophy, and spacing until the official font is available.

---

# 5. The Shape Language

KORA geometry is derived from a football visual system but must be interpreted abstractly.

The identity uses:

- irregular polygonal panels;
- fragments related to football-panel geometry;
- large fields that meet at angled boundaries;
- partial/cropped geometric masses;
- outlined geometric structures;
- clustered colored cells;
- thin network-like curves.

## 5.1 The key rule

**Never reduce the system to repeated hexagons.**

The visual language is not “put hexagons everywhere.”  
It is a system of **partial football-derived geometry, irregular polygon fields, and connective lines**.

## 5.2 Large polygon fields

Use these for:

- hero art;
- section transitions;
- image masks;
- editorial callouts;
- event storytelling;
- campaign sections.

They may be:

- partially off-canvas;
- cropped;
- oversized;
- asymmetric;
- intersecting a section edge.

Do not force them into small UI controls.

## 5.3 Polygon clusters

Small groups of colored polygon cells can appear as accent compositions.

Use sparingly:

- footer/corner art;
- campaign modules;
- editorial separators;
- merchandise-like graphic moments.

Do not create a repeating honeycomb background.

## 5.4 Image framing

Photography can be placed beside or inside angular/polygonal fields.

The brand effect comes from the relationship between:

**photo + white/navy space + one bold polygon field + small accent geometry.**

Do not clip every image into a football shape. Repetition weakens the system.

---

# 6. Patterns — Critical Interpretation

> **This section is mandatory reading for AI tools.**
>
> KORA patterns are frequently misinterpreted. They are not generic decoration and they are not a tiled football texture.

The identity contains multiple related graphic families. They must remain distinct.

## 6.1 Pattern Family A — Polygon / Panel Structure

This family uses enlarged football-derived panel geometry.

Characteristics:

- irregular polygon cells;
- thick or clearly visible separation between major fields when used as solid composition;
- some cells may be filled with navy, fuchsia, coral, green, or white;
- the structure may continue beyond the viewport;
- only a fragment may be visible;
- scale is usually large.

Correct mental model:

> Imagine zooming deeply into a football-panel structure until it becomes an abstract architectural composition.

Incorrect mental model:

> A wallpaper made of many small hexagons.

### Correct uses

- side of a hero;
- lower edge of a section;
- large campaign card;
- image crop/mask;
- full-bleed visual interlude;
- a single oversized background fragment at low contrast.

### Incorrect uses

- behind every form;
- inside every card;
- 30 tiny repeated cells;
- evenly tiled grid;
- equal use of every brand color.

---

## 6.2 Pattern Family B — Thin Organic Network Lines

This is the pattern most likely to be misunderstood.

The identity shows **thin, flowing, irregular lines** crossing and bending through space. The lines can use brand colors and can appear over white or navy.

They should feel like:

- connections;
- routes;
- an ecosystem;
- movement through an industry;
- a network of forces behind the visible game.

They should **not** feel like:

- random scribbles;
- topographic contour lines;
- tangled cables;
- a perfect mathematical mesh;
- a spider web;
- a circuit board;
- a Voronoi diagram generated at random.

### Geometry behavior

The lines:

- curve gently;
- change direction organically;
- cross or approach each other;
- are not equally spaced;
- do not create a strict repeating tile;
- may enter and leave the canvas;
- should have significant negative space;
- should use a small number of strokes.

### Color behavior

On a white/light surface:

- navy can provide the structural line;
- coral/green/fuchsia can provide selective additional routes.

On navy:

- colored lines may become more visible;
- keep density controlled;
- never compete with text.

### Scale

The network is **large-scale**.

A viewer should perceive several sweeping paths, not dozens of miniature repeated marks.

### Cropping

Cropping is encouraged. A pattern does not need to be fully visible.

Let lines:

- begin outside the viewport;
- leave through an edge;
- disappear behind a panel/image;
- occupy only one corner or band.

This makes the pattern feel like part of a larger system.

---

## 6.3 Pattern Family C — Outline Panel Network

Another expression uses polygon/panel outlines rather than filled masses.

This can be subtle and monochromatic.

Use it as:

- low-opacity background structure;
- large edge decoration;
- quiet texture on navy;
- a framing device.

Do not let it reduce text contrast.

---

## 6.4 Pattern Composition, not Pattern Wallpaper

This is a foundational KORA rule:

**PATTERN COMPOSITION ≠ PATTERN WALLPAPER**

Patterns should be **art-directed into a composition**.

A good pattern placement answers:

- Why is it here?
- What edge or content does it support?
- Where does the eye enter?
- Where does the pattern leave?
- Which area remains quiet?
- Does it reinforce the section hierarchy?

If the pattern can be repeated seamlessly in all directions and still look identical, it is probably being used incorrectly for KORA.

---

## 6.5 Pattern density

Use three conceptual density levels:

### Quiet
One or a few lines / one oversized outline fragment.

Best for:

- forms;
- dashboards;
- tables;
- authentication;
- long reading pages.

### Standard
Several visible lines or a clear cropped geometric fragment.

Best for:

- marketing sections;
- about pages;
- event information;
- section headers.

### Expressive
Multiple brand colors, large panel fragments, stronger network presence.

Best for:

- hero;
- campaign landing pages;
- major visual transitions.

Never use expressive density continuously across an entire site.

---

## 6.6 Layering order

Recommended stack:

1. base surface;
2. low-contrast pattern or large polygon field;
3. photography/illustration when present;
4. content surface if needed;
5. typography and interactive UI;
6. small accent detail.

Patterns belong **behind information**, never above controls.

Use `pointer-events: none` for decorative layers.

---

## 6.7 Pattern implementation

When official SVG assets exist, use them.

Preferred implementation:

```css
.brand-pattern {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.brand-pattern > img,
.brand-pattern > svg {
  position: absolute;
  width: min(70vw, 900px);
  height: auto;
}
```

Then position/crop the asset intentionally.

Do **not** default to:

```css
background-repeat: repeat;
background-size: 80px;
```

That behavior usually violates the brand composition.

---

# 7. Photography and Visual Content

Photography should feel documentary/editorial rather than stock-commercial.

Prefer:

- real football culture;
- people at work;
- industry activity;
- event environments;
- Saudi football history and contemporary context;
- authentic candid moments.

Avoid:

- generic stock players isolated on artificial stadium backgrounds;
- excessive AI-looking imagery;
- visual clichés such as balls/fire/neon trails unless specifically art-directed.

## 7.1 Photo treatment

Photography may be:

- full bleed;
- framed in a clean rectangle;
- cropped against polygon geometry;
- used in a split composition.

Do not apply a heavy brand-color overlay to every image.

---

# 8. Layout System

## 8.1 Container

Use a consistent content container with responsive side padding.

Suggested starting point:

```css
--container-max: 1440px;
--page-pad-desktop: clamp(32px, 5vw, 80px);
--page-pad-mobile: 20px;
```

These are implementation starting values, not immutable brand measurements.

## 8.2 Grid

Use a 12-column desktop grid when a formal grid is useful.

The design may break the grid for:

- hero display text;
- large brand art;
- full-bleed imagery;
- cropped shapes.

Functional content should return to the grid.

## 8.3 Section rhythm

KORA benefits from generous vertical rhythm.

Marketing/storytelling sections should feel spacious.  
Application/product screens can be denser but must still avoid cramped UI.

Prefer fewer, stronger sections over many small boxed modules.

## 8.4 Asymmetry

Controlled asymmetry is encouraged.

Examples:

- title occupies one side while a shape exits the opposite edge;
- an image aligns to a grid while an oversized number floats outside its column;
- a section label is small while the heading is dramatically large.

Asymmetry must still feel aligned and intentional.

---

# 9. Spacing

Use a consistent spacing scale.

Recommended implementation scale:

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 24px;
--space-6: 32px;
--space-7: 48px;
--space-8: 64px;
--space-9: 96px;
--space-10: 128px;
```

For branded editorial layouts, use the upper end generously.

Do not solve visual hierarchy by adding borders everywhere. Often spacing is the separator.

---

# 10. Corners, Borders, and Shadows

## 10.1 Radius

The identity can support rounded digital containers, but rounding should be controlled.

Use:

- small/medium radius for controls;
- medium/large radius for major cards where appropriate;
- rounded rectangles for selected branded digital surfaces.

Avoid:

- pill shapes for every component;
- huge “friendly SaaS” rounding across the entire UI.

## 10.2 Borders

Prefer subtle borders over heavy shadows in functional interfaces.

Borders may use:

- neutral gray;
- navy tint;
- white with low opacity on dark surfaces.

## 10.3 Shadows

Shadows should be restrained.

Use them for:

- floating navigation if necessary;
- modal elevation;
- dropdowns;
- clearly elevated interactive layers.

Do not use large soft shadows on every card.

---

# 11. Navigation

Navigation should be clean and confident.

## 11.1 Marketing sites

Header can be:

- transparent over a hero when contrast is safe;
- white/light;
- navy.

Use the official lockup. Keep the number of primary navigation items controlled.

Primary CTA may be visually distinct, but should remain within the palette.

## 11.2 Product / dashboard interfaces

Brand expression should be quieter.

Use navy as the anchor for:

- sidebar/header;
- active navigation;
- key actions.

Do not cover dense workspaces with patterns.

A small branded edge, header moment, or empty-state artwork is enough.

## 11.3 Sticky behavior

Sticky navigation is acceptable when useful. Ensure:

- it does not cover anchors;
- mobile height stays compact;
- scroll state has sufficient contrast.

---

# 12. Buttons

## 12.1 Primary

Recommended:

- navy fill + white text on light surfaces;
- white fill + navy text on navy surfaces.

## 12.2 Accent

Fuchsia/coral/green may be used for context-specific emphasis, not randomly.

## 12.3 Secondary

Use outline or quiet neutral treatment.

## 12.4 Button behavior

Every interactive button needs:

- default;
- hover;
- active;
- focus-visible;
- disabled;
- loading where applicable.

Do not rely on color alone for state.

Avoid gradient buttons.

---

# 13. Links

Text links should remain visibly interactive.

Possible treatments:

- underline;
- animated underline;
- color change with accessible contrast;
- arrow icon where navigation direction is meaningful.

Editorial links may use a more expressive underline/accent.

Functional links should remain simple.

---

# 14. Cards

Cards are **not** the default answer to every section.

Use a card when content genuinely needs:

- grouping;
- independent interaction;
- repeatable items;
- bounded comparison.

Otherwise use open layout and spacing.

## 14.1 Branded card

A major promotional/editorial card may contain:

- navy surface;
- one cropped polygon field;
- one accent color;
- oversized number;
- photography;
- network pattern at low density.

Do not combine all of these by default.

## 14.2 Functional card

Keep functional cards calm:

- white/light surface;
- subtle border;
- clear title;
- restrained radius;
- no decorative pattern unless the card is an empty state or campaign module.

---

# 15. Forms

Forms must optimize completion and error recovery.

## 15.1 Fields

Use:

- persistent label;
- clear input boundary;
- readable placeholder only as secondary guidance;
- helper/error text below;
- strong focus-visible state.

Do not use placeholder-only labels.

## 15.2 Brand treatment

Brand forms through:

- typography;
- primary button;
- section heading;
- restrained navy/accent details;
- optional quiet pattern outside the form column.

Do **not** put busy patterns behind inputs.

## 15.3 Validation

Error states must use:

- clear message;
- icon where useful;
- semantic error color;
- accessible association with the field.

Success/error meaning must not depend on brand colors alone.

---

# 16. Tables and Data-Dense Interfaces

Tables should prioritize scanning.

Use:

- clear header row;
- consistent alignment;
- adequate row height;
- restrained separators;
- sticky header where useful;
- horizontal overflow strategy on small screens.

Branding should come from:

- typography;
- navy headers/active controls;
- subtle accent status chips;
- surrounding page composition.

Do not place decorative patterns inside data tables.

---

# 17. Status Chips and Tags

Use compact chips for real categorical/status meaning.

Keep:

- clear text;
- restrained fills;
- sufficient contrast;
- consistent semantic mapping.

Do not turn every metadata item into a pill.

---

# 18. Modals, Drawers, and Overlays

Keep overlays functional and visually quiet.

- strong title;
- concise body;
- obvious primary/secondary actions;
- accessible focus trapping;
- escape/close behavior;
- prevent background interaction.

Patterns are normally unnecessary inside modals.

---

# 19. Empty, Loading, Error, and Success States

Every production KORA frontend must design these states.

## Empty
Good place for a small brand illustration/pattern fragment.

## Loading
Use skeletons for structured content. Use spinners only when appropriate.

## Error
Explain what happened and provide recovery.

## Success
Confirm the result and show the next logical action.

Do not make any of these states a blank screen.

---

# 20. Motion

Motion should communicate:

- reveal;
- connection;
- progression;
- entry into a larger system.

Suitable motions:

- gentle line drawing;
- cropped shape sliding into frame;
- staggered text reveal;
- number count-up when meaningful;
- subtle image mask reveal;
- underline/route movement.

Avoid:

- bouncy cartoon motion;
- constant floating objects;
- excessive parallax;
- spinning footballs;
- animation that delays task completion.

Respect:

```css
@media (prefers-reduced-motion: reduce) {
  /* Remove non-essential animation */
}
```

---

# 21. Section Numbering and Editorial Devices

Numbering such as:

- `01`
- `02`
- `03`

is a useful KORA editorial device.

Use it for:

- major site sections;
- journey stages;
- categories;
- campaign chapters.

It should reinforce hierarchy, not become meaningless decoration.

Large numerals may become visual composition elements, especially in marketing/editorial pages.

---

# 22. Iconography

Use a coherent icon family with simple strokes.

Icons should be:

- geometric;
- clean;
- legible;
- consistent in stroke and optical size.

Do not create an icon set by turning every concept into a football symbol.

The KORA logo symbol is a brand mark, not a generic UI icon.

---

# 23. Logo Usage in Web Products

Always use official supplied logo assets.

Do not:

- redraw the logo;
- change proportions;
- rotate it;
- add shadows;
- recolor outside approved brand combinations;
- place it on low-contrast backgrounds;
- use the symbol as a decorative repeating texture.

Allow adequate clear space around the logo.

Choose the appropriate official variation for the background.

---

# 24. Marketing / Campaign Websites

These may use the most expressive version of the system.

Recommended character:

- large hero typography;
- one strong visual concept per viewport;
- oversized geometry;
- art-directed patterns;
- editorial numbering;
- image/polygon compositions;
- navy full-bleed sections;
- bold white space;
- selective bright accents.

Still maintain:

- fast load;
- clear CTA;
- readable copy;
- accessible contrast;
- mobile integrity.

---

# 25. Recruitment / Application Websites

Recruitment pages should feel energetic but conversion-focused.

Use brand expression in:

- hero;
- section dividers;
- team/category visuals;
- CTA zones;
- footer.

Keep application steps and forms quieter.

A recruitment site should communicate:

1. what KORA is;
2. why participation matters;
3. available roles/teams;
4. expectations;
5. how and when to apply;
6. deadline/status clearly.

Do not let decorative motion or patterns compete with application information.

---

# 26. Internal Tools / Dashboards

For administrative KORA systems, reduce decorative density substantially.

Use the identity through:

- official logo;
- Ghroob typography;
- navy navigation;
- brand accent tokens;
- selected empty states;
- subtle page-header graphic moments.

The workspace itself should remain neutral and task-oriented.

**Functional clarity overrides decorative branding.**

Do not use giant hero typography inside ordinary CRUD screens.

---

# 27. Responsive Design

KORA must remain KORA on mobile; do not simply remove all identity.

## Desktop
Can support:

- asymmetric compositions;
- large patterns;
- oversized type;
- split layouts;
- off-canvas shapes.

## Tablet
Reduce overlap and pattern density.

## Mobile
Preserve the idea while simplifying:

- one strong shape instead of several;
- crop pattern more aggressively;
- stack content;
- reduce display size fluidly;
- keep CTA reachable;
- avoid horizontal overflow;
- maintain RTL correctly.

Use fluid typography where useful:

```css
font-size: clamp(min, preferred, max);
```

Decorative graphics must never cause layout overflow.

---

# 28. Accessibility

Brand fidelity does not override accessibility.

Required:

- WCAG-conscious contrast;
- keyboard navigation;
- visible focus;
- semantic headings;
- accessible labels;
- alt text for meaningful imagery;
- decorative imagery hidden from assistive technology;
- reduced-motion support;
- touch targets large enough for mobile;
- state not communicated by color alone.

Test bright brand colors before using them as text on white.

---

# 29. Performance

Brand assets can be visually rich, so implementation discipline matters.

- Prefer SVG for vector logos/patterns.
- Optimize raster imagery.
- Use responsive image sizes.
- Lazy-load below-the-fold media.
- Avoid huge decorative PNGs when a vector exists.
- Do not load every pattern on every page.
- Preload only truly critical fonts/assets.
- Prevent layout shift by reserving media dimensions.

---

# 30. CSS Design Tokens — Starting Structure

```css
:root {
  /* Brand */
  --kora-navy: #2D3B70;
  --kora-fuchsia: #944399;
  --kora-coral: #F26557;
  --kora-green: #4EA649;
  --kora-white: #FFFFFF;

  /* Neutral UI — project may refine */
  --ui-text: #172033;
  --ui-muted: #667085;
  --ui-border: #D9DEE8;
  --ui-surface: #FFFFFF;
  --ui-surface-soft: #F6F7F9;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 48px;
  --space-8: 64px;
  --space-9: 96px;
  --space-10: 128px;

  /* Layout */
  --container-max: 1440px;
  --page-pad: clamp(20px, 5vw, 80px);

  /* Radius */
  --radius-control: 10px;
  --radius-card: 18px;
  --radius-large: 28px;
}
```

The neutral colors and exact UI radii above are implementation defaults, **not official identity colors or measured brand specifications**. They may be adjusted for the product while preserving the overall system.

---

# 31. Asset Strategy

When a KORA asset package is supplied, inspect it before writing UI.

Expected asset families may include:

- official English logo;
- Arabic lockup;
- English lockup;
- symbol/ball mark;
- white/reversed lockup;
- main logo SVG;
- navigation lockup;
- brand imagery;
- mesh imagery;
- official pattern SVGs;
- campaign/event graphic kits.

### Asset priority

Use assets in this order:

1. official vector asset;
2. official raster asset;
3. CSS recreation only for generic layout geometry;
4. never invent/reconstruct the logo or official pattern from memory.

### Important

A filename containing `old` should not be chosen when a current equivalent exists unless the project explicitly requires it.

---

# 32. Composition Recipes

These recipes describe the design grammar without forcing a page template.

## Recipe A — Editorial Hero

- light or navy base;
- large display heading;
- short supporting paragraph;
- primary CTA;
- one oversized cropped polygon/pattern composition;
- optional image;
- ample negative space.

## Recipe B — Dark Brand Section

- navy full-width surface;
- white heading/body;
- one accent color;
- thin organic network lines at low/medium density;
- content remains dominant.

## Recipe C — Image + Polygon Story

- photograph occupies roughly one major region;
- adjacent/overlapping polygon field creates directional energy;
- heading aligns to grid;
- one accent color;
- no extra decorative card layer.

## Recipe D — Functional Form Page

- quiet white/light main area;
- clear form column;
- navy typography/action;
- subtle brand art outside form;
- no pattern behind fields.

## Recipe E — Dashboard

- neutral workspace;
- navy navigation;
- branded page title;
- white cards/tables;
- limited accent states;
- pattern only in empty state/header/rare promotional panel.

---

# 33. Anti-Patterns — Never Do These

Do **not**:

- tile small football panels across the entire background;
- use a generic honeycomb motif as “KORA style”;
- use every brand color in every section;
- make all cards gradient;
- put network lines behind long body text at high contrast;
- place decorative patterns above interactive controls;
- make every image polygon-shaped;
- use the logo symbol as a bullet/icon everywhere;
- create excessive glassmorphism;
- create neon glow;
- use generic stadium imagery as the only football cue;
- shrink desktop compositions without redesigning them for mobile;
- use placeholder-only form labels;
- hide important information in hover-only interactions;
- sacrifice readability for condensed typography;
- create a generic admin template and merely recolor it navy;
- interpret “football industry” as a sports scoreboard aesthetic.

---

# 34. AI Generation Guardrails

When an AI tool is asked to create a KORA frontend, include or enforce the following:

> Build the interface using KORA's design language. Do not copy a previous page layout. Use navy `#2D3B70` as the structural anchor and fuchsia `#944399`, coral `#F26557`, and green `#4EA649` as selective accents. Use the official Ghroob font and official logo/pattern assets when supplied. Compose patterns as oversized, cropped, art-directed elements; never tile small hexagons or create a generic honeycomb. Distinguish between large football-derived polygon geometry and the thin organic network-line pattern. Keep functional surfaces calm and readable. Use large editorial typography and generous whitespace on marketing pages, but reduce decorative density in forms, tables, and dashboards. Support Arabic RTL as a native layout. Preserve accessibility, responsiveness, and performance.

### Negative prompt / correction instruction

> Do not use generic SaaS styling, glassmorphism, neon sports aesthetics, tiled hexagons, random gradients, excessive pills, excessive cards, repeating football icons, or dense decorative patterns. Do not redraw official brand assets when files are provided. Do not let decorative layers reduce text contrast or interfere with controls.

---

# 35. Decision Rules for New Components

When designing a component that is not covered above, answer these questions in order:

1. **What is the user's task?**
2. **What hierarchy does the component need?**
3. **Can standard accessible UI solve it cleanly?**
4. **Where can KORA identity enter without harming the task?**
5. **Does this component actually need a pattern or shape?**
6. **If a brand graphic is added, can one element do the job instead of three?**
7. **Does the mobile version preserve the concept without preserving unnecessary complexity?**

If uncertain, choose the simpler functional component and apply brand identity through typography, color, spacing, and one controlled graphic gesture.

---

# 36. Brand Intensity Scale

Not every page needs the same amount of identity.

## Level 1 — Utility
For:
- tables;
- settings;
- admin;
- forms;
- data entry.

Brand through typography, logo, navy, and small accents.

## Level 2 — Branded Product
For:
- portal home;
- profile;
- application status;
- event schedule.

Add selective shapes and occasional patterns.

## Level 3 — Editorial
For:
- about;
- event story;
- team presentation;
- content features.

Use large typography, imagery, polygon compositions, numbering.

## Level 4 — Campaign
For:
- landing hero;
- launch;
- major announcement;
- event promotion.

Use the fullest art-directed system, while retaining readability.

**Do not use Level 4 styling on every screen.**

---

# 37. Quality-Control Checklist

Before considering a KORA frontend complete, verify:

## Brand
- [ ] Official logo asset used.
- [ ] Correct core palette.
- [ ] Ghroob used where available.
- [ ] Navy visually anchors the system.
- [ ] Accent colors are selective.
- [ ] No generic honeycomb treatment.
- [ ] Patterns are composed/cropped, not wallpapered.
- [ ] Network lines look intentional, sparse, and large-scale.
- [ ] Logo is not used as generic decoration.

## Layout
- [ ] Clear dominant hierarchy.
- [ ] Enough whitespace.
- [ ] Functional UI returns to a stable grid.
- [ ] Asymmetry is intentional, not accidental.
- [ ] Cards are used only when grouping is needed.

## Arabic / RTL
- [ ] Real RTL document direction.
- [ ] Mixed Arabic/English tested.
- [ ] Directional icons behave correctly.
- [ ] Mobile RTL checked independently.

## Responsive
- [ ] No horizontal overflow.
- [ ] Hero recomposed for mobile.
- [ ] Decorative shapes crop safely.
- [ ] Pattern density reduced where necessary.
- [ ] Controls remain touch-friendly.

## Accessibility
- [ ] Contrast checked.
- [ ] Keyboard navigation works.
- [ ] Focus is visible.
- [ ] Inputs have labels.
- [ ] Images have correct alt/decorative handling.
- [ ] Reduced motion supported.
- [ ] State does not depend on color alone.

## Performance
- [ ] SVG used where appropriate.
- [ ] Images optimized.
- [ ] Below-fold media lazy-loaded.
- [ ] Fonts loaded intentionally.
- [ ] No unnecessary pattern assets loaded globally.

## UX
- [ ] Primary action is obvious.
- [ ] Loading/error/empty/success states exist.
- [ ] Forms explain validation and recovery.
- [ ] Decoration never blocks information.
- [ ] Product-specific requirements were not distorted to mimic an old KORA site.

---

# 38. Final Principle

A successful KORA website should be recognizable **even if the logo is temporarily hidden**.

Recognition should come from the combined system:

**Ghroob typography  
+ navy-led palette  
+ selective fuchsia/coral/green  
+ oversized football-derived polygon geometry  
+ sparse organic network lines  
+ editorial scale  
+ generous negative space  
+ deliberate cropping  
+ disciplined functional UI.**

The goal is not to reproduce one KORA website.

The goal is to make different KORA websites feel as though they were designed by the **same visual system, with the same design intelligence, for different purposes.**

---

# 39. Official Asset Manifest — Mandatory AI Reference

> This section documents the actual files supplied in the KORA identity package. An AI or developer must inspect this manifest before choosing, recreating, or substituting any KORA visual asset.
>
> **Important correction to the generic pattern guidance above:** the supplied identity package DOES contain official hexagonal/panel-strip assets (`pattern-6.svg` and `pattern-8.svg`). Therefore, the rule is not “hexagons are forbidden.” The correct rule is: **do not invent a generic honeycomb as a substitute for KORA’s patterns. When an official hex/panel asset is appropriate, use the supplied asset itself and preserve its composition.**

## 39.1 Package structure

```text
src/
├─ assets/
│  ├─ brand/
│  │  ├─ kora-english.svg
│  │  ├─ kora-field-ball.png
│  │  ├─ kora-lockup-ar.png
│  │  ├─ kora-lockup-ball.png
│  │  ├─ kora-lockup-en.png
│  │  ├─ kora-lockup-white.png
│  │  ├─ kora-main-tight.svg
│  │  ├─ kora-main.svg
│  │  ├─ kora-nav-lockup.png
│  │  ├─ kora-old-ball.png
│  │  ├─ kora-old-word.png
│  │  └─ kora-real-football.png
│  ├─ images/
│  │  └─ mesh-0.png
│  └─ patterns/
│     ├─ pattern-6.svg
│     ├─ pattern-8.svg
│     └─ pattern-9.svg
└─ itfGhroob/
   └─ itfGhroob/
      ├─ itfGhroob-Light.otf
      ├─ itfGhroob-Regular.otf
      ├─ itfGhroob-Medium.otf
      ├─ itfGhroob-Bold.otf
      └─ itfGhroob-ExtraBold.otf
```

The archive contains **21 actual asset/font files** plus folders.

# 40. Brand Asset Dictionary

## 40.1 `assets/brand/kora-english.svg`

**Observed content:** standalone English `KORA` wordmark in vector form.

- Canvas: `1001 × 248`.
- It contains the custom angular KORA Latin lettering only.
- No Arabic wordmark.
- No ball/icon above it.
- The supplied vector uses a very light cool gray/off-white fill around `#E5E7EE`.

**Use for:**

- English-only brand moments;
- footer/header when the English wordmark alone is intentionally required;
- vector contexts where crisp scaling is important.

**Do not use for:**

- Arabic-only branding;
- a full bilingual lockup;
- generic headings or text. This is artwork, not a font.

**AI rule:** never type `KORA` in Ghroob and assume it replaces this wordmark. Use this SVG when the official English wordmark is required.

---

## 40.2 `assets/brand/kora-lockup-ar.png`

**Observed content:** standalone Arabic wordmark `كورة`.

- Size: `620 × 208`.
- Transparent PNG.
- White/light artwork.
- No English wordmark.
- No ball icon.

**Use for:** Arabic-only brand placement when a raster lockup is appropriate, especially on dark/navy or photographic backgrounds with sufficient contrast.

**AI rule:** this is a brand wordmark asset, not ordinary Arabic text. Do not recreate it by typing `كورة` in Ghroob.

---

## 40.3 `assets/brand/kora-lockup-ball.png`

**Observed content:** the KORA **iconic partial-football mark only**.

- Size: `355 × 183`.
- Transparent PNG.
- White/light mark.
- The symbol deliberately shows only a partial portion of a football/panel structure rather than a complete ball.

**Use for:**

- compact brand symbol;
- favicon/app-mark source only if technically suitable and approved;
- small branded moments where the full wordmark is unnecessary;
- lockups where the icon is intentionally separated from the name.

**Do not:** treat it as a generic football UI icon, bullet, status icon, or repeating decoration.

---

## 40.4 `assets/brand/kora-lockup-en.png`

**Observed content:** standalone English `KORA` wordmark.

- Size: `620 × 152`.
- Transparent PNG.
- White/light artwork.
- No Arabic wordmark and no ball icon.

**Use for:** English-only raster placements, particularly on dark backgrounds.

**Preference:** if both formats work, prefer `kora-english.svg` for scalable web rendering; use this PNG when the raster version is specifically needed or matches the supplied composition better.

---

## 40.5 `assets/brand/kora-lockup-white.png`

**Observed content:** horizontal **combined bilingual lockup** containing:

`KORA` + partial-football icon + `كورة`

- Size: `1747 × 208`.
- Transparent PNG.
- White/light artwork.
- Long horizontal aspect ratio.

**Use for:**

- dark/navy hero/header/footer surfaces;
- wide bilingual brand signatures;
- contexts where both English and Arabic brand names should appear together.

**Do not squeeze it into narrow mobile spaces.** Choose a more compact official mark instead.

---

## 40.6 `assets/brand/kora-nav-lockup.png`

**Observed content:** compact Arabic lockup combining the partial-football icon above the Arabic `كورة` wordmark.

- Size: `616 × 436`.
- Transparent PNG.
- White/light artwork.
- More vertically compact/square in composition than the bilingual horizontal lockup.

**Primary intended use:** navigation/header branding and compact UI brand placement, as its filename explicitly indicates.

**AI selection rule:** for an Arabic navigation/header where space permits this stacked form, prefer this purpose-built asset rather than manually stacking separate files.

---

## 40.7 `assets/brand/kora-main.svg`

**Observed content:** full vector artwork of the **Arabic primary lockup**: partial-football icon positioned above `كورة`.

- Canvas: `2048 × 2048`.
- Large square artboard with substantial surrounding area.
- Vector artwork contains light gray/off-white tonal fills.

**Use for:** high-quality scalable primary Arabic brand artwork when its full artboard behavior is useful.

**Implementation warning:** because the SVG uses a large square canvas, it may create more visual whitespace than expected when inserted directly with ordinary `<img>` sizing.

---

## 40.8 `assets/brand/kora-main-tight.svg`

**Observed content:** the same primary Arabic icon + wordmark family as `kora-main.svg`, but with a **tight/cropped viewBox** around the useful artwork.

- ViewBox: approximately `480 620 1080 800`.
- Vector.

**Preferred web use:** when the Arabic primary lockup must size predictably without the large empty square artboard of `kora-main.svg`.

**AI rule:** generally prefer `kora-main-tight.svg` over `kora-main.svg` for ordinary responsive web placement unless the larger artboard is intentionally needed.

---

## 40.9 `assets/brand/kora-field-ball.png`

**Observed content:** realistic 3D/rendered football with selected panels colored in KORA navy, coral, green, and fuchsia.

- Size: `1024 × 1024`.
- Transparent PNG.
- Full physical ball representation.

**Use for:** campaign/editorial visual storytelling where a literal football object is appropriate.

**Do not confuse this with the KORA logo symbol.** It is imagery, not the primary brand mark.

---

## 40.10 `assets/brand/kora-real-football.png`

**Observed content:** realistic traditional football image, primarily white with dark/navy panels.

- Size: `1024 × 1024`.
- Transparent PNG.

**Use for:** literal football imagery, comparisons, storytelling, or campaign compositions.

**Do not use as the logo.**

---

## 40.11 `assets/brand/kora-old-ball.png`

**Observed content:** older/legacy raster version of the partial-football icon.

- Size: `604 × 312`.
- Transparent PNG.

**Status:** **legacy/old** because the filename explicitly marks it `old`.

**AI rule:** do not select it by default when current equivalents such as `kora-lockup-ball.png`, `kora-main-tight.svg`, or other current lockups exist. Use only when a task explicitly requires the legacy asset or visual comparison.

---

## 40.12 `assets/brand/kora-old-word.png`

**Observed content:** older/legacy Arabic `كورة` wordmark.

- Size: `1062 × 367`.
- Transparent PNG.

**Status:** legacy/old.

**AI rule:** do not use in new frontend work by default. Prefer current official wordmark/lockup assets.

---

# 41. Non-Logo Brand Image

## 41.1 `assets/images/mesh-0.png`

**Observed content:** high-resolution abstract **organic mesh/membrane artwork**.

- Size: `4096 × 4096`.
- Large raster image (~6 MB in the supplied package).
- Predominantly white negative space.
- Soft, blurred, translucent-looking boundaries and junctions.
- Color appears selectively along the membrane edges/junctions using KORA-like navy/purple, coral, green, and blue-violet tones.
- The visual feels fluid, biological/networked, and atmospheric rather than geometric and tiled.

This asset is especially important because it represents a **different visual family** from the SVG polygon patterns.

### Correct use

Use `mesh-0.png` for high-expression brand moments such as:

- hero/background art;
- editorial transitions;
- campaign splash sections;
- atmospheric edge/corner crop;
- a large visual layer with substantial white negative space.

### Incorrect use

Do not:

- shrink it into a tiny repeated texture;
- tile it;
- place dense UI text over the visually active junctions;
- use the 4096px source at full weight everywhere without optimization;
- mistake it for the thin line-network pattern described elsewhere.

### Web implementation

Because the source is 4096×4096 and heavy, create responsive optimized derivatives (for example AVIF/WebP) for production while preserving the official original as the source asset. Crop rather than distort.

**AI interpretation:** this is an atmospheric branded image, not a procedural CSS effect. If supplied, use the real asset instead of trying to recreate it with random gradients or blur filters.

---

# 42. Official Pattern Files — Exact Meanings

## 42.1 `assets/patterns/pattern-6.svg`

**Observed content:** long horizontal strip made from a repeated two-row sequence of dark navy hexagonal/panel cells.

- SVG size: `10685 × 2129`.
- Dominant dark fill around `#151F47`.
- Highly horizontal aspect ratio.
- Regular, structured repetition.

### Use

Suitable for:

- horizontal edge/band decoration;
- footer or section-edge treatments;
- cropped structural motif;
- controlled brand strip where this exact official composition fits.

### Critical rule

This file proves that **repetition/hexagonal cells are part of the official asset library**. However, the AI must use this **specific designed asset/composition**, not generate arbitrary honeycomb wallpaper and call it KORA.

Do not stretch it non-proportionally.

---

## 42.2 `assets/patterns/pattern-8.svg`

**Observed content:** long horizontal cluster/chain of hexagonal/panel cells using the KORA palette.

- SVG size: `23066 × 4595`.
- Includes approximately these embedded brand values: navy `#2B3A6F`, fuchsia `#934398`, coral `#F06357`, green `#4DA648`, plus darker navy around `#151E47`.
- The colors appear in an intentionally irregular sequence rather than a uniform rainbow repetition.

### Use

Suitable for:

- campaign/footer bands;
- lower/upper edge crops;
- branded editorial separators;
- selected merchandise-like or event compositions;
- controlled accent zones.

### Rule

Do not recolor every cell arbitrarily and do not rebuild it as a generic CSS hex grid when the SVG is available.

The slight hexadecimal differences from the canonical palette are embedded in the supplied artwork and should generally be preserved **inside the SVG**. UI color tokens should still use the canonical palette defined earlier.

---

## 42.3 `assets/patterns/pattern-9.svg`

**Observed content:** large irregular football/panel-derived composition rather than a regular tiled strip.

- ViewBox: `0 0 2915.47 2991.62`.
- Uses large navy filled panel forms.
- Includes overlaid/adjacent outline structures in white/light and coral.
- Coral strokes are explicitly thick (around `28` units in the SVG).
- Composition is vertically/square oriented and visually dynamic.

### Use

This is the strongest official example of the principle:

**large-scale pattern composition, not generic wallpaper.**

Use it:

- oversized;
- cropped by a viewport/section edge;
- behind or adjacent to hero/editorial content;
- as a major branded visual gesture.

Do not reduce it to a tiny repeating icon.

---

# 43. Reconciling the Pattern Families

The actual asset package establishes **three separate pattern/image behaviors**:

1. **Regular panel strip** — `pattern-6.svg`.
2. **Colored panel cluster/strip** — `pattern-8.svg`.
3. **Oversized irregular panel composition** — `pattern-9.svg`.
4. **Atmospheric organic mesh image** — `mesh-0.png` (image family, not SVG panel pattern).

Therefore, an AI must **not force every KORA pattern into one rule**.

### Selection logic

- Need a narrow structural horizontal band? → consider `pattern-6.svg`.
- Need a colorful branded horizontal cluster? → consider `pattern-8.svg`.
- Need a large expressive polygon composition? → consider `pattern-9.svg`.
- Need atmospheric/soft/organic hero art? → consider `mesh-0.png`.
- Need a clean functional screen? → often use **none** of them.

The existence of an asset does not mean it must appear on every page.

---

# 44. Ghroob Font File Manifest

The supplied font family identifies itself internally as **`itf Ghroob`** and includes Arabic support. The package contains five static OTF weights.

| File | Internal style | Recommended CSS weight | Primary web role |
|---|---|---:|---|
| `itfGhroob-Light.otf` | Light | `300` | oversized elegant display, low-emphasis editorial text; avoid for tiny UI |
| `itfGhroob-Regular.otf` | Regular | `400` | body copy, normal labels, standard UI text |
| `itfGhroob-Medium.otf` | Medium | `500` | navigation, buttons, emphasized labels, compact subheadings |
| `itfGhroob-Bold.otf` | Bold | `700` | headings, strong buttons/labels, section titles |
| `itfGhroob-ExtraBold.otf` | Extra Bold | `800` | hero/display emphasis, short high-impact headings |

> The identity presentation explicitly demonstrates Light, Regular, and Bold. Medium and ExtraBold are additionally present in the delivered font package, so they are available for digital hierarchy when useful. Do not overuse ExtraBold in dense UI.

## 44.1 Recommended `@font-face`

Use the actual paths in the project after copying the official files into the project’s public/static font directory. Example:

```css
@font-face {
  font-family: "Ghroob";
  src: url("/fonts/itfGhroob-Light.otf") format("opentype");
  font-weight: 300;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Ghroob";
  src: url("/fonts/itfGhroob-Regular.otf") format("opentype");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Ghroob";
  src: url("/fonts/itfGhroob-Medium.otf") format("opentype");
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Ghroob";
  src: url("/fonts/itfGhroob-Bold.otf") format("opentype");
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "Ghroob";
  src: url("/fonts/itfGhroob-ExtraBold.otf") format("opentype");
  font-weight: 800;
  font-style: normal;
  font-display: swap;
}
```

## 44.2 Weight usage rules

### Light — 300
Use selectively for:

- very large numerals;
- editorial display phrases;
- oversized section numbers;
- low-density visual typography.

Avoid for small body copy and low-contrast text.

### Regular — 400
Default for:

- body text;
- descriptions;
- input text;
- table cells;
- long Arabic copy;
- normal metadata.

### Medium — 500
Default emphasis weight for:

- navigation;
- buttons;
- tabs;
- field labels;
- filters;
- compact headings.

### Bold — 700
Use for:

- H2/H3-level headings;
- important card titles;
- strong CTA text where needed;
- key values.

### ExtraBold — 800
Reserve for:

- hero headings;
- campaign headlines;
- short major statements.

Do not use ExtraBold for entire forms, tables, or paragraphs.

## 44.3 Arabic and Latin

The delivered Ghroob files contain Arabic glyph support as well as Latin characters/numerals. Therefore, the same family can maintain visual continuity across Arabic and English.

Still test:

- Arabic shaping;
- punctuation;
- mixed Arabic/English strings;
- numerals;
- line-height at each weight;
- browser rendering on Windows/macOS/mobile.

## 44.4 Font licensing/serving caution

The files are supplied as OTF. Before public production deployment, the project owner should ensure web-serving rights and licensing permit hosting the font files. If WOFF2 versions are officially available, they are generally preferable for web delivery. Do not use an unofficial online converter if licensing or font integrity is uncertain.

---

# 45. Asset Selection Decision Tree for AI Tools

Before creating or coding a KORA visual element, follow this order:

### Need to show the brand name/logo?

- Arabic primary stacked mark → `kora-main-tight.svg` is generally the strongest scalable web choice.
- Arabic compact navigation mark → `kora-nav-lockup.png`.
- Arabic word only → `kora-lockup-ar.png`.
- English word only → `kora-english.svg` preferred for vector use; `kora-lockup-en.png` if raster is specifically suitable.
- English + icon + Arabic in one horizontal signature → `kora-lockup-white.png`.
- Icon only → `kora-lockup-ball.png`.
- Never default to files containing `old`.

### Need football imagery rather than a logo?

- branded colored physical football → `kora-field-ball.png`.
- traditional physical football → `kora-real-football.png`.

### Need branded decoration?

- dark regular horizontal panel band → `pattern-6.svg`.
- multicolor horizontal panel band → `pattern-8.svg`.
- large irregular panel composition → `pattern-9.svg`.
- soft atmospheric organic mesh → `mesh-0.png`.

### Need typography?

Use `itf Ghroob` from the supplied OTF files according to the weight hierarchy above. Do not recreate brand wordmarks by typing them in the font.

---

# 46. Mandatory Asset Rules for Generated Frontends

1. **Inspect the asset folder before drawing anything brand-specific.**
2. **Prefer current official SVGs over raster equivalents where the same intended mark exists and SVG behavior is suitable.**
3. **Do not convert a logo into text.** Wordmarks are artwork.
4. **Do not use `kora-old-*` files in new work unless explicitly requested.**
5. **Do not use realistic football PNGs as logos.**
6. **Do not use the partial-football logo symbol as a generic UI icon.**
7. **Do not procedurally imitate `mesh-0.png` with random gradients when the asset is supplied.**
8. **Do not rebuild `pattern-6`, `pattern-8`, or `pattern-9` from generic CSS shapes when the official SVG can be used.**
9. **Do not stretch any logo/pattern non-proportionally.**
10. **Preserve transparency around PNG lockups.**
11. **Choose a logo variant based on background contrast and available aspect ratio.**
12. **Optimize heavy raster assets for production without changing the visual design.**
13. **Use `kora-main-tight.svg` when the large whitespace of `kora-main.svg` creates sizing problems.**
14. **Treat canonical UI colors and colors embedded inside official artwork differently:** do not rewrite an SVG merely because its embedded color differs by one or two RGB values from the UI token.
15. **A page does not become more KORA by using more assets.** Select the minimum asset set that supports the composition.

---

# 47. Updated Pattern Anti-Pattern Rule

Where earlier sections say “do not use honeycomb” or “never reduce the system to repeated hexagons,” interpret them precisely as follows:

> **Do not invent a generic honeycomb/repeated-hex visual language and use it as a substitute for KORA’s identity.**
>
> **Official KORA assets that themselves contain repeated hex/panel structures — especially `pattern-6.svg` and `pattern-8.svg` — are valid and should be used when their intended composition fits the design.**

This distinction is mandatory. The error is **generic AI-generated honeycomb**, not the existence of hexagonal/panel geometry itself.

---

# 48. Source-of-Truth Priority

When there is uncertainty, use this priority:

1. **Actual supplied current asset file** for its own visual appearance and proportions.
2. **Official KORA identity guidelines** for brand intent and system rules.
3. **This master reference** for web interpretation and implementation behavior.
4. Existing KORA web products as examples of application, not as immutable templates.
5. AI inference only when none of the above defines the issue.

If an AI cannot access an asset referenced here, it must **request the asset or use a clearly temporary placeholder** rather than hallucinating its appearance.
