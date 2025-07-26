#!/usr/bin/env python
"""
Смарт-скрипт для миграции фотографий из Joomla в Django
Использует интеллектуальное сопоставление по характеристикам объектов
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
    
    print("Не найден ни один файл маппинга")
    return None


def extract_features_from_title(title):
    """Извлекает характеристики из названия объекта"""
    features = {
        'bedrooms': None,
        'is_studio': False,
        'area_approx': None,
        'keywords': []
    }
    
    title_lower = title.lower()
    
    # Определяем тип жилья
    if 'studio' in title_lower:
        features['is_studio'] = True
        features['bedrooms'] = 0
    else:
        # Ищем количество спален
        bedroom_patterns = [
            r'(\d+)\s*bedroom',
            r'(\d+)\s*br',
            r'(\d+)br'
        ]
        for pattern in bedroom_patterns:
            match = re.search(pattern, title_lower)
            if match:
                features['bedrooms'] = int(match.group(1))
                break
    
    # Извлекаем ключевые слова для дополнительной фильтрации
    keywords = []
    if 'jacuzzi' in title_lower:
        keywords.append('jacuzzi')
    if 'terrace' in title_lower or 'garden' in title_lower:
        keywords.append('terrace')
    if 'apartment hotel' in title_lower:
        keywords.append('hotel')
    if 'terra grove' in title_lower:
        keywords.append('terra_grove')
    if 'serene condo' in title_lower:
        keywords.append('serene_condo')
    if 'urban scapes' in title_lower:
        keywords.append('urban_scapes')
    
    features['keywords'] = keywords
    
    return features


def calculate_compatibility_score(joomla_record, django_property):
    """Вычисляет совместимость между записью Joomla и объектом Django"""
    score = 0
    reasons = []
    
    # Извлекаем характеристики из названий
    joomla_features = extract_features_from_title(joomla_record['title'])
    django_title = django_property.title
    django_features = extract_features_from_title(django_title)
    
    # Проверяем тип жилья (студия vs спальни)
    if joomla_features['is_studio'] and django_features['is_studio']:
        score += 10
        reasons.append("Оба - студии")
    elif (joomla_features['bedrooms'] is not None and 
          django_property.bedrooms is not None and 
          joomla_features['bedrooms'] == django_property.bedrooms):
        score += 10
        reasons.append(f"Совпадение спален: {joomla_features['bedrooms']}")
    elif joomla_features['is_studio'] != django_features['is_studio']:
        score -= 5
        reasons.append("Несовпадение типа жилья")
    
    # Проверяем площадь (если есть в legacy_id Django объекта)
    django_legacy = django_property.legacy_id or ''
    area_match = re.search(r'(\d+)M$', django_legacy)
    if area_match:
        django_area_from_legacy = int(area_match.group(1))
        # Студии обычно 30-50 кв.м, 1BR - 40-80 кв.м, 2BR - 60-120 кв.м
        if joomla_features['is_studio'] and 25 <= django_area_from_legacy <= 55:
            score += 5
            reasons.append(f"Площадь подходит для студии: {django_area_from_legacy}м²")
        elif (joomla_features['bedrooms'] == 1 and 35 <= django_area_from_legacy <= 85):
            score += 5
            reasons.append(f"Площадь подходит для 1BR: {django_area_from_legacy}м²")
        elif (joomla_features['bedrooms'] == 2 and 60 <= django_area_from_legacy <= 120):
            score += 5
            reasons.append(f"Площадь подходит для 2BR: {django_area_from_legacy}м²")
        elif (joomla_features['bedrooms'] == 3 and 90 <= django_area_from_legacy <= 150):
            score += 5
            reasons.append(f"Площадь подходит для 3BR: {django_area_from_legacy}м²")
    
    # Проверяем ключевые слова
    common_keywords = set(joomla_features['keywords']) & set(django_features['keywords'])
    if common_keywords:
        score += len(common_keywords) * 3
        reasons.append(f"Общие ключевые слова: {', '.join(common_keywords)}")
    
    # Проверяем совпадение названий проектов
    joomla_title_lower = joomla_record['title'].lower()
    django_title_lower = django_title.lower()
    
    # Специальные проекты
    if 'layan green park' in joomla_title_lower and 'layan green park' in django_title_lower:
        score += 8
        reasons.append("Проект: Layan Green Park")
    elif 'momentum' in joomla_title_lower and 'momentum' in django_title_lower:
        score += 8
        reasons.append("Проект: Momentum")
    elif 'aura condominium' in joomla_title_lower and 'aura condominium' in django_title_lower:
        score += 8
        reasons.append("Проект: AURA Condominium")
    elif 'akra collection' in joomla_title_lower and 'akra collection' in django_title_lower:
        score += 8
        reasons.append("Проект: Akra collection")
    
    # Проверяем район/локацию
    locations = ['layan', 'rawai', 'bang tao', 'chalong', 'thalang', 'laguna']
    for location in locations:
        if location in joomla_title_lower and location in django_title_lower:
            score += 3
            reasons.append(f"Район: {location.title()}")
            break
    
    return score, reasons


def find_best_property_match(joomla_record, candidate_properties):
    """Находит наилучшее соответствие среди кандидатов"""
    best_property = None
    best_score = 0
    best_reasons = []
    
    print(f"   🧠 Анализируем {len(candidate_properties)} кандидатов...")
    
    for prop in candidate_properties:
        # Проверяем, нет ли уже изображений
        existing_images = PropertyImage.objects.filter(property=prop).count()
        if existing_images > 0:
            print(f"      ⏭️  {prop.legacy_id} уже имеет {existing_images} изображений - пропускаем")
            continue
            
        score, reasons = calculate_compatibility_score(joomla_record, prop)
        
        print(f"      🔢 {prop.legacy_id} ({prop.title[:40]}...): {score} баллов")
        for reason in reasons[:3]:  # Показываем первые 3 причины
            print(f"         • {reason}")
        
        if score > best_score:
            best_score = score
            best_property = prop
            best_reasons = reasons
    
    if best_property:
        print(f"   🏆 ЛУЧШИЙ КАНДИДАТ: {best_property.legacy_id} ({best_score} баллов)")
        print(f"      {best_property.title}")
        for reason in best_reasons:
            print(f"      ✓ {reason}")
    
    return best_property, best_score


def find_property_by_joomla_data(joomla_record):
    """Находит объект недвижимости по данным из Joomla с умным сопоставлением"""
    article_id = joomla_record['article_id']
    title = joomla_record['title']
    note = joomla_record.get('note', '')
    
    print(f"\n🔍 Умный поиск для ID {article_id}: {title[:60]}...")
    print(f"   Код проекта: '{note}'")
    
    # Стратегия 1: Точное совпадение по legacy_id
    if note.strip():
        exact_match = Property.objects.filter(legacy_id__iexact=note.strip()).first()
        if exact_match:
            existing_images = PropertyImage.objects.filter(property=exact_match).count()
            if existing_images == 0:
                print(f"   ✅ ТОЧНОЕ СОВПАДЕНИЕ: {exact_match.legacy_id}")
                return exact_match
            else:
                print(f"   ⏭️  Точное совпадение {exact_match.legacy_id} уже имеет {existing_images} изображений")
    
    # Стратегия 2: Поиск по коду проекта + умное сопоставление
    if note.strip():
        candidates = Property.objects.filter(legacy_id__icontains=note.strip())
        if candidates.exists():
            print(f"   🎯 Найдено {candidates.count()} кандидатов по коду проекта")
            best_match, score = find_best_property_match(joomla_record, candidates)
            if best_match and score >= 10:  # Минимальный порог
                return best_match
    
    # Стратегия 3: Поиск по названию + умное сопоставление
    title_candidates = Property.objects.filter(title__icontains=title[:30])
    if title_candidates.exists():
        print(f"   🎯 Найдено {title_candidates.count()} кандидатов по названию")
        best_match, score = find_best_property_match(joomla_record, title_candidates)
        if best_match and score >= 8:  # Более низкий порог для поиска по названию
            return best_match
    
    print(f"   ❌ Подходящий объект не найден")
    return None


def copy_and_optimize_image(source_path, destination_path):
    """Копирует изображение и оптимизирует его"""
    try:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        with Image.open(source_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            img.save(destination_path, 'JPEG', quality=85, optimize=True)
            
        return True
    except Exception as e:
        print(f"Ошибка при копировании изображения {source_path}: {e}")
        return False


def migrate_photos():
    """Основная функция миграции фотографий"""
    mapping_data = load_photo_mapping()
    if not mapping_data:
        return
    
    source_media_path = Path('media/images_from_joomla/images')
    django_media_path = Path('media/properties')
    django_media_path.mkdir(parents=True, exist_ok=True)
    
    stats = {
        'total_objects': 0,
        'processed_objects': 0,
        'total_photos': 0,
        'migrated_photos': 0,
        'skipped_objects': 0,
        'errors': []
    }
    
    print(f"Начинаем СМАРТ-миграцию фотографий...")
    print(f"Всего объектов для обработки: {len(mapping_data['mappings'])}")
    
    # Сначала очищаем все существующие изображения для чистого теста
    PropertyImage.objects.all().delete()
    print("Все существующие изображения удалены для чистого теста")
    
    with transaction.atomic():
        for mapping in mapping_data['mappings']:
            stats['total_objects'] += 1
            article_id = mapping['article_id']
            photos = mapping['photos']
            
            if not photos:
                print(f"⏭️  Пропуск объекта {article_id}: нет фотографий")
                stats['skipped_objects'] += 1
                continue
            
            try:
                property_obj = find_property_by_joomla_data(mapping)
                
                if not property_obj:
                    error_msg = f"Объект с ID {article_id} не найден"
                    stats['errors'].append(error_msg)
                    print(f"  ❌ {error_msg}")
                    continue
                
                print(f"  📸 Начинаем миграцию {len(photos)} фотографий...")
                
                migrated_count = 0
                for idx, photo_path in enumerate(photos):
                    stats['total_photos'] += 1
                    
                    source_file = source_media_path / photo_path
                    
                    if not source_file.exists():
                        error_msg = f"Файл не найден: {source_file}"
                        stats['errors'].append(error_msg)
                        print(f"    ⚠️  {error_msg}")
                        continue
                    
                    original_name = Path(photo_path).name
                    clean_name = "".join(c for c in original_name if c.isalnum() or c in '._-')
                    django_filename = f"{property_obj.id}_{idx+1:02d}_{clean_name}"
                    django_file_path = django_media_path / django_filename
                    
                    if copy_and_optimize_image(source_file, django_file_path):
                        property_image = PropertyImage.objects.create(
                            property=property_obj,
                            image=f"properties/{django_filename}",
                            title=Path(photo_path).stem,
                            is_main=(idx == 0),
                            order=idx + 1
                        )
                        
                        stats['migrated_photos'] += 1
                        migrated_count += 1
                        if migrated_count <= 3 or migrated_count == len(photos):
                            print(f"    ✅ {idx+1}/{len(photos)}: {django_filename}")
                        elif migrated_count == 4:
                            print(f"    ✅ ... (продолжается)")
                    else:
                        error_msg = f"Ошибка копирования: {source_file}"
                        stats['errors'].append(error_msg)
                
                stats['processed_objects'] += 1
                print(f"  ✅ Завершено: {migrated_count}/{len(photos)} фотографий")
                
            except Exception as e:
                error_msg = f"Ошибка при обработке объекта {article_id}: {str(e)}"
                stats['errors'].append(error_msg)
                print(f"  ❌ {error_msg}")
                continue
    
    # Выводим статистику
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ СМАРТ-МИГРАЦИИ ФОТОГРАФИЙ")
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
        for i, error in enumerate(stats['errors'][:10], 1):
            print(f"  {i:2d}. {error}")
        if len(stats['errors']) > 10:
            print(f"  ... и ещё {len(stats['errors']) - 10} ошибок")
    
    with open('migration_smart_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"\nПодробная статистика сохранена в migration_smart_stats.json")


if __name__ == '__main__':
    migrate_photos()