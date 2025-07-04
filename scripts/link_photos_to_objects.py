#!/usr/bin/env python3
"""
Скрипт для привязки фотографий к объектам недвижимости
на основе данных из joomla_base.json
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class PhotoLinker:
    def __init__(self, json_file: str, photos_dir: str):
        self.json_file = json_file
        self.photos_dir = Path(photos_dir)
        self.content_data = []
        self.photo_mapping = {}
        
    def load_json_data(self) -> None:
        """Загрузить данные из JSON файла"""
        print("Загрузка данных из JSON файла...")
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Найти таблицу с контентом
            for item in data:
                if isinstance(item, dict) and item.get('type') == 'table' and item.get('name') == 'ec9oj_content':
                    self.content_data = item.get('data', [])
                    break
                    
            print(f"Найдено {len(self.content_data)} записей контента")
            
        except Exception as e:
            print(f"Ошибка при загрузке JSON: {e}")
            
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
                for photo_file in item.rglob('*.jpg'):
                    if photo_file.is_file():
                        photos.append(str(photo_file.relative_to(self.photos_dir)))
                        
                for photo_file in item.rglob('*.jpeg'):
                    if photo_file.is_file():
                        photos.append(str(photo_file.relative_to(self.photos_dir)))
                        
                for photo_file in item.rglob('*.png'):
                    if photo_file.is_file():
                        photos.append(str(photo_file.relative_to(self.photos_dir)))
                        
                if photos:
                    photo_map[project_name] = photos
                    
        print(f"Найдено {len(photo_map)} проектов с фотографиями")
        return photo_map
        
    def normalize_name(self, name: str) -> str:
        """Нормализовать название для сравнения"""
        # Удалить специальные символы, привести к нижнему регистру
        normalized = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
        
    def find_matching_project(self, title: str, intro_text: str, images_field: str) -> Optional[str]:
        """Найти подходящий проект по названию статьи"""
        title_normalized = self.normalize_name(title)
        
        # Список проектов для поиска
        project_names = list(self.photo_mapping.keys())
        
        # Точное совпадение
        for project in project_names:
            project_normalized = self.normalize_name(project)
            if project_normalized == title_normalized:
                return project
                
        # Поиск по ключевым словам
        for project in project_names:
            project_normalized = self.normalize_name(project)
            if project_normalized in title_normalized or title_normalized in project_normalized:
                return project
                
        # Поиск по именам в тексте
        for project in project_names:
            project_words = self.normalize_name(project).split()
            if any(word in title_normalized for word in project_words if len(word) > 3):
                return project
                
        # Поиск по информации в поле images
        if images_field:
            try:
                images_data = json.loads(images_field)
                if images_data.get('image_intro'):
                    image_path = images_data['image_intro']
                    for project in project_names:
                        if project.lower() in image_path.lower():
                            return project
            except:
                pass
                
        return None
        
    def link_photos_to_objects(self) -> List[Dict]:
        """Связать фотографии с объектами недвижимости"""
        print("Привязка фотографий к объектам...")
        
        self.photo_mapping = self.scan_photos()
        results = []
        
        for item in self.content_data:
            if not isinstance(item, dict):
                continue
                
            title = item.get('title', '')
            intro_text = item.get('introtext', '')
            images_field = item.get('images', '')
            article_id = item.get('id', '')
            
            # Найти соответствующий проект
            matching_project = self.find_matching_project(title, intro_text, images_field)
            
            if matching_project:
                photos = self.photo_mapping[matching_project]
                result = {
                    'article_id': article_id,
                    'title': title,
                    'project': matching_project,
                    'photos': photos,
                    'photo_count': len(photos)
                }
                results.append(result)
                print(f"✓ {title} -> {matching_project} ({len(photos)} фото)")
            else:
                # Попробовать найти по существующему пути изображения
                if images_field:
                    try:
                        images_data = json.loads(images_field)
                        if images_data.get('image_intro'):
                            print(f"? {title} - существующее изображение: {images_data['image_intro']}")
                    except:
                        pass
                        
        return results
        
    def generate_report(self, results: List[Dict]) -> None:
        """Создать отчет о привязке фотографий"""
        print("\n" + "="*50)
        print("ОТЧЕТ О ПРИВЯЗКЕ ФОТОГРАФИЙ")
        print("="*50)
        
        print(f"Всего объектов с привязанными фотографиями: {len(results)}")
        
        total_photos = sum(r['photo_count'] for r in results)
        print(f"Общее количество привязанных фотографий: {total_photos}")
        
        print("\nДетальный список:")
        for result in results:
            print(f"\n{result['title']}")
            print(f"  ID: {result['article_id']}")
            print(f"  Проект: {result['project']}")
            print(f"  Фотографий: {result['photo_count']}")
            if result['photo_count'] <= 5:
                for photo in result['photos']:
                    print(f"    - {photo}")
            else:
                for photo in result['photos'][:3]:
                    print(f"    - {photo}")
                print(f"    ... и еще {result['photo_count'] - 3} фото")
                
        # Неопознанные проекты
        linked_projects = {r['project'] for r in results}
        unlinked_projects = set(self.photo_mapping.keys()) - linked_projects
        
        if unlinked_projects:
            print(f"\nПроекты без привязки к объектам ({len(unlinked_projects)}):")
            for project in sorted(unlinked_projects):
                print(f"  - {project} ({len(self.photo_mapping[project])} фото)")
                
    def save_mapping_to_file(self, results: List[Dict], filename: str = 'photo_mapping.json') -> None:
        """Сохранить результаты в файл"""
        print(f"\nСохранение результатов в {filename}...")
        
        output_data = {
            'total_objects': len(results),
            'total_photos': sum(r['photo_count'] for r in results),
            'mappings': results,
            'available_projects': list(self.photo_mapping.keys())
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        print(f"Результаты сохранены в {filename}")
        
    def run(self) -> None:
        """Запустить весь процесс привязки фотографий"""
        print("Начинаем привязку фотографий к объектам недвижимости...")
        
        # Загрузить данные из JSON
        self.load_json_data()
        
        if not self.content_data:
            print("Не найдены данные контента в JSON файле")
            return
            
        # Привязать фотографии к объектам
        results = self.link_photos_to_objects()
        
        # Создать отчет
        self.generate_report(results)
        
        # Сохранить результаты
        self.save_mapping_to_file(results)
        
        print("\nПроцесс завершен!")


def main():
    """Основная функция"""
    json_file = 'joomla_base.json'
    photos_dir = 'media/images_from_joomla/images'
    
    if not os.path.exists(json_file):
        print(f"Файл {json_file} не найден")
        return
        
    if not os.path.exists(photos_dir):
        print(f"Папка {photos_dir} не найдена")
        return
        
    linker = PhotoLinker(json_file, photos_dir)
    linker.run()


if __name__ == '__main__':
    main()