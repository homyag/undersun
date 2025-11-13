// Dynamic search counter functionality - Production Version
let initAttempts = 0;
const MAX_INIT_ATTEMPTS = 3;

function initializeSearchCounter() {
    initAttempts++;
    
    // Ищем форму более надежными способами
    const searchForm = document.querySelector('form[action*="search"]') || 
                      document.querySelector('form[method="get"]') ||
                      document.querySelector('form');
    const searchCountElements = Array.from(document.querySelectorAll('[data-search-count]'));

    if (!searchForm || searchCountElements.length === 0) {
        // Попробуем еще раз через 500ms, если не исчерпали попытки
        if (initAttempts < MAX_INIT_ATTEMPTS) {
            setTimeout(initializeSearchCounter, 500);
        }
        return;
    }

    // Сохраняем первоначальное значение как fallback
    const initialCount = searchCountElements[0].textContent.trim();

    function setSearchCount(value) {
        searchCountElements.forEach(el => {
            el.textContent = value;
        });
    }
    
    // Ищем элементы фильтрации
    const typeSelect = searchForm.querySelector('select[name="type"]') || 
                      document.querySelector('select[name="type"]');
    
    const locationSelect = searchForm.querySelector('select[name="location"]') ||
                          document.querySelector('select[name="location"]');
    
    const minPriceInput = searchForm.querySelector('input[name="min_price"]') ||
                         document.querySelector('input[name="min_price"]');
                         
    const maxPriceInput = searchForm.querySelector('input[name="max_price"]') ||
                         document.querySelector('input[name="max_price"]');
    
    let updateTimeout;
    
    // Update search count with filters
    function updateSearchCount() {
        clearTimeout(updateTimeout);
        updateTimeout = setTimeout(() => {
            // Create URL params for GET request
            const params = new URLSearchParams();
            if (typeSelect && typeSelect.value) params.append('type', typeSelect.value);
            if (locationSelect && locationSelect.value) params.append('location', locationSelect.value);
            if (minPriceInput && minPriceInput.value) params.append('min_price', minPriceInput.value);
            if (maxPriceInput && maxPriceInput.value) params.append('max_price', maxPriceInput.value);
            
            // Если все фильтры пустые, показываем изначальное значение без AJAX запроса
            if (params.toString() === '') {
                setSearchCount(initialCount);
                return;
            }

            // Показываем индикатор загрузки
            setSearchCount('...');
            
            // Определяем языковой префикс из текущего URL или языка документа
            const currentPath = window.location.pathname;
            const documentLang = document.documentElement.lang?.split('-')[0] || 'en';
            const langPrefix = currentPath.match(/^\/(ru|en|th)\//)?.[0] || `/${documentLang}/`;
            
            // Fetch count from server
            fetch(`${langPrefix}property/ajax/search-count/?${params.toString()}`, {
                method: 'GET'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.text().then(text => {
                    try {
                        return JSON.parse(text);
                    } catch (e) {
                        console.error('Invalid JSON response:', text);
                        throw new Error('Invalid JSON response');
                    }
                });
            })
            .then(data => {
                if (data.success) {
                    setSearchCount(data.count);
                } else {
                    console.error('Server error:', data.error);
                    // Возвращаем первоначальное значение при ошибке
                    setSearchCount(initialCount);
                }
            })
            .catch(error => {
                console.error('Error fetching search count:', error);
                // Возвращаем первоначальное значение при ошибке сети
                setSearchCount(initialCount);
            });
        }, 300); // Debounce updates
    }
    
    // Get CSRF token
    function getCsrfToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
    
    // Add event listeners to form inputs
    if (typeSelect) {
        typeSelect.addEventListener('change', updateSearchCount);
    }
    if (locationSelect) {
        locationSelect.addEventListener('change', updateSearchCount);
    }
    if (minPriceInput) {
        minPriceInput.addEventListener('input', updateSearchCount);
    }
    if (maxPriceInput) {
        maxPriceInput.addEventListener('input', updateSearchCount);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Запуск инициализации с небольшой задержкой
    setTimeout(initializeSearchCounter, 100);
});
