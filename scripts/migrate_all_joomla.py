#!/usr/bin/env python
"""
Скрипт массовой миграции всех объектов недвижимости из Joomla в Django
Анализирует joomla_base.json и мигрирует все найденные объекты
"""

import os
import sys
import json
import django
from decimal import Decimal, InvalidOperation
from django.utils.text import slugify
from django.db import transaction
import re

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property, PropertyType, PropertyImage, PropertyFeature, PropertyFeatureRelation
from apps.locations.models import District, Location

# Маппинг полей из Joomla в Django
FIELD_MAPPINGS = {
    # Основные поля контента
    'title': 'title',
    'alias': 'slug',
    'introtext': 'description',
    'fulltext': 'full_description',
    
    # Кастомные поля (по field_id)
    '100': 'legacy_id',        # CN169, VS82, etc.
    '101': 'offer_type',       # type-buy, type-rent
    '102': 'property_type',    # type-villa, type-condo, etc.
    '103': 'district_code',    # district-karon, etc.
    '104': 'completion_status', # status-off-plan, etc.
    '66': 'price_thb',         # Цена в THB
    '91': 'price_usd',         # Цена в USD
    '93': 'bedrooms',          # Количество спален
    '94': 'bathrooms',         # Количество ванных
    '92': 'area_total',        # Площадь в м²
    '17': 'coordinates',       # Координаты lat,lng
    '19': 'location_text',     # Текстовое описание локации
    '3': 'images_json',        # JSON с изображениями
    '6': 'amenities',          # Удобства (множественное поле)
    '7': 'features',           # Характеристики
}

# Маппинг типов сделок
DEAL_TYPE_MAPPING = {
    'type-buy': 'sale',
    'type-rent': 'rent',
    'type-sale': 'sale',
}

# Маппинг типов недвижимости
PROPERTY_TYPE_MAPPING = {
    'type-villa': 'villa',
    'type-condo': 'apartment',
    'type-apartment': 'apartment',
    'type-townhouse': 'townhouse',
    'type-land': 'land',
    'type-business': 'business',
    'type-investment': 'investment',
}

# Маппинг районов
DISTRICT_MAPPING = {
    'district-karon': 'Карон',
    'district-kata': 'Ката',
    'district-patong': 'Патонг',
    'district-kamala': 'Камала',
    'district-rawai': 'Равай',
    'district-chalong': 'Чалонг',
    'district-thalang': 'Таланг',
    'district-wichit': 'Вичит',
}

# Маппинг удобств в булевые поля
AMENITY_BOOLEAN_MAPPING = {
    'Pool': 'pool',
    'Free Parking': 'parking',
    'Security': 'security',
    'Gym': 'gym',
}

def load_joomla_data():
    """Загрузка данных из joomla_base.json"""
    print("Загрузка данных из joomla_base.json...")
    
    try:
        with open('joomla_base.json', 'r', encoding='utf-8') as f:
            # Это структурированный JSON экспорт PHPMyAdmin
            full_data = json.load(f)
        
        # Извлекаем все данные из всех таблиц
        all_records = []
        
        if isinstance(full_data, list):
            for item in full_data:
                if isinstance(item, dict):
                    # Ищем таблицы с данными
                    if item.get('type') == 'table' and 'data' in item:
                        table_name = item.get('name', '')
                        table_data = item.get('data', [])
                        
                        # Добавляем информацию о таблице к каждой записи
                        for record in table_data:
                            if isinstance(record, dict):
                                record['_table'] = table_name
                                all_records.append(record)
                        
                        print(f"Таблица {table_name}: {len(table_data)} записей")
        
        print(f"Всего загружено {len(all_records)} записей из всех таблиц")
        return all_records
        
    except FileNotFoundError:
        print("❌ Файл joomla_base.json не найден!")
        return []
    except Exception as e:
        print(f"❌ Ошибка при загрузке данных: {e}")
        return []

def extract_content_objects(data):
    """Извлечение объектов контента (статей)"""
    print("Извлечение объектов контента...")
    
    content_objects = []
    field_values = {}
    
    # Разделяем данные на контент и значения полей по таблицам
    for item in data:
        table_name = item.get('_table', '')
        
        # Таблица контента (статьи недвижимости)
        if table_name == 'ec9oj_content' and 'title' in item and 'alias' in item:
            content_objects.append(item)
            
        # Таблица значений кастомных полей
        elif table_name == 'ec9oj_fields_values' and 'field_id' in item and 'item_id' in item and 'value' in item:
            item_id = item['item_id']
            field_id = item['field_id']
            
            if item_id not in field_values:
                field_values[item_id] = {}
            
            # Обрабатываем множественные значения (например, удобства)
            if field_id in field_values[item_id]:
                # Если поле уже существует, делаем его списком
                if not isinstance(field_values[item_id][field_id], list):
                    field_values[item_id][field_id] = [field_values[item_id][field_id]]
                field_values[item_id][field_id].append(item['value'])
            else:
                field_values[item_id][field_id] = item['value']
    
    print(f"Найдено {len(content_objects)} объектов контента из ec9oj_content")
    print(f"Найдено значений полей для {len(field_values)} объектов из ec9oj_fields_values")
    
    return content_objects, field_values

