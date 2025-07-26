#!/usr/bin/env python3
"""
Детальный анализ различий между данными Django и маппинга
"""

import os
import sys
import django
import json

# Настройка Django окружения
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property

def analyze_differences():
    """Детальный анализ различий"""
    
    # Загружаем маппинг
    with open('real_estate_mapping.json', 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)
    
    mapping_properties = mapping_data['properties']
    
    # Получаем Django данные
    django_properties = list(Property.objects.all().values(
        'id', 'legacy_id', 'title', 'bedrooms', 'area_total'
    ))
    
    print("=== АНАЛИЗ РАЗЛИЧИЙ ===")
    print(f"Django объектов: {len(django_properties)}")
    print(f"Маппинг объектов: {len(mapping_properties)}")
    
    # Анализируем примеры данных
    print("\n=== ПРИМЕРЫ DJANGO LEGACY_ID ===")
    for i, prop in enumerate(django_properties[:10]):
        print(f"{i+1}. ID: {prop['id']}, Legacy: {prop['legacy_id']}, Title: {prop['title'][:50]}...")
    
    print("\n=== ПРИМЕРЫ МАППИНГ LEGACY_ID ===")
    valid_mapping = [p for p in mapping_properties if p.get('project_code') and p.get('bedrooms') is not None and p.get('living_area')]
    
    for i, prop in enumerate(valid_mapping[:10]):
        legacy_id = f"{prop['project_code']}-{prop['bedrooms']}BR-{prop['living_area']}M"
        print(f"{i+1}. ID: {prop['id']}, Generated Legacy: {legacy_id}, Title: {prop['title'][:50]}...")
    
    # Проверяем качество данных в маппинге
    print("\n=== КАЧЕСТВО ДАННЫХ МАППИНГА ===")
    
    with_project_code = [p for p in mapping_properties if p.get('project_code')]
    with_bedrooms = [p for p in mapping_properties if p.get('bedrooms') is not None]
    with_area = [p for p in mapping_properties if p.get('living_area') is not None]
    
    print(f"С project_code: {len(with_project_code)}/{len(mapping_properties)}")
    print(f"С bedrooms: {len(with_bedrooms)}/{len(mapping_properties)}")
    print(f"С living_area: {len(with_area)}/{len(mapping_properties)}")
    
    # Создаем индекс по title для поиска совпадений
    print("\n=== ПОИСК СОВПАДЕНИЙ ПО TITLE ===")
    
    django_by_title = {}
    for prop in django_properties:
        title_clean = prop['title'].lower().strip()
        django_by_title[title_clean] = prop
    
    title_matches = 0
    potential_matches = []
    
    for mapping_prop in mapping_properties:
        title_clean = mapping_prop['title'].lower().strip()
        if title_clean in django_by_title:
            title_matches += 1
            django_match = django_by_title[title_clean]
            
            # Генерируем legacy_id для маппинга
            if mapping_prop.get('project_code') and mapping_prop.get('bedrooms') is not None and mapping_prop.get('living_area'):
                generated_legacy = f"{mapping_prop['project_code']}-{mapping_prop['bedrooms']}BR-{mapping_prop['living_area']}M"
                
                potential_matches.append({
                    'django_legacy': django_match['legacy_id'],
                    'generated_legacy': generated_legacy,
                    'title': mapping_prop['title'][:50],
                    'match': django_match['legacy_id'] == generated_legacy
                })
    
    print(f"Совпадений по title: {title_matches}")
    
    print("\n=== ПРИМЕРЫ ПОТЕНЦИАЛЬНЫХ СОВПАДЕНИЙ ===")
    for i, match in enumerate(potential_matches[:10]):
        match_status = "✅" if match['match'] else "❌"
        print(f"{i+1}. {match_status} Django: {match['django_legacy']} | Generated: {match['generated_legacy']}")
        print(f"   Title: {match['title']}...")
    
    # Анализируем типы legacy_id в Django
    print("\n=== АНАЛИЗ LEGACY_ID В DJANGO ===")
    legacy_patterns = {}
    
    for prop in django_properties:
        legacy_id = prop['legacy_id']
        if legacy_id:
            # Определяем паттерн
            if '-' in legacy_id:
                parts = legacy_id.split('-')
                if len(parts) == 3 and 'BR' in parts[1] and 'M' in parts[2]:
                    pattern = "CODE-XBR-YM"
                elif len(parts) == 2:
                    pattern = "CODE-SUFFIX"
                else:
                    pattern = "OTHER-DASH"
            else:
                pattern = "NO-DASH"
            
            legacy_patterns[pattern] = legacy_patterns.get(pattern, 0) + 1
    
    print("Паттерны legacy_id в Django:")
    for pattern, count in legacy_patterns.items():
        print(f"  {pattern}: {count}")
    
    # Ищем объекты без кода проекта в маппинге
    print("\n=== ОБЪЕКТЫ БЕЗ PROJECT_CODE В МАППИНГЕ ===")
    no_project_code = [p for p in mapping_properties if not p.get('project_code')]
    print(f"Объектов без project_code: {len(no_project_code)}")
    
    for i, prop in enumerate(no_project_code[:5]):
        print(f"{i+1}. ID: {prop['id']}, Title: {prop['title'][:50]}...")

def main():
    try:
        analyze_differences()
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()