from modeltranslation.translator import register, TranslationOptions
from .models import Service


@register(Service)
class ServiceTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'content', 'meta_title', 'meta_description', 'meta_keywords')
    required_languages = ('ru',)
    fallback_languages = {'en': ('ru',), 'th': ('ru',)}