# Undersun Frontend Map

## Runtime Stack

- Server rendering: Django templates under `templates/`.
- Styling: Tailwind plus custom CSS.
- Primary CSS runtime path: `templates/base.html` -> `{% static 'css/dist/styles.css' %}` -> `theme/static/css/dist/styles.css`.
- Primary Tailwind source for runtime path: `theme/static_src/src/styles.css`, built by `theme/static_src/package.json`.
- Secondary/root Tailwind path: `static/css/tailwind.css` -> `static/css/tailwind.min.css`, built by root `package.json`; not loaded by base layout by default.
- JavaScript: vanilla modules under `static/js`, with some jQuery in legacy/favorites flows.

## Global Files

- `templates/base.html`: SEO meta, Tailwind/CSS loading, global recaptcha bootstrap, global layout blocks.
- `templates/includes/layout/header.html`: desktop navigation, language/currency controls.
- `templates/includes/layout/mobile_menu.html`: mobile navigation.
- `templates/includes/layout/footer.html`: footer.
- `templates/includes/layout/global_scripts.html`: global scripts and currency UI helpers.
- `static/js/main.js`: shared/legacy helpers.
- `static/js/forms.js`: common AJAX form submission and popup feedback.
- `static/js/analytics/metrika-goals.js`: declarative `data-ym-*` and programmatic Metrika goals.
- `templates/core/includes/recaptcha_token_field.html`: hidden reCAPTCHA fields.
- `templates/core/includes/form_security_fields.html`: honeypot and render timestamp fields.

## Home

- View: `apps.core.views.HomeView`.
- Root template: `templates/core/home.html`.
- Data/structured includes: `templates/includes/home/home_data_injection.html`, `templates/includes/home/home_structured_data.html`.
- Section includes: `templates/core/includes/home/home_*_section.html`.
- JS modules: `static/js/home/hero.js`, `search-counter.js`, `featured-properties.js`, `consultation.js`, `process-steps.js`, `our-team.js`, `reviews-carousel.js`.
- Important pattern: featured properties are rendered from server bootstrap payload and update on `currencyChanged`.

## Catalog

- View: `apps.properties.views.PropertyListView` plus sale/rent/type subclasses.
- Root template: `templates/properties/list.html`.
- Shared includes: `templates/includes/list/list_data_injection.html`, `list_scripts.html`, `list_styles.html`.
- Section includes: `templates/properties/includes/list/list_*`.
- JS modules: `static/js/list/list_main_init.js`, `list_map_functions.js`, `list_map_data_loader.js`, `list_view_toggle.js`, `list_favorites.js`, `list_utility_functions.js`.
- Important patterns: grid/map state is frontend-driven, map data comes from AJAX JSON, filters are server-backed and partly auto-submitted.

## Property Detail

- View: `apps.properties.views.PropertyDetailView`.
- Root template: `templates/properties/detail.html`.
- Bootstrap include: `templates/properties/includes/detail_bootstrap.js.html`.
- JS behavior: `static/js/properties/detail.js`.
- CSS: `static/css/properties/detail.css` if loaded by the template.
- Important pattern: keep Django-dependent data inline, keep behavior in `detail.js`.
- Common features: gallery, carousel, modals, favorites, forms, price/currency updates, map bootstrap, Metrika goals.

## Map

- View: `apps.core.views.MapView`.
- Root template: `templates/core/map.html`.
- JS modules: `static/js/map/map_core.js`, `map_page.js`, `map_popups.js`.
- Important patterns: listen for `currencyChanged`, use existing popup builders and Metrika goal dispatch.

## Favorites

- Route/template: `templates/properties/favorites.html`.
- JS: `static/js/favorites/favorites.js`.
- CSS: `static/css/favorites/favorites.css`.
- Storage: `localStorage` key `favorites`.
- Backend data endpoint: `apps.properties.views.get_favorite_properties`.
- Do not re-enable server persistence through `toggle_favorite`; it intentionally returns disabled.

## Forms And Security

- Backend endpoints: `apps.users.views`.
- Common client submission: `static/js/forms.js`; some page modules implement local handlers.
- Required frontend fields: CSRF token, optional reCAPTCHA hidden token/action, honeypot `website`, `form_rendered_at`.
- Backend validation: `apps.core.utils.validate_form_security`.
- Response contract: JSON with `success` and `message`.

## Analytics

- Add declarative goals with `data-ym-goal`.
- Add parameters with `data-ym-param-*` or JSON `data-ym-params`.
- For non-DOM events, call `window.dispatchMetrikaGoal(goalName, params)`.
- Existing catalogs: `docs/METRIKA_GOALS_*.md`.

## Currency

- Backend service: `apps.currency.services.CurrencyService`.
- Frontend event: `currencyChanged`.
- Currency selector template: `templates/currency/currency_selector.html`.
- Global currency script helpers also appear in `templates/includes/layout/global_scripts.html`.
- Do not maintain a separate currency source of truth outside session/global event flow.
