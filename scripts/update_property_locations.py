#!/usr/bin/env python3
"""
Скрипт для обновления локаций объектов недвижимости на основе данных из joomla_base.json
"""

import os
import sys
import json
import django
from django.conf import settings

# Добавляем путь к Django проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property
from apps.locations.models import Location, District


def load_joomla_data():
    """Загрузка данных из joomla_base.json"""
    json_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'joomla_base.json')
    
    if not os.path.exists(json_file):
        print(f"Файл {json_file} не найден!")
        return None
    
    print(f"Загружаем данные из {json_file}...")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data


def extract_property_data(joomla_data):
    """Извлечение данных о недвижимости из Joomla"""
    properties_data = {}
    
    # Находим таблицу контента
    content_table = None
    fields_values_table = None
    
    for item in joomla_data:
        if item.get('type') == 'table':
            if item.get('name') == 'ec9oj_content':
                content_table = item.get('data', [])
            elif item.get('name') == 'ec9oj_fields_values':
                fields_values_table = item.get('data', [])
    
    if not content_table:
        print("Таблица ec9oj_content не найдена!")
        return properties_data
    
    if not fields_values_table:
        print("Таблица ec9oj_fields_values не найдена!")
        return properties_data
    
    print(f"Найдено {len(content_table)} записей в таблице контента")
    print(f"Найдено {len(fields_values_table)} значений полей")
    
    # Группируем значения полей по item_id
    field_values_by_item = {}
    for field_value in fields_values_table:
        item_id = field_value.get('item_id')
        field_id = field_value.get('field_id')
        value = field_value.get('value')
        
        if item_id not in field_values_by_item:
            field_values_by_item[item_id] = {}
        
        field_values_by_item[item_id][field_id] = value
    
    # Обрабатываем каждый объект контента
    for content_item in content_table:
        item_id = content_item.get('id')
        title = content_item.get('title', '')
        
        # Проверяем, относится ли это к недвижимости (по категории или другим признакам)
        catid = content_item.get('catid')
        
        # Собираем данные о локации из дополнительных полей
        fields = field_values_by_item.get(item_id, {})
        
        # Ищем поля, связанные с локацией
        location_text = None
        district_name = None
        
        # Проверяем различные field_id для локации и района
        for field_id, value in fields.items():
            # ID полей на основе анализа реальных данных
            if field_id == '103':  # District
                district_name = value
            elif field_id == '19':  # Location Text
                location_text = value
            elif field_id == '17':  # GPS coordinates
                # Сохраняем координаты на будущее
                pass
        
        # Также проверяем основные поля контента
        if not location_text:
            # Иногда локация может быть в introtext или других полях
            introtext = content_item.get('introtext', '')
            if 'район' in introtext.lower() or 'district' in introtext.lower():
                # Парсим район из текста
                pass
        
        properties_data[item_id] = {
            'title': title,
            'catid': catid,
            'location_text': location_text,
            'district_name': district_name,
            'fields': fields
        }
    
    return properties_data


def find_properties_without_location():
    """Поиск объектов недвижимости без локации в Django"""
    properties_without_location = Property.objects.filter(location__isnull=True)
    
    print(f"Найдено {properties_without_location.count()} объектов без локации:")
    
    for prop in properties_without_location:
        print(f"  - ID: {prop.id}, Legacy ID: {prop.legacy_id}, Название: {prop.title}")
    
    return properties_without_location


def match_properties_with_joomla_data(django_properties, joomla_data):
    """Сопоставление объектов Django с данными из Joomla"""
    matches = []
    
    for django_prop in django_properties:
        legacy_id = django_prop.legacy_id
        
        if not legacy_id:
            print(f"Объект {django_prop.title} не имеет legacy_id")
            continue
        
        # Ищем соответствие в данных Joomla
        joomla_match = None
        for joomla_id, joomla_prop in joomla_data.items():
            # Пробуем найти по названию или другим критериям
            if django_prop.title.lower() in joomla_prop['title'].lower() or \
               joomla_prop['title'].lower() in django_prop.title.lower():
                joomla_match = joomla_prop
                break
        
        if joomla_match:
            matches.append({
                'django_property': django_prop,
                'joomla_data': joomla_match
            })
            print(f"Найдено совпадение: {django_prop.title} -> {joomla_match['title']}")
        else:
            print(f"Не найдено совпадение для: {django_prop.title}")
    
    return matches


