# Инструкция: добавление целей Яндекс.Метрики

## 1. Когда использовать data-атрибуты
Если событие инициируется кликом/submit/change по DOM-элементу, добавьте атрибуты прямо в шаблон:
```html
<button
  data-ym-goal="catalog_filters_reset"
  data-ym-param-context="sidebar"
  data-ym-event="click">
  Очистить
</button>
```
- `data-ym-goal` — идентификатор цели.
- `data-ym-event` (опционально) — событие (по умолчанию `click`). Поддерживаются `click`, `submit`, `change`.
- `data-ym-param-*` — дополнительные параметры (преобразуются в объект: `context`, `propertyId`, и т.д.).
- `data-ym-params` — можно передать JSON строкой.
- `data-ym-once="true"` — сработает один раз (после отправки атрибут отключается).

Слушатель (`static/js/analytics/metrika-goals.js`) автоматически обрабатывает эти атрибуты и вызывает `window.trackMetrikaGoal`.

## 2. Когда нужен JavaScript helper
Если событие нельзя повесить на DOM (например, галерея, автослайдер, AJAX), используйте `window.dispatchMetrikaGoal`:
```js
function shareProperty() {
    window.dispatchMetrikaGoal('property_share_click', {
        propertyId: PROPERTY_ID,
        source: 'carousel'
    });
}
```
Helper определён в `static/js/analytics/metrika-goals.js`. Он проксирует вызов в `trackMetrikaGoal`/`ym` и принимает произвольный объект параметров.

### Utility функции
- `firePropertyGoal` (в `static/js/properties/detail.js`) — обёртка, которая автоматически добавляет `propertyId` и вызывает `dispatchMetrikaGoal`.
- Похожую функцию можно создать для других страниц, если однотипные события повторяются.

## 3. Настройка цели в Метрике
1. В интерфейсе Метрики перейдите в «Цели» → «Добавить цель».
2. Выберите тип «JavaScript-событие».
3. Укажите идентификатор (например, `property_viewing_submit`).
4. Сохраните; цель начнёт фиксироваться сразу после деплоя.

## 4. Документация по существующим целям
- [METRIKA_GOALS_HOME.md](./METRIKA_GOALS_HOME.md) — главная страница.
- [METRIKA_GOALS_CATALOG.md](./METRIKA_GOALS_CATALOG.md) — каталог.
- [METRIKA_GOALS_PROPERTY_DETAIL.md](./METRIKA_GOALS_PROPERTY_DETAIL.md) — карточка объекта.

Перед добавлением новой цели:
- Проверьте, не существует ли уже нужный идентификатор (ищите `data-ym-goal` или `dispatchMetrikaGoal` по проекту).
- Если цель уникальная, разработайте консистентное имя (например, `секция_действие`, латиницей).
- Обновите соответствующий справочник `.md` (из списка выше) — там хранится описание всех goal id.

## 5. Чек-лист
- [ ] Добавлены атрибуты `data-ym-goal` **или** вызов `dispatchMetrikaGoal`.
- [ ] При необходимости — параметры (`data-ym-param-*` или объект в JS).
- [ ] Идентификатор цели явно описан в одном из файлов `docs/METRIKA_GOALS_*.md`.
- [ ] Цель заведена в интерфейсе Метрики (тип JS-событие).
- [ ] Проверено в DevTools/отладчике Метрики, что событие отправляется.
