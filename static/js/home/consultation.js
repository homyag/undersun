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
    const quickForm = document.getElementById('quickConsultationForm');
    if (!quickForm) return;

    const phoneInput = quickForm.querySelector('input[name="phone"]');
    if (!phoneInput) return;

    const placeholder = phoneInput.getAttribute('placeholder') || '+66 63 303 3133';
    if (!phoneInput.getAttribute('placeholder')) {
        phoneInput.setAttribute('placeholder', placeholder);
    }

    const allowedCharRegex = /[0-9+()\s-]/;

    phoneInput.addEventListener('input', function (e) {
        const { selectionStart } = e.target;
        const sanitized = e.target.value.replace(/[^0-9+()\s-]/g, '');

        if (sanitized !== e.target.value) {
            e.target.value = sanitized;
            if (selectionStart !== null) {
                const newPos = Math.max(selectionStart - 1, 0);
                requestAnimationFrame(() => {
                    e.target.setSelectionRange(newPos, newPos);
                });
            }
        }
    });

    phoneInput.addEventListener('keydown', function (e) {
        if (
            e.key === 'Backspace' ||
            e.key === 'Delete' ||
            e.key === 'Tab' ||
            e.key === 'Enter' ||
            e.key === 'ArrowLeft' ||
            e.key === 'ArrowRight' ||
            e.key === 'Home' ||
            e.key === 'End'
        ) {
            return;
        }

        if (!allowedCharRegex.test(e.key) && !e.ctrlKey && !e.metaKey) {
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
