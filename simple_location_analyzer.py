#!/usr/bin/env python3
"""
Простой анализатор локаций из JSON файла
"""
import re
from collections import defaultdict

def analyze_locations():
    """Анализирует файл JSON и извлекает все локации"""
    
    print("Чтение файла JSON...")
    
    with open('underson_bd_dump.json', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("Анализ локаций на основе field_id=19 (Location Text)...")
    
    # Найдем все значения location text
    location_pattern = r'{"field_id":"19","item_id":"(\d+)","value":"([^"]+)"}'
    
    locations = []
    for match in re.finditer(location_pattern, content):
        item_id = match.group(1)
        location_text = match.group(2)
        locations.append({
            'item_id': item_id,
            'location': location_text
        })
    
    print(f"Найдено {len(locations)} локаций")
    
    # Анализируем и группируем локации
    location_groups = defaultdict(list)
    
    # Известные районы и их подрайоны
    districts = {
        'Mueang Phuket': ['Chalong', 'Karon', 'Kata', 'Rawai', 'Wichit', 'Ratsada', 'Talad Nuea', 'Talad Yai', 'Ko Kaeo'],
        'Kathu District': ['Patong', 'Kamala', 'Kathu'],
        'Thalang': ['Cherng Talay', 'Cherngtalay', 'Choeng Thale', 'Bang Tao', 'Bangtao', 'Layan', 'Surin', 'Mai Khao', 'Maikhao', 'Nai Yang', 'Naiyang', 'Nai Thon', 'Sakhu', 'Si Sunthon', 'Thep Krasatti', 'Pa Khlok']
    }
    
    # Альтернативные написания
    location_mapping = {
        'Choeng Thale': 'Cherng Talay',
        'Cherngtalay': 'Cherng Talay',
        'Bangtao': 'Bang Tao',
        'Maikhao': 'Mai Khao',
        'Naiyang': 'Nai Yang',
        'Thep Krasasttri': 'Thep Krasatti',
        'Thep Krasattri': 'Thep Krasatti',
        'Ko Pu': 'Ko Kaeo',
        'Koh Kaew': 'Ko Kaeo',
        'Koh Keaw': 'Ko Kaeo',
        'Kata': 'Karon',  # Kata часто является частью Karon
        'Pa Tong': 'Patong',
        'Cherntalay': 'Cherng Talay',
        'Khok Tanote': 'Khok Tanot',
        'Khok Tanot': 'Cherng Talay',  # Khok Tanot является частью Cherng Talay
        'Laguna': 'Cherng Talay',
        'Had Surin': 'Surin',
        'Pa Sak': 'Cherng Talay',
        'Cape Yamu': 'Ko Kaeo',
        'Tapepratarn': 'Ratsada',
        'Bang Thao Nok': 'Bang Tao'
    }
    
    # Группируем локации по районам
    unique_locations = set()
    location_groups = defaultdict(set)  # Используем set вместо list
    
    for loc in locations:
        location_text = loc['location']
        
        # Извлекаем название локации из текста
        found_location = None
        found_district = None
        
        # Сначала проверим прямые совпадения
        for district, places in districts.items():
            for place in places:
                if place.lower() in location_text.lower():
                    found_location = place
                    found_district = district
                    break
            if found_location:
                break
        
        # Если не найдено, проверим альтернативные написания
        if not found_location:
            for alt_name, real_name in location_mapping.items():
                if alt_name.lower() in location_text.lower():
                    found_location = real_name
                    # Найдем район для этой локации
                    for district, places in districts.items():
                        if real_name in places:
                            found_district = district
                            break
                    break
        
        # Если всё еще не найдено, попробуем извлечь из текста
        if not found_location:
            # Попробуем найти по ключевым словам
            text_lower = location_text.lower()
            
            # Проверим district keywords
            if 'mueang phuket' in text_lower or 'capital amphe' in text_lower:
                found_district = 'Mueang Phuket'
            elif 'kathu district' in text_lower:
                found_district = 'Kathu District'
            elif 'thalang district' in text_lower:
                found_district = 'Thalang'
            
            # Попробуем извлечь конкретную локацию
            words = location_text.split(',')
            if len(words) > 0:
                first_word = words[0].strip()
                if first_word and not first_word.lower() in ['phuket', 'thailand', 'chang wat']:
                    found_location = first_word
        
        if found_location and found_district:
            location_groups[found_district].add(found_location)
            unique_locations.add(f"{found_district}::{found_location}")
        
        # Сохраняем пример для отладки
        if len(unique_locations) <= 5:
            print(f"Пример: {location_text} -> {found_district}::{found_location}")
    
    print(f"\nВсего уникальных локаций: {len(unique_locations)}")
    
    # Выводим структуру
    print("\n" + "=" * 60)
    print("СТРУКТУРА ЛОКАЦИЙ ПХУКЕТА:")
    print("=" * 60)
    
    for district in sorted(location_groups.keys()):
        print(f"\n- District: {district}")
        for location in sorted(location_groups[district]):
            print(f"  - {location}")
    
    # Покажем также сырые данные для дополнительного анализа
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ СЫРЫХ ДАННЫХ ЛОКАЦИЙ:")
    print("=" * 60)
    
    sample_locations = locations[:30]  # Первые 30 записей
    for i, loc in enumerate(sample_locations):
        print(f"{i+1:2d}. ID: {loc['item_id']}, Location: {loc['location']}")
    
    return location_groups

if __name__ == "__main__":
    locations = analyze_locations()
    
    print("\n" + "=" * 60)
    print("ФИНАЛЬНЫЙ СПИСОК ЛОКАЦИЙ:")
    print("=" * 60)
    
    for district, places in locations.items():
        print(f"\n- District: {district}")
        for place in sorted(places):
            print(f"  - {place}")