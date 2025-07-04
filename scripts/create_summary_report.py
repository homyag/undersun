#!/usr/bin/env python3
"""
Создание краткого отчета по найденным изображениям недвижимости
"""

import json
from pathlib import Path

def create_summary_report():
    """Создает краткий отчет с основной информацией"""
    
    # Загружаем результаты анализа
    results_file = Path('real_estate_images_analysis.json')
    if not results_file.exists():
        print("Файл результатов анализа не найден!")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Создаем краткий отчет
    summary = {
        "summary": {
            "total_records": data['total_found'],
            "total_property_images": sum(len(record['image_paths']) for record in data['records']),
            "analysis_date": "2025-07-03"
        },
        "records": []
    }
    
    for record in data['records']:
        # Декодируем пути изображений
        decoded_images = []
        for img_path in record['image_paths']:
            try:
                decoded_path = img_path.encode().decode('unicode_escape')
                decoded_images.append(decoded_path)
            except:
                decoded_images.append(img_path)
        
        record_summary = {
            "id": record['id'],
            "title": record['title'],
            "alias": record['alias'],
            "image_count": len(decoded_images),
            "image_paths": decoded_images,
            "created": record['created'],
            "modified": record['modified'],
            "status": "active" if record['state'] == '1' else "inactive" if record['state'] == '0' else "unknown",
            "category_id": record['catid']
        }
        summary['records'].append(record_summary)
    
    # Статистика по папкам
    folder_stats = {}
    for record in data['records']:
        for img_path in record['image_paths']:
            folder = img_path.split('/')[1] if '/' in img_path else 'unknown'
            if folder not in folder_stats:
                folder_stats[folder] = {'image_count': 0, 'record_count': 0, 'record_ids': set()}
            folder_stats[folder]['image_count'] += 1
            folder_stats[folder]['record_ids'].add(record['id'])
    
    # Преобразуем статистику в нужный формат
    summary['folder_statistics'] = {}
    for folder, stats in folder_stats.items():
        summary['folder_statistics'][folder] = {
            'image_count': stats['image_count'],
            'record_count': len(stats['record_ids']),
            'record_ids': sorted(list(stats['record_ids']))
        }
    
    # Сохраняем краткий отчет
    output_file = Path('real_estate_summary.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"Краткий отчет создан: {output_file}")
    
    # Выводим краткую статистику в консоль
    print(f"\\nКраткая статистика:")
    print(f"- Найдено записей: {summary['summary']['total_records']}")
    print(f"- Всего изображений недвижимости: {summary['summary']['total_property_images']}")
    print(f"- Папок проектов: {len(summary['folder_statistics'])}")
    print(f"\\nПапки проектов:")
    for folder, stats in sorted(summary['folder_statistics'].items()):
        print(f"  - {folder}: {stats['image_count']} изображений в {stats['record_count']} записях")
    
    return output_file

if __name__ == "__main__":
    create_summary_report()