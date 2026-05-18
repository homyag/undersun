---
name: undersun-frontend
description: Work safely on the Undersun Estate frontend in the Django codebase. Use when modifying Django templates, Tailwind/CSS, vanilla JavaScript modules, analytics goals, forms, currency/favorites UI, homepage/catalog/property-detail/map/blog frontend behavior, or when deciding which frontend file or build pipeline owns a UI change.
---

# Undersun Frontend

## Core Rule

Treat this as a server-rendered Django frontend with page-specific vanilla JS. Before editing, identify the owning template/include, the static JS module, and the active CSS pipeline. Do not assume React/Vite/Webpack or a single Tailwind source of truth.

For the detailed file map, read `references/frontend-map.md` when a task touches a page area you have not already inspected in the current turn. For public page redesign, layout, styling, content hierarchy, or visual polish, also read `references/visual-design.md`.

## Workflow

1. Locate the page entry point in `config/urls.py`, the Django view, and the template root.
2. Check whether behavior lives in the template, a bootstrap include, `static/js`, or mixed legacy code.
3. Check CSS ownership before styling:
   - `templates/base.html` loads `theme/static/css/dist/styles.css` when `TAILWIND_USE_CDN = False`.
   - `theme/static_src/package.json` owns the active Tailwind build for the base layout.
   - Root `package.json` builds `static/css/tailwind.min.css`, but that file is not loaded by `templates/base.html` unless a specific template explicitly references it.
4. Preserve language-prefix routing and use existing URL helpers or current language prefix conventions.
5. Preserve existing analytics, currency, favorites, reCAPTCHA, honeypot, and form timing patterns.
6. Verify with targeted template/static checks and, when relevant, run the correct CSS build command.

## Page Ownership

- Homepage: `apps.core.views.HomeView`, `templates/core/home.html`, includes in `templates/core/includes/home/*` and `templates/includes/home/*`, behavior in `static/js/home/*`.
- Catalog: `apps.properties.views.PropertyListView`, `templates/properties/list.html`, includes in `templates/properties/includes/list/*` and `templates/includes/list/*`, behavior in `static/js/list/*`.
- Property detail: `apps.properties.views.PropertyDetailView`, `templates/properties/detail.html`, bootstrap data in `templates/properties/includes/detail_bootstrap.js.html`, behavior in `static/js/properties/detail.js`.
- Map page: `apps.core.views.MapView`, `templates/core/map.html`, behavior in `static/js/map/*`.
- Favorites: `templates/properties/favorites.html`, behavior in `static/js/favorites/favorites.js`, persistence in `localStorage`.
- Forms: endpoints in `apps.users.views`, common AJAX helpers in `static/js/forms.js`, hidden security fields in `templates/core/includes/*`.

## Implementation Rules

- Keep template inline JS limited to server-derived bootstrap data. For property detail, add data to `detail_bootstrap.js.html` and behavior to `static/js/properties/detail.js`.
- Use existing `currencyChanged` event handling for price/UI updates. Do not create a parallel currency state model.
- Keep favorites client-side through `localStorage`. Use backend favorite endpoints only to fetch current property data for stored IDs.
- Add CTA analytics with `data-ym-goal` when declarative tracking is enough. Use `window.dispatchMetrikaGoal(goalName, params)` for programmatic events.
- New forms must include CSRF, reCAPTCHA token fields when configured, and `form_security_fields.html`; backend handlers should keep the JSON contract.
- Prefer extending existing page modules over adding new global scripts. Add a new file only when the page area already has modular JS and the ownership is clear.
- Preserve multilingual behavior for `ru`, `en`, `th`; avoid hard-coded non-prefixed public URLs.

## Public Page Design

When changing public-facing layouts, do not let Tailwind defaults or repeated cards define the page. First define the page intent, one memorable visual move, and a stable token system; then implement. Keep the result premium, real-estate specific, and consistent with the existing Undersun brand palette.

Use `references/visual-design.md` for adapted design rules from the editorial frontend skill.

## Build And Validation

Use the theme pipeline for CSS that affects the current base layout:

```bash
cd theme/static_src
npm run build
```

Use root Tailwind only when the changed template explicitly consumes `static/css/tailwind.min.css`:

```bash
npm run build-css-prod
```

For JS/template changes, prefer targeted checks:

```bash
python manage.py check
rg -n "changed-selector-or-goal" templates static/js static/css
```

If you change URL-dependent frontend code, test localized paths such as `/ru/...`, `/en/...`, and `/th/...` where practical.
