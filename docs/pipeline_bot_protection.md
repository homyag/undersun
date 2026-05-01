# Pipeline защиты от ботов

Документ фиксирует цели, задачи и ход работ по усилению антибот-защиты. Все выполненные действия отмечаем в разделе "Ход работ" с таймштампом формата `[YYYY-MM-DD HH:MM TZ] описание`.

## Цели проекта
- Снизить долю "прямых" бот-визитов, которые фиксирует Яндекс.Метрика, без ущерба для реальных пользователей
- Автоматизировать блокировки и разграничить уровни реагирования (логирование → JS challenge → reCAPTCHA → бан)
- Повысить прозрачность: централизованная статистика, отчеты и документация для мониторинга
- Обеспечить быстрый откат и контроль whitelist/blacklist для поисковых роботов и доверенных IP

## Важные предпосылки
- Трафик из России проходит через обратный прокси `91.212.150.176` (nginx на v2980957) → реальные IP прокидываются через `X-Real-IP`/`X-Forwarded-For`
- Оригинальный backend доступен по `51.79.173.21:443`; прокси форвардит HTTPS и ведёт отдельные логи (`undersunestate_proxy_access.log`)
- Все антибот-правила (fail2ban, middleware, cron) должны учитывать прокси, чтобы не банить его и анализировать исходные IP пользователей

## Ключевые метрики
- Количество "прямых" визитов от ботов (по данным Метрики) до/после релизов
- Число и доля заблокированных IP (fail2ban + scoring) и динамика по дням
- Ложноположительные срабатывания (ручные разбаны, обращения пользователей)
- Время реакции системы: от первого подозрительного запроса до блокировки

## Контрольные кейсы (baseline)
- Валидные роботы: Googlebot/Chrome-Lighthouse (диапазоны 74.125.* / 66.249.* / 66.102.*), Ahrefs/AhrefsSiteAudit, PetalBot, OpenAI SearchBot — должны быть в whitelist при скоринге
- Подозрительные IP из proxy access (без UA, атаки на WP/Laravel): 20.205.115.105, 20.220.148.239, 20.203.201.174, 104.208.81.121, 4.194.217.214, 20.27.221.169, 20.151.2.11, 20.69.252.116, 20.151.224.91, 20.123.25.77
- Аномальные пики нагрузки: 30.01 и 06.02 (>130k хитов/сутки) почти целиком состоят из Google Lighthouse; используем как эталон для стресс-тестов и корректировки порогов

## Whitelist / Blacklist (Ф0 итог)
**Whitelist:**
- 91.212.150.176 — обратный прокси для Рф трафика
- Googlebot диапазоны 66.249.64.0/19, 66.102.0.0/20, 74.125.0.0/16 (Chrome-Lighthouse/Web rendering)
- Ahrefs (User-Agent `AhrefsBot`, `AhrefsSiteAudit`), PetalBot (`*.petalsearch.com`), OpenAI SearchBot (`OAI-SearchBot/1.3`)

**Blacklist seeds (наблюдать/банить при совпадении):**
- 20.205.115.105, 20.220.148.239, 20.203.201.174, 104.208.81.121, 4.194.217.214, 20.27.221.169, 20.151.2.11, 20.69.252.116, 20.151.224.91, 20.123.25.77 (скан/брут WP)
- IP с UA `-` или `Go-http-client/*` без Referer и запросами на бэкапы/CSCO* (отмечены в proxy access)


