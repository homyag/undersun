# План исправления SEO-ошибок и улучшений сайта

Дата: 2026-06-12
Основание: `docs/UNDERS_SECOND_SEO_AUDIT_FACT_CHECK_2026_06_12.md`
Сайт: `https://undersunestate.com`

## Цель

План описывает порядок устранения подтвержденных SEO-ошибок, технических недостатков и точек роста сайта Undersun Estate.

Подход:

1. Сначала закрыть риски индексации, bot protection и доверия к данным.
2. Затем убрать языковые ошибки и неконсистентность metadata.
3. После этого улучшить schema, mobile rendering, изображения и performance.
4. В конце расширять контент и E-E-A-T.

## Статус реализации

Обновлено: 2026-06-18.

Реализовано в первой партии правок:

- Bot protection: исправлен официальный OpenAI crawler `OAI-SearchBot`, добавлены tracked Bingbot IP ranges, `Googlebot`/`Bingbot` убраны из безусловного UA whitelist, удалены `Bytespider`, `CensysInspect`, `MJ12bot`.
- `security.txt`: путь `/.well-known/security.txt` больше не блокируется ни настройками bot protection, ни middleware.
- EN language leaks: исправлены русские строки на главной, About hero alt, часть EN `.po` переводов, добавлена migration для `ko-kaeo -> Ko Kaeo`.
- EN geography translations: добавлена диагностика `find_missing_translations`, заполнены `name_en/description_en` для `District` и `Location`, исправлен мусорный `Krabi` description. Production 2026-06-13: `locations.0003`, `0004` и `0005` применены; missing translations `ru -> en` больше не найдены; кириллица в `Location.name_en/description_en` не обнаружена.
- EN price fallback: `price_number_only`, `Property.price_display` и `Property.get_formatted_price` больше не возвращают жестко прошитые `По запросу`, `/мес` и `скидка` на EN-страницах. Production HTML-check 2026-06-13: `/en/`, `/en/property/sale/`, `/en/locations/thalang/`, `/en/locations/thalang/cherng-talay/` вернули `200`; `Ко Каео`, `По запросу`, `Локация ` в видимом HTML не найдены.
- GSC live rendered HTML `/en/` 2026-06-13: Google видит реальную страницу, а не challenge; canonical, hreflang, основной контент и JSON-LD присутствуют. Внешние robots blocks у Ahrefs/gstatic не являются ошибками сайта; `/en/bot/metrika-loaded/` — analytics beacon, не SEO-контент.
- GSC URL Inspection 2026-06-17: `/en/`, `/ru/`, `/th/`, `/en/property/sale/`, одна карточка объекта и одна location detail page проверены; live rendered HTML/screenshot OK, status `200`, canonical, hreflang, основной HTML-контент и JSON-LD подтверждены.
- Bing Webmaster Tools 2026-06-17: ключевые URL проверены, все OK.
- GSC rendered HTML cleanup: локально исправлены новые подтвержденные утечки homepage featured data/JS: `/м²` в price-per-sqm заменен на `/m²` для EN, `price_formatted: "Цена по запросу"` больше не генерируется в JSON при наличии THB-цены, raw USD/RUB price fields для JS заполняются через серверную конвертацию, `/мес` локализован, WhatsApp prefill и Google Reviews `aria-label` переведены.
- EN amenities translations: заполнены пустые `PropertyFeature.name_en`.
- EN property translation tooling: добавлена batch-команда `translate_missing_properties` для управляемого перевода объектов порциями. Production fact-check: проблема с `Property.title_en`, найденная локально, на production не подтверждается.
- Property type cleanup tooling: добавлена команда `audit_property_type_conflicts` для CSV-аудита и контролируемого исправления выбранных объектов.
- Формы главной: privacy links заменены с `#` на локализованный URL privacy page, honeypot label переписан как техническая строка.
- Favorites pages: добавлен `noindex, follow`.
- Sitemap: `District` и `Location` detail pages добавлены в sitemap с localized alternates.
- Hreflang для индексируемых filter landing pages: language URLs строятся от canonical URL и сохраняют approved canonical query string.
- Metadata/H1: переписан EN H1 главной, добавлены более сильные EN/TH/RU metadata для About, общий `truncate_meta` больше не добавляет буквальное `...` по умолчанию и очищает terminal ellipsis.
- Footer: год копирайта заменен на динамический.
- Production slug migration для property URLs: выполнена безопасная миграция `28` активных объектов со старых русскоязычных транслитерированных slug на EN slug; перед работой создан backup БД, старые URL закрыты `301` redirects на уровне Nginx.
- Schema/JSON-LD: property/detail, service, home FAQ и location/district ItemList schema доработаны; убран `no-image.svg` из `Product.image`/`Place.image`, добавлены `inLanguage`/`mainEntityOfPage`, EN location ItemList больше не использует raw Russian `property.title`.

Требует деплойных действий после выкладки:

- Выполнить `python manage.py compilemessages -l en -l th`, потому что `.mo` файлы не хранятся в git.
- Перезапустить application workers, чтобы Python-код и новые `.mo` были загружены.

## Этап 1. Критические технические риски

Срок: 1 неделя

### 1. Исправить bot protection — частично реализовано 2026-06-12

Статус: реализованы правки whitelist, official crawler names, Bingbot IP ranges и разблокировка `security.txt`. Production-проверка Googlebot/Bingbot через webmaster tools выполнена 2026-06-17. Осталось отдельное решение по Redis для rate-limit state.

Проблема:

- Сейчас whitelist работает по логике `IP OR User-Agent`.
- `Googlebot` и другие боты могут быть пропущены только по строке User-Agent.
- Это открывает риск spoofing: любой клиент может назвать себя `Googlebot`.
- `security.txt` заблокирован в настройках и middleware.
- `LocMemCache` хранит rate-limit/challenge state отдельно в каждом процессе.

Задачи:

1. Убрать безусловный bypass только по User-Agent для поисковых ботов.
2. Для `Googlebot` требовать совпадение с official Google IP ranges.
3. Для `Bingbot` реализовать такую же проверку по verified IP ranges.
4. Проверить актуальные User-Agent OpenAI, Anthropic и Perplexity по официальной документации.
5. Проверить и исправить `OpenAI-SearchBot`, если официальный crawler называется иначе.
6. Добавить недостающие crawler UA только после проверки.
7. Убрать из whitelist сомнительные боты, если они не нужны бизнесу:
   - `Bytespider`;
   - `CensysInspect`;
   - `MJ12bot`.
8. Разблокировать `/.well-known/security.txt` или осознанно опубликовать этот файл.
9. Перенести bot/rate-limit cache с `LocMemCache` на Redis, если production работает в несколько workers.

Критерии приемки:

- Обычные пользователи не получают ложный challenge.
- Googlebot проходит проверку в Google Search Console URL Inspection.
- Поддельный `Googlebot` с чужого IP не проходит whitelist.
- `/.well-known/security.txt` не блокируется middleware, если файл решено публиковать.
- Rate-limit/challenge state общий для всех workers.

### 2. Проверить доступность сайта для поисковых роботов — реализовано 2026-06-17

Статус: подтверждено внешними webmaster tools. Google Search Console live test для `/en/` 2026-06-13: Google получил полноценный rendered HTML главной, не challenge. Google Search Console URL Inspection 2026-06-17: `/en/`, `/ru/`, `/th/`, `/en/property/sale/`, одна карточка объекта и одна location detail page проверены; live rendered HTML/screenshot OK, status `200`, canonical, hreflang, основной HTML-контент и JSON-LD подтверждены. Bing Webmaster Tools 2026-06-17: ключевые URL проверены, все OK.

Проблема:

- `/en/` сейчас доступен с whitelisted audit IP, но предыдущие `403` показывают, что bot protection может блокировать часть audit tools или bot-like clients.
- Доступ настоящего Googlebot нельзя выводить только из локальных HTTP-проверок.

Задачи:

