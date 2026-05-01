# Undersun Estate - Current Function Map

This document is an architecture-oriented reference for the current codebase. It focuses on stable entry points and important runtime modules, not every helper function.

## 1. Python Entry Points

### Core App

#### `apps/core/views.py`

- `serialize_properties_for_js(properties)`
  - serializes featured property payloads for home page JavaScript
- `HomeView`
  - builds the homepage context: featured properties, team, banner, services, recent properties, blog teasers
- `SearchView`
  - server-rendered search page using property filters
- `MapView`
  - dedicated branded map page
- `SitemapView`
  - renders sitemap XML
- legacy redirect helpers
  - redirect old paths to current routes

#### `apps/core/models.py`

- `SEOPage.get_title/get_description/get_keywords`
  - language-aware SEO fallback for static pages
- `SEOContentBlock.get_content`
  - language-aware content block retrieval
- `PromotionalBanner.get_active_banner/get_random_banner/get_language_aware_url`
  - homepage banner selection and link normalization
- `SEOTemplate.generate_seo_for_property`
  - property SEO generation from templates
- `Service.get_menu_services`
  - menu-facing service queryset
- `Team.get_homepage_team/get_all_active`
  - team selection for homepage and public sections

#### `apps/core/middleware.py`

- `LanguageRedirectMiddleware`
  - redirects `/` to a language-prefixed URL
- `LegacyRealEstateRedirectMiddleware`
  - moves legacy real-estate paths to the current catalog
- `BadInquiryRequestLoggerMiddleware`
  - blocks invalid methods on inquiry AJAX endpoints
- `ForbiddenPathLoggerMiddleware`
  - records suspicious CMS/config probing
- `BotDetectionMiddleware`
  - evaluates request score and applies allow/monitor/challenge/block decisions
- `PermissionsPolicyMiddleware`, `FrameAncestorsMiddleware`
  - response security headers for admin/CSP concerns

#### `apps/core/bot_detection.py`

- `BotDetectionService.evaluate`
  - the main scoring engine for suspicious requests
- whitelist/blacklist checks
  - IP, User-Agent, ASN, header and request-pattern heuristics

### Properties App

#### `apps/properties/models.py`

- `PropertyType.ordered_for_navigation`
  - navigation ordering for property types
- `Property.get_main_image_absolute_url`
  - absolute main image URL for feeds and structured data
- `Property.get_price_in_currency`
  - core currency-aware price accessor
- `Property.get_formatted_price`
  - formatted UI price
- `Property.get_formatted_price_per_sqm`
  - formatted price-per-sqm string
- `Property.get_seo_template`
  - best matching SEO template lookup
- `Property.get_seo_data`
  - final SEO payload for property pages

#### `apps/properties/views.py`

- `PropertyListView`
  - main catalog list view with filtering, sorting and map-mode pagination behavior
- `PropertySaleView`, `PropertyRentView`, `PropertyByTypeView`
  - specialized list variants
- `PropertyDetailView`
  - detail page renderer with similar properties and bootstrap data
- `favorites_view`, `get_favorite_properties`
  - favorites page and data endpoint
- `property_list_ajax`
  - HTML fragment endpoint for list updates
- `map_properties_json`
  - map payload endpoint
- `get_locations_for_district`
  - dependent location dropdown endpoint
- `ajax_search_count`
  - instant result count endpoint
- `bulk_upload_images`, `update_image_order`
  - admin-facing image management endpoints
- `YandexYmlFeedView`
  - public XML feed endpoint

### Currency App

#### `apps/currency/services.py`

- `CurrencyService.get_selected_currency_code`
  - session/language-based currency resolution
- `CurrencyService.get_price_field_names`
  - maps currency to model field names
- `CurrencyService.convert_price`
  - app-level currency conversion helper
- `CurrencyService.format_price`
  - generic formatting helper

#### `apps/currency/views.py`

- `ChangeCurrencyView`
  - POST endpoint that stores selected currency in session
- `ExchangeRatesView`
  - JSON rate matrix endpoint for frontend use

### Locations App

#### `apps/locations/views.py`

- `LocationListView`
  - district listing page
- `DistrictDetailView`
  - district landing page with property stats and median prices
- `LocationDetailView`
  - location landing page with property stats

### Users App

#### `apps/users/views.py`

- `property_inquiry_view`
  - handles detailed property inquiry requests
- `quick_consultation_view`
  - handles the quick phone form
- `contact_form_view`
  - general contact submissions
- `office_visit_request_view`
  - office visit form
- `faq_question_view`
  - FAQ form
- `newsletter_subscribe_view`
  - newsletter subscription endpoint

Common behavior:

- reCAPTCHA validation
- honeypot/timing security validation
- JSON response contract
- admin notifications

### Blog App

#### `apps/blog/views.py`

- `blog_list`
  - public list view
- `blog_detail`
  - public detail view
- `blog_detail_amp`
  - AMP view
- `blog_category`, `blog_tag`
  - taxonomy pages
- `legacy_blog_article_redirect`
  - redirects old article URLs

#### `apps/blog/services.py`

- `translate_blog_post`, `translate_blog_category`
  - translation helpers
- `build_blog_post_schema`
  - structured data generator for article pages
- `build_breadcrumb_schema`, `build_blog_item_list_schema`, `build_blog_search_schema`
  - SEO schema helpers

## 2. JavaScript Modules

### Global

- `static/js/forms.js`
  - generic AJAX form submission helpers and popup feedback
- `static/js/analytics/metrika-goals.js`
  - declarative and imperative Yandex Metrika event dispatch
- `static/js/main.js`
  - global legacy utilities and shared page behavior

### Homepage

- `static/js/home/featured-properties.js`
  - featured carousel rendering, consultation cards, currency synchronization
- `static/js/home/consultation.js`
  - consultation-related interactions for home page sections
- `static/js/home/hero.js`, `search-counter.js`, `featured-properties.js`, `process-steps.js`, `our-team.js`, `reviews-carousel.js`
  - section-specific homepage behavior

### Catalog

- `static/js/list/list_main_init.js`
  - filter events, auto-submit, mobile filter toggle, initialization glue
- `static/js/list/list_map_functions.js`
  - map creation, markers, clusters, popup rendering
- `static/js/list/list_map_data_loader.js`
  - map payload fetching and fallback handling
- `static/js/list/list_view_toggle.js`
  - grid/map switching with localStorage persistence
- `static/js/list/list_favorites.js`
  - catalog favorite button handling
- `static/js/list/list_utility_functions.js`
  - cross-module catalog helpers

### Property Detail

- `static/js/properties/detail.js`
  - gallery, carousel, favorites, modals, submissions, price refresh, metrika events

### Favorites

- `static/js/favorites/favorites.js`
  - favorites page rendering and currency-aware updates

## 3. Template Bootstrap Data

### `templates/base.html`

Defines and initializes:

- Yandex Metrika tracking helpers
- challenge cookie/token client logic
- hidden form token injection

### `templates/core/home.html`

Provides:

- `window.homePageData`
- translation strings
- URL constants consumed by home JS modules

### `templates/properties/detail.html`

Provides:

- `PROPERTY_*` constants
- `window.propertyDetailTranslations`
- map/detail/bootstrap payloads

## 4. Operational Commands

- `python manage.py update_exchange_rates`
- `python manage.py parse_properties ...`
- `python manage.py parse_blog ...`
- `python manage.py analyze_bad_requests ...`
- `python manage.py ban_bad_requests ...`

## 5. Notes

- This file is intentionally architecture-level, not a line-by-line dump of all helpers.
- Historical change-log documents in `docs/` may mention older implementations; prefer the current code plus this file.
