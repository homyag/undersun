from modeltranslation.translator import register, TranslationOptions
from .models import PromotionalBanner


@register(PromotionalBanner)
class PromotionalBannerTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'discount_text', 'button_text')
    required_languages = ('ru',)
    fallback_languages = {'en': ('ru',), 'th': ('ru',)}