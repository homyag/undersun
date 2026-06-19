import json
import os
import re
import xml.etree.ElementTree as ET
from html import unescape as html_unescape

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse
from urllib.parse import unquote, urlparse
from django.utils.text import slugify
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.models import SEOPage
from apps.core.utils import truncate_meta
from apps.core.amp_utils import convert_html_to_amp
from apps.currency.services import CurrencyService

from .models import BlogPost, BlogCategory, BlogTag
from .services import (
    build_blog_item_list_schema,
    build_blog_post_schema,
    build_blog_search_schema,
    build_breadcrumb_schema,
)


PAGE_LABELS = {
    'ru': 'Страница {page}',
    'en': 'Page {page}',
    'th': 'หน้า {page}',
}

BLOG_META_STRINGS = {
    'ru': {
        'site_title': 'Блог Undersun Estate',
        'site_h1': 'Блог Undersun Estate',
        'category_title': '{name} — блог Undersun Estate',
        'category_description': 'Материалы категории {name} в блоге Undersun Estate: обзоры рынка, инвестиционные советы и новости недвижимости Пхукета.',
        'tag_title': 'Статьи о {name} — блог Undersun Estate',
        'tag_description': 'Подборка статей с тегом {name} в блоге Undersun Estate о недвижимости, инвестициях и жизни на Пхукете.',
        'search_title': 'Поиск по блогу: {query} — Undersun Estate',
        'search_description': 'Результаты поиска по запросу “{query}” в блоге Undersun Estate.',
        'post_title': '{title} — блог Undersun Estate',
    },
    'en': {
        'site_title': 'Undersun Estate Blog',
        'site_h1': 'Undersun Estate Blog',
        'category_title': '{name} — Undersun Estate Blog',
        'category_description': 'Posts in the {name} category from the Undersun Estate blog: Phuket property insights, investment tips and market updates.',
        'tag_title': 'Articles about {name} — Undersun Estate Blog',
        'tag_description': 'A selection of blog posts tagged {name} covering Phuket real estate, investment and lifestyle topics.',
        'search_title': 'Blog search: {query} — Undersun Estate',
        'search_description': 'Search results for “{query}” in the Undersun Estate blog.',
        'post_title': '{title} — Undersun Estate Blog',
    },
    'th': {
        'site_title': 'บล็อก Undersun Estate',
        'site_h1': 'บล็อก Undersun Estate',
        'category_title': '{name} — บล็อก Undersun Estate',
        'category_description': 'บทความในหมวด {name} จากบล็อก Undersun Estate ครอบคลุมอินไซต์ตลาด อสังหาริมทรัพย์ภูเก็ต และคำแนะนำด้านการลงทุน.',
        'tag_title': 'บทความเกี่ยวกับ {name} — บล็อก Undersun Estate',
        'tag_description': 'รวมบทความที่ติดแท็ก {name} เกี่ยวกับอสังหาริมทรัพย์ การลงทุน และไลฟ์สไตล์ในภูเก็ต.',
        'search_title': 'ค้นหาในบล็อก: {query} — Undersun Estate',
        'search_description': 'ผลการค้นหา “{query}” ในบล็อก Undersun Estate.',
        'post_title': '{title} — บล็อก Undersun Estate',
    },
}

BLOG_INTRO_STRINGS = {
    'ru': {
        'root_eyebrow': 'Экспертиза Undersun Estate',
        'root_lead': 'В блоге мы публикуем аналитические обзоры рынка Пхукета, практические рекомендации по покупке недвижимости и материалы для инвесторов.',
        'root_body': 'Используйте статьи для ориентира по районам, форматам объектов, доходности и текущим изменениям рынка.',
        'category_eyebrow': 'Категория блога',
        'category_body': 'В этом разделе собраны материалы по теме {name}: актуальные обзоры, кейсы и комментарии команды Undersun Estate.',
        'tag_eyebrow': 'Подборка по теме',
        'tag_lead': 'На этой странице собраны статьи с тегом {name}.',
        'tag_body': 'Подборка помогает быстро перейти к связанным публикациям и изучить тему глубже.',
        'posts_count_one': '{count} статья',
        'posts_count_few': '{count} статьи',
        'posts_count_many': '{count} статей',
    },
    'en': {
        'root_eyebrow': 'Undersun Estate Insights',
        'root_lead': 'Our blog covers Phuket market analysis, practical buying guidance and editorial content for property investors.',
        'root_body': 'Use these articles to navigate areas, property formats, investment considerations and current market changes.',
        'category_eyebrow': 'Blog category',
        'category_body': 'This section gathers content about {name}: market reviews, case studies and commentary from the Undersun Estate team.',
        'tag_eyebrow': 'Topic collection',
        'tag_lead': 'This page features blog posts tagged {name}.',
        'tag_body': 'It helps readers move through related publications and explore the topic in more depth.',
        'posts_count_one': '{count} article',
        'posts_count_many': '{count} articles',
    },
    'th': {
        'root_eyebrow': 'อินไซต์จาก Undersun Estate',
        'root_lead': 'บล็อกของเรานำเสนอการวิเคราะห์ตลาดภูเก็ต คำแนะนำเชิงปฏิบัติในการซื้ออสังหาริมทรัพย์ และบทความสำหรับนักลงทุน.',
        'root_body': 'ใช้บทความเหล่านี้เพื่อทำความเข้าใจทำเล ประเภททรัพย์ ประเด็นการลงทุน และการเปลี่ยนแปลงของตลาดปัจจุบัน.',
        'category_eyebrow': 'หมวดหมู่บล็อก',
        'category_body': 'ส่วนนี้รวบรวมเนื้อหาเกี่ยวกับ {name} ทั้งบทวิเคราะห์ เคสศึกษา และมุมมองจากทีม Undersun Estate.',
        'tag_eyebrow': 'รวมบทความตามหัวข้อ',
        'tag_lead': 'หน้านี้รวบรวมบทความที่ติดแท็ก {name}.',
        'tag_body': 'ช่วยให้ผู้อ่านเข้าถึงบทความที่เกี่ยวข้องและศึกษาหัวข้อนี้ได้ลึกขึ้น.',
        'posts_count_many': '{count} บทความ',
    },
}


