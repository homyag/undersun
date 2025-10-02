from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import (
    PropertyInquiry,
    QuickConsultationRequest,
    ContactFormSubmission,
    OfficeVisitRequest,
    FAQQuestion,
    NewsletterSubscription
)


@admin.register(PropertyInquiry)
class PropertyInquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'inquiry_type', 'property_link', 'created_at', 'is_processed_badge')
    list_filter = ('inquiry_type', 'is_processed', 'created_at', 'property__property_type', 'preferred_contact')
    search_fields = ('name', 'phone', 'email', 'property__title')
    readonly_fields = ('created_at', 'processed_at', 'amo_lead_id')
    date_hierarchy = 'created_at'

    fieldsets = (
        (_('Контактная информация'), {
            'fields': ('name', 'phone', 'email')
        }),
        (_('Информация о запросе'), {
            'fields': ('property', 'inquiry_type', 'message', 'preferred_date', 'consultation_topic', 'preferred_contact')
        }),
        (_('Статус обработки'), {
            'fields': ('is_processed', 'processed_by', 'processed_at')
        }),
        (_('Интеграции'), {
            'fields': ('amo_lead_id',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_processed', 'mark_as_unprocessed']

    def property_link(self, obj):
        return format_html('<a href="/admin/properties/property/{}/change/">{}</a>',
                          obj.property.id, obj.property.title[:50])
    property_link.short_description = _('Объект')

    def is_processed_badge(self, obj):
        if obj.is_processed:
            return format_html('<span style="color: green;">✅ Обработан</span>')
        return format_html('<span style="color: red;">⏳ Ожидает</span>')
    is_processed_badge.short_description = _('Статус')

    def mark_as_processed(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_processed=True, processed_by=request.user, processed_at=timezone.now())
    mark_as_processed.short_description = _("Отметить как обработанные")

    def mark_as_unprocessed(self, request, queryset):
        queryset.update(is_processed=False, processed_by=None, processed_at=None)
    mark_as_unprocessed.short_description = _("Отметить как необработанные")


@admin.register(QuickConsultationRequest)
class QuickConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ('phone', 'source_page', 'created_at', 'is_processed_badge')
    list_filter = ('is_processed', 'created_at')
    search_fields = ('phone', 'source_page', 'ip_address')
    readonly_fields = ('created_at', 'source_page', 'user_agent', 'ip_address', 'amo_lead_id')
    date_hierarchy = 'created_at'

    actions = ['mark_as_processed']

    def is_processed_badge(self, obj):
        if obj.is_processed:
            return format_html('<span style="color: green;">✅ Обработан</span>')
        return format_html('<span style="color: red;">⏳ Ожидает</span>')
    is_processed_badge.short_description = _('Статус')

    def mark_as_processed(self, request, queryset):
        queryset.update(is_processed=True, processed_by=request.user)
    mark_as_processed.short_description = _("Отметить как обработанные")


@admin.register(ContactFormSubmission)
class ContactFormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'subject', 'created_at', 'is_processed_badge')
    list_filter = ('subject', 'is_processed', 'created_at')
    search_fields = ('name', 'email', 'phone', 'message')
    readonly_fields = ('created_at', 'amo_lead_id')
    date_hierarchy = 'created_at'

    fieldsets = (
        (_('Контактная информация'), {
            'fields': ('name', 'email', 'phone')
        }),
        (_('Сообщение'), {
            'fields': ('subject', 'message')
        }),
        (_('Статус'), {
            'fields': ('is_processed', 'processed_by')
        }),
        (_('Интеграции'), {
            'fields': ('amo_lead_id',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_processed']

    def is_processed_badge(self, obj):
        if obj.is_processed:
            return format_html('<span style="color: green;">✅ Обработан</span>')
        return format_html('<span style="color: red;">⏳ Ожидает</span>')
    is_processed_badge.short_description = _('Статус')

    def mark_as_processed(self, request, queryset):
        queryset.update(is_processed=True, processed_by=request.user)
    mark_as_processed.short_description = _("Отметить как обработанные")


@admin.register(OfficeVisitRequest)
class OfficeVisitRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'preferred_date', 'created_at', 'visit_confirmed', 'is_processed_badge')
    list_filter = ('visit_confirmed', 'is_processed', 'preferred_date', 'created_at')
    search_fields = ('name', 'phone', 'message')
    readonly_fields = ('created_at', 'amo_lead_id')
    date_hierarchy = 'preferred_date'

    fieldsets = (
        (_('Контактная информация'), {
            'fields': ('name', 'phone')
        }),
        (_('Детали встречи'), {
            'fields': ('preferred_date', 'confirmed_datetime', 'message')
        }),
        (_('Статус'), {
            'fields': ('visit_confirmed', 'is_processed', 'processed_by')
        }),
        (_('Интеграции'), {
            'fields': ('amo_lead_id',),
            'classes': ('collapse',)
        }),
    )

    actions = ['confirm_visit', 'mark_as_processed']

    def is_processed_badge(self, obj):
        if obj.is_processed:
            return format_html('<span style="color: green;">✅ Обработан</span>')
        return format_html('<span style="color: red;">⏳ Ожидает</span>')
    is_processed_badge.short_description = _('Статус')

    def confirm_visit(self, request, queryset):
        queryset.update(visit_confirmed=True)
    confirm_visit.short_description = _("Подтвердить встречи")

    def mark_as_processed(self, request, queryset):
        queryset.update(is_processed=True, processed_by=request.user)
    mark_as_processed.short_description = _("Отметить как обработанные")


@admin.register(FAQQuestion)
class FAQQuestionAdmin(admin.ModelAdmin):
    list_display = ('phone', 'question_preview', 'created_at', 'is_processed_badge', 'has_answer')
    list_filter = ('is_processed', 'created_at')
    search_fields = ('phone', 'question', 'answer')
    readonly_fields = ('created_at', 'answered_at', 'amo_lead_id')
    date_hierarchy = 'created_at'

    fieldsets = (
        (_('Вопрос'), {
            'fields': ('phone', 'question')
        }),
        (_('Ответ'), {
            'fields': ('answer', 'answered_at')
        }),
        (_('Статус'), {
            'fields': ('is_processed', 'processed_by')
        }),
        (_('Интеграции'), {
            'fields': ('amo_lead_id',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_processed']

    def question_preview(self, obj):
        return obj.question[:100] + '...' if len(obj.question) > 100 else obj.question
    question_preview.short_description = _('Вопрос')

    def has_answer(self, obj):
        if obj.answer:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: gray;">-</span>')
    has_answer.short_description = _('Отвечен')

    def is_processed_badge(self, obj):
        if obj.is_processed:
            return format_html('<span style="color: green;">✅ Обработан</span>')
        return format_html('<span style="color: red;">⏳ Ожидает</span>')
    is_processed_badge.short_description = _('Статус')

    def mark_as_processed(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_processed=True, processed_by=request.user, answered_at=timezone.now())
    mark_as_processed.short_description = _("Отметить как обработанные")


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active_badge', 'subscribed_at', 'source_page')
    list_filter = ('is_active', 'subscribed_at')
    search_fields = ('email', 'source_page')
    readonly_fields = ('subscribed_at', 'unsubscribed_at')
    date_hierarchy = 'subscribed_at'

    actions = ['activate_subscriptions', 'deactivate_subscriptions']

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✅ Активна</span>')
        return format_html('<span style="color: gray;">❌ Отписан</span>')
    is_active_badge.short_description = _('Статус')

    def activate_subscriptions(self, request, queryset):
        queryset.update(is_active=True, unsubscribed_at=None)
    activate_subscriptions.short_description = _("Активировать подписки")

    def deactivate_subscriptions(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_active=False, unsubscribed_at=timezone.now())
    deactivate_subscriptions.short_description = _("Деактивировать подписки")