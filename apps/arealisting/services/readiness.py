"""Publication checklist for a Property linked to AREALISTING."""

from apps.properties.models import PropertyImage
from django.utils.html import strip_tags
from ..models import ArealistingPriceReview


def publication_readiness(group):
    prop = group.property
    if prop is None:
        return {'ready': False, 'checks': []}

    available = group.units.filter(
        is_deleted=False,
        sync_enabled=True,
        availability_status='AVAILABLE',
    ).count()
    has_photo = PropertyImage.objects.filter(property=prop).exclude(image='').exists()
    has_description = bool(strip_tags(prop.description or '').strip())
    pending_price = group.price_reviews.filter(
        status=ArealistingPriceReview.Status.PENDING,
    ).first()
    missing_core = [
        label for label, present in (
            ('название', bool(prop.title.strip())),
            ('URL', bool(prop.slug)),
            ('тип недвижимости', bool(prop.property_type_id)),
            ('район', bool(prop.district_id)),
        ) if not present
    ]
    checks = [
        {
            'key': 'source', 'title': 'Связь с источником', 'required': True,
            'ok': not group.project.is_deleted,
            'detail': ('Комплекс доступен в AREALISTING.' if not group.project.is_deleted
                       else 'Комплекс удалён в источнике. Проверьте связь.'),
            'action': 'group', 'action_label': 'Проверить связь',
        },
        {
            'key': 'units', 'title': 'Доступные предложения', 'required': True,
            'ok': available > 0,
            'detail': (f'Выбрано доступных предложений: {available}.' if available
                       else 'Нет выбранных доступных предложений. Проверьте состав связи и статусы.'),
            'action': 'matching', 'action_label': 'Подобрать предложения',
        },
        {
            'key': 'price', 'title': 'Цена продажи', 'required': True,
            'ok': prop.price_sale_thb is not None and prop.price_sale_thb > 0,
            'detail': ('Цена в THB заполнена.' if prop.price_sale_thb is not None and prop.price_sale_thb > 0
                       else 'В карточке нет положительной цены в THB. Проверьте выбранные предложения и курс.'),
            'action': 'property', 'action_label': 'Проверить цену',
        },
        {
            'key': 'price_review', 'title': 'Подтверждение изменения цены', 'required': True,
            'ok': pending_price is None,
            'detail': ('Нет ожидающих предложений цены.' if pending_price is None
                       else f'Новая цена отличается на {pending_price.change_percent}% и ждёт решения.'),
            'action': 'price_review', 'action_label': 'Проверить предложение',
            'review_id': pending_price.pk if pending_price else None,
        },
        {
            'key': 'photo', 'title': 'Фотографии', 'required': True,
            'ok': has_photo,
            'detail': ('В карточке есть фотография.' if has_photo
                       else 'В карточке нет фотографии. Импортируйте материалы или добавьте фото вручную.'),
            'action': 'group', 'action_label': 'Открыть импорт фото',
        },
        {
            'key': 'core', 'title': 'Основные данные', 'required': True,
            'ok': not missing_core,
            'detail': ('Название, URL, тип и район заполнены.' if not missing_core
                       else 'Не заполнено: ' + ', '.join(missing_core) + '.'),
            'action': 'property', 'action_label': 'Заполнить карточку',
        },
        {
            'key': 'description', 'title': 'Описание', 'required': True,
            'ok': has_description,
            'detail': ('Описание заполнено.' if has_description
                       else 'Добавьте описание, чтобы посетитель понимал предложение.'),
            'action': 'property', 'action_label': 'Добавить описание',
        },
        {
            'key': 'area', 'title': 'Площадь', 'required': False,
            'ok': prop.area_total is not None and prop.area_total > 0,
            'detail': ('Общая площадь заполнена.' if prop.area_total is not None and prop.area_total > 0
                       else 'Рекомендуется проверить и указать общую площадь.'),
            'action': 'property', 'action_label': 'Проверить площадь',
        },
    ]
    if group.validation_errors:
        checks.append({
            'key': 'errors', 'title': 'Ошибки синхронизации', 'required': False,
            'ok': False, 'detail': '; '.join(str(error) for error in group.validation_errors),
            'action': 'group', 'action_label': 'Посмотреть ошибки',
        })
    return {
        'ready': all(check['ok'] for check in checks if check['required']),
        'checks': checks,
        'required_missing': sum(not check['ok'] for check in checks if check['required']),
        'warnings': sum(not check['ok'] for check in checks if not check['required']),
    }
