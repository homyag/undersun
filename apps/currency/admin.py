from django.contrib import admin, messages
from django.core.management import call_command
from django.core.management.base import CommandError
from .models import Currency, ExchangeRate, CurrencyPreference


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'is_active', 'is_base', 'decimal_places', 'updated_at')
    list_filter = ('is_active', 'is_base')
    search_fields = ('code', 'name', 'name_ru', 'name_en', 'name_th')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'symbol', 'decimal_places', 'is_active', 'is_base')
        }),
        ('Названия', {
            'fields': ('name', 'name_ru', 'name_en', 'name_th')
        }),
        ('Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('base_currency', 'target_currency', 'rate', 'date', 'source', 'updated_at')
    list_filter = ('date', 'source', 'base_currency', 'target_currency')
    search_fields = ('base_currency__code', 'target_currency__code')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'
    actions = ('update_exchange_rates_action',)
    
    fieldsets = (
        ('Курс обмена', {
            'fields': ('base_currency', 'target_currency', 'rate', 'date', 'source')
        }),
        ('Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def update_exchange_rates_action(self, request, queryset):
        """Админ-действие для запуска команды обновления курсов"""
        base_currency_code = (
            Currency.objects.filter(is_base=True).values_list('code', flat=True).first()
            or 'THB'
        )

        try:
            call_command('update_exchange_rates', base_currency=base_currency_code)
        except CommandError as exc:
            self.message_user(
                request,
                f'Не удалось обновить курсы валют: {exc}',
                level=messages.ERROR,
            )
            return

        self.message_user(
            request,
            f'Курсы валют обновлены для базовой валюты {base_currency_code}. '
            'Обновление цен недвижимости выполнено.',
            level=messages.SUCCESS,
        )

    update_exchange_rates_action.short_description = 'Обновить курсы через API'


@admin.register(CurrencyPreference)
class CurrencyPreferenceAdmin(admin.ModelAdmin):
    list_display = ('language', 'default_currency', 'updated_at')
    list_filter = ('language', 'default_currency')
    readonly_fields = ('created_at', 'updated_at')
