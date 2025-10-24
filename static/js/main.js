$(document).ready(function() {

    // ===== CSRF TOKEN SETUP =====
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken = getCookie('csrftoken');

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

    // ===== HERO CAROUSEL =====
    let currentSlide = 0;
    const slides = $('.hero-slide');
    const totalSlides = slides.length;

    function nextSlide() {
        slides.eq(currentSlide).removeClass('active');
        currentSlide = (currentSlide + 1) % totalSlides;
        slides.eq(currentSlide).addClass('active');
    }

    // Автоматическая смена слайдов каждые 5 секунд
    if (totalSlides > 1) {
        setInterval(nextSlide, 5000);
    }

    // ===== ИЗБРАННОЕ НА ОСНОВЕ LOCAL STORAGE =====
    
    // Инициализация избранного при загрузке страницы
    initializeFavorites();
    
    // Обработчик кнопок избранного с делегированием
    $(document).on('click', '.favorite-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const btn = $(this);
        const propertyId = btn.data('property-id');
        const icon = btn.find('i');
        
        
        toggleFavorite(propertyId, icon);
    });
    
    // Обновляем счетчик и состояние сердца при загрузке страницы
    updateFavoritesCounter();

    // ===== ФОРМА ЗАПРОСА ПО НЕДВИЖИМОСТИ =====
    $('#inquiryForm').on('submit', function(e) {
        e.preventDefault();

        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        const originalText = submitBtn.text();

        // Отключаем кнопку
        submitBtn.prop('disabled', true).text('Отправка...');

        $.ajax({
            url: '/property/ajax/inquiry/',
            method: 'POST',
            data: form.serialize(),
            success: function(response) {
                if (response.success) {
                    showNotification(response.message, 'success');
                    form[0].reset();
                    $('#inquiryModal').modal('hide');
                } else {
                    showNotification(response.message, 'error');
                }
            },
            error: function() {
                showNotification('Произошла ошибка. Попробуйте позже.', 'error');
            },
            complete: function() {
                submitBtn.prop('disabled', false).text(originalText);
            }
        });
    });

    // ===== ГАЛЕРЕЯ ИЗОБРАЖЕНИЙ =====
    $('.property-gallery .thumbnail').on('click', function() {
        const newSrc = $(this).data('large');
        const mainImage = $('.main-image');

        // Убираем активный класс со всех миниатюр
        $('.thumbnail').removeClass('active');
        // Добавляем активный класс к текущей
        $(this).addClass('active');

        // Плавная смена изображения
        mainImage.fadeOut(200, function() {
            mainImage.attr('src', newSrc).fadeIn(200);
        });
    });

    // ===== МОДАЛЬНОЕ ОКНО ГАЛЕРЕИ =====
    $('.main-image').on('click', function() {
        const images = [];
        $('.thumbnail').each(function() {
            images.push({
                src: $(this).data('large'),
                title: $(this).attr('alt') || ''
            });
        });

        openImageGallery(images, $('.thumbnail.active').index());
    });

    // ===== ФИЛЬТРЫ НЕДВИЖИМОСТИ =====
    $(document).on('change', '#filter-form input, #filter-form select', function() {
        updatePropertyFilters();
    });
    
    // Добавляем debounce для полей цены
    let priceTimeout;
    $(document).on('input', '#filter-form input[name="min_price"], #filter-form input[name="max_price"]', function() {
        clearTimeout(priceTimeout);
        priceTimeout = setTimeout(function() {
            updatePropertyFilters();
        }, 1000); // 1 секунда задержки
    });

    // Слайдер цены
    if ($('#priceRange').length) {
        $('#priceRange').on('input', function() {
            const value = $(this).val();
            $('#priceValue').text('$' + parseInt(value).toLocaleString());
            updatePropertyFilters();
        });
    }

    // ===== КАРТА НЕДВИЖИМОСТИ =====
    if ($('#propertyMap').length) {
        initPropertyMap();
    }

    // ===== ПОИСК С АВТОЗАПОЛНЕНИЕМ =====
    $('#searchInput').on('input', function() {
        const query = $(this).val();
        if (query.length >= 2) {
            searchProperties(query);
        } else {
            $('#searchResults').hide();
        }
    });

    // ===== LAZY LOADING ИЗОБРАЖЕНИЙ =====
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }

    // ===== АНИМАЦИИ ПРИ СКРОЛЛЕ =====
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -100px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
            }
        });
    }, observerOptions);

    // Наблюдаем за элементами для анимации
    document.querySelectorAll('.property-card, .feature-icon, .district-card').forEach(el => {
        observer.observe(el);
    });

});

// ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

function showNotification(message, type = 'info') {
    
    // Используем цвета брендбука проекта
    let bgClass, textClass, iconClass, icon;
    
    switch(type) {
        case 'success':
            bgClass = 'bg-accent'; // Желтый/золотой из брендбука
            textClass = 'text-gray-900'; // Темный текст для контраста с желтым
            iconClass = 'text-gray-900';
            icon = '<i class="fas fa-check-circle mr-2"></i>';
            break;
        case 'favorite-added':
            bgClass = 'bg-primary'; // Темно-синий из брендбука
            textClass = 'text-white';
            iconClass = 'text-accent'; // Желтая иконка на синем фоне
            icon = '<i class="fas fa-heart mr-2"></i>';
            break;
        case 'favorite-removed':
            bgClass = 'bg-secondary border border-gray-300'; // Светло-серый из брендбука
            textClass = 'text-gray-700';
            iconClass = 'text-gray-500';
            icon = '<i class="far fa-heart mr-2"></i>';
            break;
        case 'error':
            bgClass = 'bg-red-500';
            textClass = 'text-white';
            iconClass = 'text-white';
            icon = '<i class="fas fa-exclamation-triangle mr-2"></i>';
            break;
        case 'info':
        default:
            bgClass = 'bg-primary'; // Темно-синий из брендбука
            textClass = 'text-white';
            iconClass = 'text-accent'; // Желтая иконка
            icon = '<i class="fas fa-info-circle mr-2"></i>';
            break;
    }

    const notification = $(`
        <div class="fixed top-20 right-4 ${bgClass} ${textClass} px-6 py-4 rounded-xl shadow-2xl z-50 transition-all duration-500 transform translate-x-full opacity-0" 
             style="min-width: 280px; max-width: 400px;">
            <div class="flex items-center justify-between">
                <div class="flex items-center">
                    <span class="${iconClass}">${icon}</span>
                    <span class="font-medium">${message}</span>
                </div>
                <button type="button" class="ml-4 ${iconClass} hover:opacity-70 transition-opacity duration-200" onclick="$(this).parent().parent().fadeOut(300, function() { $(this).remove(); })">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        </div>
    `);

    $('body').append(notification);

    // Анимация появления
    setTimeout(() => {
        notification.removeClass('translate-x-full opacity-0').addClass('translate-x-0 opacity-100');
    }, 10);

    // Автоматически скрыть через 4 секунды
    setTimeout(() => {
        notification.addClass('translate-x-full opacity-0');
        setTimeout(() => {
            notification.remove();
        }, 500);
    }, 4000);
}

// ===== ФУНКЦИИ УПРАВЛЕНИЯ ИЗБРАННЫМ =====

// Сообщения для уведомлений об избранном
function getFavoritesMessages() {
    const defaults = {
        added: 'Добавлено в избранное',
        removed: 'Удалено из избранного'
    };

    if (window.FAVORITES_MESSAGES) {
        return {
            ...defaults,
            ...window.FAVORITES_MESSAGES
        };
    }

    return defaults;
}

// Получить список избранного из LocalStorage
function getFavorites() {
    const raw = localStorage.getItem('favorites');
    if (!raw) return [];

    try {
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) {
            return [];
        }
        return parsed
            .map(id => parseInt(id, 10))
            .filter(id => Number.isInteger(id));
    } catch (err) {
        console.warn('Failed to parse favorites from localStorage', err);
        return [];
    }
}

