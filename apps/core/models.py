from django.db import models
from django.utils.translation import gettext_lazy as _
import re


class SEOPage(models.Model):
    """SEO метатеги для страниц сайта"""
    
    # URL паттерн для страницы (например: 'home', 'properties', 'about')
    page_name = models.CharField(_('Имя страницы'), max_length=100, unique=True)
    
    # SEO данные для русского языка
    title_ru = models.CharField(_('Title (RU)'), max_length=200, blank=True)
    description_ru = models.TextField(_('Description (RU)'), max_length=300, blank=True)
    keywords_ru = models.TextField(_('Keywords (RU)'), blank=True)
    
    # SEO данные для английского языка
    title_en = models.CharField(_('Title (EN)'), max_length=200, blank=True)
    description_en = models.TextField(_('Description (EN)'), max_length=300, blank=True)
    keywords_en = models.TextField(_('Keywords (EN)'), blank=True)
    
    # SEO данные для тайского языка
    title_th = models.CharField(_('Title (TH)'), max_length=200, blank=True)
    description_th = models.TextField(_('Description (TH)'), max_length=300, blank=True)
    keywords_th = models.TextField(_('Keywords (TH)'), blank=True)
    
    # Общие настройки
    is_active = models.BooleanField(_('Активно'), default=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('SEO страница')
        verbose_name_plural = _('SEO страницы')
        
    def __str__(self):
        return self.page_name
        
    def get_title(self, language_code='ru'):
        """Получить заголовок для указанного языка"""
        field_name = f'title_{language_code}'
        return getattr(self, field_name, '') or getattr(self, 'title_ru', '')
        
    def get_description(self, language_code='ru'):
        """Получить описание для указанного языка"""
        field_name = f'description_{language_code}'
        return getattr(self, field_name, '') or getattr(self, 'description_ru', '')
        
    def get_keywords(self, language_code='ru'):
        """Получить ключевые слова для указанного языка"""
        field_name = f'keywords_{language_code}'
        return getattr(self, field_name, '') or getattr(self, 'keywords_ru', '')


class PromotionalBanner(models.Model):
    """Модель для управления рекламным баннером на главной странице"""
    
    # Визуальное оформление
    image = models.ImageField(_('Фоновое изображение'), upload_to='promotional_banners/', 
                            help_text=_('Рекомендуемое разрешение: 1248x125 пикселей'))
    
    # Временные настройки
    valid_until = models.DateField(_('Действительно до'), blank=True, null=True,
                                 help_text=_('Дата окончания действия предложения'))
    button_url = models.CharField(_('Ссылка кнопки'), max_length=200, blank=True,
                                help_text=_('URL или имя Django URL pattern. Поддерживает: "/property/" (статический URL), "property_list" (имя URL), "https://example.com" (внешний URL)'))
    
    # Настройки отображения
    is_active = models.BooleanField(_('Активно'), default=True,
                                  help_text=_('Показывать ли баннер на сайте'))
    priority = models.IntegerField(_('Приоритет'), default=100,
                                 help_text=_('Чем меньше число, тем выше приоритет. Показывается баннер с наивысшим приоритетом'))
    
    # Даты
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('Рекламный баннер')
        verbose_name_plural = _('Рекламные баннеры')
        ordering = ['priority', '-created_at']
    
    def __str__(self):
        status = _('Активный') if self.is_active else _('Неактивный')
        # Получаем заголовок на русском языке для отображения
        try:
            title = self.translations.get(language_code='ru').title
        except:
            title = f"Баннер #{self.pk}"
        return f"{title} ({status})"
    
    def get_translation(self, language_code='ru'):
        """Получить перевод для указанного языка с fallback на русский"""
        try:
            return self.translations.get(language_code=language_code)
        except PromotionalBannerTranslation.DoesNotExist:
            try:
                return self.translations.get(language_code='ru')
            except PromotionalBannerTranslation.DoesNotExist:
                return None
    
    @property
    def title(self):
        """Получить заголовок для текущего языка"""
        from django.utils.translation import get_language
        current_language = get_language() or 'ru'
        # Берем первые 2 символа для языковых кодов типа 'ru', 'en', 'th'
        lang_code = current_language[:2]
        translation = self.get_translation(lang_code)
        return translation.title if translation else ''
    
    @property
    def description(self):
        """Получить описание для текущего языка"""
        from django.utils.translation import get_language
        current_language = get_language() or 'ru'
        lang_code = current_language[:2]
        translation = self.get_translation(lang_code)
        return translation.description if translation else ''
    
    @property
    def discount_text(self):
        """Получить текст скидки для текущего языка"""
        from django.utils.translation import get_language
        current_language = get_language() or 'ru'
        lang_code = current_language[:2]
        translation = self.get_translation(lang_code)
        return translation.discount_text if translation else ''
    
    @property
    def button_text(self):
        """Получить текст кнопки для текущего языка"""
        from django.utils.translation import get_language
        current_language = get_language() or 'ru'
        lang_code = current_language[:2]
        translation = self.get_translation(lang_code)
        return translation.button_text if translation else ''
    
    @classmethod
    def get_active_banner(cls):
        """Получить активный баннер с наивысшим приоритетом"""
        from django.utils import timezone
        now = timezone.now().date()
        
        queryset = cls.objects.filter(is_active=True).prefetch_related('translations')
        
        # Фильтруем по дате окончания, если указана
        queryset = queryset.filter(
            models.Q(valid_until__isnull=True) | 
            models.Q(valid_until__gte=now)
        )
        
        return queryset.first()
    
    def get_language_aware_url(self, language_code=None):
        """Получить URL кнопки с учетом текущего языка"""
        if not self.button_url:
            return None
        
        # Получаем текущий язык, если не передан
        if language_code is None:
            from django.utils.translation import get_language
            current_language = get_language() or 'ru'
            language_code = current_language[:2]
        
        # Если URL начинается с http:// или https://, возвращаем как есть
        if self.button_url.startswith(('http://', 'https://')):
            return self.button_url
        
        # Если URL начинается с '/', это статический URL
        if self.button_url.startswith('/'):
            # Проверяем, не содержит ли URL уже языковой префикс
            if not any(self.button_url.startswith(f'/{lang}/') for lang in ['ru', 'en', 'th']):
                return f'/{language_code}{self.button_url}'
            return self.button_url
        
        # Если URL не содержит '/', предполагаем, что это имя URL pattern
        try:
            from django.urls import reverse
            # Пытаемся разобрать URL pattern с параметрами
            url_parts = self.button_url.split(':')
            if len(url_parts) == 2:
                # Формат: "app_name:url_name" или "app_name:url_name:param"
                app_name, url_pattern = url_parts
                return reverse(f'{app_name}:{url_pattern}')
            else:
                # Простое имя URL pattern
                return reverse(self.button_url)
        except Exception:
            # Если не удалось распарсить как URL pattern, возвращаем как статический URL
            return f'/{language_code}/{self.button_url.lstrip("/")}'
    
    def is_valid(self):
        """Проверить, действителен ли баннер на текущую дату"""
        if not self.is_active:
            return False
        
        if self.valid_until:
            from django.utils import timezone
            return self.valid_until >= timezone.now().date()
        
        return True


class PromotionalBannerTranslation(models.Model):
    """Переводы для рекламных баннеров"""
    
    LANGUAGE_CHOICES = [
        ('ru', 'Русский'),
        ('en', 'English'),
        ('th', 'ไทย'),
    ]
    
    banner = models.ForeignKey(PromotionalBanner, on_delete=models.CASCADE, related_name='translations')
    language_code = models.CharField(_('Язык'), max_length=2, choices=LANGUAGE_CHOICES)
    
    # Переводимые поля
    title = models.CharField(_('Заголовок'), max_length=200)
    description = models.TextField(_('Описание'), max_length=500)
    discount_text = models.CharField(_('Текст скидки/предложения'), max_length=100, blank=True,
                                   help_text=_('Например: "Скидка 20%" или "Ограниченное предложение"'))
    button_text = models.CharField(_('Текст кнопки'), max_length=50, blank=True,
                                 help_text=_('Например: "Узнать подробнее" или "Связаться с нами"'))
    
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('Перевод баннера')
        verbose_name_plural = _('Переводы баннеров')
        unique_together = [['banner', 'language_code']]
        ordering = ['language_code']
    
    def __str__(self):
        return f"{self.title} ({self.get_language_code_display()})"


class SEOTemplate(models.Model):
    """Шаблоны для автоматической генерации SEO метатегов объектов недвижимости"""
    
    TEMPLATE_TYPES = [
        ('property_detail', _('Карточка недвижимости')),
        ('property_list_type', _('Список по типу недвижимости')),
        ('property_list_location', _('Список по локации')),
    ]
    
    # Импортируем типы недвижимости из PropertyType
    PROPERTY_TYPE_CHOICES = [
        ('', _('-- Все типы --')),
        ('villa', _('Вилла')),
        ('apartment', _('Апартаменты')),
        ('townhouse', _('Таунхаус')),
        ('land', _('Земельный участок')),
        ('investment', _('Инвестиции')),
        ('business', _('Готовый бизнес')),
    ]
    
    DEAL_TYPE_CHOICES = [
        ('', _('-- Все типы сделок --')),
        ('sale', _('Продажа')),
        ('rent', _('Аренда')),
        ('both', _('Продажа/Аренда')),
    ]
    
    # Основная информация
    name = models.CharField(_('Название шаблона'), max_length=100)
    template_type = models.CharField(_('Тип шаблона'), max_length=50, choices=TEMPLATE_TYPES)
    property_type = models.CharField(_('Тип недвижимости'), max_length=50, blank=True, 
                                   choices=PROPERTY_TYPE_CHOICES,
                                   help_text=_('Выберите тип недвижимости или оставьте пустым для всех типов'))
    deal_type = models.CharField(_('Тип сделки'), max_length=20, blank=True,
                               choices=DEAL_TYPE_CHOICES,
                               help_text=_('Выберите тип сделки или оставьте пустым для всех типов'))
    
    # Шаблоны для русского языка
    title_template_ru = models.CharField(_('Шаблон заголовка (RU)'), max_length=200,
                                       help_text=_('Используйте переменные: {title}, {type}, {location}, {district}, {price}, {area}'))
    description_template_ru = models.TextField(_('Шаблон описания (RU)'), max_length=300,
                                             help_text=_('Используйте переменные: {title}, {type}, {location}, {district}, {price}, {area}, {rooms}'))
    keywords_template_ru = models.TextField(_('Шаблон ключевых слов (RU)'),
                                          help_text=_('Используйте переменные через запятую'))
    
    # Шаблоны для английского языка
    title_template_en = models.CharField(_('Шаблон заголовка (EN)'), max_length=200, blank=True)
    description_template_en = models.TextField(_('Шаблон описания (EN)'), max_length=300, blank=True)
    keywords_template_en = models.TextField(_('Шаблон ключевых слов (EN)'), blank=True)
    
    # Шаблоны для тайского языка
    title_template_th = models.CharField(_('Шаблон заголовка (TH)'), max_length=200, blank=True)
    description_template_th = models.TextField(_('Шаблон описания (TH)'), max_length=300, blank=True)
    keywords_template_th = models.TextField(_('Шаблон ключевых слов (TH)'), blank=True)
    
    # Настройки
    priority = models.IntegerField(_('Приоритет'), default=100, 
                                 help_text=_('Чем меньше число, тем выше приоритет'))
    is_active = models.BooleanField(_('Активно'), default=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('SEO шаблон')
        verbose_name_plural = _('SEO шаблоны')
        ordering = ['priority', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def get_template(self, field_type, language_code='ru'):
        """Получить шаблон для указанного типа поля и языка"""
        field_name = f'{field_type}_template_{language_code}'
        return getattr(self, field_name, '') or getattr(self, f'{field_type}_template_ru', '')
    
    def render_template(self, template_text, property_obj, language_code='ru'):
        """Отрендерить шаблон с данными объекта недвижимости"""
        if not template_text or not property_obj:
            return template_text
            
        # Подготавливаем переменные для подстановки с учётом языка
        context = {
            'title': property_obj.title,
            'type': property_obj._get_translated_type_name(language_code),
            'location': str(property_obj.location) if property_obj.location else '',
            'district': property_obj._get_translated_district_name(language_code),
            'price': self._format_price(property_obj),
            'area': f"{property_obj.total_area}" if property_obj.total_area else '',
            'rooms': f"{property_obj.bedrooms}" if property_obj.bedrooms else '',
            'deal_type': property_obj._get_translated_deal_type(language_code),
        }
        
        # Заменяем переменные в шаблоне
        result = template_text
        for key, value in context.items():
            result = result.replace(f'{{{key}}}', str(value) if value else '')
            
        # Очищаем лишние пробелы и знаки препинания
        result = re.sub(r'\s+', ' ', result)  # Множественные пробелы
        result = re.sub(r'\s*,\s*,', ',', result)  # Двойные запятые
        result = re.sub(r',\s*$', '', result)  # Запятая в конце
        result = result.strip()
        
        return result
    
    def _format_price(self, property_obj):
        """Форматировать цену для отображения"""
        if property_obj.deal_type == 'sale' and property_obj.price_sale_usd:
            return f"${property_obj.price_sale_usd:,.0f}"
        elif property_obj.deal_type == 'rent' and property_obj.price_rent_monthly:
            return f"${property_obj.price_rent_monthly:,.0f}/мес"
        elif property_obj.deal_type == 'both':
            if property_obj.price_sale_usd:
                return f"${property_obj.price_sale_usd:,.0f}"
        return ""
    
    def generate_seo_for_property(self, property_obj, language_code='ru'):
        """Сгенерировать SEO данные для объекта недвижимости"""
        return {
            'title': self.render_template(self.get_template('title', language_code), property_obj, language_code),
            'description': self.render_template(self.get_template('description', language_code), property_obj, language_code),
            'keywords': self.render_template(self.get_template('keywords', language_code), property_obj, language_code),
        }


class Service(models.Model):
    """Модель для статичных страниц услуг агентства"""
    
    # Slug для URL
    slug = models.SlugField(_('URL-адрес'), max_length=100, unique=True,
                           help_text=_('Уникальный URL адрес страницы (например: buying-property)'))
    
    # Основная информация (многоязычные поля будут добавлены через modeltranslation)
    title = models.CharField(_('Заголовок'), max_length=200)
    description = models.TextField(_('Краткое описание'), max_length=500,
                                 help_text=_('Краткое описание услуги для превью'))
    content = models.TextField(_('Основной контент'),
                             help_text=_('Подробное описание услуги'))
    
    # SEO поля
    meta_title = models.CharField(_('SEO заголовок'), max_length=200, blank=True,
                                help_text=_('Если пустое, будет использоваться основной заголовок'))
    meta_description = models.TextField(_('SEO описание'), max_length=300, blank=True,
                                      help_text=_('Если пустое, будет использоваться краткое описание'))
    meta_keywords = models.TextField(_('SEO ключевые слова'), blank=True)
    
    # Изображение для страницы
    image = models.ImageField(_('Изображение'), upload_to='services/', blank=True,
                            help_text=_('Основное изображение для страницы услуги'))
    
    # Иконка для меню
    icon_class = models.CharField(_('CSS класс иконки'), max_length=100, blank=True,
                                help_text=_('CSS класс для иконки в меню (например: fas fa-home)'))
    
    # Настройки отображения
    is_active = models.BooleanField(_('Активно'), default=True)
    show_in_menu = models.BooleanField(_('Показывать в меню'), default=True)
    menu_order = models.IntegerField(_('Порядок в меню'), default=100,
                                   help_text=_('Порядок отображения в меню (меньше = выше)'))
    
    # Даты
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('Услуга')
        verbose_name_plural = _('Услуги')
        ordering = ['menu_order', 'title']
        
    def __str__(self):
        return self.title
        
    def get_absolute_url(self):
        """Получить URL страницы услуги"""
        from django.urls import reverse
        return reverse('core:service_detail', kwargs={'slug': self.slug})
        
    def get_meta_title(self):
        """Получить SEO заголовок или основной заголовок"""
        return self.meta_title if self.meta_title else self.title
        
    def get_meta_description(self):
        """Получить SEO описание или краткое описание"""
        return self.meta_description if self.meta_description else self.description
        
    @classmethod
    def get_menu_services(cls):
        """Получить услуги для отображения в меню"""
        return cls.objects.filter(is_active=True, show_in_menu=True).order_by('menu_order', 'title')


class Team(models.Model):
    """Модель сотрудников компании"""
    
    ROLE_CHOICES = [
        ('sales_director', _('Sales Director')),
        ('senior_manager', _('Senior Manager for International Client Relations')),
        ('manager', _('Manager for International Client Relations')),
        ('chief_art_officer', _('Chief Art Officer (CAO)')),
        ('chief_marketing_officer', _('Chief Marketing Officer (CMO)')),
        ('chief_financial_officer', _('Chief Financial Officer (CFO)')),
        ('office_manager', _('Office Manager')),
        ('agent', _('Агент по недвижимости')),
        ('specialist', _('Специалист')),
        ('other', _('Другое')),
    ]
    
    # Основная информация
    first_name = models.CharField(_('Имя'), max_length=100)
    last_name = models.CharField(_('Фамилия'), max_length=100)
    position = models.CharField(_('Должность'), max_length=200)
    role = models.CharField(_('Роль'), max_length=50, choices=ROLE_CHOICES, default='specialist')
    
    # Контактная информация
    phone = models.CharField(_('Телефон'), max_length=20, blank=True)
    email = models.EmailField(_('Email'), blank=True)
    whatsapp = models.CharField(_('WhatsApp'), max_length=20, blank=True,
                               help_text=_('Номер телефона для WhatsApp'))
    
    # Фото сотрудника
    photo = models.ImageField(_('Фото'), upload_to='team/', blank=True,
                            help_text=_('Рекомендуемое разрешение: 300x300 пикселей'))
    
    # Описание и навыки
    bio = models.TextField(_('Биография'), blank=True,
                          help_text=_('Краткая информация о сотруднике'))
    specialization = models.TextField(_('Специализация'), blank=True,
                                    help_text=_('Основные направления работы'))
    
    # Языки
    languages = models.CharField(_('Языки'), max_length=200, blank=True,
                               help_text=_('Перечислите языки через запятую'))
    
    # Настройки отображения
    is_active = models.BooleanField(_('Активный'), default=True,
                                  help_text=_('Показывать ли сотрудника на сайте'))
    show_on_homepage = models.BooleanField(_('Показывать на главной'), default=False,
                                         help_text=_('Отображать в блоке "Наша команда" на главной странице'))
    display_order = models.IntegerField(_('Порядок отображения'), default=100,
                                      help_text=_('Порядок отображения в списке (меньше = выше)'))
    
    # Даты
    hire_date = models.DateField(_('Дата приема на работу'), blank=True, null=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('Сотрудник')
        verbose_name_plural = _('Сотрудники')
        ordering = ['display_order', 'last_name', 'first_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        """Полное имя сотрудника"""
        return f"{self.first_name} {self.last_name}"
    
    @property 
    def whatsapp_url(self):
        """URL для WhatsApp ссылки"""
        if self.whatsapp:
            # Очищаем номер от лишних символов
            phone_clean = ''.join(filter(str.isdigit, self.whatsapp))
            if phone_clean.startswith('0'):
                phone_clean = '66' + phone_clean[1:]  # Заменяем 0 на код Таиланда
            elif not phone_clean.startswith('66'):
                phone_clean = '66' + phone_clean
            return f"https://wa.me/{phone_clean}"
        return None
    
    @property
    def phone_display(self):
        """Форматированный телефон для отображения"""
        if self.phone:
            # Простое форматирование для тайских номеров
            phone_clean = ''.join(filter(str.isdigit, self.phone))
            if len(phone_clean) >= 10:
                return f"+{phone_clean[:2]} {phone_clean[2:4]} {phone_clean[4:7]} {phone_clean[7:]}"
        return self.phone
    
    @classmethod
    def get_homepage_team(cls):
        """Получить команду для отображения на главной странице"""
        return cls.objects.filter(
            is_active=True, 
            show_on_homepage=True
        ).order_by('display_order', 'last_name')
    
    @classmethod
    def get_all_active(cls):
        """Получить всех активных сотрудников"""
        return cls.objects.filter(is_active=True).order_by('display_order', 'last_name')
    
    def get_languages_list(self):
        """Получить список языков как массив"""
        if self.languages:
            return [lang.strip() for lang in self.languages.split(',') if lang.strip()]
        return []