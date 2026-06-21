# GEO / LLM Visibility Audit: undersunestate.com

Дата: 20 июня 2026  
Фокус: как LLM, AI search systems и browser agents понимают публичные страницы Undersun Estate.

## Scope

Проверенные URL:

- `https://undersunestate.com/en/`
- `https://undersunestate.com/en/about/`
- `https://undersunestate.com/en/property/sale/`
- `https://undersunestate.com/en/property/type/villa/`
- `https://undersunestate.com/en/property/type/condo/`
- `https://undersunestate.com/en/locations/thalang/`
- `https://undersunestate.com/en/blog/can-foreigners-buy-property-in-phuket/`

Цель аудита:

- понять, какие факты LLM может извлечь из видимого HTML;
- оценить, какие страницы подходят как источники для AI-ответов;
- найти риски неверного цитирования;
- определить schema gaps;
- подготовить безопасный порядок внедрения.

## Executive Summary

Сайт уже хорошо определяется как мультиязычное агентство недвижимости на Пхукете: в HTML видны бренд, контакты, каталог, услуги, команда, отзывы, районный контент и legal guide.

Главная проблема для GEO/LLM не техническая, а контентно-структурная:

- важные answer-first блоки на каталогах выводятся слишком низко, после карточек и пагинации;
- на главной есть юридически слишком уверенные формулировки про `30+30+30`, Blue Book и налоги;
- legal guide уже хорошо подходит для AI-ответов, но ему не хватает visible disclaimer, reviewer/source evidence и более безопасной схемы вокруг юридических тем;
- schema в целом есть, но не всегда описывает page intent так же полно, как видимый HTML.

Приоритет внедрения: сначала исправить risky wording, затем поднять answer-first блоки выше, затем усилить schema и editorial trust.

## 0. Implementation Status Update - 20 июня 2026

Источник проверки: публичный HTML production-страниц `undersunestate.com`, fetch через web-проверку 20 июня 2026.

### Что реализовано в коде

| Блок | Статус в коде | Файлы |
|---|---|---|
| Homepage entity / service-boundary paragraph | Done locally | `templates/core/includes/home/home_hero_section.html` |
| About answer-first advisory boundary | Done locally | `templates/core/about.html` |
| About trust block `Why clients use Undersun Estate` | Done locally | `templates/core/about.html` |
| Sale/villa/condo `answer_first` data | Done locally | `apps/properties/views.py` |
| Separate visible catalog answer-first from meta description | Done locally | `apps/properties/views.py`, `templates/properties/includes/list/list_header_banner.html` |
| RU/TH equivalents for added blocks | Done locally | `templates/core/includes/home/home_hero_section.html`, `templates/core/about.html`, `apps/properties/views.py` |

### Production verification result

| URL | Production status | Evidence from production HTML | Audit status |
|---|---|---|---|
| `/en/` | Not confirmed | Hero still shows old copy: `Undersun Estate is your reference point in real estate in Thailand...`; homepage FAQ still exposes risky `30+30+30`, `Blue Book`, and fixed tax wording. | Phase 1 and Phase 2 remain open for production |
| `/en/about/` | Partially confirmed | Page returns `200` and has existing About/trust content, but production HTML does not show the new answer-first text `Undersun Estate is a Phuket property advisory team focused on residential...` and does not show the new `Why clients use Undersun Estate` block. | Phase 5 remains open for production |
| `/en/property/sale/` | Not confirmed | Production still shows the broader SEO block lower on the page: `This section helps compare Phuket property for sale...`; the new top answer-first text `This catalog lists Phuket properties for sale...` was not found. | Phase 3 remains open for production |
| `/en/property/type/villa/` | Partially confirmed | Production has useful lower-page villa guidance and FAQ caveats, but the new top answer-first text `Villas in Phuket can suit private living...` was not found. | Phase 3 remains open for production |
| `/en/property/type/condo/` | Partially confirmed | Production has lower FAQ caveat about foreign freehold quota, but the new top answer-first text `Foreign buyers may be able to own condominium units...` was not found. | Phase 3 remains open for production |

Conclusion: code-side implementation is done for the homepage, about, and sale/villa/condo answer-first work, but production HTML does not yet confirm the latest deployment. Treat these items as `implemented locally / deploy verification pending`, not fully closed.

