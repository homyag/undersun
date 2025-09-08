/**
 * JavaScript для drag & drop сортировки изображений в админке Django
 * Использует библиотеку SortableJS
 */

document.addEventListener('DOMContentLoaded', function() {
    // Ожидаем полной загрузки страницы включая inline формы
    setTimeout(initImageSorting, 500);
});

function initImageSorting() {
    // Находим контейнер с изображениями PropertyImage
    const imageContainer = document.querySelector('.inline-group .tabular tbody');
    
    if (!imageContainer) {
        return;
    }
    
    // Получаем все строки с изображениями (исключаем пустые строки для новых записей)
    const imageRows = imageContainer.querySelectorAll('tr.form-row.has_original');
    
    if (imageRows.length === 0) {
        return;
    }
    
    // Инициализируем SortableJS
    const sortable = new Sortable(imageContainer, {
        // Настройки сортировки
        handle: '.drag-handle', // Перетаскивание только за ручку
        filter: 'tr:not(.has_original)', // Исключаем строки без изображений
        preventOnFilter: false,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen', 
        dragClass: 'sortable-drag',
        animation: 300,
        
        // Событие при начале перетаскивания
        onStart: function(evt) {
            evt.item.classList.add('dragging');
        },
        
        // Событие при завершении перетаскивания
        onEnd: function(evt) {
            evt.item.classList.remove('dragging');
            
            // Обновляем порядок только если позиция изменилась
            if (evt.oldIndex !== evt.newIndex) {
                updateImageOrder();
            }
        }
    });
}

function updateImageOrder() {
    // Получаем все строки с изображениями в новом порядке
    const imageRows = document.querySelectorAll('.inline-group .tabular tbody tr.form-row.has_original');
    const updateData = [];
    
    imageRows.forEach((row, index) => {
        // Находим поле order в строке
        const orderField = row.querySelector('input[name*="-order"]');
        const idField = row.querySelector('input[name*="-id"]');
        
        if (orderField && idField && idField.value) {
            // Обновляем значение в поле order (начинаем с 1)
            const newOrder = index + 1;
            orderField.value = newOrder;
            
            // Добавляем в массив для AJAX запроса
            updateData.push({
                id: idField.value,
                order: newOrder
            });
            
            // Визуальная обратная связь
            row.classList.add('order-updated');
            setTimeout(() => {
                row.classList.remove('order-updated');
            }, 2000);
        }
    });
    
    // Отправляем AJAX запрос для сохранения порядка
    if (updateData.length > 0) {
        saveImageOrder(updateData);
    }
}

function saveImageOrder(orderData) {
    // Показываем индикатор загрузки
    const container = document.querySelector('.inline-group');
    if (container) {
        container.classList.add('saving-order');
    }
    
    // Получаем CSRF токен
    const csrfTokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
    const csrfToken = csrfTokenElement ? csrfTokenElement.value : '';
    
    if (!csrfToken) {
        showNotification('❌ CSRF токен не найден', 'error');
        return;
    }
    
    // Отправляем AJAX запрос (используем admin-specific URL без i18n)
    fetch('/admin-ajax/update-image-order/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            images: orderData
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ Порядок изображений сохранен', 'success');
        } else {
            console.error('Failed to update image order:', data.message);
            showNotification('❌ Ошибка при сохранении порядка: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error updating image order:', error);
        showNotification('❌ Ошибка при сохранении порядка изображений', 'error');
    })
    .finally(() => {
        // Убираем индикатор загрузки
        if (container) {
            container.classList.remove('saving-order');
        }
    });
}

function showNotification(message, type) {
    // Создаем элемент уведомления
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 6px;
        color: white;
        font-weight: bold;
        z-index: 10000;
        max-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        opacity: 0;
        transform: translateY(-20px);
    `;
    
    // Стили в зависимости от типа
    if (type === 'success') {
        notification.style.background = '#28a745';
    } else if (type === 'error') {
        notification.style.background = '#dc3545';
    } else {
        notification.style.background = '#007cba';
    }
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // Анимация появления
    setTimeout(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateY(0)';
    }, 10);
    
    // Автоматическое скрытие
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-20px)';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Переинициализация при добавлении новых форм (Django admin inline)
document.addEventListener('formset:added', function() {
    setTimeout(initImageSorting, 100);
});

// Также переинициализируем при удалении форм
document.addEventListener('formset:removed', function() {
    setTimeout(initImageSorting, 100);
});