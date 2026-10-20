from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class ArealistingSourceModel(models.Model):
    """Common metadata retained for replayable AREALISTING source records."""

    raw_payload = models.JSONField(_('Исходный JSON'), default=dict, blank=True)
    remote_updated_at = models.DateTimeField(
        _('Изменено в AREALISTING'),
        blank=True,
        null=True,
        db_index=True,
    )
    last_seen_at = models.DateTimeField(
        _('Последний раз получено'),
        blank=True,
        null=True,
        db_index=True,
    )
    synced_at = models.DateTimeField(_('Синхронизировано'), auto_now=True)
    is_deleted = models.BooleanField(_('Удалено в источнике'), default=False, db_index=True)

    class Meta:
        abstract = True


class ArealistingProject(ArealistingSourceModel):
    class ProjectType(models.TextChoices):
        CONDO = 'CONDO', _('Кондоминиум')
        VILLA = 'VILLA', _('Вилла')
        TOWNHOUSE = 'TOWNHOUSE', _('Таунхаус')
        HOUSE = 'HOUSE', _('Таунхаус')

    external_id = models.CharField(_('External ID'), max_length=128, unique=True)
    name_en = models.CharField(_('Название (EN)'), max_length=255, blank=True)
    name_ru = models.CharField(_('Название (RU)'), max_length=255, blank=True)
    description_en = models.TextField(_('Описание (EN)'), blank=True)
    description_ru = models.TextField(_('Описание (RU)'), blank=True)
    developer_name = models.CharField(_('Застройщик'), max_length=255, blank=True)
    project_type = models.CharField(
        _('Тип проекта'),
        max_length=20,
        choices=ProjectType.choices,
        blank=True,
        db_index=True,
    )
    construction_status = models.CharField(
        _('Статус строительства'),
        max_length=40,
        blank=True,
        db_index=True,
    )
    completion_date = models.DateTimeField(_('Дата завершения'), blank=True, null=True)
    freehold_available = models.BooleanField(_('Freehold доступен'), default=False)
    leasehold_available = models.BooleanField(_('Leasehold доступен'), default=False)
    maintenance_fee = models.DecimalField(
        _('Плата за обслуживание'),
        max_digits=18,
        decimal_places=4,
        blank=True,
        null=True,
    )
    maintenance_fee_mode = models.CharField(
        _('Режим платы за обслуживание'),
        max_length=40,
        blank=True,
    )
    sinking_fund = models.DecimalField(
        _('Sinking fund'),
        max_digits=18,
        decimal_places=4,
        blank=True,
        null=True,
    )
    sinking_fund_mode = models.CharField(_('Режим sinking fund'), max_length=40, blank=True)
    latitude = models.DecimalField(
        _('Широта'),
        max_digits=18,
        decimal_places=12,
        blank=True,
        null=True,
    )
    longitude = models.DecimalField(
        _('Долгота'),
        max_digits=18,
        decimal_places=12,
        blank=True,
        null=True,
    )
    districts = models.JSONField(_('География источника'), default=list, blank=True)
    amenities = models.JSONField(_('Удобства источника'), default=list, blank=True)
    gallery = models.JSONField(_('Галерея проекта'), default=list, blank=True)
    documents = models.JSONField(_('Документы проекта'), default=list, blank=True)

    class Meta:
        verbose_name = _('AREALISTING проект')
        verbose_name_plural = _('AREALISTING проекты')
        ordering = ('name_en', 'external_id')
        indexes = [
            models.Index(fields=('is_deleted', 'project_type')),
            models.Index(fields=('developer_name',)),
        ]

    def __str__(self):
        return self.name_en or self.name_ru or self.external_id


