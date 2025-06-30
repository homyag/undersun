from django.contrib import admin
# from modeltranslation.admin import TranslationAdmin  # Temporarily disabled
from .models import District, Location

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'slug')
    list_filter = ('district',)
    prepopulated_fields = {'slug': ('name',)}