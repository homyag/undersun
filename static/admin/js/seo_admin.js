document.addEventListener('DOMContentLoaded', function() {
    // Character count for SEO fields
    const seoFields = [
        {selector: 'input[name*="title"]', maxLength: 60, warning: 50},
        {selector: 'textarea[name*="description"]', maxLength: 160, warning: 140},
    ];
    
    seoFields.forEach(function(field) {
        const elements = document.querySelectorAll(field.selector);
        elements.forEach(function(element) {
            addCharacterCounter(element, field.maxLength, field.warning);
        });
    });
    
    function addCharacterCounter(element, maxLength, warningLength) {
        const container = element.closest('.form-row');
        const counter = document.createElement('div');
        counter.className = 'character-counter';
        counter.style.cssText = 'font-size: 11px; color: #666; margin-top: 5px;';
        
        function updateCounter() {
            const length = element.value.length;
            const remaining = maxLength - length;
            
            if (length > maxLength) {
                counter.style.color = '#d63638';
                counter.innerHTML = `<strong>Превышен лимит на ${length - maxLength} символов!</strong>`;
            } else if (length > warningLength) {
                counter.style.color = '#dba617';
                counter.innerHTML = `Осталось ${remaining} символов (рекомендуется не более ${maxLength})`;
            } else {
                counter.style.color = '#00a32a';
                counter.innerHTML = `${length} символов (рекомендуется не более ${maxLength})`;
            }
        }
        
        element.addEventListener('input', updateCounter);
        container.appendChild(counter);
        updateCounter();
    }
    
    // Add helpful tooltips
    const tooltips = {
        'title': 'Заголовок страницы (рекомендуется 50-60 символов)',
        'description': 'Описание страницы для поисковых систем (рекомендуется 140-160 символов)',
        'keywords': 'Ключевые слова через запятую (необязательно, многие поисковики игнорируют)'
    };
    
    Object.keys(tooltips).forEach(function(field) {
        const elements = document.querySelectorAll(`[name*="${field}"]`);
        elements.forEach(function(element) {
            element.title = tooltips[field];
        });
    });
});