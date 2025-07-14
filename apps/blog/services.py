import requests
from django.conf import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TranslationService:
    """Сервис для автоматического перевода текста"""
    
    @staticmethod
    def translate_text(text: str, target_language: str, source_language: str = 'ru') -> Optional[str]:
        """
        Переводит текст с одного языка на другой
        
        Args:
            text: Текст для перевода
            target_language: Целевой язык ('en', 'th')
            source_language: Исходный язык (по умолчанию 'ru')
            
        Returns:
            Переведенный текст или None в случае ошибки
        """
        if not text or not text.strip():
            return text
            
        # Используем Google Translate API через googletrans (бесплатно)
        try:
            from googletrans import Translator
            translator = Translator()
            
            # Переводим текст
            result = translator.translate(text, dest=target_language, src=source_language)
            return result.text
            
        except ImportError:
            logger.warning("googletrans not installed. Install with: pip install googletrans==4.0.0rc1")
            return None
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return None
    
    @staticmethod
    def translate_html_content(html_content: str, target_language: str, source_language: str = 'ru') -> Optional[str]:
        """
        Переводит HTML контент, сохраняя разметку
        
        Args:
            html_content: HTML контент для перевода
            target_language: Целевой язык
            source_language: Исходный язык
            
        Returns:
            Переведенный HTML или None в случае ошибки
        """
        if not html_content or not html_content.strip():
            return html_content
            
        try:
            from googletrans import Translator
            from bs4 import BeautifulSoup
            import re
            
            translator = Translator()
            
            # Парсим HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Находим все текстовые узлы
            def translate_text_nodes(element):
                for child in element.children:
                    if hasattr(child, 'children'):
                        translate_text_nodes(child)
                    elif hasattr(child, 'string') and child.string and child.string.strip():
                        # Переводим текст, если это не HTML-тег
                        original_text = child.string.strip()
                        if len(original_text) > 3:  # Переводим только значимый текст
                            try:
                                translated = translator.translate(original_text, dest=target_language, src=source_language)
                                child.string.replace_with(translated.text)
                            except:
                                pass  # Пропускаем ошибки перевода отдельных фрагментов
            
            translate_text_nodes(soup)
            return str(soup)
            
        except ImportError:
            logger.warning("Required packages not installed. Install with: pip install googletrans==4.0.0rc1 beautifulsoup4")
            # Fallback: переводим как обычный текст, убирая HTML теги
            import re
            clean_text = re.sub(r'<[^>]+>', '', html_content)
            translated = TranslationService.translate_text(clean_text, target_language, source_language)
            return translated
        except Exception as e:
            logger.error(f"HTML translation error: {e}")
            return None


def translate_blog_post(blog_post, target_languages=['en', 'th']):
    """
    Автоматически переводит статью блога на указанные языки
    
    Args:
        blog_post: Объект BlogPost
        target_languages: Список языков для перевода
    """
    translation_service = TranslationService()
    
    for lang in target_languages:
        logger.info(f"Translating blog post '{blog_post.title}' to {lang}")
        
        # Переводим заголовок
        if blog_post.title and not getattr(blog_post, f'title_{lang}', None):
            translated_title = translation_service.translate_text(blog_post.title, lang)
            if translated_title:
                setattr(blog_post, f'title_{lang}', translated_title)
        
        # Переводим краткое описание
        if blog_post.excerpt and not getattr(blog_post, f'excerpt_{lang}', None):
            translated_excerpt = translation_service.translate_text(blog_post.excerpt, lang)
            if translated_excerpt:
                setattr(blog_post, f'excerpt_{lang}', translated_excerpt)
        
        # Переводим содержание (HTML)
        if blog_post.content and not getattr(blog_post, f'content_{lang}', None):
            translated_content = translation_service.translate_html_content(blog_post.content, lang)
            if translated_content:
                setattr(blog_post, f'content_{lang}', translated_content)
        
        # Переводим SEO поля
        if blog_post.meta_title and not getattr(blog_post, f'meta_title_{lang}', None):
            translated_meta_title = translation_service.translate_text(blog_post.meta_title, lang)
            if translated_meta_title:
                setattr(blog_post, f'meta_title_{lang}', translated_meta_title)
        
        if blog_post.meta_description and not getattr(blog_post, f'meta_description_{lang}', None):
            translated_meta_desc = translation_service.translate_text(blog_post.meta_description, lang)
            if translated_meta_desc:
                setattr(blog_post, f'meta_description_{lang}', translated_meta_desc)
        
        if blog_post.meta_keywords and not getattr(blog_post, f'meta_keywords_{lang}', None):
            translated_keywords = translation_service.translate_text(blog_post.meta_keywords, lang)
            if translated_keywords:
                setattr(blog_post, f'meta_keywords_{lang}', translated_keywords)
        
        # Переводим alt текст изображения
        if blog_post.featured_image_alt and not getattr(blog_post, f'featured_image_alt_{lang}', None):
            translated_alt = translation_service.translate_text(blog_post.featured_image_alt, lang)
            if translated_alt:
                setattr(blog_post, f'featured_image_alt_{lang}', translated_alt)
    
    # Сохраняем изменения
    blog_post.save()
    logger.info(f"Translation completed for blog post '{blog_post.title}'")


def translate_blog_category(blog_category, target_languages=['en', 'th']):
    """
    Автоматически переводит категорию блога на указанные языки
    
    Args:
        blog_category: Объект BlogCategory
        target_languages: Список языков для перевода
    """
    translation_service = TranslationService()
    
    for lang in target_languages:
        logger.info(f"Translating blog category '{blog_category.name}' to {lang}")
        
        # Переводим название
        if blog_category.name and not getattr(blog_category, f'name_{lang}', None):
            translated_name = translation_service.translate_text(blog_category.name, lang)
            if translated_name:
                setattr(blog_category, f'name_{lang}', translated_name)
        
        # Переводим описание
        if blog_category.description and not getattr(blog_category, f'description_{lang}', None):
            translated_desc = translation_service.translate_text(blog_category.description, lang)
            if translated_desc:
                setattr(blog_category, f'description_{lang}', translated_desc)
        
        # Переводим SEO поля
        if blog_category.meta_title and not getattr(blog_category, f'meta_title_{lang}', None):
            translated_meta_title = translation_service.translate_text(blog_category.meta_title, lang)
            if translated_meta_title:
                setattr(blog_category, f'meta_title_{lang}', translated_meta_title)
        
        if blog_category.meta_description and not getattr(blog_category, f'meta_description_{lang}', None):
            translated_meta_desc = translation_service.translate_text(blog_category.meta_description, lang)
            if translated_meta_desc:
                setattr(blog_category, f'meta_description_{lang}', translated_meta_desc)
        
        if blog_category.meta_keywords and not getattr(blog_category, f'meta_keywords_{lang}', None):
            translated_keywords = translation_service.translate_text(blog_category.meta_keywords, lang)
            if translated_keywords:
                setattr(blog_category, f'meta_keywords_{lang}', translated_keywords)
    
    # Сохраняем изменения
    blog_category.save()
    logger.info(f"Translation completed for blog category '{blog_category.name}'")