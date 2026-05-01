# Featured Properties Currency Update

## Status

Этот файл сохранён как исторический change log по эволюции валютного поведения в блоке featured properties.

## Current Source Of Truth

Актуальную реализацию нужно смотреть в:

- `apps/core/views.py`
- `static/js/home/featured-properties.js`
- `templates/core/home.html`
- `templates/currency/currency_selector.html`

## Current Architectural Notes

- Блок featured properties получает серверный bootstrap payload и рендерится клиентским модулем.
- Обновление валюты завязано на `currencyChanged`.
- Логика блока больше не должна документироваться через старые line-by-line notes; текущая структура отражена в `docs/AGENT.md` и `docs/FUNCTIONS*.md`.
