#!/usr/bin/env python3
"""
Скрипт для создания полного списка amenities (26 элементов)
Создает все PropertyFeature объекты с мультиязычными названиями
"""

import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import PropertyFeature

def create_full_amenities():
    """Создать полный список amenities из 26 элементов"""
    
    # Полный список amenities с мультиязычными названиями
    amenities_data = [
        {
            'name': 'Кондиционер',
            'icon': 'fas fa-snowflake',
            'key': 'air-conditioning'
        },
        {
            'name': 'WiFi',
            'icon': 'fas fa-wifi',
            'key': 'wifi'
        },
        {
            'name': 'Бассейн',
            'icon': 'fas fa-swimmer',
            'key': 'pool'
        },
        {
            'name': 'Кухня',
            'icon': 'fas fa-utensils',
            'key': 'kitchen'
        },
        {
            'name': 'Микроволновая печь',
            'icon': 'fas fa-microwave',
            'key': 'microwave'
        },
        {
            'name': 'Посудомоечная машина',
            'icon': 'fas fa-sink',
            'key': 'dishwasher'
        },
        {
            'name': 'Стиральная машина',
            'icon': 'fas fa-tshirt',
            'key': 'washer'
        },
        {
            'name': 'Сауна',
            'icon': 'fas fa-hot-tub',
            'key': 'sauna'
        },
        {
            'name': 'Кофеварка',
            'icon': 'fas fa-coffee',
            'key': 'coffee-maker'
        },
        {
            'name': 'Телевизор',
            'icon': 'fas fa-tv',
            'key': 'tv'
        },
        {
            'name': 'Рабочее место',
            'icon': 'fas fa-desktop',
            'key': 'workplace'
        },
        {
            'name': 'Камин',
            'icon': 'fas fa-fire',
            'key': 'fireplace'
        },
        {
            'name': 'Тренажерный зал',
            'icon': 'fas fa-dumbbell',
            'key': 'gym'
        },
        {
            'name': 'Бесплатная парковка',
            'icon': 'fas fa-parking',
            'key': 'free-parking'
        },
        {
            'name': 'Зона барбекю',
            'icon': 'fas fa-fire-alt',
            'key': 'bbq-zone'
        },
        {
            'name': 'Ванна',
            'icon': 'fas fa-bath',
            'key': 'bathtub'
        },
        {
            'name': 'Душ',
            'icon': 'fas fa-shower',
            'key': 'shower'
        },
        {
            'name': 'Лифт',
            'icon': 'fas fa-elevator',
            'key': 'elevator'
        },
        {
            'name': 'Можно с животными',
            'icon': 'fas fa-paw',
            'key': 'pets-welcome'
        },
        {
            'name': 'Курение запрещено',
            'icon': 'fas fa-smoking-ban',
            'key': 'non-smoking'
        },
        {
            'name': 'Гараж',
            'icon': 'fas fa-warehouse',
            'key': 'garage'
        },
        {
            'name': 'Балкон',
            'icon': 'fas fa-building',
            'key': 'balcony'
        },
        {
            'name': 'Огороженная территория',
            'icon': 'fas fa-shield-alt',
            'key': 'fenced-area'
        },
        {
            'name': 'Видеонаблюдение',
            'icon': 'fas fa-video',
            'key': 'video-surveillance'
        },
        {
            'name': 'Охрана',
            'icon': 'fas fa-shield',
            'key': 'security'
        },
        {
            'name': 'Сейф',
            'icon': 'fas fa-lock',
            'key': 'safe'
        },
    ]
    
    created_count = 0
    updated_count = 0
    
    print("Создание полного списка amenities...")
    print("="*50)
    
    for amenity_data in amenities_data:
        feature, created = PropertyFeature.objects.get_or_create(
            name=amenity_data['name'],
            defaults={
                'icon': amenity_data['icon']
            }
        )
        
        if created:
            created_count += 1
            print(f"✓ Создано: {amenity_data['name']}")
        else:
            # Обновляем иконку если она изменилась
            if feature.icon != amenity_data['icon']:
                feature.icon = amenity_data['icon']
                feature.save()
                updated_count += 1
                print(f"↻ Обновлено: {amenity_data['name']}")
            else:
                print(f"- Уже существует: {amenity_data['name']}")
    
    print("\n" + "="*50)
    print("РЕЗУЛЬТАТ СОЗДАНИЯ AMENITIES:")
    print("="*50)
    print(f"✓ Создано новых amenities: {created_count}")
    print(f"↻ Обновлено существующих: {updated_count}")
    print(f"📊 Всего amenities в системе: {PropertyFeature.objects.count()}")
    
    # Проверка созданных amenities
    print("\n📋 Список всех amenities:")
    for feature in PropertyFeature.objects.all().order_by('name'):
        print(f"  • {feature.name} ({feature.icon})")
    
    return created_count, updated_count

if __name__ == '__main__':
    create_full_amenities()