// Сохранить список избранного в LocalStorage
function saveFavorites(favorites) {
    const sanitized = (favorites || [])
        .map(id => parseInt(id, 10))
        .filter(id => Number.isInteger(id));
    localStorage.setItem('favorites', JSON.stringify(sanitized));
}

// Проверить, находится ли объект в избранном
function isFavorite(propertyId) {
    const id = parseInt(propertyId, 10);
    if (!Number.isInteger(id)) {
        return false;
    }
    return getFavorites().includes(id);
}

function updateFavoriteButtons(propertyId, isFavoriteNow) {
    document.querySelectorAll(`.favorite-btn[data-property-id="${propertyId}"]`).forEach(btn => {
        const iconEl = btn.querySelector('i');
        if (!iconEl) return;

        iconEl.classList.toggle('fas', isFavoriteNow);
        iconEl.classList.toggle('far', !isFavoriteNow);
        iconEl.classList.toggle('text-red-500', isFavoriteNow);
        iconEl.classList.toggle('text-gray-600', !isFavoriteNow);
    });

    const standaloneIcon = document.getElementById(`favorite-${propertyId}`);
    if (standaloneIcon) {
        standaloneIcon.classList.toggle('fas', isFavoriteNow);
        standaloneIcon.classList.toggle('far', !isFavoriteNow);
        standaloneIcon.classList.toggle('text-red-500', isFavoriteNow);
        standaloneIcon.classList.toggle('text-gray-600', !isFavoriteNow);
    }
}

// Добавить/удалить объект из избранного
function toggleFavorite(propertyId, icon = null) {
    const id = parseInt(propertyId, 10);
    if (!Number.isInteger(id)) {
        return false;
    }

    const favorites = getFavorites();
    const wasFavorite = favorites.includes(id);
    let updatedFavorites;

    const messages = getFavoritesMessages();

    if (wasFavorite) {
        updatedFavorites = favorites.filter(favId => favId !== id);
        if (icon) {
            icon.removeClass('fas text-red-500').addClass('far text-gray-600');
        }
        showNotification(messages.removed, 'favorite-removed');
    } else {
        updatedFavorites = [...favorites, id];
        if (icon) {
            icon.removeClass('far text-gray-600').addClass('fas text-red-500');
        }
        showNotification(messages.added, 'favorite-added');
    }

    saveFavorites(updatedFavorites);
    updateFavoriteButtons(id, !wasFavorite);
    updateFavoritesCounter();

    return !wasFavorite;
}

// Обновить счетчик избранного
function formatFavoritesCount(count) {
    return count > 99 ? '99+' : count;
}

function updateFavoritesCounter() {
    const count = getFavorites().length;
    const displayValue = formatFavoritesCount(count);

    $('.favorites-count').each(function() {
        const el = $(this);
        el.text(displayValue);

        if (count > 0) {
            el.removeClass('hidden');
            el.addClass('inline-flex');
            el.css('display', 'inline-flex');
        } else {
            el.addClass('hidden');
            el.css('display', 'none');
        }
    });

    // Обновляем состояние сердца
    if (count > 0) {
        $('#nav-favorites-heart').removeClass('far text-gray-600').addClass('fas text-red-500');
        $('#mobile-nav-favorites-heart').removeClass('far text-gray-600').addClass('fas text-red-500');
    } else {
        $('#nav-favorites-heart').removeClass('fas text-red-500').addClass('far text-gray-600');
        $('#mobile-nav-favorites-heart').removeClass('fas text-red-500').addClass('far text-gray-600');
    }
}

// Инициализация состояния кнопок избранного на странице
function initializeFavorites() {
    $('.favorite-btn').each(function() {
        const propertyId = $(this).data('property-id');
        const id = parseInt(propertyId, 10);
        if (Number.isInteger(id)) {
            updateFavoriteButtons(id, isFavorite(id));
        }
    });
}

function updateFavoritesCount() {
    updateFavoritesCounter();
}

