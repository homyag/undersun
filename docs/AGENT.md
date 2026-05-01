# AGENT HANDBOOK - UNDERSUN ESTATE

Краткий onboarding для разработчиков и coding agents, работающих с текущей кодовой базой Undersun Estate.

## 1. Product Context

- Проект: мультиязычный сайт агентства недвижимости на Пхукете.
- Основные языки: `ru`, `en`, `th`.
- Основной сценарий: каталог объектов, карточка объекта, лидогенерация, контент-маркетинг через блог.
- Финансовая модель в коде строится вокруг THB как базовой валюты, но UI работает с `THB`, `USD`, `RUB`.

## 2. Current Stack

- Backend: `Django 5.0.6`, Python 3.x, PostgreSQL.
- Frontend: Django templates, Tailwind CSS, modular vanilla JS, частично legacy jQuery.
- Rich content: `django-tinymce`, `django-imagekit`.
- i18n: `django-modeltranslation`, `rosetta`.
- Config: `django-environ`, split settings в `config/settings/{base,development,production}.py`.

## 3. Frontend Build Reality

В проекте сейчас есть два параллельных CSS-пути:

- Основной активный путь для большинства шаблонов: root `package.json`
  - `npm run build-css`
  - `npm run build-css-prod`
  - результат: `static/css/tailwind.min.css`
- Отдельный legacy/theme pipeline:
  - `theme/static_src/package.json`
  - результат: `theme/static/css/dist/styles.css`

При изменениях сначала проверяйте, какой именно CSS-файл реально подключается в конкретном шаблоне.

## 4. Django App Map

```text
apps/
|- core        # home, static pages, SEO, banners, services, team, bot protection
|- properties  # catalog, property detail, AJAX, admin tooling, YML feed
|- locations   # districts and locations pages
|- currency    # currency models, exchange rates, session switcher
|- users       # form submissions and admin notifications
|- blog        # blog content, SEO schemas, parsing
`- data_import # legacy import dashboard and Excel tooling
```

## 5. Key Models

- `apps.properties.models.Property`
  - центральная сущность каталога
  - хранит sale/rent pricing по нескольким валютам
  - содержит SEO overrides, координаты, investment fields, contact person
- `apps.properties.models.PropertyImage`
  - управляет gallery ordering и `is_main`
- `apps.locations.models.District` / `Location`
  - двухуровневая география каталога
- `apps.currency.models.Currency` / `ExchangeRate`
  - модель валют и истории курсов
- `apps.core.models.SEOPage`, `SEOTemplate`, `SEOContentBlock`
  - SEO для статических и динамических страниц
- `apps.core.models.PromotionalBanner`, `Service`, `Team`
  - контент главной и сервисных страниц
- `apps.users.models.*`
  - все лид-формы проекта
- `apps.core.models.RequestLog`, `ManualIPBan`
  - anti-bot и operational audit layer

## 6. Main User Flows

### Homepage

- View: `apps.core.views.HomeView`
- Template: `templates/core/home.html`
- Клиентская логика: `static/js/home/*.js`
- На главной собираются featured properties, services, team, blog teasers, промобаннер и формы.

### Catalog

- View: `apps.properties.views.PropertyListView`
- Template root: `templates/properties/list.html`
- Includes: `templates/properties/includes/list/*`
- JS: `static/js/list/*`
- Поддерживаются grid/map view, фильтры, debounce submit, AJAX map payload, client-side favorites.

### Property Detail

- View: `apps.properties.views.PropertyDetailView`
- Template: `templates/properties/detail.html`
- Main JS: `static/js/properties/detail.js`
- Inline JS оставлен только для bootstrap-данных и некоторых инициализаций.

### Leads And Forms

- Endpoints: `apps.users.views`
- Все основные формы отдают JSON.
- Защита: reCAPTCHA, honeypot, минимальная задержка заполнения.

### Blog

- Views: `apps.blog.views`
- Models/services: `apps.blog.models`, `apps.blog.services`
- Есть парсинг legacy-контента и schema generation для SEO.

## 7. URL Structure

- Глобальные маршруты: `config/urls.py`
- Основные публичные роуты находятся внутри `i18n_patterns`, язык в URL обязателен.
- Вне `i18n_patterns` вынесены:
  - `/admin/`
  - `/rosetta/`
  - `/currency/`
  - `/tinymce/`
  - `/admin-ajax/`
  - `/jsi18n/`
  - `/sitemap.xml`
  - `/feeds/yandex-real-estate.xml`

## 8. Cross-Cutting Concerns

### Currency

- Выбор валюты хранится в `session`.
- Переключение идёт через `apps.currency.views.ChangeCurrencyView`.
- На фронте используется событие `currencyChanged`.

### Favorites

- Persistence клиентская, через `localStorage`.
- Backend only reads favorites for rendering current property data.
- `toggle_favorite` намеренно не используется для серверного сохранения.

### SEO

- Static pages: `SEOPage`
- Dynamic property SEO: `SEOTemplate` + property overrides
- Additional SEO blocks: `SEOContentBlock`

### Bot Protection

- Middleware stack: `apps.core.middleware`
- Scoring engine: `apps.core.bot_detection.BotDetectionService`
- Challenge cookie/token выставляется в `templates/base.html` и challenge page.
- `RequestLog` фиксирует решения `allow/monitor/challenge/block`.

### Analytics

- Base layer: `templates/base.html`
- Goal dispatcher: `static/js/analytics/metrika-goals.js`
- Page-specific events: home/list/detail modules

## 9. Important Implementation Notes

1. Не опирайтесь на старые change-log документы как на описание текущего кода.
2. Перед изменениями во фронтенде проверяйте, где живёт логика: в шаблоне, `static/js`, либо в обоих местах.
3. Перед изменениями валют всегда учитывайте `CurrencyService` и `Property.get_price_in_currency`.
4. Любые новые формы должны использовать существующую bot/form security схему.
5. Любые новые CTA желательно сразу покрывать `data-ym-goal` или `dispatchMetrikaGoal`.

## 10. Useful Commands

```bash
python manage.py runserver
python manage.py migrate
python manage.py update_exchange_rates
python manage.py parse_properties --type villa --deal-type sale --max-pages 5
python manage.py parse_blog --category news --languages ru,en,th
npm run build-css
```

## 11. Documentation Priority

Если документация расходится с кодом:

1. Код
2. `AGENT.md`
3. `ARCHITECTURE.md`
4. `FUNCTIONS_RU.md` / `FUNCTIONS.md`
5. Исторические change-log документы