## Правила BOT_PROTECTION
| Категория | Правила / значения |
|-----------|--------------------|
| **Whitelist IP** | 91.212.150.176 — обратный прокси для RU трафика |
| **Whitelist User-Agent** | Googlebot, Chrome-Lighthouse, Google InspectionTool/Read-Aloud, Bingbot/BingPreview, Yahoo Slurp, DuckDuckBot, YandexBot/YandexMetrika, Mail.RU_Bot, Baiduspider, Sogou, PetalBot, LinkedInBot, facebookexternalhit, Instagram, Twitterbot, Applebot, AhrefsBot/AhrefsSiteAudit, Screaming Frog, SemrushBot, OpenAI-SearchBot, GPTBot, ClaudeBot, AnthropicAI, Bytespider, CensysInspect, Palo Alto Networks, ChatGPT-User |
| **Blacklist IP** | 20.205.115.105; 20.220.148.239; 20.203.201.174; 104.208.81.121; 4.194.217.214; 20.27.221.169; 20.151.2.11; 20.69.252.116; 20.151.224.91; 20.123.25.77 |
| **Подозрительные User-Agent** | curl; python-requests; Go-http-client; Go-http-client/2.0; HeadlessChrome; zgrab |
| **Запрещённые пути** | `/administrator`, `/wp-admin`, `/wp-login.php`, `/wp-content`, `/wp-includes`, `/phpmyadmin`, `/pma`, `/adminer`, `/manager/html`, `/vendor/phpunit`, `/wp-json`, `/xmlrpc.php`, `/.env`, `/.git`, `/vendor`, `/composer.json`, `/package-lock.json`, `/aws`, `/cgi-bin`, `/storage`, `/backup`, `/.well-known/security.txt`, `wp-content/plugins/...` |
| **Исключения** | Методы: OPTIONS; пути: `/static/...`, `/media/...`; `POST /bot/metrika-loaded/` (если referer с нашего домена) не добавляет `js_challenge_missing` |
| **Rate limit** | 5 запросов за 10 сек → +20 (rule `rate_limit`) |
| **Порог действий** | monitor ≥30; challenge ≥60; block ≥90; fail2ban ≥100 |
| **Failover для прямых визитов** | Если сработали только `js_challenge_missing`, `single_html_hit`, `no_referer` или `no_referer_combo`, действие всегда `monitor` (даже если score > 90) |
| **Вес правил** | forbidden_path=120; suspicious_user_agent=25; missing_headers=10; missing_headers_critical=120; no_referer=20; no_referer_combo=90; js_challenge_missing=40; js_challenge_failed=80; single_html_hit=30; rate_limit=20; blacklist_ip=40; suspicious_payload=30; head_on_html=10 |

## Новые рекомендации (февраль 2026)
1. **Убрать «слепое» доверие к прокси.** Сейчас `91.212.150.176` в whitelist IP, поэтому любой трафик из РФ обходит BotDetectionMiddleware. Нужно настроить `set_real_ip_from`/`real_ip_header` на frontend-nginx и удалить этот адрес из белого списка (или хотя бы запускать скоринг даже для whitelisted IP, беря клиентский адрес из `X-Forwarded-For`). Иначе «прямые» боты, заходящие через прокси, всегда будут попадать в Метрику как обычные визиты.
2. **Повысить вес «тихих» сигналов.** По свежим логам RequestLog большинство allow‑визитов имеют только `js_challenge_missing` (15) + `no_referer` (10). Поднимите `js_challenge_missing` до ~40, `no_referer` до ~20 и добавьте правило «одиночный HTML-хит без статики за последние 5 секунд» (+30). Это пошлёт bounce‑ботов хотя бы в `monitor` и позволит анализировать/банить их сериями.
3. **Ужесточить challenge.** Раздавать страницу только после того, как браузер подтянул cookie `bot_challenge`, полученный от сервера. Стратегия: первый запрос → 302/403 со `Set-Cookie`, второй запрос без валидного токена → мгновенный блок. Так однохоповые GET даже не попадут в шаблоны и не зажгут Метрику.
4. **Пассивная аналитика «нулевых» визитов.** Периодически (cron/management-команда) агрегировать RequestLog по IP/ASN для событий со score <30, хранить топ-списки и автоматически маркировать источники, у которых десятки «0:00» визитов в сутки. Параллельно выгружать из Метрики сегмент «время на сайте = 0» и сопоставлять с IP/ASN → обновлять blacklist и отслеживать эффективность релизов.
5. **Фиксировать изменения.** Любые корректировки весов, whitelist/blacklist, настроек челленджа и cron‑отчётов добавлять в этот файл (дата + суть), чтобы команда видела историю и могла быстро откатить изменения, если появятся ложные блокировки.
6. **Ускорить выдачу `bot_challenge`.**
   - **Set-Cookie на сервере.** В `BotDetectionMiddleware` при первом allow/monitor ответе устанавливаем `bot_challenge`, чтобы фронтенд не ждал загрузки JS.
   - **Минимальный inline-скрипт.** В `<head>` размещаем крошечный script, который синхронно пишет cookie или делает `sendBeacon` — это гарантирует токен даже при медленном соединении.
   - **Отдельный `challenge.js`.** Выделяем лёгкий файл, подключаем его через `<script defer ...>` и `preload/preconnect`, чтобы cookie появлялся до тяжёлых бандлов.
   - **Set-Cookie при challenge-редиректе.** Если возвращаем 302/refresh-страницу, она сразу отправляет cookie; после reload пользователь уже проходит проверку.

