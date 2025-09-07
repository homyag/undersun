from django import forms
from django.core.files.storage import default_storage
from django.urls import reverse
from django.utils.safestring import mark_safe
import json


class MultipleImageWidget(forms.ClearableFileInput):
    """
    Виджет для загрузки нескольких изображений одновременно
    """
    template_name = 'admin/widgets/multiple_image_widget.html'
    
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs.update({
            'multiple': True,
            'accept': 'image/*',
            'class': 'multiple-image-input'
        })
        super().__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        # Базовый input для множественного выбора файлов
        html = super().render(name, value, attrs, renderer)
        
        # Добавляем область для предварительного просмотра
        preview_html = '''
        <div class="multiple-image-preview" id="preview-{}">
            <div class="image-preview-container">
                <!-- Здесь будут отображаться выбранные изображения -->
            </div>
            <div class="upload-info">
                <p>Выберите несколько изображений для загрузки</p>
                <p><small>Поддерживаемые форматы: JPG, PNG, GIF. Максимальный размер: 10MB на файл</small></p>
            </div>
        </div>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const input = document.querySelector('input[name="{}"]');
                const preview = document.getElementById('preview-{}');
                const container = preview.querySelector('.image-preview-container');
                
                if (input) {{
                    input.addEventListener('change', function(e) {{
                        container.innerHTML = '';
                        const files = Array.from(e.target.files);
                        
                        files.forEach((file, index) => {{
                            if (file.type.startsWith('image/')) {{
                                const reader = new FileReader();
                                reader.onload = function(e) {{
                                    const imageDiv = document.createElement('div');
                                    imageDiv.className = 'image-preview-item';
                                    imageDiv.innerHTML = `
                                        <img src="${{e.target.result}}" alt="Preview ${{index + 1}}" style="width: 150px; height: 100px; object-fit: cover; margin: 5px; border: 1px solid #ddd;">
                                        <div class="image-info">
                                            <p><strong>${{file.name}}</strong></p>
                                            <p>Размер: ${{(file.size / 1024 / 1024).toFixed(2)}} MB</p>
                                        </div>
                                    `;
                                    container.appendChild(imageDiv);
                                }};
                                reader.readAsDataURL(file);
                            }}
                        }});
                        
                        if (files.length > 0) {{
                            preview.querySelector('.upload-info p').textContent = `Выбрано файлов: ${{files.length}}`;
                        }}
                    }});
                }}
            }});
        </script>
        <style>
            .multiple-image-preview {{
                margin-top: 10px;
                padding: 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f9f9f9;
            }}
            .image-preview-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 10px;
            }}
            .image-preview-item {{
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
            }}
            .image-info {{
                font-size: 12px;
                color: #666;
                margin-top: 5px;
            }}
            .image-info p {{
                margin: 2px 0;
            }}
            .upload-info {{
                text-align: center;
                color: #666;
            }}
            .upload-info p {{
                margin: 5px 0;
            }}
        </style>
        '''.format(name, name, name)
        
        return mark_safe(html + preview_html)


