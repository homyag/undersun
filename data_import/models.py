from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import json


class ImportFile(models.Model):
    """Модель для хранения загруженных файлов импорта"""
    STATUS_CHOICES = [
        ('uploaded', _('Загружен')),
        ('processing', _('Обрабатывается')),
        ('completed', _('Завершен')),
        ('failed', _('Ошибка')),
    ]
    
    IMPORT_TYPES = [
        ('property_update', _('Обновление недвижимости')),
        ('property_create', _('Создание недвижимости')),
        ('price_update', _('Обновление цен')),
    ]
    
    # Основная информация
    name = models.CharField(_('Название файла'), max_length=255)
    file = models.FileField(_('Файл'), upload_to='imports/')
    import_type = models.CharField(_('Тип импорта'), max_length=20, choices=IMPORT_TYPES)
    status = models.CharField(_('Статус'), max_length=20, choices=STATUS_CHOICES, default='uploaded')
    
    # Пользователь, загрузивший файл
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Загрузил'))
    
    # Маппинг полей
    mapping = models.ForeignKey('PropertyImportMapping', on_delete=models.SET_NULL, 
                               blank=True, null=True, verbose_name=_('Маппинг полей'))
    
    # Статистика
    total_rows = models.PositiveIntegerField(_('Всего строк'), default=0)
    processed_rows = models.PositiveIntegerField(_('Обработано строк'), default=0)
    successful_rows = models.PositiveIntegerField(_('Успешно обработано'), default=0)
    failed_rows = models.PositiveIntegerField(_('Ошибок'), default=0)
    
    # Результаты парсинга
    parsed_data = models.JSONField(_('Распарсенные данные'), blank=True, null=True)
    validation_errors = models.JSONField(_('Ошибки валидации'), blank=True, null=True)
    
    # Временные метки
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    started_at = models.DateTimeField(_('Начато'), blank=True, null=True)
    completed_at = models.DateTimeField(_('Завершено'), blank=True, null=True)
    
    class Meta:
        verbose_name = _('Файл импорта')
        verbose_name_plural = _('Файлы импорта')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    @property
    def success_rate(self):
        """Процент успешно обработанных записей"""
        if self.total_rows == 0:
            return 0
        return round((self.successful_rows / self.total_rows) * 100, 2)
    
    def add_validation_error(self, row_number, field, error_message):
        """Добавить ошибку валидации"""
        if not self.validation_errors:
            self.validation_errors = []
        
        self.validation_errors.append({
            'row': row_number,
            'field': field,
            'error': error_message
        })
        self.save(update_fields=['validation_errors'])


class ImportLog(models.Model):
    """Подробные логи импорта"""
    LOG_LEVELS = [
        ('info', _('Информация')),
        ('warning', _('Предупреждение')),
        ('error', _('Ошибка')),
        ('success', _('Успех')),
    ]
    
    import_file = models.ForeignKey(ImportFile, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(_('Уровень'), max_length=10, choices=LOG_LEVELS)
    message = models.TextField(_('Сообщение'))
    row_number = models.PositiveIntegerField(_('Номер строки'), blank=True, null=True)
    details = models.JSONField(_('Детали'), blank=True, null=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Лог импорта')
        verbose_name_plural = _('Логи импорта')
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_level_display()}: {self.message[:50]}"


class PropertyImportMapping(models.Model):
    """Маппинг полей Excel на поля модели Property"""
    
    # Основные поля недвижимости
    PROPERTY_FIELDS = [
        ('legacy_id', _('ID объекта (legacy_id)')),
        ('title', _('Название (title)')),
        ('price_sale_usd', _('Цена продажи USD (price_sale_usd)')),
        ('price_sale_thb', _('Цена продажи THB (price_sale_thb)')),
        ('price_sale_rub', _('Цена продажи RUB (price_sale_rub)')),
        ('price_rent_monthly', _('Аренда USD (price_rent_monthly)')),
        ('price_rent_monthly_thb', _('Аренда THB (price_rent_monthly_thb)')),
        ('price_rent_monthly_rub', _('Аренда RUB (price_rent_monthly_rub)')),
        ('area_total', _('Общая площадь (area_total)')),
        ('area_living', _('Жилая площадь (area_living)')),
        ('area_land', _('Площадь участка (area_land)')),
        ('bedrooms', _('Спальни (bedrooms)')),
        ('bathrooms', _('Ванные (bathrooms)')),
        ('floor', _('Этаж (floor)')),
        ('floors_total', _('Всего этажей (floors_total)')),
        ('status', _('Статус (status)')),
        ('deal_type', _('Тип сделки (deal_type)')),
        ('latitude', _('Широта (latitude)')),
        ('longitude', _('Долгота (longitude)')),
        ('furnished', _('С мебелью (furnished)')),
        ('pool', _('Бассейн (pool)')),
        ('parking', _('Парковка (parking)')),
        ('security', _('Охрана (security)')),
        ('gym', _('Спортзал (gym)')),
        ('year_built', _('Год постройки (year_built)')),
        ('distance_to_beach', _('До пляжа (distance_to_beach)')),
        ('distance_to_airport', _('До аэропорта (distance_to_airport)')),
        ('distance_to_school', _('До школы (distance_to_school)')),
        ('double_beds', _('Двуспальные кровати (double_beds)')),
        ('single_beds', _('Односпальные кровати (single_beds)')),
        ('sofa_beds', _('Диван-кровати (sofa_beds)')),
        ('pool_area', _('Площадь бассейна (pool_area)')),
        ('is_urgent_sale', _('Срочная продажа (is_urgent_sale)')),
        ('urgency_note', _('Примечание срочности (urgency_note)')),
        ('architectural_style', _('Архитектурный стиль (architectural_style)')),
        ('material_type', _('Материалы (material_type)')),
        ('suitable_for', _('Подходит для (suitable_for)')),
    ]
    
    name = models.CharField(_('Название маппинга'), max_length=100)
    description = models.TextField(_('Описание'), blank=True)
    is_default = models.BooleanField(_('По умолчанию'), default=False)
    
    # JSON структура маппинга: {"excel_column": "property_field"}
    # Например: {"A": "legacy_id", "B": "title", "C": "price_sale_usd"}
    field_mapping = models.JSONField(_('Маппинг полей'), default=dict)
    
    # Настройки обработки
    header_row = models.PositiveIntegerField(_('Строка заголовков'), default=1,
                                           help_text=_('Номер строки с заголовками (1-based)'))
    data_start_row = models.PositiveIntegerField(_('Начало данных'), default=2,
                                                help_text=_('Номер первой строки с данными (1-based)'))
    
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('Маппинг импорта')
        verbose_name_plural = _('Маппинги импорта')
        ordering = ['-is_default', 'name']
    
    def __str__(self):
        return f"{self.name} {'(по умолчанию)' if self.is_default else ''}"
    
    def save(self, *args, **kwargs):
        # Если это маппинг по умолчанию, убираем флаг у остальных
        if self.is_default:
            PropertyImportMapping.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_default(cls):
        """Получить маппинг по умолчанию"""
        return cls.objects.filter(is_default=True).first()
    
    def get_mapped_fields(self):
        """Получить список замаппленных полей"""
        return list(self.field_mapping.values()) if self.field_mapping else []
    
    def get_excel_columns(self):
        """Получить список Excel колонок"""
        return list(self.field_mapping.keys()) if self.field_mapping else []
