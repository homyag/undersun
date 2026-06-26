from pathlib import Path
from unittest.mock import Mock, patch

import requests
from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.bot_detection import BotDetectionService
from apps.core.context_processors import _get_active_nav_section
from apps.core.services import TranslationService
from apps.core.utils import truncate_meta


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


class SeoUtilsTests(SimpleTestCase):
    def test_truncate_meta_does_not_append_literal_ellipsis(self):
        text = ' '.join(['Phuket property buyers compare villas condos land title checks and location context'] * 4)

        result = truncate_meta(text, limit=90)

        self.assertLessEqual(len(result), 90)
        self.assertFalse(result.endswith('...'))

    def test_truncate_meta_strips_existing_terminal_ellipsis(self):
        self.assertEqual(
            truncate_meta('Compare villas, condos and land in Phuket...'),
            'Compare villas, condos and land in Phuket',
        )

    def test_truncate_meta_preserves_short_description(self):
        self.assertEqual(
            truncate_meta('Compare Phuket villas and condos with local context.'),
            'Compare Phuket villas and condos with local context.',
        )


class LlmsTxtEndpointTests(SimpleTestCase):
    def test_llms_txt_is_plain_text_source_map(self):
        response = self.client.get('/llms.txt')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')

        body = response.content.decode('utf-8')
        normalized_body = ' '.join(body.split())

        self.assertTrue(body.startswith('# Undersun Estate'))
        self.assertIn('Canonical Site Sources', body)
        self.assertIn('https://undersunestate.com/en/property/type/villa/', body)
        self.assertIn(
            'not be treated as legal, tax, financial, immigration, or investment advice',
            normalized_body,
        )
        self.assertNotIn('<html', body.lower())


class HomeFaqContentTests(SimpleTestCase):
    def _read_project_file(self, relative_path):
        return Path(settings.BASE_DIR, relative_path).read_text(encoding='utf-8')

    def test_home_faq_schema_matches_visible_question_count(self):
        template = self._read_project_file('templates/core/includes/home/home_faq_section.html')

        self.assertEqual(template.count('"@type": "Question"'), 5)
        self.assertEqual(template.count('<!-- FAQ Item '), 5)

    def test_home_faq_avoids_legal_tax_and_fee_guarantees(self):
        content = '\n'.join([
            self._read_project_file('templates/core/includes/home/home_faq_section.html'),
            self._read_project_file('locale/ru/LC_MESSAGES/django.po'),
            self._read_project_file('locale/en/LC_MESSAGES/django.po'),
            self._read_project_file('locale/th/LC_MESSAGES/django.po'),
        ])

        risky_phrases = [
            'юридически безопасный',
            '30+30+30',
            '1,1%',
            '6,8%',
            '0 THB',
            'legally secure',
            'legally established practice',
            '1.1%',
            '6.8%',
        ]

        for phrase in risky_phrases:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, content)


class NavigationContextTests(SimpleTestCase):
    def _request_for_view(self, *, namespace='', view_name='', url_name=''):
        request = Mock()
        request.resolver_match = Mock(
            namespace=namespace,
            app_name=namespace,
            view_name=view_name,
            url_name=url_name,
        )
        return request

    def test_service_slug_with_property_does_not_activate_properties_nav(self):
        request = self._request_for_view(
            namespace='core',
            view_name='core:service_detail',
            url_name='service_detail',
        )

        self.assertEqual(_get_active_nav_section(request), 'services')

    def test_blog_slug_with_property_does_not_activate_properties_nav(self):
        request = self._request_for_view(
            namespace='blog',
            view_name='blog:detail',
            url_name='detail',
        )

        self.assertEqual(_get_active_nav_section(request), 'blog')

    def test_map_and_about_sections_are_not_properties_nav(self):
        self.assertEqual(
            _get_active_nav_section(self._request_for_view(namespace='core', view_name='core:map', url_name='map')),
            'map',
        )
        self.assertEqual(
            _get_active_nav_section(self._request_for_view(namespace='core', view_name='core:about', url_name='about')),
            'about',
        )

    def test_property_and_location_views_activate_properties_nav(self):
        self.assertEqual(
            _get_active_nav_section(self._request_for_view(
                namespace='properties',
                view_name='properties:property_detail',
                url_name='property_detail',
            )),
            'properties',
        )
        self.assertEqual(
            _get_active_nav_section(self._request_for_view(view_name='district_detail', url_name='district_detail')),
            'properties',
        )


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