1. Проверить в Google Search Console URL Inspection:
   - `/en/`;
   - `/ru/`;
   - `/th/`;
   - `/en/property/sale/`;
   - одну карточку объекта;
   - одну location detail page.
   Статус: выполнено 2026-06-17, все OK.
2. Посмотреть rendered HTML и screenshot от Google.
   Статус: выполнено 2026-06-17 в рамках URL Inspection, live rendered HTML/screenshot OK.
3. Проверить, видит ли Google:
   - status `200`;
   - canonical;
   - hreflang;
   - основной HTML-контент;
   - JSON-LD schema.
   Статус: выполнено 2026-06-17: status `200`, canonical, hreflang, основной HTML-контент и JSON-LD подтверждены.
4. Аналогично проверить ключевые URL в Bing Webmaster Tools.
   Статус: выполнено 2026-06-17, все OK.

Критерии приемки:

- Google URL Inspection показывает, что страницы доступны.
- Bing Webmaster Tools показывает, что ключевые URL доступны.
- Rendered HTML содержит основной контент.
- Нет ошибок доступа, blocked by robots, server error или WAF/challenge.

## Этап 2. Языковая чистка EN-версии

Срок: 1-2 недели

### 3. Убрать русские тексты с EN-страниц — частично реализовано 2026-06-12

Статус: закрыты подтвержденные шаблонные проблемы на главной, About, catalog/list и location pages. Добавлены команды `python manage.py find_missing_translations` и `python manage.py translate_missing_properties`; после заполнения `District`/`Location` и `PropertyFeature` локально осталось `1867` gaps `ru -> en`. Важно: локальная проблема с пустыми `Property.title_en` на production не подтверждается. Production 2026-06-13 показал, что `find_missing_translations` уже чистый по `locations.Location`; отдельная data migration `locations.0005` закрыла кириллицу в заполненных `Location.description_en`.

Подтвержденные проблемы:

- `/en/` содержит `Ко Каео`.
- `/en/` содержит русский абзац `Лучшие виллы, апартаменты и дома Пхукета...`.
- `/en/property/sale/` содержит:
  - `Подходящие удобства не найдены`;
  - `Продажа и аренда`;
  - `Ко Каео`.
- `/en/locations/thalang/bangtao/` содержит `До аэропорта`.
- `/en/about/` содержит русский `alt` у hero image:
  - `Вилла и кондоминиум на фоне заката в Пхукете`.
- В локальной БД через `find_missing_translations` было найдено `1926` missing translations `ru -> en`; после географических и amenities migrations осталось `1867`.
- Production fact-check 2026-06-12 на VPS `51.79.173.21`: `active_missing_title_en = 0`, `all_missing_title_en = 0`, `active_cyrillic_title_en = 0`, `all_cyrillic_title_en = 0`.
- Публичный HTML `https://undersunestate.com/en/property/sale/`: проверено `64` property link texts, `0` с кириллицей; первые проверенные property detail pages имеют EN `<title>` и H1 без кириллицы.
- Production 2026-06-13: `locations.District` и `locations.Location` больше не имеют missing translations `ru -> en` после применения `locations.0003` и `0004`.
- Production 2026-06-13: прямой regex-аудит выявил кириллицу в заполненных `Location.description_en` для `cherng-talay`, `karon`, `rawai`, `chalong`, `wichit`, `ratsada`, `talad-nuea`, `talad-yai`, `patong`, `kamala`, `kathu`, `thep-krasasttri`, `si-sunthon`, `pa-khlok`, `mai-khao`, `sakhu`, `bangtao`; `locations.0005` применена и повторный regex-аудит больше ничего не выводит.
- Production HTML-check 2026-06-13: `/en/`, `/en/property/sale/`, `/en/locations/thalang/`, `/en/locations/thalang/cherng-talay/` вернули `200`; `ko_kaeo_ru=False`, `price_ru=False`, `location_ru=False`.
- GSC live rendered HTML `/en/` 2026-06-13 выявил дополнительные утечки не в видимом первом HTML-check, а в rendered/data layer:
  - price-per-sqm в featured cards/JSON был вида `$1 616/м²`;
  - `featured-properties-townhouse` содержал `price_formatted: "Цена по запросу"` для объектов с THB-ценой и пустой сохраненной USD-ценой;
  - WhatsApp consultation link содержал русское prefill-сообщение в URL;
  - Google Reviews controls имели русские `aria-label`.
- Локально 2026-06-13 исправлено: `Property.get_formatted_price_per_sqm`, `serialize_properties_for_js`, `home_data_injection.html`, `featured-properties.js`, EN/TH `.po/.mo`. Проверки: `python manage.py check`, `node --check static/js/home/featured-properties.js`, serializer smoke-test и `/en/` HTML smoke-test.
- `properties.PropertyFeature` больше не имеет missing translations `ru -> en`.

Задачи:

1. Заполнить `locations.Location.name_en` для `ko-kaeo`.
   Статус: выполнено, расширено на все `District`/`Location`.
2. Выгрузить все modeltranslation gaps `ru -> en`.
   Статус: выполнено через `python manage.py find_missing_translations`; текущий хвост `1867`.
3. Разделить найденные проблемы по источникам:
   - DB/modeltranslation;
   - templates;
   - `.po` translation files;
   - generated context/metadata.
4. Исправить русские UI-строки в шаблонах и переводах.
5. Исправить EN alt для hero image на `/en/about/`.
6. Пересобрать `.po/.mo`, если изменения затрагивают translation files.
7. Проверить ключевые EN-страницы повторным HTML-сканом на кириллицу.

Инструкция для production по `locations.0005`:

1. Задеплоить файл `apps/locations/migrations/0005_replace_russian_english_location_descriptions.py`.
2. На VPS выполнить:

   ```bash
   cd /home/ubuntu/undersun
   /home/ubuntu/venv/bin/python manage.py showmigrations locations
   /home/ubuntu/venv/bin/python manage.py migrate locations
   ```

3. Повторить проверку заполненных EN-полей на кириллицу:

   ```bash
   /home/ubuntu/venv/bin/python manage.py shell -c $'import re
   from apps.locations.models import Location
   cyr = re.compile(r"[А-Яа-яЁё]")
   for loc in Location.objects.select_related("district").order_by("id"):
       for field in ("name_en", "description_en"):
           value = getattr(loc, field) or ""
           if cyr.search(value):
               print(loc.id, loc.slug, field, repr(value[:160]))'
   ```

   Ожидаемый результат: команда ничего не выводит.

4. После этого повторить HTML-проверку EN-страниц:

   ```bash
   /home/ubuntu/venv/bin/python manage.py shell -c $'import re
   from bs4 import BeautifulSoup
   from django.test import Client
   cyr = re.compile(r"[А-Яа-яЁё]")
   client = Client(HTTP_HOST="undersunestate.com", REMOTE_ADDR="127.0.0.1")
   for url in ["/en/", "/en/property/sale/", "/en/locations/thalang/", "/en/locations/thalang/cherng-talay/"]:
       response = client.get(url, HTTP_USER_AGENT="Mozilla/5.0 SEO-check", HTTP_ACCEPT="text/html")
       soup = BeautifulSoup(response.content.decode("utf-8", "ignore"), "html.parser")
       visible = soup.get_text(" ", strip=True)
       hits = sorted(set(cyr.findall(visible)))
       html = response.content.decode("utf-8", "ignore")
       print(url, response.status_code, "cyrillic_chars", len(hits), "contains_price_ru", "По запросу" in visible, "contains_ru_sqm", "/м²" in html, "contains_ru_month", "/мес" in html)
       if "По запросу" in visible or "/м²" in html or "/мес" in html:
           print("PRICE_RU_HIT")
   ```

   Ожидаемый результат: `contains_price_ru False`, `contains_ru_sqm False`, `contains_ru_month False`; кириллица допустима только в осознанных именах/отзывах, но не в интерфейсных строках, H1, location descriptions и card prices.

Критерии приемки:

