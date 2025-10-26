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
    def get_selected_currency_code(request):
        """Определить выбранную пользователем валюту с учетом языка"""
        code = request.session.get('currency') if request else None

        if not code:
            language = getattr(request, 'LANGUAGE_CODE', 'en') if request else 'en'
            default_currency = CurrencyService.get_currency_for_language(language)
            code = default_currency.code if default_currency else 'USD'

        return (code or 'USD').upper()

    @staticmethod
    def get_price_field_names(currency_code):
        """Вернуть имена полей цены для выбранной валюты (продажа, аренда)"""
        mapping = {
            'USD': ('price_sale_usd', 'price_rent_monthly'),
            'THB': ('price_sale_thb', 'price_rent_monthly_thb'),
            'RUB': ('price_sale_rub', 'price_rent_monthly_rub'),
        }

        return mapping.get((currency_code or 'USD').upper(), mapping['USD'])
    
    @staticmethod
    def convert_price(amount, from_currency_code, to_currency_code):
        """Конвертировать цену между валютами"""
        if from_currency_code == to_currency_code:
            return amount
            
        from_currency = CurrencyService.get_currency_by_code(from_currency_code)
        to_currency = CurrencyService.get_currency_by_code(to_currency_code)
        
        if not from_currency or not to_currency:
            return None

        direct_conversion = ExchangeRate.convert_amount(amount, from_currency, to_currency)
        if direct_conversion is not None:
            return direct_conversion

        base_currency = Currency.objects.filter(is_base=True).first()
        if not base_currency or base_currency in (from_currency, to_currency):
            return None

        amount_in_base = ExchangeRate.convert_amount(amount, from_currency, base_currency)
        if amount_in_base is None:
            return None

        return ExchangeRate.convert_amount(amount_in_base, base_currency, to_currency)
    
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
