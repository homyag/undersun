import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('arealisting', '0012_arealistingmediajob_preferred_main_asset_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='arealistingsyncevent', name='kind',
            field=models.CharField(
                choices=[('NEW_UNIT', 'Новое доступное предложение'), ('SOLD', 'Предложение продано'),
                         ('UNIT_PRICE', 'Цена предложения изменилась'),
                         ('UNIT_FIELDS', 'Характеристики предложения изменились'),
                         ('CARD_PRICE', 'Цена карточки обновлена'),
                         ('PRICE_SKIPPED', 'Цена карточки не обновлена'),
                         ('PRICE_REVIEW', 'Цена ждёт подтверждения'),
                         ('ACTIVE_NO_UNITS', 'Активная карточка без доступных предложений')],
                db_index=True, max_length=20, verbose_name='Событие',
            ),
        ),
        migrations.AddField(
            model_name='arealistingsyncevent', name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True, db_index=True, verbose_name='Проверено'),
        ),
        migrations.AddField(
            model_name='arealistingsyncevent', name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='arealisting_reviewed_events',
                                    to=settings.AUTH_USER_MODEL, verbose_name='Проверил'),
        ),
    ]
