from django.contrib import admin
from django.db.models import Q
from django.http import JsonResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.http import HttpResponseRedirect
from django import forms
from django.forms.utils import flatatt
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from tinymce.widgets import TinyMCE
# from modeltranslation.admin import TranslationAdmin, TranslationTabularInline
from .models import BlogCategory, BlogPost, BlogPostPropertyLink, BlogTag
from .services import translate_blog_post, translate_blog_category


BLOG_TINYMCE_LINK_ATTRS = {
    'link_target_list': [
        {'title': _('В текущем окне'), 'value': ''},
        {'title': _('В новой вкладке'), 'value': '_blank'},
    ],
    'link_rel_list': [
        {'title': _('Без rel'), 'value': ''},
        {'title': 'nofollow', 'value': 'nofollow'},
        {'title': 'noreferrer', 'value': 'noreferrer'},
        {'title': 'noopener noreferrer', 'value': 'noopener noreferrer'},
        {'title': 'nofollow noopener noreferrer', 'value': 'nofollow noopener noreferrer'},
        {'title': 'sponsored nofollow', 'value': 'sponsored nofollow'},
        {'title': 'ugc nofollow', 'value': 'ugc nofollow'},
    ],
}


def blog_content_tinymce_widget():
    return TinyMCE(
        attrs={'class': 'tinymce-content'},
        mce_attrs=BLOG_TINYMCE_LINK_ATTRS.copy(),
    )