BLOG_SEO_DEFAULTS = {
    'ru': {
        'title': 'Блог Undersun Estate: недвижимость Пхукета и инвестиции',
        'description': 'Аналитика рынка Пхукета, советы по покупке вилл и апартаментов, истории сделок и новости от экспертов Undersun Estate.',
    },
    'en': {
        'title': 'Undersun Estate Blog — Phuket Real Estate & Investment Insights',
        'description': 'Market news, purchase guides, ROI tips and agency stories about Phuket property investments from the Undersun Estate team.',
    },
    'th': {
        'title': 'บล็อก Undersun Estate – อินไซต์อสังหาริมทรัพย์ภูเก็ตและการลงทุน',
        'description': 'อัปเดตตลาด คู่มือการซื้อ และเคล็ดลับการลงทุนอสังหาริมทรัพย์ในภูเก็ตที่คัดสรรโดยทีม Undersun Estate.',
    },
}


HEADING_PATTERN = re.compile(r'<h([23])([^>]*)>(.*?)</h\1>', re.IGNORECASE | re.DOTALL)
HEADING_ID_PATTERN = re.compile(r'\sid=(["\'])(.*?)\1', re.IGNORECASE)
IMG_TAG_PATTERN = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
TINYMCE_ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
TINYMCE_MAX_UPLOAD_SIZE = 5 * 1024 * 1024
TINYMCE_INLINE_SVG_PREFIXES = ('blog/editor/',)
SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
XLINK_NAMESPACE = 'http://www.w3.org/1999/xlink'
SVG_BLOCKED_DECLARATION_PATTERN = re.compile(r'<!\s*(DOCTYPE|ENTITY)\b', re.IGNORECASE)
SVG_URL_PATTERN = re.compile(r'url\(\s*([^)]+?)\s*\)', re.IGNORECASE)
SVG_UNSAFE_VALUE_TOKENS = (
    'javascript:',
    'vbscript:',
    'data:text/html',
    '<script',
    '</script',
    'expression(',
    '@import',
)
SVG_ALLOWED_TAGS = {
    'svg',
    'g',
    'defs',
    'title',
    'desc',
    'path',
    'rect',
    'circle',
    'ellipse',
    'line',
    'polyline',
    'polygon',
    'text',
    'tspan',
    'lineargradient',
    'radialgradient',
    'stop',
    'clippath',
    'mask',
    'pattern',
    'symbol',
    'use',
    'a',
}
SVG_ALLOWED_ATTRS = {
    'id',
    'class',
    'role',
    'aria-label',
    'focusable',
    'version',
    'viewbox',
    'preserveaspectratio',
    'width',
    'height',
    'x',
    'y',
    'x1',
    'y1',
    'x2',
    'y2',
    'cx',
    'cy',
    'r',
    'rx',
    'ry',
    'd',
    'points',
    'transform',
    'fill',
    'fill-rule',
    'fill-opacity',
    'font-family',
    'font-size',
    'font-style',
    'font-weight',
    'stroke',
    'stroke-width',
    'stroke-linecap',
    'stroke-linejoin',
    'stroke-miterlimit',
    'stroke-dasharray',
    'stroke-dashoffset',
    'stroke-opacity',
    'opacity',
    'style',
    'offset',
    'stop-color',
    'stop-opacity',
    'gradientunits',
    'gradienttransform',
    'patternunits',
    'patterncontentunits',
    'clip-path',
    'clip-rule',
    'mask',
    'text-anchor',
    'text-decoration',
    'href',
    'target',
    'rel',
}

ET.register_namespace('', SVG_NAMESPACE)
ET.register_namespace('xlink', XLINK_NAMESPACE)


def _svg_local_name(name):
    if name.startswith('{'):
        return name.rsplit('}', 1)[-1]
    return name


def _is_safe_svg_attr_value(tag_name, attr_name, value):
    normalized = html_unescape(str(value or '')).strip().lower()
    if any(token in normalized for token in SVG_UNSAFE_VALUE_TOKENS):
        return False

    if attr_name == 'href':
        if tag_name == 'a':
            return (
                normalized.startswith('#')
                or normalized.startswith('https://')
                or normalized.startswith('http://')
            )
        return normalized.startswith('#')

    for match in SVG_URL_PATTERN.finditer(normalized):
        target = match.group(1).strip(' \'"')
        if not target.startswith('#'):
            return False

    return True


