#!/usr/bin/env python3
"""
Скрипт нормализации локаций и районов Пхукета
"""

import os
import sys
import django
from django.db import transaction

# Добавляем путь к Django проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.locations.models import Location, District
from apps.properties.models import Property

# Корректная структура районов и локаций Пхукета на основе административного деления
DISTRICTS_DATA = {
    'Thalang': {
        'name_en': 'Thalang',
        'name_ru': 'Таланг',
        'name_th': 'ถลาง',
        'locations': {
            'Thep Krasattri': {'name_en': 'Thep Krasattri', 'name_ru': 'Теп Красаттри', 'name_th': 'เทพกษัตรีย์'},
            'Si Sunthon': {'name_en': 'Si Sunthon', 'name_ru': 'Си Сунтон', 'name_th': 'ศรีสุนทร'},
            'Cherng Talay': {'name_en': 'Cherng Talay', 'name_ru': 'Черн Талай', 'name_th': 'เชิงทะเล'},
            'Pa Khlok': {'name_en': 'Pa Khlok', 'name_ru': 'Па Клок', 'name_th': 'ป่าคลอก'},
            'Mai Khao': {'name_en': 'Mai Khao', 'name_ru': 'Май Као', 'name_th': 'ไม้ขาว'},
            'Sakhu': {'name_en': 'Sakhu', 'name_ru': 'Саку', 'name_th': 'สาคู'},
            # Дополнительные популярные области
            'Bang Tao': {'name_en': 'Bang Tao', 'name_ru': 'Банг Тао', 'name_th': 'บางเทา'},
            'Layan': {'name_en': 'Layan', 'name_ru': 'Лаян', 'name_th': 'ลายัน'},
            'Surin': {'name_en': 'Surin', 'name_ru': 'Сурин', 'name_th': 'สุรินทร์'},
            'Nai Thon': {'name_en': 'Nai Thon', 'name_ru': 'Най Тон', 'name_th': 'นายธน'},
            'Nai Yang': {'name_en': 'Nai Yang', 'name_ru': 'Най Янг', 'name_th': 'นายยาง'},
        }
    },
    'Kathu': {
        'name_en': 'Kathu',
        'name_ru': 'Кату',
        'name_th': 'กะทู้',
        'locations': {
            'Kathu': {'name_en': 'Kathu', 'name_ru': 'Кату', 'name_th': 'กะทู้'},
            'Patong': {'name_en': 'Patong', 'name_ru': 'Патонг', 'name_th': 'ป่าตอง'},
            'Kamala': {'name_en': 'Kamala', 'name_ru': 'Камала', 'name_th': 'กมลา'},
        }
    },
    'Mueang Phuket': {
        'name_en': 'Mueang Phuket',
        'name_ru': 'Муанг Пхукет',
        'name_th': 'เมืองภูเก็ต',
        'locations': {
            'Talad Yai': {'name_en': 'Talad Yai', 'name_ru': 'Талад Яй', 'name_th': 'ตลาดใหญ่'},
            'Talad Nuea': {'name_en': 'Talad Nuea', 'name_ru': 'Талад Нуа', 'name_th': 'ตลาดเหนือ'},
            'Ko Kaeo': {'name_en': 'Ko Kaeo', 'name_ru': 'Ко Кео', 'name_th': 'เกาะแก้ว'},
            'Ratsada': {'name_en': 'Ratsada', 'name_ru': 'Ратсада', 'name_th': 'รัษฎา'},
            'Wichit': {'name_en': 'Wichit', 'name_ru': 'Вичит', 'name_th': 'วิชิต'},
            'Chalong': {'name_en': 'Chalong', 'name_ru': 'Чалонг', 'name_th': 'ฉลอง'},
            'Rawai': {'name_en': 'Rawai', 'name_ru': 'Равай', 'name_th': 'ราไวย์'},
            'Karon': {'name_en': 'Karon', 'name_ru': 'Карон', 'name_th': 'กะรน'},
            # Дополнительные популярные области
            'Kata': {'name_en': 'Kata', 'name_ru': 'Ката', 'name_th': 'กะตะ'},
            'Kata Noi': {'name_en': 'Kata Noi', 'name_ru': 'Ката Ной', 'name_th': 'กะตะน้อย'},
            'Nai Harn': {'name_en': 'Nai Harn', 'name_ru': 'Най Харн', 'name_th': 'นายหาญ'},
            'Cape Panwa': {'name_en': 'Cape Panwa', 'name_ru': 'Кейп Панва', 'name_th': 'แหลมพันวา'},
        }
    }
}


def normalize_districts():
    """Нормализация районов"""
    print("=== Нормализация районов ===")
    
    # Сначала удаляем дублирующиеся районы (русские названия)
    duplicates_to_remove = ['Карон', 'Пхукет', 'Камала', 'Патонг', 'Чалонг', 'Равай', 'Вичит']
    
    for district_name in duplicates_to_remove:
        try:
            district = District.objects.get(name=district_name)
            # Переносим все локации на корректные районы
            for location in district.locations.all():
                print(f"Перенос локации {location.name} из района {district.name}")
                # Определяем правильный район
                new_district = get_correct_district_for_location(location.name)
                if new_district:
                    location.district = new_district
                    # Убеждаемся, что у локации есть slug
                    if not location.slug:
                        from django.utils.text import slugify
                        location.slug = slugify(location.name)
                    location.save()
                    print(f"  -> перенесено в район {new_district.name}")
            
            print(f"Удаление дублирующегося района: {district.name}")
            district.delete()
        except District.DoesNotExist:
            print(f"Район {district_name} не найден")
    
    # Создаем/обновляем корректные районы
    for district_key, district_data in DISTRICTS_DATA.items():
        district, created = District.objects.get_or_create(
            name=district_data['name_en'],
            defaults={
                'name_ru': district_data['name_ru'],
                'name_th': district_data['name_th'],
                'slug': district_key.lower().replace(' ', '-'),
            }
        )
        
        if created:
            print(f"Создан район: {district.name}")
        else:
            # Обновляем переводы
            district.name_ru = district_data['name_ru']
            district.name_th = district_data['name_th']
            if not district.slug:
                district.slug = district_key.lower().replace(' ', '-')
            district.save()
            print(f"Обновлен район: {district.name}")


