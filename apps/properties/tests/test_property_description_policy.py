import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase

from apps.core.context_processors import seo_context
from apps.properties.views import PropertyDetailView, property_detail_amp
from apps.properties.yml_feed import YandexYmlFeedGenerator


class PropertyDescriptionPolicyTests(SimpleTestCase):
    def test_property_detail_templates_preserve_description_copy(self):
        expected_fragments = {
            'templates/properties/detail.html': '{{ property.description|safe }}',
            'templates/properties/property_detail_amp.html': '{{ amp_description|safe }}',
            'templates/properties/includes/detail_structured_data_product.html': (
                'property.description|striptags|truncatechars:400|escapejs'
            ),
            'templates/properties/includes/detail_structured_data_place.html': (
                'property.description|striptags|truncatechars:400|escapejs'
            ),
            'templates/core/service_detail.html': (
                'property.description|striptags|truncatewords:15'
            ),
            'templates/includes/home/home_structured_data.html': (
                'prop.description|truncatechars:200|escapejs'
            ),
        }

        for relative_path, expected_fragment in expected_fragments.items():
            with self.subTest(template=relative_path):
                source = Path(settings.BASE_DIR, relative_path).read_text(encoding='utf-8')
                self.assertIn(expected_fragment, source)
                for line in source.splitlines():
                    if 'property.description' in line or 'prop.description' in line or 'amp_description' in line:
                        self.assertNotIn('sale_only', line)

    def test_property_detail_meta_description_is_not_replaced(self):
        request = RequestFactory().get('/ru/property/rental-income-home/')
        request.LANGUAGE_CODE = 'ru'
        property_obj = SimpleNamespace(
            get_seo_data=lambda language_code: {
                'title': 'Вилла с арендным доходом',
                'description': 'Арендный доход и спрос на аренду в этом проекте.',
                'keywords': 'вилла, аренда',
            }
        )

        with patch('apps.core.context_processors.Property.objects.get', return_value=property_obj):
            context = seo_context(request)

        self.assertEqual(
            context['page_description'],
            'Арендный доход и спрос на аренду в этом проекте.',
        )

    def test_property_views_do_not_sanitize_description_fields(self):
        detail_source = inspect.getsource(PropertyDetailView.get_context_data)
        amp_source = inspect.getsource(property_detail_amp)

        self.assertEqual(detail_source.count("'property_schema_description'"), 1)
        self.assertIn(
            'property_schema_description = _build_property_schema_description(',
            amp_source,
        )
        self.assertIn('meta_description = truncate_meta(raw_description)', amp_source)

    def test_yml_description_preserves_rental_copy(self):
        generator = YandexYmlFeedGenerator('https://example.com')
        property_obj = SimpleNamespace(
            short_description='Rental income and long-term lease options.',
            description='',
        )

        description = generator._prepare_description(property_obj)

        self.assertEqual(description, 'Rental income and long-term lease options.')