- На ключевых EN-страницах нет кириллицы, кроме осознанных брендов/имен.
- `ko-kaeo` на EN рендерится как `Ko Kaeo`.
- EN metadata не содержит русских названий локаций.
- EN UI labels и placeholders на английском.

### 4. Исправить формы на главной — реализовано 2026-06-12

Статус: privacy links на главной заменены на локализованный privacy URL, honeypot label в EN переписан как техническое скрытое поле, проблемный EN placeholder исправлен в `.po`.

Проблемы:

- У `faqQuestionForm` Privacy Policy link равен `#`.
- У `officeVisitForm` Privacy Policy link равен `#`.
- Honeypot label `Your website` может выглядеть как реальное поле в tooling/accessibility checks.
- На EN-формах встречаются русские placeholders, например `Расскажите, что вы ищете`.

Задачи:

1. Заменить `#` privacy links на локализованные privacy URLs:
   - `/en/privacy/`;
   - `/ru/privacy/`;
   - `/th/privacy/`.
2. Проверить все формы на главной:
   - quick consultation;
   - reviews section contact;
   - FAQ question;
   - office visit.
3. Переписать honeypot label так, чтобы он не выглядел как пользовательское поле.
4. Проверить, что honeypot остается невидимым и не ломает bot/form security.
5. Исправить русские placeholders в EN-формах.

Критерии приемки:

- Все privacy links ведут на локализованные страницы.
- Видимые поля имеют корректные label/placeholder.
- Honeypot работает и не мешает accessibility tooling.

## Этап 3. Индексация и metadata

Срок: 1-2 недели

### 5. Исключить favorites pages из индекса — реализовано 2026-06-12

Статус: для favorites pages добавлен `noindex, follow`; `/en/property/favorites/` проверен локально и возвращает нужный `meta robots`.

Проблема:

- `/en/property/favorites/` возвращает `200`.
- Страница имеет self-canonical.
- Нет `meta robots` noindex.
- Страница не должна быть индексируемой SEO landing page.

Задачи:

1. Добавить `noindex, follow` для favorites pages во всех языках.
2. Проверить `/en/property/favorites/`, `/ru/property/favorites/`, `/th/property/favorites/`.
3. Убедиться, что favorites pages не попадают в sitemap.

Критерии приемки:

- Favorites pages содержат `meta robots="noindex, follow"` или `X-Robots-Tag: noindex, follow`.
- Canonical не конфликтует с noindex.
- Sitemap не содержит favorites URLs.

### 6. Добавить district/location detail pages в sitemap — реализовано 2026-06-12

Статус: `SitemapView` включает `District` и `Location` detail pages с alternates для `ru`, `en`, `th`; локально проверено наличие `/en/locations/thalang/` и `/en/locations/thalang/bangtao/`.

Проблема:

- Detail pages районов и локаций существуют и имеют SEO-контент.
- Примеры:
  - `/en/locations/thalang/`;
  - `/en/locations/thalang/bangtao/`.
- Но эти страницы отсутствуют в sitemap.

Задачи:

1. Обновить `SitemapView`.
2. Включить объекты `District`.
3. Включить объекты `Location`.
4. Добавить localized alternates для `ru`, `en`, `th`.
5. Добавить корректный `lastmod`, если есть reliable timestamp.
6. Проверить отсутствие duplicates, query URLs и private URLs.

Критерии приемки:

- `/en/locations/thalang/` есть в sitemap.
- `/en/locations/thalang/bangtao/` есть в sitemap.
- Sitemap валиден.
- Hreflang alternates в sitemap соответствуют реальным localized pages.

### 7. Исправить hreflang на индексируемых filter landing pages — реализовано 2026-06-12

Статус: language/hreflang URLs строятся от canonical URL и сохраняют canonical query string; локально проверено на `/ru/property/type/villa/?district=thalang`.

Проблема:

- Пример из проверки:
  - `/ru/property/type/villa/?district=thalang`
  - canonical включает `?district=thalang`
  - hreflang alternates теряют `district=thalang`.
- Это означает, что hreflang может вести на неэквивалентные страницы.

Задачи:

1. Определить список approved indexable filter params.
2. Строить hreflang от canonical-equivalent URL.
3. Сохранять approved params в localized alternates.
4. Проверить `villa + district` landing pages во всех языках.
5. Не включать transient params, sorting и search query в indexable hreflang.

Критерии приемки:

- Canonical и hreflang описывают одну и ту же страницу/интент.
- Hreflang не теряет approved indexable params.
- Transient filters не создают uncontrolled duplicate indexable pages.

### 8. Переписать слабые metadata — реализовано 2026-06-17

Статус: EN H1 главной переписан, About title/description/OG усилены trust signals. 2026-06-17 закрыта чистка meta descriptions с буквальным `...`: общий `truncate_meta` больше не добавляет `...` по умолчанию и очищает terminal ellipsis из исходного текста. EN title главной оставлен без изменения, потому что текущий `Undersun Estate - Phuket Real Estate` не конфликтует с buyer-intent задачей и не содержит подтвержденной ошибки.

Проверки 2026-06-17:

- `python manage.py test apps.core.tests.SeoUtilsTests` — OK.
- `python manage.py check` — OK.
- Django Client smoke-check: `/en/`, `/ru/`, `/th/`, `/en/about/`, `/en/locations/thalang/`, `/en/locations/thalang/cherng-talay/`, `/en/property/sale/` и одна EN property detail page вернули `200`; у каждой страницы один H1, description не заканчивается на `...`, canonical/hreflang/JSON-LD присутствуют.
- Sitemap sample audit: проверено `250` rendered sitemap URL, `ellipsis_hits 0`.

Подтвержденные проблемы:

- EN H1 главной:
  - `Phuket, Thailand All Phuket properties in one catalog`
- `/en/` description заканчивается на буквальное `...`.
- `/en/locations/thalang/` description заканчивается на буквальное `...`.
- `/en/about/`:
  - `<title>`: `About Us - Undersun Estate`;
  - description общий;
  - `og:title` не совпадает с `<title>` и не использует PPA/co-founder trust signal.

Задачи:

1. Переписать EN H1 главной в один связный buyer-intent heading.
   Статус: выполнено ранее.
2. Обновить EN title главной, если нужно усилить buyer intent и Thailand/Phuket context.
   Статус: изменение не требуется по текущему HTML; title валиден и не содержит подтвержденной ошибки.
3. Убрать буквальные `...` из meta descriptions.
   Статус: выполнено 2026-06-17 через `truncate_meta` и проверку rendered URL.
4. Переписать `/en/about/` title/description/OG title.
   Статус: выполнено ранее.
5. Отразить в About metadata реальные trust signals:
   - Phuket Property Association;
   - co-founder positioning;
   - Phuket real estate expertise.
   Статус: выполнено ранее.

Критерии приемки:

- На каждой странице один ясный H1.
- Description не обрывается многоточием.
- Title, description и OG согласованы.
- Metadata соответствуют видимому контенту.

## Этап 4. Консистентность данных объектов

Срок: 1-3 недели

### 9. Почистить конфликты `property_type` — реализовано 2026-06-17

Статус: production fact-check выполнен на VPS `51.79.173.21`. Добавлена команда `python manage.py audit_property_type_conflicts` для read-only аудита, CSV-выгрузки и точечного применения после ручной проверки ID. Production re-check 2026-06-17 после ручной правки данных: массовый конфликт `villa_title_vs_condo` больше не найден; audit-only выводит `Conflicts found: 1`, только `villa_title_vs_townhouse` для объекта `#608`. Ручная проверка 2026-06-17 подтвердила, что `#608` корректно остается `property_type=townhouse`, поэтому оставшийся audit hit считается false-positive из-за названия проекта `Anocha Luxury Villas`.

Проблема:

- Production refined audit 2026-06-12:
  - `63` активных объекта: `villa` есть в title, но `property_type = condo`;
  - `1` активный объект: title указывает на house, но содержит имя проекта `Anocha Luxury Villas` и `property_type = townhouse`; требует ручной проверки, не auto-fix;
  - прежние `land/plot` с `townhouse` классифицированы как участок у дома, а не как автоматический конфликт типа.
