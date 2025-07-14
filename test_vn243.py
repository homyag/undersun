#!/usr/bin/env python3
"""
Тест объекта VN243 с новой системой amenities
"""
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.properties.models import Property, PropertyFeature, PropertyFeatureRelation

def test_vn243():
    """Тест объекта VN243"""
    try:
        property_obj = Property.objects.get(legacy_id='VN243')
        print(f"Найден объект: {property_obj.title}")
        print(f"Тип: {property_obj.property_type}")
        print(f"Цена THB: {property_obj.price_sale_thb}")
        print(f"Площадь участка: {property_obj.area_land}")
        
        # Выведем все amenities объекта
        print("\nAmenities через PropertyFeatureRelation:")
        amenities = PropertyFeatureRelation.objects.filter(property=property_obj)
        for amenity in amenities:
            print(f"  ✓ {amenity.feature.name}: {amenity.value}")
            
        print(f"\nВсего amenities: {amenities.count()}")
        
    except Property.DoesNotExist:
        print("Объект VN243 не найден")

if __name__ == '__main__':
    test_vn243()