import json
import shutil
import tempfile
from types import SimpleNamespace
from urllib.parse import urlparse

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings

from .services import get_blog_post_translation_plan
from .views import (
    BUYING_GUIDE_BLOG_SLUG,
    _extract_blog_toc_and_content,
    _sanitize_svg_upload,
    tinymce_upload,
)


class BlogTranslationPlanTests(SimpleTestCase):
    def test_plan_skips_existing_translations_without_force(self):
        post = SimpleNamespace(
            title='Русский заголовок',
            title_en='Existing title',
            title_th='',
            excerpt='Русское описание',
            excerpt_en='',
            excerpt_th='',
            content='<p>Русский текст</p>',
            content_en='Existing content',
            content_th='',
            meta_title='SEO заголовок',
            meta_title_en='',
            meta_title_th='',
            meta_description='SEO описание',
            meta_description_en='',
            meta_description_th='',
            meta_keywords='ключи',
            meta_keywords_en='',
            meta_keywords_th='',
            featured_image_alt='Alt',
            featured_image_alt_en='Existing alt',
            featured_image_alt_th='',
        )

        plan, skipped_count = get_blog_post_translation_plan(
            post,
            target_languages=['en', 'th'],
            force_retranslate=False,
        )

        translated_fields = {item['translated_field_name'] for item in plan}
        self.assertNotIn('title_en', translated_fields)
        self.assertNotIn('content_en', translated_fields)
        self.assertNotIn('featured_image_alt_en', translated_fields)
        self.assertIn('meta_title_en', translated_fields)
        self.assertIn('title_th', translated_fields)
        self.assertEqual(skipped_count, 3)

    def test_plan_includes_existing_translations_with_force(self):
        post = SimpleNamespace(
            title='Русский заголовок',
            title_en='Existing title',
            excerpt='',
            content='',
            meta_title='',
            meta_description='',
            meta_keywords='',
            featured_image_alt='',
        )

        plan, skipped_count = get_blog_post_translation_plan(
            post,
            target_languages=['en'],
            force_retranslate=True,
        )

        self.assertEqual([item['translated_field_name'] for item in plan], ['title_en'])
        self.assertEqual(skipped_count, 6)


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


class BuyingGuideRedirectTests(SimpleTestCase):
    def test_top_level_buying_guide_redirects_to_blog_article(self):
        response = self.client.get('/en/buying-guide/')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], f'/en/blog/{BUYING_GUIDE_BLOG_SLUG}/')

    def test_legacy_russian_short_slug_redirects_to_blog_article(self):
        response = self.client.get('/ru/blog/thailand-property-buying-checklist/?utm_source=test')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response['Location'],
            f'/ru/blog/{BUYING_GUIDE_BLOG_SLUG}/?utm_source=test',
        )

    def test_legacy_english_checklist_slug_redirects_to_blog_article(self):
        response = self.client.get('/en/blog/checklist-buyer-real-estate-thailand/')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], f'/en/blog/{BUYING_GUIDE_BLOG_SLUG}/')


class BlogSvgInlineTests(SimpleTestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

    def test_local_editor_svg_is_inlined_with_accessible_text(self):
        default_storage.save(
            'blog/editor/keypoints.svg',
            ContentFile('''
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 430" width="800" height="430">
              <title>Ключевые выводы | Рынок недвижимости Таиланда 2026</title>
              <script>alert(1)</script>
              <text x="20" y="26">Ключевые выводы</text>
              <text x="20" y="46">Рынок недвижимости Таиланда 2026</text>
              <text x="32" y="77">Спрос на кондо сохраняется</text>
            </svg>
            '''.encode('utf-8')),
        )
        html = '<p><img src="../../../../media/blog/editor/keypoints.svg" alt="" width="800" height="430"></p>'

        _, processed_content = _extract_blog_toc_and_content(html)

        self.assertIn('<svg', processed_content)
        self.assertIn('data-inline-blog-svg="true"', processed_content)
        self.assertIn('role="img"', processed_content)
        self.assertIn('aria-labelledby="blog-svg-title-1 blog-svg-desc-1"', processed_content)
        self.assertIn('Ключевые выводы | Рынок недвижимости Таиланда 2026', processed_content)
        self.assertIn('Спрос на кондо сохраняется', processed_content)
        self.assertIn('class="blog-inline-svg"', processed_content)
        self.assertNotIn('<img', processed_content)
        self.assertNotIn('<script', processed_content)

    def test_absolute_local_editor_svg_is_inlined_for_allowed_host(self):
        default_storage.save(
            'blog/editor/absolute.svg',
            ContentFile('''
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 430">
              <title>Инфографика рынка Пхукета</title>
              <text x="20" y="26">Данные рынка Пхукета</text>
            </svg>
            '''.encode('utf-8')),
        )
        html = '<p><img src="https://undersunestate.com/media/blog/editor/absolute.svg" alt=""></p>'

        with override_settings(ALLOWED_HOSTS=['undersunestate.com']):
            _, processed_content = _extract_blog_toc_and_content(html)

        self.assertIn('<svg', processed_content)
        self.assertIn('Инфографика рынка Пхукета', processed_content)
        self.assertNotIn('<img', processed_content)

    def test_external_svg_image_is_not_inlined(self):
        html = '<p><img src="https://example.com/chart.svg" alt="External chart"></p>'

        _, processed_content = _extract_blog_toc_and_content(html)

        self.assertIn('<img src="https://example.com/chart.svg"', processed_content)
        self.assertNotIn('data-inline-blog-svg', processed_content)


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
