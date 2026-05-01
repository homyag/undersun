# Nginx конфигурация Undersun Estate

Этот файл фиксирует расположение и ключевые настройки nginx на прокси-сервере (v2980957) и на prod-сервере (51.79.173.21). Обновляйте его при изменении конфигов.

## Proxy (v2980957)
- Корневой конфиг: `/etc/nginx/nginx.conf`
- Виртуальный хост: `/etc/nginx/sites-available/undersunestate.com` → symlink в `sites-enabled`
- Основные параметры:
  - `upstream undersunestate_origin { server 51.79.173.21:443; keepalive 20; }`
  - HTTPS listener (`listen 443 ssl http2; server_name undersunestate.com`) с сертификатами Let’s Encrypt (`/etc/letsencrypt`)
  - Проксирование всех путей:
    ```nginx
    location / {
        proxy_pass https://undersunestate_origin;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_request_buffering off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_ssl_server_name on;
        proxy_ssl_name undersunestate.com;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }
    ```
  - HTTP → HTTPS редирект (`listen 80` блок)
  - `.well-known/acme-challenge` отдаётся из `/var/www/html` для certbot

## Prod (51.79.173.21)
- Корневой конфиг: `/etc/nginx/nginx.conf`
- Сайт: `/etc/nginx/sites-available/undersun` → symlink в `sites-enabled`
- Сертификаты: `/etc/letsencrypt/live/undersunestate.com` (тот же домен)
- Основные блоки:
  - `limit_req_zone`, `limit_conn_zone` и карта `$bad_ua` в начале файла
  - default server (`listen 443 default_server ssl http2; server_name _; return 444;`)
  - HTTP → HTTPS редирект (`listen 80; return 301 https://undersunestate.com$request_uri;`)
  - Основной сервер `undersunestate.com`:
    - Логи: `access_log /var/log/nginx/example.log`
    - Лимиты: `limit_conn conn 20`, `limit_req` для `/` и `/currency/rates/`
    - Блокировка опасных путей (regex в `location ~* ... { return 444; }`)
    - Отдача статики/медиа из `/home/ubuntu/undersun/staticfiles` и `/home/ubuntu/undersun/media`
    - Проксирование в локальный gunicorn (`proxy_pass http://127.0.0.1:8000`) с заголовками:
      ```nginx
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      ```
    - Таймауты: `proxy_read_timeout/proxy_connect_timeout/proxy_send_timeout 60s`
  - `www` поддомен редиректится на основное имя

## Примечания
- **Логи:**
  - Прокси: `/var/log/nginx/undersunestate_proxy_access.log`, `/var/log/nginx/undersunestate_proxy_error.log`
  - Prod: `/var/log/nginx/example.log` + системные `/var/log/nginx/access.log`
- **Изменения real IP:** для корректного определения клиента на бэкенде нужно добавить на prod nginx:
  ```nginx
  set_real_ip_from 91.212.150.176;
  real_ip_header X-Forwarded-For;
  real_ip_recursive on;
  ```
  и убрать `91.212.150.176` из Django `BOT_PROTECTION['WHITELIST_IPS']`.
- После правок не забывайте `sudo nginx -t && sudo systemctl reload nginx`.
