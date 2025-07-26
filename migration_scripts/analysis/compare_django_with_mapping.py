#!/usr/bin/env python3
"""
Скрипт для сравнения данных в БД Django с данными из маппинга real_estate_mapping.json
Legacy ID в Django имеет формат: {project_code}-{bedrooms}BR-{living_area}M
"""

import os
import sys
import django
import json
from collections import defaultdict
from decimal import Decimal

# Настройка Django окружения
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property

def load_mapping_data():
    """Загрузить данные из маппинга"""
    with open('real_estate_mapping.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['properties']

def extract_django_data():
    """Извлечь данные из БД Django"""
    properties = Property.objects.all().values(
        'id', 'legacy_id', 'title', 'bedrooms', 'area_total'
    )
    
    django_data = []
    for prop in properties:
        # Парсим legacy_id для извлечения компонентов
        legacy_id = prop['legacy_id']
        project_code = None
        bedrooms_from_legacy = None
        area_from_legacy = None
        
        if legacy_id:
            try:
                # Формат: {project_code}-{bedrooms}BR-{living_area}M
                parts = legacy_id.split('-')
                if len(parts) >= 3:
                    project_code = parts[0]
                    if 'BR' in parts[1]:
                        bedrooms_from_legacy = int(parts[1].replace('BR', ''))
                    if 'M' in parts[2]:
                        area_from_legacy = float(parts[2].replace('M', ''))
            except (ValueError, IndexError):
                pass
        
        django_data.append({
            'django_id': prop['id'],
            'legacy_id': legacy_id,
            'title': prop['title'],
            'project_code': project_code,
            'bedrooms': prop['bedrooms'],
            'bedrooms_from_legacy': bedrooms_from_legacy,
            'area_total': prop['area_total'],
            'area_from_legacy': area_from_legacy
        })
    
    return django_data

def create_legacy_id(project_code, bedrooms, living_area):
    """Создать legacy_id в формате Django"""
    if not all([project_code, bedrooms is not None, living_area]):
        return None
    return f"{project_code}-{bedrooms}BR-{living_area}M"

def compare_data():
    """Сравнить данные Django с маппингом"""
    
    print("Загрузка данных...")
    mapping_data = load_mapping_data()
    django_data = extract_django_data()
    
    print(f"Данные маппинга: {len(mapping_data)} объектов")
    print(f"Данные Django: {len(django_data)} объектов")
    
    # Создаем индексы для быстрого поиска
    mapping_by_id = {str(item['id']): item for item in mapping_data}
    mapping_by_legacy = {}
    
    for item in mapping_data:
        legacy_id = create_legacy_id(
            item.get('project_code'),
            item.get('bedrooms'),
            item.get('living_area')
        )
        if legacy_id:
            mapping_by_legacy[legacy_id] = item
    
    django_by_legacy = {item['legacy_id']: item for item in django_data if item['legacy_id']}
    
    # Результаты сравнения
    results = {
        'django_count': len(django_data),
        'mapping_count': len(mapping_data),
        'matches_by_legacy_id': 0,
        'django_only': [],
        'mapping_only': [],
        'data_mismatches': [],
        'missing_legacy_ids': [],
        'invalid_legacy_ids': []
    }
    
    print("\nСравнение по legacy_id...")
    
    # Сравниваем Django объекты с маппингом
    for django_item in django_data:
        legacy_id = django_item['legacy_id']
        
        if not legacy_id:
            results['missing_legacy_ids'].append({
                'django_id': django_item['django_id'],
                'title': django_item['title']
            })
            continue
        
        if legacy_id in mapping_by_legacy:
            results['matches_by_legacy_id'] += 1
            mapping_item = mapping_by_legacy[legacy_id]
            
            # Проверяем соответствие данных
            mismatches = []
            
            if django_item['bedrooms'] != mapping_item.get('bedrooms'):
                mismatches.append(f"bedrooms: Django={django_item['bedrooms']}, Mapping={mapping_item.get('bedrooms')}")
            
            if django_item['area_total'] != mapping_item.get('living_area'):
                mismatches.append(f"area: Django={django_item['area_total']}, Mapping={mapping_item.get('living_area')}")
            
            if django_item['project_code'] != mapping_item.get('project_code'):
                mismatches.append(f"project_code: Django={django_item['project_code']}, Mapping={mapping_item.get('project_code')}")
            
            if mismatches:
                results['data_mismatches'].append({
                    'legacy_id': legacy_id,
                    'django_id': django_item['django_id'],
                    'mapping_id': mapping_item['id'],
                    'title': django_item['title'],
                    'mismatches': mismatches
                })
        else:
            results['django_only'].append({
                'legacy_id': legacy_id,
                'django_id': django_item['django_id'],
                'title': django_item['title'],
                'project_code': django_item['project_code'],
                'bedrooms': django_item['bedrooms'],
                'area_total': django_item['area_total']
            })
    
    # Ищем объекты только в маппинге
    for legacy_id, mapping_item in mapping_by_legacy.items():
        if legacy_id not in django_by_legacy:
            results['mapping_only'].append({
                'legacy_id': legacy_id,
                'mapping_id': mapping_item['id'],
                'title': mapping_item['title'],
                'project_code': mapping_item.get('project_code'),
                'bedrooms': mapping_item.get('bedrooms'),
                'living_area': mapping_item.get('living_area')
            })
    
    return results

def save_comparison_report(results):
    """Сохранить отчет о сравнении"""
    
    # Функция для конвертации Decimal в float
    def convert_decimals(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {key: convert_decimals(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_decimals(item) for item in obj]
        return obj
    
    # Конвертируем Decimal значения
    results_converted = convert_decimals(results)
    
    report = {
        "comparison_summary": {
            "django_objects": results['django_count'],
            "mapping_objects": results['mapping_count'],
            "matches_by_legacy_id": results['matches_by_legacy_id'],
            "django_only_count": len(results['django_only']),
            "mapping_only_count": len(results['mapping_only']),
            "data_mismatches_count": len(results['data_mismatches']),
            "missing_legacy_ids_count": len(results['missing_legacy_ids'])
        },
        "detailed_results": results_converted
    }
    
    # Сохраняем JSON отчет
    with open('django_mapping_comparison.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Создаем текстовый отчет
    with open('django_mapping_comparison_report.md', 'w', encoding='utf-8') as f:
        f.write("# Отчет сравнения данных Django с маппингом\n\n")
        
        f.write("## Общая статистика\n\n")
        f.write(f"- **Объектов в Django**: {results['django_count']}\n")
        f.write(f"- **Объектов в маппинге**: {results['mapping_count']}\n")
        f.write(f"- **Совпадений по legacy_id**: {results['matches_by_legacy_id']}\n")
        f.write(f"- **Только в Django**: {len(results['django_only'])}\n")
        f.write(f"- **Только в маппинге**: {len(results['mapping_only'])}\n")
        f.write(f"- **Несоответствия данных**: {len(results['data_mismatches'])}\n")
        f.write(f"- **Отсутствует legacy_id**: {len(results['missing_legacy_ids'])}\n\n")
        
        if results['django_only']:
            f.write("## Объекты только в Django\n\n")
            for item in results['django_only'][:20]:  # Показываем первые 20
                f.write(f"- **{item['legacy_id']}**: {item['title']}\n")
            if len(results['django_only']) > 20:
                f.write(f"... и еще {len(results['django_only']) - 20} объектов\n")
            f.write("\n")
        
        if results['mapping_only']:
            f.write("## Объекты только в маппинге\n\n")
            for item in results['mapping_only'][:20]:  # Показываем первые 20
                f.write(f"- **{item['legacy_id']}**: {item['title']}\n")
            if len(results['mapping_only']) > 20:
                f.write(f"... и еще {len(results['mapping_only']) - 20} объектов\n")
            f.write("\n")
        
        if results['data_mismatches']:
            f.write("## Несоответствия данных\n\n")
            for item in results['data_mismatches'][:10]:  # Показываем первые 10
                f.write(f"### {item['legacy_id']}: {item['title']}\n")
                for mismatch in item['mismatches']:
                    f.write(f"- {mismatch}\n")
                f.write("\n")
            if len(results['data_mismatches']) > 10:
                f.write(f"... и еще {len(results['data_mismatches']) - 10} несоответствий\n")
        
        if results['missing_legacy_ids']:
            f.write("## Объекты без legacy_id в Django\n\n")
            for item in results['missing_legacy_ids'][:20]:
                f.write(f"- ID {item['django_id']}: {item['title']}\n")
            if len(results['missing_legacy_ids']) > 20:
                f.write(f"... и еще {len(results['missing_legacy_ids']) - 20} объектов\n")

def main():
    print("=" * 60)
    print("СРАВНЕНИЕ ДАННЫХ DJANGO С МАППИНГОМ")
    print("=" * 60)
    
    try:
        results = compare_data()
        save_comparison_report(results)
        
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ СРАВНЕНИЯ")
        print("=" * 60)
        
        print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Django объектов: {results['django_count']}")
        print(f"   Маппинг объектов: {results['mapping_count']}")
        print(f"   Совпадений по legacy_id: {results['matches_by_legacy_id']}")
        
        print(f"\n📋 РАЗЛИЧИЯ:")
        print(f"   Только в Django: {len(results['django_only'])}")
        print(f"   Только в маппинге: {len(results['mapping_only'])}")
        print(f"   Несоответствия данных: {len(results['data_mismatches'])}")
        print(f"   Отсутствует legacy_id: {len(results['missing_legacy_ids'])}")
        
        if results['data_mismatches']:
            print(f"\n⚠️  ПРИМЕРЫ НЕСООТВЕТСТВИЙ:")
            for item in results['data_mismatches'][:3]:
                print(f"   {item['legacy_id']}: {', '.join(item['mismatches'])}")
        
        print(f"\n💾 Отчеты сохранены:")
        print(f"   django_mapping_comparison.json")
        print(f"   django_mapping_comparison_report.md")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()