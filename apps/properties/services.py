from django.contrib import messages
from apps.core.services import translation_service
import logging

logger = logging.getLogger(__name__)


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
    fields_to_translate = ['title', 'description', 'short_description', 'address']
    
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
            preserve_html = field_name == 'description' and '<' in russian_value
            
            # Переводим
            translated_text = translation_service.translate_text(
                russian_value, 
                lang, 
                preserve_html=preserve_html
            )
            
            if translated_text:
                setattr(property_obj, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
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
                setattr(feature_obj, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    feature_obj.save()
    logger.info(f"Translation completed for property feature '{feature_obj.name}'")