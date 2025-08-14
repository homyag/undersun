# Generated manually for removing old promotional banner fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_migrate_promotional_banner_data'),
    ]

    operations = [
        # Удаляем старые поля modeltranslation
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='title',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='title_ru',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='title_en',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='title_th',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='description',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='description_ru',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='description_en',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='description_th',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='discount_text',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='discount_text_ru',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='discount_text_en',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='discount_text_th',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='button_text',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='button_text_ru',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='button_text_en',
        ),
        migrations.RemoveField(
            model_name='promotionalbanner',
            name='button_text_th',
        ),
    ]