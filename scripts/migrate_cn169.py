#!/usr/bin/env python
"""
Скрипт миграции объекта CN169 из Joomla в Django систему
Анализирует найденные характеристики и сопоставляет их с текущей моделью Property
"""

import os
import sys
import json
import django
from decimal import Decimal
from django.utils.text import slugify

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property, PropertyType, PropertyImage, PropertyFeature, PropertyFeatureRelation
from apps.locations.models import District, Location

def analyze_cn169_data():
    """Анализ найденных данных объекта CN169"""
    print("=== АНАЛИЗ ОБЪЕКТА CN169 ===")
    print()
    
    # Данные из найденного объекта
    cn169_data = {
        "id": "1110",
        "title": "2 Bedroom Apartment in Kata Area, Phuket at Kata View Complex",
        "alias": "2-bedroom-apartment-in-kata-area-phuket-at-kata-view-complex",
        "legacy_id": "CN169",
        "offer_type": "Buy", 
        "real_estate_type": "Condo",
        "district": "Karon",
        "completion_status": "Off-plan",
        "price_thb": 8197200,
        "bedrooms": 2,
        "bathrooms": 2,
        "size_sqm": 66,
        "coordinates": "7.820942999999998,98.308938",
        "location_text": "Karon, Phuket, Thailand",
        "complex_name": "Kata View Complex",
        "amenities": [
            "Air Conditioning==Кондиционер==เครื่องปรับอากาศ==空调",
            "WiFi==WiFi==WiFi==WiFi",
            "Pool==Бассейн==สระว่ายน้ำ==泳池",
            "Kitchen==Кухня==ครัว==厨房",
            "Microwave==Микроволновая печь==เครื่องอบปานกาว==微波炉",
            "Dishwasher==Посудомоечная машина==เครื่องซักขวาง==洗碗机",
            "Washer==Стиральная машина==เครื่องซักผ้า==洗衣机",
            "Sauna==Сауна==ซาวน่า==桑拿",
            "Coffee Maker==Кофеварка==เครื่องชงกาแฟ==咖啡机",
            "TV==Телевизор==ทีวี==电视",
            "Workplace==Рабочее место==สถานที่ทำงาน==工作场所",
            "Fireplace==Камин==พื้นไฟ==壁炉",
            "Gym==Тренажерный зал==ฟิตเนส==健身房",
            "Free Parking==Бесплатная парковка==ที่จอดรถฟรี==免费停车场",
            "BBQ Zone==Зона барбекю==พื้นที่ปิ้งย่าง==烧烤区",
            "Bathtub==Ванна==อ่างอาบน้ำ==浴缸",
            "Shower==Душ==ฝ่ายอาบน้ำ==淋浴",
            "Elevator==Лифт==ลิฟต์==電梯",
            "Pets Welcome==Можно с животными==สัตว์เลี้ยงที่ได้รับอนุญาต==可带宠物",
            "Non Smoking==Курение запрещено==ห้ามสูบบุหรี่==禁止抽烟",
            "Garage==Гараж==ห้องปรับรถ==车库",
            "Balcony==Балкон==ระเบียง==阳台",
            "Fenced area==Огороженная территория==พื้นที่ตั้งค่ารั้ว==围栏区域",
            "Video surveillance==Видеонаблюдение==การตรวจสอบภาพวีดีโอ==视频监控",
            "Security==Охрана==ความปลอดภัย==安全",
            "Safe==Сейф==ตู้เซฟ==保险柜"
        ],
        "images": [
            "images/Kata_View/11_Room_image_5.jpg",
            "images/Kata_View/07_Room_image_1.jpg",
            "images/Kata_View/08_Room_image_2.jpg",
            "images/Kata_View/09_Room_image_3.jpg",
            "images/Kata_View/10_Room_image_4.jpg",
            "images/Kata_View/06_Lobby.jpg",
            "images/Kata_View/04_Pool.jpg",
            "images/Kata_View/05_Pool_2.jpg",
            "images/Kata_View/01_Roof_Top.jpg",
            "images/Kata_View/02_Building.jpg",
            "images/Kata_View/03_Building_and_entrance_.jpg",
            "images/Kata_View/A6.jpg"
        ]
    }
    
    print("Основные характеристики:")
    print(f"- ID: {cn169_data['legacy_id']}")
    print(f"- Название: {cn169_data['title']}")
    print(f"- Тип сделки: {cn169_data['offer_type']}")
    print(f"- Тип недвижимости: {cn169_data['real_estate_type']}")
    print(f"- Район: {cn169_data['district']}")
    print(f"- Статус готовности: {cn169_data['completion_status']}")
    print(f"- Цена (THB): {cn169_data['price_thb']:,}")
    print(f"- Спальни: {cn169_data['bedrooms']}")
    print(f"- Ванные: {cn169_data['bathrooms']}")
    print(f"- Площадь (м²): {cn169_data['size_sqm']}")
    print(f"- Координаты: {cn169_data['coordinates']}")
    print(f"- Комплекс: {cn169_data['complex_name']}")
    print(f"- Количество изображений: {len(cn169_data['images'])}")
    print(f"- Количество удобств: {len(cn169_data['amenities'])}")
    print()
    
    return cn169_data

