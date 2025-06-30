from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit
from apps.locations.models import District, Location


class PropertyType(models.Model):
    """Типы недвижимости"""
    PROPERTY_TYPES = [
        ('villa', _('Вилла')),
        ('apartment', _('Апартаменты')),
        ('townhouse', _('Таунхаус')),
        ('land', _('Земельный участок')),
        ('investment', _('Инвестиции')),
        ('business', _('Готовый бизнес')),
    ]

    name = models.CharField(_('Тип'), max_length=20, choices=PROPERTY_TYPES, unique=True)
    name_display = models.CharField(_('Отображаемое название'), max_length=50)
    icon = models.CharField(_('Иконка'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Тип недвижимости')
        verbose_name_plural = _('Типы недвижимости')

    def __str__(self):
        return self.name_display


class Developer(models.Model):
    """Застройщики"""
    name = models.CharField(_('Название'), max_length=100)
    slug = models.SlugField(_('URL'), unique=True)
    description = models.TextField(_('Описание'), blank=True)
    logo = models.ImageField(_('Логотип'), upload_to='developers/', blank=True)
    website = models.URLField(_('Сайт'), blank=True)

    class Meta:
        verbose_name = _('Застройщик')
        verbose_name_plural = _('Застройщики')

    def __str__(self):
        return self.name


class Property(models.Model):
    """Основная модель недвижимости"""
    STATUS_CHOICES = [
        ('available', _('Доступно')),
        ('reserved', _('Забронировано')),
        ('sold', _('Продано')),
        ('rented', _('Сдано')),
    ]

    DEAL_TYPES = [
        ('sale', _('Продажа')),
        ('rent', _('Аренда')),
        ('both', _('Продажа/Аренда')),
    ]

    # Основная информация
    title = models.CharField(_('Название'), max_length=200)
    slug = models.SlugField(_('URL'), unique=True)
    property_type = models.ForeignKey(PropertyType, on_delete=models.CASCADE, verbose_name=_('Тип'))
    deal_type = models.CharField(_('Тип сделки'), max_length=10, choices=DEAL_TYPES, default='sale')
    status = models.CharField(_('Статус'), max_length=10, choices=STATUS_CHOICES, default='available')

    # Описание
    description = models.TextField(_('Описание'))
    short_description = models.CharField(_('Краткое описание'), max_length=300, blank=True)

    # Локация
    district = models.ForeignKey(District, on_delete=models.CASCADE, verbose_name=_('Район'))
    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name=_('Локация'), blank=True, null=True)
    address = models.CharField(_('Адрес'), max_length=200, blank=True)

    # Координаты для карты
    latitude = models.DecimalField(_('Широта'), max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(_('Долгота'), max_digits=11, decimal_places=8, blank=True, null=True)

    # Характеристики
    bedrooms = models.PositiveIntegerField(_('Спальни'), blank=True, null=True)
    bathrooms = models.PositiveIntegerField(_('Ванные'), blank=True, null=True)
    area_total = models.DecimalField(_('Общая площадь, м²'), max_digits=8, decimal_places=2, blank=True, null=True)
    area_living = models.DecimalField(_('Жилая площадь, м²'), max_digits=8, decimal_places=2, blank=True, null=True)
    area_land = models.DecimalField(_('Площадь участка, м²'), max_digits=10, decimal_places=2, blank=True, null=True)
    floor = models.PositiveIntegerField(_('Этаж'), blank=True, null=True)
    floors_total = models.PositiveIntegerField(_('Всего этажей'), blank=True, null=True)

    # Цены
    price_sale_usd = models.DecimalField(_('Цена продажи, USD'), max_digits=12, decimal_places=2, blank=True, null=True)
    price_sale_thb = models.DecimalField(_('Цена продажи, THB'), max_digits=15, decimal_places=2, blank=True, null=True)
    price_rent_monthly = models.DecimalField(_('Аренда в месяц, USD'), max_digits=10, decimal_places=2, blank=True,
                                             null=True)

    # Дополнительная информация
    developer = models.ForeignKey(Developer, on_delete=models.SET_NULL, blank=True, null=True,
                                  verbose_name=_('Застройщик'))
    year_built = models.PositiveIntegerField(_('Год постройки'), blank=True, null=True)
    furnished = models.BooleanField(_('С мебелью'), default=False)
    pool = models.BooleanField(_('Бассейн'), default=False)
    parking = models.BooleanField(_('Парковка'), default=False)
    security = models.BooleanField(_('Охрана'), default=False)
    gym = models.BooleanField(_('Спортзал'), default=False)

    # Новые поля для совместимости со старой БД
    legacy_id = models.CharField(_('ID старой системы'), max_length=20, blank=True, null=True, unique=True,
                                help_text=_('Идентификатор из старой Joomla системы (например: VS82)'))
    complex_name = models.CharField(_('Название комплекса'), max_length=100, blank=True,
                                   help_text=_('Название жилого комплекса или проекта'))
    pool_area = models.DecimalField(_('Площадь бассейна, м²'), max_digits=6, decimal_places=2, blank=True, null=True)
    
    # Финансовая информация
    original_price_thb = models.DecimalField(_('Первоначальная цена, THB'), max_digits=15, decimal_places=2, 
                                           blank=True, null=True,
                                           help_text=_('Цена до скидки'))
    is_urgent_sale = models.BooleanField(_('Срочная продажа'), default=False)
    urgency_note = models.CharField(_('Примечание о срочности'), max_length=200, blank=True,
                                   help_text=_('Дополнительная информация о срочной продаже'))
    
    # Архитектурные особенности
    architectural_style = models.CharField(_('Архитектурный стиль'), max_length=100, blank=True)
    material_type = models.CharField(_('Материалы'), max_length=200, blank=True,
                                    help_text=_('Основные строительные материалы'))
    
    # Инвестиционная информация
    investment_potential = models.TextField(_('Инвестиционный потенциал'), blank=True,
                                          help_text=_('Описание инвестиционной привлекательности'))
    suitable_for = models.CharField(_('Подходит для'), max_length=200, blank=True,
                                   help_text=_('Назначение использования (отпуск, постоянное проживание и т.д.)'))
    
    # Расстояния до ключевых объектов (в минутах)
    distance_to_beach = models.PositiveIntegerField(_('До пляжа, мин'), blank=True, null=True)
    distance_to_airport = models.PositiveIntegerField(_('До аэропорта, мин'), blank=True, null=True)
    distance_to_school = models.PositiveIntegerField(_('До школы, мин'), blank=True, null=True)

    # Мета-информация
    views_count = models.PositiveIntegerField(_('Просмотры'), default=0)
    is_featured = models.BooleanField(_('Рекомендуемое'), default=False)
    is_active = models.BooleanField(_('Активно'), default=True)

    # SEO поля (опциональные - для переопределения автогенерации)
    custom_title_ru = models.CharField(_('Заголовок (RU)'), max_length=200, blank=True,
                                     help_text=_('Оставьте пустым для автоматической генерации'))
    custom_description_ru = models.TextField(_('Описание (RU)'), max_length=300, blank=True,
                                           help_text=_('Оставьте пустым для автоматической генерации'))
    custom_keywords_ru = models.TextField(_('Ключевые слова (RU)'), blank=True,
                                        help_text=_('Оставьте пустым для автоматической генерации'))
    
    custom_title_en = models.CharField(_('Заголовок (EN)'), max_length=200, blank=True,
                                     help_text=_('Оставьте пустым для автоматической генерации'))
    custom_description_en = models.TextField(_('Описание (EN)'), max_length=300, blank=True,
                                           help_text=_('Оставьте пустым для автоматической генерации'))
    custom_keywords_en = models.TextField(_('Ключевые слова (EN)'), blank=True,
                                        help_text=_('Оставьте пустым для автоматической генерации'))
    
    custom_title_th = models.CharField(_('Заголовок (TH)'), max_length=200, blank=True,
                                     help_text=_('Оставьте пустым для автоматической генерации'))
    custom_description_th = models.TextField(_('Описание (TH)'), max_length=300, blank=True,
                                           help_text=_('Оставьте пустым для автоматической генерации'))
    custom_keywords_th = models.TextField(_('Ключевые слова (TH)'), blank=True,
                                        help_text=_('Оставьте пустым для автоматической генерации'))

    # Временные метки
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('Недвижимость')
        verbose_name_plural = _('Недвижимость')
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('property_detail', kwargs={'slug': self.slug})

    @property
    def main_image(self):
        """Получить главное изображение"""
        return self.images.filter(is_main=True).first()

    @property
    def price_display(self):
        """Отформатированная цена для отображения"""
        if self.deal_type == 'sale' and self.price_sale_usd:
            price_str = f"${self.price_sale_usd:,.0f}"
            if self.is_urgent_sale and self.original_price_thb and self.price_sale_thb:
                # Показываем скидку если это срочная продажа
                discount_percent = ((self.original_price_thb - self.price_sale_thb) / self.original_price_thb) * 100
                if discount_percent > 0:
                    price_str += f" (скидка {discount_percent:.0f}%)"
            return price_str
        elif self.deal_type == 'rent' and self.price_rent_monthly:
            return f"${self.price_rent_monthly:,.0f}/мес"
        return "Цена по запросу"
    
    @property
    def total_area(self):
        """Alias для совместимости с SEOTemplate"""
        return self.area_total
    
    def has_custom_seo(self, language_code='ru'):
        """Проверить, есть ли кастомные SEO поля для языка"""
        title_field = f'custom_title_{language_code}'
        return bool(getattr(self, title_field, ''))
    
    def get_custom_seo(self, language_code='ru'):
        """Получить кастомные SEO данные"""
        return {
            'title': getattr(self, f'custom_title_{language_code}', ''),
            'description': getattr(self, f'custom_description_{language_code}', ''),
            'keywords': getattr(self, f'custom_keywords_{language_code}', ''),
        }
    
    def get_seo_template(self):
        """Найти подходящий SEO шаблон для этого объекта"""
        from apps.core.models import SEOTemplate
        
        # Ищем точное совпадение по типу недвижимости и типу сделки
        template = SEOTemplate.objects.filter(
            template_type='property_detail',
            property_type=self.property_type.name,
            deal_type=self.deal_type,
            is_active=True
        ).order_by('priority').first()
        
        # Если не найден, ищем по типу недвижимости без учета типа сделки
        if not template:
            template = SEOTemplate.objects.filter(
                template_type='property_detail',
                property_type=self.property_type.name,
                deal_type='',
                is_active=True
            ).order_by('priority').first()
        
        # Если не найден, ищем общий шаблон
        if not template:
            template = SEOTemplate.objects.filter(
                template_type='property_detail',
                property_type='',
                is_active=True
            ).order_by('priority').first()
        
        return template
    
    def generate_auto_seo(self, language_code='ru'):
        """Автоматическая генерация SEO данных как fallback"""
        # Получаем переведённые значения
        type_name = self._get_translated_type_name(language_code)
        district_name = self._get_translated_district_name(language_code)
        deal_type_name = self._get_translated_deal_type(language_code)
        price_str = self.price_display
        
        # Переведённые статические тексты
        static_texts = {
            'ru': {
                'in_preposition': 'в',
                'real_estate': 'недвижимость пхукет',
                'default_location': 'Пхукет'
            },
            'en': {
                'in_preposition': 'in',
                'real_estate': 'phuket real estate',
                'default_location': 'Phuket'
            },
            'th': {
                'in_preposition': 'ใน',
                'real_estate': 'อสังหาริมทรัพย์ภูเก็ต',
                'default_location': 'ภูเก็ต'
            }
        }
        
        texts = static_texts.get(language_code, static_texts['ru'])
        in_prep = texts['in_preposition']
        real_estate = texts['real_estate']
        
        # Генерируем SEO данные
        title = f"{self.title} - {type_name} {in_prep} {district_name}"
        
        description_parts = [
            f"{deal_type_name} {type_name} {in_prep} {district_name}",
            price_str,
            self.short_description or ''
        ]
        description = '. '.join(filter(None, description_parts)).strip()
        
        keywords = f"{type_name}, {district_name}, {real_estate}, {deal_type_name}"
        
        return {
            'title': title,
            'description': description,
            'keywords': keywords,
        }
    
    def _get_translated_type_name(self, language_code='ru'):
        """Получить переведённое название типа недвижимости"""
        if not self.property_type:
            defaults = {
                'ru': 'недвижимость',
                'en': 'real estate',
                'th': 'อสังหาริมทรัพย์'
            }
            return defaults.get(language_code, defaults['ru'])
        
        # Используем переведённое поле из modeltranslation
        field_name = f'name_display_{language_code}' if language_code != 'ru' else 'name_display'
        translated_name = getattr(self.property_type, field_name, None)
        
        # Fallback на русский язык
        if not translated_name:
            translated_name = self.property_type.name_display
            
        return translated_name or 'недвижимость'
    
    def _get_translated_district_name(self, language_code='ru'):
        """Получить переведённое название района"""
        if not self.district:
            defaults = {
                'ru': 'Пхукет',
                'en': 'Phuket',
                'th': 'ภูเก็ต'
            }
            return defaults.get(language_code, defaults['ru'])
        
        # Используем переведённое поле из modeltranslation
        field_name = f'name_{language_code}' if language_code != 'ru' else 'name'
        translated_name = getattr(self.district, field_name, None)
        
        # Fallback на русский язык
        if not translated_name:
            translated_name = self.district.name
            
        return translated_name or 'Пхукет'
    
    def _get_translated_deal_type(self, language_code='ru'):
        """Получить переведённое название типа сделки"""
        deal_type_translations = {
            'sale': {
                'ru': 'Продажа',
                'en': 'Sale',
                'th': 'ขาย'
            },
            'rent': {
                'ru': 'Аренда',
                'en': 'Rent',
                'th': 'เช่า'
            },
            'both': {
                'ru': 'Продажа/Аренда',
                'en': 'Sale/Rent',
                'th': 'ขาย/เช่า'
            }
        }
        
        deal_translations = deal_type_translations.get(self.deal_type, {})
        return deal_translations.get(language_code, deal_translations.get('ru', self.deal_type))
    
    def get_seo_data(self, language_code='ru'):
        """Получить финальные SEO данные с учетом приоритетов"""
        # 1. Проверяем кастомные SEO поля
        if self.has_custom_seo(language_code):
            return self.get_custom_seo(language_code)
        
        # 2. Ищем подходящий шаблон
        template = self.get_seo_template()
        if template:
            return template.generate_seo_for_property(self, language_code)
        
        # 3. Fallback - автогенерация
        return self.generate_auto_seo(language_code)


class PropertyImage(models.Model):
    """Изображения недвижимости"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('Изображение'), upload_to='properties/')
    title = models.CharField(_('Название'), max_length=100, blank=True)
    is_main = models.BooleanField(_('Главное изображение'), default=False)
    order = models.PositiveIntegerField(_('Порядок'), default=0)

    # Автоматическое создание thumbnails
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(300, 200)],
        format='JPEG',
        options={'quality': 80}
    )

    medium = ImageSpecField(
        source='image',
        processors=[ResizeToFit(800, 600)],
        format='JPEG',
        options={'quality': 85}
    )

    class Meta:
        verbose_name = _('Изображение')
        verbose_name_plural = _('Изображения')
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.property.title} - {self.title or 'Image'}"

    def save(self, *args, **kwargs):
        # Автоматически делать первое изображение главным
        if self.is_main:
            PropertyImage.objects.filter(property=self.property).exclude(id=self.id).update(is_main=False)
        elif not PropertyImage.objects.filter(property=self.property, is_main=True).exists():
            self.is_main = True
        super().save(*args, **kwargs)


class PropertyFeature(models.Model):
    """Дополнительные характеристики"""
    name = models.CharField(_('Название'), max_length=100)
    icon = models.CharField(_('Иконка'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Характеристика')
        verbose_name_plural = _('Характеристики')

    def __str__(self):
        return self.name


class PropertyFeatureRelation(models.Model):
    """Связь недвижимости с характеристиками"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='features')
    feature = models.ForeignKey(PropertyFeature, on_delete=models.CASCADE)
    value = models.CharField(_('Значение'), max_length=100, blank=True)

    class Meta:
        unique_together = ['property', 'feature']