function getMapUiElements() {
    return {
        overlay: document.getElementById('map-status-overlay'),
        spinner: document.getElementById('map-status-spinner'),
        icon: document.getElementById('map-status-icon'),
        title: document.getElementById('map-status-title'),
        text: document.getElementById('map-status-text'),
        summary: document.getElementById('map-results-summary'),
        summaryText: document.getElementById('map-results-summary-text'),
        refreshButton: document.getElementById('map-refresh-button'),
        resetButton: document.getElementById('map-reset-view-button'),
    };
}

let mapBoundsRefreshTimer = null;
let lastLoadedMapBounds = null;

function isBoundsBasedMapLoadingEnabled() {
    return window.mapConfig?.enableBoundsBasedLoading === true;
}

function getMapBoundsRefreshDelay() {
    const configuredDelay = Number(window.mapConfig?.boundsRefreshDebounceMs);
    return Number.isFinite(configuredDelay) && configuredDelay >= 0 ? configuredDelay : 550;
}

function appendMapBoundsParams(params) {
    if (!isBoundsBasedMapLoadingEnabled()) {
        return null;
    }

    const bounds = window.propertiesMapBridge?.getBoundsParams?.();
    if (!bounds) {
        return null;
    }

    Object.entries(bounds).forEach(([key, value]) => {
        if (Number.isFinite(Number(value))) {
            params.set(key, value);
        }
    });

    return bounds;
}

function boundsContain(container, inner) {
    if (!container || !inner) {
        return false;
    }

    return (
        Number(container.bounds_north) >= Number(inner.bounds_north) &&
        Number(container.bounds_south) <= Number(inner.bounds_south) &&
        Number(container.bounds_east) >= Number(inner.bounds_east) &&
        Number(container.bounds_west) <= Number(inner.bounds_west)
    );
}

function setMapStatus(mode, summaryCount = null) {
    const ui = getMapUiElements();
    if (!ui.overlay || !ui.title || !ui.text || !ui.summary || !ui.summaryText) {
        return;
    }

    const translations = window.djangoTranslations || {};

    const states = {
        loading: {
            title: translations.mapLoadingTitle || 'Loading map',
            text: translations.mapLoadingText || 'Loading properties on the map.',
            showOverlay: true,
            showSpinner: true,
            showIcon: false,
        },
        empty: {
            title: translations.mapEmptyTitle || 'No properties on the map',
            text: translations.mapEmptyText || 'Try relaxing filters or switching back to the list.',
            showOverlay: true,
            showSpinner: false,
            showIcon: true,
        },
        error: {
            title: translations.mapErrorTitle || 'Could not update the map',
            text: translations.mapErrorText || 'Please refresh the page or try different filters.',
            showOverlay: true,
            showSpinner: false,
            showIcon: true,
        },
        ready: {
            title: '',
            text: '',
            showOverlay: false,
            showSpinner: false,
            showIcon: false,
        },
    };

    const state = states[mode] || states.ready;

    ui.overlay.classList.toggle('hidden', !state.showOverlay);
    ui.spinner.classList.toggle('hidden', !state.showSpinner);
    ui.icon.classList.toggle('hidden', !state.showIcon);
    ui.title.textContent = state.title;
    ui.text.textContent = state.text;

    if (typeof summaryCount === 'number') {
        ui.summaryText.textContent = `${translations.mapResultsSummary || 'Objects on map'}: ${summaryCount}`;
        ui.summary.classList.toggle('hidden', summaryCount <= 0);
    } else if (mode !== 'ready') {
        ui.summary.classList.add('hidden');
    }
}

window.setMapStatus = setMapStatus;

document.addEventListener('DOMContentLoaded', () => {
    const ui = getMapUiElements();

    if (ui.refreshButton) {
        ui.refreshButton.addEventListener('click', () => {
            updateMapMarkers();
        });
    }

    if (ui.resetButton) {
        ui.resetButton.addEventListener('click', () => {
            if (window.propertiesMapBridge?.resetView) {
                window.propertiesMapBridge.resetView();
            }
        });
    }
});

document.addEventListener('catalog-map:ready', () => {
    const ui = getMapUiElements();
    if (!ui.summary || !ui.summaryText) {
        return;
    }

    if (ui.summary.classList.contains('hidden')) {
        setMapStatus('ready');
    }
});

document.addEventListener('catalog-map:error', () => {
    setMapStatus('error');
});

