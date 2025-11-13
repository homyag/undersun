// Global functions for consultation form tabs
window.switchConsultationTab = function (consultationId, tabName) {
    // Update tab buttons
    document.querySelectorAll(`[data-consultation-id="${consultationId}"].consultation-tab`).forEach(tab => {
        tab.classList.remove('active');
        if (tab.getAttribute('data-tab') === tabName) {
            tab.classList.add('active');
        }
    });

    // Update tab content
    document.querySelectorAll(`[data-consultation-id="${consultationId}"].consultation-content`).forEach(content => {
        content.classList.add('hidden');
        content.classList.remove('active');
        if (content.getAttribute('data-tab') === tabName) {
            content.classList.remove('hidden');
            content.classList.add('active');
        }
    });
};

// Handle phone callback form submission
function showConsultationMessage(message, type = 'success') {
    if (typeof FormsPopup !== 'undefined') {
        if (type === 'error') {
            FormsPopup.showError(message);
        } else {
            FormsPopup.showSuccess(message);
        }
    } else {
        alert(message);
    }
}

window.handlePhoneCallback = function (event, consultationId) {
    event.preventDefault();

    const form = event.target;
    const phoneInput = form.querySelector('input[name="phone"]');
    const phone = phoneInput ? phoneInput.value.trim() : '';

    if (!phone) {
        showConsultationMessage('Пожалуйста, введите номер телефона', 'error');
        return;
    }

    const phoneRegex = /^\+?[\d\s\-\(\)]{10,15}$/;
    if (!phoneRegex.test(phone)) {
        showConsultationMessage('Пожалуйста, введите корректный номер телефона', 'error');
        return;
    }

    const langPrefix = typeof getLanguagePrefix === 'function'
        ? getLanguagePrefix()
        : `/${(document.documentElement.lang || 'ru').split('-')[0]}`;

    const endpoint = `${langPrefix.replace(/\/$/, '')}/users/quick-consultation/`;

    if (typeof submitFormAjax === 'function') {
        submitFormAjax(form, endpoint, () => {
            window.switchConsultationTab(consultationId, 'whatsapp');
        });
        return;
    }

    const button = form.querySelector('button[type="submit"]');
    const originalText = button ? button.textContent : '';

    if (button) {
        button.textContent = 'Отправляем...';
        button.disabled = true;
    }

    if (phoneInput) {
        phoneInput.value = phone;
    }

    const formData = new FormData(form);

    const headers = { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' };
    const csrfToken = typeof getCSRFToken === 'function'
        ? getCSRFToken()
        : document.querySelector('meta[name="csrf-token"]')?.content;
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }

    fetch(endpoint, {
        method: 'POST',
        body: formData,
        headers
        ,
        credentials: 'same-origin'
    })
        .then(response => {
            if (!response.ok && response.status !== 400) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showConsultationMessage(data.message || 'Спасибо! Мы свяжемся с вами в ближайшее время.', 'success');
                phoneInput.value = '';
                window.switchConsultationTab(consultationId, 'whatsapp');
            } else {
                const message = data.message || 'Произошла ошибка. Попробуйте еще раз.';
                showConsultationMessage(message, 'error');
            }
        })
        .catch(error => {
            console.error('Error submitting consultation form:', error);
            showConsultationMessage('Произошла ошибка. Попробуйте еще раз.', 'error');
        })
        .finally(() => {
            if (button) {
                button.textContent = originalText || 'Заказать звонок';
                button.disabled = false;
            }
        });
};

// Phone mask functionality
function initPhoneMask() {
    const phoneInput = document.getElementById('phone');
    if (!phoneInput) return;

    phoneInput.addEventListener('input', function (e) {
        let value = e.target.value.replace(/\D/g, '');
        let formattedValue = '';

        if (value.length > 0) {
            if (value.startsWith('7') || value.startsWith('8')) {
                // Russian format
                if (value.startsWith('8')) value = '7' + value.slice(1);
                formattedValue = '+7';
                if (value.length > 1) formattedValue += ' (' + value.slice(1, 4);
                if (value.length >= 4) formattedValue += ') ' + value.slice(4, 7);
                if (value.length >= 7) formattedValue += '-' + value.slice(7, 9);
                if (value.length >= 9) formattedValue += '-' + value.slice(9, 11);
            } else {
                // International format
                formattedValue = '+' + value.slice(0, 15);
            }
        }

        e.target.value = formattedValue;
    });

    phoneInput.addEventListener('keydown', function (e) {
        if (e.key === 'Backspace' || e.key === 'Delete') {
            return;
        }
        if (!/[0-9+]/.test(e.key) && !e.ctrlKey && !e.metaKey && e.key !== 'Tab' && e.key !== 'Enter') {
            e.preventDefault();
        }
    });
}

// Phone consultation form submission
// REMOVED: Now handled by forms.js with quickConsultationForm ID
// function initPhoneConsultationForm() {
//     const form = document.getElementById('phoneConsultationForm');
//     if (!form) return;
//
//     form.addEventListener('submit', function (e) {
//         e.preventDefault();
//         ...
//     });
// }

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    initPhoneMask();
    // initPhoneConsultationForm(); // REMOVED: Now handled by forms.js
});
