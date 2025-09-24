/**
 * International Phone Input Integration
 * Автоматическое определение страны по IP и настройка интернациональных телефонных номеров
 */

class PhoneInputManager {
    constructor() {
        this.phoneInputs = [];
        this.countryCode = null;
        this.init();
    }

    async init() {
        // Ждем полной загрузки DOM
        if (document.readyState === 'loading') {
            await new Promise(resolve => {
                document.addEventListener('DOMContentLoaded', resolve);
            });
        }

        // Ждем загрузки всех стилей и скриптов
        await this.waitForStyles();

        // Сначала определяем страну
        await this.detectCountry();

        // Затем инициализируем все поля телефонов
        this.initializePhoneInputs();

        // Дополнительное время для стабилизации dropdown позиционирования
        setTimeout(() => {
            this.reapplyDropdownFixes();
        }, 200);
    }

    /**
     * Ожидание загрузки стилей и библиотек
     */
    async waitForStyles() {
        // Проверяем, что intl-tel-input загружен
        let attempts = 0;
        while (!window.intlTelInput && attempts < 50) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }

        // Ждем загрузки CSS стилей
        await new Promise(resolve => setTimeout(resolve, 150));

        // Проверяем, что CSS стили применились
        const testElement = document.createElement('div');
        testElement.className = 'iti';
        testElement.style.visibility = 'hidden';
        testElement.style.position = 'absolute';
        testElement.style.top = '-9999px';
        document.body.appendChild(testElement);

        // Ждем применения стилей
        await new Promise(resolve => setTimeout(resolve, 50));

        const computedStyle = window.getComputedStyle(testElement);
        if (computedStyle.position !== 'relative') {
            // Если стили не применились, ждем еще
            await new Promise(resolve => setTimeout(resolve, 200));
        }