Последовательность срабатывания:
- Middleware игнорирует whitelist IP/UA и исключает `/static`, `/media`, метод OPTIONS.
- Для остальных запросов собираются заголовки и определяется bot_score по таблице.
- JS challenge (cookie + hidden поле) проверяется первым делом: если нет cookie → `js_challenge_missing`, если токен не совпал → `js_challenge_failed` (и score → challenge/block).
- `action=block` → 403 + запись в RequestLog (`bot-fastban`), далее `undersun-fastban` сразу банит IP через fail2ban.
- `action=challenge` (будет использоваться в Ф2), `monitor` — только логирование.

## Быстрый fail2ban (bot-fastban)
1. Middleware пишет строку `bot-fastban ip=<IP> score=<score> path=<path> rules=<...>` в `bad_requests.log` при action=block.
2. Настроить фильтр `/etc/fail2ban/filter.d/undersun-fastban.conf`:
   ```ini
   [Definition]
   failregex = ^.*bot-fastban ip=<HOST>.*$
   ignoreregex =
   ```
3. Добавить jail `/etc/fail2ban/jail.d/undersun-fastban.conf`:
   ```ini
   [undersun-fastban]
   enabled  = true
   port     = http,https
   filter   = undersun-fastban
   logpath  = /home/ubuntu/undersun/logs/bad_requests.log
   bantime  = 86400
   findtime = 60
   maxretry = 1
   action   = %(action_mwl)s
   ```
4. `sudo fail2ban-client reload` — теперь все автоматические блоки (403) мгновенно попадают в отдельный jail, не дожидаясь 5 нарушений.


## Пайплайн работ
| Фаза | Задачи | Ответственные | Статус |
|------|--------|---------------|--------|
| Ф0. Подготовка | Baseline Метрики, сбор логов (bad_requests + nginx + proxy), фиксация fail2ban, описание инфраструктуры/прокси, согласование whitelist | Igor / AI assistant | completed |
| Ф1. Скоринг в Django | Модель `RequestLog`, сервис `bot_detection`, `BotDetectionMiddleware`, интеграция с fail2ban и настройка весов | Igor / AI assistant | completed |
| Ф1.5 Быстрые правки | Актуализировать whitelist/blacklist, усилить ForbiddenPath, проверить reCAPTCHA/формы, финальные настройки fastban | Igor / AI assistant | completed |
| Ф2. JS Challenge | JS challenge (cookie + hidden token), challenge-редиректор (всё на проде) | Frontend + AI assistant | completed |
| Ф3. IP reputation | Интеграция бесплатной базы iptoasn/db-ip-Lite, локальный резолвер ASN, веса для датацентров, опционально abuse lookup (при наличии free API) | Infra / AI assistant | pending |
| Ф4. Автоматизация | Обновление management-команд `analyze_bad_requests`/`ban_bad_requests`, отчеты, алерты, документация по мониторингу | Igor / DevOps | pending |
| Ф5. Пострелизный аудит | Сравнение метрик до/после, анализ ложных срабатываний, тюнинг весов и whitelist/blacklist | Igor + Analytics | pending |

## Ход работ
> Добавляем записи по мере выполнения задач, пример: `[2026-02-18 14:05 GMT+8] Подготовлены миграции для RequestLog`

