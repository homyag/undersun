#!/usr/bin/env python3
"""
Создание простого HTML отчета по анализу изображений недвижимости
"""

import json
from pathlib import Path

def create_html_report():
    """Создает HTML отчет на основе результатов анализа"""
    
    # Загружаем результаты анализа
    results_file = Path('real_estate_images_analysis.json')
    if not results_file.exists():
        print("Файл результатов анализа не найден!")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Подсчитываем статистику
    total_records = data['total_found']
    total_images = sum(len(record['image_paths']) for record in data['records'])
    folder_stats = {}
    for record in data['records']:
        for img_path in record['image_paths']:
            folder = img_path.split('/')[1] if '/' in img_path else 'unknown'
            if folder not in folder_stats:
                folder_stats[folder] = {'count': 0, 'records': set()}
            folder_stats[folder]['count'] += 1
            folder_stats[folder]['records'].add(record['id'])
    
    total_folders = len(folder_stats)
    
    # Создаем HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Анализ изображений недвижимости - Joomla База Данных</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; background: linear-gradient(45deg, #667eea, #764ba2); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
        .stats {{ display: flex; justify-content: space-around; background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .stat-item {{ text-align: center; }}
        .stat-number {{ font-size: 2em; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #666; }}
        .record {{ border: 1px solid #ddd; margin-bottom: 30px; border-radius: 8px; overflow: hidden; }}
        .record-header {{ background: #f8f9fa; padding: 20px; border-bottom: 1px solid #ddd; }}
        .record-id {{ background: #667eea; color: white; padding: 5px 15px; border-radius: 15px; font-size: 0.9em; display: inline-block; }}
        .record-title {{ font-size: 1.3em; font-weight: bold; margin: 10px 0; color: #333; }}
        .record-info {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin: 15px 0; font-size: 0.9em; color: #666; }}
        .record-body {{ padding: 20px; }}
        .images-section {{ margin-bottom: 20px; }}
        .images-title {{ font-weight: bold; color: #333; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 2px solid #667eea; display: inline-block; }}
        .images-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px; margin: 15px 0; }}
        .image-item {{ background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.85em; word-break: break-all; border-left: 3px solid #667eea; }}
        .folder-stats {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 30px 0; }}
        .folder-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ddd; }}
        .folder-name {{ font-weight: bold; }}
        .folder-count {{ color: #667eea; font-weight: bold; }}
        .state-active {{ color: #28a745; }}
        .state-inactive {{ color: #dc3545; }}
        .state-unknown {{ color: #ffc107; }}
        .no-images {{ color: #666; font-style: italic; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Анализ изображений недвижимости</h1>
            <p>Найденные записи из таблицы ec9oj_content с изображениями объектов недвижимости</p>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number">{total_records}</div>
                <div class="stat-label">Записей найдено</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{total_images}</div>
                <div class="stat-label">Изображений недвижимости</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{total_folders}</div>
                <div class="stat-label">Папок проектов</div>
            </div>
        </div>
"""
    
    # Добавляем записи
    for i, record in enumerate(data['records'], 1):
        # Определяем статус
        state = record.get('state', 'unknown')
        if state == '1':
            state_class = 'state-active'
            state_text = 'Активная'
        elif state == '0':
            state_class = 'state-inactive'
            state_text = 'Неактивная'
        else:
            state_class = 'state-unknown'
            state_text = 'Неизвестно'
        
        # Декодируем Unicode в путях изображений
        property_images = []
        for img_path in record['image_paths']:
            try:
                # Декодируем Unicode последовательности
                decoded_path = img_path.encode().decode('unicode_escape')
                property_images.append(decoded_path)
            except:
                property_images.append(img_path)
        
        other_images = []
        other_image_paths = [img for img in record['all_image_paths'] if img not in record['image_paths']]
        for img_path in other_image_paths[:10]:  # Показываем только первые 10
            try:
                decoded_path = img_path.encode().decode('unicode_escape')
                other_images.append(decoded_path)
            except:
                other_images.append(img_path)
        
        html_content += f"""
        <div class="record">
            <div class="record-header">
                <div class="record-id">ID: {record['id']}</div>
                <div class="record-title">{record['title']}</div>
                <div class="record-info">
                    <div><strong>Алиас:</strong> {record['alias']}</div>
                    <div><strong>Категория:</strong> {record['catid']}</div>
                    <div><strong>Статус:</strong> <span class="{state_class}">{state_text}</span></div>
                    <div><strong>Создано:</strong> {record['created']}</div>
                    <div><strong>Изменено:</strong> {record['modified']}</div>
                </div>
            </div>
            <div class="record-body">
                <div class="images-section">
                    <div class="images-title">🏠 Изображения недвижимости ({len(property_images)})</div>
                    <div class="images-grid">
        """
        
        if property_images:
            for img_path in property_images:
                html_content += f'<div class="image-item">{img_path}</div>'
        else:
            html_content += '<div class="no-images">Изображения недвижимости не найдены</div>'
        
        html_content += """
                    </div>
                </div>
        """
        
        if other_images:
            html_content += f"""
                <div class="images-section">
                    <div class="images-title">🔧 Другие изображения ({len(other_image_paths)})</div>
                    <div class="images-grid">
            """
            for img_path in other_images:
                html_content += f'<div class="image-item">{img_path}</div>'
            
            if len(other_image_paths) > 10:
                html_content += f'<div class="no-images">... и еще {len(other_image_paths) - 10} изображений</div>'
            
            html_content += """
                    </div>
                </div>
            """
        
        html_content += """
            </div>
        </div>
        """
    
    # Статистика по папкам
    html_content += """
        <div class="folder-stats">
            <h3>📂 Статистика по папкам проектов</h3>
    """
    
    for folder, stats in sorted(folder_stats.items()):
        html_content += f"""
            <div class="folder-item">
                <span class="folder-name">{folder}</span>
                <span class="folder-count">{stats['count']} изображений в {len(stats['records'])} записях</span>
            </div>
        """
    
    html_content += """
        </div>
    </div>
</body>
</html>
    """
    
    # Сохраняем HTML файл
    output_file = Path('real_estate_images_report.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML отчет создан: {output_file}")
    return output_file

if __name__ == "__main__":
    create_html_report()