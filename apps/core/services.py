import re
import time
from typing import Dict, List, Optional
from django.conf import settings
from django.utils.html import strip_tags
import requests
import logging

logger = logging.getLogger(__name__)


class TranslationService:
    """Сервис для автоматического перевода контента через API"""
    
    def __init__(self):
        self.google_api_key = getattr(settings, 'GOOGLE_TRANSLATE_API_KEY', '')
        self.deepl_api_key = getattr(settings, 'DEEPL_API_KEY', '')
        self.preferred_service = getattr(settings, 'TRANSLATION_SERVICE', 'google')
        self.translation_settings = getattr(settings, 'TRANSLATION_SETTINGS', {
            'source_language': 'ru',
            'target_languages': ['en', 'th'],
            'chunk_size': 5000,
        })
    
    def translate_text(self, text: str, target_language: str, preserve_html: bool = False) -> Optional[str]:
        """
        Переводит текст на указанный язык
        
        Args:
            text: Текст для перевода
            target_language: Целевой язык ('en', 'th')
            preserve_html: Сохранять ли HTML разметку
            
        Returns:
            Переведенный текст или None в случае ошибки
        """
        if not text or not text.strip():
            return text
            
        # Удаляем HTML теги если не нужно их сохранять
        if not preserve_html:
            text = strip_tags(text)
            
        # Разбиваем на чунки если текст слишком длинный
        chunks = self._split_text_into_chunks(text)
        translated_chunks = []
        
        for chunk in chunks:
            if self.preferred_service == 'deepl' and self.deepl_api_key:
                translated_chunk = self._translate_with_deepl(chunk, target_language)
            elif self.google_api_key:
                translated_chunk = self._translate_with_google(chunk, target_language)
            else:
                logger.error("No translation API key configured")
                return None
                
            if translated_chunk is None:
                logger.error(f"Failed to translate chunk: {chunk[:100]}...")
                return None
                
            translated_chunks.append(translated_chunk)
            
            # Небольшая пауза между запросами
            time.sleep(0.1)
        
        return ''.join(translated_chunks)
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """Разбивает текст на части для соблюдения лимитов API"""
        chunk_size = self.translation_settings['chunk_size']
        
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Разбиваем по предложениям
        sentences = re.split(r'([.!?]\s+)', text)
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i] if i < len(sentences) else ""
            separator = sentences[i + 1] if i + 1 < len(sentences) else ""
            full_sentence = sentence + separator
            
            if len(current_chunk) + len(full_sentence) <= chunk_size:
                current_chunk += full_sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = full_sentence
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
    
    def _translate_with_google(self, text: str, target_language: str) -> Optional[str]:
        """Перевод через Google Translate API"""
        try:
            url = "https://translation.googleapis.com/language/translate/v2"
            params = {
                'key': self.google_api_key,
                'q': text,
                'source': self.translation_settings['source_language'],
                'target': target_language,
                'format': 'text'
            }
            
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if 'data' in data and 'translations' in data['data']:
                return data['data']['translations'][0]['translatedText']
            else:
                logger.error(f"Unexpected Google Translate response: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Translate API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Google Translate unexpected error: {e}")
            return None
    
    def _translate_with_deepl(self, text: str, target_language: str) -> Optional[str]:
        """Перевод через DeepL API"""
        try:
            # DeepL использует другие коды языков
            deepl_language_map = {
                'en': 'EN',
                'th': 'TH',  # Проверить поддержку тайского в DeepL
            }
            
            target_lang = deepl_language_map.get(target_language, target_language.upper())
            
            url = "https://api-free.deepl.com/v2/translate"
            headers = {
                'Authorization': f'DeepL-Auth-Key {self.deepl_api_key}',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            data = {
                'text': text,
                'source_lang': 'RU',
                'target_lang': target_lang,
            }
            
            response = requests.post(url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if 'translations' in result and result['translations']:
                return result['translations'][0]['text']
            else:
                logger.error(f"Unexpected DeepL response: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepL API error: {e}")
            return None
        except Exception as e:
            logger.error(f"DeepL unexpected error: {e}")
            return None
    
    def translate_model_fields(self, instance, fields: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Переводит указанные поля модели на все целевые языки
        
        Args:
            instance: Экземпляр модели
            fields: Список полей для перевода
            
        Returns:
            Словарь переводов: {field_name: {language: translated_text}}
        """
        translations = {}
        
        for field_name in fields:
            # Получаем значение русского поля
            russian_value = getattr(instance, field_name, '')
            
            if not russian_value:
                continue
                
            translations[field_name] = {}
            
            # Определяем, нужно ли сохранять HTML (для полей с HTML контентом)
            preserve_html = field_name in ['content', 'description'] and '<' in russian_value
            
            for target_language in self.translation_settings['target_languages']:
                translated_text = self.translate_text(
                    russian_value, 
                    target_language, 
                    preserve_html=preserve_html
                )
                
                if translated_text:
                    translations[field_name][target_language] = translated_text
                    logger.info(f"Translated {field_name} to {target_language}")
                else:
                    logger.warning(f"Failed to translate {field_name} to {target_language}")
        
        return translations
    
    def apply_translations_to_model(self, instance, translations: Dict[str, Dict[str, str]]) -> None:
        """
        Применяет переводы к экземпляру модели
        
        Args:
            instance: Экземпляр модели
            translations: Словарь переводов
        """
        for field_name, field_translations in translations.items():
            for language, translated_text in field_translations.items():
                # Формируем имя поля с языковым суффиксом
                translated_field_name = f"{field_name}_{language}"
                
                # Проверяем, что поле существует в модели
                if hasattr(instance, translated_field_name):
                    setattr(instance, translated_field_name, translated_text)
                    logger.info(f"Set {translated_field_name} = {translated_text[:50]}...")
    
    def is_configured(self) -> bool:
        """Проверяет, настроен ли сервис перевода"""
        return bool(self.google_api_key or self.deepl_api_key)
    
    def get_available_service(self) -> Optional[str]:
        """Возвращает доступный сервис перевода"""
        if self.preferred_service == 'deepl' and self.deepl_api_key:
            return 'deepl'
        elif self.google_api_key:
            return 'google'
        return None


# Глобальный экземпляр сервиса
translation_service = TranslationService()