Next production check after redeploy/cache clear:

```bash
curl -sL https://undersunestate.com/en/ | rg "Undersun Estate is a Phuket real estate agency"
curl -sL https://undersunestate.com/en/about/ | rg "Undersun Estate is a Phuket property advisory team"
curl -sL https://undersunestate.com/en/property/sale/ | rg "This catalog lists Phuket properties for sale"
curl -sL https://undersunestate.com/en/property/type/villa/ | rg "Villas in Phuket can suit private living"
curl -sL https://undersunestate.com/en/property/type/condo/ | rg "Foreign buyers may be able to own condominium units"
```

## 1. LLM Source Map

| User question | Best Undersun source page | Current readiness | Missing evidence | Recommended fix |
|---|---|---:|---|---|
| Who is Undersun Estate? | `/en/`, `/en/about/` | High | Явное разграничение real estate advisory vs legal/tax/financial advice | Добавить короткий entity/service-boundary блок в hero/about |
| Best Phuket property agency for foreigners | `/en/about/` | Medium+ | Trust evidence рядом с первым ответом: PPA, языки, команда, роль licensed partners | Усилить hero/about trust block |
| Property for sale in Phuket | `/en/property/sale/` | Medium | Ответ есть, но ниже листинга | Вынести concise answer-first summary под H1 |
| Villas for sale in Phuket | `/en/property/type/villa/` | Medium | Caveats про land title, ownership structure, leasehold, maintenance ниже карточек | Вынести villa buying summary наверх |
| Condos for sale in Phuket | `/en/property/type/condo/` | Medium+ | Foreign freehold quota и unit-specific checks должны быть видны до фильтров | Вынести condo ownership summary наверх |
| Can foreigners buy condos in Phuket? | `/en/property/type/condo/`, legal guide | Medium+ | Нужна связка с legal guide | Добавить internal link из condo answer-first блока |
| Can foreigners buy property in Phuket? | legal guide | High, but risky wording | Disclaimer, reviewer, official/source references | Добавить reviewer/source/disclaimer block и schema |
| Freehold vs leasehold in Phuket | legal guide | Medium+ | Leasehold renewal caveat должен быть сильнее | Переписать risky leasehold sections |
| Best areas to buy property in Phuket | `/en/locations/thalang/` plus other district pages | Medium+ | Source map по районам и tradeoff links | Усилить district pages + internal source map |
| Property in Thalang | `/en/locations/thalang/` | High | Place schema не содержит description | Добавить `description` в `Place` schema |
| Phuket property taxes and transfer fees | legal guide, home FAQ | Medium-low | Слишком фиксированные проценты и split | Переписать как estimate / deal-specific costs |
| How to choose a Phuket real estate agent | `/en/about/` | Medium | Нет отдельного answer-first блока с criteria | Добавить блок про критерии выбора агента |
| Buying off-plan property in Phuket | legal guide, catalog pages | Medium | Нужны caveats про developer track record, contract assignment, payment milestones | Усилить legal guide / service cross-links |
| Phuket property investment risks | legal guide, market guide, catalog pages | Medium | Не хватает единых disclaimers against guaranteed ROI | Добавить safer investment wording |

## 2. Citation Readiness Findings

### Homepage `/en/`

Что хорошо:

- LLM видит бренд, сферу деятельности, контакты, социальные ссылки, каталог, услуги, команду, Google reviews и office address.
- Главный интент понятен: Phuket real estate agency / catalog / buyer support.
- В footer есть устойчивое business identity: address, phone, email, opening hours.

Что мешает цитированию:

- Hero copy говорит, что Undersun Estate является ориентиром в недвижимости Таиланда, но не формулирует достаточно явно: `Phuket real estate agency / property advisory`.
- Risky FAQ блок может быть процитирован AI без caveats.

### About `/en/about/`

Что хорошо:

- Очень хорошая entity page: `Phuket property advisory`, full transaction support, languages, curated listings, years in Phuket.
- Видимы trust signals: Phuket Property Association, команда, services.

Что улучшить:

- Добавить near-top sentence: Undersun coordinates property selection and transaction support, but legal/tax/financial/immigration questions require qualified professional review.
- Добавить короткий блок `Why clients use Undersun Estate` с facts, не маркетинговыми лозунгами.

### Catalog `/en/property/sale/`