        document.body.removeChild(testElement);
    }

    /**
     * Повторное применение фиксов dropdown после инициализации
     */
    reapplyDropdownFixes() {
        this.phoneInputs.forEach(phoneInput => {
            this.fixDropdownPositioning(phoneInput.input, phoneInput.iti);
        });
    }

    /**
     * Определение страны по IP
     */
    async detectCountry() {
        try {
            // Сначала пробуем определить по локали браузера (быстрее)
            this.countryCode = this.getCountryFromLocale();

            // Если не удалось, пробуем IP сервисы
            if (!this.countryCode) {
                const services = [
                    'https://ipapi.co/json/',
                    'https://api.ipdata.co/json/?api-key=test'
                ];

                for (const service of services) {
                    try {
                        const response = await fetch(service, {
                            method: 'GET',
                            headers: {
                                'Accept': 'application/json',
                            },
                            timeout: 3000
                        });

                        if (response.ok) {
                            const data = await response.json();

                            if (data.country_code || data.country) {
                                this.countryCode = (data.country_code || data.country).toLowerCase();
                                console.log('Detected country by IP:', this.countryCode);
                                break;
                            }
                        }
                    } catch (error) {
                        console.warn('Failed to detect country from', service, error);
                    }
                }
            }

            // Последний fallback: Thailand (по умолчанию для вашего проекта)
            if (!this.countryCode) {
                this.countryCode = 'th';
            }

            console.log('Final country code:', this.countryCode);

        } catch (error) {
            console.error('Country detection failed:', error);
            this.countryCode = 'th'; // Thailand по умолчанию
        }
    }

    /**
     * Определение страны по локали браузера
     */
    getCountryFromLocale() {
        try {
            const locale = navigator.language || navigator.userLanguage;
            const countryMappings = {
                'ru': 'ru',
                'ru-RU': 'ru',
                'en-US': 'us',
                'en-GB': 'gb',
                'th': 'th',
                'th-TH': 'th'
            };

            return countryMappings[locale] || null;
        } catch (error) {
            return null;
        }
    }

    /**
     * Инициализация всех полей телефонов на странице
     */
    initializePhoneInputs() {
        const phoneFields = document.querySelectorAll('input[type="tel"]');

        phoneFields.forEach(field => {
            this.setupPhoneInput(field);
        });
    }

    /**
     * Настройка конкретного поля телефона
     */
    setupPhoneInput(input) {
        if (!window.intlTelInput) {
            console.error('intl-tel-input library not loaded');
            return;
        }

        const iti = window.intlTelInput(input, {
            // Начальная страна
            initialCountry: this.countryCode || 'th',

            // Приоритетные страны (для вашего проекта)
            preferredCountries: ['th', 'ru', 'gb', 'us'],

            // Показывать только эти страны (можно убрать для полного списка)
            // onlyCountries: ['th', 'ru', 'gb', 'us', 'de', 'fr', 'cn', 'jp'],

            // Настройки
            separateDialCode: true,
            autoPlaceholder: "aggressive",
            formatOnDisplay: true,
            nationalMode: false,

            // Utilities script для валидации
            utilsScript: "https://cdn.jsdelivr.net/npm/intl-tel-input@18.2.1/build/js/utils.js",

            // Кастомизация placeholder
            customPlaceholder: function(selectedCountryPlaceholder, selectedCountryData) {
                return selectedCountryPlaceholder;
            }
        });

        // Сохраняем ссылку на объект
        this.phoneInputs.push({
            input: input,
            iti: iti
        });

        // Добавляем валидацию
        this.addValidation(input, iti);

        // Обновляем placeholder в зависимости от страны
        this.updatePlaceholder(input, iti);

        // Исправляем позиционирование dropdown
        this.fixDropdownPositioning(input, iti);
    }

    /**
     * Добавление валидации
     */
    addValidation(input, iti) {
        const errorMsg = document.createElement('div');
        errorMsg.className = 'text-red-600 text-sm mt-1 hidden';
        errorMsg.id = input.id + '_error';
        input.parentNode.appendChild(errorMsg);

        const validatePhone = () => {
            const container = input.closest('.iti').parentElement;

            if (!input.value.trim()) {
                errorMsg.classList.add('hidden');
                input.classList.remove('border-red-500');
                container.classList.remove('phone-input-error', 'phone-input-valid');
                return true;
            }

            // Проверяем, загружены ли utils для валидации
            if (typeof window.intlTelInputUtils === 'undefined') {
                console.warn('intlTelInputUtils not loaded, validation skipped');
                return true;
            }

            const isValid = iti.isValidNumber();

            if (!isValid) {
                const errorCode = iti.getValidationError();
                errorMsg.textContent = this.getErrorMessage(errorCode);
                errorMsg.classList.remove('hidden');
                input.classList.add('border-red-500');
                container.classList.add('phone-input-error');
                container.classList.remove('phone-input-valid');
                return false;
            } else {
                errorMsg.classList.add('hidden');
                input.classList.remove('border-red-500');
                container.classList.add('phone-input-valid');
                container.classList.remove('phone-input-error');
                return true;
            }
        };

        // Валидация при изменении
        input.addEventListener('blur', validatePhone);
        input.addEventListener('input', () => {
            // Убираем ошибку при начале ввода
            if (errorMsg.classList.contains('hidden') === false) {
                errorMsg.classList.add('hidden');
                input.classList.remove('border-red-500');
            }
        });

        // Валидация при смене страны
        input.addEventListener('countrychange', () => {
            this.updatePlaceholder(input, iti);
            validatePhone();
        });
    }

    /**
     * Обновление placeholder в зависимости от выбранной страны
     */
    updatePlaceholder(input, iti) {
        // Даем время для intl-tel-input установить свой placeholder
        setTimeout(() => {
            const countryCode = iti.getSelectedCountryData().iso2;

            // Кастомные placeholder без кода страны (так как intl-tel-input показывает код отдельно)
            const customPlaceholders = {
                'th': '63 303 3133',
                'ru': '(999) 123-45-67',
                'us': '(555) 123-4567',
                'gb': '7700 900123'
            };

            if (customPlaceholders[countryCode]) {
                input.placeholder = customPlaceholders[countryCode];
            }
            // Если страна не в нашем списке, используем автоматический placeholder от intl-tel-input
        }, 100);
    }

    /**
     * Получение текста ошибки валидации
     */
    getErrorMessage(errorCode) {
        const errorMessages = {
            [intlTelInputUtils.validationError.INVALID_COUNTRY_CODE]: "Неверный код страны",
            [intlTelInputUtils.validationError.TOO_SHORT]: "Номер слишком короткий",
            [intlTelInputUtils.validationError.TOO_LONG]: "Номер слишком длинный",
            [intlTelInputUtils.validationError.NOT_A_NUMBER]: "Недопустимые символы",
            [intlTelInputUtils.validationError.INVALID_LENGTH]: "Неверная длина номера"
        };

        return errorMessages[errorCode] || "Неверный номер телефона";
    }

    /**
     * Получение всех валидных номеров
     */
    getAllPhoneNumbers() {
        const numbers = {};

        this.phoneInputs.forEach((phoneInput, index) => {
            const fieldName = phoneInput.input.name || `phone_${index}`;
            const isValid = phoneInput.iti.isValidNumber();

            numbers[fieldName] = {
                value: phoneInput.input.value,
                international: phoneInput.iti.getNumber(),
                national: phoneInput.iti.getNumber(intlTelInputUtils.numberFormat.NATIONAL),
                country: phoneInput.iti.getSelectedCountryData(),
                isValid: isValid
            };
        });

        return numbers;
    }

    /**
     * Валидация всех полей телефонов
     */
    validateAllPhones() {
        let allValid = true;

        this.phoneInputs.forEach(phoneInput => {
            if (phoneInput.input.value.trim()) {
                const isValid = phoneInput.iti.isValidNumber();
                if (!isValid) {
                    allValid = false;
                    phoneInput.input.focus();
                }
            }
        });

        return allValid;
    }

    /**
     * Исправляем позиционирование dropdown
     */
    fixDropdownPositioning(input, iti) {
        const container = input.closest('.iti');
        console.log('Setting up dropdown positioning for:', input.id || input.name || 'phone input', 'Container:', container);

        if (!container) {
            console.error('No .iti container found for input:', input);
            return;
        }

        // Фикс для первоначального позиционирования
        const fixInitialPosition = () => {
            const dropdown = container.querySelector('.iti__dropdown');
            console.log('Attempting to fix dropdown positioning, dropdown found:', !!dropdown);

            if (dropdown) {
                console.log('Current dropdown position:', window.getComputedStyle(dropdown).position);
                console.log('Current dropdown top:', window.getComputedStyle(dropdown).top);
                console.log('Current dropdown left:', window.getComputedStyle(dropdown).left);

                // Принудительно устанавливаем правильное позиционирование
                dropdown.style.setProperty('position', 'absolute', 'important');
                dropdown.style.setProperty('top', '100%', 'important');
                dropdown.style.setProperty('left', '0', 'important');
                dropdown.style.setProperty('right', 'auto', 'important');
                dropdown.style.setProperty('bottom', 'auto', 'important');
                dropdown.style.setProperty('transform', 'none', 'important');
                dropdown.style.setProperty('-webkit-transform', 'none', 'important');
                dropdown.style.setProperty('-moz-transform', 'none', 'important');
                dropdown.style.setProperty('z-index', '1050', 'important');
                dropdown.style.setProperty('contain', 'layout style paint', 'important');

                // Убираем любые стили, которые могут мешать
                dropdown.style.removeProperty('margin-top');
                dropdown.style.removeProperty('margin-left');

                // Устанавливаем контейнер как relative если он не установлен
                if (container.style.position !== 'relative') {
                    container.style.setProperty('position', 'relative', 'important');
                }

                // Обеспечиваем правильную прокрутку
                const countryList = dropdown.querySelector('.iti__country-list');
                if (countryList) {
                    // Важно: устанавливаем прокрутку БЕЗ !important для лучшей совместимости
                    countryList.style.overflowY = 'auto';
                    countryList.style.maxHeight = '200px';
                    countryList.style.scrollBehavior = 'smooth';
                    countryList.style.webkitOverflowScrolling = 'touch';

                    // Дополнительные стили для надежной прокрутки
                    countryList.style.overflowX = 'hidden';
                    countryList.style.height = 'auto';

                    // Убираем любые конфликтующие стили
                    countryList.style.removeProperty('overflow');
                    countryList.style.removeProperty('height');

                    console.log('Scroll properties set for country list');
                }

                console.log('Fixed dropdown positioning for:', input.id || input.name || 'phone input');
                console.log('After fix - position:', window.getComputedStyle(dropdown).position);
                console.log('After fix - top:', window.getComputedStyle(dropdown).top);
                console.log('After fix - left:', window.getComputedStyle(dropdown).left);
            }
        };

        // Применяем фикс при открытии dropdown
        const flagContainer = container.querySelector('.iti__flag-container');
        console.log('Flag container found:', !!flagContainer);

        if (flagContainer) {
            flagContainer.addEventListener('click', (e) => {
                console.log('Flag container clicked');
                // Ждем создания dropdown с несколькими попытками
                const waitForDropdown = (attempts = 0) => {
                    const dropdown = container.querySelector('.iti__dropdown');
                    console.log(`Attempt ${attempts + 1}: Dropdown found:`, !!dropdown);

                    if (dropdown) {
                        fixInitialPosition();
                    } else if (attempts < 10) {
                        setTimeout(() => waitForDropdown(attempts + 1), 50);
                    } else {
                        console.log('Failed to find dropdown after 10 attempts');
                    }
                };

                // Начинаем поиск dropdown немедленно
                waitForDropdown();
            });
        }

        // Дополнительный фикс при любых кликах на контейнере
        container.addEventListener('click', (e) => {
            console.log('Container clicked');
            setTimeout(() => {
                const dropdown = container.querySelector('.iti__dropdown');
                if (dropdown && window.getComputedStyle(dropdown).display !== 'none') {
                    console.log('Dropdown visible after click, applying fix');
                    fixInitialPosition();
                }
            }, 100); // Увеличили задержку
        });

        // Применяем фикс при focus на input
        input.addEventListener('focus', () => {
            console.log('Input focused');
            setTimeout(fixInitialPosition, 1);
        });

        // Применяем фикс при инициализации
        setTimeout(fixInitialPosition, 100);

        // MutationObserver для отслеживания изменений DOM (только создание dropdown)
        let dropdownFixed = false;
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && !dropdownFixed) {
                    const dropdown = container.querySelector('.iti__dropdown');
                    if (dropdown && window.getComputedStyle(dropdown).display !== 'none') {
                        console.log('Dropdown appeared via MutationObserver');
                        fixInitialPosition();
                        dropdownFixed = true; // Больше не фиксим этот dropdown

                        // Отключаем observer после первого фикса
                        setTimeout(() => {
                            observer.disconnect();
                        }, 1000);
                    }
                }
            });
        });

        // Наблюдаем за изменениями в контейнере (только создание новых элементов)
        observer.observe(container, {
            childList: true,
            subtree: false // Не следим за вложенными изменениями
        });

        // Фикс для проблемы с позиционированием при скролле страницы
        window.addEventListener('scroll', () => {
            const dropdown = container.querySelector('.iti__dropdown');
            if (dropdown && dropdown.style.display !== 'none') {
                fixInitialPosition();
            }
        }, { passive: true });

        // Фикс для resize окна
        window.addEventListener('resize', () => {
            const dropdown = container.querySelector('.iti__dropdown');
            if (dropdown && dropdown.style.display !== 'none') {
                setTimeout(fixInitialPosition, 100);
            }
        }, { passive: true });
    }
}

// Глобальная инициализация
let phoneManager = null;

// Функция для инициализации с проверкой загрузки библиотеки
async function initializePhoneManager() {
    // Ждем загрузки intl-tel-input библиотеки
    let attempts = 0;
    while (typeof window.intlTelInput === 'undefined' && attempts < 100) {
        await new Promise(resolve => setTimeout(resolve, 100));
        attempts++;
    }

    if (typeof window.intlTelInput !== 'undefined') {
        console.log('intl-tel-input library loaded, initializing PhoneInputManager...');
        phoneManager = new PhoneInputManager();
        window.phoneManager = phoneManager;
    } else {
        console.error('intl-tel-input library not found after waiting 10 seconds. Please check if it is included properly.');
    }
}

// Автоматическая инициализация при загрузке DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePhoneManager);
} else {
    // DOM уже загружен
    initializePhoneManager();
}

// Дополнительная попытка инициализации при загрузке окна
window.addEventListener('load', () => {
    if (!phoneManager && typeof window.intlTelInput !== 'undefined') {
        console.log('Secondary initialization attempt...');
        initializePhoneManager();
    }
});

// Экспорт для использования в других скриптах
window.PhoneInputManager = PhoneInputManager;