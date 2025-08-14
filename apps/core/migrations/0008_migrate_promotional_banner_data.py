# Generated manually for migrating promotional banner translation data

from django.db import migrations


def migrate_promotional_banner_translations(apps, schema_editor):
    """Перенос переводов из modeltranslation полей в новую модель"""
    PromotionalBanner = apps.get_model('core', 'PromotionalBanner')
    PromotionalBannerTranslation = apps.get_model('core', 'PromotionalBannerTranslation')
    
    # Языки для миграции
    languages = ['ru', 'en', 'th']
    
    for banner in PromotionalBanner.objects.all():
        for lang in languages:
            # Получаем значения для каждого языка
            title_field = f'title_{lang}' if lang != 'ru' else 'title'
            description_field = f'description_{lang}' if lang != 'ru' else 'description'
            discount_text_field = f'discount_text_{lang}' if lang != 'ru' else 'discount_text'
            button_text_field = f'button_text_{lang}' if lang != 'ru' else 'button_text'
            
            # Проверяем наличие полей (могут отсутствовать при первом запуске)
            title = getattr(banner, title_field, '') if hasattr(banner, title_field) else ''
            description = getattr(banner, description_field, '') if hasattr(banner, description_field) else ''
            discount_text = getattr(banner, discount_text_field, '') if hasattr(banner, discount_text_field) else ''
            button_text = getattr(banner, button_text_field, '') if hasattr(banner, button_text_field) else ''
            
            # Создаем перевод только если есть данные (хотя бы заголовок)
            if title:
                PromotionalBannerTranslation.objects.get_or_create(
                    banner=banner,
                    language_code=lang,
                    defaults={
                        'title': title or f'Баннер {banner.pk} ({lang.upper()})',
                        'description': description or '',
                        'discount_text': discount_text or '',
                        'button_text': button_text or '',
                    }
                )
            elif lang == 'ru':
                # Для русского языка создаем запись в любом случае
                PromotionalBannerTranslation.objects.get_or_create(
                    banner=banner,
                    language_code=lang,
                    defaults={
                        'title': f'Баннер {banner.pk}',
                        'description': '',
                        'discount_text': '',
                        'button_text': '',
                    }
                )


def reverse_migrate_promotional_banner_translations(apps, schema_editor):
    """Обратная миграция - копируем данные обратно в основную модель"""
    PromotionalBanner = apps.get_model('core', 'PromotionalBanner')
    PromotionalBannerTranslation = apps.get_model('core', 'PromotionalBannerTranslation')
    
    # Получаем все переводы
    translations = PromotionalBannerTranslation.objects.select_related('banner')
    
    for translation in translations:
        banner = translation.banner
        lang = translation.language_code
        
        # Определяем имена полей
        title_field = f'title_{lang}' if lang != 'ru' else 'title'
        description_field = f'description_{lang}' if lang != 'ru' else 'description'
        discount_text_field = f'discount_text_{lang}' if lang != 'ru' else 'discount_text'
        button_text_field = f'button_text_{lang}' if lang != 'ru' else 'button_text'
        
        # Устанавливаем значения если поля существуют
        if hasattr(banner, title_field):
            setattr(banner, title_field, translation.title)
        if hasattr(banner, description_field):
            setattr(banner, description_field, translation.description)
        if hasattr(banner, discount_text_field):
            setattr(banner, discount_text_field, translation.discount_text)
        if hasattr(banner, button_text_field):
            setattr(banner, button_text_field, translation.button_text)
        
        banner.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_add_promotional_banner_translation'),
    ]

    operations = [
        migrations.RunPython(
            migrate_promotional_banner_translations,
            reverse_migrate_promotional_banner_translations,
        ),
    ]