/**
 * JavaScript для автоматического определения обязательных полей 
 * и добавления визуальных индикаторов в Django админке
 */

document.addEventListener('DOMContentLoaded', function() {
    // Функция для проверки, является ли поле обязательным
    function isFieldRequired(input) {
        // Проверяем HTML атрибут required
        if (input.hasAttribute('required')) {
            return true;
        }
        
        // Проверяем, есть ли в классе CSS обозначение required
        if (input.classList.contains('required-field')) {
            return true;
        }
        
        // Найдем родительский .form-row элемент
        const formRow = input.closest('.form-row');
        if (!formRow) {
            return false; // Если нет родительского .form-row, пропускаем
        }
        
        // Для Django - проверяем наличие звездочки в label
        const label = formRow.querySelector('label');
        if (label && label.textContent.includes('*')) {
            return true;
        }
        
        // Для Django - проверяем наличие класса 'required' в контейнере
        if (formRow.classList.contains('required')) {
            return true;
        }
        
        return false;
    }
    
    // Функция для добавления индикатора обязательности
    function markRequiredField(formRow) {
        if (!formRow.classList.contains('required-marked')) {
            formRow.classList.add('required');
            formRow.classList.add('required-marked');
            
            // Найдем label и добавим звездочку, если её нет
            const label = formRow.querySelector('label');
            if (label && !label.textContent.includes('*')) {
                label.innerHTML = label.innerHTML + ' <span style="color: #dc2626; font-weight: bold;">*</span>';
            }
        }
    }
    
    // Основная функция для обработки всех полей формы
    function processRequiredFields() {
        // Получаем все поля ввода в форме
        const inputs = document.querySelectorAll('input, select, textarea');
        
        inputs.forEach(function(input) {
            // Пропускаем скрытые поля и кнопки
            if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') {
                return;
            }
            
            // Проверяем, является ли поле обязательным
            if (isFieldRequired(input)) {
                const formRow = input.closest('.form-row');
                if (formRow) {
                    markRequiredField(formRow);
                }
            }
        });
        
        // Обрабатываем специфические поля Django по их именам
        const specificRequiredFields = [
            // Property model обязательные поля
            'input[name="title"]',
            'input[name="slug"]', 
            'select[name="property_type"]',
            'select[name="district"]',
            'textarea[name="description"]',
            
            // PropertyType model обязательные поля
            'select[name="name"]',
            'input[name="name_display"]',
            
            // Developer model обязательные поля
            'input[name="name"][id*="developer"]',
            'input[name="slug"][id*="developer"]',
            
            // BlogPost model обязательные поля
            'input[name="title"][id*="blog"]',
            'input[name="slug"][id*="blog"]',
            'select[name="category"]',
            'select[name="author"]',
            'textarea[name="excerpt"]',
            'textarea[name="content"]',
            
            // BlogCategory model обязательные поля
            'input[name="name"][id*="category"]',
            'input[name="slug"][id*="category"]'
        ];
        
        specificRequiredFields.forEach(function(selector) {
            try {
                const field = document.querySelector(selector);
                if (field) {
                    const formRow = field.closest('.form-row');
                    if (formRow) {
                        markRequiredField(formRow);
                    }
                }
            } catch (error) {
                // Тихо игнорируем ошибки селекторов - поле может не существовать
            }
        });
    }
    
    // Обрабатываем поля при загрузке страницы
    processRequiredFields();
    
    // Наблюдаем за изменениями в DOM (для динамически добавляемых полей)
    const observer = new MutationObserver(function(mutations) {
        let shouldReprocess = false;
        
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length > 0) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1 && (node.tagName === 'INPUT' || node.tagName === 'SELECT' || node.tagName === 'TEXTAREA' || node.querySelector('input, select, textarea'))) {
                        shouldReprocess = true;
                    }
                });
            }
        });
        
        if (shouldReprocess) {
            setTimeout(processRequiredFields, 100); // Небольшая задержка для обеспечения полной загрузки элементов
        }
    });
    
    // Начинаем наблюдение за изменениями
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});