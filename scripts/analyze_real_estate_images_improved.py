#!/usr/bin/env python3
"""
Улучшенный анализ изображений недвижимости из базы данных Joomla
Теперь учитывает изображения как в ec9oj_content, так и в ec9oj_fields_values
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
        if normalized_path not in normalized_paths:
            normalized_paths.append(normalized_path)
    
    normalized_paths.sort()
    return normalized_paths

def analyze_content_table(data: List[Dict]) -> Dict:
    """Анализирует таблицу ec9oj_content на предмет изображений недвижимости"""
    
    # Папки проектов недвижимости (расширенный список)
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
        'Villas_Samui', 'Waterfront_Surin', 'Zire_Wongamat',
        # Добавляем новые папки на основе анализа
        'VS161_Villoft', 'Villoft_Zen_Living', 'Layan_Green_Park', 'Momentum'
    ]
    
    # Также ищем папки по паттерну (код проекта)
    project_code_patterns = [
        r'VS\d+_', r'VN\d+_', r'CN\d+_', r'PH\d+_', r'TH\d+_'
    ]
    
    results = []
    processed_count = 0
    
    for item in data:
        try:
            processed_count += 1
            if processed_count % 100 == 0:
                print(f"Обработано записей content: {processed_count}")
            
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
                # Проверяем по известным папкам
                is_property_image = False
                for folder in property_folders:
                    if folder in path:
                        property_images.append(path)
                        is_property_image = True
                        break
                
                # Если не найдено, проверяем по паттернам кодов проектов
                if not is_property_image:
                    for pattern in project_code_patterns:
                        if re.search(pattern, path):
                            property_images.append(path)
                            break
            
            # Если найдены изображения недвижимости, добавляем в результат
            if property_images:
                result_item = {
                    'id': item.get('id', ''),
                    'title': item.get('title', ''),
                    'alias': item.get('alias', ''),
                    'note': item.get('note', ''),  # Добавляем поле note (код проекта)
                    'image_paths': property_images,
                    'all_image_paths': image_paths,  # Все найденные изображения
                    'created': item.get('created', ''),
                    'modified': item.get('modified', ''),
                    'state': item.get('state', ''),
                    'catid': item.get('catid', ''),
                    'source': 'content'  # Источник данных
                }
                results.append(result_item)
        
        except Exception as e:
            print(f"Ошибка при обработке записи content: {e}")
            continue
    
    return results

def analyze_fields_values(data: List[Dict], content_records: List[Dict]) -> List[Dict]:
    """Анализирует таблицу ec9oj_fields_values для дополнительных изображений"""
    
    # Создаем словарь для быстрого поиска content записей
    content_dict = {record['id']: record for record in content_records}
    
    # Папки проектов недвижимости (тот же список)
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
        'Villas_Samui', 'Waterfront_Surin', 'Zire_Wongamat',
        'VS161_Villoft', 'Villoft_Zen_Living', 'Layan_Green_Park', 'Momentum'
    ]
    
    project_code_patterns = [
        r'VS\d+_', r'VN\d+_', r'CN\d+_', r'PH\d+_', r'TH\d+_'
    ]
    
    # Группируем поля по item_id
    fields_by_item = {}
    processed_count = 0
    
    for item in data:
        try:
            processed_count += 1
            if processed_count % 1000 == 0:
                print(f"Обработано записей fields_values: {processed_count}")
            
            if isinstance(item, dict) and 'item_id' in item and 'field_id' in item and 'value' in item:
                item_id = item['item_id']
                field_id = item['field_id']
                value = item['value']
                
                # Интересуют только поля с изображениями (обычно field_id = 3)
                if field_id == '3' and value:
                    if item_id not in fields_by_item:
                        fields_by_item[item_id] = []
                    fields_by_item[item_id].append(value)
                    
        except Exception as e:
            print(f"Ошибка при обработке записи fields_values: {e}")
            continue
    
    # Обрабатываем найденные поля
    updated_records = content_records.copy()
    
    for item_id, field_values in fields_by_item.items():
        try:
            # Объединяем все значения полей для этого item_id
            combined_value = ' '.join(field_values)
            
            # Ищем изображения в значениях полей
            image_paths = extract_image_paths(combined_value)
            
            if not image_paths:
                continue
            
            # Фильтруем только изображения недвижимости
            property_images = []
            for img in image_paths:
                # Проверяем по известным папкам
                is_property_image = False
                for folder in property_folders:
                    if folder in img:
                        property_images.append(img)
                        is_property_image = True
                        break
                
                # Если не найдено, проверяем по паттернам кодов проектов
                if not is_property_image:
                    for pattern in project_code_patterns:
                        if re.search(pattern, img):
                            property_images.append(img)
                            break
            
            if not property_images:
                continue
                
            # Ищем соответствующую запись в content
            content_record = content_dict.get(item_id)
            
            if content_record:
                # Обновляем существующую запись
                for i, record in enumerate(updated_records):
                    if record['id'] == item_id:
                        # Объединяем изображения
                        all_property_images = list(set(record['image_paths'] + property_images))
                        all_images = list(set(record['all_image_paths'] + image_paths))
                        
                        updated_records[i]['image_paths'] = sorted(all_property_images)
                        updated_records[i]['all_image_paths'] = sorted(all_images)
                        updated_records[i]['source'] = 'content+fields'
                        break
            else:
                # Создаем новую запись (только из fields_values)
                new_record = {
                    'id': item_id,
                    'title': f'Запись только в fields_values (ID: {item_id})',
                    'alias': f'fields-only-{item_id}',
                    'note': '',
                    'image_paths': sorted(property_images),
                    'all_image_paths': sorted(image_paths),
                    'created': '',
                    'modified': '',
                    'state': 'unknown',
                    'catid': 'unknown',
                    'source': 'fields_only'
                }
                updated_records.append(new_record)
                
        except Exception as e:
            print(f"Ошибка при обработке item_id {item_id}: {e}")
            continue
    
    return updated_records

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
    print("\nАнализ записей content на предмет изображений недвижимости...")
    content_results = analyze_content_table(content_table_data)
    
    # Если есть дополнительные поля, анализируем и их
    if fields_values_data:
        print("\nАнализ дополнительных полей fields_values...")
        final_results = analyze_fields_values(fields_values_data, content_results)
    else:
        final_results = content_results
    
    # Выводим результаты
    print(f"\nВсего найдено записей с изображениями недвижимости: {len(final_results)}")
    
    # Группируем по источникам
    content_only = [r for r in final_results if r['source'] == 'content']
    fields_only = [r for r in final_results if r['source'] == 'fields_only']
    both_sources = [r for r in final_results if r['source'] == 'content+fields']
    
    print(f"  - Только в content: {len(content_only)}")
    print(f"  - Только в fields_values: {len(fields_only)}")
    print(f"  - В обеих таблицах: {len(both_sources)}")
    
    print("="*80)
    
    # Выводим детальную информацию
    for i, record in enumerate(final_results[:20], 1):  # Показываем первые 20
        print(f"\n{i}. ID: {record['id']} | Источник: {record['source']}")
        print(f"   Код проекта: {record['note']}")
        print(f"   Название: {record['title'][:60]}...")
        print(f"   Алиас: {record['alias'][:60]}...")
        print(f"   Категория: {record['catid']}")
        print(f"   Создано: {record['created']}")
        print(f"   Изменено: {record['modified']}")
        print(f"   Статус: {record['state']}")
        print(f"   Изображения недвижимости ({len(record['image_paths'])}):")
        
        for img_path in record['image_paths'][:5]:  # Показываем первые 5
            print(f"     - {img_path}")
        
        if len(record['image_paths']) > 5:
            print(f"     ... и еще {len(record['image_paths']) - 5} изображений")
    
    if len(final_results) > 20:
        print(f"\n... и еще {len(final_results) - 20} записей")
    
    # Сохраняем результаты в JSON файл
    output_file = Path('real_estate_images_analysis_improved.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_found': len(final_results),
            'content_only': len(content_only),
            'fields_only': len(fields_only),
            'both_sources': len(both_sources),
            'records': final_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nРезультаты сохранены в файл: {output_file}")
    
    # Статистика по папкам
    print("\nСтатистика по папкам проектов:")
    folder_stats = {}
    for record in final_results:
        for img_path in record['image_paths']:
            folder = img_path.split('/')[1] if '/' in img_path else 'unknown'
            if folder not in folder_stats:
                folder_stats[folder] = {'count': 0, 'records': set()}
            folder_stats[folder]['count'] += 1
            folder_stats[folder]['records'].add(record['id'])
    
    # Сортируем по количеству изображений
    sorted_folders = sorted(folder_stats.items(), key=lambda x: x[1]['count'], reverse=True)
    
    for folder, stats in sorted_folders[:20]:  # Топ-20
        print(f"  {folder}: {stats['count']} изображений в {len(stats['records'])} записях")

if __name__ == "__main__":
    main()