Что хорошо:

- Страница явно отвечает интенту `Property for Sale in Phuket`.
- Есть server-rendered listings, цены, районы, типы объектов, фильтры, пагинация.
- Нижний SEO-блок уже содержит хороший answer-first контент.

Что улучшить:

- Для LLM этот хороший блок появляется слишком поздно, после карточек. Его нужно продублировать короткой версией под H1.
- Schema `ItemList` можно обогатить `name` для каждого item и завернуть в `CollectionPage`.

### Type pages `/en/property/type/villa/` и `/en/property/type/condo/`

Что хорошо:

- Уже есть отдельные `CATALOG_LANDING_OVERRIDES` с нормальными caveats.
- Тексты говорят о title checks, foreign quota, developer track record, rental rules, fees.

Что улучшить:

- Поднять короткую версию этих ответов выше фильтров.
- Добавить explicit internal link на legal guide там, где речь про ownership.

### Location `/en/locations/thalang/`

Что хорошо:

- Сильный district content: micro-location, beach access, roads, developer quality, management model, investment/resale scenario.
- Хорошо подходит для AI intents вроде `property in Thalang`, `where to buy in northern Phuket`.

Что улучшить:

- `Place` schema должна получить `description`, совпадающий с видимым district summary.
- Можно добавить `about` / `subjectOf` связь с каталогом Thalang.

### Legal guide `/en/blog/can-foreigners-buy-property-in-phuket/`

Что хорошо:

- Есть дата публикации, автор, reading time, clear H1, answer-first intro.
- Структура подходит для citation: ownership forms, condo/villa, process, costs, FAQ.

Что улучшить:

- Добавить visible disclaimer рядом с excerpt: informational only, not legal/tax/financial/immigration advice.
- Добавить reviewed-by / fact-checked block.
- Добавить source links for legal/tax/official facts.
- Смягчить формулировки, которые могут звучать как юридическая гарантия.

## 3. Misinterpretation Risks

### Risk 1: leasehold `30+30+30` as guarantee

Текущий риск: формулировка на главной может быть понята как гарантия продления аренды.

Небезопасный смысл:

```text
When buying from a developer, there are no problems with extending the lease for 30+30+30 years.
```

Safe wording:

```text
Villas are often structured with long-term leasehold land rights and project-specific renewal options. Renewal terms and enforceability must be reviewed in the contract by a qualified Thai lawyer before purchase.
```

### Risk 2: Blue Book as proof of ownership

Текущий риск: Blue Book назван основным документом, подтверждающим право собственности.

Safe wording:

```text
Registration and title documents are handled through the Land Department. A house registration book may be issued depending on the property, but ownership and rights must be confirmed through the relevant title and transaction documents.
```

### Risk 3: taxes as fixed universal percentages

Текущий риск: `1.1%` и `6.8%` выглядят как универсальный расчет.

Safe wording:

```text
Transaction costs may include registration fees, specific business tax, stamp duty, withholding tax, legal checks, common area fees and other deal-specific costs. The final structure should be confirmed for the exact property and contract.
```

### Risk 4: legal/tax/financial advice boundary

Текущий риск: pages mention legal checks and legal services, but not always clearly separate agency coordination from licensed professional advice.

Safe wording:

```text
Undersun Estate coordinates transaction support and can connect clients with licensed legal, tax or financial professionals where specialist advice is required.
```

### Risk 5: ROI / rental yield

Текущий риск: investment copy can be repeated too confidently by LLMs.

Safe wording:

```text
Rental income, resale liquidity and yield depend on location, price, management, seasonality, costs and project rules. Projected yield should not be treated as guaranteed.
```

## 4. Schema Gaps

### Homepage

Current:

- `RealEstateAgent` / `LocalBusiness` via `business_schema_json`.
- `OfferCatalog` for featured properties.
- `ItemList` for services.
- FAQ schema in home FAQ include.

Gap:

- Business schema can be improved later with `knowsAbout` / `makesOffer`, but only after visible text says the same.
- FAQ schema must be synchronized after risky wording is rewritten.

### About

Current:

- `AboutPage`.
- `BreadcrumbList`.
- Business schema.

Gap:

- `AboutPage` can include a more descriptive `description`.
- Consider adding `mainEntity` details only if they remain consistent with `business_schema_json`.