def check_model_compatibility(cn169_data):
    """Проверка совместимости с текущей моделью Property"""
    print("=== АНАЛИЗ СОВМЕСТИМОСТИ С МОДЕЛЬЮ PROPERTY ===")
    print()
    
    # Проверяем какие поля можем заполнить напрямую
    direct_mapping = {
        'title': cn169_data['title'],
        'slug': slugify(cn169_data['alias']),
        'legacy_id': cn169_data['legacy_id'],
        'deal_type': 'sale',  # CN169 - Buy
        'status': 'available',
        'bedrooms': cn169_data['bedrooms'],
        'bathrooms': cn169_data['bathrooms'],
        'area_total': Decimal(str(cn169_data['size_sqm'])),
        'price_sale_thb': Decimal(str(cn169_data['price_thb'])),
        'complex_name': cn169_data['complex_name'],
        'is_active': True,
    }
    
    # Работа с координатами
    if cn169_data['coordinates']:
        lat, lng = cn169_data['coordinates'].split(',')
        direct_mapping['latitude'] = Decimal(lat.strip())
        direct_mapping['longitude'] = Decimal(lng.strip())
    
    print("Поля, которые можно заполнить напрямую:")
    for field, value in direct_mapping.items():
        print(f"- {field}: {value}")
    print()
    
    # Поля, требующие дополнительной обработки
    needs_processing = {
        'property_type': f"Нужно найти/создать тип 'condo' вместо 'apartment'",
        'district': f"Нужно найти/создать район 'Karon' (указан в данных)",
        'location': f"Нужно создать локацию из '{cn169_data['location_text']}'",
        'description': "Нужно извлечь из Joomla поля introtext/fulltext",
        'amenities': f"Нужно обработать {len(cn169_data['amenities'])} удобств",
        'images': f"Нужно создать {len(cn169_data['images'])} изображений",
        'price_sale_usd': "Можно вычислить из THB (курс ~32-35)",
        'furnished': "Судя по удобствам - с мебелью",
        'pool': "Есть в списке удобств",
        'parking': "Есть в списке удобств",
        'security': "Есть в списке удобств",
        'gym': "Есть в списке удобств",
    }
    
    print("Поля, требующие дополнительной обработки:")
    for field, note in needs_processing.items():
        print(f"- {field}: {note}")
    print()
    
    # Отсутствующие в исходных данных
    missing_fields = [
        'area_living', 'area_land', 'floor', 'floors_total',
        'price_rent_monthly', 'developer', 'year_built',
        'pool_area', 'original_price_thb', 'is_urgent_sale',
        'architectural_style', 'material_type', 'investment_potential',
        'suitable_for', 'distance_to_beach', 'distance_to_airport',
        'distance_to_school'
    ]
    
    print("Поля, отсутствующие в исходных данных (останутся пустыми):")
    for field in missing_fields:
        print(f"- {field}")
    print()
    
    return direct_mapping, needs_processing

def analyze_amenities_mapping():
    """Анализ маппинга удобств"""
    print("=== АНАЛИЗ УДОБСТВ (AMENITIES) ===")
    print()
    
    # Удобства, которые можно напрямую смапить в булевые поля модели
    boolean_mappings = {
        'Pool': 'pool',
        'Free Parking': 'parking', 
        'Security': 'security',
        'Gym': 'gym',
    }
    
    # Удобства, которые указывают на меблированность
    furniture_indicators = [
        'Kitchen', 'Microwave', 'Dishwasher', 'Washer', 
        'Coffee Maker', 'TV', 'Workplace', 'Fireplace'
    ]
    
    # Удобства, которые нужно создать как PropertyFeature
    feature_amenities = [
        'Air Conditioning', 'WiFi', 'Sauna', 'Bathtub', 'Shower',
        'Elevator', 'Pets Welcome', 'Non Smoking', 'Garage',
        'Balcony', 'Fenced area', 'Video surveillance', 'Safe',
        'BBQ Zone'
    ]
    
    print("Удобства → булевые поля модели:")
    for amenity, field in boolean_mappings.items():
        print(f"- {amenity} → {field}")
    print()
    
    print("Удобства, указывающие на меблированность (furnished=True):")
    for amenity in furniture_indicators:
        print(f"- {amenity}")
    print()
    
    print("Удобства для создания PropertyFeature:")
    for amenity in feature_amenities:
        print(f"- {amenity}")
    print()

