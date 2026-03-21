# Undersun Estate Documentation Hub

Этот файл собирает все доступные `.md` ресурсы проекта и группирует их по темам. Используйте ссылки ниже для быстрой навигации.

## 1. Обзор и архитектура
- [AGENT Handbook](./AGENT.md) — краткий onboarding для разработчиков и агентов: архитектура, ключевые модули, советы по внедрению.
- [AI platform Overview](./ARCHITECTURE.md) — подробное описание платформы (целевые аудитории, фичи, технический стек, деплой).
- [FUNCTIONS (EN)](./FUNCTIONS.md) / [FUNCTIONS (RU)](./FUNCTIONS_RU.md) — справочник по функциям Python/JS, контекстным процессорам и утилитам перевода.
- [js_refactoring_summary.md](./js_refactoring_summary.md) — как разделены bootstrap-данные и JS-логика на карточке объекта.

## 2. Импорт контента и данных
- [BLOG_PARSER.md](./BLOG_PARSER.md) — команда `parse_blog`, поддерживаемые категории, извлечение медиа и видео.
- [PROPERTY_PARSER.md](./PROPERTY_PARSER.md) — команда `parse_properties`, типы объектов и сделок, обработка изображений и цен.
- [YML_FEED.md](./YML_FEED.md) — генерация Yandex Real Estate YML, ограничение данных, настройки магазина.

## 3. Валюта, формы и UI-обновления
- [CURRENCY_FIX_SUMMARY.md](./CURRENCY_FIX_SUMMARY.md) — переход на THB как базовую валюту, поведение шапки и страниц объектов.
- [FEATURED_PROPERTIES_CURRENCY_UPDATE.md](./FEATURED_PROPERTIES_CURRENCY_UPDATE.md) — обновления валют в главном блоке, синхронизация дропдаунов.
- [CONSULTATION_FORM_UPDATE.md](./CONSULTATION_FORM_UPDATE.md) — новая форма консультации с вкладками (Call/WhatsApp/Telegram).
- [CONSULTATION_FORM_BRANDING_UPDATE.md](./CONSULTATION_FORM_BRANDING_UPDATE.md) — визуальный ребрендинг формы с жёлтым акцентом.
- [MAP_IMPROVEMENTS.md](./MAP_IMPROVEMENTS.md) — дорожная карта по улучшению интерактивной карты (UI/UX, кластеры, фильтры, аналитика).

## 4. Защита от ботов
- [BOT_PROTECTION_PLAN.md](./BOT_PROTECTION_PLAN.md) — общий план по внедрению RequestLog, BotDetectionMiddleware и fail2ban-интеграции.
- [pipeline_bot_protection.md](./pipeline_bot_protection.md) — хронология фаз проекта, whitelist/blacklist, baseline логов.
- [phase1_bot_detection.md](./phase1_bot_detection.md) — подробности реализации Фазы 1 (модель RequestLog, scoring-движок, middleware).
- [bad_requests_ban.md](./bad_requests_ban.md) — руководство по мониторингу fail2ban, cron-задачам и ручным блокировкам.
- [решение_от_клода.md](./решение_от_клода.md) — идеи по дополнительным метрикам, поведенческим сигналам и quick wins.

## 5. Дополнительные материалы
- [AGENT.md](./AGENT.md) — (дублирует раздел 1, оставлен для совместимости).
- Все прочие `.md`, включая FAQ/обновления, находятся в этой папке и связаны через соответствующие разделы выше.
- [CSP_RESOURCE_UPDATE_GUIDE.md](./CSP_RESOURCE_UPDATE_GUIDE.md) — инструкция, что делать при добавлении новых внешних ресурсов (обновление CSP, тесты, документация).
- [METRIKA_GOALS_PROPERTY_DETAIL.md](./METRIKA_GOALS_PROPERTY_DETAIL.md) — список целей Яндекс.Метрики для страницы объекта (формы, CTA, галерея, модалки).
- [METRIKA_GOALS_HOME.md](./METRIKA_GOALS_HOME.md) — цели Метрики на главной (герой, featured блок, формы, офис).
- [METRIKA_GOALS_CATALOG.md](./METRIKA_GOALS_CATALOG.md) — цели Метрики на странице каталога (фильтры, сортировка, карта, карточки).
- [METRIKA_GOALS_GUIDE.md](./METRIKA_GOALS_GUIDE.md) — инструкция по добавлению новых целей (data-атрибуты, `dispatchMetrikaGoal`, чек-лист).

> При добавлении новых документов размещайте их в `docs/` и обновляйте данное оглавление.
