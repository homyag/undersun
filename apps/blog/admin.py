from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.http import HttpResponseRedirect
from django import forms
from tinymce.widgets import TinyMCE
# from modeltranslation.admin import TranslationAdmin, TranslationTabularInline
from .models import BlogCategory, BlogPost, BlogTag
from .services import translate_blog_post, translate_blog_category


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color_preview', 'is_active', 'order', 'posts_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')
    
    def color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; border-radius: 3px;"></div>',
            obj.color
        )
    color_preview.short_description = _('Цвет')
    
    def posts_count(self, obj):
        return obj.posts.count()
    posts_count.short_description = _('Количество статей')


class BlogTagInline(admin.TabularInline):
    model = BlogTag.posts.through
    extra = 1


class BlogPostAdminForm(forms.ModelForm):
    """Форма для BlogPost с кастомными виджетами"""
    
    class Meta:
        model = BlogPost
        fields = '__all__'
        widgets = {
            # Только поля content используют TinyMCE
            'content': TinyMCE(attrs={'class': 'tinymce-content'}),
            'content_en': TinyMCE(attrs={'class': 'tinymce-content'}),
            'content_th': TinyMCE(attrs={'class': 'tinymce-content'}),
        }


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    form = BlogPostAdminForm
    list_display = ('title', 'category', 'author', 'status', 'is_featured', 'published_at', 'views_count')
    list_filter = ('status', 'is_featured', 'category', 'created_at', 'published_at')
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Основная информация (Русский)'), {
            'fields': ('title', 'slug', 'excerpt', 'content', 'category', 'author')
        }),
        (_('Переводы - English'), {
            'fields': ('title_en', 'excerpt_en', 'content_en'),
            'classes': ('collapse',)
        }),
        (_('Переводы - ไทย'), {
            'fields': ('title_th', 'excerpt_th', 'content_th'),
            'classes': ('collapse',)
        }),
        (_('Изображения'), {
            'fields': ('featured_image', 'featured_image_alt', 'featured_image_alt_en', 'featured_image_alt_th'),
            'classes': ('collapse',)
        }),
        (_('SEO - Русский'), {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        (_('SEO - English'), {
            'fields': ('meta_title_en', 'meta_description_en', 'meta_keywords_en'),
            'classes': ('collapse',)
        }),
        (_('SEO - ไทย'), {
            'fields': ('meta_title_th', 'meta_description_th', 'meta_keywords_th'),
            'classes': ('collapse',)
        }),
        (_('Настройки публикации'), {
            'fields': ('status', 'is_featured', 'allow_comments', 'published_at')
        }),
    )
    
    readonly_fields = ('views_count',)
    
    def save_model(self, request, obj, form, change):
        if not change:  # Если это новый объект
            obj.author = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('category', 'author')
    
    actions = ['make_published', 'make_draft', 'make_featured', 'auto_translate']
    
    def make_published(self, request, queryset):
        updated = queryset.update(status='published')
        self.message_user(request, f'{updated} статей опубликовано.')
    make_published.short_description = _('Опубликовать выбранные статьи')
    
    def make_draft(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} статей перенесено в черновики.')
    make_draft.short_description = _('Перенести в черновики')
    
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} статей отмечено как рекомендуемые.')
    make_featured.short_description = _('Отметить как рекомендуемые')
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранные статьи на английский и тайский"""
        translated_count = 0
        for post in queryset:
            try:
                translate_blog_post(post)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода статьи "{post.title}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            self.message_user(request, f'Успешно переведено {translated_count} статей на английский и тайский языки.')
        else:
            self.message_user(request, 'Не удалось перевести ни одной статьи. Убедитесь, что установлен пакет googletrans.', level=messages.WARNING)
    
    auto_translate.short_description = _('🌐 Автоматически перевести на EN и TH')
    
    def get_urls(self):
        """Добавляем кастомные URL для отдельных объектов"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/translate/', self.admin_site.admin_view(self.translate_single_post), name='blog_blogpost_translate'),
        ]
        return custom_urls + urls
    
    def translate_single_post(self, request, object_id):
        """Переводит отдельную статью"""
        try:
            post = BlogPost.objects.get(pk=object_id)
            translate_blog_post(post)
            messages.success(request, f'Статья "{post.title}" успешно переведена на английский и тайский языки.')
        except BlogPost.DoesNotExist:
            messages.error(request, 'Статья не найдена.')
        except Exception as e:
            messages.error(request, f'Ошибка перевода: {e}')
        
        return HttpResponseRedirect(f"/admin/blog/blogpost/{object_id}/change/")
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Добавляем кнопку перевода в форму редактирования"""
        extra_context = extra_context or {}
        if object_id:
            extra_context['show_translate_button'] = True
            extra_context['translate_url'] = f"/admin/blog/blogpost/{object_id}/translate/"
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(BlogTag)
class BlogTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'posts_count', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    
    def posts_count(self, obj):
        return obj.posts.count()
    posts_count.short_description = _('Количество статей')
