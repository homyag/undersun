/**
 * Phone Input - Disabled
 * Автоматическое определение страны отключено
 */

class PhoneInputManager {
    constructor() {
        // Отключено - не инициализируем intl-tel-input
        // Phone input auto-detection intentionally disabled; no runtime init
    }

    async init() {
        // Не делаем ничего
    }
}

// Глобальная заглушка - не инициализируем
let phoneManager = null;
window.phoneManager = phoneManager;
window.PhoneInputManager = PhoneInputManager;
