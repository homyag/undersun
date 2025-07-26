# Скрипты миграции UnderSun Estate

Организованные скрипты для миграции данных из Joomla в Django.

## 📁 Структура папок

### 🚀 core/ - Основные скрипты миграции
- **migrate_underson_full_dump.py** - Основной скрипт миграции данных из Joomla в Django
- **create_real_estate_mapping.py** - Создание маппинга объектов недвижимости
- **migrate_photos_to_django.py** - Миграция фотографий в Django
- **create_amenities.py** - Создание и настройка удобств (amenities)

### 🔍 analysis/ - Скрипты анализа и проверки
- **fix_photo_analysis.py** - Исправленный анализ фотографий
- **normalize_and_check_photos.py** - Нормализация и проверка фотографий
- **compare_django_with_mapping.py** - Сравнение данных Django с маппингом
- **analyze_data_differences.py** - Анализ различий в данных

### 🔧 utilities/ - Вспомогательные утилиты
- **quick_status.py** - Быстрая проверка статуса миграции

## 🚀 Порядок выполнения миграции

### 1. Подготовка данных
```bash
cd migration_scripts/core
python create_real_estate_mapping.py
```

### 2. Создание удобств
```bash
python create_amenities.py
```

### 3. Основная миграция данных
```bash
python migrate_underson_full_dump.py
```

### 4. Анализ фотографий
```bash
cd ../analysis
python fix_photo_analysis.py
```

### 5. Миграция фотографий
```bash
cd ../core
python migrate_photos_to_django.py
```

### 6. Проверка результатов
```bash
cd ../utilities
python quick_status.py
```

## 📊 Результаты миграции

После завершения миграции:
- **748 объектов** недвижимости в Django
- **10,155 фотографий** мигрировано
- **657 объектов** с фотографиями (87.8%)
- **96.8%** фотографий найдены и доступны

## ⚠️ Важные замечания

1. **Резервное копирование**: Всегда делайте резервную копию БД перед миграцией
2. **Окружение**: Убедитесь, что Django окружение настроено корректно
3. **Права доступа**: Проверьте права на папки с медиафайлами
4. **Тестирование**: Используйте dry_run режим для тестирования

## 🔧 Настройки

Основные файлы настроек:
- `joomla_base.json` - Дамп базы данных Joomla
- `real_estate_mapping.json` - Маппинг объектов недвижимости
- `media/images_from_joomla/images/` - Папка с фотографиями

## 📝 Логи и отчеты

Скрипты создают детальные отчеты:
- `photo_migration_report.md` - Отчет о миграции фотографий
- `corrected_photo_analysis_report.md` - Анализ фотографий
- `normalized_mapping_report.md` - Отчет нормализации данных

---
*Создано: январь 2025*  
*Статус: Готово к использованию*
