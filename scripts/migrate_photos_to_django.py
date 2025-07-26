#!/usr/bin/env python
"""
Скрипт для миграции фотографий из Joomla в Django
Привязывает фотографии к объектам недвижимости используя photo_mapping.json
"""

import os
import sys
import json
import shutil
from pathlib import Path
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

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
        'errors': []
    }
    
    print(f"Начинаем миграцию фотографий...")
    print(f"Всего объектов для обработки: {len(mapping_data['mappings'])}")
    
    with transaction.atomic():
        for mapping in mapping_data['mappings']:
            stats['total_objects'] += 1
            article_id = mapping['article_id']
            photos = mapping['photos']
            
            # Ищем объект недвижимости по названию
            try:
                title = mapping['title']
                # Сначала пытаемся найти по точному названию
                property_obj = Property.objects.filter(title__iexact=title).first()
                
                if not property_obj:
                    # Если не найдено, ищем по части названия (первые 50 символов)
                    property_obj = Property.objects.filter(title__icontains=title[:50]).first()
                
                if not property_obj:
                    # Если всё ещё не найдено, ищем по legacy_id
                    property_obj = Property.objects.filter(legacy_id=article_id).first()
                
                if not property_obj:
                    raise Property.DoesNotExist(f"Объект с названием '{title}' не найден")
                
                print(f"Найден объект: {property_obj.title} (ID: {property_obj.id}, legacy_id: {property_obj.legacy_id})")
                
                # Удаляем старые изображения если есть
                PropertyImage.objects.filter(property=property_obj).delete()
                
                # Обрабатываем фотографии
                for idx, photo_path in enumerate(photos):
                    stats['total_photos'] += 1
                    
                    # Полный путь к исходному файлу
                    source_file = source_media_path / photo_path
                    
                    if not source_file.exists():
                        error_msg = f"Файл не найден: {source_file}"
                        stats['errors'].append(error_msg)
                        print(f"  ⚠️  {error_msg}")
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
                        with open(django_file_path, 'rb') as f:
                            property_image = PropertyImage.objects.create(
                                property=property_obj,
                                image=f"properties/{django_filename}",
                                title=Path(photo_path).stem,
                                is_main=(idx == 0),  # Первое изображение делаем главным
                                order=idx + 1
                            )
                        
                        stats['migrated_photos'] += 1
                        print(f"  ✅ Загружено: {django_filename}")
                    else:
                        error_msg = f"Ошибка копирования: {source_file}"
                        stats['errors'].append(error_msg)
                
                stats['processed_objects'] += 1
                print(f"  📸 Обработано {len(photos)} фотографий для объекта {property_obj.title}")
                
            except Property.DoesNotExist:
                error_msg = f"Объект с legacy_id={article_id} не найден в Django"
                stats['errors'].append(error_msg)
                print(f"  ❌ {error_msg}")
                continue
            except Exception as e:
                error_msg = f"Ошибка при обработке объекта {article_id}: {str(e)}"
                stats['errors'].append(error_msg)
                print(f"  ❌ {error_msg}")
                continue
    
    # Выводим статистику
    print("\n" + "="*50)
    print("РЕЗУЛЬТАТЫ МИГРАЦИИ ФОТОГРАФИЙ")
    print("="*50)
    print(f"Всего объектов: {stats['total_objects']}")
    print(f"Обработано объектов: {stats['processed_objects']}")
    print(f"Всего фотографий: {stats['total_photos']}")
    print(f"Мигрировано фотографий: {stats['migrated_photos']}")
    print(f"Ошибок: {len(stats['errors'])}")
    
    if stats['errors']:
        print("\n🚨 ОШИБКИ:")
        for error in stats['errors'][:10]:  # Показываем первые 10 ошибок
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... и ещё {len(stats['errors']) - 10} ошибок")
    
    # Сохраняем подробную статистику
    with open('migration_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"\nПодробная статистика сохранена в migration_stats.json")


if __name__ == '__main__':
    migrate_photos()