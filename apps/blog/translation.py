from modeltranslation.translator import translator, TranslationOptions
from .models import BlogCategory, BlogPost


class BlogCategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'meta_title', 'meta_description', 'meta_keywords')


class BlogPostTranslationOptions(TranslationOptions):
    fields = ('title', 'excerpt', 'content', 'meta_title', 'meta_description', 'meta_keywords', 'featured_image_alt')


translator.register(BlogCategory, BlogCategoryTranslationOptions)
translator.register(BlogPost, BlogPostTranslationOptions)