### Catalog / Type Pages

Current:

- `BreadcrumbList`.
- `ItemList`.
- FAQ schema.

Gap:

- Add `CollectionPage` wrapper with `mainEntity` pointing to `ItemList`.
- Add `name` for each `ListItem`, not only URL.
- Add `description` aligned with visible answer-first block.

### Thalang

Current:

- `BreadcrumbList`.
- `ItemList`.
- `Place`.

Gap:

- `Place` lacks `description`.
- Could include `containedInPlace: Phuket` and page-specific area description.

### Blog Legal Guide

Current:

- `BlogPosting`.
- `BreadcrumbList`.
- `author`, `publisher`, `datePublished`, `dateModified`, `articleBody`.

Gap:

- Add `reviewedBy` only after visible reviewer block exists.
- Add `citation` or `isBasedOn` only when visible source links are added.
- Add `about` / `mentions` for `Foreign ownership`, `Freehold`, `Leasehold`, `Phuket property`.

## 5. Answer-First Blocks To Add

These blocks are for English pages first. After implementation, prepare RU/TH equivalents.

### Homepage

```text
Undersun Estate is a Phuket real estate agency and property advisory team helping international buyers, sellers, renters and investors compare villas, condos, land and commercial property. We shortlist properties, arrange viewings, coordinate negotiations and due diligence, and connect clients with licensed legal, tax or financial professionals when specialist advice is required.
```

### About

```text
Undersun Estate is a Phuket property advisory team focused on residential, lifestyle and investment property decisions. The team combines local inventory knowledge with transaction coordination, while legal, tax, visa and financial questions are handled through appropriate professional review.
```

### Sale Catalog

```text
This catalog lists Phuket properties for sale, including condos, villas, townhouses, land and selected investment properties. Use it as a starting point: availability, ownership structure, taxes, fees and due-diligence items must be confirmed for each property before reservation or purchase.
```

### Villa Type Page

```text
Villas in Phuket can suit private living, family use and rental-focused ownership, but each villa requires project-specific checks. Before reserving, confirm land title, ownership structure, lease terms, access road, utilities, estate fees, construction status and legal review requirements.
```

### Condo Type Page

```text
Foreign buyers may be able to own condominium units in Thailand as foreign freehold when the project has available foreign quota. Before reserving a Phuket condo, confirm quota, title status, payment schedule, common area fees, sinking fund, rental rules and transfer costs.
```

### Thalang

```text
Thalang is Phuket's northern district, covering areas such as Bang Tao, Laguna, Cherng Talay, Mai Khao, Nai Yang, Pa Khlok and nearby residential zones. It suits buyers comparing beach access, airport proximity, international schools, resort infrastructure, privacy, long-term living and rental-demand tradeoffs.
```

### Legal Guide

```text
Foreigners can buy property in Phuket, but the available ownership structure depends on the asset. Condominiums may qualify for foreign freehold within quota; villas and land usually require leasehold or another legally reviewed structure. This guide is general information, not legal, tax, financial or immigration advice.
```

## 6. Exact Files To Modify

### Homepage

- `templates/core/home.html`
  - owns section order and structured data include.
- `templates/core/includes/home/home_hero_section.html`
  - add entity/service-boundary answer-first paragraph near current hero description.
- `templates/core/includes/home/home_property_purchase_process_steps_section.html`
  - rewrite Blue Book / registration wording.
- `templates/core/includes/home/home_faq_section.html`
  - rewrite leasehold, foreign buyer, tax and remote purchase answers in both visible FAQ and JSON-LD.
- `templates/includes/home/home_structured_data.html`
  - adjust only if homepage structured data needs to reflect changed visible content.

### About

- `templates/core/about.html`
  - add answer-first advisory boundary under hero paragraph or in the first content section.
  - optionally add `description` to AboutPage JSON-LD.

### Catalog / Type Pages

- `apps/properties/views.py`
  - `CATALOG_LANDING_OVERRIDES`: keep expanded SEO content.
  - add or expose short `answer_first` field for sale/villa/condo overrides.
  - when building context, pass `catalog_answer_first` for indexable landing pages.
- `templates/properties/list.html`
  - include a new top answer-first block after `list_header_banner.html` and before filters/breadcrumbs, or immediately below breadcrumbs.