function updatePropertyFilters() {
    const form = $('#filter-form');
    const formData = form.serialize();

    // Показать лоадер
    $('.properties-container').addClass('loading');
    
    // Добавляем индикатор загрузки
    if (!$('.loading-overlay').length) {
        $('.properties-container').append('<div class="loading-overlay"><div class="spinner"></div></div>');
    }

    // AJAX запрос к новому endpoint
    $.ajax({
        url: '/property/ajax/list/',
        method: 'GET',
        data: formData,
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                // Обновляем список недвижимости
                updatePropertiesGrid(response.properties);
                
                // Обновляем пагинацию
                updatePagination(response.pagination);
                
                // Обновляем счетчик результатов
                updateResultsCount(response.pagination.total_count);
                
                // Обновляем состояние сортировки
                updateSortSelect();
                
                // Обновить URL без перезагрузки
                const newUrl = window.location.pathname + '?' + formData;
                history.pushState(null, '', newUrl);
            }
        },
        error: function(xhr, status, error) {
            console.error('AJAX error:', error);
            console.error('XHR:', xhr);
            console.error('Status:', status);
            showNotification('Ошибка при обновлении фильтров', 'error');
        },
        complete: function() {
            // Убираем лоадер
            $('.properties-container').removeClass('loading');
            $('.loading-overlay').remove();
        }
    });
}

function updatePropertiesGrid(properties) {
    // Используем более надежные селекторы
    let container = $('#properties-grid');
    if (container.length === 0) {
        container = $('.properties-grid');
    }
    if (container.length === 0) {
        container = $('.properties-list');
    }
    
    if (container.length === 0) {
        console.error('No container found! All selectors failed');
        return;
    }
    
    container.empty();
    
    if (properties.length === 0) {
        container.html('<div class="no-results"><p>По выбранным критериям ничего не найдено</p></div>');
        return;
    }
    
    properties.forEach((property) => {
        const propertyHtml = createPropertyCard(property);
        container.append(propertyHtml);
    });
    
    // Переинициализируем обработчики событий для новых элементов
    initPropertyCards();
}

