from django.db import migrations, models


def set_language_code(apps, schema_editor):
    PromotionalBanner = apps.get_model('core', 'PromotionalBanner')
    PromotionalBanner.objects.filter(language_code__isnull=True).update(language_code='ru')


def unset_language_code(apps, schema_editor):
    PromotionalBanner = apps.get_model('core', 'PromotionalBanner')
    PromotionalBanner.objects.update(language_code='ru')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_alter_promotionalbanner_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='promotionalbanner',
            name='language_code',
            field=models.CharField(choices=[('ru', 'Русский'), ('en', 'Английский'), ('th', 'Тайский')], default='ru', help_text='Создавайте отдельные баннеры для каждого языка (RU / EN / TH).', max_length=2, verbose_name='Язык'),
        ),
        migrations.AlterField(
            model_name='promotionalbanner',
            name='desktop_image',
            field=models.ImageField(blank=True, help_text='Рекомендуемый размер: 2400×150 px. Держите ключевой контент в центральной зоне, края могут обрезаться.', upload_to='promotional_banners/', verbose_name='Изображение для десктопа'),
        ),
        migrations.AlterField(
            model_name='promotionalbanner',
            name='tablet_image',
            field=models.ImageField(blank=True, help_text='Рекомендуемый размер: 1536×150 px. Фокусируйте основной контент в центре кадра.', upload_to='promotional_banners/', verbose_name='Изображение для планшета'),
        ),
        migrations.AlterField(
            model_name='promotionalbanner',
            name='mobile_image',
            field=models.ImageField(blank=True, help_text='Рекомендуемый размер: 828×150 px. Располагайте текст и логотип внутри центральных 60% ширины.', upload_to='promotional_banners/', verbose_name='Изображение для мобильных устройств'),
        ),
        migrations.RunPython(set_language_code, unset_language_code),
    ]
