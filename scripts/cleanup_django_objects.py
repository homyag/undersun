#!/usr/bin/env python
"""
Скрипт для удаления объектов недвижимости из Django, которых нет в Joomla
ОСТОРОЖНО: Этот скрипт удаляет данные без возможности восстановления!
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


def load_comparison_data():
    """Загружает данные сравнения Joomla и Django"""
    try:
        with open('joomla_django_comparison.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Файл joomla_django_comparison.json не найден")
        print("Сначала запустите compare_joomla_django_objects.py")
        return None
    except json.JSONDecodeError:
        print("❌ Ошибка чтения JSON файла")
        return None


def analyze_objects_to_delete(comparison_data):
    """Анализирует объекты для удаления"""
    django_only_objects = comparison_data.get('django_only', [])
    
    if not django_only_objects:
        print("✅ Нет объектов для удаления - все объекты Django найдены в Joomla")
        return []
    
    print(f"📊 Найдено {len(django_only_objects)} объектов для удаления:")
    print("-" * 80)
    
    # Группируем по legacy_id для анализа
    by_legacy_pattern = {}
    no_legacy_id = []
    
    for obj in django_only_objects:
        legacy_id = obj.get('legacy_id')
        if legacy_id:
            pattern = legacy_id[:2] if len(legacy_id) >= 2 else legacy_id
            if pattern not in by_legacy_pattern:
                by_legacy_pattern[pattern] = []
            by_legacy_pattern[pattern].append(obj)
        else:
            no_legacy_id.append(obj)
    
    print("🔍 Анализ по типам legacy_id:")
    for pattern, objects in by_legacy_pattern.items():
        print(f"  {pattern}*: {len(objects)} объектов")
    
    if no_legacy_id:
        print(f"  Без legacy_id: {len(no_legacy_id)} объектов")
    
    return django_only_objects


def preview_deletion(objects_to_delete):
    """Предварительный просмотр объектов для удаления"""
    if not objects_to_delete:
        return
    
    print(f"\n📋 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР УДАЛЕНИЯ ({len(objects_to_delete)} объектов):")
    print("=" * 100)
    print(f"{'ID':<6} {'Legacy ID':<12} {'Title':<65} {'Created':<12}")
    print("-" * 100)
    
    # Показываем первые 20 объектов
    for i, obj in enumerate(objects_to_delete[:20]):
        title = obj['django_title'][:60] + '...' if len(obj['django_title']) > 60 else obj['django_title']
        created = obj.get('django_created', '')[:10] if obj.get('django_created') else 'N/A'
        legacy_id = obj.get('legacy_id', 'None')
        
        print(f"{obj['django_id']:<6} {legacy_id:<12} {title:<65} {created:<12}")
    
    if len(objects_to_delete) > 20:
        print(f"... и ещё {len(objects_to_delete) - 20} объектов")
    
    # Статистика по изображениям
    total_properties = [obj['django_id'] for obj in objects_to_delete]
    images_count = PropertyImage.objects.filter(property_id__in=total_properties).count()
    
    print(f"\n📸 Связанных изображений будет удалено: {images_count}")


def create_backup(objects_to_delete):
    """Создает резервную копию объектов перед удалением"""
    if not objects_to_delete:
        return None
    
    property_ids = [obj['django_id'] for obj in objects_to_delete]
    
    # Получаем полные данные объектов
    properties = Property.objects.filter(id__in=property_ids).values()
    images = PropertyImage.objects.filter(property_id__in=property_ids).values()
    
    backup_data = {
        'timestamp': datetime.now().isoformat(),
        'deleted_count': len(properties),
        'properties': list(properties),
        'images': list(images),
        'deletion_reason': 'Objects not found in Joomla database'
    }
    
    backup_filename = f"deleted_objects_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(backup_filename, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"💾 Резервная копия создана: {backup_filename}")
    return backup_filename


def delete_objects(objects_to_delete, create_backup_flag=True):
    """Удаляет объекты из базы данных Django"""
    if not objects_to_delete:
        print("✅ Нет объектов для удаления")
        return
    
    property_ids = [obj['django_id'] for obj in objects_to_delete]
    
    print(f"\n🗑️  НАЧИНАЕМ УДАЛЕНИЕ {len(property_ids)} ОБЪЕКТОВ...")
    
    # Создаем резервную копию
    backup_file = None
    if create_backup_flag:
        backup_file = create_backup(objects_to_delete)
    
    try:
        with transaction.atomic():
            # Сначала удаляем связанные изображения
            deleted_images = PropertyImage.objects.filter(property_id__in=property_ids).delete()
            print(f"🖼️  Удалено изображений: {deleted_images[0]}")
            
            # Затем удаляем объекты недвижимости
            deleted_properties = Property.objects.filter(id__in=property_ids).delete()
            print(f"🏠 Удалено объектов недвижимости: {deleted_properties[0]}")
            
            print("✅ Удаление завершено успешно!")
            
            # Создаем отчет об удалении
            create_deletion_report(objects_to_delete, backup_file)
            
    except Exception as e:
        print(f"❌ Ошибка при удалении: {e}")
        raise


def create_deletion_report(deleted_objects, backup_file):
    """Создает отчет об удалении"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'deleted_count': len(deleted_objects),
        'backup_file': backup_file,
        'deleted_objects': deleted_objects
    }
    
    report_filename = f"deletion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(report_filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"📊 Отчет об удалении создан: {report_filename}")


def main():
    """Основная функция"""
    print("🧹 ОЧИСТКА БАЗЫ ДАННЫХ DJANGO")
    print("Удаление объектов, отсутствующих в Joomla")
    print("=" * 60)
    
    # Загружаем данные сравнения
    comparison_data = load_comparison_data()
    if not comparison_data:
        return
    
    # Анализируем объекты для удаления
    objects_to_delete = analyze_objects_to_delete(comparison_data)
    if not objects_to_delete:
        return
    
    # Показываем предварительный просмотр
    preview_deletion(objects_to_delete)
    
    # Запрашиваем подтверждение
    print(f"\n⚠️  ВНИМАНИЕ: Вы собираетесь удалить {len(objects_to_delete)} объектов недвижимости!")
    print("   Это действие нельзя отменить!")
    print("   Будет создана резервная копия перед удалением.")
    
    confirm = input("\n❓ Вы уверены, что хотите продолжить? (yes/no): ").strip().lower()
    
    if confirm in ['yes', 'y', 'да']:
        delete_objects(objects_to_delete, create_backup_flag=True)
        
        # Проверяем результат
        remaining_count = Property.objects.count()
        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   Объектов осталось в базе: {remaining_count}")
        print(f"   Удалено объектов: {len(objects_to_delete)}")
        
    else:
        print("❌ Удаление отменено пользователем")


if __name__ == '__main__':
    main()