# План переработки страницы карты `/map/`

**Статус:** active, internal staff rollout  
**Дата:** 2026-07-10  
**Последняя актуализация:** 2026-07-11  
**Область:** публичная мультиязычная страница `/ru|en|th/map/`. Каталоговый режим карты `/property/?map_view=true` использует общее ядро и API, но его визуальная переделка является отдельной задачей.

## 1. Цель и продуктовый ориентир

Сделать `/map/` основным рабочим инструментом поиска недвижимости по карте: пользователь открывает карту сразу, быстро ограничивает выдачу, перемещается по острову, получает только объекты в видимой области и открывает короткую карточку без перезагрузки страницы.

Ориентиры по паттернам, а не копирование дизайна:

- **FazWaz:** map-first поиск, синхронизация карты и результатов, фильтры без разрыва сценария, карточка результата как следующий шаг к detail.
- **ГдеБЕНЗ:** карта как первый экран, компактные и понятные controls, геолокация, реакция интерфейса на viewport и touch-first mobile flow.

Не переносим нерелевантные функции: пользовательские отметки, маршрутизацию, игровую механику, тяжёлые heatmap-слои и декоративный hero.

## 2. Текущее состояние и проблемные места

Подтверждено по коду на 2026-07-10:

- маршрут и view: `apps/core/urls.py`, `apps/core/views.py:MapView`;
- шаблон: `templates/core/map.html` (около 1 700 строк, включая крупный inline CSS и inline JS);
- карта: MapLibre GL JS 5.6.2 из CDN, общее ядро `static/js/map/map_core.js`, orchestration `static/js/map/map_page.js`, popup builder `static/js/map/map_popups.js`;
- данные: `apps.properties.views.map_properties_json`, уже есть query по bounds, debounce на `moveend`, буфер bounds и лимит `1000`;
- фильтры рендерятся существующим `list_filters_card.html`, но `map_page.js` вызывает `form.submit()`, то есть меняет страницу и восстанавливает scroll вместо обновления карты in-place;
- endpoint формирует цену в USD и русскую строку `"Цена по запросу"`, хотя UI поддерживает `ru`, `en`, `th` и currency switcher;
- маркеры, hover-popup, spread одинаковых координат, избранное, Мetrika и district overlay уже реализованы в общем map core.

Главный вывод: MapLibre остаётся целесообразным движком, но интерактивный интерфейс карты не должен оставаться в крупном Django template и наборе глобальных vanilla-скриптов. Нужны самостоятельное map application, строгий API-контракт, запросы без перезагрузки и интеграция с Django как с backend/BFF.

## 3. Выбор стека и способ внедрения

### Рекомендованный стек

- **Backend/BFF:** текущий Django + PostgreSQL. Django остаётся владельцем моделей, фильтров, i18n, выбранной валюты, прав доступа, SEO, Metrika bootstrap и публичных URL.
- **Map application:** React 19 + TypeScript + Vite, собираемые в отдельный `frontend/map/` workspace.
- **Карта:** MapLibre GL JS; DOM/UI управляется React, а не вручную из MapLibre callbacks.
- **Server state:** TanStack Query для cancellation, caching, retry и stale responses.
- **UI state:** локальный React state/reducer; Zustand добавлять только если state начнёт пересекать несвязанные subtree. Не добавлять Redux.
- **Стили:** CSS Modules или scoped CSS variables. Не подключать третий Tailwind pipeline: существующий проект уже имеет два CSS pipeline.
- **Тесты:** Vitest + Testing Library для state/components; Playwright для реального MapLibre, touch и viewport сценариев.

React оправдан здесь не как «новая технология», а потому что карта имеет синхронные состояния filters/URL/viewport/results/selection/sheets и требует предсказуемого lifecycle. Оставлять это в одном 1 788-строчном map core и template рискованнее, чем изолировать интерактивное приложение.

### Почему не делать отдельный сайт или полный SPA

- Не выносить `/map/` в другой домен/репозиторий: потеряются единые language-prefixed URL, cookies/session currency, CSP, analytics, обратные ссылки и простой rollback.
- Не переводить весь Django сайт на React/Next.js: задача касается одной сложной surface, а каталогу, detail и SEO-контенту выгоден текущий SSR.
- Не продолжать развивать map UI в Django templates + глобальном vanilla JS: это минимальная миграция сегодня, но не устраняет сложность state/desktop-mobile variants и даёт слабую тестируемость.

### Интеграционный контракт

1. Django продолжает отвечать на `/ru|en|th/map/` server-rendered shell с title, canonical/hreflang, JSON-LD, global header/footer и fallback message.
2. Template помещает один mount node `<div id="property-map-app">` и безопасный JSON bootstrap (`language`, translations, selected currency, endpoints, CSRF when needed, feature flags). Никакой бизнес-логики карты inline.
3. Vite production build пишет hashed assets и `manifest.json` в Django static directory. Нужен небольшой Django template tag, который по manifest подключает ровно map entry CSS/JS с `defer`.
4. В development Vite dev server обслуживает только map entry через разрешённый origin; production никогда не зависит от dev server/CDN bundle.
5. Django JSON endpoint остаётся same-origin. React не читает модели, session или currency напрямую: он получает только явный API/bootstrapped contract.
6. На feature flag Django выбирает legacy shell либо новый mount node. Это делает canary и rollback серверным переключением без миграции данных.

### Порядок миграции

1. Сначала стабилизировать API contract и написать adapter, который позволяет legacy map core временно читать новый payload.
2. Создать React app с пустым shell и подключить его к локальному/production manifest без изменения public URL.
3. Перенести в него в порядке: query state -> filter panel -> map viewport -> result card -> mobile sheets -> analytics.
4. Сравнить новый и legacy flow за feature flag. Удалять `static/js/map/map_page.js`, `map_popups.js` и page-specific CSS только после полного rollout.

## 4. Целевое UX-поведение

### Desktop (>= 1024px)

- Первый экран: карта на всю доступную высоту под глобальным header; без hero перед рабочей областью.
- Слева основной прокручиваемый список карточек текущей выдачи. Фильтры открываются поверх списка в drawer и не занимают вторую постоянную колонку; состояние drawer сохраняется в `localStorage`.
- Над картой компактная строка: поиск района/локации, `Искать в этой области`, счётчик, переключатель слоя, reset view. Кнопка поиска появляется только когда пользователь изменил viewport после последнего запроса.
- При click маркера открывается MapLibre popup над выбранным пином с автоматическим безопасным позиционированием внутри карты. Карточка даёт фото, цену в текущей валюте, тип, район, 3 характеристики, WhatsApp и переход к detail; favourite намеренно исключён из popup.
- Click по карточке списка центрирует карту и открывает popup; click по пину выделяет и прокручивает соответствующую карточку. Список рендерится порциями, чтобы не создавать весь DOM выдачи сразу.
- Поиск после debounce синхронизирует filters и selected property через `history.replaceState`; обновлённая ссылка открывает тот же набор фильтров. Viewport остаётся runtime-state текущего mount и не публикуется в URL.

### Mobile (< 1024px)

- Карта занимает viewport под header; никаких боковых колонок и hero.
- Верхняя строка содержит только поисковый запрос, кнопку фильтра, счётчик и геолокацию; touch target не меньше 44x44 px.
- Фильтры открываются в bottom sheet с fixed footer: `Показать N объектов` и reset. Изменения применяются без page reload; sheet закрывается только по явному действию пользователя.
- Tap по маркеру открывает bottom sheet карточки объекта, а не узкий MapLibre popup. Для нескольких объектов в одной координате сначала показывается доступный список выбора; favourite намеренно исключён из sheet и popup.
- Hover не используется. При keyboard navigation все controls и карточка доступны с корректными focus states и labels.

### Состояния

- Initial loading: карта и панель получают skeleton, базовая карта отображается до результатов.
- Pending viewport: ненавязчивый floating CTA `Искать в этой области`, без блокировки карты.
- Loading results: счётчик/CTA показывают прогресс, старые маркеры остаются до ответа; запрос можно отменить.
- Empty: в панели показываются причина, reset и переход к каталогу; карта остаётся интерактивной.
- Error/offline: не удалять прошлые результаты, дать `Повторить` и логировать техническую ошибку без вывода stack trace пользователю.

## 5. Архитектура и контракты

### 5.1. Разделение ответственности

