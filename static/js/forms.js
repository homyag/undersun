/**
 * Универсальная система обработки форм с AJAX
 * Undersun Estate - Forms Handler
 */

// Утилита для показа popup
const FormsPopup = {
    /**
     * Показать успешный popup
     * @param {string} message - Текст сообщения
     */
    showSuccess(message) {
        const popup = document.getElementById('successPopup');
        const messageEl = document.getElementById('successPopupMessage');

        if (!popup || !messageEl) {
            console.error('Success popup elements not found');
            alert(message);
            return;
        }

        messageEl.textContent = message;
        popup.style.display = 'flex';
        popup.classList.remove('hidden');

        // Автоматически закрыть через 5 секунд
        setTimeout(() => {
            this.hideSuccess();
        }, 5000);
    },

    /**
     * Скрыть успешный popup
     */
    hideSuccess() {
        const popup = document.getElementById('successPopup');
        if (popup) {
            popup.style.display = 'none';
            popup.classList.add('hidden');
        }
    },

    /**
     * Показать popup ошибки
     * @param {string} message - Текст ошибки
     */
    showError(message) {
        const popup = document.getElementById('errorPopup');
        const messageEl = document.getElementById('errorPopupMessage');

        if (!popup || !messageEl) {
            console.error('Error popup elements not found');
            alert(message);
            return;
        }

        messageEl.textContent = message;
        popup.style.display = 'flex';
        popup.classList.remove('hidden');
    },

    /**
     * Скрыть popup ошибки
     */
    hideError() {
        const popup = document.getElementById('errorPopup');
        if (popup) {
            popup.style.display = 'none';
            popup.classList.add('hidden');
        }
    }
};

// Получение CSRF токена
function getCSRFToken() {
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    const inputToken = document.querySelector('[name=csrfmiddlewaretoken]');
    return metaToken?.content || inputToken?.value || '';
}

/**
 * Универсальный обработчик отправки формы
 * @param {HTMLFormElement} form - Форма для отправки
 * @param {string} url - URL endpoint
 * @param {Function} successCallback - Callback при успехе (опционально)
 * @param {Function} errorCallback - Callback при ошибке (опционально)
 */
function submitFormAjax(form, url, successCallback = null, errorCallback = null) {
    const formData = new FormData(form);
    const submitButton = form.querySelector('[type="submit"]');
    const originalButtonText = submitButton?.textContent || 'Отправить';

    // Деактивируем кнопку отправки
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = 'Отправка...';
    }

    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok && response.status !== 400) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Показываем успешное сообщение
            FormsPopup.showSuccess(data.message);

            // Сбрасываем форму
            form.reset();

            // Вызываем кастомный callback если есть
            if (successCallback) {
                successCallback(data);
            }
        } else {
            // Показываем ошибку
            FormsPopup.showError(data.message || 'Произошла ошибка при отправке формы');

            // Вызываем кастомный callback если есть
            if (errorCallback) {
                errorCallback(data);
            }
        }
    })
    .catch(error => {
        console.error('Form submission error:', error);
        FormsPopup.showError('Произошла ошибка. Пожалуйста, попробуйте позже.');

        if (errorCallback) {
            errorCallback(error);
        }
    })
    .finally(() => {
        // Активируем кнопку обратно
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
        }
    });
}

// Получение текущего языкового префикса из URL
function getLanguagePrefix() {
    const path = window.location.pathname;
    const match = path.match(/^\/(ru|en|th)\//);
    if (match) {
        return `/${match[1]}`;
    }
    const documentLang = document.documentElement.lang?.split('-')[0] || 'en';
    return `/${documentLang}`;
}

// Инициализация обработчиков при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    // Получаем языковой префикс
    const langPrefix = getLanguagePrefix();

    // Закрытие popups
    const successPopupClose = document.getElementById('successPopupClose');
    if (successPopupClose) {
        successPopupClose.addEventListener('click', () => FormsPopup.hideSuccess());
    }

    const errorPopupClose = document.getElementById('errorPopupClose');
    if (errorPopupClose) {
        errorPopupClose.addEventListener('click', () => FormsPopup.hideError());
    }

    // Закрытие popup при клике вне его
    document.getElementById('successPopup')?.addEventListener('click', function(e) {
        if (e.target === this) {
            FormsPopup.hideSuccess();
        }
    });

    document.getElementById('errorPopup')?.addEventListener('click', function(e) {
        if (e.target === this) {
            FormsPopup.hideError();
        }
    });

    // === ОБРАБОТЧИКИ ДЛЯ ВСЕХ ФОРМ ===

    // 1. Быстрая консультация (форма с телефоном на главной)
    const quickConsultationForm = document.getElementById('quickConsultationForm');
    if (quickConsultationForm) {
        quickConsultationForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitFormAjax(this, `${langPrefix}/users/quick-consultation/`);
        });
    }

    // 2. Контактная форма
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitFormAjax(this, `${langPrefix}/users/contact/`);
        });
    }

    // 3. Запись на встречу в офисе
    const officeVisitForm = document.getElementById('officeVisitForm');
    if (officeVisitForm) {
        officeVisitForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitFormAjax(this, `${langPrefix}/users/office-visit/`);
        });
    }

    // 4. Вопрос из FAQ
    const faqQuestionForm = document.getElementById('faqQuestionForm');
    if (faqQuestionForm) {
        faqQuestionForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitFormAjax(this, `${langPrefix}/users/faq-question/`);
        });
    }

    // 5. Подписка на новости
    const newsletterForm = document.getElementById('newsletterForm');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitFormAjax(this, `${langPrefix}/users/newsletter/subscribe/`);
        });
    }

    // 6. Запись на просмотр объекта (на странице объекта)
    const viewingRequestForm = document.getElementById('viewingRequestForm');
    if (viewingRequestForm) {
        viewingRequestForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const propertyId = this.dataset.propertyId;
            submitFormAjax(this, `${langPrefix}/users/property/${propertyId}/inquiry/`);
        });
    }

    // 7. Консультация по объекту (на странице объекта)
    const consultationRequestForm = document.getElementById('consultationRequestForm');
    if (consultationRequestForm) {
        consultationRequestForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const propertyId = this.dataset.propertyId;
            submitFormAjax(this, `${langPrefix}/users/property/${propertyId}/inquiry/`);
        });
    }

    // 8. Форма контакта в секции Reviews (главная страница)
    const reviewsSectionContactForm = document.getElementById('reviewsSectionContactForm');
    if (reviewsSectionContactForm) {
        reviewsSectionContactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitFormAjax(this, `${langPrefix}/users/contact/`);
        });
    }
});

// Экспортируем для использования в других скриптах
window.FormsPopup = FormsPopup;
window.submitFormAjax = submitFormAjax;
window.getCSRFToken = getCSRFToken;
