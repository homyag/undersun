# Undersun Estate Documentation Hub

Этот каталог содержит как актуальную документацию по текущей архитектуре, так и исторические заметки по отдельным релизам.

## Source of Truth

- Источник истины по архитектуре: код в `apps/`, `config/`, `templates/`, `static/js/`.
- Актуальные обзорные документы: [AGENTS.md](../AGENTS.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [FUNCTIONS_RU.md](./FUNCTIONS_RU.md), [FUNCTIONS.md](./FUNCTIONS.md).
- Исторические change-log документы не должны использоваться как описание текущего устройства проекта без сверки с кодом.

## 1. Current Architecture

- [AGENTS.md](../AGENTS.md) — короткий onboarding по текущей архитектуре, ключевым workflows и ограничениям проекта.
- [ARCHITECTURE.md](./ARCHITECTURE.md) — расширенный обзор платформы: стек, маршруты, данные, фронтенд, аналитика, защита от ботов, деплой.
- [FUNCTIONS_RU.md](./FUNCTIONS_RU.md) / [FUNCTIONS.md](./FUNCTIONS.md) — актуальная карта ключевых Python entry points, middleware, сервисов и JS-модулей.
- [js_refactoring_summary.md](./js_refactoring_summary.md) — текущее разделение bootstrap-данных и клиентской логики на странице объекта.

## 2. Import And Feeds

- [PROPERTY_PARSER.md](./PROPERTY_PARSER.md) — импорт объектов недвижимости с legacy-источников.
- [BLOG_PARSER.md](./BLOG_PARSER.md) — импорт статей блога.
- [YML_FEED.md](./YML_FEED.md) — актуальный Yandex Real Estate XML/YML feed.

## 3. Security And Operations

- [BOT_PROTECTION_PLAN.md](./BOT_PROTECTION_PLAN.md) — operational summary по антибот-защите.
- [phase1_bot_detection.md](./phase1_bot_detection.md) — детализация scoring/middleware слоя.
- [pipeline_bot_protection.md](./pipeline_bot_protection.md) — хронология внедрения и operational decisions.
- [bad_requests_ban.md](./bad_requests_ban.md) — runbook по мониторингу fail2ban и bad requests.
- [NGINX_CONFIG.md](./NGINX_CONFIG.md) — схема nginx на proxy и prod.
- [CSP_RESOURCE_UPDATE_GUIDE.md](./CSP_RESOURCE_UPDATE_GUIDE.md) — как добавлять внешние ресурсы без поломки CSP.

## 4. Product Analytics

- [METRIKA_GOALS_GUIDE.md](./METRIKA_GOALS_GUIDE.md) — правила добавления новых целей Метрики.
- [METRIKA_GOALS_HOME.md](./METRIKA_GOALS_HOME.md) — цели главной страницы.
- [METRIKA_GOALS_CATALOG.md](./METRIKA_GOALS_CATALOG.md) — цели каталога.
- [METRIKA_GOALS_PROPERTY_DETAIL.md](./METRIKA_GOALS_PROPERTY_DETAIL.md) — цели карточки объекта.

## 5. Historical Documents

Эти файлы оставлены как история изменений и контекста прошлых итераций. Они полезны для понимания эволюции проекта, но не являются описанием текущей архитектуры:

- [CURRENCY_FIX_SUMMARY.md](./CURRENCY_FIX_SUMMARY.md)
- [FEATURED_PROPERTIES_CURRENCY_UPDATE.md](./FEATURED_PROPERTIES_CURRENCY_UPDATE.md)
- [CONSULTATION_FORM_UPDATE.md](./CONSULTATION_FORM_UPDATE.md)
- [CONSULTATION_FORM_BRANDING_UPDATE.md](./CONSULTATION_FORM_BRANDING_UPDATE.md)
- [MAP_IMPROVEMENTS.md](./MAP_IMPROVEMENTS.md)
- [решение_от_клода.md](./решение_от_клода.md)

## Maintenance Rules

- Если меняется архитектура, сначала обновляйте [AGENTS.md](../AGENTS.md) и [ARCHITECTURE.md](./ARCHITECTURE.md).
- Если меняются entry points, маршруты, middleware или клиентские модули, обновляйте [FUNCTIONS_RU.md](./FUNCTIONS_RU.md) и [FUNCTIONS.md](./FUNCTIONS.md).
- Если документ описывает конкретный релиз, явно помечайте его как historical/change log.
