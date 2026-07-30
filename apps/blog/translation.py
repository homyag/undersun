from modeltranslation.translator import translator, TranslationOptions
from .models import BlogCategory, BlogPost, BlogPostFAQ, BlogPostPropertyLink


class BlogCategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'meta_title', 'meta_description', 'meta_keywords')


class BlogPostTranslationOptions(TranslationOptions):
    fields = ('title', 'excerpt', 'content', 'meta_title', 'meta_description', 'meta_keywords', 'featured_image_alt')


class BlogPostPropertyLinkTranslationOptions(TranslationOptions):
    fields = ('editor_note',)


class BlogPostFAQTranslationOptions(TranslationOptions):
    fields = ('question', 'answer',)


translator.register(BlogCategory, BlogCategoryTranslationOptions)
translator.register(BlogPost, BlogPostTranslationOptions)
translator.register(BlogPostPropertyLink, BlogPostPropertyLinkTranslationOptions)
translator.register(BlogPostFAQ, BlogPostFAQTranslationOptions)
