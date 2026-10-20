from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('arealisting', '0011_arealistingmediajob')]

    operations = [
        migrations.AddField(
            model_name='arealistingmediajob',
            name='preferred_main_asset_id',
            field=models.PositiveBigIntegerField(blank=True, null=True, verbose_name='Главное фото из источника'),
        ),
    ]
