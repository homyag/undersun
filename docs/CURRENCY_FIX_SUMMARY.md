# Currency Fix Summary

## Status

Этот документ сохранён как исторический change log.

## How To Read It

- Он описывает прошлую фазу исправлений валютного поведения.
- Он не является источником актуальной архитектуры.
- Текущую реализацию нужно смотреть в:
  - `apps/currency/services.py`
  - `apps/currency/views.py`
  - `apps/properties/models.py`
  - `static/js/home/featured-properties.js`
  - `static/js/properties/detail.js`
  - `static/js/favorites/favorites.js`
  - `templates/currency/currency_selector.html`

## Current Architectural Notes

- Выбор валюты хранится в session.
- Дефолтная валюта определяется через `CurrencyPreference` и `CurrencyService`.
- Синхронизация фронтенда идёт через событие `currencyChanged`.
- Источником истины по текущему устройству являются `AGENTS.md`, `docs/ARCHITECTURE.md` и `docs/FUNCTIONS*.md`.
