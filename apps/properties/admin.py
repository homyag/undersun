from django.contrib import admin
# from modeltranslation.admin import TranslationAdmin  # Временно отключено
from .models import (
    Property, PropertyImage, PropertyType, Developer,
    PropertyFeature, PropertyFeatureRelation
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ('image', 'title', 'is_main', 'order')


class PropertyFeatureInline(admin.TabularInline):
    model = PropertyFeatureRelation
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('legacy_id',
    'title', 'property_type', 'location', 'deal_type', 'status', 'price_sale_usd', 'is_featured', 'created_at')
    list_filter = ('property_type', 'location', 'deal_type', 'status', 'is_featured', 'furnished')
    search_fields = ('legacy_id', 'title', 'description', 'address')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PropertyImageInline, PropertyFeatureInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'property_type', 'deal_type', 'status', 'is_featured', 'is_active')
        }),
        ('Описание', {
            'fields': ('description', 'short_description')
        }),
        ('Локация', {
            'fields': ('location', 'address', 'latitude', 'longitude')
        }),
        ('Характеристики', {
            'fields': ('bedrooms', 'bathrooms', 'area_total', 'area_living', 'area_land', 'floor', 'floors_total')
        }),
        ('Цены', {
            'fields': ('price_sale_usd', 'price_sale_thb', 'price_rent_monthly')
        }),
        ('Дополнительно', {
            'fields': ('developer', 'year_built', 'furnished', 'pool', 'parking', 'security', 'gym')
        }),
        ('SEO настройки (опционально)', {
            'fields': (
                ('custom_title_ru', 'custom_title_en', 'custom_title_th'),
                ('custom_description_ru', 'custom_description_en', 'custom_description_th'),
                ('custom_keywords_ru', 'custom_keywords_en', 'custom_keywords_th'),
            ),
            'classes': ('collapse',),
            'description': 'Оставьте поля пустыми для автоматической генерации SEO данных на основе шаблонов'
        }),
    )


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_display', 'icon')


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = ('name', 'website')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(PropertyFeature)
class PropertyFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')