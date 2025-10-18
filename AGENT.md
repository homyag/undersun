# AGENT HANDBOOK - UNDERSUN ESTATE

This file is a quick-start briefing for autonomous coding agents working on the Undersun Estate Django project (real estate marketplace focused on Phuket, Thailand). It summarizes the codebase, key workflows, and gotchas so you can move fast without rereading every source file.

---

## 1. Mission & Domain Context
- Multi-language (RU/EN/TH) real estate platform for sale and rent inventory.
- Target audience prioritizes Russian-speaking investors; THB is the financial source of truth.
- Core differentiators: investment storytelling, consultation funnel, interactive map, currency-aware UX, rich media galleries.

---

## 2. Tech Stack & Runtime
- **Backend**: Django 5.0.6, Python 3.x, PostgreSQL (psycopg2-binary).
- **Frontend**: Django templates + Tailwind CSS 4.x, Font Awesome, jQuery, modular vanilla JS.
- **Maps**: Leaflet + custom SVG markers, optional markercluster/draw plugins (see `MAP_IMPROVEMENTS.md`).
- **Translations**: django-modeltranslation, Rosetta UI, optional Google/DeepL APIs via `TranslationService`.
- **Media**: django-imagekit for responsive thumbnails, TinyMCE for blog content.
- **Build tooling**: Tailwind CLI (`npm run build-css` / `build-css-prod`).
- **Environment management**: django-environ; settings split across `config/settings/{base,development,production}.py`.

Minimum local setup:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install  # Tailwind build (optional but recommended)
python manage.py migrate
python manage.py runserver
```
Optional seed data lives in repo dumps (`complete_real_estate.db`, `undersunestate_dump_*.sql`).

---

## 3. Django App Map
```
apps/
|- core          # home, static pages, SEO, promotional banners, team
|- properties    # listings, gallery, filters, AJAX endpoints, admin tooling
|- locations     # districts/locations hierarchy
|- currency      # currencies, exchange rates, session handling
|- users         # inquiry + consultation submissions, newsletter, office visits
|- blog          # blog posts, categories, parser utilities
`- data_import   # legacy migration & parsers (properties/blog)
```
Supporting assets:
- `templates/` contains large composable templates (esp. `core/home.html`, `properties/detail.html`, `properties/includes/list/*`).
- `static/js` holds feature-specific bundles (`home/featured-properties.js`, `list/*`, `favorites/*`, `properties/detail.js`).
- `static/admin/js` manages sortable image UX and admin fixes.

---

## 4. Canonical Models & Services
- **Property** (`apps/properties/models.py`): master object with multi-currency pricing (THB base), investment metadata, map coordinates, SEO overrides, translated fields.
- **PropertyImage**: auto-maintains `is_main` flag, exposes `thumbnail`/`medium` specs for galleries and popups.
- **PropertyType**, **PropertyFeature**, **Developer**, **Agent**: taxonomy + relationships; translation config in `translation.py`.
- **District** / **Location** (`apps/locations`): two-level geography used in filters and map popups.
- **Currency** / **ExchangeRate** (`apps/currency`): enforce single base currency (THB). `ExchangeRate.convert_amount` is the safe conversion path.
- **PromotionalBanner**, **SEOTemplate**, **Service**, **Team** (`apps/core`): drive homepage banner, SEO fallback, static service pages, and team listings.
- **BlogPost** / **BlogCategory**: power content marketing; authors can be core team members.
- **Inquiry models** (`apps/users/models.py`): capture all lead forms (property inquiries, quick consultations, contact forms, office visits, FAQ, newsletter). Integration with AmoCRM is stubbed.
- **TranslationService** (`apps/core/services.py`): wraps Google/DeepL APIs, chunking, HTML preservation. Global instance exposed as `translation_service`.

---

## 5. Key User Workflows
### Homepage (`apps/core/views.HomeView`, `templates/core/home.html`)
- Loads featured properties for villas/condos/townhouses, serialized via `serialize_properties_for_js` and consumed by `static/js/home/featured-properties.js`.
- Consultation cards injected every fourth carousel item; branding/styling rules captured in `CONSULTATION_FORM_UPDATE.md` & `CONSULTATION_FORM_BRANDING_UPDATE.md`.
- Currency changes propagate through custom events (`currencyChanged`), reusing shared conversion helpers.

