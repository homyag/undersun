# Undersun Estate - Актуальная Карта Функций

Этот документ описывает текущие ключевые entry points проекта. Он ориентирован на архитектуру и реальные runtime-модули, а не на полный перечень каждого helper-метода.

## 1. Python Entry Points

### Приложение `core`

#### `apps/core/views.py`

- `serialize_properties_for_js(properties)`
  - сериализует featured properties для JS на главной
- `HomeView`
  - собирает контекст главной: featured properties, команда, баннер, услуги, свежие объекты, блог
- `SearchView`
  - серверный search flow поверх фильтров недвижимости
- `MapView`
  - брендированная страница карты; legacy shell остаётся default, React/Vite shell включается `MAP_REBUILD_ENABLED` и по умолчанию ограничен `MAP_REBUILD_STAFF_ONLY`
  - bootstrap нового shell: язык, валюта, endpoints, OpenFreeMap style URL, фильтры и локализованные UI strings
- `SitemapView`
  - отдаёт sitemap XML
- legacy redirect helpers
  - перенаправляют старые URL в текущую структуру

#### `apps/core/models.py`

- `SEOPage.get_title/get_description/get_keywords`
  - language-aware SEO fallback для статических страниц
- `SEOContentBlock.get_content`
  - получение SEO/контентных блоков с fallback по языку
- `PromotionalBanner.get_active_banner/get_random_banner/get_language_aware_url`
  - выбор баннера и нормализация ссылки
- `SEOTemplate.generate_seo_for_property`
  - генерация SEO для карточек недвижимости
- `Service.get_menu_services`
  - выборка услуг для навигации
- `Team.get_homepage_team/get_all_active`
  - выборка команды для главной и публичных секций

#### `apps/core/middleware.py`

- `LanguageRedirectMiddleware`
  - редиректит `/` в language-prefixed URL
- `LegacyRealEstateRedirectMiddleware`
  - переводит старые `/real-estate/...` URL в текущий каталог
- `BadInquiryRequestLoggerMiddleware`
  - блокирует неверные методы на inquiry AJAX endpoints
- `ForbiddenPathLoggerMiddleware`
  - пишет в лог обращения к типичным bot/scanner path
- `BotDetectionMiddleware`
  - главный слой bot scoring и решений `allow/monitor/challenge/block`
- `PermissionsPolicyMiddleware`, `FrameAncestorsMiddleware`
  - security headers и CSP-related response logic

#### `apps/core/bot_detection.py`

- `BotDetectionService.evaluate`
  - основной scoring engine для подозрительных запросов
- whitelist/blacklist и ASN/header heuristics
  - централизованная anti-bot логика

### Приложение `properties`

#### `apps/properties/models.py`

- `PropertyType.ordered_for_navigation`
  - порядок типов недвижимости для меню и UI
- `Property.get_main_image_absolute_url`
  - абсолютный URL главного изображения для feed/SEO
- `Property.get_price_in_currency`
  - основной currency-aware accessor цены
- `Property.get_formatted_price`
  - форматированная цена для UI
- `Property.get_formatted_price_per_sqm`
  - цена за квадратный метр
- `Property.get_seo_template`
  - выбор подходящего SEO template
- `Property.get_seo_data`
  - итоговый SEO payload страницы объекта

#### `apps/properties/views.py`

- `PropertyListView`
  - основной каталог: фильтры, сортировка, map mode, pagination behavior
- `PropertySaleView`, `PropertyRentView`, `PropertyByTypeView`
  - специализированные каталожные view
- `PropertyDetailView`
  - карточка объекта и её bootstrap context
- `favorites_view`, `get_favorite_properties`
  - страница избранного и data endpoint
- `property_list_ajax`
  - HTML fragment endpoint для списка
- `map_properties_json`
  - JSON payload для карты
- `get_locations_for_district`
  - зависимый список локаций по району
- `ajax_search_count`
  - быстрый счётчик результатов
- `bulk_upload_images`, `update_image_order`
  - admin image tooling
- `YandexYmlFeedView`
  - XML feed endpoint

### Приложение `currency`

#### `apps/currency/services.py`

- `CurrencyService.get_selected_currency_code`
  - определяет валюту из session/языка
- `CurrencyService.get_price_field_names`
  - маппит валюту в соответствующие model fields
- `CurrencyService.convert_price`
  - app-level конвертация
- `CurrencyService.format_price`
  - универсальное форматирование

#### `apps/currency/views.py`

- `ChangeCurrencyView`
  - POST endpoint смены валюты
