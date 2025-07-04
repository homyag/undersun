# 🛠️ Скрипты миграции и управления данными

Эта папка содержит все скрипты для миграции данных из Joomla в Django, анализа данных и управления базой данных.

## 📋 Быстрый старт

### 1. Полная миграция из Joomla
```bash
# Анализ и привязка изображений
python analyze_real_estate_images.py
python link_photos_to_objects.py

# Миграция данных
python migrate_all_joomla.py
python migrate_photos_to_django.py
```

### 2. Очистка базы данных
```bash
# Анализ объектов для удаления
python cleanup_preview_only.py

# Умная очистка (рекомендуется)
python smart_cleanup.py
python execute_safe_cleanup.py
```

### 3. Сравнение и анализ
```bash
# Сравнение Joomla ↔ Django
python compare_joomla_django_objects.py

# Создание отчетов
python create_html_report.py
```

## 📁 Категории скриптов

### 🔍 Анализ данных
- `analyze_real_estate_images.py` - анализ структуры изображений
- `compare_joomla_django_objects.py` - сравнение объектов между системами
- `cleanup_preview_only.py` - анализ объектов для удаления

### 🔄 Миграция данных  
- `migrate_all_joomla.py` - полная миграция из Joomla
- `migrate_photos_to_django.py` - миграция фотографий
- `migrate_cn169.py` - специализированная миграция
- `link_photos_to_objects.py` - привязка фотографий к объектам

### 🧹 Очистка базы данных
- `smart_cleanup.py` - умный анализ и планирование очистки
- `execute_safe_cleanup.py` - безопасное выполнение очистки
- `cleanup_django_objects.py` - универсальная очистка с подтверждением

### 📊 Создание отчетов
- `create_html_report.py` - подробный HTML отчет
- `create_simple_html_report.py` - упрощенный отчет
- `create_summary_report.py` - сводный отчет
- `joomla_django_summary.py` - краткая сводка ID

## ⚠️ Важные примечания

### Перед запуском:
1. Убедитесь что `joomla_base.json` находится в корне проекта
2. Настройте Django окружение: `export DJANGO_SETTINGS_MODULE=config.settings.development`
3. Создайте резервную копию базы данных

### Безопасность:
- Всегда используйте preview режим перед удалением данных
- Скрипты автоматически создают резервные копии
- Проверяйте отчеты перед выполнением операций

### Результаты работы:
- Данные сохраняются в папке `../data/`
- Отчеты в `../data/reports/`
- Резервные копии в `../data/backups/`

## 📚 Полная документация

Подробная документация доступна в файле:
**`../docs/SCRIPTS_DOCUMENTATION.md`**

---

*Все скрипты протестированы и готовы к использованию!* 🚀