def _sanitize_svg_element(element):
    tag_name = _svg_local_name(element.tag).lower()

    for child in list(element):
        child_name = _svg_local_name(child.tag).lower()
        if child_name not in SVG_ALLOWED_TAGS:
            element.remove(child)
            continue
        _sanitize_svg_element(child)

    for attr_name in list(element.attrib):
        local_attr_name = _svg_local_name(attr_name).lower()
        if (
            local_attr_name.startswith('on')
            or local_attr_name not in SVG_ALLOWED_ATTRS
            or not _is_safe_svg_attr_value(tag_name, local_attr_name, element.attrib[attr_name])
        ):
            del element.attrib[attr_name]


def _sanitize_svg_upload(uploaded_file):
    raw_content = uploaded_file.read()
    try:
        svg_text = raw_content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Invalid SVG encoding. Use UTF-8 SVG files.') from exc

    root = _parse_and_sanitize_svg(svg_text)
    return ET.tostring(root, encoding='utf-8', method='xml')


def _parse_and_sanitize_svg(svg_text):
    if SVG_BLOCKED_DECLARATION_PATTERN.search(svg_text):
        raise ValueError('Invalid SVG content. DOCTYPE and ENTITY declarations are not allowed.')

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise ValueError('Invalid SVG file.') from exc

    if _svg_local_name(root.tag).lower() != 'svg':
        raise ValueError('Invalid SVG file. Root element must be <svg>.')

    _sanitize_svg_element(root)
    return root


def _normalize_svg_accessible_text(value):
    return re.sub(r'\s+', ' ', html_unescape(str(value or ''))).strip()


def _collect_svg_accessible_text(root):
    title = ''
    desc = ''
    text_lines = []

    for element in root.iter():
        tag_name = _svg_local_name(element.tag).lower()
        text_value = _normalize_svg_accessible_text(''.join(element.itertext()))
        if not text_value:
            continue
        if tag_name == 'title' and not title:
            title = text_value
        elif tag_name == 'desc' and not desc:
            desc = text_value
        elif tag_name == 'text':
            if not text_lines or text_lines[-1] != text_value:
                text_lines.append(text_value)

    return title, desc, text_lines


def _resolve_local_blog_svg_path(src):
    if not src:
        return ''

    parsed = urlparse(html_unescape(src))
    if parsed.scheme and parsed.scheme not in {'http', 'https'}:
        return ''
    if parsed.netloc:
        source_host = parsed.netloc.split(':', 1)[0].lower()
        allowed_hosts = {
            host.lstrip('.').lower()
            for host in getattr(settings, 'ALLOWED_HOSTS', [])
            if host and host != '*'
        }
        if not allowed_hosts or not any(
            source_host == host or source_host.endswith(f'.{host}')
            for host in allowed_hosts
        ):
            return ''

    raw_path = unquote(parsed.path or src)
    media_url_path = urlparse(settings.MEDIA_URL).path or '/media/'
    media_rel_path = ''

    if raw_path.startswith(media_url_path):
        media_rel_path = raw_path[len(media_url_path):]
    elif raw_path.startswith('media/'):
        media_rel_path = raw_path[len('media/'):]
    elif '/media/' in raw_path:
        media_rel_path = raw_path.split('/media/', 1)[1]
    elif 'media/' in raw_path:
        media_rel_path = raw_path.split('media/', 1)[1]

    media_rel_path = media_rel_path.lstrip('/').replace('\\', '/')
    normalized_path = os.path.normpath(media_rel_path).replace('\\', '/')
    if (
        not normalized_path
        or normalized_path.startswith('../')
        or normalized_path == '..'
        or not normalized_path.lower().endswith('.svg')
        or not any(normalized_path.startswith(prefix) for prefix in TINYMCE_INLINE_SVG_PREFIXES)
    ):
        return ''

    return normalized_path


def _ensure_svg_child_text(root, tag_name, text_value, element_id, insert_index=0):
    namespace_tag = f'{{{SVG_NAMESPACE}}}{tag_name}'
    for child in list(root):
        if _svg_local_name(child.tag).lower() == tag_name:
            if text_value and not _normalize_svg_accessible_text(''.join(child.itertext())):
                child.text = text_value
            child.set('id', element_id)
            return child

    child = ET.Element(namespace_tag)
    child.set('id', element_id)
    child.text = text_value
    root.insert(insert_index, child)
    return child


def _build_inline_blog_svg(svg_path, img_tag, index):
    try:
        if not default_storage.exists(svg_path):
            return ''
        if default_storage.size(svg_path) > TINYMCE_MAX_UPLOAD_SIZE:
            return ''
        with default_storage.open(svg_path, 'rb') as svg_file:
            svg_text = svg_file.read().decode('utf-8-sig')
        root = _parse_and_sanitize_svg(svg_text)
    except (OSError, UnicodeDecodeError, ValueError):
        return ''

    title, desc, text_lines = _collect_svg_accessible_text(root)
    img_alt = _normalize_svg_accessible_text(img_tag.get('alt', ''))
    accessible_title = title or img_alt or (text_lines[0] if text_lines else '')
    if not accessible_title:
        return ''

    desc_source = desc or ' '.join(line for line in text_lines if line != accessible_title)
    accessible_desc = truncate_meta(desc_source, limit=1200) if desc_source else ''
    title_id = f'blog-svg-title-{index}'
    desc_id = f'blog-svg-desc-{index}'

    _ensure_svg_child_text(root, 'title', accessible_title, title_id, insert_index=0)
    labelled_by = [title_id]
    if accessible_desc:
        _ensure_svg_child_text(root, 'desc', accessible_desc, desc_id, insert_index=1)
        labelled_by.append(desc_id)

    root.set('role', 'img')
    root.set('focusable', 'false')
    root.set('aria-labelledby', ' '.join(labelled_by))
    root.set('data-inline-blog-svg', 'true')

    img_classes = img_tag.get('class') or []
    if isinstance(img_classes, str):
        img_classes = img_classes.split()
    svg_classes = (root.get('class') or '').split()
    class_names = []
    for class_name in [*svg_classes, *img_classes, 'blog-inline-svg']:
        if class_name and class_name not in class_names:
            class_names.append(class_name)
    root.set('class', ' '.join(class_names))

    if img_tag.get('width') and not root.get('width'):
        root.set('width', img_tag['width'])
    if img_tag.get('height') and not root.get('height'):
        root.set('height', img_tag['height'])

    return ET.tostring(root, encoding='unicode', method='xml')


