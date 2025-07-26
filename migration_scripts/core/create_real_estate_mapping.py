#!/usr/bin/env python
"""
Создание полного маппинга базы данных для объектов недвижимости
Извлекает данные из joomla_base.json и создает структурированный mapping
"""

import json
import re
from pathlib import Path
from collections import defaultdict

def load_joomla_data():
    """Загружает данные из дампа Joomla"""
    print("Загрузка данных из joomla_base.json...")
    with open('joomla_base.json', 'r', encoding='utf-8') as f:
        joomla_data = json.load(f)
    
    # Найдем таблицы
    tables = {}
    for item in joomla_data:
        if item.get('type') == 'table':
            table_name = item.get('name')
            if table_name:
                tables[table_name] = item.get('data', [])
                print(f"Найдена таблица {table_name}: {len(tables[table_name])} записей")
    
    return tables

def extract_project_code(note_field):
    """Извлекает код проекта из поля note"""
    if not note_field:
        return ""
    
    # Ищем коды вида VS161, VN352, CN1 и т.д.
    code_patterns = [
        r'\b([A-Z]{1,3}\d{1,4})\b',  # VS161, VN352, CN1, etc
        r'\b([A-Z]{2,4}-\d+)\b',      # VIP-123, etc
        r'\b([A-Z]{2}\d+[A-Z]*)\b',   # VS161A, etc
    ]
    
    for pattern in code_patterns:
        match = re.search(pattern, note_field.upper())
        if match:
            return match.group(1)
    
    return note_field.strip()

def determine_photo_folder(title, project_code, article_id):
    """Определяет папку с фотографиями на основе title и project_code"""
    
    # Сначала пробуем найти по коду проекта
    if project_code:
        # Простые варианты
        candidates = [
            project_code,
            f"{project_code}",
            f"{project_code}_project",
        ]
        
        # Добавляем варианты с названием
        if title:
            clean_title = re.sub(r'[^\w\s-]', '', title).strip()
            clean_title = re.sub(r'\s+', '_', clean_title)
            candidates.extend([
                f"{project_code}_{clean_title[:20]}",
                f"{project_code}_{clean_title.split('_')[0]}",
            ])
        
        return candidates[0]  # Возвращаем первый кандидат
    
    # Если нет кода проекта, используем название
    if title:
        clean_title = re.sub(r'[^\w\s-]', '', title).strip()
        clean_title = re.sub(r'\s+', '_', clean_title)
        return clean_title[:30]  # Ограничиваем длину
    
    # Fallback - используем ID
    return f"property_{article_id}"

def get_bedrooms_from_fields(fields_values, item_id):
    """Извлекает количество спален из field_id=93"""
    for field in fields_values:
        if (str(field.get('item_id')) == str(item_id) and 
            str(field.get('field_id')) == '93'):
            value = field.get('value', '')
            if value:
                # Извлекаем число из строки
                numbers = re.findall(r'\d+', str(value))
                if numbers:
                    return int(numbers[0])
    return None

def get_living_area_from_fields(fields_values, item_id):
    """Извлекает жилую площадь из field_id=92 (Size sq.m)"""
    for field in fields_values:
        if (str(field.get('item_id')) == str(item_id) and 
            str(field.get('field_id')) == '92'):
            value = field.get('value', '')
            if value:
                # Извлекаем число (может быть с точкой)
                numbers = re.findall(r'\d+\.?\d*', str(value))
                if numbers:
                    return float(numbers[0])
    return None

def extract_photo_files_from_content(content_text, images_field):
    """Извлекает имена файлов фотографий из контента и поля images"""
    photo_files = []
    
    # Извлекаем из поля images (JSON)
    if images_field and images_field.strip() and images_field != '{}':
        try:
            images_data = json.loads(images_field)
            if isinstance(images_data, dict):
                # Ищем intro_image и fulltext_image
                intro_image = images_data.get('image_intro', '')
                fulltext_image = images_data.get('image_fulltext', '')
                
                for img in [intro_image, fulltext_image]:
                    if img and img.strip():
                        # Извлекаем имя файла
                        filename = img.split('/')[-1]
                        if filename and filename not in photo_files:
                            photo_files.append(filename)
        except:
            pass
    
    # Извлекаем из контента (ищем img src)
    if content_text:
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        matches = re.findall(img_pattern, content_text, re.IGNORECASE)
        
        for img_src in matches:
            # Извлекаем имя файла
            filename = img_src.split('/')[-1]
            if filename and '.' in filename and filename not in photo_files:
                photo_files.append(filename)
    
    return photo_files

