#!/usr/bin/env python
"""
Улучшенный скрипт для миграции фотографий из Joomla в Django
Использует точное сопоставление по legacy_id, площади и количеству спален
"""

import os
import sys
import json
import shutil
import re
from pathlib import Path
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from decimal import Decimal

# Добавляем путь к Django проекту
sys.path.append('/Users/igorantonov/MyProjects/undersunestate_django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from apps.properties.models import Property, PropertyImage


def load_photo_mapping():
    """Загружает маппинг фотографий из JSON файла"""
    # Сначала пытаемся загрузить улучшенную версию
    for filename in ['photo_mapping_improved.json', 'photo_mapping.json']:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                print(f"Загружен файл маппинга: {filename}")
                return json.load(f)
        except FileNotFoundError:
            continue
        except json.JSONDecodeError:
            print(f"Ошибка чтения JSON файла {filename}")
            continue
    
    print("Не найден ни один файл маппинга (photo_mapping_improved.json или photo_mapping.json)")
    return None


def extract_legacy_info_from_note(note):
    """Извлекает информацию из поля note (код проекта)"""
    if not note:
        return None, None, None
    
    # Удаляем пробелы
    note = note.strip()
    
    # Попытка извлечь информацию из legacy_id формата CN12-1BR-30M
    # Ищем паттерн: БУКВЫ-ЦИФРЫ-ЦИФРЫBR-ЦИФРЫM
    pattern = r'([A-Z]{2,4}\d+)-?(\d*)BR-?(\d+)M?'
    match = re.search(pattern, note)
    if match:
        project_code = match.group(1)
        bedrooms = int(match.group(2)) if match.group(2) else None
        area = int(match.group(3)) if match.group(3) else None
        return project_code, bedrooms, area
    
    # Если не подходит под паттерн, просто возвращаем код проекта
    return note, None, None


def find_property_by_joomla_data(joomla_record):
    """Находит объект недвижимости по данным из Joomla"""
    article_id = joomla_record['article_id']
    title = joomla_record['title']
    note = joomla_record.get('note', '')
    
    print(f"\n🔍 Поиск объекта для ID {article_id}: {title[:60]}...")
    print(f"   Код проекта (note): '{note}'")
    
    # Извлекаем информацию из note
    project_code, expected_bedrooms, expected_area = extract_legacy_info_from_note(note)
    print(f"   Извлечено: код={project_code}, спальни={expected_bedrooms}, площадь={expected_area}")
    
    # Стратегии поиска в порядке приоритета
    search_strategies = []
    
    # 1. Поиск по точному legacy_id (если есть note)
    if note:
        search_strategies.append(('legacy_id точное совпадение', lambda: Property.objects.filter(legacy_id__iexact=note)))
    
    # 2. Поиск по legacy_id содержащему код проекта
    if project_code:
        search_strategies.append(('legacy_id содержит код проекта', 
                                lambda: Property.objects.filter(legacy_id__icontains=project_code)))
    
    # 3. Поиск по названию + дополнительные критерии
    base_query = Property.objects.filter(title__icontains=title[:30])
    
    # Добавляем фильтры если есть информация
    if expected_bedrooms is not None:
        search_strategies.append(('название + спальни', 
                                lambda: base_query.filter(bedrooms=expected_bedrooms)))
    
    if expected_area is not None:
        # Поиск по площади с допуском ±5 кв.м
        area_min = expected_area - 5
        area_max = expected_area + 5
        search_strategies.append(('название + площадь', 
                                lambda: base_query.filter(area_total__gte=area_min, area_total__lte=area_max)))
    
    if expected_bedrooms is not None and expected_area is not None:
        area_min = expected_area - 5
        area_max = expected_area + 5
        search_strategies.append(('название + спальни + площадь', 
                                lambda: base_query.filter(
                                    bedrooms=expected_bedrooms,
                                    area_total__gte=area_min, 
                                    area_total__lte=area_max
                                )))
    
    # 4. Поиск только по названию (fallback)
    search_strategies.append(('только название', lambda: base_query))
    
    # Применяем стратегии поиска
    for strategy_name, strategy_func in search_strategies:
        try:
            properties = strategy_func()
            count = properties.count()
            print(f"   🎯 {strategy_name}: найдено {count} объектов")
            
            if count == 1:
                property_obj = properties.first()
                print(f"   ✅ НАЙДЕН: {property_obj.title}")
                print(f"      ID: {property_obj.id}, Legacy: {property_obj.legacy_id}")
                print(f"      Спальни: {property_obj.bedrooms}, Площадь: {property_obj.area_total}")
                return property_obj
            elif count > 1:
                print(f"   ⚠️  Найдено несколько объектов:")
                for prop in properties[:3]:
                    print(f"      - {prop.title[:50]}... (ID: {prop.id}, Legacy: {prop.legacy_id})")
                
                # Если найдено несколько, берем первый с подходящими характеристиками
                if expected_bedrooms is not None or expected_area is not None:
                    for prop in properties:
                        match_score = 0
                        if expected_bedrooms is not None and prop.bedrooms == expected_bedrooms:
                            match_score += 1
                        if expected_area is not None and prop.area_total:
                            area_diff = abs(float(prop.area_total) - expected_area)
                            if area_diff <= 5:
                                match_score += 1
                        
                        if match_score > 0:
                            print(f"   ✅ ВЫБРАН ПО ХАРАКТЕРИСТИКАМ: {prop.title}")
                            return prop
                
                # Если нет подходящих, берем первый
                property_obj = properties.first()
                print(f"   ⚠️  ВЫБРАН ПЕРВЫЙ: {property_obj.title}")
                return property_obj
                
        except Exception as e:
            print(f"   ❌ Ошибка в стратегии '{strategy_name}': {e}")
            continue
    
    print(f"   ❌ Объект не найден ни одной стратегией")
    return None


def copy_and_optimize_image(source_path, destination_path):
    """Копирует изображение и оптимизирует его"""
    try:
        # Создаем папку если её нет
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        # Открываем изображение
        with Image.open(source_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Ограничиваем размер (максимум 2048x2048)
            img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            
            # Сохраняем с оптимизацией
            img.save(destination_path, 'JPEG', quality=85, optimize=True)
            
        return True
    except Exception as e:
        print(f"Ошибка при копировании изображения {source_path}: {e}")
        return False


def migrate_photos():
    """Основная функция миграции фотографий"""
    # Загружаем маппинг
    mapping_data = load_photo_mapping()
    if not mapping_data:
        return
    
    # Пути
    source_media_path = Path('media/images_from_joomla/images')
    django_media_path = Path('media/properties')
    
    # Создаем папку для изображений Django
    django_media_path.mkdir(parents=True, exist_ok=True)
    
    # Статистика
    stats = {
        'total_objects': 0,
        'processed_objects': 0,
        'total_photos': 0,
        'migrated_photos': 0,
        'skipped_objects': 0,
        'errors': []
    }
    
    print(f"Начинаем улучшенную миграцию фотографий...")
    print(f"Всего объектов для обработки: {len(mapping_data['mappings'])}")
    
    # Группируем объекты по legacy_id для обнаружения дублей
    objects_by_legacy = {}
    for mapping in mapping_data['mappings']:
        note = mapping.get('note', '')
        if note not in objects_by_legacy:
            objects_by_legacy[note] = []
        objects_by_legacy[note].append(mapping)
    
    print(f"Найдено {len(objects_by_legacy)} уникальных кодов проектов")
    
    # Показываем статистику дублей
    duplicates = {k: v for k, v in objects_by_legacy.items() if len(v) > 1}
    if duplicates:
        print(f"Обнаружено {len(duplicates)} кодов с дублями:")
        for code, objects in duplicates.items():
            print(f"  {code}: {len(objects)} объектов")
    
    with transaction.atomic():
        for mapping in mapping_data['mappings']:
            stats['total_objects'] += 1
            article_id = mapping['article_id']
            photos = mapping['photos']
            
            # Пропускаем объекты без фотографий
            if not photos:
                print(f"⏭️  Пропуск объекта {article_id}: нет фотографий")
                stats['skipped_objects'] += 1
                continue
            
            # Ищем объект недвижимости
            try:
                property_obj = find_property_by_joomla_data(mapping)
                
                if not property_obj:
                    error_msg = f"Объект с ID {article_id} не найден в Django"
                    stats['errors'].append(error_msg)
                    print(f"  ❌ {error_msg}")
                    continue
                
                # Проверяем, есть ли уже изображения для этого объекта
                existing_images = PropertyImage.objects.filter(property=property_obj).count()
                if existing_images > 0:
                    print(f"  ⚠️  У объекта {property_obj.title[:50]}... уже есть {existing_images} изображений")
                    print(f"      Пропускаем для избежания дублей")
                    stats['skipped_objects'] += 1
                    continue
                
                print(f"  📸 Начинаем миграцию {len(photos)} фотографий...")
                
                # Обрабатываем фотографии
                migrated_count = 0
                for idx, photo_path in enumerate(photos):
                    stats['total_photos'] += 1
                    
                    # Полный путь к исходному файлу
                    source_file = source_media_path / photo_path
                    
                    if not source_file.exists():
                        error_msg = f"Файл не найден: {source_file}"
                        stats['errors'].append(error_msg)
                        print(f"    ⚠️  {error_msg}")
                        continue
                    
                    # Генерируем имя файла для Django
                    original_name = Path(photo_path).name
                    # Очищаем имя файла от спецсимволов
                    clean_name = "".join(c for c in original_name if c.isalnum() or c in '._-')
                    django_filename = f"{property_obj.id}_{idx+1:02d}_{clean_name}"
                    
                    # Путь для сохранения в Django
                    django_file_path = django_media_path / django_filename
                    
                    # Копируем и оптимизируем изображение
                    if copy_and_optimize_image(source_file, django_file_path):
                        # Создаем запись в базе данных
                        property_image = PropertyImage.objects.create(
                            property=property_obj,
                            image=f"properties/{django_filename}",
                            title=Path(photo_path).stem,
                            is_main=(idx == 0),  # Первое изображение делаем главным
                            order=idx + 1
                        )
                        
                        stats['migrated_photos'] += 1
                        migrated_count += 1
                        print(f"    ✅ {idx+1}/{len(photos)}: {django_filename}")
                    else:
                        error_msg = f"Ошибка копирования: {source_file}"
                        stats['errors'].append(error_msg)
                
                stats['processed_objects'] += 1
                print(f"  ✅ Завершено: {migrated_count}/{len(photos)} фотографий для {property_obj.title[:50]}...")
                
            except Exception as e:
                error_msg = f"Ошибка при обработке объекта {article_id}: {str(e)}"
                stats['errors'].append(error_msg)
                print(f"  ❌ {error_msg}")
                continue
    
    # Выводим статистику
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ УЛУЧШЕННОЙ МИГРАЦИИ ФОТОГРАФИЙ")
    print("="*70)
    print(f"Всего объектов: {stats['total_objects']}")
    print(f"Обработано объектов: {stats['processed_objects']}")
    print(f"Пропущено объектов: {stats['skipped_objects']}")
    print(f"Всего фотографий: {stats['total_photos']}")
    print(f"Мигрировано фотографий: {stats['migrated_photos']}")
    print(f"Ошибок: {len(stats['errors'])}")
    
    if stats['migrated_photos'] > 0:
        avg_photos = stats['migrated_photos'] / stats['processed_objects'] if stats['processed_objects'] > 0 else 0
        print(f"Среднее количество фото на объект: {avg_photos:.1f}")
    
    if stats['errors']:
        print("\n🚨 ОШИБКИ:")
        for i, error in enumerate(stats['errors'][:15], 1):  # Показываем первые 15 ошибок
            print(f"  {i:2d}. {error}")
        if len(stats['errors']) > 15:
            print(f"  ... и ещё {len(stats['errors']) - 15} ошибок")
    
    # Сохраняем подробную статистику
    with open('migration_improved_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"\nПодробная статистика сохранена в migration_improved_stats.json")


if __name__ == '__main__':
    migrate_photos()