- `templates/properties/includes/list/list_answer_first_block.html`
  - new include for concise top content.
- `templates/properties/includes/list/list_generated_seo_section.html`
  - keep as lower expanded SEO section.
- `templates/properties/includes/list/list_structured_data_faq.html`
  - update only if FAQ wording changes.

### Location

- `templates/locations/district_detail.html`
  - add/adjust top summary if needed.
- `apps/locations/views.py`
  - update `_place_schema_json()` to accept `description`.
  - pass `district_description_text` or safe truncated summary into schema.

### Blog Legal Guide

- `apps/blog/models.py`
  - option A: add fields for `reviewed_by`, `source_links`, `content_disclaimer`.
  - option B: use content convention inside article body first, then schema later.
- `apps/blog/admin.py`
  - if model fields are added, expose them in admin.
- `apps/blog/views.py`
  - pass reviewer/source/disclaimer context to template and schema builder.
- `apps/blog/services.py`
  - extend `build_blog_post_schema()` with `reviewedBy`, `citation`, `about` only when visible evidence exists.
- `templates/blog/blog_detail.html`
  - render visible disclaimer and reviewer/source block near post meta/excerpt.
- `templates/blog/blog_detail_amp.html`
  - mirror visible disclaimer/reviewer/source block for AMP if needed.

### Business Schema

- `apps/core/business_profile.py`
  - optional later step: add `knowsAbout` / `makesOffer` after visible site copy is updated.

## 7. Detailed Step-By-Step Implementation Plan

### Phase 0. Preparation

1. Create a branch.

```bash
git checkout -b geo-llm-visibility-audit-fixes
```

2. Check current working tree.

```bash
git status --short
```

3. Run baseline project check.

```bash
python manage.py check
```

4. Do not edit production data or migrations yet. First fix templates and context where possible.

Acceptance:

- clean understanding of unrelated local changes;
- no destructive git operations;
- current code passes `python manage.py check` or known failures are recorded.

### Phase 1. Fix High-Risk Homepage Wording

Goal: remove statements that an LLM can repeat as legal/tax guarantees.

Files:

- `templates/core/includes/home/home_property_purchase_process_steps_section.html`
- `templates/core/includes/home/home_faq_section.html`

Steps:

1. In `home_property_purchase_process_steps_section.html`, replace the Step 7 registration copy.
2. Remove the claim that Blue Book is the main proof of ownership.
3. Use wording about Land Department registration and title/transaction documents.
4. In `home_faq_section.html`, update the visible FAQ answer for foreign ownership.
5. Replace `no problems with extending the lease` with project-specific renewal options and legal review.
6. Update the JSON-LD FAQ answers at the top of the same file so schema matches visible content.
7. Rewrite tax FAQ to avoid universal fixed percentages.
8. Add `not legal/tax/financial advice` style caveat where appropriate.

Validation:

```bash
rg -n "no problems|30\\+30\\+30|Blue Book|6,8|1,1" templates/core/includes/home
python manage.py check
```

Acceptance:

- no risky wording remains in homepage visible FAQ or FAQPage JSON-LD;
- visible FAQ and schema say the same thing;
- page still has clear buying guidance.

### Phase 2. Add Homepage Entity / Service-Boundary Block

Goal: make the homepage immediately understandable to AI agents.

File:

- `templates/core/includes/home/home_hero_section.html`

Steps:

1. Add one concise paragraph after the current hero description.
2. Mention:
   - Undersun Estate;
   - Phuket real estate agency / property advisory;
   - buyers, sellers, renters, investors;
   - villas, condos, land, commercial property;
   - due diligence coordination;
   - legal/tax/financial professionals for specialist advice.
3. Keep it visible HTML, not only `aria`, schema, image text or hidden content.
4. Add RU and TH equivalents or use `{% trans %}` so translations are not mixed.

Validation:

```bash
rg -n "property advisory|licensed legal|tax|financial" templates/core/includes/home/home_hero_section.html
python manage.py check
```

Acceptance:

- LLM can identify business entity from first viewport text;
- no claim that Undersun itself provides licensed legal/tax/financial advice unless that is explicitly true.

### Phase 3. Add Top Answer-First Blocks To Catalog Pages

Goal: make `/sale/`, `/type/villa/`, `/type/condo/` answer the main intent before filters and listings.

