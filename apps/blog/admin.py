import subprocess
import sys

from django.contrib import admin
from django.conf import settings
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.utils import timezone
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
from .models import BlogCategory, BlogPost, BlogPostPropertyLink, BlogTag, BlogTranslationJob
from .services import queue_blog_translation_job, translate_blog_category


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


class BlogTranslationJobInline(admin.TabularInline):
    model = BlogTranslationJob
    extra = 0
    can_delete = False
    fields = (
        'status_badge',
        'progress_display',
        'target_languages',
        'force_retranslate',
        'current_field_display',
        'error_message_display',
        'created_at',
        'finished_at',
    )
    readonly_fields = fields
    ordering = ('-created_at',)
    verbose_name = _('Задание перевода')
    verbose_name_plural = _('Задания перевода')
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requested_by')

    def status_badge(self, obj):
        return format_translation_job_status(obj)

    status_badge.short_description = _('Статус')

    def progress_display(self, obj):
        return format_translation_job_progress(obj)

    progress_display.short_description = _('Прогресс')

    def current_field_display(self, obj):
        return format_html(
            '<span data-blog-translation-job-current-field="{}">{}</span>',
            obj.pk,
            obj.current_field or '—',
        )

    current_field_display.short_description = _('Текущее поле')

    def error_message_display(self, obj):
        return format_html(
            '<span data-blog-translation-job-error="{}">{}</span>',
            obj.pk,
            obj.error_message or '',
        )

    error_message_display.short_description = _('Ошибка')


def format_translation_job_status(job):
    colors = {
        BlogTranslationJob.STATUS_PENDING: '#6b7280',
        BlogTranslationJob.STATUS_RUNNING: '#2563eb',
        BlogTranslationJob.STATUS_SUCCEEDED: '#15803d',
        BlogTranslationJob.STATUS_FAILED: '#b91c1c',
        BlogTranslationJob.STATUS_CANCELLED: '#92400e',
    }
    return format_html(
        '<span data-blog-translation-job-status="{}" '
        'style="display:inline-flex;align-items:center;gap:6px;'
        'padding:2px 8px;border-radius:999px;background:{};color:#fff;'
        'font-weight:600;white-space:nowrap;">{}</span>',
        job.pk,
        colors.get(job.status, '#6b7280'),
        job.get_status_display(),
    )


def format_translation_job_progress(job):
    return format_html(
        '<span data-blog-translation-job-progress="{}">{}% ({}/{}, ошибок: {})</span>',
        job.pk,
        job.progress_percent,
        job.completed_fields,
        job.total_fields,
        job.failed_fields,
    )


