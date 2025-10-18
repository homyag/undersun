from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal


class Currency(models.Model):
    """Модель валюты"""
    code = models.CharField(_('Код валюты'), max_length=3, unique=True, help_text=_('ISO 4217 код (USD, EUR, RUB, THB)'))
    name = models.CharField(_('Название'), max_length=50)
    name_ru = models.CharField(_('Название (RU)'), max_length=50, blank=True)
    name_en = models.CharField(_('Название (EN)'), max_length=50, blank=True)
    name_th = models.CharField(_('Название (TH)'), max_length=50, blank=True)
    symbol = models.CharField(_('Символ'), max_length=10, help_text=_('Символ валюты ($, €, ₽, ฿)'))
    is_active = models.BooleanField(_('Активна'), default=True)
    is_base = models.BooleanField(_('Базовая валюта'), default=False, help_text=_('Базовая валюта для расчетов'))
    decimal_places = models.PositiveSmallIntegerField(_('Знаков после запятой'), default=2)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('Валюта')
        verbose_name_plural = _('Валюты')
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.symbol})"

    def save(self, *args, **kwargs):
        # Убеждаемся, что есть только одна базовая валюта
        if self.is_base:
            Currency.objects.filter(is_base=True).exclude(pk=self.pk).update(is_base=False)
        super().save(*args, **kwargs)


class ExchangeRate(models.Model):
    """Модель курса обмена валют"""
    base_currency = models.ForeignKey(
        Currency, 
        on_delete=models.CASCADE, 
        related_name='base_rates',
        verbose_name=_('Базовая валюта')
    )
    target_currency = models.ForeignKey(
        Currency, 
        on_delete=models.CASCADE, 
        related_name='target_rates',
        verbose_name=_('Целевая валюта')
    )
    rate = models.DecimalField(
        _('Курс'), 
        max_digits=12, 
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))]
    )
    date = models.DateField(_('Дата'))
    source = models.CharField(_('Источник'), max_length=50, default='exchangerate-api.com')
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('Курс обмена')
        verbose_name_plural = _('Курсы обмена')
        unique_together = ['base_currency', 'target_currency', 'date']
        ordering = ['-date', 'base_currency', 'target_currency']

    def __str__(self):
        return f"{self.base_currency.code}/{self.target_currency.code}: {self.rate} ({self.date})"

    @classmethod
    def get_latest_rate(cls, base_currency, target_currency):
        """Получить последний курс между валютами"""
        if base_currency == target_currency:
            return Decimal('1.0')
        
        try:
            rate = cls.objects.filter(
                base_currency=base_currency,
                target_currency=target_currency
            ).latest('date')
            return rate.rate
        except cls.DoesNotExist:
            # Пробуем найти обратный курс
            try:
                reverse_rate = cls.objects.filter(
                    base_currency=target_currency,
                    target_currency=base_currency
                ).latest('date')
                return Decimal('1.0') / reverse_rate.rate
            except cls.DoesNotExist:
                return None

    @classmethod
    def convert_amount(cls, amount, from_currency, to_currency):
        """Конвертировать сумму из одной валюты в другую"""
        if from_currency == to_currency:
            return amount

        rate = cls.get_latest_rate(from_currency, to_currency)
        if rate is None:
            return None

        # Конвертируем amount в Decimal для совместимости с rate
        if isinstance(amount, float):
            amount = Decimal(str(amount))
        elif not isinstance(amount, Decimal):
            amount = Decimal(amount)

        # Возвращаем результат как float для удобства использования
        return float(amount * rate)


class CurrencyPreference(models.Model):
    """Модель предпочтений валюты для языков и пользователей"""
    LANGUAGE_CHOICES = [
        ('ru', _('Русский')),
        ('en', _('English')),
        ('th', _('ไทย')),
    ]

    language = models.CharField(_('Язык'), max_length=2, choices=LANGUAGE_CHOICES, unique=True)
    default_currency = models.ForeignKey(
        Currency, 
        on_delete=models.CASCADE,
        verbose_name=_('Валюта по умолчанию')
    )
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('Предпочтение валюты')
        verbose_name_plural = _('Предпочтения валют')

    def __str__(self):
        return f"{self.get_language_display()}: {self.default_currency.code}"