function createPropertyCard(property) {
    const imageUrl = property.main_image_thumbnail_url || property.main_image_url || '/static/images/no-image.jpg';
    const propertyUrl = `/property/${property.slug}/`;
    
    // Определяем тип сделки и соответствующий badge
    let dealTypeBadge = '';
    if (property.deal_type === 'sale') {
        dealTypeBadge = '<span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-accent text-gray-900 shadow-sm">Продажа</span>';
    } else if (property.deal_type === 'rent') {
        dealTypeBadge = '<span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-primary text-white shadow-sm">Аренда</span>';
    } else {
        dealTypeBadge = '<span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-tertiary text-white shadow-sm">Продажа/Аренда</span>';
    }
    
    // Определяем состояние кнопки избранного
    const isFav = isFavorite(property.id);
    const heartClass = isFav ? 'fas text-red-500' : 'far text-gray-600';
    
    // Featured badge
    const featuredBadge = property.is_featured ? 
        '<div class="absolute top-2 right-2"><span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-accent text-gray-900 shadow-sm"><i class="fas fa-star mr-1"></i> Рекомендуем</span></div>' : '';
    
    // Формируем цену для отображения
    let priceDisplay = 'Цена по запросу';
    if (property.deal_type === 'rent' && property.price_usd) {
        priceDisplay = `$${property.price_usd.toLocaleString()}/мес`;
    } else if (property.price_usd) {
        priceDisplay = `$${property.price_usd.toLocaleString()}`;
    }
    
    // Создаем детали (спальни, ванные, площадь)
    let detailsHtml = '';
    let detailsCount = 0;
    
    if (property.bedrooms) {
        detailsHtml += `
            <div class="bg-gray-50 p-3 rounded-lg">
                <div class="text-primary text-sm font-medium">
                    <i class="fas fa-bed mb-2 text-accent"></i>
                    <div>${property.bedrooms} спален</div>
                </div>
            </div>`;
        detailsCount++;
    }
    
    if (property.bathrooms) {
        detailsHtml += `
            <div class="bg-gray-50 p-3 rounded-lg">
                <div class="text-primary text-sm font-medium">
                    <i class="fas fa-bath mb-2 text-accent"></i>
                    <div>${property.bathrooms} ванных</div>
                </div>
            </div>`;
        detailsCount++;
    }
    
    if (property.area) {
        detailsHtml += `
            <div class="bg-gray-50 p-3 rounded-lg">
                <div class="text-primary text-sm font-medium">
                    <i class="fas fa-ruler-combined mb-2 text-accent"></i>
                    <div>${property.area} м²</div>
                </div>
            </div>`;
        detailsCount++;
    }
    
    // Создаем grid с динамическим количеством колонок
    const gridCols = detailsCount === 1 ? 'grid-cols-1' : detailsCount === 2 ? 'grid-cols-2' : 'grid-cols-3';
    
    return `
        <div class="property-card">
            <div class="bg-white rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300 h-full flex flex-col overflow-hidden group">
                <div class="relative">
                    <img src="${imageUrl}" class="w-full h-56 object-cover group-hover:scale-105 transition-transform duration-300" alt="${property.title}" loading="lazy">
                    
                    <!-- Property Status Badge -->
                    <div class="absolute top-2 left-2">
                        ${dealTypeBadge}
                    </div>
                    
                    <!-- Favorite Button -->
                    <div class="absolute top-3 right-3">
                        <button class="bg-white/90 hover:bg-white p-2 rounded-full transition-all duration-200 group favorite-btn shadow-lg hover:shadow-xl transform hover:scale-110"
                                data-property-id="${property.id}">
                            <i class="${heartClass} group-hover:text-red-500 fa-heart transition-all duration-200"></i>
                        </button>
                    </div>
                    
                    <!-- Featured Badge -->
                    ${featuredBadge}
                </div>
                
                <div class="p-6 flex-1 flex flex-col">
                    <h6 class="font-bold text-lg text-primary mb-3 leading-tight">
                        <a href="${propertyUrl}" class="hover:text-accent transition-colors">
                            ${property.title.length > 50 ? property.title.substring(0, 50) + '...' : property.title}
                        </a>
                    </h6>
                    
                    <div class="text-tertiary mb-4 flex items-center font-medium">
                        <i class="fas fa-map-marker-alt mr-2 text-accent"></i>
                        ${property.district_name}
                    </div>
                    
                    <div class="mb-4 flex-1">
                        <div class="grid ${gridCols} gap-4 text-center">
                            ${detailsHtml}
                        </div>
                    </div>
                    
                    <div class="flex justify-between items-center mb-6">
                        <div class="property-price">
                            <span class="text-2xl font-bold text-accent">${priceDisplay}</span>
                        </div>
                        <div class="property-type">
                            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-primary text-white">${property.property_type_name}</span>
                        </div>
                    </div>
                </div>
                
                <div class="p-6 pt-0">
                    <a href="${propertyUrl}" class="block w-full text-center bg-accent hover:bg-yellow-500 text-gray-900 py-3 px-6 rounded-lg transition-colors font-bold shadow-md hover:shadow-lg">
                        Подробнее
                    </a>
                </div>
            </div>
        </div>
    `;
}