- `ExchangeRatesView`
  - JSON endpoint с матрицей курсов

### Приложение `locations`

#### `apps/locations/views.py`

- `LocationListView`
  - список районов
- `DistrictDetailView`
  - лендинг района со статистикой и медианными ценами
- `LocationDetailView`
  - лендинг локации со статистикой и объектами

### Приложение `users`

#### `apps/users/views.py`

- `property_inquiry_view`
  - заявки по конкретному объекту
- `quick_consultation_view`
  - быстрая форма телефона
- `contact_form_view`
  - общая контактная форма
- `office_visit_request_view`
  - запись в офис
- `faq_question_view`
  - форма вопроса из FAQ
- `newsletter_subscribe_view`
  - подписка на новости

Общее поведение:

- reCAPTCHA
- honeypot/timing validation
- JSON contract
- admin notifications

### Приложение `blog`

#### `apps/blog/views.py`

- `blog_list`
  - публичный список статей
- `blog_detail`
  - публичная карточка статьи
- `blog_detail_amp`
  - AMP версия статьи
- `blog_category`, `blog_tag`
  - страницы таксономий
- `legacy_blog_article_redirect`
  - редиректы со старых URL

#### `apps/blog/services.py`

- `translate_blog_post`, `translate_blog_category`
  - перевод контента блога
- `build_blog_post_schema`
  - structured data для статьи
- `build_breadcrumb_schema`, `build_blog_item_list_schema`, `build_blog_search_schema`
  - SEO schema helpers

## 2. JavaScript Modules

### Глобальный слой

- `static/js/forms.js`
  - универсальная AJAX-отправка форм и popup feedback
- `static/js/analytics/metrika-goals.js`
  - declarative/imparative integration с Яндекс.Метрикой
  - React map вызывает этот bridge через `frontend/map/src/analytics.ts`: `map_rebuild_filters_changed`, `map_rebuild_viewport_search`, `map_rebuild_property_selected`, `map_rebuild_favorite_changed`, `map_rebuild_map_error` и `map_rebuild_timing`
  - параметры событий содержат только агрегированные технические значения; не передавать ID/slug объекта, query text, координаты или PII
- `static/js/main.js`
  - legacy/shared client utilities

### Главная страница

- `static/js/home/featured-properties.js`
  - карусель featured properties, consultation cards, currency sync
- `static/js/home/consultation.js`
  - сценарии консультационных блоков
- `static/js/home/hero.js`, `search-counter.js`, `process-steps.js`, `our-team.js`, `reviews-carousel.js`
  - секционные сценарии главной

### Каталог

- `static/js/list/list_main_init.js`
  - init glue: фильтры, auto-submit, mobile toggle, базовая инициализация
- `static/js/list/list_map_functions.js`
  - карта, маркеры, кластеры, попапы
- `static/js/list/list_map_data_loader.js`
  - загрузка payload для карты
- `static/js/list/list_view_toggle.js`
  - переключение grid/map с persistence в `localStorage`
- `static/js/list/list_favorites.js`
  - кнопки избранного в каталоге
- `static/js/list/list_utility_functions.js`
  - общие утилиты каталога

### Карточка объекта

- `static/js/properties/detail.js`
  - галерея, карусель, избранное, модалки, цены, формы, метрика

### Избранное

- `static/js/favorites/favorites.js`
  - рендер и обновление страницы избранного

## 3. Template Bootstrap Data

### `templates/base.html`

Определяет:

- Yandex Metrika helpers
- challenge cookie/token client logic
- автоматическую вставку hidden token в формы

### `templates/core/home.html`

Прокидывает:

- `window.homePageData`
- translation strings
- URL constants для home modules

### `templates/properties/detail.html`

Прокидывает:

- `PROPERTY_*` constants
- `window.propertyDetailTranslations`
- detail/map/bootstrap payload

## 4. Operational Commands

- `python manage.py update_exchange_rates`
- `python manage.py benchmark_map_endpoint --requests 10` — повторяемый in-process baseline JSON endpoint карты: fixed bounds, объём ответа, p50/p95, SQL query count, количество объектов и дубли координат.
- `python manage.py parse_properties ...`
- `python manage.py parse_blog ...`
- `python manage.py analyze_bad_requests ...`
- `python manage.py ban_bad_requests ...`

## 5. Notes

- Документ intentionally high-level и архитектурный.
- Старые change-log файлы в `docs/` могут описывать прежнюю реализацию; для текущего состояния приоритет у кода и этого документа.
