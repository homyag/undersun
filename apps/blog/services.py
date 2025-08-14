from django.contrib import messages
from apps.core.services import translation_service
import logging

logger = logging.getLogger(__name__)


def translate_blog_post(blog_post, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит статью блога на указанные языки
    
    Args:
        blog_post: Объект BlogPost
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода
    fields_to_translate = ['title', 'excerpt', 'content', 'meta_title', 'meta_description', 'meta_keywords', 'featured_image_alt']
    
    for lang in target_languages:
        logger.info(f"Translating blog post '{blog_post.title}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(blog_post, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(blog_post, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Определяем, нужно ли сохранять HTML
            preserve_html = field_name == 'content' and '<' in russian_value
            
            # Переводим
            translated_text = translation_service.translate_text(
                russian_value, 
                lang, 
                preserve_html=preserve_html
            )
            
            if translated_text:
                setattr(blog_post, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    blog_post.save()
    logger.info(f"Translation completed for blog post '{blog_post.title}'")


def translate_blog_category(blog_category, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит категорию блога на указанные языки
    
    Args:
        blog_category: Объект BlogCategory
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода
    fields_to_translate = ['name', 'description', 'meta_title', 'meta_description', 'meta_keywords']
    
    for lang in target_languages:
        logger.info(f"Translating blog category '{blog_category.name}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(blog_category, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(blog_category, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Переводим
            translated_text = translation_service.translate_text(russian_value, lang)
            
            if translated_text:
                setattr(blog_category, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    blog_category.save()
    logger.info(f"Translation completed for blog category '{blog_category.name}'")