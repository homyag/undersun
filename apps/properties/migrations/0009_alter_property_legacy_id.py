# Generated by Django 5.0.6 on 2025-07-08 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0008_alter_property_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='property',
            name='legacy_id',
            field=models.CharField(blank=True, help_text='Идентификатор из старой Joomla системы (например: VS82)', max_length=20, null=True, verbose_name='ID старой системы'),
        ),
    ]
