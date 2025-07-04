#!/usr/bin/env python
"""
Скрипт для сравнения объектов недвижимости между Joomla и Django
Создает сравнительный файл с указанием соответствий
"""

import os
import sys
import json
import re
from pathlib import Path

# Добавляем путь к Django проекту
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from apps.properties.models import Property


def load_joomla_data():
    """Загружает данные из joomla_base.json"""
    try:
        with open('joomla_base.json', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Ищем таблицу ec9oj_content
        content_start = content.find('"name":"ec9oj_content"')
        if content_start == -1:
            print("Таблица ec9oj_content не найдена")
            return []
            
        # Ищем начало данных
        data_start = content.find('"data":', content_start)
        if data_start == -1:
            print("Данные таблицы не найдены")
            return []
            
        # Находим начало массива данных
        array_start = content.find('[', data_start)
        if array_start == -1:
            print("Массив данных не найден")
            return []
            
        # Находим конец массива данных (ищем закрывающую скобку на том же уровне)
        bracket_count = 0
        array_end = array_start
        for i, char in enumerate(content[array_start:], array_start):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    array_end = i
                    break
        
        # Извлекаем JSON данные
        json_data = content[array_start:array_end + 1]
        
        try:
            data = json.loads(json_data)
            print(f"Загружено {len(data)} записей из таблицы ec9oj_content")
            return data
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}")
            return []
            
    except FileNotFoundError:
        print("Файл joomla_base.json не найден")
        return []
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return []


def filter_property_records(joomla_data):
    """Фильтрует записи недвижимости из данных Joomla"""
    property_records = []
    
    # Категории недвижимости (можно расширить при необходимости)
    property_categories = {
        '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40',
        '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52', '53'
    }
    
    for record in joomla_data:
        # Проверяем что это опубликованная запись и относится к недвижимости
        if (record.get('state') == '1' and 
            record.get('catid') in property_categories and
            record.get('title') and 
            not record.get('title', '').lower().startswith(('политика', 'privacy', 'นโยบาย'))):
            
            property_records.append({
                'id': record.get('id'),
                'title': record.get('title', '').strip(),
                'alias': record.get('alias', ''),
                'catid': record.get('catid'),
                'created': record.get('created'),
                'introtext': record.get('introtext', '')[:100] + '...' if record.get('introtext') else ''
            })
    
    return property_records


def get_django_properties():
    """Получает все объекты недвижимости из Django"""
    properties = Property.objects.all().values('id', 'title', 'legacy_id', 'created_at')
    return list(properties)


def find_matching_property(joomla_record, django_properties):
    """Находит соответствующий объект в Django для записи Joomla"""
    joomla_title = joomla_record['title'].strip()
    
    # Поиск по точному названию
    for django_prop in django_properties:
        if django_prop['title'] and django_prop['title'].strip() == joomla_title:
            return django_prop
    
    # Поиск по части названия (первые 50 символов)
    for django_prop in django_properties:
        if (django_prop['title'] and 
            len(joomla_title) >= 30 and
            joomla_title[:30].lower() in django_prop['title'].lower()):
            return django_prop
    
    # Поиск по ключевым словам
    joomla_words = set(re.findall(r'\b\w{4,}\b', joomla_title.lower()))
    if len(joomla_words) >= 2:
        for django_prop in django_properties:
            if django_prop['title']:
                django_words = set(re.findall(r'\b\w{4,}\b', django_prop['title'].lower()))
                common_words = joomla_words.intersection(django_words)
                if len(common_words) >= 2:
                    return django_prop
    
    return None