class BulkImageUploadWidget(forms.Widget):
    """
    Специальный виджет для массовой загрузки изображений для PropertyAdmin
    """
    template_name = 'admin/widgets/bulk_image_upload.html'
    
    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        
        attrs.update({
            'id': f'bulk-upload-{name}',
            'class': 'bulk-image-upload'
        })
        
        html = f'''
        <div class="bulk-image-upload-container">
            <div class="upload-area" id="upload-area-{name}">
                <input type="file" 
                       name="bulk_images" 
                       id="bulk-images-{name}"
                       multiple 
                       accept="image/*"
                       style="display: none;">
                <div class="upload-prompt" onclick="document.getElementById('bulk-images-{name}').click();">
                    <div class="upload-icon">📸</div>
                    <h3>Загрузить несколько изображений</h3>
                    <p>Нажмите здесь или перетащите файлы</p>
                    <p><small>Поддерживаемые форматы: JPG, PNG, GIF</small></p>
                </div>
                <div class="selected-images" id="selected-images-{name}"></div>
            </div>
            <div class="upload-actions">
                <button type="button" class="btn btn-primary" onclick="uploadBulkImages('{name}')">
                    Загрузить выбранные изображения
                </button>
                <button type="button" class="btn btn-secondary" onclick="clearSelection('{name}')">
                    Очистить выбор
                </button>
            </div>
        </div>
        
        <script>
            let selectedFiles_{name} = [];
            
            // Drag & Drop функциональность
            const uploadArea_{name} = document.getElementById('upload-area-{name}');
            
            uploadArea_{name}.addEventListener('dragover', function(e) {{
                e.preventDefault();
                this.classList.add('drag-over');
            }});
            
            uploadArea_{name}.addEventListener('dragleave', function(e) {{
                e.preventDefault();
                this.classList.remove('drag-over');
            }});
            
            uploadArea_{name}.addEventListener('drop', function(e) {{
                e.preventDefault();
                this.classList.remove('drag-over');
                const files = Array.from(e.dataTransfer.files).filter(file => file.type.startsWith('image/'));
                handleFileSelection_{name}(files);
            }});
            
            // Обработка выбора файлов
            document.getElementById('bulk-images-{name}').addEventListener('change', function(e) {{
                const files = Array.from(e.target.files);
                handleFileSelection_{name}(files);
            }});
            
            function handleFileSelection_{name}(files) {{
                selectedFiles_{name} = files;
                displaySelectedImages_{name}();
            }}
            
            function displaySelectedImages_{name}() {{
                const container = document.getElementById('selected-images-{name}');
                container.innerHTML = '';
                
                if (selectedFiles_{name}.length > 0) {{
                    const header = document.createElement('h4');
                    header.textContent = `Выбрано изображений: ${{selectedFiles_{name}.length}}`;
                    container.appendChild(header);
                    
                    const imageGrid = document.createElement('div');
                    imageGrid.className = 'image-grid';
                    
                    selectedFiles_{name}.forEach((file, index) => {{
                        const reader = new FileReader();
                        reader.onload = function(e) {{
                            const imageItem = document.createElement('div');
                            imageItem.className = 'image-item';
                            imageItem.innerHTML = `
                                <img src="${{e.target.result}}" alt="${{file.name}}">
                                <div class="image-details">
                                    <p><strong>${{file.name}}</strong></p>
                                    <p>${{(file.size / 1024 / 1024).toFixed(2)}} MB</p>
                                    <button type="button" onclick="removeImage_{name}(${{index}})" class="remove-btn">✕</button>
                                </div>
                            `;
                            imageGrid.appendChild(imageItem);
                        }};
                        reader.readAsDataURL(file);
                    }});
                    
                    container.appendChild(imageGrid);
                }}
            }}
            
            function removeImage_{name}(index) {{
                selectedFiles_{name}.splice(index, 1);
                displaySelectedImages_{name}();
            }}
            
            function clearSelection_{name}() {{
                selectedFiles_{name} = [];
                document.getElementById('bulk-images-{name}').value = '';
                displaySelectedImages_{name}();
            }}
            
            function uploadBulkImages(widgetName) {{
                if (selectedFiles_{name}.length === 0) {{
                    alert('Пожалуйста, выберите изображения для загрузки');
                    return;
                }}
                
                // Здесь будет AJAX запрос для загрузки изображений
                // Пока что показываем уведомление
                alert(`Будет загружено ${{selectedFiles_{name}.length}} изображений. Эта функция будет реализована в следующем шаге.`);
            }}
        </script>
        
        <style>
            .bulk-image-upload-container {{
                border: 2px dashed #ccc;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                background: #fafafa;
            }}
            
            .upload-area {{
                min-height: 200px;
                position: relative;
            }}
            
            .upload-area.drag-over {{
                border-color: #007cba;
                background-color: #f0f8ff;
            }}
            
            .upload-prompt {{
                text-align: center;
                cursor: pointer;
                padding: 40px;
            }}
            
            .upload-icon {{
                font-size: 48px;
                margin-bottom: 10px;
            }}
            
            .selected-images {{
                margin-top: 20px;
            }}
            
            .image-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}
            
            .image-item {{
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                background: white;
                position: relative;
            }}
            
            .image-item img {{
                width: 100%;
                height: 120px;
                object-fit: cover;
                border-radius: 4px;
            }}
            
            .image-details {{
                padding: 8px 0;
                font-size: 12px;
            }}
            
            .image-details p {{
                margin: 2px 0;
            }}
            
            .remove-btn {{
                position: absolute;
                top: 5px;
                right: 5px;
                background: rgba(255, 0, 0, 0.8);
                color: white;
                border: none;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                cursor: pointer;
                font-size: 12px;
            }}
            
            .upload-actions {{
                margin-top: 20px;
                text-align: center;
            }}
            
            .upload-actions button {{
                margin: 0 10px;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }}
            
            .btn-primary {{
                background: #007cba;
                color: white;
            }}
            
            .btn-secondary {{
                background: #666;
                color: white;
            }}
        </style>
        '''
        
        return mark_safe(html)