def create_migration_django_object():
    """Создание объекта в Django"""
    print("=== СОЗДАНИЕ ОБЪЕКТА В DJANGO ===")
    print()
    
    # Данные объекта
    cn169_data = analyze_cn169_data()
    
    try:
        # 1. Проверяем существование типа недвижимости
        try:
            property_type = PropertyType.objects.get(name='apartment')
            print(f"✓ Найден тип недвижимости: {property_type}")
        except PropertyType.DoesNotExist:
            # Создаем тип "apartment" если его нет
            property_type = PropertyType.objects.create(
                name='apartment',
                name_display='Апартаменты'
            )
            print(f"✓ Создан тип недвижимости: {property_type}")
        
        # 2. Проверяем существование района
        try:
            district = District.objects.get(name_en__icontains='karon')
            print(f"✓ Найден район: {district}")
        except District.DoesNotExist:
            # Создаем район если его нет
            district = District.objects.create(
                name='Карон',
                name_en='Karon',
                name_th='กะรน'
            )
            print(f"✓ Создан район: {district}")
        
        # 3. Создаем локацию если её нет
        location, created = Location.objects.get_or_create(
            name_en__icontains='kata',
            district=district,
            defaults={
                'name': 'Ката',
                'name_en': 'Kata',
                'name_th': 'กะตะ'
            }
        )
        if created:
            print(f"✓ Создана локация: {location}")
        else:
            print(f"✓ Найдена локация: {location}")
        
        # 4. Проверяем существование объекта
        if Property.objects.filter(legacy_id='CN169').exists():
            print("⚠️ Объект CN169 уже существует в базе данных")
            property_obj = Property.objects.get(legacy_id='CN169')
            print(f"   Существующий объект: {property_obj}")
        else:
            # 5. Создаем объект недвижимости
            lat, lng = cn169_data['coordinates'].split(',')
            
            # Обрезаем длинные поля для соответствия ограничениям модели
            title = cn169_data['title'][:200]  # max_length=200
            short_slug = slugify(cn169_data['alias'])[:50]  # для slug
            
            property_obj = Property.objects.create(
                title=title,
                slug=short_slug,
                property_type=property_type,
                deal_type='sale',
                status='available',
                legacy_id=cn169_data['legacy_id'],
                description="2 Bedroom apartment in a residential complex Kata View 5 minutes from Kata Beach, Phuket.",
                district=district,
                location=location,
                address=cn169_data['location_text'][:200],  # max_length=200
                latitude=Decimal(lat.strip()),
                longitude=Decimal(lng.strip()),
                bedrooms=cn169_data['bedrooms'],
                bathrooms=cn169_data['bathrooms'],
                area_total=Decimal(str(cn169_data['size_sqm'])),
                price_sale_thb=Decimal(str(cn169_data['price_thb'])),
                price_sale_usd=Decimal(str(cn169_data['price_thb'] / 33)),  # Примерный курс
                complex_name=cn169_data['complex_name'][:100],  # max_length=100
                furnished=True,  # Судя по удобствам
                pool=True,
                parking=True,
                security=True,
                gym=True,
                is_active=True,
            )
            print(f"✓ Создан объект недвижимости: {property_obj}")
        
        # 6. Создаем характеристики (amenities)
        amenities_en = [
            'Air Conditioning', 'WiFi', 'Pool', 'Kitchen', 'Microwave',
            'Dishwasher', 'Washer', 'Sauna', 'Coffee Maker', 'TV',
            'Workplace', 'Fireplace', 'Gym', 'Free Parking', 'BBQ Zone',
            'Bathtub', 'Shower', 'Elevator', 'Pets Welcome', 'Non Smoking',
            'Garage', 'Balcony', 'Fenced area', 'Video surveillance',
            'Security', 'Safe'
        ]
        
        created_features = 0
        for amenity_name in amenities_en:
            feature, created = PropertyFeature.objects.get_or_create(
                name=amenity_name,
                defaults={'icon': f'icon-{amenity_name.lower().replace(" ", "-")}'}
            )
            
            # Связываем с объектом недвижимости
            relation, created_rel = PropertyFeatureRelation.objects.get_or_create(
                property=property_obj,
                feature=feature
            )
            
            if created_rel:
                created_features += 1
        
        print(f"✓ Создано/обновлено {created_features} характеристик")
        
        print()
        print("=== РЕЗУЛЬТАТ МИГРАЦИИ ===")
        print(f"✓ Объект CN169 успешно создан: {property_obj}")
        print(f"✓ Цена: {property_obj.price_display}")
        print(f"✓ Локация: {property_obj.district}, {property_obj.location}")
        print(f"✓ Характеристики: {property_obj.features.count()}")
        print(f"✓ URL: {property_obj.get_absolute_url()}")
        
        return property_obj
        
    except Exception as e:
        print(f"❌ Ошибка при создании объекта: {e}")
        return None

def main():
    """Основная функция"""
    print("МИГРАЦИЯ ОБЪЕКТА CN169 ИЗ JOOMLA В DJANGO")
    print("=" * 50)
    print()
    
    # Анализ данных
    cn169_data = analyze_cn169_data()
    
    # Анализ совместимости
    direct_mapping, needs_processing = check_model_compatibility(cn169_data)
    
    # Анализ удобств
    analyze_amenities_mapping()
    
    # Создание объекта
    property_obj = create_migration_django_object()
    
    if property_obj:
        print()
        print("🎉 МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print(f"Объект доступен по адресу: http://localhost:8000{property_obj.get_absolute_url()}")
    else:
        print()
        print("❌ Миграция не удалась")

if __name__ == '__main__':
    main()