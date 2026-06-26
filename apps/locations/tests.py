from django.test import SimpleTestCase

from apps.locations.phuket_area_content import (
    get_location_description,
    get_location_faq_items,
)


class PhuketAreaContentTests(SimpleTestCase):
    def test_surin_uses_bang_tao_context(self):
        description = get_location_description('surin', 'en')
        faq_text = ' '.join(
            f"{item['question']} {item['answer']}"
            for item in get_location_faq_items('surin', 'en')
        )

        self.assertIn('Surin', description)
        self.assertIn('Bang Tao', description)
        self.assertIn('Surin', faq_text)

    def test_nai_harn_is_covered_by_rawai_context(self):
        self.assertIn('Nai Harn', get_location_description('rawai', 'en'))
        self.assertIn('Най Харн', get_location_description('rawai', 'ru'))
        self.assertIn('Nai Harn Beach', get_location_description('rawai', 'th'))

        faq_text = ' '.join(
            f"{item['question']} {item['answer']}"
            for item in get_location_faq_items('rawai', 'en')
        )
        self.assertIn('Nai Harn Beach', faq_text)

    def test_laguna_is_covered_by_cherng_talay_context(self):
        self.assertIn('Laguna Phuket', get_location_description('cherng-talay', 'en'))
        self.assertIn('Laguna Phuket', get_location_description('cherng-talay', 'ru'))
        self.assertIn('Laguna Phuket', get_location_description('cherng-talay', 'th'))

        faq_text = ' '.join(
            f"{item['question']} {item['answer']}"
            for item in get_location_faq_items('cherng-talay', 'en')
        )
        self.assertIn('Laguna Phuket', faq_text)
