from django.urls import path
from .views import ChangeCurrencyView, ExchangeRatesView

app_name = 'currency'

urlpatterns = [
    path('change/', ChangeCurrencyView.as_view(), name='change'),
    path('rates/', ExchangeRatesView.as_view(), name='rates'),
]