class ArealistingManualProperty(models.Model):
    """An explicit decision to maintain an Undersun card without the feed."""

    property = models.OneToOneField(
        'properties.Property', on_delete=models.CASCADE,
        related_name='arealisting_manual', verbose_name=_('Объект Undersun'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Объект на ручном ведении')
        verbose_name_plural = _('Объекты на ручном ведении')


class ArealistingSkippedUnit(models.Model):
    unit = models.OneToOneField(
        'ArealistingUnit',
        on_delete=models.CASCADE,
        related_name='skip_decision',
        verbose_name=_('Предложение AREALISTING'),
    )
    skipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='arealisting_skipped_units',
        verbose_name=_('Пропустил'),
    )
    reason = models.CharField(_('Причина'), max_length=255, blank=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)

    class Meta:
        verbose_name = _('Пропущенное предложение AREALISTING')
        verbose_name_plural = _('Пропущенные предложения AREALISTING')
        ordering = ('-created_at',)

    def __str__(self):
        return str(self.unit)


class ArealistingListingGroup(models.Model):
    class CatalogOrigin(models.TextChoices):
        EXISTING = 'EXISTING', _('Существующая карточка Undersun')
        AREALISTING_DRAFT = 'AREALISTING_DRAFT', _('Черновик из AREALISTING')

    class GroupingMode(models.TextChoices):
        PROJECT = 'PROJECT', _('Проект')
        LAYOUT = 'LAYOUT', _('Планировка')
        UNIT = 'UNIT', _('Юнит')

    project = models.ForeignKey(
        ArealistingProject,
        on_delete=models.CASCADE,
        related_name='listing_groups',
        verbose_name=_('Проект'),
    )
    property = models.OneToOneField(
        'properties.Property',
        on_delete=models.SET_NULL,
        related_name='arealisting_group',
        verbose_name=_('Объект Undersun'),
        blank=True,
        null=True,
    )
    grouping_mode = models.CharField(
        _('Режим группировки'),
        max_length=16,
        choices=GroupingMode.choices,
        default=GroupingMode.PROJECT,
    )
    name = models.CharField(_('Название группы'), max_length=255, blank=True)
    currency = models.CharField(_('Валюта'), max_length=3, blank=True)
    min_price = models.DecimalField(
        _('Минимальная цена'), max_digits=18, decimal_places=2, blank=True, null=True
    )
    max_price = models.DecimalField(
        _('Максимальная цена'), max_digits=18, decimal_places=2, blank=True, null=True
    )
    min_area_sqm = models.DecimalField(
        _('Минимальная площадь'), max_digits=12, decimal_places=2, blank=True, null=True
    )
    max_area_sqm = models.DecimalField(
        _('Максимальная площадь'), max_digits=12, decimal_places=2, blank=True, null=True
    )
    available_units_count = models.PositiveIntegerField(_('Доступных юнитов'), default=0)
    is_ready_for_publication = models.BooleanField(_('Готово к публикации'), default=False)
    is_active = models.BooleanField(_('Активная группа'), default=True)
    catalog_origin = models.CharField(
        _('Происхождение карточки'),
        max_length=24,
        choices=CatalogOrigin.choices,
        default=CatalogOrigin.EXISTING,
        db_index=True,
    )
    source_owned_fields = models.JSONField(
        _('Поля под управлением AREALISTING'),
        default=list,
        blank=True,
    )
    locked_fields = models.JSONField(_('Заблокированные поля'), default=list, blank=True)
    excluded_media_source_keys = models.JSONField(
        _('Исключённые фото AREALISTING'), default=list, blank=True,
        help_text=_('Эти исходные материалы не импортируются в карточку при следующих запусках.'),
    )
    validation_errors = models.JSONField(_('Ошибки проверки'), default=list, blank=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('AREALISTING группа публикации')
        verbose_name_plural = _('AREALISTING группы публикации')
        ordering = ('project__name_en', 'grouping_mode', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('project', 'grouping_mode', 'name'),
                name='uniq_arealisting_listing_group',
            )
        ]

    def __str__(self):
        suffix = self.name or self.get_grouping_mode_display()
        return f'{self.project} — {suffix}'


class ArealistingUnit(ArealistingSourceModel):
    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', _('Доступен')
        SOLD = 'SOLD', _('Продан')

    external_id = models.CharField(_('External ID'), max_length=128, unique=True)
    project = models.ForeignKey(
        ArealistingProject,
        on_delete=models.CASCADE,
        related_name='units',
        verbose_name=_('Проект'),
    )
    listing_group = models.ForeignKey(
        ArealistingListingGroup,
        on_delete=models.SET_NULL,
        related_name='units',
        verbose_name=_('Группа публикации'),
        blank=True,
        null=True,
    )
    unit_number = models.CharField(_('Номер юнита'), max_length=100, blank=True)
    bedrooms = models.PositiveIntegerField(_('Спальни'), blank=True, null=True)
    bathrooms = models.DecimalField(
        _('Ванные'), max_digits=6, decimal_places=2, blank=True, null=True
    )
    floor = models.IntegerField(_('Этаж'), blank=True, null=True)
    internal_area_sqm = models.DecimalField(
        _('Внутренняя площадь, м²'), max_digits=12, decimal_places=2, blank=True, null=True
    )
    plot_size_sqm = models.DecimalField(
        _('Площадь участка, м²'), max_digits=14, decimal_places=2, blank=True, null=True
    )
    sea_view = models.BooleanField(_('Вид на море'), blank=True, null=True)
    availability_status = models.CharField(
        _('Доступность'),
        max_length=24,
        choices=AvailabilityStatus.choices,
        blank=True,
        db_index=True,
    )
    property_type = models.CharField(_('Тип недвижимости'), max_length=20, blank=True)
    price = models.DecimalField(_('Цена'), max_digits=18, decimal_places=2, blank=True, null=True)
    currency = models.CharField(_('Валюта'), max_length=3, blank=True, db_index=True)
    price_per_sqm = models.DecimalField(
        _('Цена за м²'), max_digits=18, decimal_places=2, blank=True, null=True
    )
    maintenance_fee = models.DecimalField(
        _('Плата за обслуживание'),
        max_digits=18,
        decimal_places=4,
        blank=True,
        null=True,
    )
    maintenance_fee_mode = models.CharField(
        _('Режим платы за обслуживание'), max_length=40, blank=True
    )
    sinking_fund = models.DecimalField(
        _('Sinking fund'), max_digits=18, decimal_places=4, blank=True, null=True
    )
    sinking_fund_mode = models.CharField(_('Режим sinking fund'), max_length=40, blank=True)
    furnishing = models.JSONField(_('Варианты меблировки'), default=list, blank=True)
    gallery = models.JSONField(_('Галерея юнита'), default=list, blank=True)
    sync_enabled = models.BooleanField(_('Синхронизация включена'), default=True)

    class Meta:
        verbose_name = _('AREALISTING юнит')
        verbose_name_plural = _('AREALISTING юниты')
        ordering = ('project__name_en', 'unit_number', 'external_id')
        indexes = [
            models.Index(fields=('project', 'availability_status', 'is_deleted')),
            models.Index(fields=('listing_group', 'availability_status')),
        ]

    def __str__(self):
        number = self.unit_number or self.external_id
        return f'{self.project} — {number}'


class ArealistingPaymentPlan(ArealistingSourceModel):
    external_id = models.CharField(_('External ID'), max_length=128, unique=True)
    project = models.ForeignKey(
        ArealistingProject,
        on_delete=models.CASCADE,
        related_name='payment_plans',
        verbose_name=_('Проект'),
    )
    name = models.CharField(_('Название'), max_length=255, blank=True)
    description = models.TextField(_('Описание'), blank=True)
    items = models.JSONField(_('Этапы оплаты'), default=list, blank=True)

    class Meta:
        verbose_name = _('AREALISTING план оплаты')
        verbose_name_plural = _('AREALISTING планы оплаты')
        ordering = ('project__name_en', 'name', 'external_id')

    def __str__(self):
        return self.name or self.external_id


class ArealistingLocationMapping(ArealistingSourceModel):
    class MappingMode(models.TextChoices):
        UNMAPPED = 'UNMAPPED', _('Не сопоставлено')
        DISTRICT = 'DISTRICT', _('Район')
        LOCATION = 'LOCATION', _('Локация')
        IGNORE = 'IGNORE', _('Игнорировать')

    external_id = models.CharField(_('External ID'), max_length=128, unique=True)
    source_name = models.CharField(_('Название в AREALISTING'), max_length=255, blank=True)
    source_type = models.CharField(_('Тип в AREALISTING'), max_length=40, blank=True)
    parent_external_id = models.CharField(_('Parent external ID'), max_length=128, blank=True)
    description_en = models.TextField(_('Описание (EN)'), blank=True)
    description_ru = models.TextField(_('Описание (RU)'), blank=True)
    gallery = models.JSONField(_('Галерея локации'), default=list, blank=True)
    mapping_mode = models.CharField(
        _('Режим сопоставления'),
        max_length=16,
        choices=MappingMode.choices,
        default=MappingMode.UNMAPPED,
        db_index=True,
    )
    district = models.ForeignKey(
        'locations.District',
        on_delete=models.PROTECT,
        related_name='arealisting_mappings',
        verbose_name=_('Район Undersun'),
        blank=True,
        null=True,
    )
    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.PROTECT,
        related_name='arealisting_mappings',
        verbose_name=_('Локация Undersun'),
        blank=True,
        null=True,
    )
    is_confirmed = models.BooleanField(_('Подтверждено'), default=False, db_index=True)

    class Meta:
        verbose_name = _('AREALISTING сопоставление локации')
        verbose_name_plural = _('AREALISTING сопоставления локаций')
        ordering = ('is_confirmed', 'source_name', 'external_id')

    def clean(self):
        super().clean()
        errors = {}
        if self.mapping_mode == self.MappingMode.DISTRICT and not self.district_id:
            errors['district'] = _('Для режима «Район» выберите район Undersun.')
        if self.mapping_mode == self.MappingMode.LOCATION and not self.location_id:
            errors['location'] = _('Для режима «Локация» выберите локацию Undersun.')
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.mapping_mode == self.MappingMode.LOCATION and self.location_id:
            self.district = self.location.district
        elif self.mapping_mode == self.MappingMode.DISTRICT:
            self.location = None
        else:
            self.district = None
            self.location = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.source_name or self.external_id