- Production re-check 2026-06-17:
  - `0` активных объектов `villa_title_vs_condo`;
  - остался `#608`, `type=townhouse`, `status=available`, slug `three-storey-4-bedroom-house-in-ratsada-area-phuket-at-anocha-luxury-villas`, title `Three-storey 4 bedroom house in Ratsada area, Phuket at Anocha Luxury Villas`;
  - ручная проверка подтвердила корректность типа `townhouse`; audit hit считается false-positive, потому что `Villas` входит в название проекта, а `house` не имеет отдельного типа в текущей taxonomy.
- Это влияет на metadata, schema, filters, category pages и trust.

Задачи:

1. Выгрузить список конфликтующих объектов.
   Статус: команда добавлена; пример: `python manage.py audit_property_type_conflicts --csv property_type_conflicts.csv`.
2. Проверить каждый конфликт по фактическому типу объекта.
   Статус: выполнено; массовые `villa -> condo` конфликты исправлены вручную на production, `#608` проверен вручную и подтвержден как корректный `townhouse`.
3. Исправить `Property.property_type`.
   Статус: выполнено; production re-check 2026-06-17 подтверждает, что массовые исправления применены, `#608` менять не нужно.
4. Перегенерировать metadata/schema, если они зависят от типа.
   Статус: не требуется для `#608`, так как тип подтвержден корректным; массовые исправления отражаются через существующую генерацию metadata/schema.
5. Проверить карточки объектов, category pages и фильтры.
   Статус: production audit подтверждает отсутствие оставшихся реальных конфликтов `property_type`.

Инструкция для production:

1. Задеплоить код с командой `apps/properties/management/commands/audit_property_type_conflicts.py`.
2. Перед изменением данных сделать backup production DB штатным способом проекта. Минимально: сохранить свежий `pg_dump`/managed backup с датой перед запуском `--apply`.
3. На VPS выполнить audit-only проверку:

   ```bash
   cd /home/ubuntu/undersun
   /home/ubuntu/venv/bin/python manage.py check
   /home/ubuntu/venv/bin/python manage.py audit_property_type_conflicts --csv /home/ubuntu/property_type_conflicts_2026_06_12.csv --limit 20
   ```

4. Скачать или открыть CSV и вручную проверить каждый ID:
   - реальные виллы, которые сейчас `property_type=condo`, добавить в список для исправления на `villa`;
   - объект с `Anocha Luxury Villas` не исправлять автоматически: там `Villas` может быть названием проекта, а не типом объекта;
   - строки с `is_ambiguous=True` не применять без ручной проверки карточки и фото.
5. Применять исправления только точечно и небольшими батчами:

   ```bash
   /home/ubuntu/venv/bin/python manage.py audit_property_type_conflicts --expected villa --ids 1 9 10 --apply
   ```

   Команда намеренно требует одновременно `--expected` и явный список `--ids`, чтобы не менять типы массово по одному слову в title.

6. После каждого батча повторить audit:

   ```bash
   /home/ubuntu/venv/bin/python manage.py audit_property_type_conflicts --csv /home/ubuntu/property_type_conflicts_after.csv --limit 20
   ```

7. Проверить публичные страницы:
   - `/en/property/type/villa/` содержит исправленные объекты;
   - `/en/property/type/condo/` больше не содержит исправленные виллы;
   - карточка каждого исправленного объекта возвращает `200`, имеет корректный H1, breadcrumbs, canonical и schema `additionalType`.
8. После проверки очистить application/page cache, если он включен, и перезапустить только нужные services по обычной deployment-процедуре проекта.

Что не делать:

- Не запускать `--apply` без CSV-review.
- Не исправлять `house` в отдельный тип, пока в taxonomy нет `house`.
- Не считать `land/plot` в title автоматическим признаком типа `land`, если это дом/таунхаус с участком.
- Не менять slugs в рамках этой задачи: это отдельный этап с redirects.

Критерии приемки:

- Title/H1/schema/category/filter не противоречат друг другу.
- Property schema не сообщает тип, который конфликтует с видимым названием.
- Category pages не содержат объекты неправильного типа.

### 10. Slug migration для EN property URLs — реализовано на production 2026-06-12

Статус: выполнено на VPS `51.79.173.21` с предварительным backup БД, строгим CSV-review и `301` redirects.

Проблема:

- В первичном аудите было найдено до `46` активных property URLs с русскоязычными транслитерированными slug.
- После production fact-check строгий список был сужен до `28` активных объектов, где `title_en` уже английский, а текущий `Property.slug` оставался русскоязычной транслитерацией.
- Это ухудшает языковую консистентность EN-версии.
- Важно: в текущей модели `Property.slug` является глобальным полем, а не отдельным `slug_en/slug_ru/slug_th`. Поэтому изменение slug меняет URL карточки сразу для `/en/`, `/ru/` и `/th/`; для сохранения старых ссылок нужны redirects по всем языковым префиксам.

Что сделано на production:

1. Создан backup production PostgreSQL:

   ```text
   /home/ubuntu/backups/undersundb_before_slug_migration_20260612_193647.dump
   ```

   Backup проверен через `pg_restore -l`, dump читается.

2. Сформирован строгий CSV со списком примененной миграции:

   ```text
   /home/ubuntu/property_slug_migration_strict_2026_06_12.csv
   ```

   Итоговый объем: `28` объектов.

3. Slug обновлены в production DB транзакционно; лог примененных изменений сохранен:

   ```text
   /home/ubuntu/property_slug_migration_applied_2026_06_12.csv
   ```

4. Настроены постоянные redirects на уровне Nginx:

   ```text
   /etc/nginx/property_slug_redirects.conf
   /etc/nginx/sites-available/undersun
   ```

   Добавлен `map` старых URL на новые URL и `301` redirect в HTTPS server block. Для каждого объекта добавлены redirects для `/en/`, `/ru/`, `/th/`: всего `84` redirect entries.

5. Перед правкой Nginx сохранен backup конфига:

   ```text
   /etc/nginx/sites-available/undersun.before_slug_migration_20260612_193647
   ```

6. `sudo nginx -t` после изменений успешен; Nginx перезагружен.

7. Проверено фактическое состояние production DB:

   ```text
   rows 28
   ok 28
   old_still []
   other []
   ```

8. Проверены sample redirects:

   ```text
   /en/property/kvartira-s-1-spalnej-v-50-m-ot-morya-v-komplekse-the-title-balcony/
   -> 301 /en/property/1-bedroom-apartment-50-m-from-the-sea-in-the-complex-the-title-balcony/

   /ru/property/kvartira-s-1-spalnej-v-50-m-ot-morya-v-komplekse-the-title-balcony/
   -> 301 /ru/property/1-bedroom-apartment-50-m-from-the-sea-in-the-complex-the-title-balcony/

   /th/property/kvartira-s-1-spalnej-v-50-m-ot-morya-v-komplekse-the-title-balcony/
   -> 301 /th/property/1-bedroom-apartment-50-m-from-the-sea-in-the-complex-the-title-balcony/
   ```

9. Проверена доступность нового URL внутри production Django при whitelisted/browser-like request:

   ```text
   en 200
   ru 200
   th 200
   ```

10. Проверены canonical и hreflang на sample EN карточке:

   ```text
   canonical https://undersunestate.com/en/property/1-bedroom-apartment-50-m-from-the-sea-in-the-complex-the-title-balcony/
   old_in_html False
   alternates: ru, en, th, x-default на новый slug
   ```

11. Проверен sitemap через production Django:

   ```text
   status 200
   old_count 0
   new_count 15
   ```

Примечание:

- Внешний `curl` нового URL может получать `403` из-за production anti-bot middleware без browser/challenge headers. Это не было принято за ошибку маршрута: Django-route проверен отдельно whitelisted/browser-like запросом и возвращает `200`.

Критерии приемки:

