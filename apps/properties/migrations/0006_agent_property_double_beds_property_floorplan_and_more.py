# Generated by Django 5.0.6 on 2025-07-08 13:57

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0005_property_price_rent_monthly_rub_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Имя')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='Телефон')),
                ('whatsapp', models.CharField(blank=True, max_length=20, verbose_name='WhatsApp')),
                ('telegram', models.CharField(blank=True, max_length=50, verbose_name='Telegram')),
                ('bio', models.TextField(blank=True, verbose_name='Биография')),
                ('photo', models.ImageField(blank=True, upload_to='agents/', verbose_name='Фото')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('legacy_id', models.CharField(blank=True, help_text='Идентификатор из старой Joomla системы', max_length=20, unique=True, verbose_name='ID из Joomla')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Агент',
                'verbose_name_plural': 'Агенты',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='property',
            name='double_beds',
            field=models.PositiveIntegerField(blank=True, help_text='Количество двуспальных кроватей', null=True, verbose_name='Двуспальные кровати'),
        ),
        migrations.AddField(
            model_name='property',
            name='floorplan',
            field=models.ImageField(blank=True, help_text='План планировки этажей', upload_to='properties/floorplans/', verbose_name='План этажа'),
        ),
        migrations.AddField(
            model_name='property',
            name='intro_image',
            field=models.ImageField(blank=True, help_text='Дополнительное изображение для анонса', upload_to='properties/intro/', verbose_name='Интро изображение'),
        ),
        migrations.AddField(
            model_name='property',
            name='single_beds',
            field=models.PositiveIntegerField(blank=True, help_text='Количество односпальных кроватей', null=True, verbose_name='Односпальные кровати'),
        ),
        migrations.AddField(
            model_name='property',
            name='sofa_beds',
            field=models.PositiveIntegerField(blank=True, help_text='Количество диван-кроватей', null=True, verbose_name='Диван-кровати'),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='alt_text',
            field=models.CharField(blank=True, help_text='Альтернативный текст для SEO и доступности', max_length=200, verbose_name='Alt текст'),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='image_type',
            field=models.CharField(choices=[('main', 'Основная галерея'), ('intro', 'Интро изображение'), ('floorplan', 'План этажа'), ('teaser', 'Тизер')], default='main', help_text='Тип изображения для категоризации', max_length=20, verbose_name='Тип изображения'),
        ),
        migrations.AddField(
            model_name='property',
            name='agent',
            field=models.ForeignKey(blank=True, help_text='Ответственный агент', null=True, on_delete=django.db.models.deletion.SET_NULL, to='properties.agent', verbose_name='Агент по недвижимости'),
        ),
    ]
