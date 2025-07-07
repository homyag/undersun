from django.contrib import admin
from .models import SEOPage, SEOTemplate, PromotionalBanner, Service


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
    list_display = ('title', 'discount_text', 'is_active', 'priority', 'valid_until', 'created_at')
    list_filter = ('is_active', 'valid_until', 'created_at')
    search_fields = ('title', 'description', 'discount_text', 'button_text')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'priority')
    ordering = ['priority', '-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'image'),
            'description': 'Основное содержимое рекламного баннера'
        }),
        ('Предложение и акция', {
            'fields': ('discount_text', 'valid_until'),
            'description': 'Информация о скидке или специальном предложении'
        }),
        ('Кнопка действия', {
            'fields': ('button_text', 'button_url'),
            'description': 'Настройки кнопки призыва к действию'
        }),
        ('Настройки отображения', {
            'fields': ('is_active', 'priority'),
            'description': 'Приоритет: чем меньше число, тем выше приоритет. Показывается только один активный баннер с наивысшим приоритетом'
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
            'title': 'Основной заголовок баннера (до 200 символов)',
            'description': 'Описание предложения (до 500 символов)',
            'image': 'Фоновое изображение баннера. Рекомендуемое разрешение: 1920x1080 пикселей',
            'discount_text': 'Текст акции или скидки, например "Скидка 20%" или "Ограниченное предложение"',
            'valid_until': 'Дата окончания действия предложения. Оставьте пустым для бессрочного предложения',
            'button_text': 'Текст на кнопке призыва к действию',
            'button_url': 'Ссылка для перехода при нажатии на кнопку (URL или Django URL pattern)',
            'is_active': 'Показывать ли баннер на сайте',
            'priority': 'Чем меньше число, тем выше приоритет (1 = самый высокий приоритет)',
        }
        
        for field_name, help_text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = help_text
        
        return form
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('priority', '-created_at')
    
    actions = ['activate_banners', 'deactivate_banners', 'duplicate_banners']
    
    def activate_banners(self, request, queryset):
        """Активировать выбранные баннеры"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Активировано {updated} баннеров")
    activate_banners.short_description = "Активировать выбранные баннеры"
    
    def deactivate_banners(self, request, queryset):
        """Деактивировать выбранные баннеры"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {updated} баннеров")
    deactivate_banners.short_description = "Деактивировать выбранные баннеры"
    
    def duplicate_banners(self, request, queryset):
        """Дублировать выбранные баннеры"""
        for banner in queryset:
            banner.pk = None
            banner.title = f"{banner.title} (копия)"
            banner.is_active = False  # Копии создаются неактивными
            banner.save()
        self.message_user(request, f"Продублировано {queryset.count()} баннеров")
    duplicate_banners.short_description = "Дублировать выбранные баннеры"
    
    def save_model(self, request, obj, form, change):
        """Дополнительная логика при сохранении"""
        super().save_model(request, obj, form, change)
        
        # Показываем предупреждение, если создается баннер с истекшим сроком действия
        if obj.valid_until:
            from django.utils import timezone
            if obj.valid_until < timezone.now().date():
                self.message_user(request, 
                    f"Внимание: Дата окончания действия баннера '{obj.title}' уже прошла!", 
                    level='WARNING')
    
    class Media:
        css = {
            'all': ('admin/css/seo_admin.css',)
        }
        js = ('admin/js/seo_admin.js',)


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
    
    actions = ['activate_services', 'deactivate_services', 'add_to_menu', 'remove_from_menu', 'duplicate_services']
    
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