- Старые EN/RU/TH URLs дают `301` на новые URLs с сохранением языкового префикса.
- Новые URLs возвращают `200`.
- Canonical указывает на новый URL.
- Hreflang ведет на корректные localized equivalents.
- Sitemap содержит новые canonical URLs и не содержит старый sample slug.

## Этап 5. Schema

Срок: 1-2 недели

### 11. Довести текущую schema, а не добавлять ее "с нуля" — реализовано 2026-06-17

Статус: локальная ветка содержит `Product/Offer` на property detail и дополнительные исправления schema. Django Client audit по реальному HTML завершен без ошибок (`issue_count 0`). Внешний Google Rich Results Test выполнен 2026-06-17 для homepage, property detail, service detail, blog detail и location page: критических ошибок нет. Minor issues есть у части Product snippets, Merchant listings, Articles и LocalBusiness, их можно разобрать отдельным follow-up, но они не блокируют закрытие schema-блока.

Факт:

- Schema уже есть на основных типах страниц.
- Главная содержит `WebSite`, `RealEstateAgent`, `LocalBusiness`, `ItemList`, `OfferCatalog`, `FAQPage`.
- Blog detail содержит `BlogPosting`.
- Service pages содержат `Service`, `BreadcrumbList`, `FAQPage`.
- В локальной ветке property detail содержит primary `Product` с `Offer`, `priceCurrency`, `price`, `availability`, `url`, `seller`, а также отдельный `Place` block.
- Вывод внешнего аудита про отсутствие primary property schema не подтверждается для текущей локальной ветки; production нужно перепроверить после деплоя.
- Property `Product` и `Place` больше не подставляют generic `/static/images/no-image.svg` как изображение объекта. Для schema используются только реальные property photos; для объектов без фото поле `image` не публикуется.
- `Product`, `Place`, `FAQPage`, service schema и home structured data получили `inLanguage`; property `Product`/`Place` и service schema получили `mainEntityOfPage`.
- `WebSite` schema получила стабильный `@id` и связь с publisher `#real-estate-agent`.
- EN `ItemList` schema на district/location pages больше не использует raw `property.title`; применяется безопасный локализованный title с auto-SEO fallback.
- Локальная проверка покрыла `30` active property detail pages, все active service pages, `10` blog posts, `5` district pages и `5` location pages.

Задачи:

1. Прогнать через Rich Results Test:
   - homepage;
   - property detail;
   - service detail;
   - blog detail;
   - location page.
   Статус: выполнено 2026-06-17, критических ошибок нет.
   - Homepage `https://undersunestate.com/ru/`: просканировано 2026-06-17 15:51:38, обнаружено `23` элемента без ошибок: `9` Product snippets, `9` Merchant listings, `3` Articles, `1` LocalBusiness, `1` Organization. Minor issues у Product snippets, Merchant listings и Articles.
   - Property detail `https://undersunestate.com/ru/property/3-bedroom-villa-with-pool-in-rawai-area-phuket-in-quinta-lane-by-intira-villas/`: просканировано 2026-06-17 15:54:57, обнаружено `5` элементов без ошибок: `1` Product snippet, `1` Merchant listing, `1` BreadcrumbList, `1` LocalBusiness, `1` Organization. Minor issues у Product snippet, Merchant listing и LocalBusiness.
   - Service detail `https://undersunestate.com/ru/services/buying-property/`: просканировано 2026-06-17 15:55:33, обнаружено `3` элемента без ошибок: `1` BreadcrumbList, `1` LocalBusiness, `1` Organization. Minor issue у LocalBusiness.
   - Blog detail `https://undersunestate.com/ru/blog/mozhet-li-inostranec-kupit-nedvizhimost-na-phukete-v-2026-godu/`: просканировано 2026-06-17 16:00:46, обнаружено `4` элемента без ошибок: `1` Article, `1` BreadcrumbList, `1` LocalBusiness, `1` Organization. Minor issues у Article и LocalBusiness.
   - Location page `https://undersunestate.com/ru/locations/thalang/`: просканировано 2026-06-17 16:05:50, обнаружено `4` элемента без ошибок: `1` BreadcrumbList, `1` Carousel, `1` LocalBusiness, `1` Organization. Minor issue у LocalBusiness.
2. Добавить или починить primary property detail schema.
   Статус: выполнено, primary `Product/Offer` подтвержден и усилен.
   - `Product/Offer` или другая truthful structure;
   - visible price;
   - currency;
   - title;
   - images;
   - availability/status.
3. Проверить, что schema не противоречит `property_type`.
   Статус: выполнено; локальный audit не нашел противоречий в проверенной выборке, production cleanup `property_type` закрыт в пункте 9.
4. Не добавлять `aggregateRating`, если нет надежной синхронизации visible reviews.
   Статус: выполнено, `aggregateRating` не добавлялся.
5. Не обещать rich results как гарантированный результат.
   Статус: принято как ограничение.

Инструкция для production:

1. После деплоя открыть одну активную карточку объекта на `en`, `ru`, `th`.
2. Проверить page source: должны быть JSON-LD блоки `Product`, `Offer`, `Place`, `FAQPage`, `BreadcrumbList` без битого JSON.
3. Прогнать URL через Rich Results Test:
   - одну property detail page;
   - homepage;
   - service detail;
   - blog detail;
   - location page.
4. Для property detail сверить с видимым HTML:
   - `Product.name` совпадает с H1;
   - `Offer.price` и `priceCurrency` совпадают с видимой ценой;
   - `availability` соответствует `Property.status`;
   - `additionalType` не противоречит исправленному `property_type`;
   - нет `aggregateRating`, если reviews не синхронизируются и не видны на странице.
5. Результаты Rich Results Test сохранить в audit notes или приложить screenshot к задаче.

Критерии приемки:

- Rich Results Test не показывает критических ошибок.
- Schema совпадает с видимым HTML.
- Price/currency/status в schema совпадают с карточкой объекта.
- Нет fake ratings, placeholder values или неподтвержденных claims.

## Этап 6. Mobile и performance

Срок: 2-4 недели

### 12. Исправить mobile first-screen rendering — выполнено 2026-06-17

Статус: исправлено и проверено локальным Playwright/Chrome audit 2026-06-17.

Подтвержденные проблемы:

- Mobile homepage H1 обрезался справа — исправлено через safe wrapping.
- Mobile header controls могли обрезаться на узких экранах — добавлена mobile-защита contact bar.
- Cookie banner перекрывал важный контент первого экрана — mobile banner стал компактнее; на property detail переносится под top nav.
- На catalog mobile screenshot обрезались headline/breadcrumb — breadcrumbs переведены на wrapping.
- На property mobile screenshot cookie banner перекрывал property facts — исправлено; facts/price/CTA не перекрываются.

Задачи:

1. Проверить mobile screenshots для — выполнено 2026-06-17:
   - homepage;
   - catalog;
   - property detail;
   - location page.
2. Исправить H1 wrapping и ширины контейнеров — выполнено.
3. Исправить mobile header controls — выполнено.
4. Пересмотреть позиционирование cookie banner на mobile — выполнено.
5. Проверить, что важные CTA и property facts не перекрываются — выполнено.
6. Прогнать Playwright screenshots после правок — выполнено.

Проверенные URL и viewports 2026-06-17:

- `/ru/`
- `/ru/property/sale/`
- `/ru/property/3-bedroom-villa-with-pool-in-rawai-area-phuket-in-quinta-lane-by-intira-villas/`
- `/ru/locations/thalang/`
- Mobile: `320x740`, `360x740`, `390x844`.
- Desktop smoke: `1366x900`.

Критерии приемки:

- Нет горизонтального clipping: `documentElement.scrollWidth` и `body.scrollWidth` равны viewport на проверенных mobile URL.
- Cookie banner не перекрывает критические property facts/CTA: подтверждено на property detail.
- H1 и breadcrumbs читаемы на mobile: подтверждено screenshots/DOM rects.
- Desktop layout не деградировал: desktop smoke `1366x900`, все проверенные URL `200`, horizontal scroll не появился.

