# Яндекс.Метрика: цели для главной страницы

## Герой и поисковая форма
- `hero_view_all` — клик по кнопке «Смотреть все объекты».
- `hero_search_submit` — отправка формы поиска в hero. Параметры: `device=desktop|mobile`.

## Промобаннер
- `promo_banner_click` — клик по промо баннеру. Параметры: `bannerId`, `name`, `lang`.

## Блок Featured Properties
- `featured_tab_switch` — переключение вкладок (Виллы/Квартиры/Дома), параметр `type`.
- `featured_card_click` — клик по карточке (изображение/заголовок/кнопка). Параметры: `id`, `slug`, `type`, `position`, `link`, `render`.
- `featured_catalog_click` — кнопка «Смотреть каталог». 
- `featured_type_shortcut` — переходы по текстовым ссылкам тип/навигация. Параметры `type`, `placement` (top/bottom).

## Форма телефона (hero phone)
- `phone_form_submit` — отправка формы «Нужна подборка недвижимости».

## Секция "Что мы предлагаем"
- `what_section_catalog_click` — CTA «Смотреть все объекты» внутри секции.
- `what_service_click` — ссылки «Подробнее» для карточек услуг. Параметр `service` (slug).

## Секция FAQ
- `faq_form_submit` — отправка формы «Задать вопрос».

## Секция Visit Office
- `visit_open_meeting_modal` — кнопка «Связаться для встречи».
- `visit_show_map` — кнопка «Показать на карте».
- `visit_office_form_submit` — отправка формы записи на встречу.

> Все цели отправляются через data-атрибуты (`data-ym-goal`). Параметры доступны в отчётах через «Параметр цели».
