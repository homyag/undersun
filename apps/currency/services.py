from django.utils import timezone
from .models import Currency, ExchangeRate, CurrencyPreference


class CurrencyService:
    """Сервис для работы с валютами и курсами"""
    
    @staticmethod
    def get_currency_for_language(language_code):
        """Получить валюту по умолчанию для языка"""
        try:
            preference = CurrencyPreference.objects.get(language=language_code)
            return preference.default_currency
        except CurrencyPreference.DoesNotExist:
            # Если предпочтение не найдено, возвращаем базовую валюту
            base_currency = Currency.objects.filter(is_base=True).first()
            return base_currency if base_currency else Currency.objects.filter(code='USD').first()
    
    @staticmethod
    def get_active_currencies():
        """Получить все активные валюты"""
        return Currency.objects.filter(is_active=True).order_by('code')
    
    @staticmethod
    def get_currency_by_code(code):
        """Получить валюту по коду"""
        try:
            return Currency.objects.get(code=code, is_active=True)
        except Currency.DoesNotExist:
            return None
    
    @staticmethod
    def convert_price(amount, from_currency_code, to_currency_code):
        """Конвертировать цену между валютами"""
        if from_currency_code == to_currency_code:
            return amount
            
        from_currency = CurrencyService.get_currency_by_code(from_currency_code)
        to_currency = CurrencyService.get_currency_by_code(to_currency_code)
        
        if not from_currency or not to_currency:
            return None
            
        return ExchangeRate.convert_amount(amount, from_currency, to_currency)
    
    @staticmethod
    def format_price(amount, currency_code):
        """Отформатировать цену в указанной валюте"""
        currency = CurrencyService.get_currency_by_code(currency_code)
        if not currency:
            return f"{amount:,.2f} {currency_code}"
            
        symbol = currency.symbol
        decimal_places = currency.decimal_places
        
        if decimal_places == 0:
            return f"{symbol}{amount:,.0f}"
        else:
            return f"{symbol}{amount:,.{decimal_places}f}"
    
    @staticmethod
    def get_latest_rates_summary():
        """Получить сводку последних курсов"""
        summary = {}
        currencies = Currency.objects.filter(is_active=True)
        base_currency = Currency.objects.filter(is_base=True).first()
        
        if not base_currency:
            return summary
            
        for currency in currencies:
            if currency == base_currency:
                summary[currency.code] = {
                    'rate': 1.0,
                    'currency': currency,
                    'date': timezone.now().date()
                }
            else:
                rate = ExchangeRate.get_latest_rate(base_currency, currency)
                if rate:
                    try:
                        latest_rate = ExchangeRate.objects.filter(
                            base_currency=base_currency,
                            target_currency=currency
                        ).latest('date')
                        summary[currency.code] = {
                            'rate': float(rate),
                            'currency': currency,
                            'date': latest_rate.date
                        }
                    except ExchangeRate.DoesNotExist:
                        pass
                        
        return summary