# Generated by Django 5.0.6 on 2025-07-08 14:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0007_alter_propertytype_name_display_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='property',
            name='slug',
            field=models.SlugField(max_length=150, unique=True, verbose_name='URL'),
        ),
    ]
