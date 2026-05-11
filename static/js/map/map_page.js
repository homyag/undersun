(function () {
    const MAP_DEFAULT_CENTER = [98.3923, 7.8804];
    const FILTER_SUBMIT_DELAY = 400;
    const PRICE_FILTER_SUBMIT_DELAY = 800;

    let geolocateMarker = null;
    let mapReady = false;
    let propertiesLoaded = false;

    function getMapLoadingElement() {
        return document.getElementById('map-loading');
    }

    function setMapLoadingMessage(message) {
        const loadingElement = getMapLoadingElement();
        const textElement = loadingElement?.querySelector('p');
        if (textElement && message) {
            textElement.textContent = message;
        }
    }

    function showMapLoading(message) {
        const loadingElement = getMapLoadingElement();
        if (!loadingElement) {
            return;
        }

        if (message) {
            setMapLoadingMessage(message);
        }
        loadingElement.style.display = 'flex';
    }

    function hideMapLoading() {
        const loadingElement = getMapLoadingElement();
        if (!loadingElement) {
            return;
        }

        loadingElement.style.display = 'none';
    }

    function updateStats(properties) {
        const visible = properties.length;
        const sale = properties.filter((property) => property.deal_type === 'sale' || property.deal_type === 'both').length;
        const rent = properties.filter((property) => property.deal_type === 'rent' || property.deal_type === 'both').length;

        setText('map-visible-count', visible);
        setText('map-visible-sale', sale);
        setText('map-visible-rent', rent);
        setText('map-toolbar-visible', visible);
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    function getMapPropertiesUrl() {
        const endpoint = window.djangoUrls?.mapPropertiesJson;
        if (!endpoint) {
            return null;
        }

        const url = new URL(endpoint, window.location.origin);
        const currentParams = new URLSearchParams(window.location.search);
        currentParams.delete('page');
        url.search = currentParams.toString();
        return url.toString();
    }

    async function fetchMapProperties() {
        const url = getMapPropertiesUrl();
        if (!url) {
            return [];
        }

        const response = await fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        });

        if (!response.ok) {
            throw new Error(`Map properties request failed: ${response.status}`);
        }

        const payload = await response.json();
        if (!payload?.success || !Array.isArray(payload.properties)) {
            throw new Error('Invalid map properties payload');
        }

        return payload.properties;
    }

    function refreshMapFromPayload(properties) {
        if (!window.propertiesMapBridge) {
            return;
        }

        window.propertiesMapBridge.setProperties(properties);
        updateStats(properties);
    }

    function syncMapReadyState() {
        if (mapReady && propertiesLoaded) {
            hideMapLoading();
        }
    }

    async function loadMapProperties() {
        propertiesLoaded = false;
        showMapLoading(window.djangoTranslations?.mapLoadingText || '');

        try {
            const properties = await fetchMapProperties();
            refreshMapFromPayload(properties);
            propertiesLoaded = true;
            syncMapReadyState();
        } catch (error) {
            console.error('Failed to load map properties:', error);
            setMapLoadingMessage(window.djangoTranslations?.mapErrorText || 'Unable to load map');
        }
    }

    function locateUser() {
        if (!navigator.geolocation) {
            showNotification(window.i18nGeoUnsupported || 'Geolocation is not supported');
            return;
        }

        navigator.geolocation.getCurrentPosition((position) => {
            const map = window.propertiesMapBridge?.getMap();
            if (!map || typeof maplibregl === 'undefined') {
                return;
            }

            const lngLat = [position.coords.longitude, position.coords.latitude];
            map.easeTo({
                center: lngLat,
                zoom: 13,
                duration: 700,
            });

            if (geolocateMarker) {
                geolocateMarker.remove();
            }

            geolocateMarker = new maplibregl.Marker({
                color: '#F1B400',
            }).setLngLat(lngLat).addTo(map);
        }, () => {
            showNotification(window.i18nGeoFailed || 'Unable to determine your position');
        });
    }

    function bindFloatingButtons() {
        document.getElementById('geoLocateBtn')?.addEventListener('click', locateUser);
        document.getElementById('resetViewBtn')?.addEventListener('click', () => {
            window.propertiesMapBridge?.resetView();
        });
    }

    function initMapFilterForm() {
        const form = document.getElementById('filter-form');
        if (!form) {
            return;
        }

        const inputs = Array.from(form.querySelectorAll('input, select'));
        inputs.forEach((input) => {
            if (input.name === 'sort' || input.name === 'current_property_type') {
                return;
            }

            const eventName = (input.type === 'checkbox' || input.type === 'radio' || input.tagName === 'SELECT')
                ? 'change'
                : 'input';

            input.addEventListener(eventName, () => {
                clearTimeout(input._mapFilterTimeout);
                const delay = (input.name === 'min_price' || input.name === 'max_price')
                    ? PRICE_FILTER_SUBMIT_DELAY
                    : FILTER_SUBMIT_DELAY;

                input._mapFilterTimeout = setTimeout(() => {
                    form.submit();
                }, delay);
            });
        });

        const districtSelect = document.getElementById('district-select');
        const locationSelect = document.getElementById('location-select');
        if (!districtSelect || !locationSelect) {
            return;
        }

        const defaultOption = locationSelect.querySelector('option[value=""]');
        const defaultLabel = defaultOption?.textContent || window.djangoTranslations?.allLocations || 'All locations';

        districtSelect.addEventListener('change', () => {
            const districtSlug = districtSelect.value;
            locationSelect.innerHTML = `<option value="">${defaultLabel}</option>`;

            if (!districtSlug) {
                form.submit();
                return;
            }

            const endpoint = window.djangoUrls?.getLocationsForDistrict;
            if (!endpoint) {
                form.submit();
                return;
            }

            fetch(`${endpoint}?district=${encodeURIComponent(districtSlug)}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
                .then((response) => response.json())
                .then((payload) => {
                    if (!payload?.success || !Array.isArray(payload.locations)) {
                        return;
                    }

                    payload.locations.forEach((location) => {
                        const option = document.createElement('option');
                        option.value = location.slug;
                        option.textContent = location.name;
                        locationSelect.appendChild(option);
                    });
                })
                .catch((error) => {
                    console.error('Failed to load locations for district:', error);
                })
                .finally(() => {
                    form.submit();
                });
        });
    }

    function showNotification(message) {
        if (!message) {
            return;
        }

        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 bg-primary text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-all duration-300 transform translate-x-full';
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => notification.classList.remove('translate-x-full'), 40);
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => notification.remove(), 300);
        }, 2500);
    }

    function syncFavoriteIcons() {
        const favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
        document.querySelectorAll('[id^="favorite-"]').forEach((icon) => {
            const propertyId = parseInt(icon.id.replace('favorite-', ''), 10);
            const isFavorite = favorites.includes(propertyId);
            icon.classList.toggle('fas', isFavorite);
            icon.classList.toggle('far', !isFavorite);
        });
    }

    function initializeMapPage() {
        if (!window.propertiesMapBridge) {
            return;
        }

        showMapLoading(window.djangoTranslations?.mapLoadingText || '');
        window.propertiesMapBridge.initialize('property-map');
        bindFloatingButtons();
        initMapFilterForm();
        syncFavoriteIcons();
        loadMapProperties();
    }

    document.addEventListener('catalog-map:ready', () => {
        mapReady = true;
        syncMapReadyState();
    });

    document.addEventListener('catalog-map:error', () => {
        setMapLoadingMessage(window.djangoTranslations?.mapErrorText || 'Unable to load map');
        showMapLoading();
    });

    window.addEventListener('resize', () => {
        window.propertiesMapBridge?.refreshSize();
    });

    window.addEventListener('currencyChanged', () => {
        loadMapProperties();
    });

    document.addEventListener('DOMContentLoaded', initializeMapPage);

    if (typeof window.toggleFavorite !== 'function') {
        window.toggleFavorite = function toggleFavorite(propertyId) {
            let favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
            if (favorites.includes(propertyId)) {
                favorites = favorites.filter((id) => id !== propertyId);
                showNotification(window.djangoTranslations?.favoriteRemoved || 'Removed from favorites');
            } else {
                favorites.push(propertyId);
                showNotification(window.djangoTranslations?.favoriteAdded || 'Added to favorites');
            }
            localStorage.setItem('favorites', JSON.stringify(favorites));
            syncFavoriteIcons();
        };
    }

    window.syncFavoriteIcons = syncFavoriteIcons;

    window.mapPageBridge = {
        refresh: loadMapProperties,
        locateUser,
        resetView() {
            window.propertiesMapBridge?.resetView();
        },
    };
})();
