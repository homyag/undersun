# JavaScript Refactoring Summary

## Текущее разделение

Страница объекта недвижимости (`templates/properties/detail.html`) теперь разделена на два слоя:

1. **Bootstrap-данные (inline)** — подключаются через include `properties/includes/detail_bootstrap.js.html`. Здесь формируются:
   - константы `PROPERTY_IMAGES`, `PROPERTY_ID`, `PROPERTY_TITLE`, `PROPERTY_SLUG`, `PROPERTY_DEAL_TYPE`;
   - словарь `PROPERTY_DATA` с ценами, рассчитанными на сервере через `convert_price`;
   - `MAP_DATA`, `INQUIRY_ENDPOINT`, `TRANSLATIONS`, а также `window.propertyDetailTranslations`;
   - единственный `DOMContentLoaded`‑обработчик, который инициализирует карту Leaflet (если есть координаты) и может использовать переменные из Django.

2. **Функциональная логика** — файл `static/js/properties/detail.js`. В нём находятся все динамические сценарии: галерея, карусель, формы, модалки, переключение валют, избранное и т.д. Файл не содержит шаблонных тегов и может кэшироваться как статик.

## Что осталось inline

- Только данные, зависящие от шаблона: списки изображений, локализованные текстовые константы, рассчитанные сервером цены и ссылки на AJAX‑эндпоинты.
- Минимальный код инициализации карты Leaflet, так как он использует `MAP_DATA` из Django.

## Что вынесено во внешний файл

Все функции из прежнего inline-скрипта живут в `detail.js`:
- управление галереей и каруселью (`openGallery`, `nextImage`, `startAutoCarousel`, и т.д.);
- обработчики форм (`handleFormSubmit`, интеграция с reCAPTCHA, уведомления);
- логика избранного (`toggleFavoriteDetail`, `updateFavoritesCounter`);
- вспомогательные функции (`isMobile`, `shareProperty`, `downloadImage`, `showNotification`, `toggleDescription`, сохранение реферера каталога и пр.).

Таким образом inline-код больше не содержит дублирующих функций — он лишь передаёт данные, а всё поведение реализовано в `detail.js`.

## Результаты

- **Поддерживаемость**: изменение логики требует правок только в `static/js/properties/detail.js`.
- **Минимальный inline**: шаблон использует include на ~80 строк вместо прежних ~900.
- **Чистая ответственность**: Django отвечает за данные и локализацию, фронтенд — за UX-функции.

## Рекомендации по сопровождению

- При добавлении новых данных для JS расширяйте include `detail_bootstrap.js.html`, чтобы не возвращаться к длинным inline-скриптам.
- Любые новые функции, не требующие шаблонных тегов, размещайте в `detail.js` и подключайте через модульные функции или события.
- Следите за порядком подключения: сначала include с данными, затем `detail.js`, как уже сделано в `templates/properties/detail.html`.