class BaseAdminWithRequiredFields(admin.ModelAdmin):
    """Базовый класс админ-панели с подключением стилей для обязательных полей"""
    
    class Media:
        css = {
            'all': ('admin/css/required_fields.css',)
        }
        js = ('admin/js/required_fields.js',)
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Добавляем CSS класс 'required' для обязательных полей"""
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        
        # Проверяем, является ли поле обязательным
        if formfield and not db_field.blank and not db_field.null:
            if hasattr(formfield.widget, 'attrs'):
                formfield.widget.attrs['class'] = formfield.widget.attrs.get('class', '') + ' required-field'
        
        return formfield


@admin.register(BlogCategory)
class BlogCategoryAdmin(BaseAdminWithRequiredFields):
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


class BlogPropertyPickerWidget(forms.Widget):
    """Visible admin widget that stores the selected property id in a hidden input."""

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        final_attrs = self.build_attrs(self.attrs, attrs)
        existing_class = final_attrs.get('class', '')
        final_attrs['class'] = f'{existing_class} blog-property-picker__input'.strip()
        input_html = format_html(
            '<input type="hidden" name="{}" value="{}"{}>',
            name,
            value or '',
            mark_safe(flatatt(final_attrs)),
        )

        return format_html(
            '''
            <div class="blog-property-picker" data-search-url="{}">
                {}
                <div class="blog-property-picker__preview" data-property-picker-preview>
                    <div class="blog-property-picker__empty">
                        <strong>{}</strong>
                        <span>{}</span>
                    </div>
                </div>
                <div class="blog-property-picker__actions">
                    <button type="button" class="button blog-property-picker__open" data-property-picker-open>
                        {}
                    </button>
                    <button type="button" class="button blog-property-picker__clear" data-property-picker-clear hidden>
                        {}
                    </button>
                </div>
            </div>
            ''',
            reverse('admin:blog_blogpost_property_picker_search'),
            input_html,
            _('Объект не выбран'),
            _('Нажмите “Выбрать объект”, чтобы найти карточку по названию, ID, району или комплексу.'),
            _('Выбрать объект'),
            _('Очистить'),
        )


class BlogPostPropertyLinkInline(admin.TabularInline):
    model = BlogPostPropertyLink
    extra = 1
    fields = ('property', 'order', 'editor_note', 'editor_note_en', 'editor_note_th')
    ordering = ('order', 'id')
    verbose_name = _('Ссылка на объект')
    verbose_name_plural = _('Ссылки на объекты недвижимости')

    class Media:
        css = {
            'all': ('admin/css/blog_property_picker.css',)
        }
        js = ('admin/js/blog_property_picker.js',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'property':
            kwargs['widget'] = BlogPropertyPickerWidget()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class BlogPostAdminForm(forms.ModelForm):
    """Форма для BlogPost с кастомными виджетами"""
    
    class Meta:
        model = BlogPost
        fields = '__all__'
        widgets = {
            # Только поля content используют TinyMCE
            'content': blog_content_tinymce_widget(),
            'content_en': blog_content_tinymce_widget(),
            'content_th': blog_content_tinymce_widget(),
        }


@admin.register(BlogPost)
class BlogPostAdmin(BaseAdminWithRequiredFields):
    form = BlogPostAdminForm
    list_display = ('title', 'slug', 'category', 'team_author', 'author', 'status', 'is_featured', 'published_at', 'views_count')
    list_filter = ('status', 'is_featured', 'category', 'created_at', 'published_at')
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ('-created_at',)
    inlines = [BlogPostPropertyLinkInline]
    
    fieldsets = (
        (_('Основная информация (Русский)'), {
            'fields': ('title', 'slug', 'excerpt', 'content', 'category', 'team_author', 'author')
        }),
        (_('Дополнительные поля для событий'), {
            'fields': ('event_date', 'event_location', 'event_price'),
            'classes': ('collapse',),
            'description': _('Заполняется только для мероприятий')
        }),
        (_('Дополнительные поля для кейсов и обзоров'), {
            'fields': ('project_url', 'rating'),
            'classes': ('collapse',),
            'description': _('Заполняется для кейсов (ссылка) и обзоров (рейтинг 1-5)')
        }),
        (_('Поля миграции'), {
            'fields': ('original_url', 'original_id'),
            'classes': ('collapse',),
            'description': _('Автоматически заполняется при импорте')
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
            # Устанавливаем Татьяну как автора по умолчанию, если team_author не указан
            if not obj.team_author_id:
                try:
                    from apps.core.models import Team
                    tatiana = Team.objects.get(id=5)  # Tatiana Korostyleva
                    obj.team_author = tatiana
                except Team.DoesNotExist:
                    pass  # Если Татьяна не найдена, оставляем пустым
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('category', 'author', 'team_author').prefetch_related('property_links')
    
    actions = ['make_published', 'make_draft', 'make_featured', 'auto_translate', 'force_retranslate']
    
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
        """Автоматически переводит выбранные статьи на английский и тайский (только пустые поля)"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        skipped_count = 0
        
        for post in queryset:
            try:
                translate_blog_post(post, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода статьи "{post.title}": {e}', level=messages.ERROR)
                skipped_count += 1
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, 
                f'Успешно переведено {translated_count} статей через {service_name.upper()}. '
                f'Пропущено: {skipped_count} (уже переведены или ошибки).')
        else:
            self.message_user(request, 'Не удалось перевести ни одной статьи.', level=messages.WARNING)
    
    auto_translate.short_description = _('🌐 Перевести на EN и TH (только пустые поля)')
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранные статьи, перезаписывая существующие переводы"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for post in queryset:
            try:
                translate_blog_post(post, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода статьи "{post.title}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, 
                f'Принудительно переведено {translated_count} статей через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одной статьи.', level=messages.WARNING)
    
    force_retranslate.short_description = _('🔄 Перевести заново (перезаписать все переводы)')
    
    def get_urls(self):
        """Добавляем кастомные URL для отдельных объектов"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'property-picker/search/',
                self.admin_site.admin_view(self.property_picker_search),
                name='blog_blogpost_property_picker_search',
            ),
            path('<int:object_id>/translate/', self.admin_site.admin_view(self.translate_single_post), name='blog_blogpost_translate'),
        ]
        return custom_urls + urls

    def property_picker_search(self, request):
        """JSON endpoint for the blog post property picker."""
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            return JsonResponse({'results': []}, status=403)

        from apps.properties.models import Property

        queryset = (
            Property.objects
            .select_related('property_type', 'district', 'location')
            .prefetch_related('images')
        )

        raw_ids = request.GET.get('ids', '').strip()
        if raw_ids:
            requested_ids = [value for value in raw_ids.split(',') if value.isdigit()]
            properties_by_id = {
                str(property_obj.pk): property_obj
                for property_obj in queryset.filter(pk__in=requested_ids)
            }
            results = [
                self._serialize_property_for_picker(properties_by_id[property_id], request)
                for property_id in requested_ids
                if property_id in properties_by_id
            ]
            return JsonResponse({'results': results, 'has_next': False})

        query = request.GET.get('q', '').strip()
        property_type = request.GET.get('property_type', '').strip()
        deal_type = request.GET.get('deal_type', '').strip()
        include_inactive = request.GET.get('include_inactive') == '1'

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        if property_type:
            queryset = queryset.filter(property_type__name=property_type)

        if deal_type == 'sale':
            queryset = queryset.filter(deal_type__in=['sale', 'both'])
        elif deal_type == 'rent':
            queryset = queryset.filter(deal_type__in=['rent', 'both'])

        if query:
            search_filter = (
                Q(title__icontains=query) |
                Q(title_en__icontains=query) |
                Q(title_th__icontains=query) |
                Q(slug__icontains=query) |
                Q(legacy_id__icontains=query) |
                Q(complex_name__icontains=query) |
                Q(address__icontains=query) |
                Q(district__name__icontains=query) |
                Q(location__name__icontains=query)
            )
            if query.isdigit():
                search_filter |= Q(pk=int(query))
            queryset = queryset.filter(search_filter)

        try:
            page = max(1, int(request.GET.get('page', '1')))
        except ValueError:
            page = 1

        page_size = 12
        offset = (page - 1) * page_size
        properties = list(queryset.order_by('-is_featured', '-created_at')[offset:offset + page_size + 1])
        has_next = len(properties) > page_size
        properties = properties[:page_size]

        return JsonResponse({
            'results': [
                self._serialize_property_for_picker(property_obj, request)
                for property_obj in properties
            ],
            'has_next': has_next,
        })

    def _serialize_property_for_picker(self, property_obj, request):
        """Return compact JSON used by the admin picker card UI."""
        main_image = property_obj.main_image
        image_url = main_image.thumbnail_url if main_image else ''
        deal_type = 'sale' if property_obj.deal_type in {'sale', 'both'} else 'rent'

        try:
            price = property_obj.get_formatted_price('THB', deal_type)
        except Exception:
            price = property_obj.price_display

        return {
            'id': property_obj.pk,
            'legacy_id': property_obj.legacy_id or '',
            'title': property_obj.title or '',
            'title_en': getattr(property_obj, 'title_en', '') or '',
            'title_th': getattr(property_obj, 'title_th', '') or '',
            'url': property_obj.get_absolute_url(),
            'image_url': image_url,
            'property_type': property_obj.property_type.name_display if property_obj.property_type else '',
            'property_type_slug': property_obj.property_type.name if property_obj.property_type else '',
            'deal_type': property_obj.get_deal_type_display(),
            'status': property_obj.get_status_display(),
            'is_active': property_obj.is_active,
            'location': property_obj.get_display_location_label(),
            'complex_name': property_obj.complex_name or '',
            'bedrooms': property_obj.bedrooms,
            'area_total': str(property_obj.area_total or ''),
            'price': price,
            'translations': {
                'ru': bool(property_obj.title),
                'en': bool(getattr(property_obj, 'title_en', '')),
                'th': bool(getattr(property_obj, 'title_th', '')),
            },
        }
    
    def translate_single_post(self, request, object_id):
        """Переводит отдельную статью"""
        from apps.core.services import translation_service
        
        try:
            post = BlogPost.objects.get(pk=object_id)
            
            if not translation_service.is_configured():
                messages.error(request, 
                    'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.')
                return HttpResponseRedirect(f"/admin/blog/blogpost/{object_id}/change/")
            
            # Проверяем параметр force из GET-запроса
            force_retranslate = request.GET.get('force', 'false').lower() == 'true'
            
            translate_blog_post(post, force_retranslate=force_retranslate)
            
            service_name = translation_service.get_available_service()
            action_text = "принудительно переведена заново" if force_retranslate else "переведена"
            messages.success(request, 
                f'Статья "{post.title}" успешно {action_text} через {service_name.upper()}.')
                
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
class BlogTagAdmin(BaseAdminWithRequiredFields):
    list_display = ('name', 'slug', 'posts_count', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    
    def posts_count(self, obj):
        return obj.posts.count()
    posts_count.short_description = _('Количество статей')
