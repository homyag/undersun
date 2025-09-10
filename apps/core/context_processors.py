from apps.properties.models import PropertyType, Property
from apps.locations.models import District, Location
from apps.core.models import SEOPage, Service
import re

def site_context(request):
    """Глобальный контекст для всех шаблонов"""
    return {
        'property_types': PropertyType.objects.all(),
        'districts': District.objects.prefetch_related('locations').all(),
        'current_language': request.LANGUAGE_CODE,
        'menu_services': Service.get_menu_services(),
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