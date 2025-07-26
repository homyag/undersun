#!/usr/bin/env python3
"""
Скрипт для нормализации legacy_id и проверки наличия фотографий
"""

import os
import sys
import django
import json
from pathlib import Path

# Настройка Django окружения
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property

def normalize_legacy_id(project_code, bedrooms, living_area):
    """Нормализация legacy_id для соответствия формату Django"""
    if not project_code:
        return None
    
    if bedrooms is None or living_area is None:
        return project_code
    
    # Конвертируем float в int если это целое число
    if isinstance(living_area, float) and living_area.is_integer():
        living_area = int(living_area)
    
    return f"{project_code}-{bedrooms}BR-{living_area}M"

def check_photo_files(photo_folder, photo_files, media_path):
    """Проверка наличия файлов фотографий"""
    if not photo_folder or not photo_files:
        return {"status": "no_photos", "existing": 0, "missing": 0, "missing_files": []}
    
    folder_path = media_path / photo_folder
    existing_files = []
    missing_files = []
    
    for photo_file in photo_files:
        file_path = folder_path / photo_file
        if file_path.exists():
            existing_files.append(photo_file)
        else:
            missing_files.append(photo_file)
    
    return {
        "status": "checked",
        "existing": len(existing_files),
        "missing": len(missing_files),
        "total": len(photo_files),
        "missing_files": missing_files,
        "folder_exists": folder_path.exists()
    }

