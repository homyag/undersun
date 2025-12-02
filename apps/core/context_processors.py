import json
from django.conf import settings
from django.templatetags.static import static
from django.urls import translate_url, reverse
from urllib.parse import urlsplit, urlunsplit
from apps.properties.models import PropertyType, Property
from apps.locations.models import District, Location
from apps.core.models import SEOPage, Service
import re


HERO_OG_IMAGE_PATHS = [
    'images/home_page/homepage_hero_section/thailand_hero_section_1.webp',
    'images/home_page/homepage_hero_section/thailand_hero_section_2.webp',
    'images/home_page/homepage_hero_section/thailand_hero_section_3.webp',
]

def site_context(request):
    """Глобальный контекст для всех шаблонов"""
    hero_image_urls = []
    for image_path in HERO_OG_IMAGE_PATHS:
        try:
            hero_image_urls.append(request.build_absolute_uri(static(image_path)))
        except Exception:
            hero_image_urls.append(static(image_path))

    default_hero_image = hero_image_urls[0] if hero_image_urls else static('images/og-image.jpg')
    try:
        default_og_image_url = request.build_absolute_uri(default_hero_image)
    except Exception:
        default_og_image_url = default_hero_image

    current_absolute_url = request.build_absolute_uri()
    split_current = urlsplit(current_absolute_url)
    canonical_path = split_current.path or '/'
    canonical_absolute_url = urlunsplit((split_current.scheme, split_current.netloc, canonical_path, '', ''))
    language_code = getattr(request, 'LANGUAGE_CODE', 'ru')
    language_urls = {}
    hreflang_items = []
    for code, _ in settings.LANGUAGES:
        try:
            translated_url = translate_url(current_absolute_url, code)
        except Exception:
            translated_url = current_absolute_url
        split_result = urlsplit(translated_url)
        clean_absolute_url = urlunsplit((split_result.scheme, split_result.netloc, split_result.path, '', ''))
        hreflang_items.append((code, clean_absolute_url))

        relative_url = urlunsplit(('', '', split_result.path, '', ''))
        if not relative_url.startswith('/'):
            relative_url = f'/{relative_url}'
        if not relative_url.strip('/'):
            relative_url = f'/{code}/'
        language_urls[code] = relative_url

    hreflang_x_default = None
    if hreflang_items:
        language_codes_map = dict(hreflang_items)
        # Предпочитаем английскую версию в качестве x-default, если доступна
        hreflang_x_default = language_codes_map.get('en', hreflang_items[0][1])

    # Schema.org для поискового окна
    try:
        search_path = reverse('core:search')
    except Exception:
        search_path = '/search/'

    try:
        site_root_url = request.build_absolute_uri('/')
    except Exception:
        site_root_url = '/'

    try:
        search_url = request.build_absolute_uri(search_path)
    except Exception:
        search_url = search_path

    search_schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "url": site_root_url,
        "inLanguage": language_code,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{search_url}?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }

    search_schema_json = json.dumps(search_schema, ensure_ascii=False)

    return {
        'property_types': PropertyType.ordered_for_navigation(),
        'districts': District.objects.prefetch_related('locations').all(),
        'current_language': language_code,
        'menu_services': Service.get_menu_services(),
        'tailwind_use_cdn': getattr(settings, 'TAILWIND_USE_CDN', False),
        'default_og_image_url': default_og_image_url,
        'hero_og_images': hero_image_urls,
        'hreflang_items': hreflang_items,
        'hreflang_x_default': hreflang_x_default,
        'language_urls': language_urls,
        'canonical_url': canonical_absolute_url,
        'search_schema_json': search_schema_json,
        'recaptcha_site_key': getattr(settings, 'RECAPTCHA_SITE_KEY', ''),
    }

PAGINATED_VIEW_NAMES = {
    'properties:property_list',
    'properties:property_sale',
    'properties:property_rent',
    'properties:property_by_type',
    'core:search',
    'blog:list',
    'blog:category',
    'blog:tag',
    'district_detail',
    'location_detail',
}

PAGE_LABELS = {
    'ru': 'Страница {page}',
    'en': 'Page {page}',
    'th': 'หน้า {page}',
}

def _should_append_pagination_suffix(request, view_name):
    """Определяем, нужно ли добавлять номер страницы и возвращаем кортеж (bool, page_number)."""
    page_param = request.GET.get('page')

    page_number = None
    if page_param:
        try:
            page_number = int(page_param)
        except (TypeError, ValueError):
            page_number = 1
        else:
            if page_number < 1:
                page_number = 1

    if view_name in PAGINATED_VIEW_NAMES:
        return True, page_number or 1

    if page_number is not None:
        return True, page_number

    return False, None

def _append_suffix_if_needed(value, suffix):
    """Добавляет суффикс к строке, если он ещё не присутствует."""
    if not suffix:
        return value

    if not value:
        return suffix.strip(' |')

    normalized_value = value.lower()
    normalized_suffix = suffix.lower().strip()
    if normalized_suffix and normalized_suffix in normalized_value:
        return value

    return f"{value}{suffix}"

