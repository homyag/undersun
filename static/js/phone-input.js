/**
 * Phone Input - Disabled
 * Автоматическое определение страны отключено
 */

class PhoneInputManager {
    constructor() {
        // Отключено - не инициализируем intl-tel-input
        console.log('Phone input auto-detection disabled');
    }

    async init() {
        // Не делаем ничего
    }
}

// Глобальная заглушка - не инициализируем
let phoneManager = null;
window.phoneManager = phoneManager;
window.PhoneInputManager = PhoneInputManager;

console.log('Phone input functionality disabled - using simple tel inputs');