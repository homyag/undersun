#!/usr/bin/env python3
"""
Скрипт для создания amenities как PropertyFeature
"""
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import PropertyFeature

def create_amenities():
    """Создать amenities как PropertyFeature"""
    # Полный список amenities из скрипта миграции
    amenities_data = [
        ('air_conditioning', 'Кондиционер', 'fas fa-snowflake'),
        ('wifi', 'WiFi', 'fas fa-wifi'),
        ('pool', 'Бассейн', 'fas fa-swimmer'),
        ('kitchen', 'Кухня', 'fas fa-utensils'),
        ('microwave', 'Микроволновая печь', 'fas fa-microwave'),
        ('dishwasher', 'Посудомоечная машина', 'fas fa-dishwasher'),
        ('washer', 'Стиральная машина', 'fas fa-washing-machine'),
        ('sauna', 'Сауна', 'fas fa-hot-tub'),
        ('coffee_maker', 'Кофеварка', 'fas fa-coffee'),
        ('tv', 'Телевизор', 'fas fa-tv'),
        ('workplace', 'Рабочее место', 'fas fa-laptop'),
        ('fireplace', 'Камин', 'fas fa-fire'),
        ('gym', 'Тренажерный зал', 'fas fa-dumbbell'),
        ('free_parking', 'Бесплатная парковка', 'fas fa-parking'),
        ('bbq_zone', 'Зона барбекю', 'fas fa-fire'),
        ('bathtub', 'Ванна', 'fas fa-bath'),
        ('shower', 'Душ', 'fas fa-shower'),
        ('elevator', 'Лифт', 'fas fa-elevator'),
        ('pets_welcome', 'Можно с животными', 'fas fa-paw'),
        ('non_smoking', 'Курение запрещено', 'fas fa-smoking-ban'),
        ('garage', 'Гараж', 'fas fa-warehouse'),
        ('balcony', 'Балкон', 'fas fa-building'),
        ('fenced_area', 'Огороженная территория', 'fas fa-shield-alt'),
        ('video_surveillance', 'Видеонаблюдение', 'fas fa-video'),
        ('security', 'Охрана', 'fas fa-shield'),
        ('safe', 'Сейф', 'fas fa-safe'),
    ]

    created_count = 0
    for amenity_code, amenity_name, icon in amenities_data:
        feature, created = PropertyFeature.objects.get_or_create(
            name=amenity_name,
            defaults={'icon': icon}
        )
        if created:
            created_count += 1
            print(f"✓ Создан amenity: {amenity_name}")
        else:
            print(f"⚠ Amenity уже существует: {amenity_name}")

    print(f"\nВсего создано amenities: {created_count}")
    print(f"Всего amenities в системе: {PropertyFeature.objects.count()}")

if __name__ == '__main__':
    create_amenities()