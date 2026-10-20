from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('arealisting', '0003_arealistingskippedunit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='arealistingproject',
            name='project_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('CONDO', 'Кондоминиум'),
                    ('VILLA', 'Вилла'),
                    ('TOWNHOUSE', 'Таунхаус'),
                    ('HOUSE', 'Таунхаус'),
                ],
                db_index=True,
                max_length=20,
                verbose_name='Тип проекта',
            ),
        ),
    ]
