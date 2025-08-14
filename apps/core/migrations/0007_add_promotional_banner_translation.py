# Generated manually for promotional banner translation migration

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_service'),
    ]

    operations = [
        migrations.CreateModel(
            name='PromotionalBannerTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language_code', models.CharField(choices=[('ru', 'Русский'), ('en', 'English'), ('th', 'ไทย')], max_length=2, verbose_name='Язык')),
                ('title', models.CharField(max_length=200, verbose_name='Заголовок')),
                ('description', models.TextField(max_length=500, verbose_name='Описание')),
                ('discount_text', models.CharField(blank=True, help_text='Например: "Скидка 20%" или "Ограниченное предложение"', max_length=100, verbose_name='Текст скидки/предложения')),
                ('button_text', models.CharField(blank=True, help_text='Например: "Узнать подробнее" или "Связаться с нами"', max_length=50, verbose_name='Текст кнопки')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('banner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='translations', to='core.promotionalbanner')),
            ],
            options={
                'verbose_name': 'Перевод баннера',
                'verbose_name_plural': 'Переводы баннеров',
                'ordering': ['language_code'],
                'unique_together': {('banner', 'language_code')},
            },
        ),
    ]