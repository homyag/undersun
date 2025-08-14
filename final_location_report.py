#!/usr/bin/env python3
"""
Финальный отчет по локациям Пхукета
"""
import re
from collections import defaultdict

def create_final_report():
    """Создает финальный отчет по локациям"""
    
    print("Создание финального отчета по локациям Пхукета...")
    
    with open('underson_bd_dump.json', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Извлекаем данные о локациях
    location_pattern = r'{"field_id":"19","item_id":"(\d+)","value":"([^"]+)"}'
    locations = []
    
    for match in re.finditer(location_pattern, content):
        locations.append({
            'item_id': match.group(1),
            'location': match.group(2)
        })
    
    print(f"Найдено {len(locations)} записей о локациях")
    
    # Определяем финальную структуру локаций
    final_locations = {
        'Mueang Phuket': [
            'Chalong',
            'Karon', 
            'Kata',
            'Ko Kaeo',
            'Rawai',
            'Ratsada',
            'Talad Nuea',
            'Talad Yai',
            'Wichit'
        ],
        'Kathu District': [
            'Kamala',
            'Kathu',
            'Patong'
        ],
        'Thalang': [
            'Bang Tao',
            'Cherng Talay',
            'Choeng Thale',
            'Layan',
            'Mai Khao',
            'Nai Yang',
            'Nai Thon',
            'Pa Khlok',
            'Sakhu',
            'Si Sunthon',
            'Surin',
            'Thep Krasatti'
        ]
    }
    
    # Статистика по локациям
    location_stats = defaultdict(int)
    
    for loc in locations:
        location_text = loc['location'].lower()
        
        for district, places in final_locations.items():
            for place in places:
                if place.lower() in location_text:
                    location_stats[f"{district}::{place}"] += 1
                    break
    
    print("\n" + "=" * 80)
    print("ПОЛНЫЙ АНАЛИЗ ЛОКАЦИЙ ПХУКЕТА")
    print("=" * 80)
    print("\nНа основе анализа файла underson_bd_dump.json была выявлена")
    print("следующая структура локаций внутри районов Пхукета:")
    print("\n" + "=" * 80)
    
    total_locations = 0
    
    for district, places in final_locations.items():
        print(f"\n- District: {district}")
        district_total = 0
        
        for place in places:
            count = location_stats.get(f"{district}::{place}", 0)
            district_total += count
            print(f"  - {place} ({count} объектов)")
        
        print(f"  Всего в районе: {district_total} объектов")
        total_locations += district_total
    
    print(f"\n" + "=" * 80)
    print(f"ИТОГО: {total_locations} объектов недвижимости с указанием локации")
    print(f"Всего уникальных локаций: {sum(len(places) for places in final_locations.values())}")
    print("=" * 80)
    
    # Информация о полях
    print("\nИНФОРМАЦИЯ О ПОЛЯХ ЛОКАЦИИ:")
    print("-" * 40)
    print("field_id = 17: Location (координаты)")
    print("field_id = 19: Location Text (текстовое описание)")
    print("field_id = 64: Activity Location (для активностей)")
    
    print("\nСПОСОБ ОПРЕДЕЛЕНИЯ ЛОКАЦИИ В ДАННЫХ:")
    print("-" * 40)
    print("Локация объекта недвижимости определяется:")
    print("1. Через поле field_id = 19 (Location Text)")
    print("2. Через связь с категорией (catid)")
    print("3. Координаты в поле field_id = 17 (Location)")
    
    # Создаем структуру для использования в Django
    print("\n" + "=" * 80)
    print("СТРУКТУРА ДЛЯ РЕАЛИЗАЦИИ В DJANGO:")
    print("=" * 80)
    
    django_structure = """
# Модель для районов и локаций
class District(models.Model):
    name = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    name_ru = models.CharField(max_length=100)
    name_th = models.CharField(max_length=100)
    
class Location(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    name_ru = models.CharField(max_length=100)
    name_th = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

# Связь с недвижимостью
class Property(models.Model):
    # ... другие поля ...
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True)
    """
    
    print(django_structure)
    
    return final_locations

if __name__ == "__main__":
    locations = create_final_report()
    
    print("\n" + "=" * 80)
    print("КРАТКИЙ СПИСОК ЛОКАЦИЙ:")
    print("=" * 80)
    
    for district, places in locations.items():
        print(f"\n- District: {district}")
        for place in places:
            print(f"  - {place}")
    
    print(f"\n" + "=" * 80)
    print("ОТЧЕТ ЗАВЕРШЕН")
    print("=" * 80)