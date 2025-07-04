#!/usr/bin/env python
"""
Скрипт для анализа объектов недвижимости в Django, которых нет в Joomla
Только анализ, без удаления
"""

import os
import sys
import json
from datetime import datetime

# Добавляем путь к Django проекту
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from apps.properties.models import Property, PropertyImage


def load_comparison_data():
    """Загружает данные сравнения Joomla и Django"""
    try:
        with open('joomla_django_comparison.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Файл joomla_django_comparison.json не найден")
        return None


def analyze_objects_to_delete():
    """Анализирует объекты для удаления"""
    comparison_data = load_comparison_data()
    if not comparison_data:
        return
    
    django_only_objects = comparison_data.get('django_only', [])
    
    if not django_only_objects:
        print("✅ Нет объектов для удаления - все объекты Django найдены в Joomla")
        return
    
    print(f"🧹 АНАЛИЗ ОБЪЕКТОВ ДЛЯ УДАЛЕНИЯ")
    print("=" * 60)
    print(f"📊 Найдено {len(django_only_objects)} объектов, отсутствующих в Joomla")
    
    # Группируем по legacy_id для анализа
    by_legacy_pattern = {}
    no_legacy_id = []
    recent_objects = []
    old_objects = []
    
    for obj in django_only_objects:
        legacy_id = obj.get('legacy_id')
        created_date = obj.get('django_created')
        
        # Анализ по legacy_id
        if legacy_id:
            pattern = legacy_id[:2] if len(legacy_id) >= 2 else legacy_id
            if pattern not in by_legacy_pattern:
                by_legacy_pattern[pattern] = []
            by_legacy_pattern[pattern].append(obj)
        else:
            no_legacy_id.append(obj)
        
        # Анализ по дате создания
        if created_date and created_date.startswith('2025'):
            recent_objects.append(obj)
        else:
            old_objects.append(obj)
    
    print("\n🔍 Анализ по типам legacy_id:")
    for pattern, objects in sorted(by_legacy_pattern.items()):
        print(f"  {pattern}*: {len(objects)} объектов")
    
    if no_legacy_id:
        print(f"  Без legacy_id: {len(no_legacy_id)} объектов")
    
    print(f"\n📅 Анализ по датам:")
    print(f"  Недавние объекты (2025): {len(recent_objects)}")
    print(f"  Старые объекты: {len(old_objects)}")
    
    # Анализ изображений
    property_ids = [obj['django_id'] for obj in django_only_objects]
    images_count = PropertyImage.objects.filter(property_id__in=property_ids).count()
    objects_with_images = PropertyImage.objects.filter(property_id__in=property_ids).values_list('property_id', flat=True).distinct().count()
    
    print(f"\n📸 Анализ изображений:")
    print(f"  Объектов с изображениями: {objects_with_images}")
    print(f"  Всего изображений: {images_count}")
    
    # Показываем примеры объектов
    print(f"\n📋 ПРИМЕРЫ ОБЪЕКТОВ ДЛЯ УДАЛЕНИЯ:")
    print("-" * 100)
    print(f"{'ID':<6} {'Legacy ID':<12} {'Title':<65} {'Created':<12}")
    print("-" * 100)
    
    for i, obj in enumerate(django_only_objects[:15]):
        title = obj['django_title'][:60] + '...' if len(obj['django_title']) > 60 else obj['django_title']
        created = obj.get('django_created', '')[:10] if obj.get('django_created') else 'N/A'
        legacy_id = obj.get('legacy_id', 'None')
        
        print(f"{obj['django_id']:<6} {legacy_id:<12} {title:<65} {created:<12}")
    
    if len(django_only_objects) > 15:
        print(f"... и ещё {len(django_only_objects) - 15} объектов")
    
    # Рекомендации
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    
    if len(recent_objects) > 100:
        print(f"⚠️  Много недавних объектов ({len(recent_objects)}) - возможно, они созданы после экспорта Joomla")
    
    if len(no_legacy_id) > 100:
        print(f"⚠️  Много объектов без legacy_id ({len(no_legacy_id)}) - возможно, они созданы напрямую в Django")
    
    if objects_with_images > 10:
        print(f"⚠️  {objects_with_images} объектов имеют изображения - проверьте важность данных")
    
    print(f"\n📁 Для выполнения удаления запустите:")
    print(f"   python cleanup_django_objects.py")
    
    # Сохраняем отчет
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_to_delete': len(django_only_objects),
        'by_legacy_pattern': {k: len(v) for k, v in by_legacy_pattern.items()},
        'no_legacy_id_count': len(no_legacy_id),
        'recent_objects_count': len(recent_objects),
        'old_objects_count': len(old_objects),
        'objects_with_images': objects_with_images,
        'total_images': images_count,
        'objects_to_delete': django_only_objects
    }
    
    with open('deletion_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 Подробный анализ сохранен в: deletion_analysis.json")


if __name__ == '__main__':
    analyze_objects_to_delete()