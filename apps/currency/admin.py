from django.contrib import admin
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
    
    fieldsets = (
        ('Курс обмена', {
            'fields': ('base_currency', 'target_currency', 'rate', 'date', 'source')
        }),
        ('Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CurrencyPreference)
class CurrencyPreferenceAdmin(admin.ModelAdmin):
    list_display = ('language', 'default_currency', 'updated_at')
    list_filter = ('language', 'default_currency')
    readonly_fields = ('created_at', 'updated_at')