### 13. Улучшить изображения и CLS — выполнено 2026-06-17

Статус: безопасные шаблонные правки выполнены 2026-06-17; массовая переконвертация существующего media-cache в WebP/AVIF не выполнялась и должна идти отдельной performance/media задачей после PageSpeed/CrUX из пункта 14.

Подтвержденные проблемы:

- На `/en/` были изображения без явных width/height — исправлено для owned visible images на проверенном viewport-наборе.
- На `/en/property/sale/` property card images были без width/height и без responsive candidates — исправлено.
- На проверенной property detail page gallery/thumbnails были без stable dimensions — исправлено.
- Property photos часто JPG — существующая модель уже конвертирует оригиналы в WebP при сохранении, но ImageKit `thumbnail/medium` cache пока остается отдельной media-format задачей.
- WebP есть на главной, но image modernization неполная — оставить для performance backlog после фактического PageSpeed.

Задачи:

1. Добавить `width`/`height` или CSS `aspect-ratio` для — выполнено:
   - property cards;
   - galleries;
   - hero/media blocks;
   - team/service/blog images.
2. Внедрить responsive `srcset` для property media — выполнено для catalog cards, home featured property cards, property detail carousel/thumbnails.
3. Конвертировать property images в WebP/AVIF там, где это безопасно — не выполнялось массово; вынести в media-format backlog после PageSpeed/CrUX, чтобы не ломать cache/feed/интеграции.
4. Не ставить `loading="lazy"` на первые above-the-fold images — выполнено; first row catalog cards и property gallery/thumbnails больше не lazy above-the-fold.
5. Добавить preload/fetch priority для LCP image, если PageSpeed подтвердит проблему — добавлен `fetchpriority="high"` для homepage hero, location/district hero и первого property/catalog image; подтверждение через PageSpeed остается в пункте 14.
6. Проверить CLS после правок — выполнен local rendered audit по dimensions/lazy; field/lab CLS через PageSpeed остается в пункте 14.

Проверенные URL и viewports 2026-06-17:

- `/en/`
- `/en/property/sale/`
- `/en/property/3-bedroom-villa-with-pool-in-rawai-area-phuket-in-quinta-lane-by-intira-villas/`
- `/en/locations/thalang/`
- Mobile: `390x844`.
- Desktop: `1366x900`.

Финальный local Playwright/Chrome audit:

- Owned visible images without `width`/`height`: `0` на всех проверенных URL/viewports.
- Owned above-the-fold images without `width`/`height`: `0`.
- Owned lazy above-the-fold images: `0`.
- Property media without `srcset`: `0`.
- Остаточные missing dimensions на property detail относятся к внешним Leaflet/OSM tiles/markers внутри карты; это не SEO-media сайта и не исправлялось.

Критерии приемки:

- Property cards/detail images имеют стабильные размеры: подтверждено local rendered audit.
- PageSpeed не показывает массовые предупреждения по image dimensions: требует внешней проверки в пункте 14.
- CLS не ухудшается из-за media/cookie/banner blocks: local audit не нашел owned image dimension/lazy рисков; field/lab CLS проверить в пункте 14.
- Above-the-fold images не задерживаются lazy-loading: подтверждено local rendered audit.

### 14. Провести PageSpeed/CrUX проверку перед жесткими заявлениями о CWV — выполнено 2026-06-17; mobile performance follow-up открыт 2026-06-18

Статус: PageSpeed UI проверен 2026-06-17 на продовых URL. В PageSpeed для всех проверенных URL field data / CrUX: `Нет данных`, поэтому жесткие заявления по real-user CWV, INP и field TTFB не делаем. Ниже зафиксированы lab Lighthouse 13.4.0 данные, measured backlog и отдельный mobile performance plan по `FCP`, `Speed Index` и `TBT`.

Проблема:

- Внешний аудит делал прогнозы по CWV, но точные field data не были подтверждены.

Проверенные URL:

- `https://undersunestate.com/en/`
- `https://undersunestate.com/en/property/sale/`
- `https://undersunestate.com/en/property/3-bedroom-villa-with-pool-in-rawai-area-phuket-in-quinta-lane-by-intira-villas/`
- `https://undersunestate.com/en/locations/thalang/`

PageSpeed / Lighthouse lab:

