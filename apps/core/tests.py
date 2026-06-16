from unittest.mock import Mock, patch

import requests
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.bot_detection import BotDetectionService
from apps.core.services import TranslationService


BOT_PROTECTION_TEST_CONFIG = {
    'ENABLED': True,
    'WHITELIST_IPS': [],
    'WHITELIST_USER_AGENTS': [],
    'BLACKLIST_IPS': [],
    'SUSPICIOUS_USER_AGENTS': [],
    'HIGH_RISK_USER_AGENT_PATTERNS': [],
    'FORBIDDEN_PATH_PATTERNS': [],
    'HEADER_KEYS': [
        'HTTP_ACCEPT_LANGUAGE',
        'HTTP_ACCEPT_ENCODING',
        'HTTP_SEC_CH_UA',
        'HTTP_SEC_CH_UA_PLATFORM',
        'HTTP_SEC_FETCH_DEST',
        'HTTP_SEC_FETCH_SITE',
    ],
    'SKIP_PATH_PREFIXES': [],
    'SKIP_METHODS': [],
    'JS_CHALLENGE_GRACE_SECONDS': 10,
    'JS_CHALLENGE_MAX_MISSES': 3,
    'JS_CHALLENGE_EXEMPT_PATH_PREFIXES': ['/admin/'],
    'CHALLENGE_COOKIE': 'bot_challenge',
    'RULE_WEIGHTS': {
        'missing_headers_critical': 120,
        'js_challenge_missing': 40,
    },
}


class BotDetectionServiceTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _browser_headers(self, fetch_dest='document', fetch_site='same-origin'):
        return {
            'HTTP_USER_AGENT': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/146.0.0.0 YaBrowser/26.4.0.0 Safari/537.36'
            ),
            'HTTP_ACCEPT_LANGUAGE': 'ru,en;q=0.9',
            'HTTP_ACCEPT_ENCODING': 'gzip, deflate, br, zstd',
            'HTTP_SEC_FETCH_DEST': fetch_dest,
            'HTTP_SEC_FETCH_SITE': fetch_site,
            'HTTP_SEC_CH_UA_PLATFORM': '"Windows"',
        }

    @override_settings(BOT_PROTECTION=BOT_PROTECTION_TEST_CONFIG)
    def test_admin_get_is_exempt_from_js_challenge_cookie(self):
        request = self.factory.get('/admin/properties/property/', **self._browser_headers())
        service = BotDetectionService()

        result = service.evaluate(request, '77.40.3.104', '127.0.0.1')

        self.assertEqual(result.action, 'allow')
        self.assertEqual(result.score, 0)
        self.assertEqual(result.matched_rules, [])

    @override_settings(BOT_PROTECTION=BOT_PROTECTION_TEST_CONFIG)
    def test_admin_post_is_exempt_from_js_challenge_cookie(self):
        request = self.factory.post('/admin/properties/property/', {}, **self._browser_headers())
        service = BotDetectionService()

        result = service.evaluate(request, '77.40.3.104', '127.0.0.1')

        self.assertEqual(result.action, 'allow')
        self.assertEqual(result.score, 0)
        self.assertEqual(result.matched_rules, [])

    @override_settings(BOT_PROTECTION=BOT_PROTECTION_TEST_CONFIG)
    def test_public_post_still_requires_js_challenge_cookie(self):
        request = self.factory.post('/ru/property/ajax/favorites/', {}, **self._browser_headers())
        service = BotDetectionService()

        result = service.evaluate(request, '77.40.3.104', '127.0.0.1')

        self.assertEqual(result.action, 'block')
        self.assertEqual(result.score, 40)
        self.assertEqual([match.key for match in result.matched_rules], ['js_challenge_missing'])


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
