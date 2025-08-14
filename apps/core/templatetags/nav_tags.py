from django import template
from django.urls import reverse, NoReverseMatch
from django.utils.html import mark_safe

register = template.Library()

@register.simple_tag(takes_context=True)
def nav_active(context, url_name, css_class="text-accent", **kwargs):
    """
    Template tag для подсветки активного пункта меню
    """
    request = context['request']
    current_path = request.resolver_match.url_name
    
    # Проверяем точное совпадение
    if current_path == url_name:
        return css_class
    
    # Дополнительные проверки для связанных страниц
    if url_name == 'property_sale' and current_path in ['property_detail', 'property_list']:
        # Проверяем параметры для определения типа сделки
        if 'sale' in request.path or request.GET.get('deal_type') == 'sale':
            return css_class
    
    if url_name == 'property_rent' and current_path in ['property_detail', 'property_list']:
        if 'rent' in request.path or request.GET.get('deal_type') == 'rent':
            return css_class
    
    if url_name == 'blog:list' and current_path in ['blog:detail']:
        return css_class
    
    # Проверка для главной страницы
    if url_name == 'core:home' and current_path == 'home':
        return css_class
    
    return ""

@register.simple_tag(takes_context=True)
def is_active_section(context, section):
    """
    Проверяет активный раздел сайта
    """
    request = context['request']
    path = request.path
    
    if section == 'property' and '/property/' in path:
        return True
    elif section == 'blog' and '/blog/' in path:
        return True
    elif section == 'map' and '/map/' in path:
        return True
    elif section == 'about' and ('/about/' in path or '/contact/' in path):
        return True
    elif section == 'services' and '/services/' in path:
        return True
    
    return False