def _inline_blog_svg_images(html_content):
    if not html_content or '.svg' not in html_content.lower():
        return html_content

    inline_counter = 0

    def _replace(match):
        nonlocal inline_counter
        img_html = match.group(0)
        soup = BeautifulSoup(img_html, 'html.parser')
        img_tag = soup.find('img')
        if not img_tag:
            return img_html

        svg_path = _resolve_local_blog_svg_path(img_tag.get('src', ''))
        if not svg_path:
            return img_html

        inline_counter += 1
        inline_svg = _build_inline_blog_svg(svg_path, img_tag, inline_counter)
        return inline_svg or img_html

    return IMG_TAG_PATTERN.sub(_replace, html_content)


def _extract_blog_toc_and_content(html_content):
    """Добавляет id к h2/h3 и возвращает TOC для статьи."""
    if not html_content:
        return [], html_content

    toc_items = []
    used_ids = set()

    def _replace(match):
        level = int(match.group(1))
        attrs = match.group(2) or ''
        inner_html = match.group(3) or ''
        heading_text = html_unescape(strip_tags(inner_html)).replace('\xa0', ' ').strip()

        if not heading_text:
            return match.group(0)

        existing_id_match = HEADING_ID_PATTERN.search(attrs)
        if existing_id_match:
            heading_id = existing_id_match.group(2)
        else:
            base_id = slugify(heading_text) or f'section-{len(toc_items) + 1}'
            heading_id = base_id
            suffix = 2
            while heading_id in used_ids:
                heading_id = f'{base_id}-{suffix}'
                suffix += 1
            attrs = f'{attrs} id="{heading_id}"'

        used_ids.add(heading_id)
        toc_items.append({
            'level': level,
            'id': heading_id,
            'title': heading_text,
        })
        return f'<h{level}{attrs}>{inner_html}</h{level}>'

    processed_content = HEADING_PATTERN.sub(_replace, html_content)
    processed_content = _inline_blog_svg_images(processed_content)
    return toc_items, processed_content


def _append_suffix_if_needed(value, suffix):
    if not suffix:
        return value

    if not value:
        return suffix.strip(' |')

    normalized_value = value.lower()
    normalized_suffix = suffix.lower().strip()
    if normalized_suffix and normalized_suffix in normalized_value:
        return value

    return f"{value}{suffix}"


def _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj):
    if not page_obj:
        return meta_title, meta_description

    try:
        page_number = int(page_obj.number)
    except (TypeError, ValueError, AttributeError):
        page_number = 1

    if page_number <= 1:
        return meta_title, meta_description

    language = (language_code or 'ru')[:2]
    label_template = PAGE_LABELS.get(language, PAGE_LABELS['en'])
    pagination_label = label_template.format(page=page_number)
    pagination_suffix = f" | {pagination_label}"

    updated_title = _append_suffix_if_needed(meta_title, pagination_suffix)
    updated_description = _append_suffix_if_needed(meta_description, pagination_suffix)

    return updated_title, updated_description


def _get_seo_page_meta(page_name, language_code='ru'):
    """Забираем title/description/keywords для указанной SEO страницы."""
    try:
        seo_page = SEOPage.objects.get(page_name=page_name, is_active=True)
    except SEOPage.DoesNotExist:
        return {}

    return {
        'title': seo_page.get_title(language_code),
        'description': seo_page.get_description(language_code),
        'keywords': seo_page.get_keywords(language_code),
    }


def _get_blog_language(language_code='ru'):
    return (language_code or 'ru')[:2]


def _get_blog_strings(language_code='ru'):
    return BLOG_META_STRINGS.get(_get_blog_language(language_code), BLOG_META_STRINGS['ru'])


def _get_blog_intro_strings(language_code='ru'):
    return BLOG_INTRO_STRINGS.get(_get_blog_language(language_code), BLOG_INTRO_STRINGS['ru'])


def _get_translated_attr(instance, field_name, language_code='ru', fallback=''):
    if instance is None:
        return fallback

    language_code = _get_blog_language(language_code)
    localized_field_name = field_name if language_code == 'ru' else f'{field_name}_{language_code}'
    value = getattr(instance, localized_field_name, None) or getattr(instance, field_name, None) or fallback
    if isinstance(value, str):
        return value.strip()
    return value