def update_property_locations(matches):
    """Обновление локаций объектов недвижимости"""
    updated_count = 0
    
    for match in matches:
        django_prop = match['django_property']
        joomla_data = match['joomla_data']
        
        district_name_raw = joomla_data.get('district_name')
        location_text = joomla_data.get('location_text')
        
        # Маппинг районов из Joomla в Django
        district_mapping = {
            'district-karon': 'Карон',
            'district-rawai': 'Равай',
            'district-chalong': 'Чалонг',
            'district-wichit': 'Вичит',
            'district-ratsada': 'Пхукет',
            'district-ko-kaeo': 'Пхукет',
            'district-talad-nuea': 'Пхукет',
            'district-talad-yai': 'Пхукет',
            'district-patong': 'Патонг',
            'district-kamala': 'Камала',
            'district-kathu': 'Kathu',
            'district-thep-krasattri': 'Thalang',
            'district-si-sunthon': 'Thalang',
            'district-cherng-talay': 'Thalang',
            'district-pa-khlok': 'Thalang',
            'district-mai-khao': 'Thalang',
            'district-sakhu': 'Thalang',
        }
        
        # Обрабатываем название района
        district_name = None
        if district_name_raw:
            district_name = district_mapping.get(district_name_raw)
            if not district_name and district_name_raw.startswith('district-'):
                # Если нет в маппинге, пробуем обработать автоматически
                cleaned_name = district_name_raw.replace('district-', '').replace('-', ' ').title()
                district_name = cleaned_name
        
        # Пытаемся найти или создать локацию
        location = None
        
        # Сначала пытаемся найти локацию по текстовому описанию
        if location_text:
            # Ищем существующую локацию
            try:
                location = Location.objects.get(name__icontains=location_text)
            except Location.DoesNotExist:
                # Создаем новую локацию
                if district_name:
                    try:
                        # Ищем район с учетом различных вариантов названий
                        district = None
                        try:
                            district = District.objects.get(name__iexact=district_name)
                        except District.DoesNotExist:
                            # Пробуем найти по частичному совпадению
                            district = District.objects.filter(name__icontains=district_name).first()
                        
                        if district:
                            location = Location.objects.create(
                                name=location_text,
                                district=district
                            )
                            print(f"Создана новая локация: {location_text} в районе {district.name}")
                        else:
                            print(f"Район '{district_name}' не найден в базе данных")
                            continue
                    except Exception as e:
                        print(f"Ошибка при создании локации: {e}")
                        continue
            except Location.MultipleObjectsReturned:
                # Если найдено несколько, берем первую
                location = Location.objects.filter(name__icontains=location_text).first()
        
        # Если не найдена локация по тексту, пытаемся найти хотя бы район
        elif district_name:
            try:
                district = District.objects.get(name__iexact=district_name)
                # Ищем любую локацию в этом районе
                location = Location.objects.filter(district=district).first()
                if location:
                    print(f"Найдена локация в районе {district.name}: {location.name}")
            except District.DoesNotExist:
                # Пробуем найти район по частичному совпадению
                district = District.objects.filter(name__icontains=district_name).first()
                if district:
                    location = Location.objects.filter(district=district).first()
                    if location:
                        print(f"Найдена локация в районе {district.name}: {location.name}")
        
        if location:
            django_prop.location = location
            django_prop.save()
            updated_count += 1
            print(f"Обновлена локация для {django_prop.title}: {location.name}")
        else:
            print(f"Не удалось определить локацию для {django_prop.title}")
    
    print(f"Обновлено {updated_count} объектов")


def main():
    """Основная функция"""
    print("=== Обновление локаций объектов недвижимости ===")
    
    # 1. Загружаем данные из Joomla
    joomla_data = load_joomla_data()
    if not joomla_data:
        return
    
    # 2. Извлекаем данные о недвижимости
    properties_data = extract_property_data(joomla_data)
    print(f"Извлечено {len(properties_data)} объектов недвижимости из Joomla")
    
    # 3. Находим объекты без локации в Django
    django_properties = find_properties_without_location()
    
    # 4. Сопоставляем данные
    matches = match_properties_with_joomla_data(django_properties, properties_data)
    print(f"Найдено {len(matches)} совпадений")
    
    # 5. Обновляем локации
    if matches:
        print(f"Будут обновлены локации для {len(matches)} объектов")
        update_property_locations(matches)
    else:
        print("Нет совпадений для обновления")


if __name__ == '__main__':
    main()