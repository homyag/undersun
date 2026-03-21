# План защиты от ботов Undersun Estate

## 1. Уже реализованные меры (на январь 2025)

1. **Фильтрация запросов к AJAX-инквайрам**
   - `BadInquiryRequestLoggerMiddleware` теперь возвращает `405` и JSON-ответ на любые non-POST обращения к `/property/ajax/inquiry/<id>/`.
   - Googlebot не блокируется, но его обращения не попадают в обработчик форм, уменьшается шум в `bad_requests.log`.

2. **Расширенный контроль Forbidden-путей**
   - `ForbiddenPathLoggerMiddleware` отслеживает не только `wp-admin`, но и `/.env`, `/wp-json`, `/cgi-bin`, `/vendor`, `/aws`, `/backup`, `/security.txt` и т.д.
   - В логах быстрее выявляются сканеры CMS/конфигов.

3. **Rate limiting и проверка форм**
   - Декоратор `rate_limit` (5 запросов/мин на IP) подключен к AJAX-инквайрам.
   - Добавлена функция `validate_form_security`: проверка honeypot-поля `website` и минимального времени заполнения (≥2 сек).
   - Все ключевые формы (`Property detail`, `Contact`, `QuickConsultation`, `FAQ question`, `Office visit`, `Reviews`, `Blog feedback`, `Service contact`, `Newsletter`) используют include `form_security_fields.html` → сервер отклоняет ботовские сабмиты до recaptcha/ORM.

4. **Защита карточек консультаций на главной**
   - JS-карточки (`static/js/home/featured-properties.js` + `consultation.js`) добавляют скрытое поле и таймер перед отправкой, показывают сообщение при слишком быстром сабмите.

## 2. Следующие шаги в кодовой базе (без продовых действий)

1. **Management-команда анализа логов** ✅
   - Добавлена команда `python manage.py analyze_bad_requests` (аргументы: `--log-path`, `--days`, `--top`).
   - Она разбирает `logs/bad_requests.log`, показывает totals по категориям (`inquiry`, `bad-inquiry-invalid-method`, `forbidden-path`), разбивку по дням, топы IP/путей/UA и долю запросов от Googlebot (`66.249.*` или UA с Googlebot).
   - Пример запуска на проде: `python manage.py analyze_bad_requests --days 1 --top 20`.
   - Следующий шаг — обернуть её в cron/Slack-уведомления (см. раздел 3.1).

2. **Кастомный logging handler**
   - В `LOGGING` добавить handler, который на каждый `bad_requests` пишет сжатую статистику (например, в Redis/SQLite) для оперативного мониторинга.

3. **Дополнительные формы**
   - Проверить всех получателей (например, формы ROS/шаблоны в других apps) и подключить `form_security_fields` + `validate_form_security` при необходимости.

4. **Массовый бан подозрительных IP** ✅
   - Добавлена команда `python manage.py ban_bad_requests --days 30 --min-count 3 --ban --email security@undersunestate.com`.
   - Она парсит `logs/bad_requests.log`, выводит IP с количеством событий ≥ порога и (при `--ban`) вызывает `fail2ban-client set undersun-badrequests banip <IP>`.
   - Опция `--email` отправляет отчёт через утилиту `mail` (необходимо установленное `mailutils`), поэтому можно запускать её вручную или по расписанию (например, раз в неделю).

## 3. Автоматизация и мониторинг на продакшене (Ubuntu 22.04)

### 3.1 Установка cron-задачи

1. **Подготовить каталог для отчёта** (если ещё не создан):
   ```bash
   mkdir -p /home/ubuntu/undersun/logs
   ```

2. **Проверить виртуальное окружение** и сделать пробный запуск вручную:
   ```bash
   cd /home/ubuntu/undersun
   source /home/ubuntu/venv/bin/activate
   python manage.py analyze_bad_requests --days 1 --top 20 > logs/bad_requests_daily.txt
   ```
   Если файл появился и содержит отчёт — всё готово к автоматизации.

3. **Добавить cron-задачу**. Создаём файл `/etc/cron.d/undersun_bad_requests` (нужны права root) со строкой:
   ```cron
   5 1 * * * ubuntu cd /home/ubuntu/undersun && /home/ubuntu/venv/bin/python manage.py analyze_bad_requests --days 1 --top 20 > /home/ubuntu/undersun/logs/bad_requests_daily.txt
   ```
   - `ubuntu` — пользователь, под которым крутится приложение (можно заменить на `www-data`, если удобнее).
   - Путь проекта: `/home/ubuntu/undersun`.
   - Виртуальное окружение: `/home/ubuntu/venv`.
   - Отчёт будет переписываться ежедневно (если нужно архивировать, добавьте `>>` или `tee -a`).