function updatePagination(pagination) {
    const paginationContainer = $('.pagination-container');
    if (!paginationContainer.length) return;
    
    let paginationHtml = '<nav class="flex items-center space-x-2">';
    
    // Previous page
    if (pagination.has_previous) {
        paginationHtml += `<a href="#" data-page="${pagination.previous_page}" class="px-3 py-2 text-sm font-medium text-gray-500 hover:text-blue-600 border border-gray-300 rounded-md hover:border-blue-600 transition-colors hover:bg-blue-50">Предыдущая</a>`;
    }
    
    // Page numbers (simplified - show current and adjacent pages)
    const currentPage = pagination.current_page;
    const totalPages = pagination.total_pages;
    
    for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
        if (i === currentPage) {
            paginationHtml += `<span class="px-3 py-2 text-sm font-medium text-white bg-blue-600 border border-blue-600 rounded-md">${i}</span>`;
        } else {
            paginationHtml += `<a href="#" data-page="${i}" class="px-3 py-2 text-sm font-medium text-gray-500 hover:text-blue-600 border border-gray-300 rounded-md hover:border-blue-600 transition-colors hover:bg-blue-50">${i}</a>`;
        }
    }
    
    // Next page
    if (pagination.has_next) {
        paginationHtml += `<a href="#" data-page="${pagination.next_page}" class="px-3 py-2 text-sm font-medium text-gray-500 hover:text-blue-600 border border-gray-300 rounded-md hover:border-blue-600 transition-colors hover:bg-blue-50">Следующая</a>`;
    }
    
    paginationHtml += '</nav>';
    paginationContainer.html(paginationHtml);
    
    // Обработчики для AJAX pagination (только для ссылок с data-page)
    $(document).on('click', '.pagination-container a[data-page]', function(e) {
        e.preventDefault();
        const page = $(this).data('page');
        const form = $('#filter-form');
        const formData = form.serialize() + '&page=' + page;
        
        updatePropertyFiltersWithParams(formData);
    });
}

function updateResultsCount(count) {
    $('.results-count').text(`Найдено: ${count} объектов`);
}

function updateSortSelect() {
    // Обновляем select сортировки в соответствии с текущим значением в форме
    const form = $('#filter-form');
    const sortValue = form.find('input[name="sort"]').val();
    const sortSelect = $('select[onchange="updateSort(this.value)"]');
    
    if (sortSelect.length && sortValue) {
        sortSelect.val(sortValue);
    }
}

function updatePropertyFiltersWithParams(params) {
    $('.properties-container').addClass('loading');
    
    $.ajax({
        url: '/property/ajax/list/',
        method: 'GET',
        data: params,
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                updatePropertiesGrid(response.properties);
                updatePagination(response.pagination);
                updateResultsCount(response.pagination.total_count);
                
                const newUrl = window.location.pathname + '?' + params;
                history.pushState(null, '', newUrl);
            }
        },
        error: function(xhr, status, error) {
            console.error('Error updating filters:', error);
            showNotification('Ошибка при обновлении фильтров', 'error');
        },
        complete: function() {
            $('.properties-container').removeClass('loading');
            $('.loading-overlay').remove();
        }
    });
}

function initPropertyCards() {
    // Переинициализируем обработчики для новых карточек недвижимости
    $('.favorite-btn').off('click').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const btn = $(this);
        const propertyId = btn.data('property-id');
        const icon = btn.find('i');
        
        toggleFavorite(propertyId, icon);
    });
    
    // Инициализируем состояние кнопок избранного
    initializeFavorites();
}

function initPropertyMap() {
    const mapElement = document.getElementById('propertyMap');
    const propertiesData = JSON.parse(mapElement.dataset.properties);

    // Инициализация карты
    const map = L.map('propertyMap').setView([7.8804, 98.3923], 11);

    // Добавление тайлов
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Кластеризация маркеров
    const markers = L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 50
    });

    // Добавление маркеров
    propertiesData.forEach(property => {
        const marker = L.marker([property.lat, property.lng]);

        const popupContent = `
            <div class="property-popup">
                ${property.image ? `<img src="${property.image}" class="popup-image" alt="${property.title}">` : ''}
                <div class="popup-title">${property.title}</div>
                <div class="popup-price">${property.price}</div>
                <div class="popup-type">${property.type}</div>
                <a href="${property.url}" class="btn btn-primary btn-sm mt-2">Подробнее</a>
            </div>
        `;

        marker.bindPopup(popupContent);
        markers.addLayer(marker);
    });

    map.addLayer(markers);

    // Фильтрация по типам недвижимости
    $('.map-filters input[type="checkbox"]').on('change', function() {
        filterMapMarkers();
    });
}

