# Руководство: добавление новых внешних ресурсов

Этот документ описывает, что делать при появлении дополнительных внешних ресурсов (CDN, API, сторонние скрипты) — чтобы сайт продолжал работать при строгих политиках безопасности (CSP) и не ломал существующую интеграцию.

## 1. Определите тип ресурса
Соберите информацию о новом домене/URL:
- **Script** (JS, аналитика, капча, карты)
- **Style** (CSS из CDN, шрифты)
- **Font** (Google Fonts, Font Awesome)
- **Image** (иконки, тайлы карт, пиксели аналитики)
- **Frame/Embed** (YouTube, Google Maps)
- **Connect** (AJAX/fetch/WebSocket/Analytics endpoints)
- **Media** (video/audio)
- **Worker** (Service Worker, Web Worker)

## 2. Обновите CSP
Настройки находятся в `config/settings/production.py`:
- `DEFAULT_SRC`, `CONNECT_SRC`
- `CSP_EXTRA_DIRECTIVES` (dict для `script-src`, `style-src`, `img-src`, `frame-src`, `font-src`, ...)

Добавьте домен в нужную директиву. Примеры:
```python
CONNECT_SRC = "'self' ... https://api.example.com"
CSP_EXTRA_DIRECTIVES = {
    'script-src': "... https://cdn.example.com",
    'img-src': "... https://img.example.com",
    'frame-src': "... https://widgets.example.com",
}
```
Не забудьте:
- **Wildcards**: если используете `https://*.tile.openstreetmap.org`, пропишите со звездой.
- **Inline scripts/styles**: если ресурс требует inlined-кода, убедитесь, что `'unsafe-inline'` или nonce/sha добавлены.
- **WebSocket**: для wss-доменов укажите `wss://example.com` в `connect-src`.

## 3. Проверьте шаблоны/скрипты
Поиск по проекту:
```bash
rg -n "example.com"
```
Убедитесь, что новый ресурс действительно нужен (например, `templates/base.html`, `templates/includes/layout/...`, `static/js/...`).

## 4. Обновите документацию
- В файле `docs/README.md` включите краткое описание нового ресурса (если он постоянный).
- В этом документе (или отдельном changelog) зафиксируйте, когда и зачем добавлен домен.

## 5. Тестирование
1. **Локально**: с включённым debug-сервером проверьте, что браузер не ругается на CSP (консоль DevTools).
2. **Стейдж/прод**: после деплоя мониторьте браузерную консоль и `logs/bad_requests.log`.
3. **Автотест**: (опционально) добавьте smoke-тест, который проверяет, что `<script src="https://cdn.example.com/...">` доступен.

## 6. Откат/Whitelist
- При ошибке браузер сообщит, какой домен заблокирован. Скопируйте сообщение CSP violation и добавьте домен.
- Для внутренних/доверенных доменов используйте `'self'` или специфические URL.
- В крайних случаях временно расширьте директиву `'default-src'`, но лучше явно указать каждую категорию.

## 7. Пример чек-листа
- [ ] Определён тип ресурса (`script`, `img`, `frame`, ...)
- [ ] Добавлен в `CSP_EXTRA_DIRECTIVES` и/или `CONNECT_SRC`
- [ ] Проверены шаблоны/JS на использование
- [ ] Протестировано локально (DevTools → нет CSP ошибок)
- [ ] Обновлена документация (`docs/README.md` и/или changelog)
- [ ] Отслежена консоль на проде после деплоя

Следуйте этому процессу для любого нового внешнего ресурса, чтобы избежать неожиданного блокирования браузером.
