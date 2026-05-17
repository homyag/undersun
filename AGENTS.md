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
- Forms/UI helpers: `django-crispy-forms`, `crispy-tailwind`, `django-filter`.
- i18n: `django-modeltranslation`, `rosetta`.
- Config: `django-environ`, settings split в `config/settings/{base,development,production}.py`.

## 3. Frontend Build Reality

В проекте сейчас есть два Tailwind/CSS pipeline, но runtime-подключение определяется шаблоном.

- Активный путь для базового layout при `TAILWIND_USE_CDN = False`:
  - source: `theme/static_src/package.json`
  - command: из `theme/static_src` запускать `npm run dev` или `npm run build`
  - результат: `theme/static/css/dist/styles.css`
  - подключается в `templates/base.html` как `{% static 'css/dist/styles.css' %}`
- CDN fallback:
  - если `tailwind_use_cdn` true, `templates/base.html` подключает `https://cdn.tailwindcss.com`
- Root Tailwind CLI pipeline:
  - source: root `package.json`
  - commands: `npm run build-css`, `npm run build-css-prod`
  - результат: `static/css/tailwind.min.css`
  - сейчас не подключается в `templates/base.html`; используйте только если конкретный шаблон явно ссылается на этот файл.

Перед изменениями CSS всегда проверяйте, какой файл реально подключается в нужном шаблоне.

## 4. Django App Map

```text
apps/
|- core        # home, static pages, SEO, banners, services, team, bot protection
|- properties  # catalog, property detail, AJAX, admin tooling, YML feed
|- locations   # districts and locations pages
|- currency    # currency models, exchange rates, session switcher
|- users       # form submissions and admin notifications
`- blog        # blog content, SEO schemas, parsing

data_import/   # legacy import dashboard/Excel tooling; currently not in INSTALLED_APPS
```

## 5. Key Models

- `apps.properties.models.Property`
  - центральная сущность каталога
  - хранит sale/rent pricing по нескольким валютам
  - содержит SEO overrides, координаты, investment fields, contact person
- `apps.properties.models.PropertyType`, `Developer`, `Agent`, `PropertyFeature`
  - справочники, связанные с каталогом, навигацией, импортом и карточками объектов
- `apps.properties.models.PropertyImage`
  - управляет gallery ordering и `is_main`
- `apps.locations.models.District` / `Location`
  - двухуровневая география каталога
- `apps.currency.models.Currency`, `ExchangeRate`, `CurrencyPreference`
  - валюты, история курсов и валюты по умолчанию для языков
- `apps.core.models.SEOPage`, `SEOTemplate`, `SEOContentBlock`
  - SEO для статических и динамических страниц
- `apps.core.models.PromotionalBanner`, `Service`, `Team`
  - контент главной, сервисных страниц и навигации
- `apps.users.models.*`
  - все лид-формы проекта
- `apps.core.models.RequestLog`, `ManualIPBan`
  - anti-bot и operational audit layer

## 6. Main User Flows

### Homepage

- View: `apps.core.views.HomeView`
- Template: `templates/core/home.html`
- Includes: `templates/core/includes/home/*`, `templates/includes/home/*`
- Client logic: `static/js/home/*.js`
- На главной собираются featured properties, services, team, blog teasers, промобаннер и формы.

### Catalog

- View: `apps.properties.views.PropertyListView`
- Template root: `templates/properties/list.html`
- Includes: `templates/properties/includes/list/*`, `templates/includes/list/*`
- JS: `static/js/list/*`
- Поддерживаются grid/map view, фильтры, debounce submit, AJAX map payload, client-side favorites.

### Property Detail

- View: `apps.properties.views.PropertyDetailView`
- Template: `templates/properties/detail.html`
- Bootstrap data: `templates/properties/includes/detail_bootstrap.js.html`
- Main JS: `static/js/properties/detail.js`
- Inline JS оставлен для bootstrap-данных и минимальной инициализации, основная логика живёт в static JS.

### Leads And Forms

- Endpoints: `apps.users.views`
- Все основные формы отдают JSON.
- Защита: reCAPTCHA, honeypot, минимальная задержка заполнения через `validate_form_security`.
- После записи формы отправляют admin notifications через `apps.users.notifications`.

### Blog

- Views: function-based views в `apps.blog.views`
- Models/services: `apps.blog.models`, `apps.blog.services`
- Есть парсинг legacy-контента, AMP detail page и schema generation для SEO.

## 7. URL Structure

- Глобальные маршруты: `config/urls.py`
- Основные публичные роуты находятся внутри `i18n_patterns(..., prefix_default_language=True)`, язык в URL обязателен.
- Внутри localized routes:
  - `/ru|en|th/`
  - `/ru|en|th/property/`
  - `/ru|en|th/locations/`
  - `/ru|en|th/users/`
  - `/ru|en|th/blog/`
- Вне `i18n_patterns` вынесены:
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
- Legacy `/real-estate/...` обрабатывается redirect middleware/view.

## 8. Cross-Cutting Concerns

### Currency

- Выбор валюты хранится в `session`.
- Если в session валюты нет, default берётся из `CurrencyPreference` по текущему языку.
- Переключение идёт через `apps.currency.views.ChangeCurrencyView`.
- На фронте используется событие `currencyChanged`.

### Favorites

- Persistence клиентская, через `localStorage`.
- Backend принимает список ID и отдаёт актуальные данные объектов для страницы избранного.
- `toggle_favorite` намеренно не используется для серверного сохранения.

### SEO

- Static pages: `SEOPage`
- Dynamic property SEO: `SEOTemplate` + property overrides
- Additional SEO blocks: `SEOContentBlock`
- Blog/list/detail pages добавляют structured data через services/context helpers.

### Bot Protection

- Middleware stack: `apps.core.middleware`
- Scoring engine: `apps.core.bot_detection.BotDetectionService`
- Challenge cookie/token выставляется в `templates/base.html` и challenge page.
- `RequestLog` фиксирует решения `allow/monitor/challenge/block`.
- В `development.py` bot protection отключена через `BOT_PROTECTION['ENABLED'] = False`.

### Analytics

- Base layer: `templates/base.html`
- Goal dispatcher: `static/js/analytics/metrika-goals.js`
- Page-specific events: home/list/detail/map modules

## 9. Important Implementation Notes

1. Не опирайтесь на старые change-log документы как на описание текущего кода.
2. Перед изменениями во фронтенде проверяйте, где живёт логика: в шаблоне, `static/js`, либо в обоих местах.
3. Перед изменениями валют всегда учитывайте `CurrencyService` и `Property.get_price_in_currency`.
4. Любые новые формы должны использовать существующую bot/form security схему.
5. Любые новые CTA желательно сразу покрывать `data-ym-goal` или `dispatchMetrikaGoal`.
6. Для страницы объекта не возвращайте крупные inline-скрипты в шаблон: расширяйте bootstrap include только данными, а поведение держите в `static/js/properties/detail.js`.

## 10. Useful Commands

```bash
python manage.py runserver
python manage.py migrate
python manage.py setup_currencies
python manage.py update_exchange_rates
python manage.py generate_property_seo_landings
python manage.py parse_properties --type villa --deal-type buy --max-pages 5
python manage.py parse_blog --category news --languages ru,en,th
python manage.py analyze_bad_requests
python manage.py ban_bad_requests

# CSS used by templates/base.html when TAILWIND_USE_CDN = False
cd theme/static_src
npm run dev
npm run build
```

## 11. Documentation Priority

Если документация расходится с кодом:

1. Код
2. `AGENTS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/FUNCTIONS_RU.md` / `docs/FUNCTIONS.md`
5. Исторические change-log документы
