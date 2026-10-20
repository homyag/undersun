from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('arealisting', '0009_alter_arealistingsyncevent_kind_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='arealistinglistinggroup',
            name='excluded_media_source_keys',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Эти исходные материалы не импортируются в карточку при следующих запусках.',
                verbose_name='Исключённые фото AREALISTING',
            ),
        ),
    ]
