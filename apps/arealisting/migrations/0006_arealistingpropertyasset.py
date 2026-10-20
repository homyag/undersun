import django.db.models.deletion
from django.db import migrations, models


DOCUMENT_TYPES = {
    'FLOOR_PLAN',
    'MASTER_PLAN',
    'PHOTOS_RENDERS',
    'PRESENTATION',
    'DOCUMENT',
    'PRICE_LIST',
}


def classify_existing_documents(apps, schema_editor):
    Project = apps.get_model('arealisting', 'ArealistingProject')
    Asset = apps.get_model('arealisting', 'ArealistingAsset')
    for project in Project.objects.exclude(documents=[]).iterator():
        for document in project.documents or []:
            if not isinstance(document, dict):
                continue
            source_url = document.get('url')
            remote_type = str(document.get('type') or '').upper()
            if source_url and remote_type in DOCUMENT_TYPES:
                Asset.objects.filter(
                    project=project,
                    unit__isnull=True,
                    source_url=source_url,
                ).update(asset_type=remote_type)


class Migration(migrations.Migration):
    dependencies = [
        ('arealisting', '0005_listing_group_field_ownership'),
        ('properties', '0025_hide_rent_and_land_properties'),
    ]

    operations = [
        migrations.AlterField(
            model_name='arealistingasset',
            name='asset_type',
            field=models.CharField(
                choices=[
                    ('PROJECT_GALLERY', 'Галерея проекта'),
                    ('UNIT_GALLERY', 'Галерея юнита'),
                    ('FLOOR_PLAN', 'Планировка'),
                    ('MASTER_PLAN', 'Генеральный план'),
                    ('PHOTOS_RENDERS', 'Фотографии и рендеры'),
                    ('PRESENTATION', 'Презентация'),
                    ('DOCUMENT', 'Документ'),
                    ('PRICE_LIST', 'Прайс-лист'),
                    ('OTHER', 'Другое'),
                ],
                default='OTHER',
                max_length=24,
                verbose_name='Тип',
            ),
        ),
        migrations.RunPython(classify_existing_documents, migrations.RunPython.noop),
        migrations.CreateModel(
            name='ArealistingPropertyAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('GALLERY', 'Основная галерея'), ('FLOOR_PLAN', 'Планировка')], max_length=16, verbose_name='Назначение')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='property_links', to='arealisting.arealistingasset', verbose_name='Материал AREALISTING')),
                ('listing_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='property_assets', to='arealisting.arealistinglistinggroup', verbose_name='Группа публикации')),
                ('property_image', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='arealisting_property_asset', to='properties.propertyimage', verbose_name='Изображение объекта')),
            ],
            options={
                'verbose_name': 'AREALISTING изображение карточки',
                'verbose_name_plural': 'AREALISTING изображения карточек',
                'ordering': ('listing_group', 'role', 'asset__position'),
            },
        ),
        migrations.AddConstraint(
            model_name='arealistingpropertyasset',
            constraint=models.UniqueConstraint(fields=('listing_group', 'asset'), name='uniq_arealisting_group_asset'),
        ),
    ]
