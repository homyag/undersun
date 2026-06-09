import json
import shutil
import tempfile
from types import SimpleNamespace
from urllib.parse import urlparse

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import _extract_blog_toc_and_content, _sanitize_svg_upload, tinymce_upload


class BlogTocTests(SimpleTestCase):
    def test_heading_entities_are_decoded_for_toc_titles(self):
        html = '<h2>Ежегодное собрание&nbsp;P-REA &amp; Partners 2026</h2>'

        toc_items, processed_content = _extract_blog_toc_and_content(html)

        self.assertEqual(
            toc_items[0]['title'],
            'Ежегодное собрание P-REA & Partners 2026',
        )
        self.assertNotIn('&nbsp;', toc_items[0]['title'])
        self.assertIn('Ежегодное собрание&nbsp;P-REA &amp; Partners 2026', processed_content)


class TinyMCEUploadTests(SimpleTestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        self.request_factory = RequestFactory()

    def _post_upload(self, upload, user):
        request = self.request_factory.post(
            '/ru/blog/tinymce-upload/',
            {'file': upload},
            HTTP_HOST='testserver',
        )
        request.user = user
        return tinymce_upload(request)

    def test_tinymce_upload_requires_staff_user(self):
        upload = SimpleUploadedFile(
            'icon.svg',
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>',
            content_type='image/svg+xml',
        )

        response = self._post_upload(
            upload,
            SimpleNamespace(is_authenticated=False, is_staff=False),
        )

        self.assertEqual(response.status_code, 403)

    def test_tinymce_upload_accepts_and_sanitizes_svg(self):
        upload = SimpleUploadedFile(
            'floor plan.svg',
            b'''
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
                <script>alert(1)</script>
                <rect width="10" height="10" fill="url(#paint)" onload="alert(1)" />
                <a href="javascript:alert(1)"><text>Bad link</text></a>
            </svg>
            ''',
            content_type='image/svg+xml',
        )

        response = self._post_upload(
            upload,
            SimpleNamespace(is_authenticated=True, is_staff=True),
        )

        self.assertEqual(response.status_code, 200)
        location = json.loads(response.content)['location']
        self.assertIn('/media/blog/editor/floor-plan.svg', location)

        stored_path = urlparse(location).path.split('/media/', 1)[1]
        with default_storage.open(stored_path, 'rb') as stored_file:
            stored_svg = stored_file.read().decode('utf-8')

        self.assertIn('<rect', stored_svg)
        self.assertNotIn('<script', stored_svg)
        self.assertNotIn('onload', stored_svg)
        self.assertNotIn('javascript:', stored_svg)

    def test_svg_sanitizer_rejects_doctype_declarations(self):
        upload = SimpleUploadedFile(
            'unsafe.svg',
            b'<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"></svg>',
            content_type='image/svg+xml',
        )

        with self.assertRaisesMessage(ValueError, 'DOCTYPE and ENTITY'):
            _sanitize_svg_upload(upload)

    def test_svg_sanitizer_preserves_editorial_chart_markup(self):
        upload = SimpleUploadedFile(
            'chart.svg',
            '''
            <svg viewBox="0 0 800 530" xmlns="http://www.w3.org/2000/svg" width="800" height="530">
              <title>Стоимость запуска новых проектов по типам, 2008–2025</title>
              <rect width="800" height="530" fill="white"/>
              <text x="420" y="22" font-size="14" font-weight="500" fill="#474B57" text-anchor="middle" font-family="sans-serif">Стоимость запуска новых проектов по типам</text>
              <text font-size="10" fill="#aaa" font-family="sans-serif">
                <tspan x="60" y="520">Источник: </tspan>
                <a href="https://www.bualuang.co.th/en" target="_blank" rel="noopener">
                  <tspan fill="#F1B400" text-decoration="underline">Bualuang Securities</tspan>
                </a>
              </text>
            </svg>
            '''.encode('utf-8'),
            content_type='image/svg+xml',
        )

        stored_svg = _sanitize_svg_upload(upload).decode('utf-8')

        self.assertIn('Стоимость запуска новых проектов по типам', stored_svg)
        self.assertIn('font-size="14"', stored_svg)
        self.assertIn('font-weight="500"', stored_svg)
        self.assertIn('text-anchor="middle"', stored_svg)
        self.assertIn('font-family="sans-serif"', stored_svg)
        self.assertIn('href="https://www.bualuang.co.th/en"', stored_svg)
        self.assertIn('target="_blank"', stored_svg)
        self.assertIn('rel="noopener"', stored_svg)
        self.assertIn('text-decoration="underline"', stored_svg)
