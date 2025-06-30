from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, PropertyFavorite, PropertyInquiry


# Расширяем админку пользователя
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


# Перерегистрируем User админку
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(PropertyInquiry)
class PropertyInquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'property', 'created_at', 'is_processed')
    list_filter = ('is_processed', 'created_at', 'property__property_type')
    search_fields = ('name', 'email', 'property__title')
    readonly_fields = ('created_at', 'amo_lead_id')

    actions = ['mark_as_processed']

    def mark_as_processed(self, request, queryset):
        queryset.update(is_processed=True)

    mark_as_processed.short_description = "Отметить как обработанные"