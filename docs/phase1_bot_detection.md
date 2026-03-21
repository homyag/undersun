# Phase 1 — Bot detection scoring в Django

Цель: собрать все сигналы о подозрительных запросах в одной точке (RequestLog + BotDetectionMiddleware), начислять bot_score и на его основе принимать решение (log/monitor → JS challenge → блок → fail2ban).

## Архитектура
1. **Модель `RequestLog`** (apps/core/models.py)
2. **Сервис `apps/core/services/bot_detection.py`** — набор правил и калькулятор score
3. **Middleware `BotDetectionMiddleware`** — подключается после прокси-aware middlewares, работает до вьюшек
4. **Интеграция с fail2ban** — high score → запись в `bad_requests.log` + опциональный бан сразу в Django
5. **Management-команды** — обновить `analyze_bad_requests`/`ban_bad_requests` для чтения новой модели

## RequestLog (миграция)
| Поле | Тип | Комментарий |
|------|-----|-------------|
| `id` | PK | |
| `created_at` | DateTime | `auto_now_add`, индекс
| `client_ip` | GenericIPAddressField | исходный IP (из `X-Real-IP`/`X-Forwarded-For`)
| `proxy_ip` | GenericIPAddressField (null) | IP прокси (REMOTE_ADDR) — поможет отделять hops
| `user_agent` | TextField | User-Agent (truncate до 512 символов)
| `method`, `path`, `referer` | CharField | хранить путь/request line
| `status_code` | SmallInteger | Ответ, если есть (для post-response логирования)
| `headers` | JSONField (null) | ключевые заголовки (Accept-Language, Accept-Encoding, Sec-*)
| `bot_score` | SmallInteger | итоговый score 0-200
| `matched_rules` | JSONField | список `{rule, weight}`
| `action` | CharField | `allow`, `monitor`, `challenge`, `block`
| `source` | CharField | `middleware`, `nginx_ingest`, `management`

Индексы: `(client_ip, created_at)`, `bot_score`, `action`.

## BotDetectionService
Файл `apps/core/services/bot_detection.py`:

```python
@dataclass
class DetectionInput:
    request: HttpRequest
    client_ip: str
    proxy_ip: str | None
    headers: dict
    path: str
    method: str

@dataclass
class DetectionResult:
    score: int
    action: str  # allow/monitor/challenge/block
    rules: list[RuleMatch]
```

### Правила (начальные веса)
| Сигнал | Вес |
|--------|-----|
| Запрос к forbidden path (паттерны из существующего middleware) | +35 |
| User-Agent в списке запрещённых (curl, python-requests, HeadlessChrome без разрешения) | +25 |
| Нет Referer + все ресурсы HTML-only (не грузит статику) | +10 |
| Accept-Language пустая, Accept-Encoding = `identity`, Sec-headers отсутствуют | +10 |
| Высокая частота от IP: ≥5 запросов за 10 сек (через cache) | +20 |
| IP из blacklist seeds (см. раздел baseline) | +40 |
| Попытки доступа к WP/Laravel бэкдорам (regex) | +30 |
| Метод HEAD/OPTIONS на HTML страницах без follow-up | +10 |
| Known proxy/cloud ASN (placeholder, подключим в Ф3) | +15 |

Порог действия:
- `score <= 30`: allow (`RequestLog` записываем, но не блокируем)
- `31-60`: monitor → только логируем и, при желании, отправляем в Sentry
- `61-90`: challenge → отдаём JS/cookie тест (будет в Ф2)
- `91-100`: respond 403, но без fail2ban (soft block)
- `>100`: возвращаем 403/444 и пишем в `bad_requests.log` для fail2ban

Конфиг: вынести веса и пороги в `settings.BOT_PROTECTION`.

## BotDetectionMiddleware
- Опирается на `RequestHandlerMixin`:
  1. Определить `client_ip` (берём первый IP из `X-Forwarded-For`, fallback `REMOTE_ADDR`)
  2. Игнорировать `client_ip` из whitelist (прокси 91.212.150.176, Googlebot)
  3. Сформировать `DetectionInput` и передать в сервис
  4. Сохранить `RequestLog`
  5. Если action == `block`, вернуть `HttpResponseForbidden`
  6. Если action >= monitor, вывести запись в `bad_requests.log` (чтобы fail2ban видел)

### Очередность
`MIDDLEWARE` (settings): поместить после `ForbiddenPathLoggerMiddleware`, но до `CommonMiddleware`, чтобы успеть заблокировать.

## Связь с текущими компонентами
- **ForbiddenPathLoggerMiddleware**: переиспользуем правила внутри сервиса, middleware лишь помечает событие
- **nginx_bad_requests_ingest.py**: при парсинге логов создаём `RequestLog` с `source='nginx'`
- **Management-команды**: обновить `analyze_bad_requests` чтобы читать RequestLog и агрегировать score, User-Agent, ASN

## TODO список (Ф1)
1. Добавить модель `RequestLog` и миграцию (apps/core/migrations/xxxx_request_log.py)
2. Создать `apps/core/services/bot_detection.py`
3. Добавить `BotDetectionMiddleware` в `apps/core/middleware.py`, зарегистрировать в settings
4. Расширить `settings.py` конфигами `BOT_PROTECTION = {...}` (пороги, whitelist/blacklist, веса)
5. Обновить `nginx_bad_requests_ingest.py` и management-команды для записи в RequestLog
6. Написать тесты для сервиса (unit-тесты на правила) и middleware (разные заголовки/UA)
7. Документация: обновить `docs/bad_requests_ban.md` и текущий pipeline

После реализации: включаем режим monitor (action>=monitor → логируем, но не блочим), выходим на prod, собираем статистику и только потом включаем блокировки.

## Фаза 2 (JS Challenge) — план
- Добавить в `templates/base.html` лёгкий challenge (JS → localStorage + hidden поле `bot_challenge_token`).
  * При первом заходе JS генерирует токен (timestamp + hash), пишет в cookie/localStorage и добавляет `<input type="hidden" name="bot_challenge_token">` в каждую форму/запрос.
  * Для ресурсов, которые не отправляют формы (простые GET), можно задействовать сервис worker, который ставит cookie `bot_challenge=ok` после успешной загрузки JS.
- Middleware проверяет `request.COOKIES['bot_challenge']` (или POST-поле). Если токена нет → добавляет правило `js_challenge_missing` (например +25); если challenge не пройден повторно (после первого ответа) → `js_challenge_failed` (+60 → `action=challenge`).
- Challenge обходится для whitelist UA/IP, статики (`/static`, `/media`) и API, где JS не работает.
- RequestLog фиксирует matched rule `js_challenge_failed`; в будущем можно показывать в админке, сколько визитов не прошли challenge.
- При action=`challenge` отдаём страницу-редиректор с JS проверкой (например, скрипт, который устанавливает cookie и делает reload → после reload запрос уже содержит токен).
- После внедрения: сначала включаем в режиме “наблюдение” (только записи), потом добавляем реальный блок.
