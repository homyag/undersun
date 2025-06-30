from modeltranslation.translator import register, TranslationOptions
from .models import Property, PropertyType, Developer, PropertyFeature

@register(Property)
class PropertyTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'short_description', 'address')

@register(PropertyType)
class PropertyTypeTranslationOptions(TranslationOptions):
    fields = ('name_display',)

@register(Developer)
class DeveloperTranslationOptions(TranslationOptions):
    fields = ('name', 'description')

@register(PropertyFeature)
class PropertyFeatureTranslationOptions(TranslationOptions):
    fields = ('name',)