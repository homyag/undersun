from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0022_property_build_status_alter_property_legacy_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertyimage',
            name='frame_type',
            field=models.CharField(
                choices=[
                    ('facade', 'Фасад / экстерьер'),
                    ('living_room', 'Гостиная'),
                    ('bedroom', 'Спальня'),
                    ('bathroom', 'Ванная'),
                    ('kitchen', 'Кухня'),
                    ('pool', 'Бассейн'),
                    ('terrace', 'Терраса / балкон'),
                    ('view', 'Вид'),
                    ('garden', 'Сад / участок'),
                    ('floorplan', 'Планировка'),
                    ('neighborhood', 'Локация / окружение'),
                    ('interior', 'Интерьер'),
                    ('exterior', 'Экстерьер'),
                    ('other', 'Другое'),
                ],
                default='other',
                help_text='Автоматически определяемый тип кадра для генерации alt-текста',
                max_length=20,
                verbose_name='Тип кадра',
            ),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='alt_text_ru',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Alt текст (RU)'),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='alt_text_en',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Alt текст (EN)'),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='alt_text_th',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Alt текст (TH)'),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='alt_generated_by',
            field=models.CharField(
                blank=True,
                default='',
                help_text='heuristic, vision или manual',
                max_length=20,
                verbose_name='Источник alt',
            ),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='alt_confidence',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Уверенность классификации от 0 до 1',
                max_digits=4,
                null=True,
                verbose_name='Уверенность',
            ),
        ),
        migrations.AddField(
            model_name='propertyimage',
            name='alt_generated_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Сгенерировано'),
        ),
    ]
