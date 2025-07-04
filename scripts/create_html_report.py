#!/usr/bin/env python3
"""
Создание HTML отчета по анализу изображений недвижимости
"""

import json
from pathlib import Path
from urllib.parse import unquote

def create_html_report():
    """Создает HTML отчет на основе результатов анализа"""
    
    # Загружаем результаты анализа
    results_file = Path('real_estate_images_analysis.json')
    if not results_file.exists():
        print("Файл результатов анализа не найден!")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Создаем HTML
    html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Анализ изображений недвижимости - Joomla База Данных</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            line-height: 1.6;
        }}
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .stats {
            display: flex;
            justify-content: space-around;
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        .stat-item {
            text-align: center;
        }
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            color: #6c757d;
            font-size: 0.9em;
        }
        .content {
            padding: 30px;
        }
        .record {
            margin-bottom: 40px;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            overflow: hidden;
        }
        .record-header {
            background: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
        }
        .record-id {
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            display: inline-block;
            margin-bottom: 10px;
        }
        .record-title {
            font-size: 1.4em;
            font-weight: bold;
            color: #343a40;
            margin: 10px 0;
        }
        .record-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 15px 0;
            font-size: 0.9em;
            color: #6c757d;
        }
        .record-body {
            padding: 20px;
        }
        .images-section {
            margin-bottom: 20px;
        }
        .images-title {
            font-weight: bold;
            color: #495057;
            margin-bottom: 10px;
            padding-bottom: 5px;
            border-bottom: 2px solid #667eea;
            display: inline-block;
        }
        .images-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 10px;
            margin: 15px 0;
        }
        .image-item {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            word-break: break-all;
            border-left: 3px solid #667eea;
        }
        .folder-stats {
            background: #f8f9fa;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
        }
        .folder-stats h3 {
            margin-top: 0;
            color: #343a40;
        }
        .folder-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }
        .folder-name {
            font-weight: bold;
            color: #495057;
        }
        .folder-count {
            color: #667eea;
            font-weight: bold;
        }
        .state-active { color: #28a745; }
        .state-inactive { color: #dc3545; }
        .state-unknown { color: #ffc107; }
        .no-images {
            color: #6c757d;
            font-style: italic;
        }
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
        
        <div class="content">
"""
    
    # Подсчитываем статистику
    total_records = data['total_found']
    total_images = sum(len(record['image_paths']) for record in data['records'])
    total_folders = len(set(
        img.split('/')[1] for record in data['records'] 
        for img in record['image_paths'] if '/' in img
    ))
    
    # Заменяем плейсхолдеры
    html_content = html_content.format(
        total_records=total_records,
        total_images=total_images,
        total_folders=total_folders
    )
    
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
    folder_stats = {}
    for record in data['records']:
        for img_path in record['image_paths']:
            folder = img_path.split('/')[1] if '/' in img_path else 'unknown'
            if folder not in folder_stats:
                folder_stats[folder] = {'count': 0, 'records': set()}
            folder_stats[folder]['count'] += 1
            folder_stats[folder]['records'].add(record['id'])
    
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