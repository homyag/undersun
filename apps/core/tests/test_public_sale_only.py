from pathlib import Path

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from django.utils import translation

from apps.properties.views import PropertyRentView


class PublicSaleOnlyPolicyTests(SimpleTestCase):
    def test_runtime_copy_replacement_mechanism_is_removed(self):
        forbidden_tokens = (
            'sanitize_' + 'public_' + 'text',
            'sanitize_' + 'public_' + 'html',
            'sanitize_' + 'public_' + 'content',
            'sale_' + 'only_' + 'text',
            'sale_' + 'only_' + 'html',
        )

        for root_name, extension in (('apps', '*.py'), ('templates', '*.html')):
            for path in (Path(settings.BASE_DIR) / root_name).rglob(extension):
                if path == Path(__file__):
                    continue
                with self.subTest(path=path.relative_to(settings.BASE_DIR)):
                    source = path.read_text(encoding='utf-8')
                    for token in forbidden_tokens:
                        self.assertNotIn(token, source)

    def test_legacy_rent_catalog_redirects_to_sale_catalog(self):
        request = RequestFactory().get('/en/property/rent/', secure=True)
        request.LANGUAGE_CODE = 'en'
        with translation.override('en'):
            response = PropertyRentView.as_view()(request)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/en/property/sale/')