def create_comparison_report():
    """Создает сравнительный отчет между Joomla и Django"""
    print("Загружаем данные из Joomla...")
    joomla_data = load_joomla_data()
    
    if not joomla_data:
        print("Не удалось загрузить данные Joomla")
        return
    
    print("Фильтруем записи недвижимости...")
    joomla_properties = filter_property_records(joomla_data)
    
    print("Загружаем данные из Django...")
    django_properties = get_django_properties()
    
    print(f"Найдено в Joomla: {len(joomla_properties)} объектов недвижимости")
    print(f"Найдено в Django: {len(django_properties)} объектов")
    
    # Создаем сравнительный отчет
    comparison_report = {
        "summary": {
            "joomla_total": len(joomla_properties),
            "django_total": len(django_properties),
            "matched": 0,
            "joomla_only": 0,
            "django_only": 0
        },
        "matched_objects": [],
        "joomla_only": [],
        "django_only": []
    }
    
    # Отслеживаем найденные Django объекты
    matched_django_ids = set()
    
    print("Сопоставляем объекты...")
    for joomla_prop in joomla_properties:
        django_match = find_matching_property(joomla_prop, django_properties)
        
        if django_match:
            comparison_report["matched_objects"].append({
                "joomla_id": joomla_prop['id'],
                "joomla_title": joomla_prop['title'],
                "django_id": django_match['id'],
                "django_title": django_match['title'],
                "legacy_id": django_match['legacy_id'],
                "joomla_category": joomla_prop['catid'],
                "match_type": "exact_title" if joomla_prop['title'] == django_match['title'] else "partial_match"
            })
            matched_django_ids.add(django_match['id'])
            comparison_report["summary"]["matched"] += 1
        else:
            comparison_report["joomla_only"].append({
                "joomla_id": joomla_prop['id'],
                "joomla_title": joomla_prop['title'],
                "joomla_category": joomla_prop['catid'],
                "joomla_created": joomla_prop['created'],
                "intro_text": joomla_prop['introtext']
            })
            comparison_report["summary"]["joomla_only"] += 1
    
    # Находим объекты только в Django
    for django_prop in django_properties:
        if django_prop['id'] not in matched_django_ids:
            comparison_report["django_only"].append({
                "django_id": django_prop['id'],
                "django_title": django_prop['title'],
                "legacy_id": django_prop['legacy_id'],
                "django_created": django_prop['created_at'].isoformat() if django_prop['created_at'] else None
            })
            comparison_report["summary"]["django_only"] += 1
    
    # Сохраняем отчет
    with open('joomla_django_comparison.json', 'w', encoding='utf-8') as f:
        json.dump(comparison_report, f, ensure_ascii=False, indent=2, default=str)
    
    # Создаем CSV отчет для удобства
    create_csv_report(comparison_report)
    
    # Выводим статистику
    print("\n" + "="*60)
    print("СРАВНИТЕЛЬНЫЙ АНАЛИЗ JOOMLA ↔ DJANGO")
    print("="*60)
    print(f"📊 Всего объектов в Joomla: {comparison_report['summary']['joomla_total']}")
    print(f"📊 Всего объектов в Django: {comparison_report['summary']['django_total']}")
    print(f"✅ Совпадающих объектов: {comparison_report['summary']['matched']}")
    print(f"🔴 Только в Joomla: {comparison_report['summary']['joomla_only']}")
    print(f"🔵 Только в Django: {comparison_report['summary']['django_only']}")
    
    if comparison_report['summary']['matched'] > 0:
        match_percentage = (comparison_report['summary']['matched'] / 
                          comparison_report['summary']['joomla_total']) * 100
        print(f"📈 Процент совпадений: {match_percentage:.1f}%")
    
    print(f"\n📁 Отчеты сохранены:")
    print(f"   - joomla_django_comparison.json (подробный JSON)")
    print(f"   - joomla_django_comparison.csv (таблица)")


def create_csv_report(comparison_report):
    """Создает CSV отчет для удобного просмотра"""
    import csv
    
    with open('joomla_django_comparison.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Заголовки
        writer.writerow([
            'Status', 'Joomla_ID', 'Joomla_Title', 'Django_ID', 
            'Django_Title', 'Legacy_ID', 'Match_Type', 'Category'
        ])
        
        # Совпадающие объекты
        for item in comparison_report['matched_objects']:
            writer.writerow([
                'MATCHED',
                item['joomla_id'],
                item['joomla_title'],
                item['django_id'],
                item['django_title'],
                item['legacy_id'],
                item['match_type'],
                item['joomla_category']
            ])
        
        # Только в Joomla
        for item in comparison_report['joomla_only']:
            writer.writerow([
                'JOOMLA_ONLY',
                item['joomla_id'],
                item['joomla_title'],
                '',
                '',
                '',
                '',
                item['joomla_category']
            ])
        
        # Только в Django
        for item in comparison_report['django_only']:
            writer.writerow([
                'DJANGO_ONLY',
                '',
                '',
                item['django_id'],
                item['django_title'],
                item['legacy_id'],
                '',
                ''
            ])


if __name__ == '__main__':
    create_comparison_report()