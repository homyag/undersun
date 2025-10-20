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
        self.translation_settings = getattr(settings, 'TRANSLATION_SETTINGS', {
            'source_language': 'ru',
            'target_languages': ['en', 'th'],
            'chunk_size': 5000,
        })
        self.refresh_credentials()

    def refresh_credentials(self) -> None:
        """Читает актуальные реквизиты доступа из настроек."""
        self.yandex_api_key = getattr(settings, 'YANDEX_TRANSLATE_API_KEY', '')
        self.yandex_folder_id = getattr(settings, 'YANDEX_TRANSLATE_FOLDER_ID', '')
        self.yandex_endpoint = getattr(
            settings,
            'YANDEX_TRANSLATE_ENDPOINT',
            'https://translate.api.cloud.yandex.net/translate/v2/translate'
        )
    
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

        # Обновляем реквизиты, чтобы подхватить изменения без рестарта
        self.refresh_credentials()

        # Удаляем HTML теги если не нужно их сохранять
        if not preserve_html:
            text = strip_tags(text)
            
        # Разбиваем на чунки если текст слишком длинный
        chunks = self._split_text_into_chunks(text)
        translated_chunks = []
        
        for chunk in chunks:
            translated_chunk = self._translate_with_yandex(
                chunk,
                target_language,
                preserve_html=preserve_html
            )
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
    
    def _translate_with_yandex(
        self,
        text: str,
        target_language: str,
        preserve_html: bool = False
    ) -> Optional[str]:
        """Перевод через Yandex Translate API"""
        if not self.is_configured():
            logger.error("Yandex Translate API is not configured")
            return None

        format_type = 'HTML' if preserve_html else 'PLAIN_TEXT'

        payload = {
            'folderId': self.yandex_folder_id,
            'texts': [text],
            'targetLanguageCode': target_language,
            'format': format_type,
        }

        source_language = self.translation_settings.get('source_language')
        if source_language:
            payload['sourceLanguageCode'] = source_language

        headers = {
            'Authorization': f'Api-Key {self.yandex_api_key}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.post(
                self.yandex_endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            translations = data.get('translations')
            if translations:
                return translations[0].get('text')

            logger.error(f"Unexpected Yandex Translate response: {data}")
            return None
        except requests.exceptions.HTTPError as exc:
            # Логируем тело ответа, чтобы проще было диагностировать авторизацию
            error_text = exc.response.text if exc.response is not None else str(exc)
            logger.error(
                "Yandex Translate API error: %s | response body: %s",
                exc,
                error_text[:500]
            )
            return None
        except requests.exceptions.RequestException as exc:
            logger.error(f"Yandex Translate API error: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Yandex Translate unexpected error: {exc}")
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
        # Перечитываем ключи на случай, если они обновились во время работы процесса
        self.refresh_credentials()
        return bool(self.yandex_api_key and self.yandex_folder_id)

    def get_available_service(self) -> Optional[str]:
        """Возвращает доступный сервис перевода"""
        if self.is_configured():
            return 'yandex'
        return None


# Глобальный экземпляр сервиса
translation_service = TranslationService()