function filterMapMarkers() {
    // Логика фильтрации маркеров на карте
    const selectedTypes = [];
    $('.map-filters input[type="checkbox"]:checked').each(function() {
        selectedTypes.push($(this).val());
    });

    // Обновить маркеры на карте
    // Реализация зависит от конкретной структуры данных
}

function searchProperties(query) {
    $.get('/api/search/', { q: query }, function(data) {
        const results = data.results;
        let html = '';

        results.forEach(property => {
            html += `
                <div class="search-result-item">
                    <img src="${property.image}" alt="${property.title}">
                    <div class="result-info">
                        <h6>${property.title}</h6>
                        <p>${property.location}</p>
                        <span class="price">${property.price}</span>
                    </div>
                </div>
            `;
        });

        $('#searchResults').html(html).show();
    });
}

function openImageGallery(images, startIndex = 0) {
    // Простая реализация галереи
    // Можно использовать библиотеки типа Lightbox, Fancybox и т.д.
    let currentIndex = startIndex;

    const modal = $(`
        <div class="modal fade" id="imageGalleryModal" tabindex="-1">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Галерея</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img id="galleryImage" src="${images[currentIndex].src}" class="img-fluid" alt="${images[currentIndex].title}">
                        <div class="gallery-controls mt-3">
                            <button class="btn btn-outline-primary" id="prevImage">
                                <i class="fas fa-chevron-left"></i> Предыдущая
                            </button>
                            <span class="mx-3">${currentIndex + 1} из ${images.length}</span>
                            <button class="btn btn-outline-primary" id="nextImage">
                                Следующая <i class="fas fa-chevron-right"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `);

    $('body').append(modal);
    modal.modal('show');

    // Обработчики для навигации
    modal.find('#prevImage').on('click', function() {
        currentIndex = currentIndex > 0 ? currentIndex - 1 : images.length - 1;
        updateGalleryImage();
    });

    modal.find('#nextImage').on('click', function() {
        currentIndex = currentIndex < images.length - 1 ? currentIndex + 1 : 0;
        updateGalleryImage();
    });

    function updateGalleryImage() {
        modal.find('#galleryImage').attr('src', images[currentIndex].src);
        modal.find('.gallery-controls span').text(`${currentIndex + 1} из ${images.length}`);
    }

    // Навигация клавишами
    $(document).on('keydown.gallery', function(e) {
        if (e.key === 'ArrowLeft') modal.find('#prevImage').click();
        if (e.key === 'ArrowRight') modal.find('#nextImage').click();
        if (e.key === 'Escape') modal.modal('hide');
    });

    // Очистка при закрытии
    modal.on('hidden.bs.modal', function() {
        $(document).off('keydown.gallery');
        modal.remove();
    });
}

// ===== ФОРМАТИРОВАНИЕ ЧИСЕЛ =====
function formatPrice(price) {
    return '$' + parseInt(price).toLocaleString();
}

function formatArea(area) {
    return parseFloat(area).toLocaleString() + ' м²';
}

// Экспортируем избранное в глобальную область, чтобы другие бандлы могли переиспользовать их
window.getFavorites = getFavorites;
window.saveFavorites = saveFavorites;
window.isFavorite = isFavorite;
window.toggleFavorite = toggleFavorite;
window.updateFavoriteButtons = updateFavoriteButtons;
window.updateFavoritesCounter = updateFavoritesCounter;
window.initializeFavorites = initializeFavorites;

// ===== ВАЛИДАЦИЯ ФОРМ =====
function validateForm(form) {
    let isValid = true;

    form.find('input[required], select[required], textarea[required]').each(function () {
        const field = $(this);
        const value = field.val().trim();

        if (!value) {
            field.addClass('is-invalid');
            isValid = false;
        } else {
            field.removeClass('is-invalid').addClass('is-valid');
        }
    });

    // Валидация email
    const emailField = form.find('input[type="email"]');
    if (emailField.length && emailField.val()) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(emailField.val())) {
            emailField.addClass('is-invalid');
            isValid = false;
        }
    }
}