def get_correct_district_for_location(location_name):
    """Определение корректного района для локации"""
    location_name_clean = location_name.split(',')[0].strip()
    
    for district_key, district_data in DISTRICTS_DATA.items():
        for loc_key in district_data['locations'].keys():
            if loc_key.lower() in location_name_clean.lower() or location_name_clean.lower() in loc_key.lower():
                try:
                    return District.objects.get(name=district_data['name_en'])
                except District.DoesNotExist:
                    continue
    
    return None


def normalize_locations():
    """Нормализация локаций"""
    print("\n=== Нормализация локаций ===")
    
    # Удаляем дублирующиеся и некорректные локации
    locations_to_clean = [
        'Kathu, Phuket, Thailand',
        'Koktanode, Phuket, Thailand', 
        'Kamala, Phuket, Thailand',
        'Patong, Phuket, Thailand',
        'Tapepratarn, Ratsada, Phuket, Thailand',
        'Rawai, Phuket, Thailand',
        'Chalong, Phuket, Thailand',
    ]
    
    for location_name in locations_to_clean:
        try:
            location = Location.objects.get(name=location_name)
            # Переносим объекты недвижимости на правильные локации
            properties = Property.objects.filter(location=location)
            if properties.exists():
                print(f"Найдено {properties.count()} объектов для локации {location_name}")
                
                # Определяем правильную локацию
                correct_location = get_correct_location_replacement(location_name)
                if correct_location:
                    properties.update(location=correct_location)
                    print(f"  -> объекты перенесены в локацию {correct_location.name}")
            
            print(f"Удаление дублирующейся локации: {location_name}")
            location.delete()
        except Location.DoesNotExist:
            print(f"Локация {location_name} не найдена")
    
    # Создаем/обновляем корректные локации
    for district_key, district_data in DISTRICTS_DATA.items():
        district = None
        try:
            district = District.objects.get(name=district_data['name_en'])
        except District.DoesNotExist:
            try:
                district = District.objects.get(name=district_data['name_ru'])
            except District.DoesNotExist:
                print(f"Район {district_data['name_en']} / {district_data['name_ru']} не найден, пропускаем")
                continue
        
        for location_key, location_data in district_data['locations'].items():
            from django.utils.text import slugify
            
            # district уже найден выше
            
            location, created = Location.objects.get_or_create(
                name=location_data['name_en'],
                district=district,
                defaults={
                    'name_ru': location_data['name_ru'],
                    'name_th': location_data['name_th'],
                    'slug': slugify(location_key),
                }
            )
            
            if created:
                print(f"Создана локация: {location.name} в районе {district.name}")
            else:
                # Обновляем переводы
                location.name_ru = location_data['name_ru']
                location.name_th = location_data['name_th']
                if not location.slug:
                    location.slug = slugify(location_key)
                location.save()
                print(f"Обновлена локация: {location.name}")


def get_correct_location_replacement(old_location_name):
    """Получение правильной замены для старой локации"""
    mapping = {
        'Kathu, Phuket, Thailand': 'Kathu',
        'Koktanode, Phuket, Thailand': 'Thep Krasattri',
        'Kamala, Phuket, Thailand': 'Kamala',
        'Patong, Phuket, Thailand': 'Patong',
        'Tapepratarn, Ratsada, Phuket, Thailand': 'Ratsada',
        'Rawai, Phuket, Thailand': 'Rawai',
        'Chalong, Phuket, Thailand': 'Chalong',
    }
    
    new_name = mapping.get(old_location_name)
    if new_name:
        try:
            return Location.objects.get(name=new_name)
        except Location.DoesNotExist:
            return None
    
    return None


def update_property_locations():
    """Обновление связей объектов недвижимости с локациями"""
    print("\n=== Обновление связей недвижимости ===")
    
    # Ищем объекты без локации и пытаемся их привязать
    properties_without_location = Property.objects.filter(location__isnull=True)
    
    print(f"Найдено {properties_without_location.count()} объектов без локации")
    
    for prop in properties_without_location:
        # Пытаемся определить локацию по названию объекта
        location = guess_location_from_title(prop.title)
        if location:
            prop.location = location
            prop.save()
            print(f"Объект '{prop.title}' привязан к локации {location.name}")


def guess_location_from_title(title):
    """Угадывание локации по названию объекта"""
    title_lower = title.lower()
    
    # Ищем упоминания локаций в названии
    for district_key, district_data in DISTRICTS_DATA.items():
        for location_key, location_data in district_data['locations'].items():
            location_names = [
                location_data['name_en'].lower(),
                location_data['name_ru'].lower(),
                location_key.lower()
            ]
            
            for loc_name in location_names:
                if loc_name in title_lower:
                    try:
                        district = District.objects.get(name=district_data['name_en'])
                        return Location.objects.get(name=location_data['name_en'], district=district)
                    except (District.DoesNotExist, Location.DoesNotExist):
                        continue
    
    return None


def main():
    """Основная функция"""
    print("=== НОРМАЛИЗАЦИЯ ЛОКАЦИЙ И РАЙОНОВ ПХУКЕТА ===")
    
    with transaction.atomic():
        try:
            normalize_districts()
            normalize_locations()
            update_property_locations()
            
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