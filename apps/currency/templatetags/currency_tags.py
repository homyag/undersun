from django import template
from django.utils.safestring import mark_safe
from ..services import CurrencyService

register = template.Library()


@register.simple_tag(takes_context=True)
def price_in_currency(context, property_obj, deal_type='sale', currency_code=None):
    """Отображает цену объекта в указанной валюте"""
    request = context['request']
    
    # Если валюта не указана, берем из контекста
    if not currency_code:
        currency_code = context.get('selected_currency_code', 'THB')
    
    return property_obj.get_formatted_price(currency_code, deal_type)


@register.simple_tag
def format_amount(amount, currency_code):
    """Форматирует сумму в указанной валюте"""
    if not amount:
        return ""
    
    return CurrencyService.format_price(amount, currency_code)


@register.simple_tag
def convert_price(amount, from_currency, to_currency):
    """Конвертирует цену между валютами"""
    if not amount:
        return None
        
    return CurrencyService.convert_price(amount, from_currency, to_currency)


@register.simple_tag(takes_context=True)
def price_number_only(context, property_obj, deal_type='sale', currency_code=None):
    """Возвращает только число цены без символа валюты"""
    request = context['request']
    
    # Если валюта не указана, берем из контекста
    if not currency_code:
        currency_code = context.get('selected_currency_code', 'THB')
    
    price = property_obj.get_price_in_currency(currency_code, deal_type)
    if not price:
        return "По запросу"
    
    # Форматируем число с пробелами вместо запятых
    return f"{price:,.0f}".replace(',', ' ')


@register.inclusion_tag('currency/currency_selector.html', takes_context=True)
def currency_selector(context):
    """Отображает селектор валют"""
    return {
        'available_currencies': context.get('available_currencies', []),
        'selected_currency': context.get('selected_currency'),
        'request': context['request']
    }