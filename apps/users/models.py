from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class PropertyInquiry(models.Model):
    """Запросы по конкретному объекту недвижимости"""
    INQUIRY_TYPES = (
        ('viewing', _('Запись на просмотр')),
        ('consultation', _('Консультация')),
        ('general', _('Общий вопрос')),
    )

    CONTACT_PREFERENCES = (
        ('phone', _('Телефон')),
        ('whatsapp', _('WhatsApp')),
        ('email', _('Email')),
    )

    CONSULTATION_TOPICS = (
        ('price', _('Уточнение цены')),
        ('investment', _('Инвестиционный потенциал')),
        ('documents', _('Документы и оформление')),
        ('location', _('О районе и инфраструктуре')),
        ('other', _('Другое')),
    )

    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='inquiries', verbose_name=_('Объект'))
    inquiry_type = models.CharField(_('Тип запроса'), max_length=20, choices=INQUIRY_TYPES, default='general')

    # Контактная информация
    name = models.CharField(_('Имя'), max_length=100)
    phone = models.CharField(_('Телефон'), max_length=20)
    email = models.EmailField(_('Email'), blank=True)

    # Детали запроса
    message = models.TextField(_('Сообщение'), blank=True)
    preferred_date = models.DateTimeField(_('Желаемая дата'), blank=True, null=True)
    consultation_topic = models.CharField(_('Тема консультации'), max_length=20, choices=CONSULTATION_TOPICS, blank=True)
    preferred_contact = models.CharField(_('Предпочтительный способ связи'), max_length=20, choices=CONTACT_PREFERENCES, blank=True)

    # Для интеграции с AmoCRM
    amo_lead_id = models.IntegerField(_('ID лида в AmoCRM'), blank=True, null=True)

    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    is_processed = models.BooleanField(_('Обработан'), default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Обработал'))
    processed_at = models.DateTimeField(_('Дата обработки'), blank=True, null=True)

    class Meta:
        verbose_name = _('Запрос по объекту')
        verbose_name_plural = _('Запросы по объектам')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_inquiry_type_display()} от {self.name} - {self.property.title[:50]}"


class QuickConsultationRequest(models.Model):
    """Быстрый запрос консультации (форма с телефоном на главной)"""
    phone = models.CharField(_('Телефон'), max_length=20)

    # Мета данные
    source_page = models.CharField(_('Страница отправки'), max_length=255, blank=True)
    user_agent = models.CharField(_('User Agent'), max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(_('IP адрес'), blank=True, null=True)

    # Для интеграции с AmoCRM
    amo_lead_id = models.IntegerField(_('ID лида в AmoCRM'), blank=True, null=True)

    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    is_processed = models.BooleanField(_('Обработан'), default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Обработал'))

    class Meta:
        verbose_name = _('Быстрая консультация')
        verbose_name_plural = _('Быстрые консультации')
        ordering = ['-created_at']

    def __str__(self):
        return f"Быстрая консультация: {self.phone} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class ContactFormSubmission(models.Model):
    """Общая контактная форма"""
    SUBJECT_CHOICES = (
        ('property', _('Вопрос о недвижимости')),
        ('services', _('Услуги компании')),
        ('partnership', _('Сотрудничество')),
        ('other', _('Другое')),
    )

    name = models.CharField(_('Имя'), max_length=100)
    email = models.EmailField(_('Email'))
    phone = models.CharField(_('Телефон'), max_length=20, blank=True)
    subject = models.CharField(_('Тема'), max_length=50, choices=SUBJECT_CHOICES, default='other')
    message = models.TextField(_('Сообщение'))

    # Для интеграции с AmoCRM
    amo_lead_id = models.IntegerField(_('ID лида в AmoCRM'), blank=True, null=True)

    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    is_processed = models.BooleanField(_('Обработан'), default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Обработал'))

    class Meta:
        verbose_name = _('Обращение с контактной формы')
        verbose_name_plural = _('Обращения с контактной формы')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_subject_display()} от {self.name} ({self.created_at.strftime('%Y-%m-%d')})"


class OfficeVisitRequest(models.Model):
    """Запись на встречу в офисе"""
    name = models.CharField(_('Имя'), max_length=100)
    phone = models.CharField(_('Телефон'), max_length=20)
    preferred_date = models.DateField(_('Желаемая дата'))
    message = models.TextField(_('Дополнительная информация'), blank=True)
    privacy_consent = models.BooleanField(_('Согласие с политикой конфиденциальности'), default=True)

    # Для интеграции с AmoCRM
    amo_lead_id = models.IntegerField(_('ID лида в AmoCRM'), blank=True, null=True)

    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    is_processed = models.BooleanField(_('Обработан'), default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Обработал'))
    visit_confirmed = models.BooleanField(_('Встреча подтверждена'), default=False)
    confirmed_datetime = models.DateTimeField(_('Подтвержденная дата и время'), blank=True, null=True)

    class Meta:
        verbose_name = _('Запись на встречу в офисе')
        verbose_name_plural = _('Записи на встречу в офисе')
        ordering = ['-preferred_date', '-created_at']

    def __str__(self):
        return f"Встреча с {self.name} на {self.preferred_date}"


class FAQQuestion(models.Model):
    """Вопросы из секции FAQ"""
    phone = models.CharField(_('Телефон'), max_length=20)
    question = models.TextField(_('Вопрос'))
    privacy_consent = models.BooleanField(_('Согласие с политикой конфиденциальности'), default=True)

    # Для интеграции с AmoCRM
    amo_lead_id = models.IntegerField(_('ID лида в AmoCRM'), blank=True, null=True)

    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    is_processed = models.BooleanField(_('Обработан'), default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Обработал'))
    answer = models.TextField(_('Ответ'), blank=True)
    answered_at = models.DateTimeField(_('Дата ответа'), blank=True, null=True)

    class Meta:
        verbose_name = _('Вопрос из FAQ')
        verbose_name_plural = _('Вопросы из FAQ')
        ordering = ['-created_at']

    def __str__(self):
        return f"Вопрос от {self.phone}: {self.question[:50]}..."


class NewsletterSubscription(models.Model):
    """Подписка на новости"""
    email = models.EmailField(_('Email'), unique=True)
    is_active = models.BooleanField(_('Активна'), default=True)

    # Мета данные
    source_page = models.CharField(_('Страница подписки'), max_length=255, blank=True)
    subscribed_at = models.DateTimeField(_('Дата подписки'), auto_now_add=True)
    unsubscribed_at = models.DateTimeField(_('Дата отписки'), blank=True, null=True)

    class Meta:
        verbose_name = _('Подписка на новости')
        verbose_name_plural = _('Подписки на новости')
        ordering = ['-subscribed_at']

    def __str__(self):
        status = "Активна" if self.is_active else "Неактивна"
        return f"{self.email} ({status})"