def main():
    print("=" * 60)
    print("НОРМАЛИЗАЦИЯ LEGACY_ID И ПРОВЕРКА ФОТОГРАФИЙ")
    print("=" * 60)
    
    # Загружаем маппинг
    print("Загрузка маппинга...")
    with open('real_estate_mapping.json', 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    mapping_properties = mapping_data['properties']
    
    # Получаем Django данные
    print("Загрузка данных Django...")
    django_properties = list(Property.objects.all().values(
        'id', 'legacy_id', 'title', 'bedrooms', 'area_total'
    ))
    
    # Создаем индекс Django по legacy_id
    django_by_legacy = {prop['legacy_id']: prop for prop in django_properties if prop['legacy_id']}
    
    # Путь к медиа файлам
    media_path = Path('media/images_from_joomla/images')
    
    print(f"Медиа папка: {media_path.absolute()}")
    print(f"Медиа папка существует: {media_path.exists()}")
    
    # Статистика
    stats = {
        'total_mapping': len(mapping_properties),
        'total_django': len(django_properties),
        'normalized_legacy_ids': 0,
        'matched_after_normalize': 0,
        'photos_total_objects': 0,
        'photos_total_files': 0,
        'photos_existing_files': 0,
        'photos_missing_files': 0,
        'photos_missing_folders': 0
    }
    
    # Результаты
    normalized_mapping = []
    matches_after_normalize = []
    photo_check_results = []
    
    print("\nОбработка объектов...")
    
    for i, mapping_prop in enumerate(mapping_properties):
        if i % 100 == 0:
            print(f"Обработано: {i}/{len(mapping_properties)}")
        
        # Нормализация legacy_id
        normalized_legacy = normalize_legacy_id(
            mapping_prop.get('project_code'),
            mapping_prop.get('bedrooms'),
            mapping_prop.get('living_area')
        )
        
        if normalized_legacy:
            stats['normalized_legacy_ids'] += 1
        
        # Проверка совпадения с Django
        django_match = None
        if normalized_legacy and normalized_legacy in django_by_legacy:
            django_match = django_by_legacy[normalized_legacy]
            stats['matched_after_normalize'] += 1
            
            matches_after_normalize.append({
                'mapping_id': mapping_prop['id'],
                'django_id': django_match['id'],
                'legacy_id': normalized_legacy,
                'title': mapping_prop['title']
            })
        
        # Проверка фотографий
        photo_check = check_photo_files(
            mapping_prop.get('photo_folder'),
            mapping_prop.get('photo_files', []),
            media_path
        )
        
        if photo_check['status'] == 'checked':
            stats['photos_total_objects'] += 1
            stats['photos_total_files'] += photo_check['total']
            stats['photos_existing_files'] += photo_check['existing']
            stats['photos_missing_files'] += photo_check['missing']
            
            if not photo_check['folder_exists']:
                stats['photos_missing_folders'] += 1
        
        # Сохраняем результат
        result_item = {
            'mapping_id': mapping_prop['id'],
            'title': mapping_prop['title'],
            'original_project_code': mapping_prop.get('project_code'),
            'bedrooms': mapping_prop.get('bedrooms'),
            'living_area': mapping_prop.get('living_area'),
            'normalized_legacy_id': normalized_legacy,
            'django_match': django_match is not None,
            'django_id': django_match['id'] if django_match else None,
            'photo_check': photo_check
        }
        
        normalized_mapping.append(result_item)
        
        # Детальные результаты проверки фото (только с проблемами)
        if photo_check['status'] == 'checked' and (photo_check['missing'] > 0 or not photo_check['folder_exists']):
            photo_check_results.append({
                'mapping_id': mapping_prop['id'],
                'title': mapping_prop['title'][:50],
                'photo_folder': mapping_prop.get('photo_folder'),
                'total_files': photo_check['total'],
                'existing_files': photo_check['existing'],
                'missing_files': photo_check['missing'],
                'folder_exists': photo_check['folder_exists'],
                'missing_file_names': photo_check['missing_files'][:5]  # Первые 5 отсутствующих файлов
            })
    
    # Сохраняем результаты
    report = {
        'statistics': stats,
        'matches_after_normalize': matches_after_normalize,
        'photo_issues': photo_check_results,
        'normalized_mapping': normalized_mapping
    }
    
    with open('normalized_mapping_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Создаем текстовый отчет
    with open('normalized_mapping_report.md', 'w', encoding='utf-8') as f:
        f.write("# Отчет нормализации legacy_id и проверки фотографий\n\n")
        
        f.write("## Общая статистика\n\n")
        f.write(f"- **Объектов в маппинге**: {stats['total_mapping']}\n")
        f.write(f"- **Объектов в Django**: {stats['total_django']}\n")
        f.write(f"- **Нормализованных legacy_id**: {stats['normalized_legacy_ids']}\n")
        f.write(f"- **Совпадений после нормализации**: {stats['matched_after_normalize']}\n")
        f.write(f"- **Процент совпадений**: {stats['matched_after_normalize']/stats['total_django']*100:.1f}%\n\n")
        
        f.write("## Статистика фотографий\n\n")
        f.write(f"- **Объектов с фото**: {stats['photos_total_objects']}\n")
        f.write(f"- **Всего файлов фото**: {stats['photos_total_files']}\n")
        f.write(f"- **Существующих файлов**: {stats['photos_existing_files']}\n")
        f.write(f"- **Отсутствующих файлов**: {stats['photos_missing_files']}\n")
        f.write(f"- **Отсутствующих папок**: {stats['photos_missing_folders']}\n")
        f.write(f"- **Процент существующих фото**: {stats['photos_existing_files']/stats['photos_total_files']*100:.1f}%\n\n")
        
        if matches_after_normalize:
            f.write("## Примеры совпадений после нормализации\n\n")
            for i, match in enumerate(matches_after_normalize[:20]):
                f.write(f"{i+1}. **{match['legacy_id']}**: {match['title'][:50]}...\n")
                f.write(f"   Mapping ID: {match['mapping_id']}, Django ID: {match['django_id']}\n\n")
        
        if photo_check_results:
            f.write("## Проблемы с фотографиями\n\n")
            for i, issue in enumerate(photo_check_results[:20]):
                f.write(f"### {i+1}. {issue['title']}...\n")
                f.write(f"- **Папка**: {issue['photo_folder']}\n")
                f.write(f"- **Папка существует**: {issue['folder_exists']}\n")
                f.write(f"- **Всего файлов**: {issue['total_files']}\n")
                f.write(f"- **Существует**: {issue['existing_files']}\n")
                f.write(f"- **Отсутствует**: {issue['missing_files']}\n")
                if issue['missing_file_names']:
                    f.write(f"- **Примеры отсутствующих**: {', '.join(issue['missing_file_names'])}\n")
                f.write("\n")
    
    # Выводим результаты
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ НОРМАЛИЗАЦИИ И ПРОВЕРКИ")
    print("=" * 60)
    
    print(f"\n📊 СТАТИСТИКА LEGACY_ID:")
    print(f"   Объектов в маппинге: {stats['total_mapping']}")
    print(f"   Объектов в Django: {stats['total_django']}")
    print(f"   Нормализованных legacy_id: {stats['normalized_legacy_ids']}")
    print(f"   Совпадений после нормализации: {stats['matched_after_normalize']}")
    print(f"   Процент совпадений: {stats['matched_after_normalize']/stats['total_django']*100:.1f}%")
    
    print(f"\n📷 СТАТИСТИКА ФОТОГРАФИЙ:")
    print(f"   Объектов с фото: {stats['photos_total_objects']}")
    print(f"   Всего файлов фото: {stats['photos_total_files']}")
    print(f"   Существующих файлов: {stats['photos_existing_files']}")
    print(f"   Отсутствующих файлов: {stats['photos_missing_files']}")
    print(f"   Отсутствующих папок: {stats['photos_missing_folders']}")
    print(f"   Процент существующих фото: {stats['photos_existing_files']/stats['photos_total_files']*100:.1f}%")
    
    print(f"\n💾 Отчеты сохранены:")
    print(f"   normalized_mapping_report.json")
    print(f"   normalized_mapping_report.md")

if __name__ == "__main__":
    main()