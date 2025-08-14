from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
# from modeltranslation.admin import TranslationAdmin  # Временно отключено
from .models import (
    Property, PropertyImage, PropertyType, Developer,
    PropertyFeature, PropertyFeatureRelation
)
from .services import translate_property, translate_property_type, translate_developer, translate_property_feature


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ('image', 'title', 'is_main', 'order')


class PropertyFeatureInline(admin.TabularInline):
    model = PropertyFeatureRelation
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('legacy_id', 'title', 'property_type', 'district', 'deal_type', 'status', 
                   'price_sale_usd', 'is_active', 'is_featured', 'views_count', 'created_at')
    list_filter = ('is_active', 'property_type', 'district', 'deal_type', 'status', 'is_featured', 'furnished')
    search_fields = ('legacy_id', 'title', 'description', 'address')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PropertyImageInline, PropertyFeatureInline]
    list_editable = ('is_active', 'is_featured', 'status')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    actions = ['make_active', 'make_inactive', 'make_featured', 'make_not_featured', 'auto_translate', 'force_retranslate']
    
    def make_active(self, request, queryset):
        """Сделать недвижимость активной (опубликованной)"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} объектов недвижимости опубликовано.')
    make_active.short_description = "✅ Опубликовать выбранные объекты"
    
    def make_inactive(self, request, queryset):
        """Снять недвижимость с публикации"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} объектов недвижимости снято с публикации.')
    make_inactive.short_description = "❌ Снять с публикации выбранные объекты"
    
    def make_featured(self, request, queryset):
        """Сделать недвижимость рекомендуемой"""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} объектов недвижимости добавлено в рекомендуемые.')
    make_featured.short_description = "⭐ Добавить в рекомендуемые"
    
    def make_not_featured(self, request, queryset):
        """Убрать из рекомендуемых"""
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} объектов недвижимости убрано из рекомендуемых.')
    make_not_featured.short_description = "⚪ Убрать из рекомендуемых"
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранные объекты недвижимости на английский и тайский (только пустые поля)"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        skipped_count = 0
        
        for property_obj in queryset:
            try:
                translate_property(property_obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода объекта "{property_obj.title}": {e}', level=messages.ERROR)
                skipped_count += 1
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, 
                f'Успешно переведено {translated_count} объектов недвижимости через {service_name.upper()}. '
                f'Пропущено: {skipped_count} (уже переведены или ошибки).')
        else:
            self.message_user(request, 'Не удалось перевести ни одного объекта.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH (только пустые поля)"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранные объекты недвижимости, перезаписывая существующие переводы"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for property_obj in queryset:
            try:
                translate_property(property_obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода объекта "{property_obj.title}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, 
                f'Принудительно переведено {translated_count} объектов недвижимости через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного объекта.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново (перезаписать все переводы)"
    
    def get_queryset(self, request):
        """Переопределяем queryset для отображения количества просмотров"""
        return super().get_queryset(request).select_related('property_type', 'district')

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
    actions = ['auto_translate', 'force_retranslate']
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранные типы недвижимости"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_type(obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода типа "{obj.name_display}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Успешно переведено {translated_count} типов недвижимости через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного типа.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранные типы недвижимости"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_type(obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода типа "{obj.name_display}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Принудительно переведено {translated_count} типов недвижимости через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного типа.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново"


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = ('name', 'website')
    prepopulated_fields = {'slug': ('name',)}
    actions = ['auto_translate', 'force_retranslate']
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранных застройщиков"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_developer(obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода застройщика "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Успешно переведено {translated_count} застройщиков через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного застройщика.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранных застройщиков"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_developer(obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода застройщика "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Принудительно переведено {translated_count} застройщиков через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного застройщика.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново"


@admin.register(PropertyFeature)
class PropertyFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    actions = ['auto_translate', 'force_retranslate']
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранные характеристики"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_feature(obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода характеристики "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Успешно переведено {translated_count} характеристик через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одной характеристики.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранные характеристики"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте GOOGLE_TRANSLATE_API_KEY или DEEPL_API_KEY в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_feature(obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода характеристики "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Принудительно переведено {translated_count} характеристик через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одной характеристики.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново"