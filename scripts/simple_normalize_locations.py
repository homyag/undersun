#!/usr/bin/env python3
"""
Простой скрипт нормализации локаций Пхукета
"""

import os
import sys
import django
from django.db import transaction
from django.utils.text import slugify

# Добавляем путь к Django проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.locations.models import Location, District
from apps.properties.models import Property

# Локации для каждого района
LOCATIONS_DATA = {
    'Таланг': [
        {'name_en': 'Thep Krasattri', 'name_ru': 'Теп Красаттри', 'name_th': 'เทพกษัตรีย์'},
        {'name_en': 'Si Sunthon', 'name_ru': 'Си Сунтон', 'name_th': 'ศรีสุนทร'},
        {'name_en': 'Cherng Talay', 'name_ru': 'Черн Талай', 'name_th': 'เชิงทะเล'},
        {'name_en': 'Pa Khlok', 'name_ru': 'Па Клок', 'name_th': 'ป่าคลอก'},
        {'name_en': 'Mai Khao', 'name_ru': 'Май Као', 'name_th': 'ไม้ขาว'},
        {'name_en': 'Sakhu', 'name_ru': 'Саку', 'name_th': 'สาคู'},
        {'name_en': 'Bang Tao', 'name_ru': 'Банг Тао', 'name_th': 'บางเทา'},
        {'name_en': 'Layan', 'name_ru': 'Лаян', 'name_th': 'ลายัน'},
        {'name_en': 'Surin', 'name_ru': 'Сурин', 'name_th': 'สุรินทร์'},
        {'name_en': 'Nai Thon', 'name_ru': 'Най Тон', 'name_th': 'นายธน'},
        {'name_en': 'Nai Yang', 'name_ru': 'Най Янг', 'name_th': 'นายยาง'},
    ],
    'Кату': [
        {'name_en': 'Kathu', 'name_ru': 'Кату', 'name_th': 'กะทู้'},
        {'name_en': 'Patong', 'name_ru': 'Патонг', 'name_th': 'ป่าตอง'},
        {'name_en': 'Kamala', 'name_ru': 'Камала', 'name_th': 'กมลา'},
    ],
    'Муанг Пхукет': [
        {'name_en': 'Talad Yai', 'name_ru': 'Талад Яй', 'name_th': 'ตลาดใหญ่'},
        {'name_en': 'Talad Nuea', 'name_ru': 'Талад Нуа', 'name_th': 'ตลาดเหนือ'},
        {'name_en': 'Ko Kaeo', 'name_ru': 'Ко Кео', 'name_th': 'เกาะแก้ว'},
        {'name_en': 'Ratsada', 'name_ru': 'Ратсада', 'name_th': 'รัษฎา'},
        {'name_en': 'Wichit', 'name_ru': 'Вичит', 'name_th': 'วิชิต'},
        {'name_en': 'Chalong', 'name_ru': 'Чалонг', 'name_th': 'ฉลอง'},
        {'name_en': 'Rawai', 'name_ru': 'Равай', 'name_th': 'ราไวย์'},
        {'name_en': 'Karon', 'name_ru': 'Карон', 'name_th': 'กะรน'},
        {'name_en': 'Kata', 'name_ru': 'Ката', 'name_th': 'กะตะ'},
        {'name_en': 'Kata Noi', 'name_ru': 'Ката Ной', 'name_th': 'กะตะน้อย'},
        {'name_en': 'Nai Harn', 'name_ru': 'Най Харн', 'name_th': 'นายหาญ'},
        {'name_en': 'Cape Panwa', 'name_ru': 'Кейп Панва', 'name_th': 'แหลมพันวา'},
    ]
}


def add_missing_locations():
    """Добавление недостающих локаций"""
    print("=== Добавление локаций ===")
    
    for district_name, locations in LOCATIONS_DATA.items():
        try:
            district = District.objects.get(name=district_name)
            print(f"\nРайон: {district.name}")
            
            for location_data in locations:
                location, created = Location.objects.get_or_create(
                    name=location_data['name_en'],
                    district=district,
                    defaults={
                        'name_ru': location_data['name_ru'],
                        'name_th': location_data['name_th'],
                        'slug': slugify(location_data['name_en']),
                    }
                )
                
                if created:
                    print(f"  + Создана: {location.name}")
                else:
                    # Обновляем переводы
                    location.name_ru = location_data['name_ru']
                    location.name_th = location_data['name_th']
                    if not location.slug:
                        location.slug = slugify(location_data['name_en'])
                    location.save()
                    print(f"  ~ Обновлена: {location.name}")
                    
        except District.DoesNotExist:
            print(f"Район {district_name} не найден")


