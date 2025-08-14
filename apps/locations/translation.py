from modeltranslation.translator import register, TranslationOptions
from .models import District, Location

@register(District)
class DistrictTranslationOptions(TranslationOptions):
    fields = ('name', 'description')

@register(Location)
class LocationTranslationOptions(TranslationOptions):
    fields = ('name', 'description')