| Страница | Device | Score | FCP | LCP | TBT | CLS | SI | Field / CrUX | Report |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Home | Mobile | 67 | 3.3s | 5.0s | 220ms | 0.006 | 5.8s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en/aiqx04115m?form_factor=mobile) |
| Home | Desktop | 75 | 0.8s | 3.2s | 130ms | 0.016 | 2.4s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en/aiqx04115m?form_factor=desktop) |
| Catalog sale | Mobile | 65 | 3.3s | 6.5s | 210ms | 0.011 | 4.6s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en-property-sale/65253i3vv0?form_factor=mobile) |
| Catalog sale | Desktop | 91 | 0.7s | 1.6s | 10ms | 0.003 | 1.9s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en-property-sale/65253i3vv0?form_factor=desktop) |
| Property detail | Mobile | 56 | 3.5s | 6.2s | 430ms | 0.001 | 5.3s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en-property-3-bedroom-villa-with-pool-in-rawai-area-phuket-in-quinta-lane-by-intira-villas/3ty9syz7nm?form_factor=mobile) |
| Property detail | Desktop | 74 | 0.9s | 3.2s | 140ms | 0.088 | 1.8s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en-property-3-bedroom-villa-with-pool-in-rawai-area-phuket-in-quinta-lane-by-intira-villas/3ty9syz7nm?form_factor=desktop) |
| Thalang | Mobile | 84 | 3.2s | 3.5s | 70ms | 0.002 | 4.0s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en-locations-thalang/qgp0dnb05z?form_factor=mobile) |
| Thalang | Desktop | 98 | 0.7s | 0.8s | 0ms | 0.012 | 1.4s | Нет данных | [PSI](https://pagespeed.web.dev/analysis/https-undersunestate-com-en-locations-thalang/qgp0dnb05z?form_factor=desktop) |

Synthetic browser navigation timing, Chrome / Playwright, not CrUX:

| Страница | Status | Synthetic TTFB |
| --- | ---: | ---: |
| Home | 200 | 1937ms |
| Catalog sale | 200 | 1020ms |
| Property detail | 200 | 897ms |
| Thalang | 200 | 1454ms |

Measured findings:

- Field data / CrUX отсутствуют для всех проверенных URL; INP недоступен, TBT используем только как lab proxy.
- CLS в lab низкий на всех страницах: mobile `0.001-0.011`, desktop `0.003-0.088`; массовый CLS-риск не подтвердился.
- Mobile LCP остается главным performance bottleneck: home `5.0s`, catalog `6.5s`, property detail `6.2s`.
- Mobile FCP высокий и почти одинаковый на всех проверенных типах страниц: `3.2-3.5s`. Главные вероятные зоны влияния — render-blocking CSS, шрифты, TTFB и ранние blocking scripts.
- Mobile Speed Index остается слабым на home/catalog/property detail: home `5.8s`, catalog `4.6s`, property detail `5.3s`; location page лучше (`4.0s`), поэтому приоритет — главная, каталог и карточка объекта.
- Mobile TBT особенно проблемный на property detail (`430ms`), умеренно проблемный на home/catalog (`210-220ms`) и низкий на location (`70ms`). Приоритет TBT — property detail, затем home/catalog.
- PageSpeed на проде показывал `Для изображений не заданы явным образом атрибуты width и height`; post-deploy rendered audit после второго деплоя подтвердил, что owned visible images без `width`/`height` и property media без `srcset` больше не найдены на `/en/`, `/en/property/sale/`, property detail и `/en/locations/thalang/`.
- Post-deploy rendered audit 2026-06-17: homepage client-side featured carousel cleanup подтвержден на production. Дополнительно найден mobile-only нюанс на property detail: inactive gallery slides были скрыты только `opacity: 0`, поэтому DOM-аудит считал lazy gallery images above-the-fold. Добавлен local follow-up: inactive slides получают `visibility: hidden` через шаблон и `static/js/properties/detail.js`. Нужен повторный деплой `templates/properties/detail.html` и `static/js/properties/detail.js` перед финальным PSI re-check.
- Agent View accessibility follow-up 2026-06-18: PageSpeed показал `Buttons must have discernible text`, `Links must have discernible text`, `Select element must have an accessible name`. Локально добавлены accessible names для icon-only header/footer/social/WhatsApp/carousel/favorite controls и `for/id` labels для hero search controls. Local rendered audit `/en/`, `/en/property/sale/` и property detail, mobile `390x844` и desktop `1366x900`: visible unnamed `button`, `a[href]`, `select` = `0`.
- `Улучшите загрузку изображений` повторяется на всех типах страниц: от `51-52 KiB` на location до `1.1-1.7 MiB` на home и `1.05 MiB` на desktop property detail.
- Property detail mobile имеет самый высокий lab TBT: `430ms`; вероятные зоны проверки — gallery, map, third-party scripts, unused JS.
- Synthetic TTFB через браузер высокий для anonymous page loads: примерно `0.9-1.9s`; curl без браузерного контекста получает `403` из-за bot protection, поэтому curl TTFB не учитывался.

Mobile performance targets для следующего PSI/Lighthouse re-check:

- FCP: снизить mobile FCP с `3.2-3.5s` до диапазона около `2.5s` или ниже на home/catalog/property detail/location.
- Speed Index: снизить mobile SI на home/property detail до `4.0s` или ниже, catalog — ближе к `4.0s`, location — удержать около текущего уровня.
- TBT: снизить property detail mobile TBT с `430ms` до `200ms` или ниже; home/catalog — до `150ms` или ниже; location — не ухудшить.
- CLS: удержать lab CLS ниже `0.1`; текущие правки image dimensions не должны ухудшиться.
- Эти цели являются lab Lighthouse targets, не field CWV SLA, пока CrUX data отсутствуют.

Performance backlog по измерениям:

1. Деплоить property mobile gallery visibility follow-up и повторить PSI/rendered audit; после повторного деплоя warning по missing `width` / `height` должен уйти для owned images, а mobile property detail не должен иметь lazy visible images above-the-fold.
2. FCP/SI P1 — шрифты — начато 2026-06-18:
   - конвертировать используемые Gilroy `.ttf` в `.woff2`;
   - оставить только реально используемые веса для первого экрана;
   - применить `font-display: swap`;
   - preload делать только для primary above-the-fold font files;
   - не грузить italic/extra-bold варианты до первого рендера, если они не нужны в первом viewport.
3. FCP/SI P1 — critical CSS и active Tailwind build:
   - основной runtime CSS идет через `theme/static/css/dist/styles.css`, подключенный в `templates/base.html`;
   - проверить Tailwind purge/content coverage и убрать неиспользуемые классы из production build;
   - вынести или отложить CSS, который не нужен первому экрану: phone input, формы, отзывы, map/gallery-specific styling;
   - убедиться, что root Tailwind pipeline `static/css/tailwind.min.css` не подключается параллельно без необходимости.
4. FCP/SI P1 — above-the-fold media:
   - оптимизировать LCP/media pipeline: безопасный WebP/AVIF для property/home изображений, контроль размеров generated variants, CDN/cache headers для media, отдельная проверка YML/feed compatibility;
   - preload/fetchpriority оставлять только для настоящего LCP image конкретной страницы;
   - ниже-fold изображения, reviews/contact/team/news media не должны конкурировать с первым экраном.
5. TBT P1 — property detail — начато 2026-06-18:
   - отложить не критичные gallery modal, map, Leaflet/OSM и third-party сценарии до interaction/viewport;
   - в первом экране оставить только минимальную логику текущего слайда, favorite/share/contact CTA;
   - после изменения отдельно проверить property detail mobile TBT.
6. TBT P1 — catalog — начато 2026-06-18:
   - грузить map JS/data только после выбора map view или появления map container в viewport;
   - grid/list каталог должен рендериться без ранней инициализации карты;
   - проверить, что page-specific list modules не создают long tasks при первом mobile load.
7. TBT P1 — homepage — начато 2026-06-18:
   - не выполнять тяжелую инициализацию featured carousel, reviews, process steps, team/news enhancements до idle или viewport;
   - сохранить server-rendered карточки как первичный контент, а JS использовать как enhancement;
   - проверить, что home mobile TBT после изменений ниже `150ms`.
8. TBT/FCP P2 — third-party и analytics:
   - отложить Metrika/goals, reviews widgets и cookie/banner non-critical logic после first paint/idle;
   - не блокировать первый рендер синхронными analytics/form сценариями.
9. FCP P2 — anonymous-page server/cache path:
   - TTFB по browser navigation высокий, но требует отдельного server-side профилирования;
   - проверить anonymous cache, template fragment cache, bot protection/cache behavior, currency/session middleware и DB-запросы в header/home/catalog/detail.

Implementation log:

- 2026-06-18, iteration 1:
  - Catalog map assets lazy-load: `maplibre-gl.css`, `maplibre-gl.js`, `pmtiles`, `basemaps`, `static/js/map/map_popups.js`, `static/js/map/map_core.js`, `list_map_functions.js` и `list_map_data_loader.js` больше не подключаются напрямую в HTML grid/list view. Они подгружаются через `window.catalogMapAssets` при выборе map view.
  - Grid/list catalog early scripts сокращены до `list_utility_functions.js`, `list_view_toggle.js`, `list_favorites.js`, `list_main_init.js` с `defer`.
  - `list_map_data_loader.js` адаптирован под dynamic loading: binding кнопок карты выполняется idempotently даже если `DOMContentLoaded` уже прошел.
  - `fonts.css` сокращен с `16` Gilroy `.ttf` faces до `5` normal faces (`400`, `500`, `600`, `700`, `800`); редкие italic/light/black начертания больше не провоцируют отдельные font downloads и могут синтезироваться браузером.
  - `.woff2` конвертация не выполнена в этой итерации: локально отсутствуют `fontTools`, `woff2_compress`, `ttx`; оставить как отдельную asset-tooling задачу.
  - Verification: `node --check` для измененных list JS, `python manage.py check`, rendered HTML `/en/property/sale/` через Django Client: status `200`, `window.catalogMapAssets=True`, direct `maplibre`, `pmtiles`, `map_core.js`, `maplibre-gl.css` в ранних scripts/styles = `0`.
- 2026-06-18, iteration 2:
  - Homepage JS lazy-load: `hero.js` и `search-counter.js` остаются early scripts, потому что отвечают за первый экран и hero search.
  - `featured-properties.js`, `consultation.js`, `process-steps.js`, `our-team.js` и `google-reviews.js` больше не грузятся пачкой через `requestIdleCallback(..., timeout: 2000)`.
  - Для featured, consultation, process, team и reviews добавлены stable section markers и viewport/interaction loader: модуль грузится при приближении секции к viewport или при первом клике/фокусе.
  - Добавлены безопасные stubs для inline handlers `switchPropertyType`, `toggleStep`, `switchConsultationTab`, `handlePhoneCallback`, чтобы первый пользовательский клик загрузил нужный модуль и повторил действие.
  - Server-rendered homepage content сохраняется: lazy JS работает только как enhancement и не заменяет первичный HTML-контент.
  - Verification: `python manage.py check`, `node --check` для home JS modules, Node parse inline homepage loader, rendered HTML `/en/` через Django Client: status `200`, section markers present, early `/static/js/home/` script src = `0`, loader содержит featured/interaction stubs.
- 2026-06-18, iteration 3:
  - Property detail Leaflet lazy-load: `leaflet.css` и `leaflet.js` больше не подключаются как прямые ранние resources страницы объекта.
  - Map initialization перенесена из `templates/properties/includes/detail_bootstrap.js.html` в `static/js/properties/detail.js`.
  - `window.propertyDetailMapAssets` хранит URL/SRI для Leaflet, а `detail.js` подгружает CSS/JS только при приближении `#property-map` к viewport, при открытии URL с hash `#property-map` или при клике по ссылке на карту.
  - Первый экран property detail сохраняет текущую gallery/price/favorite/form логику; карта остается DOM-блоком и загружается как below-fold enhancement.
  - Verification: `node --check static/js/properties/detail.js`, `python manage.py check`, rendered HTML property detail через Django Client: status `200`, `#property-map=True`, direct Leaflet scripts/styles = `0`, `detail.js` подключен, `window.propertyDetailMapAssets=True`, `L.map` отсутствует в bootstrap HTML.

Задачи:

1. Запустить PageSpeed Insights для — выполнено 2026-06-17:
   - `/en/`;
   - `/en/property/sale/`;
   - одной property detail page;
   - одной location detail page.
2. Сохранить результаты Lighthouse и CrUX, если доступны — выполнено; Lighthouse сохранен ссылками на PSI, CrUX/field data недоступны (`Нет данных`).
3. Разделить field data и lab data — выполнено.
4. Сформировать отдельный performance backlog — выполнено; 2026-06-18 расширено mobile performance plan по FCP, Speed Index и TBT.
5. После деплоя accessibility/gallery follow-up повторить PSI на тех же URL и сравнить с baseline 2026-06-17.
6. Выполнять performance follow-up итерациями: сначала шрифты/CSS и lazy JS, затем media/WebP/AVIF и server/cache profiling.

Критерии приемки:

- Есть фактические данные по LCP, CLS, INP, TTFB: lab LCP/CLS/TBT собраны; INP и field TTFB недоступны из-за отсутствия CrUX field data; synthetic browser TTFB собран отдельно и не трактуется как CWV.
- Performance-задачи основаны на измерениях, а не прогнозах: выполнено.
- Для следующего mobile PSI re-check есть отдельные targets по FCP, Speed Index и TBT.
- Performance follow-up не ухудшает indexability, canonical, hreflang, server-rendered primary content, JSON-LD и accessibility tree.

## Этап 7. Контент и E-E-A-T

Срок: 1-3 месяца

### 15. Создать high-intent guides — не начато

Статус: не входило в первую партию правок; это контентная задача после закрытия технических рисков.

Цель:

Усилить экспертный контент под реальные запросы покупателей и AI/Search retrieval, не создавая doorway pages.

Приоритетные материалы:

1. `Can foreigners buy property in Phuket?`
2. `Leasehold vs Freehold in Thailand`
3. `Rental yield by area in Phuket`
4. `Best areas to buy property in Phuket`
5. Расширенный guide по Bang Tao.

Требования:

- Писать на основе реального опыта Undersun и локального контекста Пхукета.
- Не обещать гарантированный ROI, legal outcome или investment return.
- Добавлять named authors/reviewers там, где тема затрагивает покупку, деньги или legal-adjacent вопросы.
- Связывать guides с relevant services, location pages и property listings.

Критерии приемки:

- Каждая guide page полезна без листинга объектов.
- Есть clear H1, metadata, breadcrumbs, internal links.
- Есть авторство и дата обновления.
- Контент не является generic SEO filler.

### 16. Усилить E-E-A-T и trust signals — не начато

Статус: не входило в первую партию правок; требует бизнес-данных от клиента.

Задачи:

1. Улучшить About page:
   - title;
   - description;
   - OG title;
   - видимые trust signals.
2. Добавить или расширить профили агентов:
   - фото;
   - имя;
   - роль;
   - языки;
   - специализация;
   - активные listings.
3. Добавить company registration/license, если бизнес готов показывать эти данные.
4. Связать blog authors с bio/credentials.
5. Показать реальные process/service evidence:
   - как проходит покупка;
   - какие этапы проверяет агентство;
   - где нужна юридическая проверка;
   - какие документы и ограничения важно учитывать.

Критерии приемки:

- Trust signals видны на сайте, а не только в schema.
- Никаких неподтвержденных гарантий доходности, юридического результата или доступности сделки.
- About и service pages лучше отражают реальный опыт агентства.

### 17. Добавить property management page, если услуга реально оказывается — не начато

Статус: не входило в первую партию правок; зависит от подтверждения услуги клиентом.

Проблема:

- Dedicated `property-management` service page отсутствует.
- Это стоит делать только если агентство реально оказывает услугу.

Задачи:

1. Подтвердить у бизнеса, оказывается ли property management.
2. Если да, создать service page:
   - title/description;
   - H1;
   - process;
   - included services;
   - FAQs;
   - CTA;
   - internal links;
   - Service schema.
3. Если нет, не создавать страницу ради SEO.

Критерии приемки:

- Страница описывает реальную услугу.
- Контент не вводит пользователя в заблуждение.
- Есть понятный CTA и связь с relevant property/services pages.

## Этап 8. Legacy redirects

Срок: 1-2 недели

### 18. Исправить legacy redirects, ведущие на 404 — не начато

Статус: не входило в первую партию правок; требует выгрузки legacy URL patterns.

Проблема:

- Пример legacy URL:
  - `/real-estate/thalang/cherng-talay/450-1-bedroom-apartment`
- Redirect chain заканчивается на:
  - `/ru/property/1-bedroom-apartment/`
- Финальный статус:
  - `404`

Задачи:

1. Выгрузить legacy URL patterns из логов или старой базы.
2. Проверить текущую redirect logic.
3. Реализовать поиск объекта по `legacy_id` или redirect mapping table.
4. Если объект не найден, редиректить на релевантную category/location page.
5. Избегать redirect to 404.

Критерии приемки:

- Legacy URL не ведут на 404.
- Redirect chains короткие.
- Нерешенные legacy URLs ведут на релевантную страницу, а не на несуществующую карточку.

## Контрольный порядок запуска

1. Bot protection и проверка Googlebot/Bingbot.
2. EN language leaks и формы/privacy links.
3. Favorites `noindex`, sitemap для location/district pages, hreflang filters.
4. Metadata/H1/About.
5. Property type cleanup.
6. Property detail schema.
7. Mobile rendering и image/CLS fixes.
8. Slug migration — реализовано на production 2026-06-12.
9. Legacy redirects.
10. Content и E-E-A-T expansion.

## Проверки после каждого релиза

После каждого набора правок проверять:

1. `200/301/404` статусы ключевых URL.
2. `canonical`.
3. `hreflang`.
4. `meta robots`.
5. Sitemap.
6. robots.txt.
7. JSON-LD schema.
8. EN pages на русские строки.
9. Mobile screenshots.
10. PageSpeed Insights для затронутых типов страниц.
11. Google Search Console URL Inspection для ключевых страниц.

## Приоритетная матрица

| Приоритет | Блок | Почему |
|---|---|---|
| P0 | Bot protection и доступ Googlebot | Может напрямую блокировать индексацию. |
| P0 | EN language leaks | Видимая проблема качества и доверия. |
| P0 | Favorites `noindex` | Утилитарная страница не должна быть индексируемой. |
| P1 | Sitemap district/location pages | Важные local SEO pages должны быть discoverable. |
| P1 | Hreflang filtered landings | Влияет на multilingual SEO и релевантность alternates. |
| P1 | Property type conflicts | Ломает metadata/schema/filter trust. |
| P1 | Metadata/H1/About | Быстрый эффект для CTR, clarity и trust. |
| P2 | Property schema | Важно для machine-readable facts, но не начинать с нуля. |
| P2 | Mobile first-screen | Влияет на page experience и конверсию. |
| P2 | Image dimensions/WebP/srcset | Улучшает CLS/performance. |
| P3 | Slug migration | Реализовано на production с backup БД и `301` redirects. |
| P3 | Legacy redirects | Важно для старого трафика и ссылочного веса. |
| P3 | Guides/E-E-A-T | Среднесрочный рост органики и доверия. |
