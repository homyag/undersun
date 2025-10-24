/**
 * Favorites Page JavaScript
 * Управление страницей избранного с поддержкой двух режимов просмотра:
 * - Сетка карточек
 * - Таблица сравнения
 */

let currentProperties = []; // Глобальное хранилище для свойств
let currentView = localStorage.getItem('favoritesView') || 'grid'; // Текущий вид: 'grid' или 'table'

$(document).ready(function() {
    // Восстанавливаем состояние кнопок при загрузке
    updateViewButtons();

    loadFavoritesPage();

    // Обработчик очистки избранного
    $('#clear-favorites').on('click', function() {
        if (confirm(TRANSLATIONS.confirmClearFavorites)) {
            clearAllFavorites();
        }
    });

    // Обработчик удаления отдельных объектов
    $(document).on('click', '.remove-favorite', function() {
        const propertyId = $(this).data('property-id');
        toggleFavorite(propertyId);
        loadFavoritesPage(); // Перезагружаем страницу
    });

    // Обработчики переключения вида
    $('#grid-view-btn').on('click', function() {
        switchView('grid');
    });

    $('#table-view-btn').on('click', function() {
        switchView('table');
    });

    // Обработчик смены валюты
    window.addEventListener('currencyChanged', function() {
        // Перезагружаем избранное с новыми ценами
        loadFavoritesPage();
    });
});

/**
 * Загружает страницу избранного
 */
function loadFavoritesPage() {
    const favorites = getFavorites();
    const container = $('#favorites-container');
    const emptyState = $('#empty-favorites');
    const clearButton = $('#clear-favorites');
    const totalCount = $('#total-favorites-count');

    totalCount.text(favorites.length);

    if (favorites.length === 0) {
        container.hide();
        emptyState.show();
        clearButton.hide();
        return;
    }

    container.show();
    emptyState.hide();
    clearButton.show();

    // Загружаем данные об объектах
    loadFavoriteProperties(favorites);
}

/**
 * Загружает данные объектов из избранного через AJAX
 */
function loadFavoriteProperties(favoriteIds) {
    if (favoriteIds.length === 0) return;

    // Показываем загрузку
    $('#favorites-container').html(`
        <div class="text-center py-8">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
            <p class="mt-2 text-gray-600">${TRANSLATIONS.loadingFavorites}</p>
        </div>
    `);

    // AJAX запрос для получения данных объектов
    $.ajax({
        url: URLS.getFavoriteProperties,
        type: 'GET',
        dataType: 'json',
        cache: false,
        data: {
            'property_ids[]': favoriteIds
        },
        success: function(response) {
            if (response.success) {
                displayFavoriteProperties(response.properties);
            } else {
                showError();
            }
        },
        error: function(xhr, status, error) {
            showError();
        }
    });
}

/**
 * Отображает избранные объекты в выбранном виде
 */
function displayFavoriteProperties(properties) {
    // Сохраняем данные глобально
    currentProperties = properties;

    // Отображаем в зависимости от выбранного режима
    if (currentView === 'grid') {
        displayGridView(properties);
    } else {
        displayTableView(properties);
    }
}

/**
 * Отображает объекты в виде сетки карточек
 */
