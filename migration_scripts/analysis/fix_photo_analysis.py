#!/usr/bin/env python3
"""
Исправленный анализ фотографий - правильная обработка путей
"""

import os
import json
from pathlib import Path

def analyze_photo_mapping_corrected():
    """Исправленный анализ сопоставления фотографий"""
    
    # Загружаем маппинг
    with open('real_estate_mapping.json', 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    mapping_properties = mapping_data['properties']
    
    # Базовый путь к медиа
    media_base = Path('media/images_from_joomla/images')
    
    stats = {
        'total_objects': len(mapping_properties),
        'objects_with_photos': 0,
        'total_mapped_files': 0,
        'existing_files': 0,
        'missing_files': 0,
        'successful_objects': 0,
        'problematic_objects': 0
    }
    
    detailed_results = []
    
    for prop in mapping_properties:
        photo_files = prop.get('photo_files', [])
        
        if not photo_files:
            continue
        
        stats['objects_with_photos'] += 1
        stats['total_mapped_files'] += len(photo_files)
        
        result = {
            'id': prop['id'],
            'title': prop['title'],
            'project_code': prop.get('project_code'),
            'total_files': len(photo_files),
            'existing_files': 0,
            'missing_files': 0,
            'existing_file_list': [],
            'missing_file_list': []
        }
        
        for photo_file in photo_files:
            # Проверяем наличие файла
            file_path = media_base / photo_file
            
            if file_path.exists():
                result['existing_files'] += 1
                result['existing_file_list'].append(photo_file)
                stats['existing_files'] += 1
            else:
                result['missing_files'] += 1
                result['missing_file_list'].append(photo_file)
                stats['missing_files'] += 1
        
        if result['existing_files'] > 0:
            stats['successful_objects'] += 1
        else:
            stats['problematic_objects'] += 1
        
        detailed_results.append(result)
    
    return {
        'statistics': stats,
        'detailed_results': detailed_results
    }

def main():
    print("=" * 60)
    print("ИСПРАВЛЕННЫЙ АНАЛИЗ ФОТОГРАФИЙ")
    print("=" * 60)
    
    try:
        results = analyze_photo_mapping_corrected()
        
        # Сохраняем результаты
        with open('corrected_photo_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        stats = results['statistics']
        
        # Создаем отчет
        with open('corrected_photo_analysis_report.md', 'w', encoding='utf-8') as f:
            f.write("# Исправленный анализ фотографий\n\n")
            
            f.write("## Общая статистика\n\n")
            f.write(f"- **Всего объектов**: {stats['total_objects']}\n")
            f.write(f"- **Объектов с фотографиями**: {stats['objects_with_photos']}\n")
            f.write(f"- **Всего файлов в маппинге**: {stats['total_mapped_files']}\n")
            f.write(f"- **Существующих файлов**: {stats['existing_files']}\n")
            f.write(f"- **Отсутствующих файлов**: {stats['missing_files']}\n\n")
            
            f.write("## Результаты по объектам\n\n")
            f.write(f"- **Объектов с найденными фото**: {stats['successful_objects']}\n")
            f.write(f"- **Объектов без фото**: {stats['problematic_objects']}\n\n")
            
            # Процентные показатели
            if stats['total_mapped_files'] > 0:
                file_success_rate = stats['existing_files'] / stats['total_mapped_files'] * 100
                f.write(f"- **Процент найденных файлов**: {file_success_rate:.1f}%\n\n")
            
            if stats['objects_with_photos'] > 0:
                object_success_rate = stats['successful_objects'] / stats['objects_with_photos'] * 100
                f.write(f"- **Процент объектов с фото**: {object_success_rate:.1f}%\n\n")
            
            # Примеры успешных объектов
            successful_objects = [r for r in results['detailed_results'] if r['existing_files'] > 0]
            if successful_objects:
                f.write("## Примеры объектов с найденными фотографиями\n\n")
                for i, obj in enumerate(successful_objects[:10]):
                    f.write(f"### {i+1}. {obj['title'][:50]}...\n")
                    f.write(f"- **Project Code**: {obj['project_code']}\n")
                    f.write(f"- **Найдено файлов**: {obj['existing_files']}/{obj['total_files']}\n")
                    if obj['existing_file_list']:
                        f.write(f"- **Примеры файлов**: {', '.join(obj['existing_file_list'][:3])}\n")
                    f.write("\n")
            
            # Примеры проблемных объектов
            problematic_objects = [r for r in results['detailed_results'] if r['existing_files'] == 0]
            if problematic_objects:
                f.write("## Примеры объектов без найденных фотографий\n\n")
                for i, obj in enumerate(problematic_objects[:10]):
                    f.write(f"### {i+1}. {obj['title'][:50]}...\n")
                    f.write(f"- **Project Code**: {obj['project_code']}\n")
                    f.write(f"- **Всего файлов в маппинге**: {obj['total_files']}\n")
                    if obj['missing_file_list']:
                        f.write(f"- **Примеры отсутствующих**: {', '.join(obj['missing_file_list'][:3])}\n")
                    f.write("\n")
        
        # Выводим результаты
        print("\n" + "=" * 60)
        print("ИСПРАВЛЕННЫЕ РЕЗУЛЬТАТЫ")
        print("=" * 60)
        
        print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Объектов с фотографиями: {stats['objects_with_photos']}")
        print(f"   Всего файлов в маппинге: {stats['total_mapped_files']}")
        print(f"   Существующих файлов: {stats['existing_files']}")
        print(f"   Отсутствующих файлов: {stats['missing_files']}")
        
        if stats['total_mapped_files'] > 0:
            file_success_rate = stats['existing_files'] / stats['total_mapped_files'] * 100
            print(f"   Процент найденных файлов: {file_success_rate:.1f}%")
        
        print(f"\n🏠 ОБЪЕКТЫ:")
        print(f"   С найденными фото: {stats['successful_objects']}")
        print(f"   Без фото: {stats['problematic_objects']}")
        
        if stats['objects_with_photos'] > 0:
            object_success_rate = stats['successful_objects'] / stats['objects_with_photos'] * 100
            print(f"   Процент объектов с фото: {object_success_rate:.1f}%")
        
        print(f"\n💾 Отчеты сохранены:")
        print(f"   corrected_photo_analysis.json")
        print(f"   corrected_photo_analysis_report.md")
        
        # Дополнительная проверка для CN13
        print(f"\n🔍 ПРОВЕРКА CN13:")
        cn13_objects = [r for r in results['detailed_results'] if r.get('project_code') == 'CN13']
        print(f"   Объектов CN13: {len(cn13_objects)}")
        for obj in cn13_objects:
            print(f"   - {obj['id']}: {obj['existing_files']}/{obj['total_files']} файлов")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()