function collectMapFilterParams() {
    const form = document.getElementById('filter-form');
    const params = new URLSearchParams();

    if (!form) {
        return params;
    }

    const formData = new FormData(form);

    for (const [key, value] of formData.entries()) {
        if (typeof value === 'string' && value !== '') {
            params.append(key, value);
        }
    }

    return params;
}

function setMapProperties(properties, options = {}) {
    if (!window.propertiesMapBridge) {
        return;
    }

    window.propertiesMapBridge.setProperties(properties, options);
}

function updateMapMarkers(options = {}) {
    const endpoint = window.djangoUrls?.mapPropertiesJson;
    if (!endpoint) {
        setMapStatus('error');
        return;
    }

    const {
        fit = true,
        includeBounds = true,
        showLoading = true,
    } = options;
    const params = collectMapFilterParams();
    const requestedBounds = includeBounds ? appendMapBoundsParams(params) : null;

    if (showLoading) {
        setMapStatus('loading');
    }

    fetch(`${endpoint}?${params.toString()}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then((response) => response.json())
        .then((data) => {
            if (!data.success) {
                console.error('Error loading map properties:', data.error);
                loadCurrentPageProperties(true);
                return;
            }

            const properties = data.properties || [];
            setMapProperties(properties, { fit });
            lastLoadedMapBounds = requestedBounds || null;
            setMapStatus(properties.length ? 'ready' : 'empty', properties.length);
        })
        .catch((error) => {
            console.error('Map properties request failed:', error);
            loadCurrentPageProperties(true);
        });
}

document.addEventListener('catalog-map:bounds-changed', () => {
    if (!isBoundsBasedMapLoadingEnabled()) {
        return;
    }

    const visibleBounds = window.propertiesMapBridge?.getBoundsParams?.({ padded: false });
    if (boundsContain(lastLoadedMapBounds, visibleBounds)) {
        return;
    }

    window.clearTimeout(mapBoundsRefreshTimer);
    mapBoundsRefreshTimer = window.setTimeout(() => {
        updateMapMarkers({
            fit: false,
            includeBounds: true,
            showLoading: false,
        });
    }, getMapBoundsRefreshDelay());
});

function loadCurrentPageProperties(fromError = false) {
    const propertyCards = document.querySelectorAll('.property-card');
    const properties = [];

    propertyCards.forEach((card) => {
        let lat = parseFloat(card.dataset.latitude);
        let lng = parseFloat(card.dataset.longitude);

        if (Number.isNaN(lat) || Number.isNaN(lng)) {
            lat = parseFloat((card.dataset.latitude || '').replace(',', '.'));
            lng = parseFloat((card.dataset.longitude || '').replace(',', '.'));
        }

        if (Number.isNaN(lat) || Number.isNaN(lng)) {
            return;
        }

        const propertyId = card.dataset.propertyId;
        const title = card.dataset.title || 'Property';
        const propertyType = card.dataset.propertyType || '';
        const dealType = card.dataset.dealType || '';
        const location = card.dataset.location || '';
        const link = card.dataset.url || '#';
        const mainImage = card.dataset.mainImage || window.djangoUrls?.noImageSvg || '';
        const bedrooms = card.dataset.bedrooms || '';
        const bathrooms = card.dataset.bathrooms || '';
        const area = card.dataset.area || '';

        const priceElement = card.querySelector(`[class*="card-price-${propertyId}"]`);
        const currencyElement = card.querySelector(`[class*="current-currency-code-${propertyId}"]`);
        const price = priceElement ? priceElement.textContent.trim() : '';
        const currency = currencyElement ? currencyElement.textContent.trim() : '';
        const formattedPrice = price && currency ? `${price} ${currency}` : price;

        properties.push({
            id: propertyId,
            title,
            slug: card.dataset.slug || '',
            lat,
            lng,
            property_type: propertyType,
            property_type_label: card.dataset.propertyTypeLabel || propertyType,
            deal_type: dealType,
            price: formattedPrice || window.djangoTranslations?.priceOnRequest,
            location,
            url: link,
            image_url: mainImage,
            bedrooms,
            bathrooms,
            area,
            agent_phone: card.dataset.agentPhone || '+66633033133',
        });
    });

    setMapProperties(properties);
    setMapStatus(properties.length ? 'ready' : (fromError ? 'error' : 'empty'), properties.length);
}
