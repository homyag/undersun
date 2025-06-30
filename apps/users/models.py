from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    """Профиль пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(_('Телефон'), max_length=20, blank=True)
    country = models.CharField(_('Страна'), max_length=50, blank=True)
    language = models.CharField(_('Язык'), max_length=2, choices=[('ru', 'Русский'), ('en', 'English'), ('th', 'ไทย')],
                                default='ru')

    # Уведомления
    email_notifications = models.BooleanField(_('Email уведомления'), default=True)

    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)

    class Meta:
        verbose_name = _('Профиль пользователя')
        verbose_name_plural = _('Профили пользователей')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class PropertyFavorite(models.Model):
    """Избранная недвижимость пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE)
    created_at = models.DateTimeField(_('Добавлено'), auto_now_add=True)

    class Meta:
        unique_together = ['user', 'property']
        verbose_name = _('Избранное')
        verbose_name_plural = _('Избранное')


class PropertyInquiry(models.Model):
    """Запросы по недвижимости"""
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='inquiries')
    name = models.CharField(_('Имя'), max_length=100)
    email = models.EmailField(_('Email'))
    phone = models.CharField(_('Телефон'), max_length=20, blank=True)
    message = models.TextField(_('Сообщение'))

    # Для интеграции с AmoCRM
    amo_lead_id = models.IntegerField(_('ID лида в AmoCRM'), blank=True, null=True)

    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    is_processed = models.BooleanField(_('Обработан'), default=False)

    class Meta:
        verbose_name = _('Запрос')
        verbose_name_plural = _('Запросы')
        ordering = ['-created_at']

    def __str__(self):
        return f"Запрос от {self.name} по {self.property.title}"