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