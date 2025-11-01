from django.conf import settings
from django.templatetags.static import static
from django.urls import translate_url
from apps.properties.models import PropertyType, Property
from apps.locations.models import District, Location
from apps.core.models import SEOPage, Service
import re


HERO_OG_IMAGE_PATHS = [
    'images/home_page/homepage_hero_section/thailand_hero_section_1.jpg',
    'images/home_page/homepage_hero_section/thailand_hero_section_2.jpg',
    'images/home_page/homepage_hero_section/thailand_hero_section_3.jpg',
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
    hreflang_items = []
    for code, _ in settings.LANGUAGES:
        try:
            translated_url = translate_url(current_absolute_url, code)
        except Exception:
            translated_url = current_absolute_url
        hreflang_items.append((code, translated_url))

    hreflang_x_default = None
    if hreflang_items:
        language_codes_map = dict(hreflang_items)
        # Предпочитаем английскую версию в качестве x-default, если доступна
        hreflang_x_default = language_codes_map.get('en', hreflang_items[0][1])

    return {
        'property_types': PropertyType.ordered_for_navigation(),
        'districts': District.objects.prefetch_related('locations').all(),
        'current_language': request.LANGUAGE_CODE,
        'menu_services': Service.get_menu_services(),
        'tailwind_use_cdn': getattr(settings, 'TAILWIND_USE_CDN', False),
        'default_og_image_url': default_og_image_url,
        'hero_og_images': hero_image_urls,
        'hreflang_items': hreflang_items,
        'hreflang_x_default': hreflang_x_default,
    }

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
    if property_detail_match:
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
    if path == '/' or path == '':
        page_name = 'home'
    elif path.startswith('/property/'):
        page_name = 'properties'
    elif path.startswith('/locations/'):
        page_name = 'locations'
    elif path.startswith('/users/'):
        page_name = 'users'
    elif 'about' in path:
        page_name = 'about'
    elif 'contact' in path:
        page_name = 'contact'
    
    # Получаем SEO данные для обычных страниц
    try:
        seo_page = SEOPage.objects.get(page_name=page_name, is_active=True)
        seo_data = {
            'page_title': seo_page.get_title(language_code),
            'page_description': seo_page.get_description(language_code),
            'page_keywords': seo_page.get_keywords(language_code),
        }
    except SEOPage.DoesNotExist:
        # Значения по умолчанию
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
    
    return seo_data
