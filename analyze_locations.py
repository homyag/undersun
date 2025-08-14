#!/usr/bin/env python3
"""
Анализ файла underson_bd_dump.json для извлечения локаций
"""
import json
import re
from collections import defaultdict

def analyze_locations():
    """Анализирует файл JSON и извлекает все локации"""
    
    print("Чтение файла JSON...")
    
    with open('underson_bd_dump.json', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("Поиск таблицы категорий...")
    
    # Найдем таблицу категорий - используем более точную регулярку
    categories_start = content.find('{"type":"table","name":"ec9oj_categories"')
    if categories_start == -1:
        print("Не найдена таблица categories")
        return
    
    # Найдем начало данных
    data_start = content.find('"data":[', categories_start)
    if data_start == -1:
        print("Не найдены данные в таблице categories")
        return
    
    data_start += 7  # Пропустим '"data":['
    
    # Найдем конец данных таблицы
    bracket_count = 1
    pos = data_start
    while bracket_count > 0 and pos < len(content):
        if content[pos] == '[':
            bracket_count += 1
        elif content[pos] == ']':
            bracket_count -= 1
        pos += 1
    
    categories_data = content[data_start:pos-1]
    
    # Парсим категории построчно
    categories = []
    
    # Разделим на отдельные записи
    records = []
    current_record = ""
    brace_count = 0
    in_string = False
    escape_next = False
    
    for char in categories_data:
        if escape_next:
            current_record += char
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            current_record += char
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                
        current_record += char
        
        if brace_count == 0 and current_record.strip():
            if current_record.strip().startswith('{'):
                records.append(current_record.strip())
            current_record = ""
    
    print(f"Найдено {len(records)} записей категорий")
    
    # Парсим каждую запись
    for record in records:
        if not record.strip():
            continue
            
        # Убираем завершающую запятую
        record = record.rstrip(',')
        
        try:
            cat_data = json.loads(record)
            if 'id' in cat_data and 'parent_id' in cat_data:
                categories.append({
                    'id': cat_data['id'],
                    'parent_id': cat_data['parent_id'],
                    'title': cat_data.get('title', ''),
                    'alias': cat_data.get('alias', ''),
                    'path': cat_data.get('path', ''),
                    'extension': cat_data.get('extension', '')
                })
        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга записи: {e}")
            continue
    
    print(f"Успешно распарсено {len(categories)} категорий")
    
    # Фильтруем категории недвижимости
    real_estate_categories = []
    for cat in categories:
        if cat['extension'] == 'com_content' and ('real-estate' in cat['path'] or cat['title'] in ['Real estate', 'Mueang Phuket', 'Kathu District', 'Thalang']):
            real_estate_categories.append(cat)
    
    print(f"Найдено {len(real_estate_categories)} категорий недвижимости")
    
    # Создаем структуру локаций
    locations = defaultdict(list)
    
    # Основные районы
    districts = {
        '9': 'Mueang Phuket',
        '14': 'Kathu District', 
        '15': 'Thalang'
    }
    
    print("\nСтруктура локаций:")
    print("=" * 50)
    
    for cat in real_estate_categories:
        # Если это район
        if cat['id'] in districts:
            print(f"\n- District: {cat['title']}")
            
            # Найдем все подкатегории этого района
            subcategories = [c for c in real_estate_categories if c['parent_id'] == cat['id']]
            
            for subcat in subcategories:
                print(f"  - {subcat['title']} ({subcat['alias']})")
                locations[cat['title']].append({
                    'name': subcat['title'],
                    'alias': subcat['alias'],
                    'path': subcat['path'],
                    'id': subcat['id']
                })
    
    # Дополнительная информация
    print("\n" + "=" * 50)
    print("ДЕТАЛЬНЫЙ АНАЛИЗ КАТЕГОРИЙ:")
    print("=" * 50)
    
    for cat in real_estate_categories:
        print(f"ID: {cat['id']}, Parent: {cat['parent_id']}, Title: {cat['title']}, Alias: {cat['alias']}, Path: {cat['path']}")
    
    # Поиск field_id для локации
    print("\n" + "=" * 50)
    print("ПОИСК FIELD_ID ДЛЯ ЛОКАЦИИ:")
    print("=" * 50)
    
    # Найдем таблицу полей
    fields_match = re.search(r'{"type":"table","name":"ec9oj_fields".*?"data":\s*\[(.*?)\]\s*}', content, re.DOTALL)
    if fields_match:
        fields_data = fields_match.group(1)
        location_fields = []
        
        field_pattern = r'{"id":"(\d+)".*?"title":"([^"]+)".*?"name":"([^"]+)".*?"type":"([^"]+)"'
        
        for match in re.finditer(field_pattern, fields_data):
            field = {
                'id': match.group(1),
                'title': match.group(2),
                'name': match.group(3),
                'type': match.group(4)
            }
            if 'location' in field['title'].lower() or 'location' in field['name'].lower():
                location_fields.append(field)
                print(f"Field ID: {field['id']}, Title: {field['title']}, Name: {field['name']}, Type: {field['type']}")
    
    # Найдем таблицу значений полей
    print("\n" + "=" * 50)
    print("ПРИМЕРЫ ЗНАЧЕНИЙ ПОЛЕЙ ЛОКАЦИИ:")
    print("=" * 50)
    
    fields_values_match = re.search(r'{"type":"table","name":"ec9oj_fields_values".*?"data":\s*\[(.*?)\]\s*}', content, re.DOTALL)
    if fields_values_match:
        values_data = fields_values_match.group(1)
        
        # Ищем значения для field_id 17 (Location) и 19 (Location Text)
        location_values = []
        value_pattern = r'{"field_id":"(17|19)","item_id":"(\d+)","value":"([^"]+)"}'
        
        for match in re.finditer(value_pattern, values_data):
            value = {
                'field_id': match.group(1),
                'item_id': match.group(2),
                'value': match.group(3)
            }
            location_values.append(value)
            print(f"Field ID: {value['field_id']}, Item ID: {value['item_id']}, Value: {value['value']}")
    
    # Найдем таблицу контента для понимания связи item_id с категориями
    print("\n" + "=" * 50)
    print("СВЯЗЬ ОБЪЕКТОВ С КАТЕГОРИЯМИ:")
    print("=" * 50)
    
    content_match = re.search(r'{"type":"table","name":"ec9oj_content".*?"data":\s*\[(.*?)\]\s*}', content, re.DOTALL)
    if content_match:
        content_data = content_match.group(1)
        
        # Найдем первые несколько объектов недвижимости
        content_pattern = r'{"id":"(\d+)".*?"title":"([^"]+)".*?"catid":"(\d+)"'
        
        property_items = []
        for match in re.finditer(content_pattern, content_data):
            item = {
                'id': match.group(1),
                'title': match.group(2),
                'catid': match.group(3)
            }
            
            # Найдем категорию
            category = next((c for c in real_estate_categories if c['id'] == item['catid']), None)
            if category:
                property_items.append(item)
                print(f"Property ID: {item['id']}, Title: {item['title']}, Category: {category['title']}")
                
                if len(property_items) >= 10:  # Показать только первые 10
                    break
    
    return locations

if __name__ == "__main__":
    locations = analyze_locations()
    
    print("\n" + "=" * 50)
    print("ФИНАЛЬНЫЙ СПИСОК ЛОКАЦИЙ:")
    print("=" * 50)
    
    for district, places in locations.items():
        print(f"\n- District: {district}")
        for place in places:
            print(f"  - {place['name']}")