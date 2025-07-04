#!/usr/bin/env python
"""
Выполнение безопасного удаления объектов
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
from django.db import transaction


def load_cleanup_plan():
    """Загружает план очистки"""
    try:
        with open('smart_cleanup_plan.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ План очистки не найден. Сначала запустите smart_cleanup.py")
        return None


def execute_cleanup():
    """Выполняет безопасную очистку"""
    plan = load_cleanup_plan()
    if not plan:
        return
    
    safe_objects = plan.get('recommendations', {}).get('safe_deletion', [])
    
    if not safe_objects:
        print("✅ Нет объектов для безопасного удаления")
        return
    
    property_ids = [obj['django_id'] for obj in safe_objects]
    
    print("🎯 ВЫПОЛНЕНИЕ БЕЗОПАСНОЙ ОЧИСТКИ")
    print("=" * 50)
    print(f"📊 Объектов к удалению: {len(property_ids)}")
    
    # Проверяем изображения
    images_count = PropertyImage.objects.filter(property_id__in=property_ids).count()
    print(f"📸 Изображений к удалению: {images_count}")
    
    # Показываем примеры
    print(f"\n📋 Примеры объектов для удаления:")
    for obj in safe_objects[:5]:
        print(f"   ID {obj['django_id']}: {obj['legacy_id']} - {obj['django_title'][:50]}...")
    
    if len(safe_objects) > 5:
        print(f"   ... и ещё {len(safe_objects) - 5} объектов")
    
    print(f"\n⚠️  Это действие удалит {len(property_ids)} объектов и {images_count} изображений!")
    print("   Будет создана резервная копия.")
    
    try:
        with transaction.atomic():
            # Создаем полную резервную копию
            properties_data = list(Property.objects.filter(id__in=property_ids).values())
            images_data = list(PropertyImage.objects.filter(property_id__in=property_ids).values())
            
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'operation': 'safe_cleanup',
                'reason': 'Removing test objects with legacy_id created today',
                'deleted_count': len(properties_data),
                'deleted_images_count': len(images_data),
                'properties': properties_data,
                'images': images_data,
                'cleanup_plan': plan
            }
            
            backup_file = f"backup_safe_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"💾 Резервная копия создана: {backup_file}")
            
            # Удаляем изображения
            print("🗑️  Удаляем изображения...")
            deleted_images = PropertyImage.objects.filter(property_id__in=property_ids).delete()
            print(f"   Удалено изображений: {deleted_images[0]}")
            
            # Удаляем объекты недвижимости
            print("🗑️  Удаляем объекты недвижимости...")
            deleted_properties = Property.objects.filter(id__in=property_ids).delete()
            print(f"   Удалено объектов: {deleted_properties[0]}")
            
            # Создаем отчет
            cleanup_report = {
                'timestamp': datetime.now().isoformat(),
                'operation': 'completed',
                'deleted_properties': deleted_properties[0],
                'deleted_images': deleted_images[0],
                'backup_file': backup_file,
                'remaining_properties': Property.objects.count()
            }
            
            report_file = f"cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(cleanup_report, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"📊 Отчет создан: {report_file}")
            
            print("\n✅ ОЧИСТКА ЗАВЕРШЕНА УСПЕШНО!")
            print(f"   Удалено объектов: {deleted_properties[0]}")
            print(f"   Удалено изображений: {deleted_images[0]}")
            print(f"   Осталось объектов в базе: {Property.objects.count()}")
            
    except Exception as e:
        print(f"❌ Ошибка при выполнении очистки: {e}")
        raise


def verify_cleanup():
    """Проверяет результаты очистки"""
    print("\n🔍 ПРОВЕРКА РЕЗУЛЬТАТОВ:")
    
    # Проверяем соответствие с Joomla
    try:
        with open('joomla_django_comparison.json', 'r', encoding='utf-8') as f:
            comparison = json.load(f)
        
        joomla_count = comparison['summary']['joomla_total']
        django_count = Property.objects.count()
        
        print(f"   Объектов в Joomla: {joomla_count}")
        print(f"   Объектов в Django: {django_count}")
        
        if django_count <= joomla_count:
            print("✅ Количество объектов в Django не превышает Joomla")
        else:
            extra_count = django_count - joomla_count
            print(f"📊 В Django {extra_count} дополнительных объектов (вероятно, созданы напрямую)")
        
    except FileNotFoundError:
        print("⚠️  Файл сравнения не найден")


if __name__ == '__main__':
    print("⚡ БЕЗОПАСНАЯ ОЧИСТКА БАЗЫ ДАННЫХ")
    print("Удаление тестовых объектов с legacy_id")
    print("=" * 50)
    
    execute_cleanup()
    verify_cleanup()
    
    print(f"\n🎉 Операция завершена!")
    print(f"   База данных очищена от тестовых объектов")
    print(f"   Все важные данные сохранены")