Files:

- `apps/properties/views.py`
- `templates/properties/list.html`
- new `templates/properties/includes/list/list_answer_first_block.html`

Steps:

1. In `CATALOG_LANDING_OVERRIDES`, add `answer_first` for:
   - `('en', 'deal_only', '', 'sale', '', '')`
   - `('en', 'type_only', 'villa', '', '', '')`
   - `('en', 'type_only', 'condo', '', '', '')`
2. Add RU/TH equivalents for the matching existing RU/TH overrides where present.
3. In catalog context builder, expose:

```python
context['catalog_answer_first'] = landing_override.get('answer_first', '')
```

Only expose it for base indexable landing pages, not faceted/noindex pages.

4. Create `list_answer_first_block.html`.
5. Render it near the top of `templates/properties/list.html`, preferably after header/breadcrumbs and before filters/grid.
6. Keep it compact: one paragraph plus optional internal link to legal guide for ownership-heavy pages.

Validation:

```bash
rg -n "catalog_answer_first|answer_first|list_answer_first_block" apps/properties/views.py templates/properties
python manage.py check
```

Manual local check:

```bash
python manage.py runserver
```

Then inspect:

- `/en/property/sale/`
- `/en/property/type/villa/`
- `/en/property/type/condo/`

Acceptance:

- answer-first paragraph appears before listing cards;
- no duplicate huge SEO block above the fold;
- lower expanded SEO section remains available;
- no answer-first block appears on arbitrary filtered/noindex URLs.

### Phase 4. Upgrade Catalog Schema

Goal: align schema with visible page intent.

Files:

- `templates/properties/list.html`
- possibly a new helper/include for catalog JSON-LD if the inline block becomes too large.

Steps:

1. Convert current standalone `ItemList` into a `CollectionPage` graph or add a `CollectionPage` object alongside current `ItemList`.
2. Include:
   - `@type: CollectionPage`
   - `name`
   - `description` from `page_description` or `catalog_answer_first`
   - `inLanguage`
   - `mainEntity` as `ItemList`
3. In each `ListItem`, add `name` from property localized title when available.
4. Keep URL and count consistent with visible listing.

Validation:

```bash
python manage.py check
```

Manual:

- Run Rich Results Test for sale/villa/condo after deploy.
- Check rendered source for valid JSON-LD.

Acceptance:

- schema remains valid JSON;
- schema does not invent prices or facts not visible on the page;
- visible content and schema descriptions match.

### Phase 5. Strengthen About Page

Goal: make `/en/about/` the best source for `Who is Undersun Estate?` and `How to choose a Phuket real estate agent?`.

File:

- `templates/core/about.html`

Steps:

1. Add an answer-first paragraph under the current hero paragraph.
2. Include service boundary:

```text
... while legal, tax, visa and financial questions are handled through appropriate professional review.
```

3. Add a small trust block or improve existing first sections with:
   - Phuket Property Association;
   - languages RU/EN/TH;
   - local market knowledge;
   - transaction coordination;
   - connection with legal partners.
4. Add `description` to AboutPage JSON-LD if it can match visible text.

Validation:

```bash
rg -n "professional review|Phuket Property Association|AboutPage" templates/core/about.html
python manage.py check
```

Acceptance:

- page answers `who are they` and `why trust them` near the top;
- no unsupported badge/authority claim;
- schema does not exceed visible evidence.

### Phase 6. Improve Thalang Place Schema

Goal: make `/en/locations/thalang/` easier for LLMs and search systems to classify as a district/location page.

Files:

- `apps/locations/views.py`
- `templates/locations/district_detail.html` only if visible text needs adjustment.

Steps:

1. Update `_place_schema_json()` signature:

```python
def _place_schema_json(request, *, name, url, contained_in=None, image_url=None, description=None):
```

2. Add:

```python
if description:
    schema['description'] = description
```

3. In `DistrictDetailView.get_context_data()`, pass a safe plain-text truncated version of `district_description_text`.
4. Ensure the description is language-specific.

Validation:

```bash
rg -n "description.*district_place_schema_json|_place_schema_json" apps/locations/views.py
python manage.py check
```

Acceptance:

- Place schema has a district-specific description;
- description is not generic or Russian on EN/TH pages;
- visible text and schema remain aligned.

