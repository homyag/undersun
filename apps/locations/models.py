from django.db import models
from django.utils.translation import gettext_lazy as _


class District(models.Model):
    """Районы Пхукета"""
    name = models.CharField(_('Название'), max_length=100)
    slug = models.SlugField(_('URL'), unique=True)
    description = models.TextField(_('Описание'), blank=True)

    class Meta:
        verbose_name = _('Район')
        verbose_name_plural = _('Районы')

    def __str__(self):
        return self.name


class Location(models.Model):
    """Локации внутри районов"""
    name = models.CharField(_('Название'), max_length=100)
    slug = models.SlugField(_('URL'))
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='locations')
    description = models.TextField(_('Описание'), blank=True)

    class Meta:
        verbose_name = _('Локация')
        verbose_name_plural = _('Локации')
        unique_together = ['slug', 'district']

    def __str__(self):
        return f"{self.name}, {self.district.name}"