4. **Отправка уведомлений** (опционально):
   - Для email: `... | mail -s "Bad requests (24h)" security@undersunestate.com` (требуются `mailutils/postfix`).
   - Для Slack: после генерации отчёта вызвать `curl -X POST -H 'Content-type: application/json' --data '{"text":"'"$(cat /home/ubuntu/undersun/logs/bad_requests_daily.txt | sed 's/"/\"/g')"'"}' https://hooks.slack.com/...`.

5. **Проверка cron**: `sudo run-parts --test /etc/cron.d` или `grep CRON /var/log/syslog` убедится, что задача выполняется.

6. **Уведомления Fail2ban**: в `/etc/fail2ban/jail.d/undersun-badrequests.conf` можно добавить:
   ```
   destemail = security@undersunestate.com
   sender = noreply@undersunestate.com
   action = %(action_mwl)s
   ```
   После этого `fail2ban-client reload` и при бане придёт письмо с логами/кто забанен.

7. **Автоматический массовый бан**: в `/etc/cron.d/undersun_mass_ban` запускаем команду:
   ```cron
   0 1 * * * ubuntu cd /home/ubuntu/undersun && /home/ubuntu/venv/bin/python manage.py ban_bad_requests --days 1 --min-count 2 --ban
   ```
   Она раз в сутки анализирует лог за последние 24 часа и тут же добавляет в банлист IP, которые попались хотя бы 2 раза (без email, пока не настроен relay).

### 3.2 Fail2ban / ufw для автоматической блокировки

1. Создать фильтр `/etc/fail2ban/filter.d/undersun-badrequests.conf`:
   ```
   [Definition]
   failregex = ^WARNING .* forbidden-path .* ip=<HOST>
                ^WARNING .* bad-inquiry-invalid-method .* ip=<HOST>
   ```
2. Джейл `/etc/fail2ban/jail.d/undersun-badrequests.conf`:
   ```
   [undersun-badrequests]
   enabled  = true
   port     = http,https
   filter   = undersun-badrequests
   logpath  = /home/ubuntu/undersun/logs/bad_requests.log
   maxretry = 1
   findtime = 600
   bantime  = 86400
   destemail = security@undersunestate.com
   sender = noreply@undersunestate.com
   action = %(action_mwl)s
   ```
3. Перезапустить fail2ban: `sudo systemctl restart fail2ban` и проверить `fail2ban-client status undersun-badrequests`.

### 3.3 Nginx rate limiting

1. В `/etc/nginx/conf.d/rate_limit.conf` добавить:
   ```nginx
   limit_req_zone $binary_remote_addr zone=ajax_inquiry:10m rate=30r/m;
   limit_req_zone $binary_remote_addr zone=forbidden_scan:10m rate=10r/m;
   ```
2. В серверном блоке:
   ```nginx
   location ~ ^/(ru|en|th)/property/ajax/inquiry/\d+/ {
       limit_req zone=ajax_inquiry burst=10 nodelay;
   }

   location ~ ^/(administrator|wp-admin|wp-login\.php|wp-json|xmlrpc\.php|phpmyadmin|pma)/ {
       limit_req zone=forbidden_scan burst=5;
       return 444;
   }
   ```
3. Проверить конфиг `nginx -t` и перезагрузить `systemctl reload nginx`.

### 3.4 Логирование в централизованное хранилище

- Настроить Filebeat/rsyslog → ELK/Datadog, чтобы фильтровать паттерны и строить алерты без cron.
- Альтернатива: использовать `systemd` unit для `analyze_bad_requests --watch`, который читает файл через `tail -F` и отправляет события вебхуком.

## 4. Руководство по реагированию

1. **Проверить лог**: `tail -n 50 logs/bad_requests.log` → смотрим IP/маршрут.
2. **Проверить IP**: `whois 66.249.79.139`, для Googlebot — `host 66.249.79.139` → должно кончаться `.googlebot.com`.
3. **Блокировка**: `sudo ufw deny from <IP>`, либо `fail2ban-client set undersun-badrequests banip <IP>`.
4. **Ревью записей**: если ложные срабатывания (легитимный партнер), добавить IP в список исключений (`ALLOWED_BAD_REQUEST_IPS` в настройках logging handler’а или fail2ban `ignoreip`).

## 5. Ответственные за исполнение

- **Backend**: поддерживает middleware, rate limit, команду анализа.
- **DevOps**: внедряет cron/fail2ban/nginx-лимиты, обновляет runbook и мониторит алерты.
- **Support**: получает отчеты и при необходимости эскалирует блокировку IP/подозрительные активности.

Документ обновлять по мере внедрения новых правил или перехода на централизованный мониторинг.