function displayGridView(properties) {
    const container = $('#favorites-container');

    if (properties.length === 0) {
        container.html(`<div class="text-center py-8"><p class="text-gray-600">${TRANSLATIONS.noFavorites}</p></div>`);
        return;
    }

    let html = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">';

    properties.forEach(property => {
        html += `
            <div class="bg-white rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden group flex flex-col h-full property-card">
                <div class="relative flex-shrink-0">
                    <img src="${property.main_image_url || '/static/images/no-image.jpg'}"
                         class="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-300"
                         alt="${property.title}" loading="lazy">

                    <!-- Remove Button -->
                    <button class="absolute top-3 right-3 bg-red-500 hover:bg-red-600 text-white w-8 h-8 flex items-center justify-center rounded-full transition-all duration-200 remove-favorite shadow-lg"
                            data-property-id="${property.id}" title="${TRANSLATIONS.removeFromFavorites}">
                        <i class="fas fa-times text-sm"></i>
                    </button>

                    <!-- Deal Type Badge -->
                    <div class="absolute top-3 left-3">
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${property.deal_type === 'sale' ? 'bg-accent text-gray-900' : 'bg-primary text-white'} shadow-sm">
                            ${property.deal_type === 'sale' ? TRANSLATIONS.sale : TRANSLATIONS.rent}
                        </span>
                    </div>
                </div>

                <div class="p-6 flex flex-col flex-grow">
                    <h3 class="font-bold text-lg text-primary mb-3 leading-tight min-h-[3.5rem]">
                        <a href="/property/${property.slug}/" class="hover:text-accent transition-colors">
                            ${property.title.length > 50 ? property.title.substring(0, 50) + '...' : property.title}
                        </a>
                    </h3>

                    <div class="text-tertiary mb-4 flex items-center font-medium">
                        <i class="fas fa-map-marker-alt mr-2 text-accent"></i>
                        ${property.district_name}
                    </div>

                    <div class="flex justify-between items-center mb-4 flex-grow">
                        <div class="text-2xl font-bold text-accent">
                            ${property.price_display}
                        </div>
                        <div>
                            <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-primary text-white">
                                ${property.property_type_name}
                            </span>
                        </div>
                    </div>

                    <a href="/property/${property.slug}/" class="block w-full text-center bg-accent hover:bg-yellow-500 text-gray-900 py-3 px-6 rounded-lg transition-colors font-bold shadow-md hover:shadow-lg mt-auto">
                        ${TRANSLATIONS.viewDetails}
                    </a>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.html(html);
}

/**
 * Отображает объекты в виде таблицы сравнения
 */
function displayTableView(properties) {
    const container = $('#favorites-container');

    if (properties.length === 0) {
        container.html(`<div class="text-center py-8"><p class="text-gray-600">${TRANSLATIONS.noFavorites}</p></div>`);
        return;
    }

    let html = `
        <div class="bg-white rounded-xl shadow-lg overflow-hidden">
            <div class="overflow-x-auto">
                <table class="w-full comparison-table">
                    <thead>
                        <tr class="bg-primary text-white">
                            <th class="sticky left-0 bg-primary z-10 px-6 py-4 text-left font-semibold">${TRANSLATIONS.characteristic}</th>
    `;

    // Заголовки колонок с объектами
    properties.forEach(property => {
        html += `
            <th class="px-6 py-4 min-w-[250px] relative">
                <div class="flex flex-col items-center">
                    <button class="absolute top-2 right-2 text-red-400 hover:text-red-600 remove-favorite"
                            data-property-id="${property.id}" title="${TRANSLATIONS.removeFromFavorites}">
                        <i class="fas fa-times-circle text-xl"></i>
                    </button>
                    <img src="${property.main_image_url || '/static/images/no-image.jpg'}"
                         class="w-full h-32 object-cover rounded-lg mb-3"
                         alt="${property.title}">
                    <a href="/property/${property.slug}/" class="text-sm font-semibold hover:text-accent transition-colors text-center">
                        ${property.title.length > 40 ? property.title.substring(0, 40) + '...' : property.title}
                    </a>
                </div>
            </th>
        `;
    });

    html += `
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
    `;

    // Ряды с характеристиками
    const rows = [
        {
            label: TRANSLATIONS.price,
            icon: 'fas fa-tag',
            getValue: (p) => p.price_display || TRANSLATIONS.notSpecified
        },
        {
            label: TRANSLATIONS.pricePerSqm,
            icon: 'fas fa-calculator',
            getValue: (p) => {
                if (p.deal_type === 'rent') {
                    return `<span class="text-gray-400">${TRANSLATIONS.onlyForSale}</span>`;
                }
                if (p.price_per_sqm) {
                    return `${p.currency_symbol}${p.price_per_sqm.toLocaleString('ru-RU', {maximumFractionDigits: 0})}/м²`;
                }
                return TRANSLATIONS.notSpecified;
            }
        },
        {
            label: TRANSLATIONS.propertyType,
            icon: 'fas fa-building',
            getValue: (p) => p.property_type_name || TRANSLATIONS.notSpecified
        },
        {
            label: TRANSLATIONS.dealType,
            icon: 'fas fa-handshake',
            getValue: (p) => {
                if (p.deal_type === 'sale') return TRANSLATIONS.sale;
                if (p.deal_type === 'rent') return TRANSLATIONS.rent;
                if (p.deal_type === 'both') return TRANSLATIONS.saleRent;
                return TRANSLATIONS.notSpecified;
            }
        },
        {
            label: TRANSLATIONS.district,
            icon: 'fas fa-map-marker-alt',
            getValue: (p) => p.district_name || TRANSLATIONS.notSpecified
        },
        {
            label: TRANSLATIONS.bedrooms,
            icon: 'fas fa-bed',
            getValue: (p) => p.bedrooms ? `${p.bedrooms} ${TRANSLATIONS.bedroomsUnit}` : TRANSLATIONS.notSpecified
        },
        {
            label: TRANSLATIONS.bathrooms,
            icon: 'fas fa-bath',
            getValue: (p) => p.bathrooms ? `${p.bathrooms} ${TRANSLATIONS.bathroomsUnit}` : TRANSLATIONS.notSpecified
        },
        {
            label: TRANSLATIONS.totalArea,
            icon: 'fas fa-ruler-combined',
            getValue: (p) => p.area_total ? `${p.area_total} м²` : TRANSLATIONS.notSpecified
        },
        {
            label: TRANSLATIONS.landArea,
            icon: 'fas fa-map',
            getValue: (p) => p.area_land ? `${p.area_land} м²` : TRANSLATIONS.notSpecified
        },
        {
            label: TRANSLATIONS.pool,
            icon: 'fas fa-swimming-pool',
            getValue: (p) => p.pool ? `<span class="text-green-600"><i class="fas fa-check-circle"></i> ${TRANSLATIONS.yes}</span>` : `<span class="text-gray-400"><i class="fas fa-times-circle"></i> ${TRANSLATIONS.no}</span>`
        },
        {
            label: TRANSLATIONS.parking,
            icon: 'fas fa-car',
            getValue: (p) => p.parking ? `<span class="text-green-600"><i class="fas fa-check-circle"></i> ${TRANSLATIONS.yes}</span>` : `<span class="text-gray-400"><i class="fas fa-times-circle"></i> ${TRANSLATIONS.no}</span>`
        },
        {
            label: TRANSLATIONS.furnished,
            icon: 'fas fa-couch',
            getValue: (p) => p.furnished ? `<span class="text-green-600"><i class="fas fa-check-circle"></i> ${TRANSLATIONS.yes}</span>` : `<span class="text-gray-400"><i class="fas fa-times-circle"></i> ${TRANSLATIONS.no}</span>`
        },
        {
            label: TRANSLATIONS.actions,
            icon: 'fas fa-link',
            getValue: (p) => `<a href="/property/${p.slug}/" class="inline-flex items-center justify-center bg-accent hover:bg-yellow-500 text-gray-900 font-bold py-2 px-4 rounded-lg transition-colors w-full"><i class="fas fa-eye mr-2"></i>${TRANSLATIONS.view}</a>`
        }
    ];

    rows.forEach((row, rowIndex) => {
        html += `
            <tr class="${rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}">
                <td class="sticky left-0 ${rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'} z-10 px-6 py-4 font-semibold text-primary">
                    <i class="${row.icon} mr-2 text-accent"></i>${row.label}
                </td>
        `;

        properties.forEach(property => {
            html += `<td class="px-6 py-4 text-center">${row.getValue(property)}</td>`;
        });

        html += `</tr>`;
    });

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    container.html(html);
}

/**
 * Переключает вид отображения (сетка/таблица)
 */
function switchView(view) {
    currentView = view;

    // Сохраняем выбор в localStorage
    localStorage.setItem('favoritesView', view);

    // Обновляем кнопки
    updateViewButtons();

    // Перерисовываем контейнер
    if (currentProperties.length > 0) {
        displayFavoriteProperties(currentProperties);
    }
}

/**
 * Обновляет стили кнопок переключения вида
 */
function updateViewButtons() {
    if (currentView === 'grid') {
        $('#grid-view-btn').addClass('bg-white shadow-sm text-primary font-semibold').removeClass('text-tertiary');
        $('#table-view-btn').removeClass('bg-white shadow-sm text-primary font-semibold').addClass('text-tertiary');
    } else {
        $('#table-view-btn').addClass('bg-white shadow-sm text-primary font-semibold').removeClass('text-tertiary');
        $('#grid-view-btn').removeClass('bg-white shadow-sm text-primary font-semibold').addClass('text-tertiary');
    }
}

/**
 * Показывает сообщение об ошибке
 */
function showError() {
    $('#favorites-container').html(`
        <div class="text-center py-8">
            <i class="fas fa-exclamation-triangle text-red-500 text-4xl mb-4"></i>
            <p class="text-gray-600">${TRANSLATIONS.errorLoadingFavorites}</p>
        </div>
    `);
}

/**
 * Очищает все избранное
 */
function clearAllFavorites() {
    localStorage.removeItem('favorites');
    updateFavoritesCounter();
    loadFavoritesPage();
    showNotification(TRANSLATIONS.favoritesCleared, 'favorite-removed');
}