### Property Listing (`apps/properties/views.PropertyListView` + includes)
- Filters applied server-side via `apply_filters`; map view disables pagination through `get_paginate_by` override.
- AJAX endpoints: `property_list_ajax`, `map_properties_json`, `get_locations_for_district`, `ajax_search_count`.
- Frontend JS (see `static/js/list/*`) handles:
  - View toggling (grid vs map, persisted via `localStorage`).
  - Debounced filter submission with auto-return to map view.
  - Leaflet map with custom SVG markers, price badges, rich popups, and fallback to current page data when the full fetch fails.
  - Favorite toggles delegate to localStorage (no server persistence).

### Property Detail (`apps/properties/views.PropertyDetailView`, `templates/properties/detail.html`)
- Inline script only provides data scaffolding (PROPERTY_* constants, map init, favorite binding). All behaviour lives in `static/js/properties/detail.js` per `docs/js_refactoring_summary.md`.
- Features: media gallery modal, auto carousel, price conversions, consultation/viewing modals, WhatsApp share links, translation-ready text blocks.
- `get_similar_properties` prioritizes same type + district, then same district, then same type fallback.

### Favorites (`templates/properties/favorites.html`, `static/js/favorites/favorites.js`)
- Solely handled on the client; server supplies fresh property data via `get_favorite_properties` to respect current currency and formatting.
- Toggle endpoint is intentionally disabled (`toggle_favorite` responds with failure) to enforce localStorage usage.

### Currency Switching (`apps/currency/views.ChangeCurrencyView`)
- POST-only endpoint sets `request.session['currency']`; AJAX responses include the symbol for header/UI.
- Defaults determined by `CurrencyService.get_currency_for_language` (ru->RUB, en/th->THB, fallback->THB).
- Frontend helpers (`getHeaderCurrency`, `updateAllPricesToHeaderCurrency`) keep home carousel, favorites, and listing cards in sync; see `FEATURED_PROPERTIES_CURRENCY_UPDATE.md` for patch history.

### Lead Capture (`apps/users/views.py`)
- Multiple endpoints handle specific forms (property inquiry, quick consultation, contact form, office visit, FAQ question, newsletter). All return JSON and expect name/phone validation; integrate by POSTing to the appropriate `/users/...` path.
- `get_client_ip` offers standardized IP extraction for CRM logging.

### Blog & Content
- Public views under `apps/blog/views.py` (list/detail/category); templates live in `templates/blog`.
- `apps/blog/management/commands/parse_blog.py` and `docs/BLOG_PARSER.md` detail automated ingestion strategy (HTML scraping, image prioritization, YouTube embedding).
- `apps/properties/management/commands/parse_properties.py` + `docs/PROPERTY_PARSER.md` cover property ingestion from the legacy Joomla site.

---

## 6. Frontend Architecture Notes
- Tailwind utilities are in `static/css/tailwind.css`; run `npm run build-css` for watch mode or `build-css-prod` for minified output.
- Global utilities live in `static/js/main.js` (CSRF setup, hero carousel, legacy favorites binding, filter helpers). Modern listing logic resides in `static/js/list/*`; avoid duplicating code in templates.
- Home-specific bundles (`static/js/home/*.js`) expect `window.homePageData`, `window.translationStrings`, and `window.djangoUrls` to be injected via `json_script` blocks inside templates (`core/home.html`).
- Map enhancements (custom markers, rich popups, filter side sheet) are documented in `MAP_IMPROVEMENTS.md`; base implementation lives in `static/js/list/list_map_functions.js` and `list_map_data_loader.js`.
- Admin drag-and-drop uses SortableJS loaded from local static path; endpoints defined in `apps/properties/admin_urls.py` hit `update_image_order` / `bulk_upload_images`.

---

## 7. Internationalization & SEO
- `config/urls.py` wraps primary routes in `i18n_patterns` with `prefix_default_language=True`; always include language prefixes when generating links manually.
- Modeltranslation auto-creates `_ru/_en/_th` fields; registration files are under each app's `translation.py`.
- `TranslationService` requires API keys in `.env` (`GOOGLE_TRANSLATE_API_KEY`, `DEEPL_API_KEY`, `TRANSLATION_SERVICE`). Translation helpers in `apps/properties/services.py` show the expected usage pattern.
- `apps/core/context_processors.seo_context` chooses `SEOPage` data or falls back to sensible defaults; property detail pages call `Property.get_seo_data` (custom > template > auto generation).