def _build_blog_listing_url(url_name, *, slug=None, page=None):
    kwargs = {'slug': slug} if slug else {}
    url = reverse(url_name, kwargs=kwargs)
    if page:
        try:
            page_number = int(page)
        except (TypeError, ValueError):
            page_number = 1
        if page_number > 1:
            return f'{url}?page={page_number}'
    return url


def _set_blog_indexation(request, *, canonical_url='', meta_robots=''):
    request.canonical_url_override = canonical_url
    request.seo_meta_robots = meta_robots


def _build_blog_root_meta(language_code='ru', page_obj=None):
    seo_meta = _get_seo_page_meta('blog', language_code)
    defaults = BLOG_SEO_DEFAULTS.get(language_code, BLOG_SEO_DEFAULTS['ru'])
    meta_title = seo_meta.get('title') or defaults['title']
    meta_description = seo_meta.get('description') or defaults['description']
    meta_keywords = seo_meta.get('keywords')
    meta_title, meta_description = _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj)
    return meta_title, truncate_meta(meta_description), meta_keywords


def _build_blog_category_meta(category, language_code='ru', page_obj=None):
    strings = _get_blog_strings(language_code)
    category_name = _get_translated_attr(category, 'name', language_code, category.name)
    category_description = _get_translated_attr(category, 'description', language_code, '')
    meta_title = _get_translated_attr(category, 'meta_title', language_code, '') or strings['category_title'].format(name=category_name)
    meta_description = _get_translated_attr(category, 'meta_description', language_code, '') or category_description or strings['category_description'].format(name=category_name)
    meta_keywords = _get_translated_attr(category, 'meta_keywords', language_code, '')
    meta_title, meta_description = _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj)
    return meta_title, truncate_meta(meta_description), meta_keywords


def _build_blog_tag_meta(tag, language_code='ru', page_obj=None):
    strings = _get_blog_strings(language_code)
    meta_title = strings['tag_title'].format(name=tag.name)
    meta_description = strings['tag_description'].format(name=tag.name)
    meta_title, meta_description = _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj)
    return meta_title, truncate_meta(meta_description), ''


def _build_blog_search_meta(search_query, language_code='ru', page_obj=None):
    strings = _get_blog_strings(language_code)
    query = (search_query or '').strip()
    meta_title = strings['search_title'].format(query=query)
    meta_description = strings['search_description'].format(query=query)
    meta_title, meta_description = _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj)
    return meta_title, truncate_meta(meta_description), ''


def _build_blog_post_meta(post, language_code='ru'):
    strings = _get_blog_strings(language_code)
    translated_title = post._get_translated_value('title', language_code)
    raw_meta_title = _get_translated_attr(post, 'meta_title', language_code, '')
    meta_title = raw_meta_title or strings['post_title'].format(title=translated_title)
    meta_description = truncate_meta(post.get_meta_description(language_code))
    meta_keywords = post.get_meta_keywords(language_code)
    return meta_title, meta_description, meta_keywords


def _get_blog_linked_property_links(post, request):
    """Return active property links prepared for blog templates."""
    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    currency_code = CurrencyService.get_selected_currency_code(request)
    links = list(
        post.property_links
        .filter(property__is_active=True)
        .select_related(
            'property',
            'property__property_type',
            'property__district',
            'property__location',
        )
        .prefetch_related('property__images')
        .order_by('order', 'id')
    )

    visible_links = []
    for link in links:
        property_obj = link.property
        if language_code in {'en', 'th'} and not getattr(property_obj, f'title_{language_code}', ''):
            continue
        deal_type = 'sale' if property_obj.deal_type in {'sale', 'both'} else 'rent'
        link.display_deal_type = deal_type
        link.display_price = property_obj.get_formatted_price(currency_code, deal_type)
        link.display_property_type = property_obj._get_translated_type_name(language_code)
        visible_links.append(link)

    return visible_links


def _build_blog_list_heading(*, language_code='ru', current_category=None, current_tag=None, search_query=''):
    strings = _get_blog_strings(language_code)
    if current_category:
        return _get_translated_attr(current_category, 'name', language_code, current_category.name)
    if current_tag:
        return f"{_('Статьи с тегом')} \"{current_tag.name}\""
    if search_query:
        return _('Результаты поиска')
    return strings['site_h1']


def _format_posts_count(count, language_code='ru'):
    strings = _get_blog_intro_strings(language_code)
    count = max(int(count or 0), 0)
    if language_code == 'ru':
        mod10 = count % 10
        mod100 = count % 100
        if mod10 == 1 and mod100 != 11:
            return strings['posts_count_one'].format(count=count)
        if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
            return strings['posts_count_few'].format(count=count)
        return strings['posts_count_many'].format(count=count)
    if language_code == 'en':
        key = 'posts_count_one' if count == 1 else 'posts_count_many'
        return strings[key].format(count=count)
    return strings['posts_count_many'].format(count=count)


def _build_blog_intro(*, language_code='ru', current_category=None, current_tag=None, posts_count=0, search_query=''):
    if search_query:
        return None

    strings = _get_blog_intro_strings(language_code)
    posts_label = _format_posts_count(posts_count, language_code)

    if current_category:
        category_name = _get_translated_attr(current_category, 'name', language_code, current_category.name)
        category_description = _get_translated_attr(current_category, 'description', language_code, '')
        return {
            'eyebrow': strings['category_eyebrow'],
            'lead': category_description or strings['category_body'].format(name=category_name),
            'body': strings['category_body'].format(name=category_name),
            'meta': posts_label,
        }

    if current_tag:
        return {
            'eyebrow': strings['tag_eyebrow'],
            'lead': strings['tag_lead'].format(name=current_tag.name),
            'body': strings['tag_body'],
            'meta': posts_label,
        }

    return {
        'eyebrow': strings['root_eyebrow'],
        'lead': strings['root_lead'],
        'body': strings['root_body'],
        'meta': posts_label,
    }


