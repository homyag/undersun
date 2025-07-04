#!/usr/bin/env python3
"""
Анализ изображений недвижимости из базы данных Joomla
"""

import json
import re
from typing import Dict, List, Set
from pathlib import Path

def extract_image_paths(text: str) -> List[str]:
    """Извлекает все пути к изображениям из текста"""
    if not text:
        return []
    
    # Поиск всех путей к изображениям
    image_patterns = [
        r'images[/\\\\]+[^"\'>\s\}]+',  # Общий паттерн для изображений с экранированными слешами
        r'src="(images[/\\\\]+[^"]*)"',  # Изображения в src
        r'src=\\"(images[/\\\\]+[^"]*)\\"',  # Экранированные кавычки
        r'"image_intro":"(images[/\\\\]+[^"]*)"',  # JSON image_intro
        r'"image_fulltext":"(images[/\\\\]+[^"]*)"',  # JSON image_fulltext
        r'"Image":"(images[/\\\\]+[^"]*)"',  # JSON структуры
        r'\\"Image\\":\\"(images[/\\\\]+[^"]*)\\"',  # Экранированные JSON структуры
    ]
    
    all_paths = []
    for pattern in image_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Если в pattern есть группы, берем их, иначе весь match
            if '(' in pattern:
                all_paths.extend(matches)
            else:
                all_paths.extend(matches)
    
    # Убираем дубликаты, нормализуем пути и сортируем
    normalized_paths = []
    for path in all_paths:
        # Заменяем экранированные слеши на обычные
        normalized_path = path.replace('\\/', '/').replace('\\\\', '/')
        normalized_paths.append(normalized_path)
    
    unique_paths = list(set(normalized_paths))
    unique_paths.sort()
    
    return unique_paths

def analyze_content_table(data: List[Dict]) -> Dict:
    """Анализирует таблицу ec9oj_content на предмет изображений недвижимости"""
    
    # Папки проектов недвижимости (расширенный список)
    property_folders = [
        'AURA_Condominium',
        'Akra_collection_Layan',
        'Alisha_Garden_View',
        'Ananda_Layan',
        'Aqua_Boutique',
        'Azur_Samui',
        'Bangtao_Grand_Villa',
        'Barolo_Residences',
        'Botanica_Foresta',
        'Botanica_Luxury_Villas',
        'Botanica_Phase_9',
        'Botanica_The_Residence',
        'Botanica_Thep_Krasatti',
        'Botanica_Villas',
        'Burasari_Patong',
        'Cassia_Laguna',
        'Dusit_Grand_Park',
        'Ekkamai_Living',
        'Himma_Luxury_Villas',
        'Kamala_Hills',
        'Karnkanok_Ville',
        'Laguna_Park',
        'Layan_Estate',
        'Layan_Green_Park',
        'Layan_Tara',
        'Mono_Loft',
        'Nakara_Villas',
        'Nara_Villas',
        'Oceana_Surin',
        'Phuket_Villas',
        'Rawayana_Pool_Villas',
        'Rawai_VIP_Villas',
        'Residences_Overlook',
        'Sanctuary_Lakes',
        'Sava_Beach_Villas',
        'Seava_Estate',
        'Thalang_Garden',
        'The_Loft_Bangtao',
        'The_Residence_Bangtao',
        'Townhouse_Rawai',
        'Tri_Vananda',
        'VanBelle_Condo',
        'Villa_Samakee',
        'Villas_Botanica',
        'Villas_Samui',
        'Waterfront_Surin',
        'Zire_Wongamat'
    ]
    
    results = []
    processed_count = 0
    
    for item in data:
        try:
            processed_count += 1
            if processed_count % 100 == 0:
                print(f"Обработано записей: {processed_count}")
            
            # Проверяем, что это запись из таблицы ec9oj_content
            if not isinstance(item, dict) or 'id' not in item:
                continue
                
            # Собираем все текстовые поля где могут быть изображения
            text_fields = []
            if 'introtext' in item and item['introtext']:
                text_fields.append(item['introtext'])
            if 'fulltext' in item and item['fulltext']:
                text_fields.append(item['fulltext'])
            if 'images' in item and item['images']:
                text_fields.append(item['images'])
            
            # Объединяем все текстовые поля
            combined_text = ' '.join(text_fields)
            
            # Извлекаем все пути к изображениям
            image_paths = extract_image_paths(combined_text)
            
            if not image_paths:
                continue
                
            # Проверяем, есть ли изображения из папок недвижимости
            property_images = []
            for path in image_paths:
                for folder in property_folders:
                    if folder in path:
                        property_images.append(path)
                        break
            
            # Если найдены изображения недвижимости, добавляем в результат
            if property_images:
                result_item = {
                    'id': item.get('id', ''),
                    'title': item.get('title', ''),
                    'alias': item.get('alias', ''),
                    'image_paths': property_images,
                    'all_image_paths': image_paths,  # Все найденные изображения
                    'created': item.get('created', ''),
                    'modified': item.get('modified', ''),
                    'state': item.get('state', ''),
                    'catid': item.get('catid', '')
                }
                results.append(result_item)
        
        except Exception as e:
            print(f"Ошибка при обработке записи: {e}")
            continue
    
    return {
        'total_found': len(results),
        'records': results
    }

