from django.contrib import admin
from django.utils.translation import gettext_lazy as _
# from modeltranslation.admin import TranslationAdmin  # Temporarily disabled
from .models import District, Location

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'has_image')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'description')}),
        (_('Изображение'), {'fields': ('image',)}),
    )

    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True
    has_image.short_description = _('Фото')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'slug', 'has_image')
    list_filter = ('district',)
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'district', 'description')}),
        (_('Изображение'), {'fields': ('image',)}),
    )

    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True
    has_image.short_description = _('Фото')