def blog_list(request):
    """Список всех статей блога"""
    posts = BlogPost.get_published().prefetch_related('tags')
    language_code = getattr(request, 'LANGUAGE_CODE', 'ru')[:2]
    unsupported_query_params = set(request.GET) - {'page', 'category', 'tag', 'search'}

    category_slug = (request.GET.get('category') or '').strip()
    tag_slug = (request.GET.get('tag') or '').strip()
    search_query = (request.GET.get('search') or '').strip()
    page_number = request.GET.get('page')

    if category_slug and not tag_slug and not search_query:
        category_for_redirect = BlogCategory.objects.filter(slug=category_slug, is_active=True).first()
        if category_for_redirect:
            return HttpResponsePermanentRedirect(
                _build_blog_listing_url('blog:category', slug=category_for_redirect.slug, page=page_number)
            )

    if tag_slug and not category_slug and not search_query:
        tag_for_redirect = BlogTag.objects.filter(slug=tag_slug).first()
        if tag_for_redirect:
            return HttpResponsePermanentRedirect(
                _build_blog_listing_url('blog:tag', slug=tag_for_redirect.slug, page=page_number)
            )

    # Фильтрация по категории
    if category_slug:
        category = get_object_or_404(BlogCategory, slug=category_slug, is_active=True)
        posts = posts.filter(category=category)
    else:
        category = None

    # Фильтрация по тегу
    if tag_slug:
        tag = get_object_or_404(BlogTag, slug=tag_slug)
        posts = posts.filter(tags=tag)
    else:
        tag = None

    # Поиск
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query) |
            Q(content__icontains=search_query)
        )

    # Пагинация
    paginator = Paginator(posts, getattr(settings, 'PAGINATE_BY', 12))
    page_obj = paginator.get_page(page_number)

    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()

    if search_query:
        meta_title, meta_description, meta_keywords = _build_blog_search_meta(search_query, language_code, page_obj)
    elif category:
        meta_title, meta_description, meta_keywords = _build_blog_category_meta(category, language_code, page_obj)
    elif tag:
        meta_title, meta_description, meta_keywords = _build_blog_tag_meta(tag, language_code, page_obj)
    else:
        meta_title, meta_description, meta_keywords = _build_blog_root_meta(language_code, page_obj)

    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'categories': categories,
        'featured_posts': featured_posts,
        'current_category': category,
        'current_tag': tag,
        'search_query': search_query,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'page_keywords': meta_keywords,
        'page_h1': _build_blog_list_heading(
            language_code=language_code,
            current_category=category,
            current_tag=tag,
            search_query=search_query,
        ),
    }
    context['blog_intro'] = _build_blog_intro(
        language_code=language_code,
        current_category=category,
        current_tag=tag,
        posts_count=paginator.count,
        search_query=search_query,
    )

    if search_query or category or tag or unsupported_query_params:
        if category and not tag:
            canonical_url = _build_blog_listing_url('blog:category', slug=category.slug)
        elif tag and not category:
            canonical_url = _build_blog_listing_url('blog:tag', slug=tag.slug)
        else:
            canonical_url = reverse('blog:list')
        context['meta_robots'] = 'noindex, follow'
        context['canonical_url'] = request.build_absolute_uri(canonical_url)
        _set_blog_indexation(request, canonical_url=canonical_url, meta_robots='noindex, follow')

    if not search_query and not category and not tag:
        page_url = request.build_absolute_uri()
        item_list_schema = build_blog_item_list_schema(
            page_obj.object_list,
            request,
            language_code=language_code,
            title=meta_title,
            description=meta_description,
            page_url=page_url,
        )
        if item_list_schema:
            context['schema_blog_list_json'] = json.dumps(item_list_schema, ensure_ascii=False)

        search_schema = build_blog_search_schema(request)
        if search_schema:
            context['schema_blog_search_json'] = json.dumps(search_schema, ensure_ascii=False)

    breadcrumb_items = [
        (_('Главная'), reverse('core:home')),
        (_('Блог'), reverse('blog:list')),
    ]
    if category and not tag:
        breadcrumb_items.append((_get_translated_attr(category, 'name', language_code, category.name), category.get_absolute_url()))
    elif tag and not category:
        breadcrumb_items.append((tag.name, tag.get_absolute_url()))
    elif search_query:
        breadcrumb_items.append((_('Поиск'), None))

    breadcrumb_schema = build_breadcrumb_schema(breadcrumb_items, request)
    if breadcrumb_schema:
        context['schema_blog_breadcrumb_json'] = json.dumps(breadcrumb_schema, ensure_ascii=False)
    
    return render(request, 'blog/blog_list.html', context)


def blog_detail(request, slug):
    """Детальная страница статьи"""
    post = get_object_or_404(
        BlogPost.objects.select_related('category', 'author', 'team_author').prefetch_related('tags'),
        slug=slug,
        status='published'
    )
    
    # Увеличиваем счетчик просмотров
    post.increment_views()
    
    # Получаем похожие статьи (из той же категории)
    related_posts = BlogPost.get_published().filter(
        category=post.category
    ).exclude(id=post.id)[:3]

    more_from_category = BlogPost.get_published().filter(
        category=post.category
    ).exclude(id=post.id)
    if related_posts:
        more_from_category = more_from_category.exclude(id__in=[item.id for item in related_posts])
    more_from_category = more_from_category[:4]
    
    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()
    
    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title, meta_description, meta_keywords = _build_blog_post_meta(post, language_code)
    article_toc, processed_content = _extract_blog_toc_and_content(post.content)
    linked_property_links = _get_blog_linked_property_links(post, request)

    amp_url = request.build_absolute_uri(
        reverse('blog:detail_amp', kwargs={'slug': slug})
    )

    context = {
        'post': post,
        'related_posts': related_posts,
        'more_from_category': more_from_category,
        'categories': categories,
        'featured_posts': featured_posts,
        'article_toc': article_toc,
        'processed_content': processed_content,
        'linked_property_links': linked_property_links,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'page_description': meta_description,
        'page_keywords': meta_keywords,
        'amp_url': amp_url,
        'metrika_counter_id': getattr(settings, 'METRIKA_COUNTER_ID', 90630603),
        'amp_metrika_params': json.dumps({
            'post_id': post.id,
            'slug': post.slug,
            'category': post.category.slug if post.category else '',
            'language': language_code,
            'is_amp': True,
        }, ensure_ascii=False),
    }

    default_image_url = request.build_absolute_uri(static('images/og-image.jpg'))
    og_image_url = post.get_featured_image_absolute_url(request, getattr(request, 'LANGUAGE_CODE', 'ru'))
    if og_image_url:
        context['og_image_url'] = og_image_url

    schema_image_url = og_image_url or default_image_url

    schema_post = build_blog_post_schema(
        post,
        request,
        language_code=language_code,
        meta_description=meta_description,
        image_url=schema_image_url,
    )
    if schema_post:
        context['schema_blog_post_json'] = json.dumps(schema_post, ensure_ascii=False)

    breadcrumb_schema = build_breadcrumb_schema([
        (_('Главная'), reverse('core:home')),
        (_('Блог'), reverse('blog:list')),
        (_get_translated_attr(post.category, 'name', language_code, post.category.name) if post.category else None, post.category.get_absolute_url() if post.category else None),
        (post.title, post.get_absolute_url()),
    ], request)
    if breadcrumb_schema:
        context['schema_blog_breadcrumb_json'] = json.dumps(breadcrumb_schema, ensure_ascii=False)

    return render(request, 'blog/blog_detail.html', context)


def blog_detail_amp(request, slug):
    post = get_object_or_404(
        BlogPost.objects.select_related('category', 'author', 'team_author').prefetch_related('tags'),
        slug=slug,
        status='published'
    )

    related_posts = BlogPost.get_published().filter(
        category=post.category
    ).exclude(id=post.id)[:3]

    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title = post.get_meta_title(language_code)
    meta_description = truncate_meta(post.get_meta_description(language_code))
    meta_keywords = post.get_meta_keywords(language_code)
    linked_property_links = _get_blog_linked_property_links(post, request)

    canonical_url = request.build_absolute_uri(
        reverse('blog:detail', kwargs={'slug': slug})
    )

    og_image_url = post.get_featured_image_absolute_url(request, getattr(request, 'LANGUAGE_CODE', 'ru'))
    default_amp_image = request.build_absolute_uri(static('images/og-image.jpg'))

    context = {
        'post': post,
        'related_posts': related_posts,
        'linked_property_links': linked_property_links,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'page_description': meta_description,
        'canonical_url': canonical_url,
        'amp_content': convert_html_to_amp(post.content),
        'og_image_url': og_image_url,
        'default_amp_image': default_amp_image,
        'metrika_counter_id': getattr(settings, 'METRIKA_COUNTER_ID', 90630603),
        'amp_metrika_params': json.dumps({
            'post_id': post.id,
            'slug': post.slug,
            'category': post.category.slug if post.category else '',
            'language': language_code,
            'is_amp': True,
        }, ensure_ascii=False),
    }

    schema_image_url = og_image_url or default_amp_image
    schema_post = build_blog_post_schema(
        post,
        request,
        language_code=language_code,
        meta_description=meta_description,
        image_url=schema_image_url,
    )
    if schema_post:
        context['schema_blog_post_json'] = json.dumps(schema_post, ensure_ascii=False)

    breadcrumb_schema = build_breadcrumb_schema([
        (_('Главная'), reverse('core:home')),
        (_('Блог'), reverse('blog:list')),
        (_get_translated_attr(post.category, 'name', language_code, post.category.name) if post.category else None, post.category.get_absolute_url() if post.category else None),
        (post.title, post.get_absolute_url()),
    ], request)
    if breadcrumb_schema:
        context['schema_blog_breadcrumb_json'] = json.dumps(breadcrumb_schema, ensure_ascii=False)

    return render(request, 'blog/blog_detail_amp.html', context)


