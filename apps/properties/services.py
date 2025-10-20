from django.contrib import messages
from django.core.exceptions import FieldDoesNotExist
from apps.core.services import translation_service
import logging

logger = logging.getLogger(__name__)


def _trim_field_value(instance, field_name, value):
    """Урезает строку до максимальной длины поля, если она задана."""
    if not isinstance(value, str):
        return value

    try:
        field = instance._meta.get_field(field_name)
        max_length = getattr(field, 'max_length', None)
        if max_length and len(value) > max_length:
            return value[:max_length]
    except (FieldDoesNotExist, AttributeError):
        pass

    return value


def translate_property(property_obj, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит объект недвижимости на указанные языки
    
    Args:
        property_obj: Объект Property
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода (основываясь на translation.py)
    fields_to_translate = [
        'title',
        'description',
        'short_description',
        'address',
        'special_offer',
        'complex_name',
        'urgency_note',
        'architectural_style',
        'material_type',
        'investment_potential',
        'suitable_for',
    ]
    html_fields = {'description', 'investment_potential'}
    
    for lang in target_languages:
        logger.info(f"Translating property '{property_obj.title}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(property_obj, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(property_obj, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Определяем, нужно ли сохранять HTML (для полей с HTML контентом)
            preserve_html = field_name in html_fields and '<' in russian_value
            
            # Переводим
            translated_text = translation_service.translate_text(
                russian_value, 
                lang, 
                preserve_html=preserve_html
            )
            
            if translated_text:
                translated_text = _trim_field_value(property_obj, translated_field_name, translated_text.strip())
                setattr(property_obj, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Переводим SEO-поля, где базовым языком является RU
    seo_fields = [
        ('custom_title', False),
        ('custom_description', False),
        ('custom_keywords', False),
    ]

    for base_field, consider_html in seo_fields:
        source_value = getattr(property_obj, f"{base_field}_ru", '')
        if not source_value:
            continue

        for lang in target_languages:
            target_field_name = f"{base_field}_{lang}"
            existing_value = getattr(property_obj, target_field_name, '')

            if existing_value and not force_retranslate:
                logger.info(f"Skipping {target_field_name} - already translated")
                continue

            preserve_html = consider_html and '<' in source_value
            translated_text = translation_service.translate_text(
                source_value,
                lang,
                preserve_html=preserve_html
            )

            if translated_text:
                translated_text = _trim_field_value(property_obj, target_field_name, translated_text.strip())
                setattr(property_obj, target_field_name, translated_text)
                logger.info(f"Translated {base_field}_ru to {target_field_name}")
            else:
                logger.warning(f"Failed to translate {base_field}_ru to {lang}")

    # Сохраняем изменения
    property_obj.save()
    logger.info(f"Translation completed for property '{property_obj.title}'")


def translate_property_type(property_type_obj, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит тип недвижимости на указанные языки
    
    Args:
        property_type_obj: Объект PropertyType
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода
    fields_to_translate = ['name_display']
    
    for lang in target_languages:
        logger.info(f"Translating property type '{property_type_obj.name_display}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(property_type_obj, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(property_type_obj, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Переводим
            translated_text = translation_service.translate_text(russian_value, lang)
            
            if translated_text:
                translated_text = _trim_field_value(property_type_obj, translated_field_name, translated_text.strip())
                setattr(property_type_obj, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    property_type_obj.save()
    logger.info(f"Translation completed for property type '{property_type_obj.name_display}'")


def translate_developer(developer_obj, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит застройщика на указанные языки
    
    Args:
        developer_obj: Объект Developer
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода
    fields_to_translate = ['name', 'description']
    
    for lang in target_languages:
        logger.info(f"Translating developer '{developer_obj.name}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(developer_obj, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(developer_obj, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Переводим
            translated_text = translation_service.translate_text(russian_value, lang)
            
            if translated_text:
                translated_text = _trim_field_value(developer_obj, translated_field_name, translated_text.strip())
                setattr(developer_obj, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    developer_obj.save()
    logger.info(f"Translation completed for developer '{developer_obj.name}'")


def translate_property_feature(feature_obj, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит характеристику недвижимости на указанные языки
    
    Args:
        feature_obj: Объект PropertyFeature
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода
    fields_to_translate = ['name']
    
    for lang in target_languages:
        logger.info(f"Translating property feature '{feature_obj.name}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(feature_obj, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(feature_obj, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Переводим
            translated_text = translation_service.translate_text(russian_value, lang)
            
            if translated_text:
                translated_text = _trim_field_value(feature_obj, translated_field_name, translated_text.strip())
                setattr(feature_obj, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    feature_obj.save()
    logger.info(f"Translation completed for property feature '{feature_obj.name}'")

def translate_service_entry(service_obj, target_languages=None, force_retranslate=False):
    """Автоматический перевод записей услуг на английский и тайский"""
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']

    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")

    fields_to_translate = ['title', 'description', 'content', 'meta_title', 'meta_description']
    html_fields = {'content'}

    for lang in target_languages:
        logger.info(f"Translating service '{service_obj.title}' to {lang}")

        for field_name in fields_to_translate:
            russian_value = getattr(service_obj, field_name, '')
            if not russian_value:
                continue

            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(service_obj, translated_field_name, '')

            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} — already translated")
                continue

            preserve_html = field_name in html_fields and '<' in russian_value
            translated_text = translation_service.translate_text(
                russian_value,
                lang,
                preserve_html=preserve_html
            )

            if translated_text:
                translated_text = _trim_field_value(service_obj, translated_field_name, translated_text.strip())
                setattr(service_obj, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")

    service_obj.save()
    logger.info(f"Translation completed for service '{service_obj.title}'")
