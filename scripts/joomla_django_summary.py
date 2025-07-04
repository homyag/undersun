#!/usr/bin/env python
"""
Создание краткой сводки сопоставления ID между Joomla и Django
"""

import json
import csv

def create_summary_table():
    """Создает краткую таблицу сопоставления ID"""
    
    # Загружаем данные сравнения
    with open('joomla_django_comparison.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Создаем краткую таблицу
    summary_data = []
    
    for item in data['matched_objects']:
        summary_data.append({
            'joomla_id': item['joomla_id'],
            'legacy_id': item['legacy_id'],
            'title': item['joomla_title'][:80] + '...' if len(item['joomla_title']) > 80 else item['joomla_title'],
            'match_type': item['match_type']
        })
    
    # Сортируем по Joomla ID
    summary_data.sort(key=lambda x: int(x['joomla_id']))
    
    # Сохраняем в CSV
    with open('id_mapping_summary.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Joomla_ID', 'Django_Legacy_ID', 'Title', 'Match_Type'])
        
        for item in summary_data:
            writer.writerow([
                item['joomla_id'],
                item['legacy_id'],
                item['title'],
                item['match_type']
            ])
    
    # Выводим первые 20 записей
    print("📋 КРАТКАЯ ТАБЛИЦА СОПОСТАВЛЕНИЯ ID")
    print("="*100)
    print(f"{'Joomla ID':<10} {'Legacy ID':<12} {'Title':<65} {'Match':<10}")
    print("-"*100)
    
    for i, item in enumerate(summary_data[:20]):
        print(f"{item['joomla_id']:<10} {item['legacy_id']:<12} {item['title']:<65} {item['match_type']:<10}")
    
    if len(summary_data) > 20:
        print(f"... и ещё {len(summary_data) - 20} записей")
    
    print(f"\n💾 Полная таблица сохранена в файл: id_mapping_summary.csv")
    
    # Статистика по типам совпадений
    exact_matches = sum(1 for item in summary_data if item['match_type'] == 'exact_title')
    partial_matches = sum(1 for item in summary_data if item['match_type'] == 'partial_match')
    
    print(f"\n📊 СТАТИСТИКА СОВПАДЕНИЙ:")
    print(f"✅ Точные совпадения: {exact_matches}")
    print(f"🔍 Частичные совпадения: {partial_matches}")
    print(f"📈 Общий процент точности: {(exact_matches/len(summary_data)*100):.1f}%")

if __name__ == '__main__':
    create_summary_table()