- (нет записей)
- [2026-02-12 23:01 MSK] Получена выгрузка Яндекс.Метрики по прямым визитам (CSV за 2026-01-13 — 2026-02-12) для анализа baseline.
- [2026-02-12 23:03 MSK] Получен свежий `logs/bad_requests.log` с продакшена; готовы анализировать паттерны IP/UA.
- [2026-02-12 23:06 MSK] Зафиксирован срез `/var/log/nginx/access.log` (tail 200) с повторяющимися запросами 91.212.150.176 к `/`, `/admin/config.php`, `/.env`, `robots.txt`.
- [2026-02-12 23:08 MSK] Проверены архивы `/var/log/nginx/access.log.*`: актуальные записи за 12–13 февраля и архивы до `access.log.5.gz` (8 февраля) содержат те же атакующие IP/UA, готовы копировать нужный срез.
- [2026-02-12 23:12 MSK] Скопированы свежие nginx access/error logs (access.log, access.log.1, access.log.2-14.gz ...) в `logs/february_logs` для оффлайн-аналитики.
- [2026-02-12 23:14 MSK] Сняли baseline `fail2ban-client status undersun-badrequests` (Currently banned: 8 IP). Конфиг `undersun-badrequests.conf` (maxretry=5, findtime=3600, bantime=86400) сохранён.
- [2026-02-12 23:15 MSK] Проанализированы `logs/february_logs/access.log*`: 3037 запросов от IP 91.212.150.176 (93% без Referer). Топ пути: `/`, `/.git/config`, `/.env`, `/+CSCOL+/Java.jar`; топ UA включают `zgrab`, `Go-http-client`, `HeadlessChrome`.
- [2026-02-12 23:18 MSK] Уточнили, что 91.212.150.176 — наш обратный прокси для трафика из РФ; исключаем его из антибот-аналитики и добавляем в whitelist (fail2ban + будущий scoring).
- [2026-02-12 23:22 MSK] Получен конфиг nginx на прокси: подтверждены заголовки `X-Real-IP`/`X-Forwarded-For`, лог-файлы `/var/log/nginx/undersunestate_proxy_*`, целевой origin `51.79.173.21:443`.
- [2026-02-12 23:26 MSK] Скопированы и распакованы логи прокси (`logs/february_logs/proxy_logs/undersunestate_proxy_access.log*`); готовы анализировать реальные клиентские IP/UA.
- [2026-02-12 23:27 MSK] Бейзлайн по proxy access: 453k запросов, 40k уникальных IP. Топы — Googlebot/Chrome-Lighthouse (74.125.* / 66.249.*), Ahrefs, PetalBot, OpenAI SearchBot; фиксируем всплески 130k хитов 30.01 и 06.02.
- [2026-02-12 23:31 MSK] Запущена Фаза 1: подготовлен документ `docs/phase1_bot_detection.md` с описанием RequestLog, scoring engine и BotDetectionMiddleware.
- [2026-02-12 23:33 MSK] Реализована модель `RequestLog` (apps/core/models.py) и миграция `0019_requestlog` с индексами по IP/score/action.
- [2026-02-21 11:35 MSK] Настроен `BOT_PROTECTION` в settings, добавлен сервис `apps/core/bot_detection.py` и `BotDetectionMiddleware` — запросы скорятся и пишутся в `RequestLog`.
- [2026-02-21 12:33 MSK] Расширен whitelist User-Agent'ов (Google/Bing/Yandex/нейросети/соцсети), чтобы не штрафовать SEO/LLM ботов.
- [2026-02-21 12:34 MSK] Добавлен Screaming Frog в whitelist User-Agent (ручные SEO-аудиты проходят без скоринга).
- [2026-02-21 12:44 MSK] `RequestLog` подключён к Django admin (фильтрация по action/source, просмотр matched_rules).
- [2026-02-21 12:52 MSK] Усилен антибот: запросы без Accept-* заголовков банятся сразу (rule `missing_headers_critical` = 120 баллов, кроме whitelist IP/UA).
- [2026-02-21 12:55 MSK] В админке RequestLog теперь видно расшифровку правил и пороги блокировок → проще анализировать скоринг без консоли.
- [2026-02-21 12:59 MSK] `forbidden_path` теперь даёт 120 баллов (немедленный бан) — попытки доступа к WP/Laravel/backup не проходят.
- [2026-02-21 13:01 MSK] Добавлен `ManualIPBan` + action в админке RequestLog: модераторы могут банить IP в один клик; middleware проверяет ручные баны до скоринга.
- [2026-02-21 13:15 MSK] Добавлено правило `no_referer_combo`: если нет Referer и срабатывает любое другое правило, запрос получает +90 и сразу уходит в бан.
- [2026-02-21 13:24 MSK] Middleware пишет `bot-fastban ...` в `bad_requests.log` при action=block → можно завести отдельный fail2ban jail для мгновенных банов.
- [2026-02-21 13:32 MSK] Добавили `ChatGPT-User` (OpenAI Browse) в whitelist User-Agent — его запросы пропускаем.
- [2026-02-21 13:41 MSK] Фаза 1 (скоринг + RequestLog + fail2ban интеграции) завершена, переходим к Ф1.5/Ф2.
- [2026-02-21 13:48 MSK] Фаза 1.5 завершена: whitelist/blacklist актуализированы, ForbiddenPath/fastban/reCAPTCHA проверены.
- [2026-02-21 13:51 MSK] Включён JS challenge: base.html генерирует `bot_challenge_token`, middleware проверяет cookie/hidden поле и добавляет правила `js_challenge_missing`/`failed`.
- [2026-02-21 14:02 MSK] Админский IP 95.161.221.91 добавлен в whitelist (не участвует в скоринге/fastban).
- [2026-02-21 18:02 MSK] Реализован промежуточный challenge (страница-задержка) — первый подозрительный визит получает JS cookie и не грузит основной HTML.
- [2026-02-21 17:40 MSK] `js_challenge_failed` теперь даёт 120 баллов (мгновенный бан) — скрипты без JS не проходят.
- [2026-02-12 23:29 MSK] Фаза 0 завершена: определены whitelist/blacklist (прокси, валидные боты, подозрительные IP), собраны все baseline-данные и обновлены документы.
- [2026-02-22 16:10 ICT] На prod nginx (51.79.173.21) включён real IP chain: `set_real_ip_from 91.212.150.176; real_ip_header X-Forwarded-For; real_ip_recursive on;` — теперь middleware видит реальные клиентские IP от фронтового прокси.
- [2026-02-22 16:25 ICT] `BOT_PROTECTION['WHITELIST_IPS']` очищен от 91.212.150.176 — трафик через фронтовый nginx больше не обходит скоринг (останется только админский IP 95.161.221.91).
- [2026-02-22 16:40 ICT] Усилены веса правил (`js_challenge_missing`=40, `no_referer`=20) и добавлено правило `single_html_hit` (+30) для однохоповых HTML-запросов без последующих статических хитів.
- [2026-02-22 16:55 ICT] В whitelist UA добавлены `meta-externalagent` (Meta crawler) и `Amazonbot` — разрешаем предпросмотры ссылок для Facebook/Amazon.
- [2026-02-22 17:20 ICT] Яндекс.Метрика грузится отложенно (только после cookie `bot_challenge` + пользовательского взаимодействия); добавлен endpoint `/bot/metrika-loaded/` (sendBeacon) для фиксации факта загрузки в RequestLog.
- [2026-02-22 17:30 ICT] Slackbot и TelegramBot добавлены в whitelist UA, чтобы предпросмотры ссылок этих мессенджеров проходили без скоринга.
- [2026-02-22 17:35 ICT] В whitelist добавлены сервисные краулеры (`newsai/1.0`, `MJ12bot`, `SERankingBacklinksBot`, `PerplexityBot`, `TikTokSpider`, `BusinessValidator`) — для сниппетов и SEO-инструментов.
- [2026-02-22 18:10 ICT] Добавлен скрипт `scripts/update_iptoasn_db.py` (скачивает iptoasn TSV) и интегрирован ASN-резолвер в BotDetection (правило `asn_datacenter`, веса для AWS/OVH/Hetzner и т.д.).
- [2026-02-23 11:20 ICT] Убрано правило `no_referer_combo` и снижены веса `no_referer`/`single_html_hit`, чтобы прямой визит не получал 403.
- [2026-02-23 11:30 ICT] Challenge при первом визите отключён, если сработали только базовые правила (`js_challenge_missing`, `no_referer`, `single_html_hit`).
- [2026-02-23 12:10 ICT] Добавлен fallback для отложенной загрузки Яндекс.Метрики: если cookie `bot_challenge` уже выдана, но пользователь не взаимодействует, таймер грузит счётчик через 2 секунды (при видимой вкладке); в консоль выводится notice об инициализации.
- [2026-02-23 12:30 ICT] В BOT_PROTECTION подгружается полный список IP/IPv6 диапазонов Googlebot (из `/seo/googlebot-ip-ranges/*.json`), поэтому краулеры Google проходят по IP без доп. проверок.
- [2026-02-28 18:45 ICT] Для среза по RequestLog добавлен скрипт `scripts/analyze_request_logs.py` (топ IP/ASN за сутки, быстрый анализ паттернов).
- [2026-02-28 19:10 ICT] Усилен скоринг против «китайских» ботов: добавлены веса для ASN China Telecom/Mobile/Unicom, новое правило `high_risk_user_agent` (фиксированный UA Chrome/139) и повышены штрафы `no_referer`/`single_html_hit` — теперь спуферы, отправляющие только `/property + /jsi18n + /bot/metrika-loaded`, получают `block`.
- [2026-03-03 21:20 ICT] Instagram crawler добавлен в `WHITELIST_USER_AGENTS`, а `POST /bot/metrika-loaded/` с реферером с нашего домена больше не увеличивает `js_challenge_missing` (sendBeacon Метрики не попадает в скоринг).
- [2026-03-04 14:15 ICT] Чтобы не блокировать прямые визиты людей, добавлен failover: если сработали только базовые правила (`js_challenge_missing`, `single_html_hit`, `no_referer`, `no_referer_combo`), действие фиксируется как monitor вне зависимости от суммарного score.
- [2026-03-11 11:18 MSK] BotDetectionMiddleware сразу выдаёт cookie `bot_challenge` при allow/monitor-ответах, а фронтенд синхронизирует localStorage и cookie — реальные браузеры получают токен ещё до загрузки основного JS.
- [2026-03-12 00:45 MSK] Failover расширен: базовые правила + `asn_datacenter` с реферером из поисковиков больше не дают бан — такие визиты принудительно переводятся в monitor.
