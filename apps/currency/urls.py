from django.urls import path
from .views import ChangeCurrencyView

app_name = 'currency'

urlpatterns = [
    path('change/', ChangeCurrencyView.as_view(), name='change'),
]