def filter_real_estate_objects(content_objects, field_values):
    """Фильтрация объектов недвижимости"""
    print("Фильтрация объектов недвижимости...")
    
    real_estate_objects = []
    
    for obj in content_objects:
        obj_id = obj.get('id')
        note = obj.get('note', '')
        
        # Проверяем, есть ли у объекта legacy_id (поле 100)
        if obj_id in field_values and '100' in field_values[obj_id]:
            legacy_id = field_values[obj_id]['100']
            if legacy_id and legacy_id.strip():
                # Объединяем данные контента с кастомными полями
                combined_obj = {
                    **obj,
                    'custom_fields': field_values[obj_id]
                }
                real_estate_objects.append(combined_obj)
    
    print(f"Найдено {len(real_estate_objects)} объектов недвижимости с legacy_id")
    return real_estate_objects

def parse_property_data(obj):
    """Парсинг данных объекта недвижимости"""
    custom_fields = obj.get('custom_fields', {})
    
    # Извлекаем основные данные
    property_data = {
        'title': obj.get('title', '').strip(),
        'slug': slugify(obj.get('alias', ''))[:50],
        'description': obj.get('introtext', '').strip(),
        'legacy_id': custom_fields.get('100', '').strip(),
        'is_active': obj.get('state') == '1',
    }
    
    # Парсим координаты
    coordinates = custom_fields.get('17', '')
    if coordinates and ',' in coordinates:
        try:
            lat, lng = coordinates.split(',')
            property_data['latitude'] = Decimal(lat.strip())
            property_data['longitude'] = Decimal(lng.strip())
        except (ValueError, InvalidOperation):
            pass
    
    # Парсим цену
    price_thb = custom_fields.get('66', '')
    if price_thb:
        try:
            property_data['price_sale_thb'] = Decimal(str(price_thb).replace(',', ''))
            # Примерный курс USD
            property_data['price_sale_usd'] = property_data['price_sale_thb'] / 33
        except (ValueError, InvalidOperation):
            pass
    
    # Парсим количественные характеристики
    for field_id, field_name in [('93', 'bedrooms'), ('94', 'bathrooms'), ('92', 'area_total')]:
        value = custom_fields.get(field_id, '')
        if value:
            try:
                property_data[field_name] = int(float(str(value).replace(',', '')))
            except (ValueError, InvalidOperation):
                pass
    
    # Определяем тип сделки
    offer_type = custom_fields.get('101', '')
    property_data['deal_type'] = DEAL_TYPE_MAPPING.get(offer_type, 'sale')
    
    # Определяем тип недвижимости
    prop_type = custom_fields.get('102', '')
    property_data['property_type_name'] = PROPERTY_TYPE_MAPPING.get(prop_type, 'apartment')
    
    # Определяем район
    district_code = custom_fields.get('103', '')
    property_data['district_name'] = DISTRICT_MAPPING.get(district_code, 'Пхукет')
    
    # Парсим удобства
    amenities = custom_fields.get('6', [])
    if not isinstance(amenities, list):
        amenities = [amenities] if amenities else []
    
    # Извлекаем названия удобств из путей к иконкам
    amenity_names = []
    boolean_amenities = {}
    
    for amenity in amenities:
        if isinstance(amenity, str):
            # Извлекаем название из пути к иконке
            if 'icon-' in amenity:
                name = amenity.split('icon-')[-1].replace('.svg', '').replace('-', ' ').title()
                amenity_names.append(name)
                
                # Проверяем булевые удобства
                for amenity_key, field_name in AMENITY_BOOLEAN_MAPPING.items():
                    if amenity_key.lower().replace(' ', '-') in amenity.lower():
                        boolean_amenities[field_name] = True
    
    property_data['amenities'] = amenity_names
    property_data.update(boolean_amenities)
    
    # Устанавливаем furnished=True если есть кухонные удобства
    kitchen_indicators = ['kitchen', 'microwave', 'dishwasher', 'tv', 'workplace']
    if any(indicator in ' '.join(amenity_names).lower() for indicator in kitchen_indicators):
        property_data['furnished'] = True
    
    # Другие поля
    property_data['address'] = custom_fields.get('19', '')[:200]
    property_data['complex_name'] = obj.get('title', '').split(' at ')[-1] if ' at ' in obj.get('title', '') else ''
    property_data['complex_name'] = property_data['complex_name'][:100]
    
    return property_data

