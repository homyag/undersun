# Undersun Estate - Current Architecture Overview

## 1. Project Overview

Undersun Estate is a Django-based multilingual real estate platform for the Phuket market. The repository currently combines:

- public marketing pages,
- searchable property inventory,
- property detail pages with lead capture,
- blog/content SEO tooling,
- legacy import utilities,
- an application-level anti-bot layer.

The primary business goal of the codebase is lead generation around sale and rent inventory.

## 2. Runtime And Configuration

### Backend

- Django `5.0.6`
- Python `3.x`
- PostgreSQL in both development and production settings
- `django-environ` for environment variables

### Installed Applications

- Django core apps
- `rosetta`
- `imagekit`
- `django_filters`
- `crispy_forms`
- `crispy_tailwind`
- `tailwind`
- `tinymce`
- `modeltranslation`
- local apps under `apps.*`

### Settings Layout

- `config/settings/base.py` — shared settings, middleware, i18n, static/media, bot protection defaults
- `config/settings/development.py` — local DB, console email backend, bot protection disabled
- `config/settings/production.py` — security headers, CSP, SMTP, SSL/proxy settings

## 3. Application Structure

### `apps.core`

Responsibilities:

- home page
- about/contact/privacy/terms/service pages
- site-wide SEO context
- promotional banners and team content
- bot detection and middleware
- sitemap and legacy redirects

Key files:

- `apps/core/views.py`
- `apps/core/models.py`
- `apps/core/middleware.py`
- `apps/core/bot_detection.py`

### `apps.properties`

Responsibilities:

- property catalog and filters
- property detail page
- map/list AJAX endpoints
- favorites read API
- property admin enhancements
- Yandex real estate feed

Key files:

- `apps/properties/models.py`
- `apps/properties/views.py`
- `apps/properties/admin.py`
- `apps/properties/yml_feed.py`

### `apps.locations`

Responsibilities:

- district and location pages
- listing aggregation by geography
- statistics/median price context for district and location pages

### `apps.currency`

Responsibilities:

- currency model and exchange rates
- session currency switching
- rate API and template helpers

### `apps.users`

Responsibilities:

- form submissions
- submission notifications to admins
- property inquiries, quick consultations, office visit requests, newsletter, FAQ

### `apps.blog`

Responsibilities:

- blog list/detail/category/tag pages
- localized featured images and translated fields
- structured data helpers
- import/parsing from legacy content

### `data_import`

Responsibilities:

- Excel import dashboard
- mapping and import processing for back-office migration tasks

## 4. URL Topology

### Non-localized routes

Configured directly in `config/urls.py`:

- `/admin/`
- `/rosetta/`
- `/i18n/`
- `/currency/`
- `/tinymce/`
- `/admin-ajax/`
- `/jsi18n/`
- `/robots.txt`
- `/sitemap.xml`
- `/feeds/yandex-real-estate.xml`

### Localized routes

Wrapped in `i18n_patterns(..., prefix_default_language=True)`:

- `/ru|en|th/`
- `/ru|en|th/property/`
- `/ru|en|th/locations/`
- `/ru|en|th/users/`
- `/ru|en|th/blog/`

Legacy `/real-estate/...` paths are redirected to the current property catalog.

## 5. Data Model Highlights

### Property Domain

`apps.properties.models.Property` contains:

- property type and deal type
- district/location
- sale/rent prices in multiple currencies
- descriptive and investment fields
- coordinates and travel metrics
- contact person assignment
- SEO overrides per language

Related entities:

- `PropertyType`
- `Developer`
- `Agent`
- `PropertyImage`
- `PropertyFeature`
- `PropertyFeatureRelation`

### Content And SEO

`apps.core.models` includes:

- `SEOPage`
- `SEOContentBlock`
- `PromotionalBanner`
- `SEOTemplate`
- `Service`
- `Team`
- `RequestLog`
- `ManualIPBan`

### Blog

`apps.blog.models.BlogPost` is more than a simple article model. It includes:

- translated content fields via modeltranslation
- localized featured images
- event-specific fields
- legacy source metadata
- SEO metadata

## 6. Rendering Architecture

### Templates

The UI is server-rendered with Django templates. Large pages are split into includes:

- `templates/includes/layout/*`
- `templates/core/includes/home/*`
- `templates/properties/includes/list/*`

### JavaScript

Current client code is modularized by page area:

