from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.core.services import TranslationService


class TranslationServiceTests(SimpleTestCase):
    @override_settings(
        YANDEX_TRANSLATE_API_KEY='test-key',
        YANDEX_TRANSLATE_FOLDER_ID='test-folder',
        YANDEX_TRANSLATE_ENDPOINT='https://example.test/translate',
        TRANSLATION_SETTINGS={
            'source_language': 'ru',
            'target_languages': ['en', 'th'],
            'chunk_size': 5000,
            'request_timeout': (1.5, 7.5),
            'failure_cooldown_seconds': 60,
        },
    )
    def test_yandex_request_uses_configured_timeout(self):
        service = TranslationService()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'translations': [{'text': 'Hello'}]}

        with patch('apps.core.services.requests.post', return_value=response) as post:
            result = service._translate_with_yandex('Привет', 'en')

        self.assertEqual(result, 'Hello')
        self.assertEqual(post.call_args.kwargs['timeout'], (1.5, 7.5))

    @override_settings(
        YANDEX_TRANSLATE_API_KEY='test-key',
        YANDEX_TRANSLATE_FOLDER_ID='test-folder',
        YANDEX_TRANSLATE_ENDPOINT='https://example.test/translate',
        TRANSLATION_SETTINGS={
            'source_language': 'ru',
            'target_languages': ['en', 'th'],
            'chunk_size': 5000,
            'request_timeout': (1, 2),
            'failure_cooldown_seconds': 60,
        },
    )
    def test_yandex_network_timeout_enters_fast_fail_cooldown(self):
        service = TranslationService()

        with patch(
            'apps.core.services.requests.post',
            side_effect=requests.exceptions.ConnectTimeout('connect timed out'),
        ) as post:
            first_result = service._translate_with_yandex('Привет', 'en')
            second_result = service._translate_with_yandex('Пока', 'en')

        self.assertIsNone(first_result)
        self.assertIsNone(second_result)
        self.assertEqual(post.call_count, 1)