class ArealistingAsset(models.Model):
    class AssetType(models.TextChoices):
        PROJECT_GALLERY = 'PROJECT_GALLERY', _('Галерея проекта')
        UNIT_GALLERY = 'UNIT_GALLERY', _('Галерея юнита')
        FLOOR_PLAN = 'FLOOR_PLAN', _('Планировка')
        MASTER_PLAN = 'MASTER_PLAN', _('Генеральный план')
        PHOTOS_RENDERS = 'PHOTOS_RENDERS', _('Фотографии и рендеры')
        PRESENTATION = 'PRESENTATION', _('Презентация')
        DOCUMENT = 'DOCUMENT', _('Документ')
        PRICE_LIST = 'PRICE_LIST', _('Прайс-лист')
        OTHER = 'OTHER', _('Другое')

    source_key = models.CharField(_('Source key'), max_length=64, unique=True)
    project = models.ForeignKey(
        ArealistingProject,
        on_delete=models.CASCADE,
        related_name='assets',
        verbose_name=_('Проект'),
        blank=True,
        null=True,
    )
    unit = models.ForeignKey(
        ArealistingUnit,
        on_delete=models.CASCADE,
        related_name='assets',
        verbose_name=_('Юнит'),
        blank=True,
        null=True,
    )
    property_image = models.OneToOneField(
        'properties.PropertyImage',
        on_delete=models.SET_NULL,
        related_name='arealisting_asset',
        verbose_name=_('Изображение объекта'),
        blank=True,
        null=True,
    )
    file = models.FileField(_('Локальный файл'), upload_to='arealisting/assets/%Y/%m/', blank=True)
    source_url = models.TextField(_('Исходный URL'))
    asset_type = models.CharField(
        _('Тип'), max_length=24, choices=AssetType.choices, default=AssetType.OTHER
    )
    position = models.PositiveIntegerField(_('Порядок'), default=0)
    checksum = models.CharField(_('Checksum'), max_length=128, blank=True)
    downloaded_at = models.DateTimeField(_('Загружено'), blank=True, null=True)
    last_error = models.TextField(_('Последняя ошибка'), blank=True)
    is_active = models.BooleanField(_('Активно'), default=True, db_index=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('AREALISTING asset')
        verbose_name_plural = _('AREALISTING assets')
        ordering = ('project__name_en', 'unit__unit_number', 'asset_type', 'position')
        constraints = [
            models.CheckConstraint(
                check=models.Q(project__isnull=False) | models.Q(unit__isnull=False),
                name='arealisting_asset_has_owner',
            )
        ]

    def __str__(self):
        return f'{self.get_asset_type_display()} #{self.position + 1}'


class ArealistingPropertyAsset(models.Model):
    class Role(models.TextChoices):
        GALLERY = 'GALLERY', _('Основная галерея')
        FLOOR_PLAN = 'FLOOR_PLAN', _('Планировка')

    listing_group = models.ForeignKey(
        ArealistingListingGroup,
        on_delete=models.CASCADE,
        related_name='property_assets',
        verbose_name=_('Группа публикации'),
    )
    asset = models.ForeignKey(
        ArealistingAsset,
        on_delete=models.CASCADE,
        related_name='property_links',
        verbose_name=_('Материал AREALISTING'),
    )
    property_image = models.OneToOneField(
        'properties.PropertyImage',
        on_delete=models.SET_NULL,
        related_name='arealisting_property_asset',
        verbose_name=_('Изображение объекта'),
        blank=True,
        null=True,
    )
    role = models.CharField(_('Назначение'), max_length=16, choices=Role.choices)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('AREALISTING изображение карточки')
        verbose_name_plural = _('AREALISTING изображения карточек')
        ordering = ('listing_group', 'role', 'asset__position')
        constraints = [
            models.UniqueConstraint(
                fields=('listing_group', 'asset'),
                name='uniq_arealisting_group_asset',
            )
        ]

    def __str__(self):
        return f'{self.listing_group} — {self.get_role_display()}'


class ArealistingSyncState(models.Model):
    class Status(models.TextChoices):
        IDLE = 'IDLE', _('Ожидает')
        RUNNING = 'RUNNING', _('Выполняется')
        SUCCESS = 'SUCCESS', _('Успешно')
        FAILED = 'FAILED', _('Ошибка')

    key = models.CharField(_('Ключ'), max_length=50, unique=True, default='global')
    status = models.CharField(
        _('Статус'), max_length=16, choices=Status.choices, default=Status.IDLE
    )
    last_successful_sync_at = models.DateTimeField(
        _('Последняя успешная синхронизация'), blank=True, null=True
    )
    current_started_at = models.DateTimeField(_('Текущий запуск начат'), blank=True, null=True)
    last_error = models.TextField(_('Последняя ошибка'), blank=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('AREALISTING состояние синхронизации')
        verbose_name_plural = _('AREALISTING состояния синхронизации')

    def __str__(self):
        return f'{self.key}: {self.get_status_display()}'


class ArealistingSyncRun(models.Model):
    class Mode(models.TextChoices):
        FULL = 'FULL', _('Полная')
        INCREMENTAL = 'INCREMENTAL', _('Инкрементальная')
        TARGETED = 'TARGETED', _('Выборочная')

    class Status(models.TextChoices):
        RUNNING = 'RUNNING', _('Выполняется')
        SUCCESS = 'SUCCESS', _('Успешно')
        FAILED = 'FAILED', _('Ошибка')
        DRY_RUN = 'DRY_RUN', _('Проверка без записи')

    mode = models.CharField(_('Режим'), max_length=16, choices=Mode.choices)
    status = models.CharField(
        _('Статус'), max_length=16, choices=Status.choices, default=Status.RUNNING
    )
    started_at = models.DateTimeField(_('Начато'), auto_now_add=True)
    finished_at = models.DateTimeField(_('Завершено'), blank=True, null=True)
    since = models.DateTimeField(_('Изменения с'), blank=True, null=True)
    resources = models.JSONField(_('Ресурсы'), default=list, blank=True)
    project_ids = models.JSONField(_('Project IDs'), default=list, blank=True)
    summary = models.JSONField(_('Итог'), default=dict, blank=True)
    error = models.TextField(_('Ошибка'), blank=True)

    class Meta:
        verbose_name = _('AREALISTING запуск синхронизации')
        verbose_name_plural = _('AREALISTING запуски синхронизации')
        ordering = ('-started_at',)

    def __str__(self):
        return f'{self.get_mode_display()} — {self.started_at:%Y-%m-%d %H:%M:%S}'


class ArealistingPropertyChange(models.Model):
    class Kind(models.TextChoices):
        MATCH = 'MATCH', _('Сопоставление')
        DETACH = 'DETACH', _('Отвязка')
        FIELDS = 'FIELDS', _('Характеристики')
        PRICE = 'PRICE', _('Цена')

    property = models.ForeignKey(
        'properties.Property', on_delete=models.CASCADE, related_name='arealisting_changes',
        verbose_name=_('Карточка'),
    )
    project = models.ForeignKey(
        ArealistingProject, on_delete=models.SET_NULL, blank=True, null=True,
        verbose_name=_('Проект'),
    )
    kind = models.CharField(_('Действие'), max_length=12, choices=Kind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        verbose_name=_('Сотрудник'),
    )
    sync_run = models.ForeignKey(
        ArealistingSyncRun, on_delete=models.SET_NULL, blank=True, null=True,
        verbose_name=_('Запуск синхронизации'),
    )
    details = models.JSONField(_('Изменения'), default=dict)
    created_at = models.DateTimeField(_('Дата'), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('AREALISTING изменение карточки')
        verbose_name_plural = _('AREALISTING изменения карточек')
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'{self.get_kind_display()}: #{self.property_id}'


class ArealistingSyncEvent(models.Model):
    class Kind(models.TextChoices):
        NEW_UNIT = 'NEW_UNIT', _('Новое доступное предложение')
        SOLD = 'SOLD', _('Предложение продано')
        UNIT_PRICE = 'UNIT_PRICE', _('Цена предложения изменилась')
        UNIT_FIELDS = 'UNIT_FIELDS', _('Характеристики предложения изменились')
        CARD_PRICE = 'CARD_PRICE', _('Цена карточки обновлена')
        PRICE_SKIPPED = 'PRICE_SKIPPED', _('Цена карточки не обновлена')
        PRICE_REVIEW = 'PRICE_REVIEW', _('Цена ждёт подтверждения')
        ACTIVE_WITHOUT_UNITS = 'ACTIVE_NO_UNITS', _('Активная карточка без доступных предложений')

    run = models.ForeignKey(ArealistingSyncRun, on_delete=models.CASCADE,
                            related_name='events', verbose_name=_('Запуск'))
    kind = models.CharField(_('Событие'), max_length=20, choices=Kind.choices, db_index=True)
    project = models.ForeignKey(ArealistingProject, on_delete=models.SET_NULL,
                                blank=True, null=True, verbose_name=_('Проект'))
    unit = models.ForeignKey(ArealistingUnit, on_delete=models.SET_NULL,
                             blank=True, null=True, verbose_name=_('Предложение'))
    property = models.ForeignKey('properties.Property', on_delete=models.SET_NULL,
                                 blank=True, null=True, verbose_name=_('Карточка'))
    details = models.JSONField(_('Подробности'), default=dict)
    created_at = models.DateTimeField(_('Дата'), auto_now_add=True)
    reviewed_at = models.DateTimeField(_('Проверено'), blank=True, null=True, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='arealisting_reviewed_events', verbose_name=_('Проверил'),
    )

    class Meta:
        verbose_name = _('AREALISTING событие синхронизации')
        verbose_name_plural = _('AREALISTING события синхронизации')
        ordering = ('-created_at', '-pk')
        indexes = [models.Index(fields=('run', 'kind'), name='arealisting_run_kind_idx')]

    def __str__(self):
        return self.get_kind_display()


class ArealistingPriceReview(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Ожидает решения')
        APPROVED = 'APPROVED', _('Подтверждено')
        REJECTED = 'REJECTED', _('Отклонено')
        SUPERSEDED = 'SUPERSEDED', _('Предложение устарело')

    group = models.ForeignKey(ArealistingListingGroup, on_delete=models.SET_NULL,
                              blank=True, null=True, related_name='price_reviews',
                              verbose_name=_('Группа'))
    project = models.ForeignKey(ArealistingProject, on_delete=models.SET_NULL,
                                blank=True, null=True, verbose_name=_('Проект'))
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE,
                                 related_name='arealisting_price_reviews', verbose_name=_('Карточка'))
    sync_run = models.ForeignKey(ArealistingSyncRun, on_delete=models.SET_NULL,
                                 blank=True, null=True, verbose_name=_('Запуск'))
    before = models.JSONField(_('Текущие цены'), default=dict)
    after = models.JSONField(_('Предложенные цены'), default=dict)
    units = models.JSONField(_('Выбранные предложения'), default=list)
    change_percent = models.DecimalField(_('Изменение, %'), max_digits=9, decimal_places=2)
    status = models.CharField(_('Статус'), max_length=12, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    reviewed_at = models.DateTimeField(_('Решение принято'), blank=True, null=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    blank=True, null=True, verbose_name=_('Решение принял'))

    class Meta:
        verbose_name = _('AREALISTING проверка цены')
        verbose_name_plural = _('AREALISTING проверки цен')
        ordering = ('-created_at', '-pk')
        constraints = [models.UniqueConstraint(
            fields=('group',), condition=models.Q(status='PENDING'),
            name='uniq_arealisting_pending_price_review',
        )]

    def __str__(self):
        return f'{self.property} — {self.get_status_display()}'


class ArealistingMediaJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Ожидает')
        RUNNING = 'RUNNING', _('Загружается')
        SUCCESS = 'SUCCESS', _('Завершено')
        PARTIAL = 'PARTIAL', _('Есть ошибки')
        FAILED = 'FAILED', _('Не выполнено')

    group = models.ForeignKey(
        ArealistingListingGroup, on_delete=models.CASCADE,
        related_name='media_jobs', verbose_name=_('Группа'),
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Запустил'),
    )
    status = models.CharField(
        _('Статус'), max_length=12, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    selected_asset_ids = models.JSONField(_('Выбранные фото'), default=list)
    preferred_main_asset_id = models.PositiveBigIntegerField(_('Главное фото из источника'), null=True, blank=True)
    preview_fingerprint = models.CharField(_('Снимок выбора'), max_length=64)
    prune_missing = models.BooleanField(_('Удалять исключённые фото'), default=True)
    total = models.PositiveIntegerField(_('Всего операций'), default=0)
    processed = models.PositiveIntegerField(_('Выполнено операций'), default=0)
    totals = models.JSONField(_('Итог'), default=dict, blank=True)
    results = models.JSONField(_('Результат по фото'), default=list, blank=True)
    error = models.TextField(_('Ошибка задания'), blank=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    started_at = models.DateTimeField(_('Начато'), null=True, blank=True)
    finished_at = models.DateTimeField(_('Завершено'), null=True, blank=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('Импорт фото AREALISTING')
        verbose_name_plural = _('Импорты фото AREALISTING')
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'Импорт фото #{self.pk} — {self.group}'