| Слой | Ответственность | Целевое место |
| --- | --- | --- |
| Django template | SSR shell, SEO, global layout, bootstrap config, Vite asset tag | `templates/core/map.html` + `templates/core/includes/map/` |
| React UI | filter panel/sheets, toolbar, cards, empty/error/loading, accessibility | `frontend/map/src/components/` |
| Map integration | MapLibre lifecycle, sources/layers, marker/cluster strategy, viewport/selection | `frontend/map/src/map/` |
| state + requests | URL state, TanStack Query, debounce, abort, state machine, DOM rendering | `frontend/map/src/features/search/` |
| cards | typed property presentation and analytics event hooks | `frontend/map/src/map/` |
| data API | фильтры, bounds, counts, currency/localization, performance limit | `apps/properties/views.py` или выделенный map service/serializer |

Не дублировать карту в Django template и не смешивать map app с list-specific selectors. Общий backend contract допускает отдельный legacy adapter для каталожной карты, но не требует подключать React туда в первой итерации.

### 5.2. API `GET /<lang>/property/ajax/map/`

Сохранить существующие фильтры `PropertyListView.apply_filters`, но определить версионированный/документированный ответ:

```json
{
  "success": true,
  "request_id": "uuid",
  "results": {
    "visible_count": 48,
    "total_count": 326,
    "truncated": false,
    "next_action": "none"
  },
  "viewport": {"north": 8.1, "south": 7.7, "east": 98.6, "west": 98.1},
  "properties": [{
    "id": 123,
    "coordinates": [98.31, 7.88],
    "url": "/en/property/example/",
    "title": "...",
    "type": {"key": "villa", "label": "Villa"},
    "deal_type": "sale",
    "price": {"amount": 12000000, "currency": "THB", "formatted": "THB 12,000,000", "period": null},
    "location": {"district": "Bang Tao", "location": "..."},
    "image": {"thumbnail_url": "...", "alt": "..."},
    "facts": {"bedrooms": 3, "bathrooms": 3, "area_sqm": 250}
  }]
}
```

Правила API:

- валидировать координаты на уровне queryset (`latitude/longitude__isnull=False`) и не использовать truthiness, чтобы не потерять допустимые нулевые значения;
- цену и `formatted` получать через существующий currency service/property API для выбранной currency и языка; все fallback labels переводить сервером;
- `total_count` означает все результаты фильтра, `visible_count` - отправленные объекты внутри viewport; сообщать `truncated`, а не молча обрезать ответ;
- возвращать только поля карты, главное изображение получать без N+1 (`Prefetch` с одним `is_main` или annotated image);
- принять bounds, zoom и client request id; ограничить допустимый bbox/zoom и rate-limit/кэшировать идентичные запросы;
- для далёкого zoom возвращать агрегированные buckets/clusters, для близкого - отдельные объекты. Не отправлять 1000 DOM-маркеров на mobile.

Переходный контракт, реализованный до новой map app: legacy-клиент не передаёт `map_mode` и получает `mode: "properties"` с прежним flat `properties`. Новый клиент передаёт `map_mode=auto`; при `zoom <= 10` API возвращает `mode: "aggregates"`, пустой `properties` и `aggregates: [{id, lat, lng, count}]`. Порог `10` и grid `80px` provisional до S0-07; в ответе также возвращается `aggregate_max_zoom`. Explicit `map_mode=properties|aggregates` доступен для controlled rollout и contract tests.

### 5.3. State, URL и запросы

- URL-backed `MapSearchState` владеет filters и `selectedPropertyId`; pending/applied viewport и runtime currency являются отдельным React state с явными переходами.
- `filters` и выбранный объект сериализуются в URL; viewport не публикуется и живёт только в текущей map session, чтобы share links оставались короткими и предсказуемыми.
- Использовать `AbortController` и sequence id: поздний ответ никогда не перезаписывает актуальное состояние.
- Debounce: text/price 350-500 ms, viewport не запрашивается автоматически до нажатия `Искать в этой области`; initial load и явное применение фильтров запрашиваются сразу.
- Кэшировать успешные ответы в memory LRU по `{filters,bounds,zoom,currency,language}` с коротким TTL. Не класть каталог и персональные фильтры в persistent localStorage.
- `currencyChanged` должен обновлять текущий map query и все price labels, не сбрасывая viewport и выбранный объект. Bootstrap currency нельзя считать изменяемым runtime-state; client cache обязан различать валюты или инвалидироваться при событии.

## 6. План реализации

### Фаза 0. Discovery и baseline

1. Зафиксировать production-like объём: всего активных объектов с координатами, p50/p95 объектов на viewport, доля одинаковых координат, средний JSON payload.
2. Снять Web Vitals и custom timings на desktop/mobile: map shell visible, MapLibre loaded, first markers, filter response, marker tap to card.
3. Проверить tile-provider SLA, attribution, CSP и лимиты. Векторный basemap включать только после отдельного сравнения качества/стоимости; raster OSM не считать бесконечно масштабируемым production решением.
4. Согласовать с бизнесом обязательные фильтры, порядок сортировки/приоритизации и поведение объектов с приблизительными координатами.

**Результат:** измеримый baseline и UX spec; без feature work.

### Фаза 1. API и data layer

1. Вынести map serialization из view в service/serializer с тестами для `ru/en/th`, `THB/USD/RUB`, sale/rent/both, отсутствующей цены/картинки/агента.
2. Устранить N+1 на images и добавить DB indexes/`EXPLAIN ANALYZE` для `is_active,status,latitude,longitude` и частых фильтров.
3. Добавить response metadata: total/visible/truncated, request id, applied viewport, server timing.
4. Ввести zoom-aware strategy: aggregate on far zoom, property points on close zoom. Сохранить deterministic spread только для близких координат на property zoom.
5. Кэшировать короткоживущие публичные responses с ключом языка, currency, filters, bounds and zoom; не кэшировать ошибки.

**Acceptance:** корректная локализация/валюта; отсутствие N+1; documented hard limit без скрытой потери объектов; p95 API при целевом viewport <= 500 ms в production baseline.

### Фаза 2. Frontend foundation и Django integration

1. Добавить изолированный Vite + React + TypeScript workspace, lockfile, scripts, production manifest output и development proxy/allowed origin.
2. Реализовать Django `vite_asset` template tag, production manifest lookup, понятный error при отсутствующем build и CSP-compatible script/style tags.
3. Заменить hero + ниже расположенную карту на SSR map shell с одним mount node; оставить inline только JSON bootstrap config/i18n data.
4. Реализовать React application frame: desktop results panel + filter drawer, mobile bottom sheet, toolbar, reduced-motion styles, focus management, scroll lock и safe-area insets.
5. Сохранить title/meta/schema, language-prefixed links, global header/footer, currency/analytics contracts.

**Acceptance:** production build подключается Django через hashed manifest; no runtime dependency on Vite dev server; карта видна на первом viewport 320-1440 px; текст/controls не перекрываются; filter flow работает keyboard/touch; no layout shift после старта карты.

### Фаза 3. In-place filtering и viewport search

1. Заменить `form.submit()` в `/map/` на typed React state + TanStack Query; не менять поведение того же Django include на странице каталога без явного adapter.
2. Добавить active chips, clear one/clear all, live count, disabled/applying states и `Искать в этой области`.
3. Поддержать browser back/forward (`popstate`) и shareable filtered URL; viewport оставить runtime-state, пока отдельная UX-проверка не подтвердит необходимость restore.
4. Добавить `AbortController`, request sequencing, LRU cache, empty/error/retry states.
5. Не делать automatic fetch на каждом `moveend`; карта остаётся плавной, пользователь подтверждает новый поиск CTA. Геолокация получает отдельное permission/error UX.

**Acceptance:** фильтр не делает full page load; stale responses не меняют результаты; back/forward восстанавливает фильтры; pan/zoom остаётся отзывчивым на среднем Android устройстве.

### Фаза 4. Результаты и карта

1. Сделать два render modes в map core: aggregate clusters at far zoom, individual markers at property zoom. Не показывать одновременно конфликтующие cluster/spiderfy/spread паттерны.
2. Оставить type visual language и улучшить иерархию маркеров: aggregate, default и selected. Marker size не должен менять layout controls.
3. Desktop: click pin открывает popup над ним; close очищает selected. Mobile: bottom result card, tap/close, selected marker remains visible.
4. Добавить синхронизированный компактный список видимых объектов на desktop как основной левый panel; mobile list mode вынести в S7-01. Рендерить список порциями.
5. Подключить neighbourhood overlay только с настоящими polygon boundaries и понятным источником данных. До этого не делать synthetic padded polygons источником навигационных решений.

