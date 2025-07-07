from modeltranslation.translator import register, TranslationOptions
from .models import PromotionalBanner, Service


@register(PromotionalBanner)
class PromotionalBannerTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'discount_text', 'button_text')
    required_languages = ('ru',)
    fallback_languages = {'en': ('ru',), 'th': ('ru',)}


@register(Service)
class ServiceTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'content', 'meta_title', 'meta_description', 'meta_keywords')
    required_languages = ('ru',)
    fallback_languages = {'en': ('ru',), 'th': ('ru',)}