def seo_context(request):
    """Контекст для SEO метатегов"""
    # Определяем имя страницы на основе URL
    path = request.path
    language_code = getattr(request, 'LANGUAGE_CODE', 'ru')
    
    # Убираем языковой префикс из пути
    if path.startswith(f'/{language_code}/'):
        path = path[len(f'/{language_code}'):]
    
    # Проверяем, это ли страница конкретного объекта недвижимости
    property_detail_match = re.match(r'^/property/([^/]+)/?$', path)
    if property_detail_match and not path.startswith('/property/type/'):
        property_slug = property_detail_match.group(1)
        try:
            property_obj = Property.objects.get(slug=property_slug, is_active=True)
            seo_data = property_obj.get_seo_data(language_code)
            return {
                'page_title': seo_data['title'],
                'page_description': seo_data['description'],
                'page_keywords': seo_data['keywords'],
            }
        except Property.DoesNotExist:
            pass  # Продолжаем с обычным определением страницы
    
    # Определяем имя страницы для обычных страниц
    page_name = 'home'  # по умолчанию
    type_page_name = None
    type_match = re.match(r'^/property/type/([^/]+)/?$', path)
    if type_match:
        type_slug = type_match.group(1)
        if PropertyType.objects.filter(name=type_slug).exists():
            type_page_name = f'properties_type_{type_slug}'

    if path == '/' or path == '':
        page_name = 'home'
    elif type_page_name:
        page_name = type_page_name
    elif path.startswith('/property/'):
        page_name = 'properties'
    elif path.startswith('/locations/'):
        page_name = 'locations'
    elif path.startswith('/users/'):
        page_name = 'users'
    elif path.startswith('/blog/tag/'):
        page_name = 'blog_tag'
    elif path.startswith('/blog/category/'):
        page_name = 'blog_category'
    elif path.startswith('/blog'):
        page_name = 'blog'
    elif path.startswith('/map'):
        page_name = 'map'
    elif 'about' in path:
        page_name = 'about'
    elif 'contact' in path:
        page_name = 'contact'
    
    # Получаем SEO данные для обычных страниц
    seo_page = None
    try:
        seo_page = SEOPage.objects.get(page_name=page_name, is_active=True)
    except SEOPage.DoesNotExist:
        if type_page_name and page_name == type_page_name:
            try:
                seo_page = SEOPage.objects.get(page_name='properties', is_active=True)
                page_name = 'properties'
            except SEOPage.DoesNotExist:
                seo_page = None

    if seo_page:
        seo_data = {
            'page_title': seo_page.get_title(language_code),
            'page_description': seo_page.get_description(language_code),
            'page_keywords': seo_page.get_keywords(language_code),
        }
    else:
        defaults = {
            'ru': {
                'title': 'Undersun Estate - Недвижимость на Пхукете',
                'description': 'Продажа и аренда недвижимости на Пхукете. Виллы, апартаменты, кондоминиумы от надежного агентства.',
                'keywords': 'недвижимость пхукет, виллы пхукет, апартаменты пхукет, продажа недвижимости'
            },
            'en': {
                'title': 'Undersun Estate - Phuket Real Estate',
                'description': 'Sale and rental of real estate in Phuket. Villas, apartments, condominiums from a reliable agency.',
                'keywords': 'phuket real estate, phuket villas, phuket apartments, property sale'
            },
            'th': {
                'title': 'Undersun Estate - อสังหาริมทรัพย์ในภูเก็ต',
                'description': 'ขายและให้เช่าอสังหาริมทรัพย์ในภูเก็ต วิลล่า อพาร์ตเมนต์ คอนโดมิเนียม',
                'keywords': 'อสังหาริมทรัพย์ภูเก็ต, วิลล่าภูเก็ต, อพาร์ตเมนต์ภูเก็ต'
            }
        }

        lang_defaults = defaults.get(language_code, defaults['ru'])
        seo_data = {
            'page_title': lang_defaults['title'],
            'page_description': lang_defaults['description'],
            'page_keywords': lang_defaults['keywords'],
        }
    
    resolver_match = getattr(request, 'resolver_match', None)
    view_name = resolver_match.view_name if resolver_match else ''
    should_append, page_number = _should_append_pagination_suffix(request, view_name)

    pagination_label = ''
    pagination_suffix = ''

    if should_append and page_number:
        label_template = PAGE_LABELS.get(language_code[:2], PAGE_LABELS['en'])
        pagination_label = label_template.format(page=page_number)
        pagination_suffix = f" | {pagination_label}"

        seo_data['page_title'] = _append_suffix_if_needed(seo_data.get('page_title'), pagination_suffix)
        seo_data['page_description'] = _append_suffix_if_needed(seo_data.get('page_description'), pagination_suffix)

    seo_data['pagination_page_number'] = page_number
    seo_data['pagination_seo_label'] = pagination_label
    seo_data['pagination_seo_suffix'] = pagination_suffix

    return seo_data
