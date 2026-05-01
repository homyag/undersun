# Яндекс.Метрика: цели для каталога недвижимости

## Фильтры, сортировка, переключение вида
- `catalog_filters_submit` — любое применение фильтров (включая авто-сабмит). Параметры: `trigger` (имя поля или `manual`), `origin` (`auto|manual|sort`).
- `catalog_filters_reset` — ссылка «Очистить».
- `catalog_mobile_filters_toggle` — раскрытие/сворачивание мобильных фильтров (`state=open|close`).
- `catalog_sort_change` — смена сортировки (`sort=...`).
- `catalog_view_change` — переключение вида `grid|map`.

## Карточки, избранное, карта
- `catalog_card_click` — клики по карточкам (изображение/текст/CTA). Параметры: `id`, `slug`, `type`, `position`, `link`, `render`.
- `catalog_map_popup_click` — клики по ссылкам в попапах карты. Параметры: `id`, `slug`, `type`, `link` (`price|cta`).
- `catalog_map_whatsapp_click` — кнопка WhatsApp в попапе карты.

## Прочее
- `catalog_sort_change` / `catalog_view_change` уже перечислены выше.
- `catalog_filters_submit` служит основным событием для анализа поведения фильтров (фронтенд добавляет параметры).

> Все события идут через data-атрибуты (в шаблонах) или JS-хелпер `firePropertyGoal` (если понадобятся дополнительные действия).
