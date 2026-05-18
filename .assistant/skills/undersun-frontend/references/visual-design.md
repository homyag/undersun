# Undersun Visual Design Rules

Use this reference for public page redesigns, layout polish, hero sections, CTA blocks, catalog presentation, property detail composition, service pages, and blog/content pages.

## Design Goal

Create a premium Phuket real-estate experience: calm, trustworthy, visually specific, and conversion-oriented without looking like a generic property portal.

The interface should feel like:

- a premium real-estate advisory brand;
- a curated Phuket property catalog;
- a confident investment and relocation guide;
- a warm service business with human contact.

It must not feel like:

- a generic SaaS landing page;
- a commodity real-estate listing aggregator;
- a travel agency brochure;
- an infobusiness funnel;
- a dashboard pretending to be a public page;
- a template made from repeated equal cards.

## Design Workflow

Before changing layout or code, define:

1. Context: what page this is, what user state it serves, and what the user should understand or do next.
2. Visual direction: what tone the page should create and why this page is specific to Phuket property.
3. One differentiator: choose one memorable visual move for the page.
4. System: lock palette, type scale, spacing rhythm, image treatment, radii, shadows, and motion tone before implementation.
5. Implementation: only then compose templates, Tailwind classes, CSS, and JS.

Do not jump from vague intent directly to grids and cards.

## Brand-Aware Aesthetic

Prefer:

- existing brand anchors: `primary #474B57`, `primaryDark #333847`, `accent #F1B400`, `tertiary #616677`;
- warm neutrals: ivory, sand, stone, soft gray, muted gold;
- restrained tropical cues: sunlight, sea/green accents, natural textures;
- strong property imagery and editorial spacing;
- clear hierarchy around search, catalog, price, location, contact, and trust.

Avoid:

- purple/blue generic SaaS gradients;
- neon tropical palettes;
- making every section a rounded bordered card;
- identical 3-column grids as the default answer;
- heavy glassmorphism/blur everywhere;
- decorative shapes that compete with property photos;
- stock travel-poster aesthetics that weaken real-estate trust.

## Page-Specific Guidance

Homepage:

- Give the first screen a strong real-estate promise and one dominant visual/composition.
- Avoid “hero plus many feature cards” as the default.
- Keep CTAs focused: catalog/search/contact, not a pile of equivalent actions.

Catalog:

- Prioritize scannability, filters, map/list clarity, and price/location trust.
- Keep filter UI usable and calm; do not let decoration compete with results.
- Avoid over-polishing cards at the cost of density and comparison.

Property detail:

- Let gallery, title, price, location, and contact path lead.
- Keep sticky/contact CTAs clear but not aggressive.
- Preserve trust signals and structured content; do not bury practical facts under decorative blocks.

Service and blog pages:

- Use a more editorial rhythm: strong headings, controlled prose width, meaningful media, and fewer stronger sections.
- Do not expose internal labels such as SEO block, visual placeholder, bootstrap data, or section image.

## Layout Discipline

- Start with hierarchy, not container decoration.
- Use CSS Grid for macro layout and Flexbox for smaller content clusters.
- Prefer `minmax(...)` grids over fragile fixed tracks.
- Collapse to one column early enough on mobile.
- Keep prose widths controlled.
- Use stable image ratios to avoid layout shift.
- Make the hero visually stronger than lower sections unless the page type has a clear reason not to.

## Copy Discipline

User-facing copy must sound like premium real-estate service copy, not implementation notes.

Do:

- write concrete, calm, human copy;
- keep headings short and meaningful;
- use real user value: location, property type, lifestyle, investment, ownership clarity, viewing/contact path;
- preserve language-specific tone for `ru`, `en`, and `th`.

Avoid:

- visible placeholder labels;
- internal terms such as “SEO section”, “visual block”, “card grid”, “bootstrap payload”;
- urgency/funnel language unless backed by real data;
- overpromising returns, legal certainty, or guarantees.

## Motion And Accessibility

- Motion should support hierarchy, not decorate every block.
- Respect `prefers-reduced-motion`.
- Keep focus states visible.
- Maintain one `h1`, logical heading order, semantic sections, descriptive alt text, usable mobile tap targets, and no horizontal overflow.
- Ensure hover-only cues have mobile/focus equivalents.

## Acceptance Checklist

- The page does not look like a generic real-estate template.
- One clear visual move can be named in a sentence.
- The visual system stays coherent from hero to final CTA.
- There are not too many equal cards.
- Property imagery, type scale, and spacing rhythm carry the design before decorative effects.
- Mobile preserves hierarchy instead of squeezing desktop layout.
- Copy is user-facing, multilingual-aware, and free of internal implementation labels.
- Analytics, forms, currency, favorites, and server-rendered SEO behavior remain intact.
