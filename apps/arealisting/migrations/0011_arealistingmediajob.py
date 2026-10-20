import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('arealisting', '0010_arealistinglistinggroup_excluded_media_source_keys'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ArealistingMediaJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDING', 'Ожидает'), ('RUNNING', 'Загружается'), ('SUCCESS', 'Завершено'), ('PARTIAL', 'Есть ошибки'), ('FAILED', 'Не выполнено')], db_index=True, default='PENDING', max_length=12, verbose_name='Статус')),
                ('selected_asset_ids', models.JSONField(default=list, verbose_name='Выбранные фото')),
                ('preview_fingerprint', models.CharField(max_length=64, verbose_name='Снимок выбора')),
                ('prune_missing', models.BooleanField(default=True, verbose_name='Удалять исключённые фото')),
                ('total', models.PositiveIntegerField(default=0, verbose_name='Всего операций')),
                ('processed', models.PositiveIntegerField(default=0, verbose_name='Выполнено операций')),
                ('totals', models.JSONField(blank=True, default=dict, verbose_name='Итог')),
                ('results', models.JSONField(blank=True, default=list, verbose_name='Результат по фото')),
                ('error', models.TextField(blank=True, verbose_name='Ошибка задания')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='Начато')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='Завершено')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='media_jobs', to='arealisting.arealistinglistinggroup', verbose_name='Группа')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Запустил')),
            ],
            options={
                'verbose_name': 'Импорт фото AREALISTING',
                'verbose_name_plural': 'Импорты фото AREALISTING',
                'ordering': ('-created_at', '-pk'),
            },
        ),
    ]