**Acceptance:** no marker overlap that hides selected property; detail/contact work; popup/card does not escape viewport; all image URLs lazy loaded; map supports touch and keyboard.

### Фаза 5. Observability, analytics и rollout

1. Добавить events: `map_view_loaded`, `map_filter_applied`, `map_search_area_clicked`, `map_marker_opened`, `map_card_detail_clicked`, `map_geolocation_*`, `map_empty_shown`, `map_api_error`. Не отправлять events на hover/move.
2. Передавать language, currency, filter count, zoom bucket, visible count, request latency bucket; исключить PII и точные пользовательские coordinates.
3. Выпустить за feature flag: internal -> 10% production -> 50% -> 100%, со сравнением baseline metrics и error rate. Сохранить возможность мгновенно переключиться на текущий UI.
4. После rollout удалить неиспользуемый hero CSS, legacy page-only handlers и устаревшие map config paths отдельным cleanup PR.

**Acceptance:** dashboard покрывает воронку и технические ошибки; rollback не требует миграции данных; no regression в текущих `catalog_map_*` целях.

## 7. Спринты и декомпозиция

Каждый спринт завершается работающим инкрементом, review и демонстрацией на `ru`, `en`, `th`. Оценка ниже предполагает команду из backend и frontend разработчика; задачи одного пункта не обязательно исполняются одним человеком. Длительность спринта определить после baseline, ориентир - одна-две недели.

### Спринт 0. Baseline и решения

**Цель:** согласовать продуктовые границы и измерить нынешнюю карту до начала миграции.

| ID | Задача | Зависимость |
| --- | --- | --- |
| S0-01 | Подготовить production-like локальную БД из актуального production dump. Предпочтительно использовать отдельную `undersunestate_map_benchmark`; для текущего запуска утверждено обновление `undersunestate_db` после локального rollback dump. Не использовать эту копию вне защищённого local environment; перед передачей третьим лицам исключить/обезличить лиды, пользователей, request logs и другие персональные данные. | Доступ к production backup/дампу |
| S0-02 | Проверить restore: миграции, справочники, currency rates, активные объекты, координаты и доступность image URLs/fixtures, нужных для карты. | S0-01 |
| S0-03 | Снять текущие объёмы: активные объекты, объекты с координатами, p50/p95 результатов в viewport, дубли координат и размер payload. | S0-02 |
| S0-04 | Записать baseline RUM/Lighthouse: map shell, first markers, filter response, interaction FPS и JS errors на desktop/mobile. | S0-03 |
| S0-05 | Проверить лицензии, attribution, rate limits, CSP и стоимость текущего/fallback tile provider. | - |
| S0-06 | Провести UX review текущей `/map/` и зафиксировать обязательные фильтры, mobile flow, допустимое поведение approximate coordinates. | - |
| S0-07 | Утвердить API schema, zoom thresholds и budgets из разделов 5 и 8 документа. | S0-03, S0-04, S0-05, S0-06 |
| S0-08 | Создать feature flag `map_rebuild_enabled` и release checklist, не меняя default UI. | S0-07 |

**Готово, когда:** baseline сохранён в проектной документации/дашборде, критерии MVP утверждены, legacy `/map/` остаётся default и flag проверен локально.

#### Фактический статус Sprint 0 на 2026-07-10

- [x] С production создан PostgreSQL custom-format dump `undersundb_map_benchmark_20260710_151932.dump` размером 16 MB.
- [x] Dump проверен на production через `pg_restore --list`; SHA-256 проверен повторно после защищённой передачи на локальный компьютер.
- [x] Перед заменой создан и проверен локальный rollback dump прежней development БД: `undersunestate_db_pre_map_restore_20260710_113511.dump`.
- [x] `undersunestate_db` пересоздана локально и восстановлена из актуального production dump. Это утверждённое исключение из предпочтительной схемы с отдельной `undersunestate_map_benchmark`.
- [x] `python manage.py check` завершён без ошибок.
- [x] В восстановленной базе: `519` активных объектов со статусом `available` и координатами.
- [x] Проверен `/ru/property/ajax/map/` на реальном bounds: HTTP `200`, `success=true`, `518` объектов в ответе.
- [x] Добавлена воспроизводимая команда `python manage.py benchmark_map_endpoint --requests 10`. Она измеряет map endpoint на четырёх fixed bounds, JSON size, p50/p95 и дубли координат.
- [x] Baseline `2026-07-10`, 10 in-process запросов на bounds: 

  | Bounds | Объекты | JSON | p50 | p95 |
  | --- | ---: | ---: | ---: | ---: |
  | Island | 518 | 505,969 B | 717.66 ms | 806.60 ms |
  | West coast | 515 | 502,694 B | 709.39 ms | 744.80 ms |
  | South | 173 | 162,547 B | 252.24 ms | 316.18 ms |
  | North | 332 | 330,954 B | 483.37 ms | 504.98 ms |

  Дубли координат: `0` групп, `0` объектов в таких группах. Этот замер не включает сеть, browser rendering, gzip и tiles, поэтому не заменяет RUM/Lighthouse. Он уже показывает, что island/west-coast payload превышает целевой budget `250 KB`, а p95 island/west-coast превышает целевой `500 ms`.
