from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .services import CurrencyService


class ChangeCurrencyView(View):
    """Представление для смены валюты"""
    
    def post(self, request):
        currency_code = request.POST.get('currency')
        next_url = request.POST.get('next', '/')
        
        # Проверяем, что валюта существует и активна
        currency = CurrencyService.get_currency_by_code(currency_code)
        if currency:
            request.session['currency'] = currency_code
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'currency': currency_code,
                    'symbol': currency.symbol
                })
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid currency code'
                })
        
        return redirect(next_url)