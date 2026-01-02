from django.contrib import admin, messages
from django.db import models
from django.utils.translation import gettext_lazy as _
from tinymce.widgets import TinyMCE
from .models import SEOPage, SEOTemplate, PromotionalBanner, Service, Team, SEOContentBlock
from .services import translation_service
from apps.properties.services import translate_service_entry


@admin.register(SEOPage)
class SEOPageAdmin(admin.ModelAdmin):
    list_display = ('page_name', 'title_ru', 'title_en', 'title_th', 'is_active', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('page_name', 'title_ru', 'title_en', 'title_th', 'description_ru', 'description_en', 'description_th')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('page_name', 'is_active')
        }),
        ('SEO для русского языка', {
            'fields': ('title_ru', 'description_ru', 'keywords_ru'),
            'classes': ('collapse',),
            'description': 'Метатеги для русской версии сайта (/ru/)'
        }),
        ('SEO для английского языка', {
            'fields': ('title_en', 'description_en', 'keywords_en'),
            'classes': ('collapse',),
            'description': 'Метатеги для английской версии сайта (/en/)'
        }),
        ('SEO для тайского языка', {
            'fields': ('title_th', 'description_th', 'keywords_th'),
            'classes': ('collapse',),
            'description': 'Метатеги для тайской версии сайта (/th/)'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('page_name')
    
    def save_model(self, request, obj, form, change):
        """Добавляем информацию о том, кто последний раз изменял"""
        super().save_model(request, obj, form, change)
        
    def get_form(self, request, obj=None, **kwargs):
        """Настройка формы с подсказками"""
        form = super().get_form(request, obj, **kwargs)
        
        # Добавляем help_text для полей
        if 'page_name' in form.base_fields:
            form.base_fields['page_name'].help_text = 'Уникальный идентификатор страницы (home, properties, about, contact, locations, users)'
            
        # Добавляем подсказки для title полей
        for lang in ['ru', 'en', 'th']:
            title_field = f'title_{lang}'
            desc_field = f'description_{lang}'
            keywords_field = f'keywords_{lang}'
            
            if title_field in form.base_fields:
                form.base_fields[title_field].help_text = 'Рекомендуется 50-60 символов'
            if desc_field in form.base_fields:
                form.base_fields[desc_field].help_text = 'Рекомендуется 140-160 символов'
            if keywords_field in form.base_fields:
                form.base_fields[keywords_field].help_text = 'Ключевые слова через запятую (необязательно)'
        
        return form
    
    actions = ['duplicate_seo_page']
    
    def duplicate_seo_page(self, request, queryset):
        """Дублировать SEO страницы"""
        for seo_page in queryset:
            seo_page.pk = None
            seo_page.page_name = f"{seo_page.page_name}_copy"
            seo_page.save()
        self.message_user(request, f"Продублировано {queryset.count()} SEO страниц")
    duplicate_seo_page.short_description = "Дублировать выбранные SEO страницы"
    
    class Media:
        css = {
            'all': ('admin/css/seo_admin.css',)
        }
        js = ('admin/js/seo_admin.js',)


@admin.register(SEOContentBlock)
class SEOContentBlockAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = (
        'slug', 'title', 'content_ru', 'content_en', 'content_th'
    )
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('title',)}
    actions = ['auto_translate_blocks', 'force_retranslate_blocks']

    fieldsets = (
        (_('Основное'), {
            'fields': ('slug', 'title', 'is_active'),
        }),
        (_('Контент (RU)'), {
            'fields': ('content_ru',),
        }),
        (_('Контент (EN)'), {
            'fields': ('content_en',),
            'classes': ('collapse',),
        }),
        (_('Контент (TH)'), {
            'fields': ('content_th',),
            'classes': ('collapse',),
        }),
        (_('Системная информация'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    formfield_overrides = {
        models.TextField: {
            'widget': TinyMCE(attrs={'class': 'tinymce-content seo-content-block'}),
        },
    }

    def _translate_queryset(self, request, queryset, force=False):
        if not translation_service.is_configured():
            self.message_user(
                request,
                _('API перевода не настроен. Укажите YANDEX_TRANSLATE_API_KEY/Folder ID.'),
                level=messages.ERROR,
            )
            return

        target_languages = translation_service.translation_settings.get('target_languages', [])
        success = 0
        skipped = 0
        errors = 0

        for block in queryset:
            source_text = (block.content_ru or '').strip()
            if not source_text:
                skipped += 1
                continue

            updated_fields = []
            for lang in target_languages:
                field_name = f'content_{lang}'
                if not hasattr(block, field_name):
                    continue

                current_value = getattr(block, field_name, '')
                if current_value and not force:
                    continue

                translated = translation_service.translate_text(
                    source_text,
                    lang,
                    preserve_html=True,
                )
                if translated:
                    setattr(block, field_name, translated)
                    updated_fields.append(field_name)
                else:
                    errors += 1

            if updated_fields:
                block.save(update_fields=updated_fields + ['updated_at'])
                success += 1
            else:
                skipped += 1

        provider = translation_service.get_available_service()
        if success:
            self.message_user(
                request,
                _('Переведено %(count)s блоков через %(provider)s. Пропущено: %(skipped)s. Ошибок: %(errors)s.') % {
                    'count': success,
                    'provider': provider.upper() if provider else 'API',
                    'skipped': skipped,
                    'errors': errors,
                },
                level=messages.SUCCESS,
            )
        elif not errors:
            self.message_user(
                request,
                _('Не удалось перевести выбранные блоки: нет текста на русском или поля уже заполнены.'),
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                _('Не удалось перевести выбранные блоки: проверьте настройки API.'),
                level=messages.ERROR,
            )

    def auto_translate_blocks(self, request, queryset):
        """Переводит пустые поля EN/TH на основе текста RU."""
        self._translate_queryset(request, queryset, force=False)

    auto_translate_blocks.short_description = _('🌐 Перевести блоки (не перезаписывать)')

    def force_retranslate_blocks(self, request, queryset):
        """Переводит блоки заново, перезаписывая существующий контент."""
        self._translate_queryset(request, queryset, force=True)

    force_retranslate_blocks.short_description = _('🔄 Перевести блоки заново (перезаписать)')


@admin.register(SEOTemplate)
class SEOTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'property_type', 'deal_type', 'priority', 'is_active', 'updated_at')
    list_filter = ('template_type', 'property_type', 'deal_type', 'is_active', 'created_at')
    search_fields = ('name', 'property_type', 'title_template_ru', 'title_template_en', 'title_template_th')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('priority', 'is_active')
    ordering = ['priority', 'name']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'template_type', 'property_type', 'deal_type', 'priority', 'is_active'),
            'description': 'Базовые настройки шаблона. Приоритет: чем меньше число, тем выше приоритет.'
        }),
        ('Шаблоны для русского языка', {
            'fields': ('title_template_ru', 'description_template_ru', 'keywords_template_ru'),
            'classes': ('collapse',),
            'description': 'Шаблоны для генерации SEO на русском языке. Переменные: {title}, {type}, {location}, {district}, {price}, {area}, {rooms}, {deal_type}'
        }),
        ('Шаблоны для английского языка', {
            'fields': ('title_template_en', 'description_template_en', 'keywords_template_en'),
            'classes': ('collapse',),
            'description': 'Шаблоны для генерации SEO на английском языке'
        }),
        ('Шаблоны для тайского языка', {
            'fields': ('title_template_th', 'description_template_th', 'keywords_template_th'),
            'classes': ('collapse',),
            'description': 'Шаблоны для генерации SEO на тайском языке'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        """Настройка формы с подсказками"""
        form = super().get_form(request, obj, **kwargs)
        
        # Добавляем help_text для базовых полей
        help_texts = {
            'name': 'Название шаблона для удобства управления',
            'template_type': 'Тип шаблона определяет, где он будет применяться',
            'property_type': 'Оставьте пустым для применения ко всем типам недвижимости',
            'deal_type': 'Оставьте пустым для применения ко всем типам сделок',
            'priority': 'Чем меньше число, тем выше приоритет (1 = самый высокий)',
        }
        
        for field_name, help_text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = help_text
        
        # Добавляем подсказки для шаблонов
        template_help = 'Доступные переменные: {title}, {type}, {location}, {district}, {price}, {area}, {rooms}, {deal_type}'
        for lang in ['ru', 'en', 'th']:
            for field_type in ['title_template', 'description_template', 'keywords_template']:
                field_name = f'{field_type}_{lang}'
                if field_name in form.base_fields:
                    if field_type == 'title_template':
                        form.base_fields[field_name].help_text = f'{template_help}. Рекомендуется 50-60 символов'
                    elif field_type == 'description_template':
                        form.base_fields[field_name].help_text = f'{template_help}. Рекомендуется 140-160 символов'
                    else:
                        form.base_fields[field_name].help_text = f'{template_help}. Ключевые слова через запятую'
        
        return form
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()
    
    actions = ['duplicate_template', 'test_template']
    
    def duplicate_template(self, request, queryset):
        """Дублировать SEO шаблоны"""
        for template in queryset:
            template.pk = None
            template.name = f"{template.name} (копия)"
            template.save()
        self.message_user(request, f"Продублировано {queryset.count()} шаблонов")
    duplicate_template.short_description = "Дублировать выбранные шаблоны"
    
    def test_template(self, request, queryset):
        """Тестировать шаблоны на примере"""
        # Здесь можно добавить логику для тестирования шаблонов
        self.message_user(request, f"Тестирование {queryset.count()} шаблонов")
    test_template.short_description = "Тестировать выбранные шаблоны"
    
    class Media:
        css = {
            'all': ('admin/css/seo_admin.css',)
        }
        js = ('admin/js/seo_admin.js',)


@admin.register(PromotionalBanner)
class PromotionalBannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'language_code', 'link', 'has_desktop', 'has_tablet', 'has_mobile')
    list_filter = ('language_code',)
    readonly_fields = ('image_recommendations',)

    fieldsets = (
        (_('Основное'), {
            'fields': ('name', 'language_code', 'link'),
        }),
        (_('Изображения'), {
            'fields': ('desktop_image', 'tablet_image', 'mobile_image', 'image_recommendations'),
            'description': _('Загрузите отдельные версии баннера для десктопа, планшета и мобильных устройств.')
        }),
    )

    def has_desktop(self, obj):
        return bool(obj.desktop_image)
    has_desktop.boolean = True
    has_desktop.short_description = _('Desktop')

    def has_tablet(self, obj):
        return bool(obj.tablet_image)
    has_tablet.boolean = True
    has_tablet.short_description = _('Tablet')

    def has_mobile(self, obj):
        return bool(obj.mobile_image)
    has_mobile.boolean = True
    has_mobile.short_description = _('Mobile')

    def image_recommendations(self, obj):
        return PromotionalBanner.image_disclaimer()
    image_recommendations.short_description = _('Рекомендации по изображениям')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_active', 'show_in_menu', 'menu_order', 'updated_at')
    list_filter = ('is_active', 'show_in_menu', 'created_at', 'updated_at')
    search_fields = ('title', 'slug', 'description', 'content')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'show_in_menu', 'menu_order')
    ordering = ['menu_order', 'title']
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'description', 'content'),
            'description': 'Основное содержимое страницы услуги'
        }),
        ('SEO настройки', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',),
            'description': 'SEO метатеги для страницы. Если поля пустые, будут использоваться основные данные'
        }),
        ('Визуальное оформление', {
            'fields': ('image', 'icon_class'),
            'classes': ('collapse',),
            'description': 'Изображение для страницы и иконка для меню'
        }),
        ('Настройки отображения', {
            'fields': ('is_active', 'show_in_menu', 'menu_order'),
            'description': 'Настройки видимости и порядка отображения'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        """Настройка формы с подсказками"""
        form = super().get_form(request, obj, **kwargs)
        
        # Добавляем help_text для полей
        help_texts = {
            'title': 'Заголовок страницы услуги (до 200 символов)',
            'slug': 'URL-адрес страницы (автоматически генерируется из заголовка)',
            'description': 'Краткое описание услуги для превью (до 500 символов)',
            'content': 'Подробное описание услуги с HTML разметкой',
            'meta_title': 'SEO заголовок (если пустое, используется основной заголовок)',
            'meta_description': 'SEO описание (если пустое, используется краткое описание)',
            'meta_keywords': 'SEO ключевые слова через запятую',
            'image': 'Основное изображение для страницы услуги',
            'icon_class': 'CSS класс иконки для меню (например: fas fa-home, fas fa-building)',
            'is_active': 'Отображать ли страницу на сайте',
            'show_in_menu': 'Показывать ли услугу в меню навигации',
            'menu_order': 'Порядок отображения в меню (меньше = выше)',
        }
        
        for field_name, help_text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = help_text
        
        return form
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('menu_order', 'title')
    
    actions = ['activate_services', 'deactivate_services', 'add_to_menu', 'remove_from_menu', 'duplicate_services', 'auto_translate_services', 'force_retranslate_services']
    
    def activate_services(self, request, queryset):
        """Активировать выбранные услуги"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Активировано {updated} услуг")
    activate_services.short_description = "Активировать выбранные услуги"
    
    def deactivate_services(self, request, queryset):
        """Деактивировать выбранные услуги"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {updated} услуг")
    deactivate_services.short_description = "Деактивировать выбранные услуги"
    
    def add_to_menu(self, request, queryset):
        """Добавить в меню"""
        updated = queryset.update(show_in_menu=True)
        self.message_user(request, f"Добавлено в меню {updated} услуг")
    add_to_menu.short_description = "Добавить в меню навигации"
    
    def remove_from_menu(self, request, queryset):
        """Убрать из меню"""
        updated = queryset.update(show_in_menu=False)
        self.message_user(request, f"Убрано из меню {updated} услуг")
    remove_from_menu.short_description = "Убрать из меню навигации"
    
    def duplicate_services(self, request, queryset):
        """Дублировать выбранные услуги"""
        for service in queryset:
            service.pk = None
            service.title = f"{service.title} (копия)"
            service.slug = f"{service.slug}-copy"
            service.is_active = False  # Копии создаются неактивными
            service.save()
        self.message_user(request, f"Продублировано {queryset.count()} услуг")
    duplicate_services.short_description = "Дублировать выбранные услуги"

    def auto_translate_services(self, request, queryset):
        """Переводит услуги на EN/TH, не перезаписывая заполненные поля"""
        from apps.core.services import translation_service

        if not translation_service.is_configured():
            self.message_user(
                request,
                'API перевода не настроен. Пожалуйста, укажите YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID.',
                level=messages.ERROR
            )
            return

        translated = 0
        errors = 0

        for service_obj in queryset:
            try:
                translate_service_entry(service_obj, force_retranslate=False)
                translated += 1
            except Exception as exc:
                errors += 1
                self.message_user(
                    request,
                    f'Ошибка перевода услуги "{service_obj.title}": {exc}',
                    level=messages.ERROR
                )

        if translated:
            provider = translation_service.get_available_service()
            self.message_user(
                request,
                f'Переведено {translated} услуг через {provider.upper()}. Пропущено: {errors}.',
                level=messages.SUCCESS
            )
        elif not errors:
            self.message_user(request, 'Не удалось перевести выбранные услуги: данные уже заполнены или отсутствуют.', level=messages.WARNING)

    auto_translate_services.short_description = "🌐 Перевести услуги на EN/TH (только пустые поля)"

    def force_retranslate_services(self, request, queryset):
        """Принудительный перевод услуг с перезаписью существующих значений"""
        from apps.core.services import translation_service

        if not translation_service.is_configured():
            self.message_user(
                request,
                'API перевода не настроен. Пожалуйста, укажите YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID.',
                level=messages.ERROR
            )
            return

        translated = 0

        for service_obj in queryset:
            try:
                translate_service_entry(service_obj, force_retranslate=True)
                translated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f'Ошибка перевода услуги "{service_obj.title}": {exc}',
                    level=messages.ERROR
                )

        if translated:
            provider = translation_service.get_available_service()
            self.message_user(
                request,
                f'Принудительно переведено {translated} услуг через {provider.upper()}.',
                level=messages.SUCCESS
            )
        else:
            self.message_user(request, 'Не удалось перевести выбранные услуги.', level=messages.WARNING)

    force_retranslate_services.short_description = "🔄 Перевести услуги заново (перезаписать)"
    
    def save_model(self, request, obj, form, change):
        """Дополнительная логика при сохранении"""
        super().save_model(request, obj, form, change)
        
        # Проверяем уникальность slug
        if Service.objects.filter(slug=obj.slug).exclude(pk=obj.pk).exists():
            self.message_user(request, 
                f"Внимание: Slug '{obj.slug}' уже используется другой услугой!", 
                level='WARNING')
    
    class Media:
        css = {
            'all': ('admin/css/seo_admin.css',)
        }
        js = ('admin/js/seo_admin.js',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'position', 'role', 'phone_display', 'email', 'is_active', 'show_on_homepage', 'display_order')
    list_filter = ('role', 'is_active', 'show_on_homepage', 'hire_date', 'created_at')
    search_fields = ('first_name', 'last_name', 'position', 'email', 'phone', 'languages', 'bio', 'specialization')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'show_on_homepage', 'display_order')
    ordering = ['display_order', 'last_name', 'first_name']
    
    fieldsets = (
        ('Личная информация', {
            'fields': ('first_name', 'last_name', 'photo'),
            'description': 'Основная информация о сотруднике'
        }),
        ('Должность и роль', {
            'fields': ('position', 'role', 'hire_date'),
            'description': 'Профессиональная информация'
        }),
        ('Контактная информация', {
            'fields': ('phone', 'email', 'whatsapp'),
            'description': 'Способы связи с сотрудником'
        }),
        ('Социальные сети', {
            'fields': ('facebook', 'instagram', 'linkedin', 'twitter', 'telegram', 'youtube', 'tiktok'),
            'classes': ('collapse',),
            'description': 'Профили в социальных сетях'
        }),
        ('Дополнительная информация', {
            'fields': ('bio', 'specialization', 'languages'),
            'classes': ('collapse',),
            'description': 'Подробная информация о сотруднике и его навыках'
        }),
        ('Настройки отображения', {
            'fields': ('is_active', 'show_on_homepage', 'display_order'),
            'description': 'Настройки видимости на сайте'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        """Полное имя для отображения в списке"""
        return obj.full_name
    get_full_name.short_description = 'ФИО'
    get_full_name.admin_order_field = 'last_name'
    
    def get_form(self, request, obj=None, **kwargs):
        """Настройка формы с подсказками"""
        form = super().get_form(request, obj, **kwargs)
        
        help_texts = {
            'first_name': 'Имя сотрудника',
            'last_name': 'Фамилия сотрудника',
            'position': 'Должность на английском языке (как указано в оригинале)',
            'role': 'Выберите роль из предложенных вариантов',
            'phone': 'Основной телефон в любом формате',
            'email': 'Рабочий email адрес',
            'whatsapp': 'Номер для WhatsApp (можно тот же, что и основной телефон)',
            'photo': 'Фото сотрудника. Рекомендуемое разрешение: 300x300 пикселей',
            'bio': 'Краткая биография или описание сотрудника',
            'specialization': 'Основные направления работы и специализации',
            'languages': 'Языки, которыми владеет сотрудник (через запятую)',
            'hire_date': 'Дата приема на работу',
            'is_active': 'Отображать ли сотрудника на сайте',
            'show_on_homepage': 'Показывать в блоке "Наша команда" на главной странице',
            'display_order': 'Порядок отображения (меньше = выше в списке)',
        }
        
        for field_name, help_text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = help_text
        
        return form
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('display_order', 'last_name', 'first_name')
    
    actions = ['activate_employees', 'deactivate_employees', 'add_to_homepage', 'remove_from_homepage', 'duplicate_employees']
    
    def activate_employees(self, request, queryset):
        """Активировать выбранных сотрудников"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Активировано {updated} сотрудников")
    activate_employees.short_description = "Активировать выбранных сотрудников"
    
    def deactivate_employees(self, request, queryset):
        """Деактивировать выбранных сотрудников"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {updated} сотрудников")
    deactivate_employees.short_description = "Деактивировать выбранных сотрудников"
    
    def add_to_homepage(self, request, queryset):
        """Добавить на главную страницу"""
        updated = queryset.update(show_on_homepage=True)
        self.message_user(request, f"Добавлено на главную {updated} сотрудников")
    add_to_homepage.short_description = "Показывать на главной странице"
    
    def remove_from_homepage(self, request, queryset):
        """Убрать с главной страницы"""
        updated = queryset.update(show_on_homepage=False)
        self.message_user(request, f"Убрано с главной {updated} сотрудников")
    remove_from_homepage.short_description = "Не показывать на главной странице"
    
    def duplicate_employees(self, request, queryset):
        """Дублировать выбранных сотрудников"""
        for employee in queryset:
            employee.pk = None
            employee.first_name = f"{employee.first_name} (копия)"
            employee.is_active = False  # Копии создаются неактивными
            employee.show_on_homepage = False
            employee.save()
        self.message_user(request, f"Продублировано {queryset.count()} сотрудников")
    duplicate_employees.short_description = "Дублировать выбранных сотрудников"
    
    def save_model(self, request, obj, form, change):
        """Дополнительная логика при сохранении"""
        super().save_model(request, obj, form, change)
        
        # Проверяем корректность WhatsApp номера
        if obj.whatsapp and obj.whatsapp == obj.phone:
            self.message_user(request, 
                "Номера телефона и WhatsApp одинаковые - это нормально если используется один номер", 
                level='INFO')
        
        # Напоминание о заполнении фото
        if not obj.photo:
            self.message_user(request, 
                "Рекомендуется добавить фото сотрудника для лучшего представления команды", 
                level='WARNING')
    
    class Media:
        css = {
            'all': ('admin/css/seo_admin.css',)
        }
        js = ('admin/js/seo_admin.js',)
