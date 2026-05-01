# Яндекс.Метрика: цели для страницы объекта недвижимости

Ниже собраны все JavaScript-цели, которые отправляются со страницы `properties/detail.html`, и контекст их использования.

## Цели для форм
| Идентификатор | Форма / действие | Описание параметров |
|---------------|------------------|---------------------|
| `property_custom_selection_submit` | Форма "Индивидуальный подбор" (блок после похожих объектов) | `form=custom_selection`, `propertyId` — ID текущего объекта |
| `property_newsletter_submit` | Подписка на новости (нижний блок) | `form=newsletter`, `propertyId` |
| `property_viewing_submit` | Модалка "Записаться на просмотр" | `form=viewing`, `propertyId` |
| `property_consultation_submit` | Модалка "Получить консультацию" | `form=consultation`, `propertyId` |
| `property_callback_submit` | Модалка "Заказать звонок" | `form=callback`, `propertyId` |

## Кнопки и ссылки
| Идентификатор | Где срабатывает | Параметры |
|---------------|-----------------|-----------|
| `property_call_click` | Все ссылки `tel:` (основной блок, альтернативные блоки, office info, модалки) | `context` (например, `sidebar_primary`, `cta_buttons`, `office_info`, `viewing_modal_alt`, `consultation_modal_alt`), `propertyId` |
| `property_whatsapp_click` | Все ссылки на WhatsApp (включая правильный URL агента и fallback) | `context`, `propertyId` |
| `property_callback_button` | Кнопка "Заказать звонок" рядом с ценой | `context=cta_bar`, `propertyId` |

## Галерея и избранное
| Идентификатор | Действие | Параметры |
|---------------|---------|-----------|
| `property_gallery_open` | Открытие полноэкранной галереи | `index` (номер изображения), `propertyId` |
| `property_gallery_download` | Кнопка «Скачать» в галерее | `index`, `propertyId` |
| `property_gallery_share` | Кнопка «Поделиться» в галерее | `index`, `propertyId` |
| `property_share_click` | Кнопка «Поделиться» на основном слайдере | `propertyId` |
| `property_favorite_toggle` | Избранное (карточка/карусель) | `status=add/remove`, `propertyId` |

## Модальные окна
| Идентификатор | Описание |
|---------------|---------|
| `property_details_modal_open` | Нажатие "Уточнить детали" (открытие модалки консультации) |
| `property_viewing_modal_open` | Клик по "Записаться на просмотр" (открытие модалки) |
| `property_consultation_modal_open` | Запуск модалки консультации (вместо виджета) |

> Все JS-события шлются через `window.dispatchMetrikaGoal`. При добавлении новых CTA на карточке объекта используйте один из существующих идентификаторов или заведите новый и опишите его здесь.