def update_district_translations():
    """Обновление переводов районов"""
    print("\n=== Обновление переводов районов ===")
    
    district_translations = {
        'Таланг': {'name_en': 'Thalang', 'name_th': 'ถลาง'},
        'Кату': {'name_en': 'Kathu', 'name_th': 'กะทู้'},
        'Муанг Пхукет': {'name_en': 'Mueang Phuket', 'name_th': 'เมืองภูเก็ต'},
    }
    
    for district in District.objects.all():
        if district.name in district_translations:
            trans = district_translations[district.name]
            district.name_en = trans['name_en']
            district.name_th = trans['name_th']
            if not district.slug:
                district.slug = slugify(trans['name_en'])
            district.save()
            print(f"Обновлен район: {district.name} -> EN: {district.name_en}, TH: {district.name_th}")


def cleanup_duplicate_locations():
    """Очистка дублирующихся локаций"""
    print("\n=== Очистка дублирующихся локаций ===")
    
    # Удаляем локации с длинными названиями, оставляем короткие
    duplicates_to_remove = [
        'Kathu, Phuket, Thailand',
        'Koktanode, Phuket, Thailand', 
        'Kamala, Phuket, Thailand',
        'Patong, Phuket, Thailand',
        'Tapepratarn, Ratsada, Phuket, Thailand',
        'Rawai, Phuket, Thailand',
        'Chalong, Phuket, Thailand',
    ]
    
    for location_name in duplicates_to_remove:
        try:
            old_location = Location.objects.get(name=location_name)
            
            # Ищем новую локацию для переноса объектов
            new_location = get_replacement_location(location_name)
            
            if new_location:
                # Переносим объекты недвижимости
                properties = Property.objects.filter(location=old_location)
                if properties.exists():
                    properties.update(location=new_location)
                    print(f"  Перенесено {properties.count()} объектов с {old_location.name} на {new_location.name}")
                
                old_location.delete()
                print(f"  Удалена дублирующаяся локация: {location_name}")
            
        except Location.DoesNotExist:
            print(f"  Локация {location_name} не найдена")


def get_replacement_location(old_name):
    """Получение замещающей локации"""
    replacements = {
        'Kathu, Phuket, Thailand': 'Kathu',
        'Koktanode, Phuket, Thailand': 'Thep Krasattri',
        'Kamala, Phuket, Thailand': 'Kamala',
        'Patong, Phuket, Thailand': 'Patong',
        'Tapepratarn, Ratsada, Phuket, Thailand': 'Ratsada',
        'Rawai, Phuket, Thailand': 'Rawai',
        'Chalong, Phuket, Thailand': 'Chalong',
    }
    
    new_name = replacements.get(old_name)
    if new_name:
        try:
            return Location.objects.get(name=new_name)
        except Location.DoesNotExist:
            return None
    
    return None


def fix_property_locations():
    """Исправление локаций объектов недвижимости"""
    print("\n=== Исправление локаций объектов ===")
    
    # Ищем объекты без локации и пытаемся их привязать
    properties_without_location = Property.objects.filter(location__isnull=True)
    
    print(f"Найдено {properties_without_location.count()} объектов без локации")
    
    for prop in properties_without_location:
        location = guess_location_from_title(prop.title)
        if location:
            prop.location = location
            prop.save()
            print(f"  {prop.title} -> {location.name}")


def guess_location_from_title(title):
    """Угадывание локации по названию"""
    title_lower = title.lower()
    
    # Поиск упоминаний известных локаций
    location_keywords = {
        'bang tao': 'Bang Tao',
        'bangtao': 'Bang Tao',
        'layan': 'Layan',
        'surin': 'Surin',
        'kamala': 'Kamala',
        'patong': 'Patong',
        'kata': 'Kata',
        'karon': 'Karon',
        'chalong': 'Chalong',
        'rawai': 'Rawai',
        'nai harn': 'Nai Harn',
        'nai yang': 'Nai Yang',
        'nai thon': 'Nai Thon',
        'mai khao': 'Mai Khao',
        'cherng talay': 'Cherng Talay',
        'thalang': 'Thep Krasattri',
        'kathu': 'Kathu',
    }
    
    for keyword, location_name in location_keywords.items():
        if keyword in title_lower:
            try:
                return Location.objects.get(name=location_name)
            except Location.DoesNotExist:
                continue
    
    return None


def main():
    """Основная функция"""
    print("=== НОРМАЛИЗАЦИЯ ЛОКАЦИЙ ПХУКЕТА ===")
    
    with transaction.atomic():
        try:
            update_district_translations()
            add_missing_locations()
            cleanup_duplicate_locations()
            fix_property_locations()
            
            print("\n=== РЕЗУЛЬТАТЫ ===")
            print(f"Районов в базе: {District.objects.count()}")
            print(f"Локаций в базе: {Location.objects.count()}")
            print(f"Объектов с локацией: {Property.objects.filter(location__isnull=False).count()}")
            print(f"Объектов без локации: {Property.objects.filter(location__isnull=True).count()}")
            
            print("\nНормализация завершена успешно!")
            
        except Exception as e:
            print(f"Ошибка при нормализации: {e}")
            raise


if __name__ == '__main__':
    main()