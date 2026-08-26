import json
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from apps.core.utils import validate_form_security


class FormSecurityConsentTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_missing_privacy_consent_is_rejected(self):
        request = self.factory.post('/ru/users/contact/', {'name': 'Test'})

        response = validate_form_security(request)

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {
                'success': False,
                'error': 'privacy_consent_required',
                'message': 'Подтвердите согласие на обработку персональных данных.',
            },
        )

    def test_checked_privacy_consent_is_accepted(self):
        for value in ('1', 'true', 'on', 'yes', 'accepted'):
            with self.subTest(value=value):
                request = self.factory.post('/ru/users/contact/', {'privacy_consent': value})
                self.assertIsNone(validate_form_security(request))

    def test_honeypot_rejection_still_has_priority(self):
        request = self.factory.post(
            '/ru/users/contact/',
            {'website': 'spam.example', 'privacy_consent': ''},
        )

        response = validate_form_security(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['error'], 'suspected_bot')


class PublicFormConsentMarkupTests(SimpleTestCase):
    form_templates = {
        'templates/core/includes/home/home_phone_contact_form_section.html': (
            'quickConsultationForm',
        ),
        'templates/core/includes/home/home_visit_office_section.html': ('officeVisitForm',),
        'templates/core/includes/home/home_faq_section.html': ('faqQuestionForm',),
        'templates/core/includes/home/home_reviews_section.html': (
            'reviewsSectionContactForm',
        ),
        'templates/core/contact.html': ('contactForm',),
        'templates/core/service_detail.html': ('serviceContactForm',),
        'templates/blog/blog_detail.html': ('blogFeedbackForm',),
        'templates/properties/detail.html': (
            'customSelectionForm',
            'newsletterForm',
            'viewingRequestForm',
            'consultationRequestForm',
            'callbackRequestForm',
        ),
    }

    def test_every_public_personal_data_form_includes_required_consent(self):
        for relative_path, form_ids in self.form_templates.items():
            source = (Path(settings.BASE_DIR) / relative_path).read_text(encoding='utf-8')
            for form_id in form_ids:
                with self.subTest(template=relative_path, form_id=form_id):
                    marker = f'id="{form_id}"'
                    form_start = source.index('<form', source.index(marker) - 200)
                    form_end = source.index('</form>', form_start)
                    form_markup = source[form_start:form_end]
                    self.assertIn('privacy_consent_checkbox.html', form_markup)

    def test_dynamic_consultation_form_has_required_consent(self):
        source = (
            Path(settings.BASE_DIR) / 'static/js/home/featured-properties.js'
        ).read_text(encoding='utf-8')

        self.assertIn('name="privacy_consent"', source)
        self.assertIn('data-privacy-consent', source)
        self.assertIn('required', source)

    def test_shared_checkbox_has_ru_en_and_th_copy(self):
        expected_copy = {
            'ru': 'Я даю согласие на обработку персональных данных',
            'en': 'I consent to the processing of my personal data',
            'th': 'ฉันยินยอมให้ประมวลผลข้อมูลส่วนบุคคล',
        }

        for language_code, expected_text in expected_copy.items():
            with self.subTest(language_code=language_code):
                markup = render_to_string(
                    'core/includes/privacy_consent_checkbox.html',
                    {
                        'LANGUAGE_CODE': language_code,
                        'privacy_consent_id': f'{language_code}-consent',
                    },
                )
                self.assertIn(expected_text, ' '.join(markup.split()))
                self.assertIn('name="privacy_consent"', markup)
                self.assertIn('required', markup)
