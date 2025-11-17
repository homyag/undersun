from django.db import models
from django.utils.translation import gettext_lazy as _
import re
import random


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
    """Модель рекламного баннера главной страницы"""

    LANGUAGE_CHOICES = (
        ('ru', _('Русский')),
        ('en', _('Английский')),
        ('th', _('Тайский')),
    )

    name = models.CharField(
        _('Название баннера'),
        max_length=150,
        default='',
        help_text=_('Внутреннее имя, чтобы не путаться между акциями в админке')
    )
    language_code = models.CharField(
        _('Язык'),
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default='ru',
        help_text=_('Создавайте отдельные баннеры для каждого языка (RU / EN / TH).')
    )
    desktop_image = models.ImageField(
        _('Изображение для десктопа'),
        upload_to='promotional_banners/',
        blank=True,
        help_text=_('Рекомендуемый размер: 2400×150 px. Держите ключевой контент в центральной зоне, края могут обрезаться.')
    )
    tablet_image = models.ImageField(
        _('Изображение для планшета'),
        upload_to='promotional_banners/',
        blank=True,
        help_text=_('Рекомендуемый размер: 1536×150 px. Фокусируйте основной контент в центре кадра.')
    )
    mobile_image = models.ImageField(
        _('Изображение для мобильных устройств'),
        upload_to='promotional_banners/',
        blank=True,
        help_text=_('Рекомендуемый размер: 828×150 px. Располагайте текст и логотип внутри центральных 60% ширины.')
    )
    link = models.CharField(
        _('Ссылка'),
        max_length=255,
        blank=True,
        help_text=_('Полный URL (https://example.com), путь с языковым префиксом (/ru/path/) или имя Django URL pattern.')
    )

    class Meta:
        verbose_name = _('Рекламный баннер')
        verbose_name_plural = _('Рекламные баннеры')
        ordering = ['language_code', 'name']

    def __str__(self):
        if not self.pk:
            return _('Новый баннер')
        lang_display = dict(self.LANGUAGE_CHOICES).get(self.language_code, self.language_code)
        base = self.name or f"#{self.pk}"
        return f"{base} [{lang_display}]"

    @classmethod
    def get_active_banner(cls, language_code=None):
        """Совместимость: возвращает случайный баннер для языка."""
        return cls.get_random_banner(language_code)

    @classmethod
    def get_random_banner(cls, language_code=None):
        """Возвращает случайный баннер для языка (с fallback на русский)."""
        if language_code is None:
            from django.utils.translation import get_language
            current_language = get_language() or 'ru'
            language_code = current_language[:2]

        banner = cls._get_random_from_queryset(
            cls.objects.filter(language_code=language_code)
        )
        if banner:
            return banner
        if language_code != 'ru':
            return cls._get_random_from_queryset(
                cls.objects.filter(language_code='ru')
            )
        return None

    @staticmethod
    def _get_random_from_queryset(queryset):
        ids = list(queryset.values_list('id', flat=True))
        if not ids:
            return None
        return queryset.filter(id=random.choice(ids)).first()

    def get_language_aware_url(self, language_code=None):
        """Получить ссылку с учётом языкового префикса (если она относительная)."""
        if not self.link:
            return None

        if language_code is None:
            from django.utils.translation import get_language
            current_language = get_language() or 'ru'
            language_code = current_language[:2]

        link = self.link.strip()

        if link.startswith(('http://', 'https://')):
            return link

        if link.startswith('/'):
            if not any(link.startswith(f'/{lang}/') for lang in ('ru', 'en', 'th')):
                return f'/{language_code}{link}'
            return link

        try:
            from django.urls import reverse
            return reverse(link)
        except Exception:
            return f'/{language_code}/{link.lstrip("/")}'

    @staticmethod
    def image_disclaimer():
        return _(
            'Загрузите три версии баннера: 2400×150 px (desktop), 1536×150 px (tablet) и 828×150 px (mobile). '
            'Важные элементы держите в центральной зоне — по ширине она безопасна для всех устройств. '
            'Создайте отдельный баннер для каждого языка (RU / EN / TH), чтобы использовать локализованные изображения.'
        )


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
    
    # Социальные сети
    facebook = models.URLField(_('Facebook'), blank=True,
                              help_text=_('Ссылка на профиль в Facebook'))
    instagram = models.URLField(_('Instagram'), blank=True,
                               help_text=_('Ссылка на профиль в Instagram'))
    linkedin = models.URLField(_('LinkedIn'), blank=True,
                              help_text=_('Ссылка на профиль в LinkedIn'))
    twitter = models.URLField(_('Twitter'), blank=True,
                             help_text=_('Ссылка на профиль в Twitter'))
    telegram = models.CharField(_('Telegram'), max_length=100, blank=True,
                               help_text=_('Username в Telegram (без @)'))
    youtube = models.URLField(_('YouTube'), blank=True,
                             help_text=_('Ссылка на канал YouTube'))
    tiktok = models.URLField(_('TikTok'), blank=True,
                            help_text=_('Ссылка на профиль в TikTok'))
    
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
        if not self.whatsapp:
            return None

        raw_value = self.whatsapp.strip()
        digits_only = ''.join(filter(str.isdigit, raw_value))

        if not digits_only:
            return None

        phone_clean = digits_only

        if raw_value.startswith('+'):
            phone_clean = digits_only
        elif raw_value.startswith('00'):
            phone_clean = digits_only[2:] or digits_only
        elif digits_only.startswith('66'):
            phone_clean = digits_only
        elif digits_only.startswith('0'):
            phone_clean = f"66{digits_only[1:]}"
        elif len(digits_only) > 10:
            phone_clean = digits_only
        else:
            phone_clean = f"66{digits_only}"

        return f"https://wa.me/{phone_clean}"
    
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
    
    @property
    def telegram_url(self):
        """URL для Telegram ссылки"""
        if self.telegram:
            username = self.telegram.lstrip('@')  # Убираем @ если есть
            return f"https://t.me/{username}"
        return None
    
    def get_social_media_list(self):
        """Получить список всех социальных сетей с данными"""
        social_media = []
        
        if self.facebook:
            social_media.append({
                'name': 'Facebook',
                'url': self.facebook,
                'icon': 'fab fa-facebook-f',
                'color': '#1877F2'
            })
        
        if self.instagram:
            social_media.append({
                'name': 'Instagram', 
                'url': self.instagram,
                'icon': 'fab fa-instagram',
                'color': '#E4405F'
            })
        
        if self.linkedin:
            social_media.append({
                'name': 'LinkedIn',
                'url': self.linkedin,
                'icon': 'fab fa-linkedin-in',
                'color': '#0A66C2'
            })
        
        if self.twitter:
            social_media.append({
                'name': 'Twitter',
                'url': self.twitter,
                'icon': 'fab fa-twitter',
                'color': '#1DA1F2'
            })
        
        if self.telegram_url:
            social_media.append({
                'name': 'Telegram',
                'url': self.telegram_url,
                'icon': 'fab fa-telegram-plane',
                'color': '#0088CC'
            })
        
        if self.youtube:
            social_media.append({
                'name': 'YouTube',
                'url': self.youtube,
                'icon': 'fab fa-youtube',
                'color': '#FF0000'
            })
        
        if self.tiktok:
            social_media.append({
                'name': 'TikTok',
                'url': self.tiktok,
                'icon': 'fab fa-tiktok',
                'color': '#000000'
            })
        
        return social_media
