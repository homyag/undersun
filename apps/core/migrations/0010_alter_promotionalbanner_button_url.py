# Generated by Django 5.0.6 on 2025-07-07 20:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_remove_old_promotional_banner_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='promotionalbanner',
            name='button_url',
            field=models.CharField(blank=True, help_text='URL или имя Django URL pattern. Поддерживает: "/property/" (статический URL), "property_list" (имя URL), "https://example.com" (внешний URL)', max_length=200, verbose_name='Ссылка кнопки'),
        ),
    ]
