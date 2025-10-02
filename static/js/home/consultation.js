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
window.handlePhoneCallback = function (event, consultationId) {
    event.preventDefault();

    const form = event.target;
    const phoneInput = form.querySelector('input[type="tel"]');
    const phone = phoneInput.value.trim();

    if (!phone) {
        alert('Пожалуйста, введите номер телефона');
        return;
    }

    // Basic phone validation
    const phoneRegex = /^\+?[\d\s\-\(\)]{10,15}$/;
    if (!phoneRegex.test(phone)) {
        alert('Пожалуйста, введите корректный номер телефона');
        return;
    }

    const button = form.querySelector('button[type="submit"]');
    const originalText = button.textContent;

    // Show loading state
    button.textContent = 'Отправляем...';
    button.disabled = true;

    // Simulate form submission (replace with actual API call)
    setTimeout(() => {
        alert('Спасибо! Мы свяжемся с вами в ближайшее время.');
        phoneInput.value = '';
        button.textContent = originalText;
        button.disabled = false;

        // Switch to WhatsApp tab as alternative
        window.switchConsultationTab(consultationId, 'whatsapp');
    }, 1500);

    // TODO: Replace with actual API call to backend
    // fetch('/api/callback-request/', {
    //     method: 'POST',
    //     headers: {
    //         'Content-Type': 'application/json',
    //         'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value
    //     },
    //     body: JSON.stringify({ phone: phone })
    // }).then(response => response.json())
    // .then(data => {
    //     if (data.success) {
    //         alert('Спасибо! Мы свяжемся с вами в ближайшее время.');
    //         phoneInput.value = '';
    //     } else {
    //         alert('Произошла ошибка. Попробуйте еще раз.');
    //     }
    // }).catch(error => {
    //     console.error('Error:', error);
    //     alert('Произошла ошибка. Попробуйте еще раз.');
    // }).finally(() => {
    //     button.textContent = originalText;
    //     button.disabled = false;
    // });
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