def analyze_fields_values(data: List[Dict], content_records: Dict) -> Dict:
    """Анализирует таблицу ec9oj_fields_values для дополнительных изображений"""
    
    # Создаем словарь для быстрого поиска
    content_dict = {record['id']: record for record in content_records['records']}
    
    # Обрабатываем field_values
    field_images = {}
    for item in data:
        if isinstance(item, dict) and 'item_id' in item and 'value' in item:
            item_id = item['item_id']
            value = item['value']
            
            # Ищем изображения в значении поля
            image_paths = extract_image_paths(value)
            
            if image_paths:
                if item_id not in field_images:
                    field_images[item_id] = []
                field_images[item_id].extend(image_paths)
    
    # Добавляем найденные изображения к существующим записям
    updated_records = []
    for record in content_records['records']:
        item_id = record['id']
        updated_record = record.copy()
        
        # Добавляем изображения из field_values если есть
        if item_id in field_images:
            additional_images = field_images[item_id]
            # Фильтруем только изображения недвижимости
            property_folders = [
                'AURA_Condominium', 'Akra_collection_Layan', 'Alisha_Garden_View',
                'Ananda_Layan', 'Aqua_Boutique', 'Azur_Samui', 'Bangtao_Grand_Villa',
                'Barolo_Residences', 'Botanica_Foresta', 'Botanica_Luxury_Villas',
                'Botanica_Phase_9', 'Botanica_The_Residence', 'Botanica_Thep_Krasatti',
                'Botanica_Villas', 'Burasari_Patong', 'Cassia_Laguna', 'Dusit_Grand_Park',
                'Ekkamai_Living', 'Himma_Luxury_Villas', 'Kamala_Hills', 'Karnkanok_Ville',
                'Laguna_Park', 'Layan_Estate', 'Layan_Green_Park', 'Layan_Tara',
                'Mono_Loft', 'Nakara_Villas', 'Nara_Villas', 'Oceana_Surin',
                'Phuket_Villas', 'Rawayana_Pool_Villas', 'Rawai_VIP_Villas',
                'Residences_Overlook', 'Sanctuary_Lakes', 'Sava_Beach_Villas',
                'Seava_Estate', 'Thalang_Garden', 'The_Loft_Bangtao',
                'The_Residence_Bangtao', 'Townhouse_Rawai', 'Tri_Vananda',
                'VanBelle_Condo', 'Villa_Samakee', 'Villas_Botanica',
                'Villas_Samui', 'Waterfront_Surin', 'Zire_Wongamat'
            ]
            
            property_images = []
            for img in additional_images:
                for folder in property_folders:
                    if folder in img:
                        property_images.append(img)
                        break
            
            if property_images:
                # Объединяем с существующими изображениями
                all_property_images = list(set(updated_record['image_paths'] + property_images))
                all_images = list(set(updated_record['all_image_paths'] + additional_images))
                
                updated_record['image_paths'] = sorted(all_property_images)
                updated_record['all_image_paths'] = sorted(all_images)
        
        updated_records.append(updated_record)
    
    # Ищем новые записи только в field_values (которых нет в content)
    for item_id, images in field_images.items():
        if item_id not in content_dict:
            # Проверяем, есть ли изображения недвижимости
            property_folders = [
                'AURA_Condominium', 'Akra_collection_Layan', 'Alisha_Garden_View',
                'Ananda_Layan', 'Aqua_Boutique', 'Azur_Samui', 'Bangtao_Grand_Villa',
                'Barolo_Residences', 'Botanica_Foresta', 'Botanica_Luxury_Villas',
                'Botanica_Phase_9', 'Botanica_The_Residence', 'Botanica_Thep_Krasatti',
                'Botanica_Villas', 'Burasari_Patong', 'Cassia_Laguna', 'Dusit_Grand_Park',
                'Ekkamai_Living', 'Himma_Luxury_Villas', 'Kamala_Hills', 'Karnkanok_Ville',
                'Laguna_Park', 'Layan_Estate', 'Layan_Green_Park', 'Layan_Tara',
                'Mono_Loft', 'Nakara_Villas', 'Nara_Villas', 'Oceana_Surin',
                'Phuket_Villas', 'Rawayana_Pool_Villas', 'Rawai_VIP_Villas',
                'Residences_Overlook', 'Sanctuary_Lakes', 'Sava_Beach_Villas',
                'Seava_Estate', 'Thalang_Garden', 'The_Loft_Bangtao',
                'The_Residence_Bangtao', 'Townhouse_Rawai', 'Tri_Vananda',
                'VanBelle_Condo', 'Villa_Samakee', 'Villas_Botanica',
                'Villas_Samui', 'Waterfront_Surin', 'Zire_Wongamat'
            ]
            
            property_images = []
            for img in images:
                for folder in property_folders:
                    if folder in img:
                        property_images.append(img)
                        break
            
            if property_images:
                # Создаем новую запись
                new_record = {
                    'id': item_id,
                    'title': f'Запись только в field_values (ID: {item_id})',
                    'alias': f'field-values-only-{item_id}',
                    'image_paths': sorted(property_images),
                    'all_image_paths': sorted(images),
                    'created': '',
                    'modified': '',
                    'state': 'unknown',
                    'catid': 'unknown'
                }
                updated_records.append(new_record)
    
    return {
        'total_found': len(updated_records),
        'records': updated_records
    }