def get_gallery_images_from_fields(fields_values, item_id):
    """Извлекает изображения галереи из field_id=3"""
    gallery_images = []
    
    for field in fields_values:
        if (str(field.get('item_id')) == str(item_id) and 
            str(field.get('field_id')) == '3'):
            value = field.get('value', '')
            if value and value.strip():
                # Если это JSON, пробуем распарсить
                try:
                    if value.startswith('[') or value.startswith('{'):
                        gallery_data = json.loads(value)
                        if isinstance(gallery_data, list):
                            for item in gallery_data:
                                if isinstance(item, dict) and 'image' in item:
                                    img_path = item['image']
                                    filename = img_path.split('/')[-1]
                                    if filename not in gallery_images:
                                        gallery_images.append(filename)
                                elif isinstance(item, str):
                                    filename = item.split('/')[-1]
                                    if filename not in gallery_images:
                                        gallery_images.append(filename)
                        elif isinstance(gallery_data, dict) and 'image' in gallery_data:
                            img_path = gallery_data['image']
                            filename = img_path.split('/')[-1]
                            if filename not in gallery_images:
                                gallery_images.append(filename)
                except:
                    # Если не JSON, ищем пути к изображениям
                    img_pattern = r'([^/\s]+\.(jpg|jpeg|png|gif|webp))'
                    matches = re.findall(img_pattern, value, re.IGNORECASE)
                    for match in matches:
                        filename = match[0]
                        if filename not in gallery_images:
                            gallery_images.append(filename)
    
    return gallery_images

def load_existing_photo_mappings():
    """Загружает существующие photo mappings для сопоставления"""
    photo_mappings = {}
    
    # Пробуем загрузить лучший доступный mapping
    mapping_files = [
        'photo_mapping_smart_verified.json',
        'photo_mapping_complete_with_folders.json',
        'photo_mapping_ultimate_fixed.json',
        'photo_mapping_ultimate.json'
    ]
    
    for mapping_file in mapping_files:
        if Path(mapping_file).exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    mappings = data.get('mappings', [])
                    
                    for mapping in mappings:
                        article_id = mapping.get('article_id')
                        photos = mapping.get('photos', [])
                        folder_matched = mapping.get('folder_matched', '')
                        
                        if article_id:
                            photo_mappings[str(article_id)] = {
                                'photos': photos,
                                'folder': folder_matched
                            }
                    
                    print(f"Загружен existing mapping из {mapping_file}: {len(photo_mappings)} объектов")
                    break
            except Exception as e:
                print(f"Ошибка загрузки {mapping_file}: {e}")
                continue
    
    return photo_mappings