- [x] SQL query-count baseline, 5 запросов на bounds: island `522` запроса для `518` объектов, west coast `519` для `515`, south `177` для `173`, north `336` для `332`. Это подтверждённый N+1: endpoint prefetches `images`, но затем повторно вызывает `prop.images.filter(...)` для каждого объекта. Исправление входит в `S1-03`.
- [x] `EXPLAIN (ANALYZE, BUFFERS)` для island property query: `Execution Time: 5.027 ms`, `518` rows, `shared hit=198`. Planner выбрал Seq Scan по `properties_property` (`610` строк, `92` отфильтрованы); на текущем объёме он корректен и не является backend bottleneck. Повторно оценить bounds indexes после роста каталога или перехода на более узкие queries.
- [x] Аудит tile/CDN/CSP: legacy map использует `https://tile.openstreetmap.org/{z}/{x}/{y}.png` и MapLibre 5.6.2 из `unpkg.com`; текущий production CSP допускает оба источника и `worker-src blob:`. Политика OSM разрешает обычный интерактивный просмотр, но сервис best-effort без SLA и допускает блокировку при вредной/тяжёлой нагрузке. Поэтому Standard OSM остаётся legacy/fallback basemap, но не является единственным production provider для новой map app. См. [OSMF Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/) и [MapLibre documentation](https://maplibre.org/maplibre-gl-js/docs/).
- [x] Решение `2026-07-10`: OpenFreeMap Liberty (`https://tiles.openfreemap.org/styles/liberty`) выбран для dev и production. `currentBasemap` переключён на `style-url`; `tiles.openfreemap.org` добавлен в production `CONNECT_SRC` и `img-src`. OpenFreeMap публикует официальный MapLibre quick start для этого style URL, но предоставляет сервис as-is и может прекратить его без предупреждения. Новая map app должна иметь аварийный fallback basemap, telemetry ошибок style/tile loading и runbook переключения provider. См. [OpenFreeMap Quick Start](https://openfreemap.org/quick_start/) и [Terms of Service](https://openfreemap.org/tos/).
- [x] Local HTTP baseline через Django development server, 5 warm запросов: `/ru/map/` - 229,677 B, p50 TTFB `650.87 ms`, max `713.27 ms`; island JSON endpoint - 505,969 B, p50 TTFB `738.74 ms`, max `751.81 ms`. Первый cold запрос страницы занял `3.69 s`. Development server не отправляет `Content-Encoding`, поэтому это несжатый application baseline, а не production HTTP/gzip metric.
- [x] Initial UX review через headless Chrome, desktop `1440x900` и mobile `390x844`: карта отсутствует в первом viewport из-за большого hero; на mobile display copy/CTA выходят за правую границу viewport; cookie banner перекрывает hero CTA и контент. Это подтверждает решения map-first shell, mobile bottom sheet и отсутствие hero в новой map app.
- [x] Миграции проверены с нуля в изолированной `test_undersunestate_db`: все migrations применяются успешно. Исправлены два дефекта historical migrations, выявленные этой проверкой: `core.0015` повторно создавал поле `PromotionalBanner.language_code`, уже созданное в `core.0013`; `properties.0018` назначал nullable FK `contact_person_id=1`, хотя команда с таким ID в чистой БД не гарантирована. Жёсткий default удалён также из runtime-модели; существующие назначенные contact person не изменяются.
- [ ] Не выполнены: production HTTP/gzip timings, Lighthouse/RUM и полный UX acceptance review после новой реализации.

**Обнаруженный blocker:** локальный код ожидает миграцию `core.0017_seocontentblock`, а production dump содержит эквивалентную применённую миграцию под именем `core.0003_seocontentblock`. Таблица `core_seocontentblock` и нужные поля существуют, карта и endpoint читают данные корректно, но `python manage.py migrate --plan` завершится `InconsistentMigrationHistory`. До отдельного reconciliation migration graph не выполнять `migrate` на восстановленной БД.

### Спринт 1. Map API и производительность данных

**Цель:** получить тестируемый API-контракт без N+1 и без скрытого ограничения результата.

#### Выполнено досрочно на 2026-07-10

- [x] `S1-03`: map endpoint больше не выполняет запрос изображений на каждый объект. `Prefetch(..., to_attr='map_images')` загружает упорядоченные images одним запросом, а serializer выбирает main image или первое изображение из памяти.
- [x] `S1-01`: сериализация вынесена из view в `apps/properties/map_serialization.py`. Пока сохранён legacy flat JSON contract для существующего `map_core.js`; versioned API contract остаётся следующей задачей.
- [x] `S1-02`: цена строится через session currency и локализованный fallback `PROPERTY_FALLBACK_LABELS`. Проверены `ru/RUB`, `en/USD`, `th/THB`, включая language-prefixed property URLs.
- [x] `S1-04`: bounds принимаются только полным набором из четырёх конечных чисел в допустимом диапазоне; optional `zoom` валидируется в `0..24`. Успешный ответ содержит `request_id`, `server_timing_ms`, `Server-Timing` и echo `zoom`; невалидные bounds/zoom возвращают `400` с безопасным error code, без текста внутреннего исключения.
- [x] `S1-05`: ответ различает `total_count` после фильтров, `viewport_count` в текущих bounds и реально отправленный `visible_count`. При лимите `1000` публикуются `truncated`, `next_action` и `max_results`, поэтому ограничение больше не скрыто. Проверка island: `total=519`, `viewport=visible=518`; без bounds все значения `519`.
- [x] Image-prefetch benchmark, 5 запросов на bounds: island `522 -> 4` SQL-запроса, p95 `738.76 -> 371.51 ms`; west coast `519 -> 4`, p95 `755.18 -> 354.11 ms`; south `177 -> 4`, p95 `301.07 -> 161.26 ms`; north `336 -> 4`, p95 `508.31 -> 259.14 ms`.
- [x] Итоговый count-aware serializer baseline: island/west coast/south/north выполняют по `11` SQL-запросов независимо от числа объектов. Дополнительные постоянные запросы получают currency preference, active currencies, exchange rate и два count metadata запроса; N+1 по images и currency conversion отсутствует. Island response: `518` объектов, `509,284 B` JSON, p95 `412.30 ms` в локальном in-process smoke benchmark.
- [x] `S1-06` реализован на API-уровне: `map_mode=auto` при `zoom <= 10` возвращает компактные grid aggregates (`id`, centroid `lat/lng`, `count`), а на близком zoom - property points. Legacy-клиент сохраняет `map_mode=properties` по умолчанию, поэтому его MapLibre flow не меняется. Smoke на production-like island bounds с `zoom=9`: `518` объектов сгруппированы в `11` aggregates без property payload. Порог `10` и сетка `80px` provisional до согласования S0-07; новый UI подключит aggregates в S4.
- [x] Начато `S1-08`: добавлены endpoint contract tests для локализации и валюты (`ru/RUB`, `en/USD`), metadata/`Server-Timing`, far-zoom aggregates и отклонения неполного bbox или invalid zoom. Отдельный regression test подтверждает не более `11` SQL queries при нескольких property results, защищая от возврата image N+1. `python manage.py test apps.properties.tests.test_map_endpoint --keepdb --verbosity 2` проходит: `5` tests. Filters, empty values, truncation и полный currency matrix остаются в этой задаче.
- [ ] `S1-07` discovery: текущий production cache backend не переопределён и использует `LocMemCache`, который не разделяется между process/workers. Server-side map-response cache не добавлялся намеренно. Перед реализацией нужен shared Redis/Memcached backend, TTL/invalidation policy и metrics hit/miss; повторный `EXPLAIN ANALYZE` для текущих `610` строк не оправдывает новые DB indexes.

| ID | Задача | Зависимость |
| --- | --- | --- |
| S1-01 | Вынести формирование map property payload из `map_properties_json` в typed serializer/service. | S0-07 |
| S1-02 | Реализовать правильные localized labels и price formatting для `ru/en/th` и `THB/USD/RUB`. | S1-01 |
| S1-03 | Переписать загрузку главного изображения через `Prefetch`/annotation и добавить query-count test. | S1-01 |
| S1-04 | Валидировать bounds/zoom, исключать объекты без координат на queryset и добавить request id/server timing. | S1-01 |
| S1-05 | Добавить `total_count`, `visible_count`, `truncated`, `next_action` и документировать лимит/приоритизацию. | S1-04 |
| S1-06 | Добавить zoom-aware aggregate payload и property-point payload; определить порог перехода. | S1-04, S0-07 |
| S1-07 | Добавить cache key/TTL и DB indexes после `EXPLAIN ANALYZE`; не кэшировать ошибки. | S1-03, S1-04, S1-05, S1-06 |
| S1-08 | Написать unit, query-count и endpoint contract tests для фильтров, empty values, bbox и всех languages/currencies. | S1-02, S1-03, S1-04, S1-05, S1-06, S1-07 |

**Готово, когда:** новый ответ API стабилен и покрыт тестами; p95 на целевом viewport укладывается в принятый budget; legacy adapter читает тот же ответ без пользовательской регрессии.

### Спринт 2. Frontend foundation и поставка assets

**Цель:** безопасно встроить независимое map application в Django без переключения публичного UI.

#### Выполнено досрочно на 2026-07-10

- [x] `S2-01`: создан `frontend/map/` с React 19, TypeScript, Vite, MapLibre GL, TanStack Query, ESLint и Vitest. `npm run lint`, `npm test` и `npm run build` проходят; Vite создаёт локальный manifest. `dist/` игнорируется, потому что production output будет перенаправлен в Django static directory только в S2-02. Нынешний `MapApp` - минимальный проверяемый bootstrap и ещё не подключён к публичной `/map/`.
- [x] `S2-02`: Vite production build направлен в `static/map-app/` и создаёт hashed assets с `manifest.json`; generated output не отслеживается Git и должен собираться до `collectstatic`. Добавлен Django tag `{% vite_asset "src/main.tsx" %}` и `{% vite_assets "src/main.tsx" %}` в `apps.core.templatetags.vite_assets`: manifest читается через static finders, URL генерируются обычным Django static storage, а отсутствие manifest безопасно возвращает пустую строку. Template tag tests и map endpoint tests проходят: `7` tests.
- [x] `S2-03`: добавлен `.github/workflows/map-frontend.yml`. Для изменений `frontend/map/` workflow на Node 22 выполняет `npm ci`, lint, Vitest, production build и проверяет наличие `static/map-app/manifest.json`. Та же последовательность локально проходит успешно.
- [x] `S2-04`: Vite dev server ограничен `127.0.0.1:5173` и CORS для Django local origins `localhost/127.0.0.1:8000`. `{% vite_assets %}` использует dev server только при `DEBUG=True` и явно заданном `VITE_DEV_SERVER_URL`; production игнорирует это значение и всегда использует same-origin built assets. Local workflow documented in `frontend/map/README.md`; проверены Vite lint/test/build и `3` template-tag tests.
- [x] `S0-08` и `S2-05`: добавлен server-side feature flag `MAP_REBUILD_ENABLED` (default `False`). При `False` `/map/` продолжает использовать `core/map.html`; при `True` `MapView` выбирает отдельный `core/map_rebuild.html` с SSR fallback, без legacy map scripts, и JSON bootstrap `map-app-bootstrap`. Контракт содержит schema version, language, selected currency, localized endpoints, OpenFreeMap style URL, initial viewport, translations и feature flags. Shell проверен на `/ru/map/`, `/en/map/`, `/th/map/`.
- [x] `S2-06`: React app валидирует bootstrap до mount; unknown schema, missing fields или invalid JSON показывают локальный fallback вместо crash. Добавлен `MapErrorBoundary`; минимальный `MapApp` и parser покрыты Vitest. Flag остаётся выключенным в default settings, поэтому public map пока не переключена.
- [x] `S2-07`: добавлен `MAP_REBUILD_STAFF_ONLY` (default `True`). Controlled internal rollout: `MAP_REBUILD_ENABLED=1`, `MAP_REBUILD_STAFF_ONLY=1`; только authenticated Django staff получает новый shell, anonymous users остаются на legacy. Для public rollout второй flag переключается в `0`; мгновенный rollback - `MAP_REBUILD_ENABLED=0`. Эти сценарии покрыты Django tests вместе с legacy fallback.

| ID | Задача | Зависимость |
| --- | --- | --- |
| S2-01 | Создать `frontend/map/`: React, TypeScript, Vite, ESLint, Vitest, lockfile и scripts для dev/build/test. | S0-07 |
| S2-02 | Настроить production asset output, Vite manifest и Django `vite_asset` template tag. | S2-01 |
| S2-03 | Добавить CI check: frontend install, test, production build и наличие manifest до `collectstatic`. | S2-02 |
| S2-04 | Настроить dev server origin/CSP и документировать local workflow; production не должен обращаться к dev server. | S2-02 |
| S2-05 | Создать SSR map shell с mount node и typed JSON bootstrap; сохранить SEO/head/footer. | S2-02 |
| S2-06 | Реализовать `MapApp` с feature flag, error boundary, bootstrap validation и test render. | S2-05 |
| S2-07 | Добавить новый UI только для staff/internal flag и проверить быстрый rollback на legacy shell. | S2-06, S0-08 |

**Готово, когда:** новый пустой shell загружается через Django на трёх языках, а отсутствие/ошибка JS не ломает SSR страницу; production build воспроизводим в CI.

### Спринт 3. Search state, filters и responsive shell

**Цель:** заменить перезагрузку формы на client state и завершить основной responsive UI.

#### Выполнено досрочно на 2026-07-10

- [x] `S3-01`: добавлен typed `MapSearchState` в `frontend/map/src/features/search/state.ts`. Он поддерживает текущий Django contract для сделки, типов, цены, района/локации, спален, amenities, build status и `q`, а `selected` хранит выбранный property ID. Serializer использует `history.replaceState`; `popstate` восстанавливает state без reload. Viewport намеренно не публикуется в URL. Vitest покрывает parse/serialize, invalid values, back-forward restore и replace-state.
- [x] `S3-02`: добавлен TanStack Query layer в `frontend/map/src/features/search/api.ts`. Query key включает language, currency и полностью сериализованный request URL; fetch получает `AbortSignal`, поэтому obsolete queries отменяются React Query lifecycle. API retries только один раз для network/5xx и не повторяет 4xx. Дополнительный in-memory LRU cache (`24` entries, TTL `20s`) сокращает повторные одинаковые запросы. Новый staff shell уже выполняет `map_mode=auto` query, но controls появятся в S3-03.
- [x] `S3-03`: новый bootstrap передаёт локализованные property types и districts с locations. Добавлен controlled desktop sidebar с deal type, multi-select property types, budget, bedrooms, district/location и reset. Каждое изменение обновляет `MapSearchState`, URL через `replaceState` и query key без page reload. Sidebar скрыт ниже `1024px`; mobile bottom sheet остаётся S3-05.
- [x] `S3-04`: добавлены active filter chips с clear-one и full reset. Чипы удаляют зависимую location вместе с district; price inputs используют debounce `450ms`, поэтому не отправляют query для каждого символа. `isFetching` даёт applying-state в панели активных фильтров, а live count остаётся в sidebar. Логика chips покрыта Vitest.
- [x] `S3-05`: добавлен mobile filter bottom sheet. Он открывается только ниже `1024px`, блокирует document scroll, закрывается по Escape/backdrop/close button, удерживает keyboard focus внутри dialog и учитывает `safe-area-inset-bottom`. Footer остаётся fixed и содержит CTA с live result count; desktop sidebar не дублируется на mobile. Vitest покрывает scroll lock и Escape close.
- [x] `S3-06`: добавлены loading skeleton, empty state с reset и request error с retry. Геолокация имеет явные состояния locating, denied и unavailable; успешные координаты пока не меняют viewport до S4-04. Retry/empty UI покрыты Vitest. Все тексты передаются серверным bootstrap для `ru/en/th`.
- [x] `S3-07`: добавлен Playwright harness с desktop (`1440x900`), tablet (`900x1000`) и iPhone 13 viewport projects. Browser test покрывает URL filter update и восстановление state после navigation/back на desktop, а также открытие/закрытие mobile filter dialog на tablet/mobile. Workflow `map-frontend` теперь устанавливает Chromium и запускает `npm run test:e2e`; локально проходят `14` Vitest tests и `3` Playwright scenarios.

| ID | Задача | Зависимость |
| --- | --- | --- |
| S3-01 | Реализовать typed `MapSearchState`, serializer URL params и `popstate` restore. | S2-06, S1-08 |
| S3-02 | Подключить TanStack Query: request key, abort, stale-response protection, retry и LRU/TTL memory cache. | S3-01 |
| S3-03 | Реализовать desktop sidebar: сделка, тип, бюджет, спальни, район, локация и reset. | S3-01 |
| S3-04 | Реализовать active chips, clear-one/clear-all, live count, debounce для text/price и applying states. | S3-02, S3-03 |
| S3-05 | Реализовать mobile filter bottom sheet: focus trap, scroll lock, safe area, fixed `Показать N объектов`. | S3-03 |
| S3-06 | Реализовать loading, empty, error/retry и denied-geolocation states с переводами. | S3-02 |
| S3-07 | Написать unit tests URL/query state и Playwright сценарии filters/back-forward для трёх breakpoints. | S3-04, S3-05, S3-06 |

**Готово, когда:** изменения фильтров не вызывают page reload, ссылка воспроизводит filters, а desktop/mobile shell проходит keyboard и touch проверки.

### Спринт 4. MapLibre, viewport и results

**Цель:** сделать интерактивную карту и карточки результатов полноценным основным сценарием.

#### Выполнено досрочно на 2026-07-10

- [x] `S4-01`: добавлен React MapLibre adapter с isolated map/source/layer ownership (`map-app-results`), cleanup через `map.remove()` и error callback в React state. Query payload преобразуется в один GeoJSON source; far-zoom aggregates получают circle/count layers. MapLibre загружается dynamic import: initial map shell bundle около `242 KB` (`75 KB` gzip), крупный MapLibre chunk подгружается только при mount. Browser matrix подтверждает canvas container на desktop.
- [x] `S4-02`: initial center/zoom берутся из typed bootstrap, а query payload обновляет единственный GeoJSON source. Property point содержит `propertyId`; click сохраняет `selected` в URL/React state без reload, выбранный marker получает accent color. Aggregate points пока не раскрываются, а viewport search CTA и geolocation move остаются S4-04.
- [x] `S4-03`: `zoomend` обновляет auto-mode query zoom. На far zoom adapter получает только aggregate features; click aggregate приближает карту, после порога API возвращает property points. `toMapFeatureCollection` намеренно выбирает ровно один набор (`aggregates` либо `properties`), поэтому cluster/spiderfy/spread conflict невозможен в новой карте.
- [x] `S4-04`: MapLibre `moveend` публикует pending bounds/zoom, но не меняет active query автоматически. CTA `Искать в этой области` применяет pending viewport; reset возвращает bootstrap Phuket center/zoom. Геолокация при success выполняет `easeTo` и создаёт новый pending viewport; denied/unavailable states остаются из S3-06.
- [x] `S4-05`: click property point открывает desktop MapLibre popup над пином с type, location, price, facts, lazy image, WhatsApp и detail link. Close очищает `selected`; popup не рендерится на mobile. Hover handlers и analytics events не добавлялись.
- [x] `S4-06`: выбранный property на mobile открывает bottom result sheet с facts, lazy image, close и detail link. Favorite удалён из popup/sheet по продуктовому решению. Desktop popup не дублируется на mobile.
- [x] `S4-07`: popup/sheet images используют native `loading="lazy"`. Desktop выбранный пин позиционируется в безопасной зоне, popup не выходит за карту и не имеет внутренней прокрутки; на mobile marker смещается выше bottom sheet.
- [x] `S4-08`: Playwright harness intercepts map API with deterministic payload. Browser smoke verifies MapLibre canvas, desktop popup, list synchronization and mobile result sheet; popup/sheet bounding boxes проверяются относительно карты/viewport. Unit suite и production build входят в обязательную локальную проверку.

| ID | Задача | Зависимость |
| --- | --- | --- |
| S4-01 | Создать React MapLibre adapter: map lifecycle, cleanup, source/layer ownership и error reporting. | S2-06 |
| S4-02 | Подключить initial viewport, selected state и data query к map source. | S3-02, S4-01 |
| S4-03 | Реализовать far-zoom aggregates и close-zoom property markers; запретить одновременный cluster/spiderfy/spread conflict. | S1-06, S4-02 |
| S4-04 | Реализовать `Искать в этой области`, pending viewport state, reset view и геолокацию. | S4-02 |
| S4-05 | Реализовать desktop MapLibre popup над пином с close behavior; hover не отправляет analytics. | S4-03 |
| S4-06 | Реализовать mobile result sheet с tap, close и переходом к detail. | S4-03, S3-05 |
| S4-07 | Реализовать lazy image, selected marker visibility и безопасное positioning popup/sheet без clipping. | S4-05, S4-06 |
| S4-08 | Добавить smoke/visual Playwright tests WebGL canvas, marker/card и no-clipping на three breakpoints. | S4-04, S4-05, S4-06, S4-07 |

**Готово, когда:** пользователь может панорамировать карту, сознательно искать в новой области, открыть объект и перейти в detail на desktop и mobile.

### Спринт 5. Наблюдаемость, качество и controlled rollout

**Цель:** безопасно вывести новую карту в production и принять решение об удалении legacy UI.

#### Выполнено досрочно на 2026-07-10

- [x] `S5-01`: React map dispatches aggregate-only Metrika events through the existing `window.dispatchMetrikaGoal` bridge: filter changes, viewport search, property selection, map error and API/client timing. The payload never includes property IDs/slugs, query text, coordinates or PII. `server_timing_ms` from the API and client elapsed timing are recorded under `map_rebuild_timing`; events are documented in `FUNCTIONS_RU.md` and `FUNCTIONS.md`.
- [ ] `S5-02` operational prerequisite: create the external Metrika/dashboard panels for the recorded goals, API p75/p95, JS error rate and rollback count. This requires production Metrika/dashboard access and must not be claimed as complete from repository code alone.
- [x] `S5-02` repository preparation: `MAP_ROLLOUT_RUNBOOK_2026_07.md` defines dashboard cards, exact event breakdowns, no-PII rule, release stages and stop/rollback conditions. External dashboard creation remains the operational prerequisite above.
- [~] `S5-03` automated portion: Playwright now runs real CSS on desktop/tablet/mobile, checks preview/sheet clipping and validates `prefers-reduced-motion`; keyboard focus trap is covered for the mobile filter dialog. Manual Safari iOS, Chrome Android, slow 4G and assistive-technology audit remain required before public rollout.

| ID | Задача | Зависимость |
| --- | --- | --- |
| S5-01 | Добавить map events и технические timings без hover spam/PII; обновить Metrika docs. | S4-08 |
| S5-02 | Настроить dashboard: conversion funnel, API latency, error rate, JS errors, fallback/rollback count. | S5-01 |
| S5-03 | Провести performance/accessibility audit: slow 4G, Safari iOS, Chrome Android, keyboard, reduced motion. | S4-08 |
| S5-04 | Исправить блокирующие дефекты и подтвердить budgets из раздела 8. | S5-02, S5-03 |
| S5-05 | Rollout: internal -> 10% -> 50% -> 100%, с заранее заданными stop/rollback conditions. | S5-04 |
| S5-06 | После стабильного 100% rollout удалить legacy hero/page handlers и закрыть feature flag отдельным PR. | S5-05 |
| S5-07 | Обновить `FUNCTIONS_RU.md`, `FUNCTIONS.md`, `AGENTS.md` и deployment runbook по фактической архитектуре. | S5-06 |

**Готово, когда:** новая карта выполняет согласованные продуктовые и технические budgets на production, rollback был проверен, legacy код удалён только после периода наблюдения.

### Спринт 6. Stabilization перед public rollout

**Цель:** закрыть ошибки согласованности state/data и эксплуатационные риски, которые важнее добавления новых функций.

#### Выявлено при актуализации 2026-07-11

- React app использует currency из immutable bootstrap в query key и не подписан на глобальное событие `currencyChanged`. При этом собственный LRU cache индексируется URL без runtime currency, поэтому после переключения валюты возможен ответ в предыдущей валюте до истечения TTL.
- При смене query key TanStack Query не получает `placeholderData/keepPreviousData`; старый payload может исчезнуть на время запроса, хотя целевое UX-поведение требует оставлять предыдущие маркеры и карточки до успешного ответа.
- Левая панель показывает `total_count`, но содержит только properties текущего viewport. Пользователю нужно явно различать «всего по фильтрам», «в этой области» и «показано», особенно при `truncated=true`.
- `selected` разрешается только внутри текущего property payload. Прямая ссылка на объект не гарантирует popup, если текущий ответ агрегированный, объект вне viewport или не вошёл в лимит.
- Любое событие MapLibre `error` сейчас переводит UI в map error state. Ошибка отдельного tile не должна выглядеть как полный отказ карты; нужен отдельный fatal/non-fatal policy и реальный fallback style/provider.
- District endpoint ранее строил fallback geometry по координатам объектов. Такая геометрия не является административной границей; это исправлено в `S6-06` удалением fallback из публичного overlay contract.

#### Выполнено 2026-07-11

- [x] `S6-01`: map app подписан на `currencyChanged` и хранит выбранную валюту как runtime state отдельно от immutable bootstrap. Query key и LRU response cache разделяют ответы по currency code; при событии cache очищается и выполняется новый запрос без сброса filters, viewport или `selected`.
- [x] Оба существующих currency selector больше не выполняют fallback page reload, когда успешный React map mount объявляет `data-currency-handler="true"`.
- [x] Unit tests проверяют разделение cache между валютами и обновление runtime currency. Playwright подтверждает смену цены в desktop popup после `currencyChanged` при сохранении URL `?selected=1`.
- [x] `S6-02`: TanStack Query использует `keepPreviousData` при смене query key, а `useMapProperties` сохраняет последний успешный payload как fallback для terminal error state. MapLibre source, список и popup не очищаются во время refetch или после ошибки; alert и Retry остаются доступными.
- [x] Unit и Playwright покрывают delayed filter response и `400` response: прежняя выдача остаётся видимой до success и после error.
- [x] `S6-03`: desktop results summary различает число карточек в списке, property points на карте, объектов в applied viewport и общий результат filters. Aggregate mode показывает count области и подсказку приблизить карту, а не «0 в списке». Filter drawer и mobile CTA используют доступный пользователю map/area count вместо `total_count`.
- [x] Новые подписи `inList/onMap/inArea/total/zoomToSeeAll` передаются server bootstrap и переведены для `ru/en/th`. Unit покрывает property/aggregate summary; Playwright проверяет все четыре count на truncated payload; Django shell tests проходят на трёх языках.

| ID | Приоритет | Задача | Acceptance criterion |
| --- | --- | --- | --- |
| S6-01 | Done | Подписать map app на `currencyChanged`, хранить runtime currency отдельно от bootstrap, инвалидировать Query/LRU cache и повторять текущий запрос без сброса filters/viewport/selected. | После `THB -> USD -> RUB` все list/popup/sheet prices меняются один раз, старые currency responses не возвращаются; есть unit и Playwright test. |
| S6-02 | Done | Сохранять предыдущий успешный payload при filter/viewport refetch; loading показывать как неблокирующее applying-state. | Во время запроса старые markers/cards остаются, stale response не перезаписывает новый state, error предлагает retry и не очищает последнюю успешную выдачу. |
| S6-03 | Done | Исправить семантику счётчиков и truncation UI: total, viewport, shown; не обещать в list больше карточек, чем реально загружено. | Заголовок и CTA однозначно различают глобальную и видимую выдачу на `properties`, `aggregates` и `truncated` ответах во всех языках. |
| S6-04 | Done | В `map_properties_json` добавить `selected_property`: публичный объект резолвится отдельно от filters/bounds и возвращается вместе с основной выдачей или aggregates. | URL с `?selected=<id>` открывает нужную карточку после reload независимо от текущего zoom/bounds; выбранный pin добавляется поверх aggregate payload, а недоступный ID очищается из URL с локализованным состоянием. |
| S6-05 | Done | Добавить классификацию MapLibre errors: tile/source/runtime warning не ломают карту, style/WebGL - fatal. При первой fatal style error OpenFreeMap переключается на встроенный OSM raster style; layers/pins/district source устанавливаются повторно. | Одиночный failed tile не скрывает карту; fatal style failure переключает provider один раз и отправляет агрегированную telemetry без event storm. Unit покрывает policy, dedupe и single fallback switch; runbook содержит staging-проверку. |
| S6-06 | Done | Endpoint district overlay использует только `Polygon`/`MultiPolygon` из vendored geoBoundaries Thailand ADM2 для Phuket; convex hull и padded bounds по координатам удалены. Ответ содержит provenance, а feature - `boundary_source` и `is_approximate: false`; политика обновления описана в `docs/MAP_BOUNDARY_DATA.md`. | Заливка не выдаёт распределение объектов за официальную границу; source/provenance задокументированы и покрыты endpoint test. |
| S6-07 | Done | Playwright matrix покрывает popup у четырёх краёв, exact overlapping coordinates, длинные RU/EN/TH titles, empty image, narrow desktop и currency switch. Добавлены bounds/no-scroll assertions, composited canvas check и popup snapshots; существующие filter tests больше не зависят от сохранённого состояния desktop drawer. | Screenshot/bounds assertions проходят в CI; нет clipping, внутреннего scroll popup и blank canvas. |

**Готово, когда:** новая карта сохраняет консистентность при смене валюты, refetch и deep link; transient tile errors не ломают поиск; UI честно объясняет объём выдачи.

### Спринт 7. Product improvements после стабилизации

**Цель:** улучшить сравнение объектов и мобильный сценарий, не перегружая карту новыми слоями до появления продуктовых метрик.

| ID | Приоритет | Задача | Acceptance criterion |
| --- | --- | --- | --- |
| S7-01 | Done | Добавить на mobile segmented control `Карта / Список`; существующий `ResultsPanel` остаётся mounted и переключается только через presentation state. При возврате к карте вызывается MapLibre resize. | Пользователь переключается без нового API request и без потери filters/viewport/selected; scroll position списка сохраняется. Playwright mobile test это подтверждает. |
| S7-02 | Done | Добавить сортировку списка: рекомендованные, цена по возрастанию/убыванию, новые. Сортировка должна быть серверной и воспроизводимой. | Порядок стабилен между запросами, параметр хранится в URL, marker set не меняется из-за client-only sort. |
| S7-03 | Done | Расширить фильтры только полями с достаточным наполнением: bathrooms, площадь объекта, площадь участка, developer/project при подтверждённой полноте данных. | Перед добавлением измерена заполненность production-like БД; empty/редкие фильтры не публикуются, все labels переведены. |
| S7-04 | Done | Добавить двустороннее hover/focus-сопоставление list card и marker на desktop без открытия popup и analytics spam. | Hover/focus card визуально выделяет pin; keyboard focus даёт тот же эффект; mouseleave/blur корректно восстанавливает selected marker. |
| S7-05 | Done | Разделить компактный marker payload и paginated/cursor card payload либо ввести отдельный card endpoint. | Панорамирование не загружает изображения и длинные тексты для сотен невидимых карточек; list подгружает следующие 20-30 элементов по scroll; gzip budget подтверждён. |
| S7-06 | In progress | Добавить saved search только после подтверждения повторных сессий и спроса; хранение должно быть связано с реальным каналом уведомлений. | Есть продуктовая метрика использования, понятный consent/notification flow и server-side persistence; простая декоративная кнопка не считается реализацией. |
| S7-07 | Done | Отдельно оценить satellite layer, drawn-area/radius search и POI/commute filters. | Для каждой функции есть data source/license, performance budget, mobile UX и измеримый user value до начала реализации. |

**Готово, когда:** mobile поддерживает полноценное сравнение в списке, desktop быстрее связывает cards с pins, а payload растёт пропорционально реально просмотренным карточкам.

#### S7-03: evidence по данным

- На локальном production-like dump проверено 519 активных доступных объектов с координатами: `bathrooms` и `area_total` заполнены у 512 (98,7%), поэтому опубликованы фильтры «Ванные» (`1`, `2`, `3`, `4+`) и диапазон общей площади.
- `area_land` заполнен у 193 объектов (37,2%), `developer` - у 0, а `complex_name` - у 9 (1,7%). Фильтры участка, застройщика и проекта не добавлены: они вводили бы пользователя в заблуждение и не проходят критерий наполненности.
- Фильтры имеют единый URL/API-contract (`bathrooms`, `min_area`, `max_area`), server-side filtering и локализованные подписи для `ru/en/th`. Unit, Django contract и Playwright tests подтверждают UI, URL и запрос к map endpoint.

#### S7-05: payload и pagination

- `/property/ajax/map/` теперь содержит только marker payload (`id`, `lat`, `lng`), aggregates и отдельно выбранный объект для popup. Он не передаёт изображения, title, цены и характеристики всех точек при каждом pan/zoom.
- `/property/ajax/map/cards/` выдаёт полные карточки страницами по 30. Infinite scroll запрашивает следующую страницу только у нижней границы списка; exact overlap использует тот же endpoint с ограниченным параметром `ids`.
- На локальном production-like dump (519 активных объектов с координатами) marker response: 32,629 bytes raw / 8,494 bytes gzip. Первая cards page (30 объектов): 30,497 bytes raw / 4,557 bytes gzip. Django contract и Playwright проверяют pagination, scroll, selected popup и overlap.

#### S7-06: discovery и product gate

- В map app добавлена цель Метрики `map_rebuild_session_started`, которая отправляется не чаще одного раза на browser session. Параметры: `is_returning` и `visit_count` (ограничен значением `9`). В событие не попадают filters, bounds, координаты, email, cookie ID или какой-либо идентификатор пользователя.
- До решения о реализации смотреть в Метрике цель за минимум 28 полных дней: долю `is_returning=true`, количество повторных map-сессий и переходы из них к выбору объекта/лиду. Сегмент строится по `page-url`, содержащему `/map/`, и указанной цели.
- Текущая `NewsletterSubscription` хранит только email и сообщает администраторам о новой подписке. Она не хранит snapshot критериев поиска и не имеет delivery job для подходящих объектов. Поэтому CTA `Save search` не добавлен: такой UI обещал бы уведомления, которых продукт пока не отправляет.
- Следующий gate: подтвердить повторные сессии и минимум 10 явных запросов от пользователей/лидов на новые подходящие объекты за период измерения; затем согласовать email consent, unsubscribe, частоту, server-side модель search snapshot и задачу периодической доставки до показа CTA.

#### S7-07: discovery решений, 2026-07-13

Ни одна из функций ниже не включается в default map shell и не добавляется в текущий sprint без указанного product gate. Решения опираются на существующий MapLibre app и same-origin Django API, а не на клиентские ключи внешних сервисов.

| Функция | Решение по источнику и лицензии | Performance budget | Mobile UX | Измеримый user value и gate |
| --- | --- | --- | --- | --- |
| Satellite | Кандидат для production: MapTiler Satellite, подключаемый style URL в существующий MapLibre. Бесплатный план MapTiler предназначен для testing/personal/non-commercial use, поэтому для коммерческого сайта требуется минимум коммерческий Flex/Custom contract, доменно ограниченный ключ и обязательная attribution. OpenFreeMap остаётся default и fallback; спутник не должен использоваться через незафиксированный public tile URL. | Не загружать satellite style/tile до явного toggle. Default shell p75 не может ухудшиться более чем на 100 ms; на warm 4G p75 от toggle до `styledata` не более 2.5 s; один style swap на действие, без повторного fetch property markers. Отдельно проверять Safari iOS/Chrome Android и tile-error telemetry. | Только один icon button `Satellite` в control stack с текстовым tooltip/aria-label; состояние видно в button. На узком экране control не конкурирует с filter/location; после смены style сохраняются viewport, filters, selection и bottom sheet. | Цель `map_rebuild_basemap_changed` с `basemap=satellite`; решение о rollout после 28 дней, не менее 5% map sessions используют toggle и нет падения `map_rebuild_property_selected` на satellite cohort. До этого: получить коммерческий ключ, проверить Phuket imagery/attribution и обновить CSP/runbook. |
| Drawn area / radius | Для geometry UI: MapLibre GeoJSON source и `maplibre-gl-terradraw`; MapLibre документирует интеграцию Terra Draw. Для расчёта circle/point-in-polygon: точечные модули Turf (MIT). Фильтрация остаётся server-side; не доверять client-side filtering. Текущие координаты хранятся как Decimal, без PostGIS/geometry index, поэтому production implementation требует PostGIS + GiST index либо отдельного измеренного ограничения для временного bbox-prefilter. | Один active geometry, максимум 50 vertices, radius 0.5-15 km, geometry payload <= 8 KB; debounce 250 ms и отмена устаревшего request. При 1,000 candidate points endpoint p95 <= 400 ms, SQL <= 8; иначе не выпускать. Geometry не сериализуется в marker/card payload и не сохраняется в localStorage. | Desktop: toolbar action `Draw area` и отдельный `Radius`, Esc/clear всегда доступны. Mobile v1: только tap-centre + chips `1 / 2 / 5 km`, clear button и bottom filter sheet; freehand/polygon editing не добавлять до подтверждения usability test. | `map_rebuild_spatial_search_applied` (`kind=radius|polygon`, без geometry) и funnel до selection/lead. Pilot только после 10 moderated user sessions: не менее 70% завершают сценарий без помощи, а selection rate после применения не ниже базовой выдачи. Перед кодом: ADR для PostGIS/ограниченного prefilter и contract-test boundary cases. |
| POI / commute | Не использовать public Nominatim для autocomplete: его policy запрещает client-side autocomplete и ограничивает общий поток. Не использовать public Overpass как runtime autocomplete/search backend. Для POI v1 допускается только curated Phuket dataset, импортируемый server-side с источником, датой, лицензией и OSM attribution (если исходные POI из OSM). Для commute/isochrone публичный openrouteservice подходит лишь для discovery: он имеет лимиты, требует attribution и прямо предупреждает, что результаты могут содержать ошибки. Production вариант требует отдельного платного договора либо self-hosted routing service; API key только на Django backend/proxy. | POI: precompute/version dataset, response <= 20 KB and p95 <= 250 ms; no network call while panning. Commute: один origin, один mode, cache normalized request 24 h, request timeout 2 s, no retry storm; isochrone GeoJSON <= 100 KB. Если provider timeout/error, filter не применяется, UI честно показывает unavailable. | Начать с 3-5 проверяемых категорий, например beach, international school, hospital; выбор категории в filter sheet, карта показывает only-on-demand overlay и clear. Commute - отдельный экран/flow, не в первом mobile filter drawer; время маршрута маркируется как estimate и имеет timestamp/source. | POI: `map_rebuild_poi_filter_applied`, потом property selection. Commute: `map_rebuild_commute_requested`/`..._completed`; запуск только после 15 качественных пользовательских запросов или подтверждения sales team, что эти категории влияют на подбор. До разработки: owner data refresh, source/license record, Phuket coverage audit и vendor/self-host cost approval. |

**Итог S7-07:** ближайший кандидат для отдельного последующего эксперимента - satellite toggle после закупки MapTiler и 28-дневного измерения. Drawn radius имеет независимый от внешнего provider путь, но требует spatial storage decision. POI/commute не входят в backlog реализации: без утверждённого источника, владельца обновлений и коммерческого routing SLA они создадут ненадёжный пользовательский контракт.

**Проверенные первичные источники:** [MapTiler pricing](https://www.maptiler.com/cloud/pricing/), [MapTiler + MapLibre style integration](https://docs.maptiler.com/sdk-js/examples/switch-from-maplibre/), [MapLibre Terra Draw example](https://maplibre.org/maplibre-gl-js/docs/examples/draw-geometries-with-terra-draw/), [Turf MIT license](https://github.com/Turfjs/turf), [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/), [openrouteservice restrictions](https://openrouteservice.org/restrictions/) and [terms](https://openrouteservice.org/terms-of-service/).

### Правила управления backlog

- Каждая задача получает owner, estimate, ссылку на PR и test evidence до начала спринта.
- В спринт не включать одновременно изменение API schema и зависящий от него rollout UI без contract tests.
- Новые функции из out of scope не добавлять в текущий спринт: они проходят отдельный discovery и получают свой acceptance criterion.
- Любой regression в language/currency, analytics или SEO является release blocker.

## 8. Нефункциональные требования

| Метрика | Цель |
| --- | --- |
| Map shell visible | <= 1.5 s p75 on 4G mobile, measured separately from tile load |
| First usable results | <= 2.5 s p75 after initial API response path |
| Filter-to-results | <= 800 ms p75, <= 1.5 s p95 end-to-end |
| Viewport interaction | >= 45 FPS p75 on target mobile with normal results set |
| API payload | <= 250 KB gzip for normal property viewport; aggregate more at far zoom |
| JS errors | < 0.5% map sessions |
| Accessibility | keyboard-operable controls, visible focus, 44 px touch targets, semantic labels, reduced motion |

Пороги уточнить после Фазы 0, но фиксировать их в CI/Lighthouse/WebPageTest budget и release dashboard.

## 9. Тестирование

### Backend

- Unit/service tests serializer, localization, currency, filters, bbox (включая antimeridian), empty/missing values and truncation metadata.
- Query-count tests и performance test на production-like fixture.
- Contract tests endpoint для `ru`, `en`, `th` и all supported currencies.

### Frontend

- Unit tests state reducer/query builder: URL, debounce, abort, stale response, cache key, `currencyChanged`.
- Playwright: desktop 1440x900, tablet 768x1024, mobile 375x812; initial state, filters, pan + search area, empty/error/retry, marker popup, back/forward, touch sheet.
- Visual regression screenshot for all breakpoints; check no blank WebGL canvas and no clipped cards.
- Manual checks: Safari iOS, Chrome Android, reduced motion, keyboard-only, slow 4G and denied geolocation.

## 10. Риски и решения

| Риск | Решение |
| --- | --- |
| Tile provider throttling / policy changes | provider review, attribution/CSP audit, cache policy, documented fallback basemap |
| Слишком много точек | zoom-aware aggregation + bounded API + list virtualization; не рендерить 1000 DOM elements |
| Неточные координаты | обозначить approximate location, не использовать искусственные районные полигоны как фактические границы |
| Общий код с catalog map | формализовать MapLibre core API и внедрять page adapters по одному; contract tests before reuse |
| Новый frontend build ломает deploy | manifest проверяется в CI и при startup/deploy; asset build обязателен до `collectstatic`; feature flag сохраняет legacy page |
| SEO потеряет контент из-за map-first shell | сохранить SSR title, description, canonical/hreflang/schema and concise crawlable supporting content below application shell |
| Сложность фильтров | повторно использовать backend `PropertyListView.apply_filters`, но не DOM implementation каталога |

## 11. Приоритеты и out of scope

**Обязательный MVP:** Фазы 0-3, базовые marker/card сценарии из Фазы 4, instrumentation из Фазы 5.

**После MVP:** comparison tray, drawn-area/radius search, commute/POI filters, satellite layer, saved searches, market heatmaps, полноценные district polygons. Каждая функция требует отдельной value/данных/performance оценки.

## 12. Изменяемые файлы

- `templates/core/map.html`, `templates/core/includes/map/*` и Django Vite manifest/template tag integration
- новый `frontend/map/` workspace: Vite config, React/TypeScript sources, tests and built manifest/assets
- временный legacy adapter в `static/js/map/*`; удалить legacy page-specific modules после rollout
- `apps/properties/views.py` плюс новый map serializer/service и tests
- `templates/includes/list/list_data_injection.html` или map-specific bootstrap include
- `docs/METRIKA_GOALS_CATALOG.md` и `docs/FUNCTIONS_RU.md`/`docs/FUNCTIONS.md` после фактического изменения contracts
