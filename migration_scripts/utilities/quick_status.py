#!/usr/bin/env python
"""
Быстрая проверка статуса импорта фотографий в Django БД
"""

import os
import sys
from pathlib import Path

# Настройка Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from django.db import models
from apps.properties.models import Property, PropertyImage

def quick_status():
    """Быстрая проверка статуса"""
    print("🔍 БЫСТРАЯ ПРОВЕРКА СТАТУСА ИМПОРТА ФОТО")
    print("=" * 60)
    
    # Общая статистика
    total_properties = Property.objects.count()
    print(f"📊 Всего объектов в Django БД: {total_properties}")
    
    # Объекты с любыми фотографиями
    properties_with_any_photos = Property.objects.filter(images__isnull=False).distinct().count()
    print(f"📷 Объекты с любыми фотографиями: {properties_with_any_photos}")
    
    # Объекты с импортированными фотографиями (parsed_, imported_, scanned_, continued_, bulk_)
    properties_with_imported = Property.objects.filter(
        models.Q(images__image__icontains='parsed_') | 
        models.Q(images__image__icontains='imported_') |
        models.Q(images__image__icontains='scanned_') |
        models.Q(images__image__icontains='continued_') |
        models.Q(images__image__icontains='bulk_')
    ).distinct().count()
    print(f"🔄 Объекты с импортированными фото: {properties_with_imported}")
    
    # Объекты БЕЗ импортированных фотографий
    without_imported = total_properties - properties_with_imported
    print(f"❌ Объекты БЕЗ импортированных фото: {without_imported}")
    
    # Статистика по типам изображений
    parsed_count = PropertyImage.objects.filter(image__icontains='parsed_').count()
    imported_count = PropertyImage.objects.filter(image__icontains='imported_').count()
    scanned_count = PropertyImage.objects.filter(image__icontains='scanned_').count()
    continued_count = PropertyImage.objects.filter(image__icontains='continued_').count()
    bulk_count = PropertyImage.objects.filter(image__icontains='bulk_').count()
    
    print(f"\n📈 ДЕТАЛЬНАЯ СТАТИСТИКА ИЗОБРАЖЕНИЙ:")
    print(f"   parsed_*: {parsed_count} изображений")
    print(f"   imported_*: {imported_count} изображений")
    print(f"   scanned_*: {scanned_count} изображений")
    print(f"   continued_*: {continued_count} изображений")
    print(f"   bulk_*: {bulk_count} изображений")
    
    total_imported_images = parsed_count + imported_count + scanned_count + continued_count + bulk_count
    print(f"   ВСЕГО импортированных: {total_imported_images} изображений")
    
    # Процентное покрытие
    coverage_percent = (properties_with_imported / total_properties) * 100 if total_properties > 0 else 0
    print(f"\n✅ Покрытие импортированными фото: {coverage_percent:.1f}%")
    
    if without_imported > 0:
        print(f"\n🎯 ОСТАЛОСЬ ОБРАБОТАТЬ: {without_imported} объектов")
    else:
        print(f"\n🎉 ВСЕ ОБЪЕКТЫ ИМЕЮТ ИМПОРТИРОВАННЫЕ ФОТОГРАФИИ!")

if __name__ == '__main__':
    quick_status()