def start_blog_translation_worker(limit=20):
    try:
        requested_limit = int(limit)
    except (TypeError, ValueError):
        requested_limit = 20

    limit = min(max(requested_limit, 1), 100)
    log_path = settings.BASE_DIR / 'logs' / 'blog_translation_worker.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_file = open(log_path, 'a', encoding='utf-8')
    try:
        subprocess.Popen(
            [
                sys.executable,
                str(settings.BASE_DIR / 'manage.py'),
                'process_blog_translation_jobs',
                '--limit',
                str(limit),
            ],
            cwd=settings.BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )
    finally:
        log_file.close()

    return limit, log_path


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
    change_form_template = 'admin/blog/blogpost/change_form.html'
    list_display = (
        'title',
        'translation_queue_status',
        'slug',
        'category',
        'team_author',
        'author',
        'status',
        'is_featured',
        'published_at',
        'views_count',
    )
    list_filter = ('status', 'is_featured', 'category', 'created_at', 'published_at')
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ('-created_at',)
    inlines = [BlogPostPropertyLinkInline, BlogTranslationJobInline]
    
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

    class Media:
        js = ('admin/js/blog_translation_jobs.js',)
    
    
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
        return (
            qs.select_related('category', 'author', 'team_author')
            .prefetch_related(
                'property_links',
                Prefetch(
                    'translation_jobs',
                    queryset=BlogTranslationJob.objects.order_by('-created_at'),
                    to_attr='prefetched_translation_jobs',
                ),
            )
        )
    
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
    
    def _get_latest_translation_job(self, obj):
        prefetched = getattr(obj, 'prefetched_translation_jobs', None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        return obj.translation_jobs.order_by('-created_at').first()

    def translation_queue_status(self, obj):
        job = self._get_latest_translation_job(obj)
        if not job:
            return format_html(
                '<span style="color:#6b7280;">{}</span>',
                _('Нет заданий'),
            )

        url = reverse('admin:blog_blogtranslationjob_change', args=[job.pk])
        return format_html(
            '<a href="{}" style="text-decoration:none;">{} {}</a>',
            url,
            format_translation_job_status(job),
            format_translation_job_progress(job),
        )

    translation_queue_status.short_description = _('Перевод')

    def _queue_translation_jobs(self, request, queryset, force_retranslate=False):
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return

        created_count = 0
        no_work_count = 0
        skipped_active_count = 0

        for post in queryset:
            active_job = post.translation_jobs.filter(
                status__in=[
                    BlogTranslationJob.STATUS_PENDING,
                    BlogTranslationJob.STATUS_RUNNING,
                ]
            ).first()

            if active_job:
                skipped_active_count += 1
                continue

            job = queue_blog_translation_job(
                post,
                requested_by=request.user,
                force_retranslate=force_retranslate,
            )

            if job.status == BlogTranslationJob.STATUS_PENDING:
                created_count += 1
            else:
                no_work_count += 1

        if created_count:
            service_name = translation_service.get_available_service()
            worker_limit, log_path = start_blog_translation_worker(limit=max(created_count, 20))
            self.message_user(
                request,
                f'Создано заданий перевода: {created_count} через {service_name.upper()}. '
                f'Обработка запущена автоматически в фоне: до {worker_limit} заданий. '
                f'Лог: {log_path}. '
                f'Пропущено активных: {skipped_active_count}. Без новых полей: {no_work_count}.',
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f'Новые задания не созданы. Активных уже было: {skipped_active_count}. '
                f'Без новых полей: {no_work_count}.',
                level=messages.WARNING,
            )

    def auto_translate(self, request, queryset):
        """Ставит выбранные статьи в очередь перевода без перезаписи заполненных полей."""
        self._queue_translation_jobs(request, queryset, force_retranslate=False)
    
    auto_translate.short_description = _('🌐 Перевести отсутствующие поля EN/TH')
    
    def force_retranslate(self, request, queryset):
        """Ставит выбранные статьи в очередь перевода с перезаписью существующих полей."""
        self._queue_translation_jobs(request, queryset, force_retranslate=True)
    
    force_retranslate.short_description = _('🔄 Перевести заново EN/TH')
    
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
        """Ставит отдельную статью в очередь перевода."""
        from apps.core.services import translation_service
        
        try:
            post = BlogPost.objects.get(pk=object_id)
            
            if not translation_service.is_configured():
                messages.error(request, 
                    'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.')
                return HttpResponseRedirect(f"/admin/blog/blogpost/{object_id}/change/")
            
            # Проверяем параметр force из GET-запроса
            force_retranslate = request.GET.get('force', 'false').lower() == 'true'

            active_job = post.translation_jobs.filter(
                status__in=[
                    BlogTranslationJob.STATUS_PENDING,
                    BlogTranslationJob.STATUS_RUNNING,
                ]
            ).first()

            if active_job:
                job_url = reverse('admin:blog_blogtranslationjob_change', args=[active_job.pk])
                messages.warning(
                    request,
                    format_html(
                        'Для статьи уже есть активное задание перевода: <a href="{}">#{}</a>.',
                        job_url,
                        active_job.pk,
                    ),
                )
                return HttpResponseRedirect(f"/admin/blog/blogpost/{object_id}/change/")

            job = queue_blog_translation_job(
                post,
                requested_by=request.user,
                force_retranslate=force_retranslate,
            )

            service_name = translation_service.get_available_service()
            job_url = reverse('admin:blog_blogtranslationjob_change', args=[job.pk])
            action_text = "перевод заново" if force_retranslate else "перевод"

            if job.status == BlogTranslationJob.STATUS_PENDING:
                worker_limit, log_path = start_blog_translation_worker(limit=20)
                messages.success(
                    request,
                    format_html(
                        'Статья "{}": {} поставлен в очередь через {}. '
                        'Обработка запущена автоматически в фоне: до {} заданий. '
                        'Задание: <a href="{}">#{}</a>. Лог: {}.',
                        post.title,
                        action_text,
                        service_name.upper(),
                        worker_limit,
                        job_url,
                        job.pk,
                        log_path,
                    ),
                )
            else:
                messages.info(
                    request,
                    format_html(
                        'Статья "{}": новых полей для перевода нет. '
                        'Задание: <a href="{}">#{}</a>.',
                        post.title,
                        job_url,
                        job.pk,
                    ),
                )
                
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
            extra_context['force_translate_url'] = f"/admin/blog/blogpost/{object_id}/translate/?force=true"
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(BlogTranslationJob)
class BlogTranslationJobAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'post_link',
        'status_badge',
        'progress_display',
        'force_retranslate',
        'current_field_display',
        'requested_by',
        'created_at',
        'started_at',
        'finished_at',
    )
    list_filter = ('status', 'force_retranslate', 'created_at')
    search_fields = ('post__title', 'post__slug', 'error_message', 'log')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ('retry_jobs', 'reset_running_jobs', 'cancel_pending_jobs')
    readonly_fields = (
        'post',
        'requested_by',
        'status_badge',
        'target_languages',
        'force_retranslate',
        'provider',
        'progress_display',
        'total_fields',
        'completed_fields',
        'skipped_fields',
        'failed_fields',
        'current_language',
        'current_field_display',
        'error_message_display',
        'log',
        'created_at',
        'updated_at',
        'started_at',
        'finished_at',
    )

    class Media:
        js = ('admin/js/blog_translation_jobs.js',)

    fieldsets = (
        (_('Задание'), {
            'fields': (
                'post',
                'requested_by',
                'status_badge',
                'target_languages',
                'force_retranslate',
                'provider',
            ),
        }),
        (_('Прогресс'), {
            'fields': (
                'progress_display',
                'total_fields',
                'completed_fields',
                'skipped_fields',
                'failed_fields',
                'current_language',
                'current_field_display',
            ),
        }),
        (_('Диагностика'), {
            'fields': ('error_message_display', 'log'),
        }),
        (_('Время'), {
            'fields': ('created_at', 'updated_at', 'started_at', 'finished_at'),
        }),
    )

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'run-pending/',
                self.admin_site.admin_view(self.run_pending_jobs),
                name='blog_blogtranslationjob_run_pending',
            ),
            path(
                'status-json/',
                self.admin_site.admin_view(self.status_json),
                name='blog_blogtranslationjob_status_json',
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('post', 'requested_by')

    def run_pending_jobs(self, request):
        pending_count = BlogTranslationJob.objects.filter(
            status=BlogTranslationJob.STATUS_PENDING,
        ).count()

        if pending_count == 0:
            self.message_user(
                request,
                'В очереди нет ожидающих заданий перевода.',
                level=messages.INFO,
            )
            return HttpResponseRedirect(reverse('admin:blog_blogtranslationjob_changelist'))

        limit, log_path = start_blog_translation_worker(limit=request.GET.get('limit', 20))

        self.message_user(
            request,
            f'Запущена обработка очереди в фоне: до {limit} заданий. '
            f'Ожидало заданий: {pending_count}. Лог: {log_path}',
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse('admin:blog_blogtranslationjob_changelist'))

    def status_json(self, request):
        if not self.has_view_permission(request):
            return JsonResponse({'jobs': []}, status=403)

        raw_ids = request.GET.get('ids', '')
        job_ids = [
            int(value)
            for value in raw_ids.split(',')
            if value.strip().isdigit()
        ]

        queryset = BlogTranslationJob.objects.select_related('post')
        if job_ids:
            queryset = queryset.filter(pk__in=job_ids)
        else:
            queryset = queryset.none()

        jobs_by_id = {job.pk: job for job in queryset}
        jobs = [
            self._serialize_job_status(jobs_by_id[job_id])
            for job_id in job_ids
            if job_id in jobs_by_id
        ]
        return JsonResponse({'jobs': jobs})

    def _serialize_job_status(self, job):
        return {
            'id': job.pk,
            'status': job.status,
            'status_label': job.get_status_display(),
            'progress_percent': job.progress_percent,
            'total_fields': job.total_fields,
            'completed_fields': job.completed_fields,
            'skipped_fields': job.skipped_fields,
            'failed_fields': job.failed_fields,
            'current_language': job.current_language,
            'current_field': job.current_field,
            'error_message': job.error_message,
            'started_at': job.started_at.isoformat() if job.started_at else '',
            'finished_at': job.finished_at.isoformat() if job.finished_at else '',
            'is_active': job.is_active,
        }

    def post_link(self, obj):
        url = reverse('admin:blog_blogpost_change', args=[obj.post_id])
        return format_html('<a href="{}">{}</a>', url, obj.post.title)

    post_link.short_description = _('Статья')
    post_link.admin_order_field = 'post__title'

    def status_badge(self, obj):
        return format_translation_job_status(obj)

    status_badge.short_description = _('Статус')
    status_badge.admin_order_field = 'status'

    def progress_display(self, obj):
        return format_translation_job_progress(obj)

    progress_display.short_description = _('Прогресс')

    def current_field_display(self, obj):
        return format_html(
            '<span data-blog-translation-job-current-field="{}">{}</span>',
            obj.pk,
            obj.current_field or '—',
        )

    current_field_display.short_description = _('Текущее поле')
    current_field_display.admin_order_field = 'current_field'

    def error_message_display(self, obj):
        return format_html(
            '<span data-blog-translation-job-error="{}">{}</span>',
            obj.pk,
            obj.error_message or '',
        )

    error_message_display.short_description = _('Ошибка')

    def retry_jobs(self, request, queryset):
        now = timezone.now()
        retryable = queryset.exclude(
            status__in=[
                BlogTranslationJob.STATUS_PENDING,
                BlogTranslationJob.STATUS_RUNNING,
            ]
        )
        updated = retryable.update(
            status=BlogTranslationJob.STATUS_PENDING,
            completed_fields=0,
            failed_fields=0,
            current_language='',
            current_field='',
            error_message='',
            started_at=None,
            finished_at=None,
            updated_at=now,
        )
        self.message_user(
            request,
            f'Повторно поставлено в очередь заданий: {updated}.',
            level=messages.SUCCESS if updated else messages.WARNING,
        )

    retry_jobs.short_description = _('Повторить выбранные завершенные/ошибочные задания')

    def reset_running_jobs(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status=BlogTranslationJob.STATUS_RUNNING).update(
            status=BlogTranslationJob.STATUS_PENDING,
            current_language='',
            current_field='',
            error_message='',
            started_at=None,
            finished_at=None,
            updated_at=now,
        )
        self.message_user(
            request,
            f'Возвращено в очередь зависших заданий: {updated}.',
            level=messages.SUCCESS if updated else messages.WARNING,
        )

    reset_running_jobs.short_description = _('Вернуть выбранные задания "В работе" в очередь')

    def cancel_pending_jobs(self, request, queryset):
        updated = queryset.filter(status=BlogTranslationJob.STATUS_PENDING).update(
            status=BlogTranslationJob.STATUS_CANCELLED,
            finished_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.message_user(
            request,
            f'Отменено ожидающих заданий: {updated}.',
            level=messages.SUCCESS if updated else messages.WARNING,
        )

    cancel_pending_jobs.short_description = _('Отменить ожидающие задания')


@admin.register(BlogTag)
class BlogTagAdmin(BaseAdminWithRequiredFields):
    list_display = ('name', 'slug', 'posts_count', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    
    def posts_count(self, obj):
        return obj.posts.count()
    posts_count.short_description = _('Количество статей')
