from django.db import migrations, models


PRICE_FIELDS = ['price_sale_thb', 'price_sale_usd', 'price_sale_rub']


def mark_existing_price_fields(apps, schema_editor):
    ListingGroup = apps.get_model('arealisting', 'ArealistingListingGroup')
    ListingGroup.objects.filter(property__isnull=False).update(
        source_owned_fields=PRICE_FIELDS,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('arealisting', '0004_alter_arealistingproject_project_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='arealistinglistinggroup',
            name='catalog_origin',
            field=models.CharField(
                choices=[
                    ('EXISTING', 'Существующая карточка Undersun'),
                    ('AREALISTING_DRAFT', 'Черновик из AREALISTING'),
                ],
                db_index=True,
                default='EXISTING',
                max_length=24,
                verbose_name='Происхождение карточки',
            ),
        ),
        migrations.AddField(
            model_name='arealistinglistinggroup',
            name='source_owned_fields',
            field=models.JSONField(
                blank=True,
                default=list,
                verbose_name='Поля под управлением AREALISTING',
            ),
        ),
        migrations.RunPython(mark_existing_price_fields, migrations.RunPython.noop),
    ]
