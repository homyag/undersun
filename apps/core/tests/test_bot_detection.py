from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.bot_detection import BotDetectionService


BOT_PROTECTION_TEST_CONFIG = {
    'ENABLED': True,
    'WHITELIST_IPS': [],
    'WHITELIST_USER_AGENTS': [],
    'BLACKLIST_IPS': [],
    'SUSPICIOUS_USER_AGENTS': [r'HeadlessChrome'],
    'HIGH_RISK_USER_AGENT_PATTERNS': [],
    'FORBIDDEN_PATH_PATTERNS': [],
    'HEADER_KEYS': ['HTTP_ACCEPT_LANGUAGE', 'HTTP_ACCEPT_ENCODING'],
    'SKIP_PATH_PREFIXES': [],
    'SKIP_METHODS': [],
    'JS_CHALLENGE_GRACE_SECONDS': 10,
    'JS_CHALLENGE_MAX_MISSES': 3,
    'JS_CHALLENGE_EXEMPT_PATH_PREFIXES': ['/admin/'],
    'CHALLENGE_COOKIE': 'bot_challenge',
    'RULE_WEIGHTS': {
        'missing_headers_critical': 120,
        'js_challenge_missing': 40,
        'suspicious_user_agent': 25,
    },
}


@override_settings(BOT_PROTECTION=BOT_PROTECTION_TEST_CONFIG)
class BotDetectionServiceTests(SimpleTestCase):
    def test_explicit_headless_browser_is_blocked(self):
        request = RequestFactory().get(
            '/en/map/',
            HTTP_USER_AGENT=(
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                'HeadlessChrome/126.0.0.0 Safari/537.36'
            ),
            HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9',
            HTTP_ACCEPT_ENCODING='gzip, deflate, br',
        )

        result = BotDetectionService().evaluate(request, '203.0.113.10', '127.0.0.1')

        self.assertEqual(result.action, 'block')
        self.assertEqual(result.score, 25)
        self.assertEqual([match.key for match in result.matched_rules], ['suspicious_user_agent'])
