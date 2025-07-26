#!/usr/bin/env python3
"""
Улучшенный скрипт для привязки фотографий к объектам недвижимости
Использует результаты улучшенного анализа изображений
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class ImprovedPhotoLinker:
    def __init__(self, analysis_file: str, photos_dir: str):
        self.analysis_file = analysis_file
        self.photos_dir = Path(photos_dir)
        self.analysis_data = {}
        self.photo_mapping = {}
        
    def load_analysis_data(self) -> None:
        """Загрузить данные из файла анализа"""
        print("Загрузка данных из файла анализа...")
        try:
            with open(self.analysis_file, 'r', encoding='utf-8') as f:
                self.analysis_data = json.load(f)
            
            print(f"Найдено {self.analysis_data['total_found']} записей с изображениями:")
            print(f"  - Только в content: {self.analysis_data['content_only']}")
            print(f"  - Только в fields_values: {self.analysis_data['fields_only']}")
            print(f"  - В обеих таблицах: {self.analysis_data['both_sources']}")
                    
        except Exception as e:
            print(f"Ошибка при загрузке файла анализа: {e}")
            
    def scan_photos(self) -> Dict[str, List[str]]:
        """Сканировать папку с фотографиями и создать карту проектов"""
        print("Сканирование папки с фотографиями...")
        
        photo_map = {}
        
        if not self.photos_dir.exists():
            print(f"Папка {self.photos_dir} не найдена")
            return photo_map
            
        # Сканировать все подпапки
        for item in self.photos_dir.iterdir():
            if item.is_dir():
                project_name = item.name
                photos = []
                
                # Рекурсивно найти все фотографии в проекте
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                    for photo_file in item.rglob(ext):
                        if photo_file.is_file():
                            photos.append(str(photo_file.relative_to(self.photos_dir)))
                
                if photos:
                    photo_map[project_name] = sorted(photos)
                    
        print(f"Найдено {len(photo_map)} проектов с фотографиями")
        return photo_map
        
    def extract_project_folder_from_path(self, image_path: str) -> Optional[str]:
        """Извлечь название папки проекта из пути к изображению"""
        if not image_path.startswith('images/'):
            return None
        
        # Убираем 'images/' и берем первую часть пути
        path_parts = image_path.replace('images/', '').split('/')
        if len(path_parts) >= 1:
            return path_parts[0]
        
        return None
    
    def find_matching_photos_from_analysis(self, record: Dict) -> List[str]:
        """Найти фотографии для записи на основе данных анализа"""
        photos = []
        
        # Собираем все пути изображений из записи анализа
        image_paths = record.get('image_paths', [])
        
        for image_path in image_paths:
            # Извлекаем папку проекта из пути
            project_folder = self.extract_project_folder_from_path(image_path)
            
            if project_folder and project_folder in self.photo_mapping:
                # Находим все фотографии в этой папке проекта
                project_photos = self.photo_mapping[project_folder]
                
                # Добавляем все фотографии из папки проекта
                for photo in project_photos:
                    if photo not in photos:
                        photos.append(photo)
        
        return sorted(photos)
    
    def normalize_name(self, name: str) -> str:
        """Нормализовать название для сравнения"""
        # Удалить специальные символы, привести к нижнему регистру
        normalized = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
        
    def link_photos_to_objects_from_analysis(self) -> List[Dict]:
        """Создать маппинг фотографий на основе данных анализа"""
        print("Создание маппинга фотографий на основе анализа...")
        
        self.photo_mapping = self.scan_photos()
        results = []
        
        records = self.analysis_data.get('records', [])
        
        for record in records:
            article_id = record.get('id', '')
            title = record.get('title', '')
            note = record.get('note', '')  # Код проекта
            source = record.get('source', '')
            
            # Находим фотографии для этой записи
            photos = self.find_matching_photos_from_analysis(record)
            
            if photos:
                result = {
                    'article_id': article_id,
                    'title': title,
                    'note': note,
                    'source': source,
                    'analysis_images': record.get('image_paths', []),
                    'photos': photos,
                    'photo_count': len(photos)
                }
                results.append(result)
                
                source_marker = f"[{source}]"
                note_marker = f"({note})" if note else ""
                print(f"✓ {title[:50]}... {note_marker} {source_marker} -> {len(photos)} фото")
            else:
                # Если не нашли фотографии, все равно добавляем запись
                result = {
                    'article_id': article_id,
                    'title': title,
                    'note': note,
                    'source': source,
                    'analysis_images': record.get('image_paths', []),
                    'photos': [],
                    'photo_count': 0
                }
                results.append(result)
                
                source_marker = f"[{source}]"
                note_marker = f"({note})" if note else ""
                print(f"? {title[:50]}... {note_marker} {source_marker} -> нет физических файлов")
                
        return results
        
    def generate_report(self, results: List[Dict]) -> None:
        """Создать отчет о привязке фотографий"""
        print("\n" + "="*70)
        print("ОТЧЕТ О ПРИВЯЗКЕ ФОТОГРАФИЙ (УЛУЧШЕННАЯ ВЕРСИЯ)")
        print("="*70)
        
        print(f"Всего записей с изображениями из анализа: {len(results)}")
        
        # Статистика по источникам
        content_only = [r for r in results if r['source'] == 'content']
        fields_only = [r for r in results if r['source'] == 'fields_only']
        both_sources = [r for r in results if r['source'] == 'content+fields']
        
        print(f"  - Только в content: {len(content_only)}")
        print(f"  - Только в fields_values: {len(fields_only)}")
        print(f"  - В обеих таблицах: {len(both_sources)}")
        
        # Статистика по фотографиям
        records_with_photos = [r for r in results if r['photo_count'] > 0]
        total_photos = sum(r['photo_count'] for r in results)
        
        print(f"\nОбъектов с найденными фотографиями: {len(records_with_photos)}")
        print(f"Общее количество фотографий: {total_photos}")
        
        if records_with_photos:
            avg_photos = total_photos / len(records_with_photos)
            print(f"Среднее количество фото на объект: {avg_photos:.1f}")
        
        # Топ объектов по количеству фотографий
        print(f"\nТоп-10 объектов по количеству фотографий:")
        top_objects = sorted(records_with_photos, key=lambda x: x['photo_count'], reverse=True)[:10]
        
        for i, obj in enumerate(top_objects, 1):
            note_marker = f"({obj['note']})" if obj['note'] else ""
            source_marker = f"[{obj['source']}]"
            print(f"  {i:2d}. {obj['photo_count']:3d} фото - {obj['title'][:40]}... {note_marker} {source_marker}")
        
        # Статистика по кодам проектов
        print(f"\nСтатистика по кодам проектов:")
        project_codes = {}
        for result in results:
            note = result['note'] or 'БЕЗ_КОДА'
            if note not in project_codes:
                project_codes[note] = {'count': 0, 'photos': 0}
            project_codes[note]['count'] += 1
            project_codes[note]['photos'] += result['photo_count']
        
        sorted_codes = sorted(project_codes.items(), 
                            key=lambda x: x[1]['photos'], reverse=True)[:15]
        
        for code, stats in sorted_codes:
            print(f"  {code}: {stats['count']} объектов, {stats['photos']} фотографий")
                
    def save_mapping_to_file(self, results: List[Dict], filename: str = 'photo_mapping_improved.json') -> None:
        """Сохранить результаты в файл"""
        print(f"\nСохранение результатов в {filename}...")
        
        # Подготавливаем статистику
        records_with_photos = [r for r in results if r['photo_count'] > 0]
        total_photos = sum(r['photo_count'] for r in results)
        
        # Группируем по источникам
        content_only = [r for r in results if r['source'] == 'content']
        fields_only = [r for r in results if r['source'] == 'fields_only']
        both_sources = [r for r in results if r['source'] == 'content+fields']
        
        output_data = {
            'total_objects': len(results),
            'objects_with_photos': len(records_with_photos),
            'total_photos': total_photos,
            'statistics': {
                'content_only': len(content_only),
                'fields_only': len(fields_only),
                'both_sources': len(both_sources)
            },
            'mappings': results,
            'available_projects': list(self.photo_mapping.keys()) if self.photo_mapping else []
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        print(f"Результаты сохранены в {filename}")
        
    def run(self) -> None:
        """Запустить весь процесс привязки фотографий"""
        print("Начинаем улучшенную привязку фотографий к объектам недвижимости...")
        
        # Загружаем данные анализа
        self.load_analysis_data()
        
        if not self.analysis_data:
            print("Не найдены данные анализа")
            return
            
        # Создаем маппинг на основе анализа
        results = self.link_photos_to_objects_from_analysis()
        
        # Создаем отчет
        self.generate_report(results)
        
        # Сохраняем результаты
        self.save_mapping_to_file(results)
        
        print("\nУлучшенный процесс завершен!")


def main():
    """Основная функция"""
    analysis_file = 'real_estate_images_analysis_improved.json'
    photos_dir = 'media/images_from_joomla/images'
    
    if not os.path.exists(analysis_file):
        print(f"Файл анализа {analysis_file} не найден")
        print("Сначала запустите скрипт analyze_real_estate_images_improved.py")
        return
        
    if not os.path.exists(photos_dir):
        print(f"Папка {photos_dir} не найдена")
        return
        
    linker = ImprovedPhotoLinker(analysis_file, photos_dir)
    linker.run()


if __name__ == '__main__':
    main()