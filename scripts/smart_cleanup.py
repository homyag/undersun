#!/usr/bin/env python
"""
Умная очистка базы Django с учетом даты создания объектов
"""

import os
import sys
import json
from datetime import datetime, date

# Добавляем путь к Django проекту
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from apps.properties.models import Property, PropertyImage
from django.db import transaction


def analyze_django_objects():
    """Умный анализ объектов Django"""
    
    print("🔍 УМНЫЙ АНАЛИЗ ОБЪЕКТОВ DJANGO")
    print("=" * 60)
    
    # Загружаем данные сравнения
    try:
        with open('joomla_django_comparison.json', 'r', encoding='utf-8') as f:
            comparison_data = json.load(f)
    except FileNotFoundError:
        print("❌ Файл сравнения не найден")
        return
    
    # Получаем объекты только в Django
    django_only = comparison_data.get('django_only', [])
    matched_objects = comparison_data.get('matched_objects', [])
    
    print(f"📊 Статистика объектов:")
    print(f"   Всего в Django: {len(django_only) + len(matched_objects)}")
    print(f"   Найдены в Joomla: {len(matched_objects)}")
    print(f"   Только в Django: {len(django_only)}")
    
    # Анализируем объекты только в Django
    if not django_only:
        print("✅ Все объекты Django найдены в Joomla")
        return
    
    # Категоризируем объекты
    categories = {
        'recent_no_legacy': [],      # Недавние без legacy_id - скорее всего новые
        'recent_with_legacy': [],    # Недавние с legacy_id - возможно, тестовые
        'old_no_legacy': [],         # Старые без legacy_id - возможно, важные
        'old_with_legacy': [],       # Старые с legacy_id - возможно, потерянные
    }
    
    today = date.today()
    
    for obj in django_only:
        has_legacy = bool(obj.get('legacy_id'))
        created_str = obj.get('django_created', '')
        
        is_recent = False
        if created_str:
            try:
                created_date = datetime.fromisoformat(created_str.replace('Z', '+00:00')).date()
                is_recent = created_date >= today
            except:
                pass
        
        if is_recent and not has_legacy:
            categories['recent_no_legacy'].append(obj)
        elif is_recent and has_legacy:
            categories['recent_with_legacy'].append(obj)
        elif not is_recent and not has_legacy:
            categories['old_no_legacy'].append(obj)
        else:
            categories['old_with_legacy'].append(obj)
    
    print(f"\n📋 Категоризация объектов:")
    print(f"   🆕 Новые без legacy_id (скорее всего созданы в Django): {len(categories['recent_no_legacy'])}")
    print(f"   🧪 Новые с legacy_id (возможно тестовые): {len(categories['recent_with_legacy'])}")
    print(f"   📝 Старые без legacy_id (важные данные): {len(categories['old_no_legacy'])}")
    print(f"   ❓ Старые с legacy_id (потерянные из Joomla): {len(categories['old_with_legacy'])}")
    
    # Рекомендации по удалению
    print(f"\n💡 РЕКОМЕНДАЦИИ ПО УДАЛЕНИЮ:")
    
    # Безопасные для удаления
    safe_to_delete = []
    
    if categories['recent_with_legacy']:
        print(f"✅ Безопасно удалить: {len(categories['recent_with_legacy'])} новых объектов с legacy_id (возможно тестовые)")
        safe_to_delete.extend(categories['recent_with_legacy'])
    
    # Требуют осторожности
    if categories['recent_no_legacy']:
        print(f"⚠️  Осторожно: {len(categories['recent_no_legacy'])} новых объектов без legacy_id (могут быть важными)")
    
    if categories['old_no_legacy']:
        print(f"🛑 НЕ удалять: {len(categories['old_no_legacy'])} старых объектов без legacy_id (важные данные)")
    
    if categories['old_with_legacy']:
        print(f"❓ Проверить: {len(categories['old_with_legacy'])} старых объектов с legacy_id (возможно потеряны при импорте)")
    
    # Показываем примеры
    if safe_to_delete:
        print(f"\n📋 ОБЪЕКТЫ, БЕЗОПАСНЫЕ ДЛЯ УДАЛЕНИЯ ({len(safe_to_delete)}):")
        print("-" * 80)
        print(f"{'ID':<6} {'Legacy ID':<12} {'Title':<50}")
        print("-" * 80)
        
        for obj in safe_to_delete[:10]:
            title = obj['django_title'][:45] + '...' if len(obj['django_title']) > 45 else obj['django_title']
            legacy_id = obj.get('legacy_id', 'None')
            print(f"{obj['django_id']:<6} {legacy_id:<12} {title:<50}")
        
        if len(safe_to_delete) > 10:
            print(f"... и ещё {len(safe_to_delete) - 10} объектов")
    
    # Анализ изображений
    if safe_to_delete:
        safe_ids = [obj['django_id'] for obj in safe_to_delete]
        images_count = PropertyImage.objects.filter(property_id__in=safe_ids).count()
        print(f"\n📸 У безопасных для удаления объектов: {images_count} изображений")
    
    # Создаем план очистки
    cleanup_plan = {
        'timestamp': datetime.now().isoformat(),
        'analysis': {
            'total_django_only': len(django_only),
            'safe_to_delete': len(safe_to_delete),
            'need_review': len(django_only) - len(safe_to_delete)
        },
        'categories': {k: len(v) for k, v in categories.items()},
        'safe_to_delete': safe_to_delete,
        'recommendations': {
            'safe_deletion': safe_to_delete,
            'manual_review_needed': categories['old_with_legacy'] + categories['old_no_legacy'],
            'caution_required': categories['recent_no_legacy']
        }
    }
    
    with open('smart_cleanup_plan.json', 'w', encoding='utf-8') as f:
        json.dump(cleanup_plan, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 План умной очистки сохранен в: smart_cleanup_plan.json")
    
    return safe_to_delete


def execute_safe_cleanup(safe_objects, dry_run=True):
    """Выполняет безопасную очистку"""
    if not safe_objects:
        print("✅ Нет объектов для безопасного удаления")
        return
    
    property_ids = [obj['django_id'] for obj in safe_objects]
    
    if dry_run:
        print(f"\n🧪 ПРОБНЫЙ ЗАПУСК (dry run)")
        print(f"Будет удалено объектов: {len(property_ids)}")
        
        images_count = PropertyImage.objects.filter(property_id__in=property_ids).count()
        print(f"Будет удалено изображений: {images_count}")
        
        print("\nДля выполнения реального удаления установите dry_run=False")
        return
    
    print(f"\n🗑️  ВЫПОЛНЯЕМ БЕЗОПАСНОЕ УДАЛЕНИЕ...")
    
    try:
        with transaction.atomic():
            # Создаем резервную копию
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'deleted_objects': safe_objects,
                'reason': 'Safe cleanup - test objects with legacy_id created recently'
            }
            
            backup_file = f"safe_cleanup_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)
            
            # Удаляем изображения
            deleted_images = PropertyImage.objects.filter(property_id__in=property_ids).delete()
            print(f"🖼️  Удалено изображений: {deleted_images[0]}")
            
            # Удаляем объекты
            deleted_properties = Property.objects.filter(id__in=property_ids).delete()
            print(f"🏠 Удалено объектов: {deleted_properties[0]}")
            
            print(f"💾 Резервная копия: {backup_file}")
            print("✅ Безопасное удаление завершено!")
            
    except Exception as e:
        print(f"❌ Ошибка при удалении: {e}")


def main():
    """Основная функция"""
    print("🎯 УМНАЯ ОЧИСТКА БАЗЫ ДАННЫХ DJANGO")
    print("Анализ и безопасное удаление объектов")
    print("=" * 60)
    
    # Выполняем анализ
    safe_objects = analyze_django_objects()
    
    if safe_objects:
        print(f"\n🎯 РЕКОМЕНДАЦИЯ:")
        print(f"   Найдено {len(safe_objects)} объектов, безопасных для удаления")
        print(f"   Это новые объекты с legacy_id, вероятно созданные для тестирования")
        
        # Выполняем пробный запуск
        execute_safe_cleanup(safe_objects, dry_run=True)
        
        print(f"\n📝 Для выполнения реального удаления:")
        print(f"   execute_safe_cleanup(safe_objects, dry_run=False)")
    else:
        print(f"\n✅ Не найдено объектов, безопасных для автоматического удаления")
        print(f"   Все объекты требуют ручной проверки")


if __name__ == '__main__':
    main()