def blog_category(request, slug):
    """Статьи определенной категории"""
    category = get_object_or_404(BlogCategory, slug=slug, is_active=True)
    posts = BlogPost.get_published().filter(category=category).prefetch_related('tags')
    
    # Пагинация
    paginator = Paginator(posts, getattr(settings, 'PAGINATE_BY', 12))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()
    
    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title, meta_description, meta_keywords = _build_blog_category_meta(category, language_code, page_obj)

    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'category': category,
        'current_category': category,
        'current_tag': None,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'page_keywords': meta_keywords,
    }
    context['blog_intro'] = _build_blog_intro(
        language_code=language_code,
        current_category=category,
        posts_count=paginator.count,
    )

    page_url = request.build_absolute_uri()
    category_name = _get_translated_attr(category, 'name', language_code, category.name)
    category_description = _get_translated_attr(category, 'description', language_code, category.description)
    about = {
        '@type': 'Thing',
        'name': category_name,
        'url': page_url,
    }
    if category_description:
        about['description'] = category_description
    item_list_schema = build_blog_item_list_schema(
        page_obj.object_list,
        request,
        language_code=language_code,
        title=meta_title,
        description=meta_description,
        page_url=page_url,
        about=about,
    )
    if item_list_schema:
        context['schema_blog_list_json'] = json.dumps(item_list_schema, ensure_ascii=False)

    breadcrumb_schema = build_breadcrumb_schema([
        (_('Главная'), reverse('core:home')),
        (_('Блог'), reverse('blog:list')),
        (category_name, category.get_absolute_url()),
    ], request)
    if breadcrumb_schema:
        context['schema_blog_breadcrumb_json'] = json.dumps(breadcrumb_schema, ensure_ascii=False)
    
    return render(request, 'blog/blog_category.html', context)


def blog_tag(request, slug):
    """Статьи с определенным тегом"""
    tag = get_object_or_404(BlogTag, slug=slug)
    posts = BlogPost.get_published().filter(tags=tag).prefetch_related('tags')
    
    # Пагинация
    paginator = Paginator(posts, getattr(settings, 'PAGINATE_BY', 12))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()
    
    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title, meta_description, meta_keywords = _build_blog_tag_meta(tag, language_code, page_obj)

    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'tag': tag,
        'current_category': None,
        'current_tag': tag,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'page_keywords': meta_keywords,
    }
    context['blog_intro'] = _build_blog_intro(
        language_code=language_code,
        current_tag=tag,
        posts_count=paginator.count,
    )

    page_url = request.build_absolute_uri()
    about = {
        '@type': 'Thing',
        'name': tag.name,
        'url': page_url,
    }
    item_list_schema = build_blog_item_list_schema(
        page_obj.object_list,
        request,
        language_code=language_code,
        title=meta_title,
        description=meta_description,
        page_url=page_url,
        about=about,
    )
    if item_list_schema:
        context['schema_blog_list_json'] = json.dumps(item_list_schema, ensure_ascii=False)

    breadcrumb_schema = build_breadcrumb_schema([
        (_('Главная'), reverse('core:home')),
        (_('Блог'), reverse('blog:list')),
        (tag.name, tag.get_absolute_url()),
    ], request)
    if breadcrumb_schema:
        context['schema_blog_breadcrumb_json'] = json.dumps(breadcrumb_schema, ensure_ascii=False)
    
    return render(request, 'blog/blog_tag.html', context)


def legacy_blog_article_redirect(request, legacy_slug):
    """Преобразуем legacy URL вида /blog/articles/123-slug/ в актуальный /blog/slug/."""
    raw_slug = unquote(legacy_slug or '').strip('/').lower()
    if not raw_slug:
        return HttpResponsePermanentRedirect(reverse('blog:list'))

    # Некоторые legacy-URL содержат несколько сегментов, поэтому берем последний.
    slug_candidate = raw_slug.split('/')[-1]

    if '-' in slug_candidate:
        possible_id, remainder = slug_candidate.split('-', 1)
        if possible_id.isdigit() and remainder:
            slug_candidate = remainder

    target_url = reverse('blog:detail', kwargs={'slug': slug_candidate})
    query_string = request.META.get('QUERY_STRING')
    if query_string:
        target_url = f"{target_url}?{query_string}"

    return HttpResponsePermanentRedirect(target_url)


@csrf_exempt
@require_POST
def tinymce_upload(request):
    """
    Загрузка изображений для TinyMCE редактора
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    
    # Проверяем тип файла
    file_extension = os.path.splitext(file.name)[1].lower()
    
    if file_extension not in TINYMCE_ALLOWED_IMAGE_EXTENSIONS:
        return JsonResponse({
            'error': 'Invalid file type. Allowed: JPG, PNG, GIF, WebP, SVG'
        }, status=400)
    
    # Проверяем размер файла (максимум 5MB)
    if file.size > TINYMCE_MAX_UPLOAD_SIZE:
        return JsonResponse({
            'error': 'File too large. Maximum size: 5MB'
        }, status=400)
    
    try:
        # Создаем безопасное имя файла
        name, ext = os.path.splitext(file.name)
        safe_name = f'{slugify(name) or "image"}{ext.lower()}'
        
        # Путь для сохранения
        upload_path = f'blog/editor/{safe_name}'

        if file_extension == '.svg':
            file_content = _sanitize_svg_upload(file)
        else:
            file_content = file.read()
        
        # Сохраняем файл
        file_path = default_storage.save(upload_path, ContentFile(file_content))
        
        # Возвращаем URL для TinyMCE
        file_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)
        
        return JsonResponse({
            'location': file_url
        })

    except ValueError as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'error': f'Upload failed: {str(e)}'
        }, status=500)