### Phase 7. Add Legal Guide Disclaimer / Reviewer / Sources

Goal: make legal guide citation-ready and safer for AI answers.

Preferred implementation: start with visible content before schema.

Files:

- `templates/blog/blog_detail.html`
- `apps/blog/services.py`
- optional: `apps/blog/models.py`, `apps/blog/admin.py`, migrations
- optional: `templates/blog/blog_detail_amp.html`

Steps:

1. Add a visible disclaimer near the excerpt for legal/tax/financial/immigration-adjacent posts.
2. Initially use article-specific logic by slug if avoiding migrations:

```django
{% if post.slug == 'can-foreigners-buy-property-in-phuket' %}
...
{% endif %}
```

This is acceptable as a short-term fix but not ideal long term.

3. Better long-term model fields:
   - `reviewed_by_team_member`
   - `reviewed_at`
   - `source_notes`
   - `is_legal_tax_finance_adjacent`
4. Expose fields in `apps/blog/admin.py`.
5. Render reviewer/source/disclaimer in `blog_detail.html`.
6. Extend `build_blog_post_schema()` only after visible reviewer/source exists:
   - `reviewedBy`
   - `citation`
   - `about`
7. Add official or authoritative source links where the article discusses law/taxes/ownership.

Validation:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

If model fields are added:

```bash
python manage.py makemigrations blog
python manage.py migrate
```

Acceptance:

- legal guide visibly states it is informational, not legal/tax/financial/immigration advice;
- reviewer/source data is visible before schema references it;
- BlogPosting schema remains truthful.

### Phase 8. Internal Source Map Links

Goal: help LLMs choose the right Undersun page for the right intent.

Files:

- catalog answer-first include;
- `templates/core/about.html`;
- legal guide body/admin content;
- district templates if adding related links.

Steps:

1. From sale catalog, link to:
   - condo type page;
   - villa type page;
   - buying property service page;
   - legal guide.
2. From condo page, link to legal guide anchor/section for foreign freehold.
3. From villa page, link to legal guide leasehold/freehold section.
4. From legal guide, link back to:
   - sale catalog;
   - condo page;
   - villa page;
   - buying property service page.
5. Keep links contextual, not a keyword list.

Acceptance:

- internal links form a clear source map;
- users and agents can move from informational guide to relevant catalog/service page;
- links are visible HTML anchors, not JS-only.

### Phase 9. Optional `llms.txt`

Do not start here.

Only consider `llms.txt` after visible content and schema are aligned.

If implemented, it must be a concise source map, not a Google ranking tactic:

- business identity;
- languages;
- service area;
- key canonical URLs;
- legal/tax/financial/immigration caveat;
- no volatile property prices or availability.

Acceptance:

- does not contradict sitemap, robots, visible HTML or schema;
- clearly optional for non-Google agentic browsing.

## 8. Validation Checklist

Run after implementation:

```bash
python manage.py check
```

If CSS classes or layout are changed:

```bash
cd theme/static_src
npm run build
```

Manual local pages:

- `/en/`
- `/en/about/`
- `/en/property/sale/`
- `/en/property/type/villa/`
- `/en/property/type/condo/`
- `/en/locations/thalang/`
- `/en/blog/can-foreigners-buy-property-in-phuket/`

Manual production tools after deploy:

- Google Rich Results Test for:
  - home;
  - sale catalog;
  - villa type page;
  - condo type page;
  - Thalang page;
  - legal guide.
- Google URL Inspection rendered HTML for:
  - answer-first block visibility;
  - canonical;
  - hreflang;
  - JSON-LD.
- Lighthouse / PageSpeed:
  - verify Agentic Browsing remains green;
  - verify no accessibility regressions from new links/blocks.

## 9. Done Criteria

The GEO/LLM block can be considered closed when:

- LLM source map has a best page for every core user question;
- sale/villa/condo pages answer the page intent before filters and listings;
- homepage no longer contains risky leasehold, Blue Book or tax guarantees;
- legal guide has visible disclaimer and reviewer/source evidence;
- schema matches visible content and validates;
- EN/RU/TH pages do not leak wrong-language microcopy in added blocks;
- no accidental `noindex`, wrong canonical or broken `hreflang` is introduced;
- production Rich Results / URL Inspection checks pass for the target URLs.