def create_property_in_django(property_data):
    """Создание объекта недвижимости в Django"""
    try:
        # Проверяем существование объекта
        legacy_id = property_data.get('legacy_id')
        if not legacy_id:
            return None, "Нет legacy_id"
        
        if Property.objects.filter(legacy_id=legacy_id).exists():
            return None, f"Объект {legacy_id} уже существует"
        
        # Получаем/создаем тип недвижимости
        property_type_name = property_data.get('property_type_name', 'apartment')
        property_type, _ = PropertyType.objects.get_or_create(
            name=property_type_name,
            defaults={'name_display': property_type_name.title()}
        )
        
        # Получаем/создаем район
        district_name = property_data.get('district_name', 'Пхукет')
        
        # Создаем корректный slug для района
        if district_name and district_name.strip():
            district_slug = slugify(district_name)
            if not district_slug:  # Если slugify дает пустую строку
                district_slug = 'unknown-district'
        else:
            district_name = 'Пхукет'
            district_slug = 'phuket'
        
        # Ищем существующий район по имени
        try:
            district = District.objects.get(name=district_name)
        except District.DoesNotExist:
            # Создаем новый район с уникальным slug
            base_slug = district_slug
            counter = 1
            while District.objects.filter(slug=district_slug).exists():
                district_slug = f"{base_slug}-{counter}"
                counter += 1
            
            district = District.objects.create(
                name=district_name,
                name_en=district_name, 
                name_th=district_name,
                slug=district_slug
            )
        
        # Создаем объект недвижимости
        property_obj = Property.objects.create(
            title=property_data.get('title', '')[:200],
            slug=property_data.get('slug', slugify(legacy_id))[:50],
            property_type=property_type,
            deal_type=property_data.get('deal_type', 'sale'),
            status='available',
            legacy_id=legacy_id,
            description=property_data.get('description', '')[:1000],
            district=district,
            address=property_data.get('address', '')[:200],
            latitude=property_data.get('latitude'),
            longitude=property_data.get('longitude'),
            bedrooms=property_data.get('bedrooms'),
            bathrooms=property_data.get('bathrooms'),
            area_total=property_data.get('area_total'),
            price_sale_thb=property_data.get('price_sale_thb'),
            price_sale_usd=property_data.get('price_sale_usd'),
            complex_name=property_data.get('complex_name', ''),
            furnished=property_data.get('furnished', False),
            pool=property_data.get('pool', False),
            parking=property_data.get('parking', False),
            security=property_data.get('security', False),
            gym=property_data.get('gym', False),
            is_active=property_data.get('is_active', True),
        )
        
        # Создаем характеристики (amenities)
        amenities = property_data.get('amenities', [])
        created_features = 0
        
        for amenity_name in amenities:
            if amenity_name and amenity_name.strip():
                feature, _ = PropertyFeature.objects.get_or_create(
                    name=amenity_name.strip(),
                    defaults={'icon': f'icon-{amenity_name.lower().replace(" ", "-")}'}
                )
                
                PropertyFeatureRelation.objects.get_or_create(
                    property=property_obj,
                    feature=feature
                )
                created_features += 1
        
        return property_obj, f"Создано с {created_features} характеристиками"
        
    except Exception as e:
        return None, f"Ошибка: {str(e)}"

def migrate_all_properties():
    """Массовая миграция всех объектов"""
    print("=" * 60)
    print("МАССОВАЯ МИГРАЦИЯ ОБЪЕКТОВ ИЗ JOOMLA В DJANGO")
    print("=" * 60)
    print()
    
    # Загружаем данные
    data = load_joomla_data()
    if not data:
        return
    
    # Извлекаем объекты контента
    content_objects, field_values = extract_content_objects(data)
    
    # Фильтруем объекты недвижимости
    real_estate_objects = filter_real_estate_objects(content_objects, field_values)
    
    if not real_estate_objects:
        print("❌ Объекты недвижимости не найдены")
        return
    
    print(f"Начинаем миграцию {len(real_estate_objects)} объектов...")
    print()
    
    # Статистика
    stats = {
        'created': 0,
        'skipped': 0,
        'errors': 0,
        'total': len(real_estate_objects)
    }
    
    # Мигрируем объекты
    for i, obj in enumerate(real_estate_objects, 1):
        # Парсим данные объекта
        property_data = parse_property_data(obj)
        legacy_id = property_data.get('legacy_id', f'UNKNOWN_{i}')
        
        print(f"[{i}/{stats['total']}] Миграция {legacy_id}...", end=' ')
        
        # Создаем объект в Django
        with transaction.atomic():
            property_obj, message = create_property_in_django(property_data)
        
        if property_obj:
            print(f"✓ {message}")
            stats['created'] += 1
        elif "уже существует" in message:
            print(f"⚠️ {message}")
            stats['skipped'] += 1
        else:
            print(f"❌ {message}")
            stats['errors'] += 1
    
    # Выводим статистику
    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТЫ МИГРАЦИИ")
    print("=" * 60)
    print(f"Всего объектов: {stats['total']}")
    print(f"Создано: {stats['created']}")
    print(f"Пропущено (уже существуют): {stats['skipped']}")
    print(f"Ошибок: {stats['errors']}")
    print()
    
    if stats['created'] > 0:
        print("🎉 МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print(f"Создано {stats['created']} новых объектов недвижимости")
        print()
        print("Объекты доступны в админ-панели:")
        print("http://localhost:8000/admin/properties/property/")
    else:
        print("ℹ️ Новые объекты не были созданы")

def main():
    """Основная функция"""
    try:
        migrate_all_properties()
    except KeyboardInterrupt:
        print("\n❌ Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")

if __name__ == '__main__':
    main()