#!/usr/bin/env python3
"""
Миграция фотографий в Django с использованием маппинга
"""

import os
import sys
import django
import json
from pathlib import Path
from django.core.files import File
from django.db import transaction
import shutil

# Настройка Django окружения
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property, PropertyImage

def load_mapping_and_django_data():
    """Загрузить данные маппинга и Django"""
    
    # Загружаем маппинг
    with open('real_estate_mapping.json', 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    # Загружаем данные Django 
    django_properties = {}
    for prop in Property.objects.all():
        if prop.legacy_id:
            django_properties[prop.legacy_id] = prop
    
    return mapping_data['properties'], django_properties

def create_legacy_id(project_code, bedrooms, living_area):
    """Создать legacy_id в формате Django"""
    if not project_code:
        return None
    
    if bedrooms is None or living_area is None:
        return project_code
    
    # Конвертируем float в int если это целое число
    if isinstance(living_area, float) and living_area.is_integer():
        living_area = int(living_area)
    
    return f"{project_code}-{bedrooms}BR-{living_area}M"

def migrate_photos(dry_run=True, limit=None):
    """Мигрировать фотографии в Django"""
    
    print("Загрузка данных...")
    mapping_properties, django_properties = load_mapping_and_django_data()
    
    media_base = Path('media/images_from_joomla/images')
    
    stats = {
        'total_mapping_objects': len(mapping_properties),
        'objects_with_photos': 0,
        'matched_django_objects': 0,
        'total_photos_in_mapping': 0,
        'existing_photos': 0,
        'missing_photos': 0,
        'photos_migrated': 0,
        'objects_migrated': 0,
        'errors': 0,
        'skipped_no_match': 0,
        'skipped_no_photos': 0
    }
    
    migration_log = []
    error_log = []
    
    processed_count = 0
    
    for mapping_obj in mapping_properties:
        # Ограничение количества для тестирования
        if limit and processed_count >= limit:
            break
            
        photo_files = mapping_obj.get('photo_files', [])
        if not photo_files:
            stats['skipped_no_photos'] += 1
            continue
        
        stats['objects_with_photos'] += 1
        stats['total_photos_in_mapping'] += len(photo_files)
        
        # Создаем legacy_id
        legacy_id = create_legacy_id(
            mapping_obj.get('project_code'),
            mapping_obj.get('bedrooms'),
            mapping_obj.get('living_area')
        )
        
        # Ищем соответствующий объект в Django
        django_obj = None
        if legacy_id and legacy_id in django_properties:
            django_obj = django_properties[legacy_id]
            stats['matched_django_objects'] += 1
        else:
            stats['skipped_no_match'] += 1
            migration_log.append({
                'mapping_id': mapping_obj['id'],
                'legacy_id': legacy_id,
                'status': 'skipped_no_django_match',
                'title': mapping_obj['title']
            })
            continue
        
        # Проверяем и мигрируем фотографии
        object_log = {
            'mapping_id': mapping_obj['id'],
            'django_id': django_obj.id,
            'legacy_id': legacy_id,
            'title': mapping_obj['title'],
            'total_photos': len(photo_files),
            'existing_photos': 0,
            'missing_photos': 0,
            'migrated_photos': 0,
            'photo_details': []
        }
        
        if not dry_run:
            # Удаляем существующие фотографии объекта
            PropertyImage.objects.filter(property=django_obj).delete()
        
        for photo_file in photo_files:
            photo_path = media_base / photo_file
            
            photo_detail = {
                'file_path': str(photo_file),
                'exists': photo_path.exists(),
                'migrated': False,
                'error': None
            }
            
            if photo_path.exists():
                stats['existing_photos'] += 1
                object_log['existing_photos'] += 1
                
                if not dry_run:
                    try:
                        # Создаем объект PropertyImage
                        with transaction.atomic():
                            with open(photo_path, 'rb') as f:
                                django_file = File(f)
                                property_image = PropertyImage(
                                    property=django_obj,
                                    alt_text=f"{django_obj.title} - фото"
                                )
                                
                                # Генерируем имя файла для Django
                                file_name = f"property_{django_obj.id}_{Path(photo_file).name}"
                                property_image.image.save(file_name, django_file, save=True)
                                
                                photo_detail['migrated'] = True
                                stats['photos_migrated'] += 1
                                object_log['migrated_photos'] += 1
                                
                    except Exception as e:
                        stats['errors'] += 1
                        photo_detail['error'] = str(e)
                        error_log.append({
                            'mapping_id': mapping_obj['id'],
                            'photo_file': photo_file,
                            'error': str(e)
                        })
                else:
                    # В режиме dry_run считаем как успешную миграцию
                    photo_detail['migrated'] = True
                    stats['photos_migrated'] += 1
                    object_log['migrated_photos'] += 1
            else:
                stats['missing_photos'] += 1
                object_log['missing_photos'] += 1
            
            object_log['photo_details'].append(photo_detail)
        
        if object_log['migrated_photos'] > 0:
            stats['objects_migrated'] += 1
        
        migration_log.append(object_log)
        processed_count += 1
        
        # Прогресс
        if processed_count % 50 == 0:
            print(f"Обработано: {processed_count} объектов...")
    
    return {
        'statistics': stats,
        'migration_log': migration_log,
        'error_log': error_log,
        'dry_run': dry_run
    }

def save_migration_report(results):
    """Сохранить отчет о миграции"""
    
    # JSON отчет
    with open('photo_migration_report.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Markdown отчет
    stats = results['statistics']
    
    with open('photo_migration_report.md', 'w', encoding='utf-8') as f:
        f.write("# Отчет миграции фотографий\n\n")
        
        mode = "DRY RUN (тестовый режим)" if results['dry_run'] else "РЕАЛЬНАЯ МИГРАЦИЯ"
        f.write(f"**Режим**: {mode}\n\n")
        
        f.write("## Общая статистика\n\n")
        f.write(f"- **Всего объектов в маппинге**: {stats['total_mapping_objects']}\n")
        f.write(f"- **Объектов с фотографиями**: {stats['objects_with_photos']}\n")
        f.write(f"- **Найдено соответствий в Django**: {stats['matched_django_objects']}\n")
        f.write(f"- **Всего фотографий в маппинге**: {stats['total_photos_in_mapping']}\n")
        f.write(f"- **Существующих фотографий**: {stats['existing_photos']}\n")
        f.write(f"- **Отсутствующих фотографий**: {stats['missing_photos']}\n")
        f.write(f"- **Мигрированных фотографий**: {stats['photos_migrated']}\n")
        f.write(f"- **Объектов мигрировано**: {stats['objects_migrated']}\n")
        f.write(f"- **Ошибок**: {stats['errors']}\n\n")
        
        # Процентные показатели
        if stats['objects_with_photos'] > 0:
            match_rate = stats['matched_django_objects'] / stats['objects_with_photos'] * 100
            f.write(f"- **Процент совпадений объектов**: {match_rate:.1f}%\n")
        
        if stats['total_photos_in_mapping'] > 0:
            photo_success_rate = stats['photos_migrated'] / stats['total_photos_in_mapping'] * 100
            f.write(f"- **Процент успешной миграции фото**: {photo_success_rate:.1f}%\n\n")
        
        # Примеры успешных миграций
        successful_migrations = [log for log in results['migration_log'] 
                               if log.get('migrated_photos', 0) > 0]
        
        if successful_migrations:
            f.write("## Примеры успешных миграций\n\n")
            for i, migration in enumerate(successful_migrations[:10]):
                f.write(f"### {i+1}. {migration['title'][:50]}...\n")
                f.write(f"- **Legacy ID**: {migration['legacy_id']}\n")
                f.write(f"- **Django ID**: {migration['django_id']}\n")
                f.write(f"- **Мигрировано фото**: {migration['migrated_photos']}/{migration['total_photos']}\n\n")
        
        # Ошибки
        if results['error_log']:
            f.write("## Ошибки миграции\n\n")
            for i, error in enumerate(results['error_log'][:10]):
                f.write(f"{i+1}. **Mapping ID**: {error['mapping_id']}\n")
                f.write(f"   **Файл**: {error['photo_file']}\n")
                f.write(f"   **Ошибка**: {error['error']}\n\n")

def main():
    print("=" * 60)
    print("МИГРАЦИЯ ФОТОГРАФИЙ В DJANGO")
    print("=" * 60)
    
    # Параметры
    dry_run = False  # Реальная миграция
    limit = None     # Все объекты
    
    if dry_run:
        print("🧪 РЕЖИМ: DRY RUN (тестовый)")
        print("📝 Никакие изменения в БД не будут сделаны")
    else:
        print("🚀 РЕЖИМ: РЕАЛЬНАЯ МИГРАЦИЯ")
        print("⚠️  БУДУТ ВНЕСЕНЫ ИЗМЕНЕНИЯ В БД!")
        
        # Подтверждение для реальной миграции
        confirm = input("\nПродолжить? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Миграция отменена.")
            return
    
    if limit:
        print(f"📊 ОГРАНИЧЕНИЕ: {limit} объектов")
    
    print("\nНачинаем миграцию...")
    
    try:
        results = migrate_photos(dry_run=dry_run, limit=limit)
        save_migration_report(results)
        
        stats = results['statistics']
        
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ МИГРАЦИИ")
        print("=" * 60)
        
        print(f"\n📊 СТАТИСТИКА:")
        print(f"   Объектов с фото: {stats['objects_with_photos']}")
        print(f"   Найдено соответствий: {stats['matched_django_objects']}")
        print(f"   Всего фотографий: {stats['total_photos_in_mapping']}")
        print(f"   Существующих фото: {stats['existing_photos']}")
        print(f"   Мигрированных фото: {stats['photos_migrated']}")
        print(f"   Объектов мигрировано: {stats['objects_migrated']}")
        print(f"   Ошибок: {stats['errors']}")
        
        if stats['objects_with_photos'] > 0:
            match_rate = stats['matched_django_objects'] / stats['objects_with_photos'] * 100
            print(f"   Процент совпадений: {match_rate:.1f}%")
        
        if stats['total_photos_in_mapping'] > 0:
            photo_success_rate = stats['photos_migrated'] / stats['total_photos_in_mapping'] * 100
            print(f"   Успешность миграции: {photo_success_rate:.1f}%")
        
        print(f"\n💾 Отчеты сохранены:")
        print(f"   photo_migration_report.json")
        print(f"   photo_migration_report.md")
        
        if dry_run:
            print(f"\n✅ Тестовый прогон завершен успешно!")
            print(f"📝 Для реальной миграции измените dry_run=False в коде")
        else:
            print(f"\n🎉 Реальная миграция завершена!")
            print(f"📸 Фотографии добавлены в Django модели")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()