- `static/js/home/*`
- `static/js/list/*`
- `static/js/properties/detail.js`
- `static/js/favorites/*`
- `static/js/analytics/metrika-goals.js`
- `static/js/forms.js`

The detail page uses a split model:

- inline bootstrap data in template
- runtime behavior in `static/js/properties/detail.js`

### CSS Build

There are two CSS build pipelines in the repository:

1. Root Tailwind CLI pipeline
   - input: `static/css/tailwind.css`
   - output: `static/css/tailwind.min.css`
2. Legacy theme pipeline
   - input: `theme/static_src/src/styles.css`
   - output: `theme/static/css/dist/styles.css`

Do not assume a single Tailwind source of truth without checking the template.

## 7. Core User Flows

### Homepage

`apps.core.views.HomeView` prepares:

- featured properties by type
- structured data snippets
- districts and property type counts
- recent properties
- latest blog posts
- team and banner data

The page relies on JSON/bootstrap payloads consumed by home JS modules.

### Property Catalog

`apps.properties.views.PropertyListView`:

- filters by deal type, property type, district, location, bedrooms, amenities, text query, build status
- sorts server-side
- disables pagination in map mode
- produces filter context for the list template

Supporting endpoints:

- `property_list_ajax`
- `map_properties_json`
- `get_locations_for_district`
- `ajax_search_count`

### Property Detail

The detail page combines:

- server-rendered main content
- gallery and carousel JS
- currency-aware price rendering
- modal lead forms
- structured data
- similar properties

### Favorites

Favorites are intentionally client-side:

- IDs stored in `localStorage`
- server endpoint returns current property data for rendering favorites page
- no authenticated persistence layer exists

### Lead Capture

Forms post into `apps.users.views` and typically enforce:

- reCAPTCHA validation
- honeypot/timing validation
- JSON success/error responses
- admin notifications

## 8. Internationalization, Currency, SEO

### Languages

- default language code in settings: `ru`
- supported public languages: `ru`, `en`, `th`
- translated model fields generated by `django-modeltranslation`

### Currency

- selected currency stored in session
- language-specific defaults via `CurrencyPreference`
- conversions via `CurrencyService` and `ExchangeRate`
- frontend synchronization via `currencyChanged` custom event

### SEO

SEO comes from several layers:

- `SEOPage` for static pages
- `SEOTemplate` for dynamic property SEO
- `Property` per-language custom overrides
- `SEOContentBlock` for flexible list/detail blocks
- structured data helpers in blog and property flows

## 9. Bot Protection And Analytics

### Bot Protection

Current anti-bot architecture includes:

- `BadInquiryRequestLoggerMiddleware`
- `ForbiddenPathLoggerMiddleware`
- `BotDetectionMiddleware`
- `BotDetectionService`
- challenge cookie/token flow in base template and challenge page
- `RequestLog` persistence and `ManualIPBan`

The stack is configured in `BOT_PROTECTION` settings and is active in production, disabled in local development.

### Analytics

Yandex Metrika integration is embedded in `templates/base.html`.

The current event model uses:

- declarative `data-ym-*` attributes
- `window.dispatchMetrikaGoal(...)`
- page-specific JS modules for detailed event dispatching

## 10. Back Office And Operations

### Admin Enhancements

- sortable property image UI
- admin AJAX endpoints under `/admin-ajax/`
- Rosetta translator UI
- extensive ModelAdmin customization for properties, blog, core models

### Imports And Feeds

- property parser command
- blog parser command
- exchange rate updater
- Excel-based data import dashboard
- Yandex feed endpoint

### Infrastructure Concerns

- proxy-aware production setup
- CSP configured in production settings
- operational nginx/fail2ban docs maintained in `docs/`

## 11. Known Architectural Constraints

1. Documentation includes historical files; not all older `.md` files describe current code.
2. Frontend logic is partially modernized but still mixed with some legacy patterns.
3. There is no broad automated test suite; regression risk should be mitigated with targeted checks.
4. Favorites remain client-side by design.
5. Some data import and migration utilities are operationally useful but should not be exposed publicly without review.

## 12. Recommended Reading Order

For new contributors:

1. `docs/AGENT.md`
2. `docs/FUNCTIONS_RU.md` or `docs/FUNCTIONS.md`
3. `config/urls.py`
4. `apps/core/views.py`
5. `apps/properties/views.py`
6. `templates/core/home.html`
7. `templates/properties/detail.html`
8. `static/js/home/*`, `static/js/list/*`, `static/js/properties/detail.js`