def main():
    """Основная функция"""
    json_file = Path('joomla_base.json')
    
    if not json_file.exists():
        print(f"Файл {json_file} не найден!")
        return
    
    print("Загрузка данных из JSON файла...")
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Ошибка при чтении JSON файла: {e}")
        return
    
    # Находим таблицы
    content_table_data = None
    fields_values_data = None
    
    for item in data:
        if isinstance(item, dict):
            if item.get('name') == 'ec9oj_content':
                content_table_data = item.get('data', [])
            elif item.get('name') == 'ec9oj_fields_values':
                fields_values_data = item.get('data', [])
    
    if not content_table_data:
        print("Таблица ec9oj_content не найдена в JSON файле!")
        return
    
    print(f"Найдено записей в таблице ec9oj_content: {len(content_table_data)}")
    
    if fields_values_data:
        print(f"Найдено записей в таблице ec9oj_fields_values: {len(fields_values_data)}")
    else:
        print("Таблица ec9oj_fields_values не найдена!")
    
    # Анализируем данные из основной таблицы
    print("Анализ записей на предмет изображений недвижимости...")
    results = analyze_content_table(content_table_data)
    
    # Если есть дополнительные поля, анализируем и их
    if fields_values_data:
        print("Анализ дополнительных полей...")
        results = analyze_fields_values(fields_values_data, results)
    
    # Выводим результаты
    print(f"\nНайдено записей с изображениями недвижимости: {results['total_found']}")
    print("="*80)
    
    for i, record in enumerate(results['records'], 1):
        print(f"\n{i}. ID: {record['id']}")
        print(f"   Название: {record['title']}")
        print(f"   Алиас: {record['alias']}")
        print(f"   Категория: {record['catid']}")
        print(f"   Создано: {record['created']}")
        print(f"   Изменено: {record['modified']}")
        print(f"   Статус: {record['state']}")
        print(f"   Изображения недвижимости ({len(record['image_paths'])}):")
        
        for img_path in record['image_paths']:
            print(f"     - {img_path}")
        
        if len(record['all_image_paths']) > len(record['image_paths']):
            print(f"   Другие изображения ({len(record['all_image_paths']) - len(record['image_paths'])}):")
            other_images = [img for img in record['all_image_paths'] if img not in record['image_paths']]
            for img_path in other_images[:5]:  # Показываем только первые 5
                print(f"     - {img_path}")
            if len(other_images) > 5:
                print(f"     ... и еще {len(other_images) - 5} изображений")
    
    # Сохраняем результаты в JSON файл
    output_file = Path('real_estate_images_analysis.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nРезультаты сохранены в файл: {output_file}")
    
    # Статистика по папкам
    print("\nСтатистика по папкам проектов:")
    folder_stats = {}
    for record in results['records']:
        for img_path in record['image_paths']:
            folder = img_path.split('/')[1] if '/' in img_path else 'unknown'
            if folder not in folder_stats:
                folder_stats[folder] = {'count': 0, 'records': []}
            folder_stats[folder]['count'] += 1
            if record['id'] not in folder_stats[folder]['records']:
                folder_stats[folder]['records'].append(record['id'])
    
    for folder, stats in sorted(folder_stats.items()):
        print(f"  {folder}: {stats['count']} изображений в {len(stats['records'])} записях")

if __name__ == "__main__":
    main()