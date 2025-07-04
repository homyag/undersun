from .models import Currency
from .services import CurrencyService


def currency_context(request):
    """Контекст-процессор для валют"""
    
    # Получаем выбранную валюту из сессии или по языку
    selected_currency_code = request.session.get('currency')
    
    if not selected_currency_code:
        # Определяем валюту по языку
        language = getattr(request, 'LANGUAGE_CODE', 'en')
        default_currency = CurrencyService.get_currency_for_language(language)
        selected_currency_code = default_currency.code if default_currency else 'USD'
    
    # Получаем валюту
    selected_currency = CurrencyService.get_currency_by_code(selected_currency_code)
    
    return {
        'available_currencies': CurrencyService.get_active_currencies(),
        'selected_currency': selected_currency,
        'selected_currency_code': selected_currency_code,
    }