---

## 8. Admin & Back Office Enhancements
- Sortable image grid with live order saving (see `static/admin/js/sortable_images.js`, `apps/properties/views.bulk_upload_images/update_image_order`).
- Permissions Policy middleware (`apps/core/middleware.PermissionsPolicyMiddleware`) resolves unload-event violations in modern browsers.
- Rosetta available at `/rosetta/` for translators.
- Data import dashboards routed via `data_import/urls.py` (review before exposing publicly).

---

## 9. Automation & Utilities
- Management commands of note:
  - `python manage.py parse_properties [--type villa --deal-type buy --max-pages 10 --verbose]`
  - `python manage.py parse_blog --category news --verbose`
  - `python manage.py update_exchange_rates` (ensures latest THB-based rates)
- Logs: default `django.log` (LocMem cache for DEV; production should swap to Redis/structured logging).
- Database migrations are plentiful; ensure you run `python manage.py migrate` after pulling.

---

## 10. Existing Documentation Index
Leverage these before reinventing context:
- `CLAUDE.md` - exhaustive project overview (architecture, features, deployment checklist).
- `FUNCTIONS.md` / `FUNCTIONS_RU.md` - function-level catalogue across Python & JS.
- `MAP_IMPROVEMENTS.md` - roadmap + TODOs for interactive map UX.
- `CURRENCY_FIX_SUMMARY.md`, `FEATURED_PROPERTIES_CURRENCY_UPDATE.md` - history of currency issues and resolutions.
- `CONSULTATION_FORM_UPDATE.md`, `CONSULTATION_FORM_BRANDING_UPDATE.md` - UX/content guidelines for consultation forms.
- `docs/BLOG_PARSER.md`, `docs/PROPERTY_PARSER.md`, `docs/js_refactoring_summary.md` - deep dives on specific subsystems.

Bookmark these to avoid duplicating documentation inside AGENT.md.

---

## 11. Implementation Tips & Pitfalls
1. **Currency discipline**: THB is the authoritative price. Always convert using `Property.get_price_in_currency` or `CurrencyService.convert_price`; do not derive USD/RUB manually.
2. **Language-aware URLs**: ensure `/ru/` prefix is preserved when generating URLs in JS (see `map_properties_json` for example). Failure leads to broken navigation.
3. **Favorites**: keep everything client-side; the backend intentionally rejects favorite writes. If you need persistence, design a new API instead of patching `toggle_favorite`.
4. **Inline scripts**: limit template JS to data bootstrapping. All behaviour should reside in static bundles (`docs/js_refactoring_summary.md` explains the separation).
5. **Map payload size**: `map_properties_json` caps results at 1000 objects; heavy filters should degrade gracefully. Reuse this view when expanding map features.
6. **Consultation cards**: brand guidelines demand yellow accent states (see branding doc). Keep CSS co-located inside `core/home.html` until a global design system emerges.
7. **Image uploads**: `PropertyImage.save` enforces a single `is_main`. When bulk importing, rely on `bulk_upload_images` to maintain ordering.
8. **Translation fallbacks**: many UI strings default to RU; if you add new fields, register them in the appropriate `translation.py` and consider updating `TranslationService` wrappers.
9. **Session state**: currency and favorites rely on session/localStorage. When adding new AJAX endpoints, propagate currency changes by dispatching the `currencyChanged` event so existing listeners update.
10. **Testing gap**: automated tests are scarce. When implementing risky changes, add targeted tests (or temporary scripts) and remove scaffolding before merge.

---

## 12. Quick Reference Commands
```bash
# Run server
python manage.py runserver

# Compile Tailwind (watch)
npm run build-css

# Update exchange rates
python manage.py update_exchange_rates

# Blog/property import samples
python manage.py parse_blog --category news --verbose
python manage.py parse_properties --type villa --deal-type sale --max-pages 5
```

---

## 13. Next Steps for Agents
- Start by scanning the relevant `.md` companion docs for your task area.
- Mirror existing JS module structure; avoid inline duplication.
- Respect multi-language and multi-currency requirements in every user-visible change.
- Coordinate with `TranslationService` and Rosetta when introducing new copy.
- When in doubt, review `CLAUDE.md` for the long-form description of any subsystem.

Happy shipping!
