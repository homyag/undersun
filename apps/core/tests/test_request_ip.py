from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.utils import get_client_ip


class ClientIpTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(TRUSTED_PROXY_CIDRS=['127.0.0.1/32', '10.0.0.0/8'])
    def test_ignores_forwarded_for_from_an_untrusted_direct_client(self):
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='198.51.100.42', REMOTE_ADDR='203.0.113.12')

        self.assertEqual(get_client_ip(request), '203.0.113.12')

    @override_settings(TRUSTED_PROXY_CIDRS=['127.0.0.1/32', '10.0.0.0/8'])
    def test_uses_the_rightmost_untrusted_address_from_a_trusted_proxy(self):
        request = self.factory.get(
            '/',
            HTTP_X_FORWARDED_FOR='198.51.100.42, 203.0.113.12, 10.1.2.3',
            REMOTE_ADDR='127.0.0.1',
        )

        self.assertEqual(get_client_ip(request), '203.0.113.12')
