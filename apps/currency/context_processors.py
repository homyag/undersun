from .models import Currency
from .services import CurrencyService


def currency_context(request):
    """Контекст-процессор для валют"""
    
    # Получаем выбранную валюту из сессии или по языку
    selected_currency_code = CurrencyService.get_selected_currency_code(request)
    selected_currency = CurrencyService.get_currency_by_code(selected_currency_code)
    
    return {
        'available_currencies': CurrencyService.get_active_currencies(),
        'selected_currency': selected_currency,
        'selected_currency_code': selected_currency_code,
    }