def create_real_estate_mapping():
    """Создает полный маппинг объектов недвижимости"""
    
    # Загружаем данные
    tables = load_joomla_data()
    content_data = tables.get('ec9oj_content', [])
    fields_data = tables.get('ec9oj_fields_values', [])
    categories_data = tables.get('ec9oj_categories', [])
    
    # Загружаем существующие photo mappings
    existing_photos = load_existing_photo_mappings()
    
    # Создаем карту категорий
    category_map = {}
    for cat in categories_data:
        category_map[cat.get('id')] = cat.get('title', 'Unknown')
    
    # Категории недвижимости (исключаем blog, agents, news и т.д.)
    excluded_catids = [2, 8, 25, 26, 49, 50, 51, 56, 57, 59, 60, 63]
    
    print("Анализ объектов недвижимости...")
    
    properties = []
    stats = {
        'total_processed': 0,
        'real_estate_found': 0,
        'with_project_code': 0,
        'with_bedrooms': 0,
        'with_living_area': 0,
        'with_photos': 0,
        'categories': defaultdict(int)
    }
    
    for content_item in content_data:
        stats['total_processed'] += 1
        
        catid = content_item.get('catid')
        
        # Пропускаем исключенные категории
        if catid in excluded_catids:
            continue
            
        # Проверяем, что это недвижимость по ключевым словам в заголовке
        title = content_item.get('title', '').lower()
        real_estate_keywords = [
            'bedroom', 'villa', 'house', 'condo', 'apartment', 
            'townhouse', 'land', 'pool', 'room', 'studio',
            'penthouse', 'duplex', 'loft', 'estate'
        ]
        
        if not any(keyword in title for keyword in real_estate_keywords):
            continue
            
        stats['real_estate_found'] += 1
        stats['categories'][catid] += 1
        
        # Извлекаем основные данные
        article_id = str(content_item.get('id', ''))
        title = content_item.get('title', '')
        note = content_item.get('note', '')
        introtext = content_item.get('introtext', '')
        fulltext = content_item.get('fulltext', '')
        images_field = content_item.get('images', '')
        
        # Извлекаем код проекта
        project_code = extract_project_code(note)
        if project_code:
            stats['with_project_code'] += 1
        
        # Извлекаем количество спален
        bedrooms = get_bedrooms_from_fields(fields_data, article_id)
        if bedrooms is not None:
            stats['with_bedrooms'] += 1
        
        # Извлекаем жилую площадь
        living_area = get_living_area_from_fields(fields_data, article_id)
        if living_area is not None:
            stats['with_living_area'] += 1
        
        # Определяем папку с фото
        photo_folder = determine_photo_folder(title, project_code, article_id)
        
        # Собираем список фотографий
        photo_files = []
        
        # Используем существующий mapping если есть
        if article_id in existing_photos:
            existing_data = existing_photos[article_id]
            photo_files = existing_data.get('photos', [])
            if existing_data.get('folder'):
                photo_folder = existing_data['folder']
        else:
            # Извлекаем из контента и images
            content_photos = extract_photo_files_from_content(
                introtext + ' ' + fulltext, images_field
            )
            photo_files.extend(content_photos)
            
            # Извлекаем из галереи (field_id=3)
            gallery_photos = get_gallery_images_from_fields(fields_data, article_id)
            photo_files.extend(gallery_photos)
            
            # Удаляем дубликаты
            photo_files = list(dict.fromkeys(photo_files))
        
        if photo_files:
            stats['with_photos'] += 1
        
        # Создаем запись объекта
        property_record = {
            "id": article_id,
            "title": title,
            "project_code": project_code,
            "bedrooms": bedrooms,
            "living_area": living_area,
            "photo_folder": photo_folder,
            "photo_files": photo_files,
            "category_id": catid,
            "category_name": category_map.get(catid, f'Unknown {catid}'),
            "note": note,
            "photo_count": len(photo_files)
        }
        
        properties.append(property_record)
    
    # Сортируем по ID
    properties.sort(key=lambda x: int(x['id']))
    
    # Создаем финальную структуру
    result = {
        "metadata": {
            "source": "joomla_base.json",
            "creation_date": "2025-01-22",
            "description": "Полный маппинг объектов недвижимости с извлечением данных из Joomla DB",
            "total_properties": len(properties),
            "statistics": dict(stats)
        },
        "properties": properties
    }
    
    # Сохраняем результат
    output_file = 'real_estate_mapping.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # Выводим статистику
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ АНАЛИЗА")
    print("="*60)
    print(f"Всего обработано записей: {stats['total_processed']:,}")
    print(f"Найдено объектов недвижимости: {stats['real_estate_found']:,}")
    print(f"С кодом проекта: {stats['with_project_code']:,}")
    print(f"С количеством спален: {stats['with_bedrooms']:,}")
    print(f"С жилой площадью: {stats['with_living_area']:,}")
    print(f"С фотографиями: {stats['with_photos']:,}")
    
    print(f"\nТОП-10 категорий по количеству объектов:")
    sorted_cats = sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True)
    for catid, count in sorted_cats[:10]:
        cat_name = category_map.get(catid, f'Unknown {catid}')
        print(f"  {catid:>2}: {count:3d} объектов - {cat_name}")
    
    print(f"\nРезультат сохранен в {output_file}")
    
    # Примеры записей
    if properties:
        print(f"\nПримеры записей:")
        for i, prop in enumerate(properties[:3]):
            print(f"\n{i+1}. ID {prop['id']}: {prop['title'][:50]}...")
            print(f"   Код проекта: {prop['project_code']}")
            print(f"   Спальни: {prop['bedrooms']}")
            print(f"   Площадь: {prop['living_area']}")
            print(f"   Папка фото: {prop['photo_folder']}")
            print(f"   Количество фото: {prop['photo_count']}")
    
    return result

if __name__ == '__main__':
    create_real_estate_mapping()