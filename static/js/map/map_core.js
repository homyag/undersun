(function () {
    const DEFAULT_CENTER = [98.3923, 7.8804];
    const DEFAULT_ZOOM = 10;
    const SOURCE_ID = 'properties';
    const HOVER_SOURCE_ID = 'property-hover';
    const SELECTED_SOURCE_ID = 'property-selected';
    const HOVER_CLUSTER_SOURCE_ID = 'property-hover-cluster';
    const SPIDER_POINT_SOURCE_ID = 'property-spider-points';
    const SPIDER_LEG_SOURCE_ID = 'property-spider-legs';
    const CLUSTER_GLOW_LAYER_ID = 'property-clusters-glow';
    const CLUSTER_RING_LAYER_ID = 'property-clusters-ring';
    const CLUSTER_LAYER_ID = 'property-clusters';
    const AGGREGATE_GLOW_LAYER_ID = 'property-aggregates-glow';
    const AGGREGATE_RING_LAYER_ID = 'property-aggregates-ring';
    const AGGREGATE_LAYER_ID = 'property-aggregates';
    const AGGREGATE_LABEL_LAYER_ID = 'property-aggregates-label';
    const SPIDER_LEG_LAYER_ID = 'property-spider-legs';
    const POINT_GLOW_LAYER_ID = 'property-points-glow';
    const POINT_RING_LAYER_ID = 'property-points-ring';
    const POINT_LAYER_ID = 'property-points';
    const POINT_ICON_LAYER_ID = 'property-points-icon';
    const SPIDER_POINT_GLOW_LAYER_ID = 'property-spider-points-glow';
    const SPIDER_POINT_RING_LAYER_ID = 'property-spider-points-ring';
    const SPIDER_POINT_LAYER_ID = 'property-spider-points';
    const SPIDER_POINT_ICON_LAYER_ID = 'property-spider-points-icon';
    const HOVER_CLUSTER_LAYER_ID = 'property-clusters-hover';
    const HOVER_POINT_LAYER_ID = 'property-points-hover';
    const SELECTED_POINT_LAYER_ID = 'property-points-selected';
    const DISTRICT_SOURCE_ID = 'districts';
    const DISTRICT_HOVER_SOURCE_ID = 'districts-hover';
    const DISTRICT_FILL_LAYER_ID = 'districts-fill';
    const DISTRICT_OUTLINE_LAYER_ID = 'districts-outline';
    const DISTRICT_HOVER_LAYER_ID = 'districts-hover';
    const DISTRICT_HOVER_OUTLINE_LAYER_ID = 'districts-hover-outline';
    const CLUSTER_INTERACTIVE_LAYER_IDS = [
        CLUSTER_LAYER_ID,
        CLUSTER_RING_LAYER_ID,
        CLUSTER_GLOW_LAYER_ID,
        HOVER_CLUSTER_LAYER_ID,
    ];
    const AGGREGATE_INTERACTIVE_LAYER_IDS = [
        AGGREGATE_LAYER_ID,
        AGGREGATE_RING_LAYER_ID,
        AGGREGATE_GLOW_LAYER_ID,
    ];
    const POINT_INTERACTIVE_LAYER_IDS = [
        SPIDER_POINT_ICON_LAYER_ID,
        POINT_ICON_LAYER_ID,
        SPIDER_POINT_LAYER_ID,
        POINT_LAYER_ID,
    ];
    const DISTRICT_INTERACTIVE_LAYER_IDS = [
        DISTRICT_FILL_LAYER_ID,
        DISTRICT_OUTLINE_LAYER_ID,
        DISTRICT_HOVER_LAYER_ID,
    ];
    const PROPERTY_ICON_NAMES = [
        'property-icon-condo-sale',
        'property-icon-condo-rent',
        'property-icon-condo-both',
        'property-icon-townhouse-sale',
        'property-icon-townhouse-rent',
        'property-icon-townhouse-both',
        'property-icon-villa-sale',
        'property-icon-villa-rent',
        'property-icon-villa-both',
        'property-icon-land-sale',
        'property-icon-land-rent',
        'property-icon-land-both',
        'property-icon-default-sale',
        'property-icon-default-rent',
        'property-icon-default-both',
    ];

    const state = {
        map: null,
        popup: null,
        loaded: false,
        pendingProperties: [],
        aggregateMarkers: [],
        districtMarkers: [],
        lastGeoJson: createEmptyFeatureCollection(),
        districtGeoJson: createEmptyFeatureCollection(),
        hoveredClusterId: null,
        hoveredPropertyId: null,
        hoverCloseTimer: null,
        isPointerOverPopup: false,
        isPinnedPopup: false,
        lastPopupPropertyId: null,
        popupAnchor: null,
        spiderClusterId: null,
        selectedPropertyId: null,
    };
    const POPUP_VIEWPORT_PADDING = 18;
    const SPIDERFY_MAX_POINTS = 24;
    const HOVER_POPUP_CLOSE_DELAY = 180;
    const MARKER_SPREAD_GROUP_RADIUS_PX = 30;
    const MARKER_SPREAD_BASE_RADIUS_PX = 28;
    const MARKER_SPREAD_MAX_RADIUS_PX = 86;

    function getMapConfig() {
        const config = { ...(window.mapConfig || {}) };

        try {
            const params = new URLSearchParams(window.location.search);
            const basemapOverride = params.get('map_basemap');
            if (basemapOverride && (basemapOverride !== 'protomaps-en' || config.protomapsEnabled)) {
                config.currentBasemap = basemapOverride;
            }
        } catch (error) {}

        return config;
    }

    function getMapBehaviorConfig() {
        const config = getMapConfig();
        const hoverMediaQuery = window.matchMedia
            ? window.matchMedia('(hover: hover) and (pointer: fine)')
            : null;

        return {
            enableHoverPopup: config.enableHoverPopup !== false && (!hoverMediaQuery || hoverMediaQuery.matches),
            enableMarkerSpread: config.enableMarkerSpread !== false,
            enablePropertyClusters: config.enablePropertyClusters === true,
            enableBoundsBasedLoading: config.enableBoundsBasedLoading === true,
            boundsPaddingRatio: Number.isFinite(Number(config.boundsPaddingRatio)) ? Number(config.boundsPaddingRatio) : 0.35,
        };
    }

    function isPropertyClusteringEnabled() {
        return getMapBehaviorConfig().enablePropertyClusters;
    }

    function isHoverPopupEnabled() {
        return getMapBehaviorConfig().enableHoverPopup;
    }

    function isBoundsBasedLoadingEnabled() {
        return getMapBehaviorConfig().enableBoundsBasedLoading;
    }

    function getRasterOsmStyle() {
        return {
            version: 8,
            sources: {
                osm: {
                    type: 'raster',
                    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                    tileSize: 256,
                    attribution: '© OpenStreetMap contributors',
                    maxzoom: 19,
                },
            },
            layers: [
                {
                    id: 'osm-raster',
                    type: 'raster',
                    source: 'osm',
                },
            ],
        };
    }

    function ensurePmtilesProtocol() {
        if (typeof maplibregl === 'undefined' || typeof pmtiles === 'undefined') {
            return false;
        }

        if (!window.__undersunPmtilesProtocol) {
            const protocol = new pmtiles.Protocol();
            maplibregl.addProtocol('pmtiles', protocol.tile);
            window.__undersunPmtilesProtocol = protocol;
        }

        return true;
    }

    function getProtomapsBasemapsApi() {
        return window.protomapsBasemaps || window.basemaps || window.protomaps?.basemaps || null;
    }

    function getProtomapsStyle() {
        const config = getMapConfig();
        const protomapsUrl = config.protomapsUrl;
        const protomapsTheme = config.protomapsTheme || 'light';
        const labelLanguage = config.labelLanguage || 'en';
        const basemapsApi = getProtomapsBasemapsApi();

        if (
            !protomapsUrl ||
            !basemapsApi ||
            typeof basemapsApi.layers !== 'function' ||
            typeof basemapsApi.namedFlavor !== 'function' ||
            !ensurePmtilesProtocol()
        ) {
            return null;
        }

        return {
            version: 8,
            glyphs: 'https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf',
            sprite: `https://protomaps.github.io/basemaps-assets/sprites/v4/${protomapsTheme}`,
            sources: {
                protomaps: {
                    type: 'vector',
                    url: `pmtiles://${protomapsUrl}`,
                    attribution: '<a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>',
                },
            },
            layers: basemapsApi.layers(
                'protomaps',
                basemapsApi.namedFlavor(protomapsTheme),
                { lang: labelLanguage }
            ),
        };
    }

    function getBaseMapStyle() {
        const config = getMapConfig();

        if (config.currentBasemap === 'protomaps-en') {
            const protomapsStyle = getProtomapsStyle();
            if (protomapsStyle) {
                return protomapsStyle;
            }
        }

        if (config.currentBasemap === 'style-url') {
            const styleUrl = config.vectorStyleUrl || window.djangoUrls?.mapStyleUrl;
            if (styleUrl) {
                return styleUrl;
            }
        }

        return getRasterOsmStyle();
    }

    function buildDistrictFilterUrl(districtSlug) {
        try {
            const url = new URL(window.location.href);
            url.searchParams.set('district', districtSlug);
            url.searchParams.set('map_view', 'true');
            url.searchParams.delete('location');
            url.searchParams.delete('page');
            return url.toString();
        } catch (error) {
            return window.location.href;
        }
    }

    function clearDistrictMarkers() {
        state.districtMarkers.forEach((marker) => marker.remove());
        state.districtMarkers = [];
    }

    function clearAggregateMarkers() {
        state.aggregateMarkers.forEach((marker) => marker.remove());
        state.aggregateMarkers = [];
    }

    function renderAggregateMarkers(properties) {
        if (!state.map || typeof maplibregl === 'undefined') {
            return;
        }

        clearAggregateMarkers();

        properties
            .filter((property) => property?.is_aggregate === true)
            .forEach((aggregate) => {
                const lat = Number(aggregate.lat);
                const lng = Number(aggregate.lng);
                const count = Number(aggregate.count);
                if (!Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(count)) {
                    return;
                }

                const element = document.createElement('button');
                const size = Math.min(58, Math.max(38, 34 + Math.log10(Math.max(count, 1)) * 14));
                element.type = 'button';
                element.className = 'catalog-map-aggregate-marker';
                element.style.setProperty('--aggregate-marker-size', `${Math.round(size)}px`);
                element.setAttribute('aria-label', `${count}`);
                element.textContent = String(count);
                element.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    state.map.once('zoomend', () => {
                        emitMapEvent('catalog-map:aggregate-selected');
                    });
                    state.map.easeTo({
                        center: [lng, lat],
                        zoom: Math.min(state.map.getZoom() + 2, 15),
                        duration: 500,
                    });
                });

                const marker = new maplibregl.Marker({
                    element,
                    anchor: 'center',
                }).setLngLat([lng, lat]).addTo(state.map);
                state.aggregateMarkers.push(marker);
            });
    }

    function syncDistrictMarkersVisibility() {
        if (!state.map || !state.districtMarkers.length) {
            return;
        }

        const zoom = state.map.getZoom();
        const isVisible = zoom >= 9.5 && zoom <= 12.2;
        state.districtMarkers.forEach((marker) => {
            const element = marker.getElement();
            if (!element) {
                return;
            }

            element.style.opacity = isVisible ? '1' : '0';
            element.style.transform = isVisible ? 'translateY(0)' : 'translateY(6px)';
            element.style.pointerEvents = isVisible ? 'auto' : 'none';
        });
    }

    function renderDistrictMarkers(districts) {
        if (!state.map) {
            return;
        }

        clearDistrictMarkers();

        districts.forEach((district) => {
            if (!district || Number.isNaN(Number(district.lat)) || Number.isNaN(Number(district.lng))) {
                return;
            }

            const element = document.createElement('div');
            element.className = 'map-district-marker';
            element.setAttribute('role', 'button');
            element.setAttribute('tabindex', '0');
            element.setAttribute('title', district.name || '');
            element.innerHTML = `
                <span class="map-district-marker__name">${district.name || ''}</span>
                <span class="map-district-marker__count">${district.properties_count || 0}</span>
            `;

            const targetUrl = buildDistrictFilterUrl(district.slug);
            const navigateToDistrict = () => {
                window.location.href = targetUrl;
            };

            element.addEventListener('click', navigateToDistrict);
            element.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    navigateToDistrict();
                }
            });

            const marker = new maplibregl.Marker({
                element,
                anchor: 'center',
            })
                .setLngLat([Number(district.lng), Number(district.lat)])
                .addTo(state.map);

            state.districtMarkers.push(marker);
        });

        syncDistrictMarkersVisibility();
    }

    function loadDistrictOverlay() {
        const endpoint = window.djangoUrls?.mapDistrictsJson;
        if (!endpoint || typeof fetch === 'undefined') {
            return;
        }

        fetch(endpoint, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`District overlay request failed: ${response.status}`);
                }
                return response.json();
            })
            .then((payload) => {
                if (!payload?.success || !Array.isArray(payload.districts)) {
                    return;
                }

                if (payload.geojson?.type === 'FeatureCollection') {
                    setDistrictsGeoJson(payload.geojson);
                }
                renderDistrictMarkers(payload.districts);
            })
            .catch(() => {});
    }

    function getDealColorExpression() {
        return [
            'match',
            ['get', 'deal_type'],
            'sale', '#10b981',
            'rent', '#3b82f6',
            'both', '#8b5cf6',
            '#F1B400'
        ];
    }

    function getClusterCoreColorExpression() {
        return [
            'step',
            ['get', 'point_count'],
            '#F1B400',
            20, '#d7a108',
            50, '#b88305'
        ];
    }

    function createEmptyFeatureCollection() {
        return {
            type: 'FeatureCollection',
            features: [],
        };
    }

    function getDealHex(dealType) {
        if (dealType === 'rent') {
            return '#3b82f6';
        }
        if (dealType === 'both') {
            return '#8b5cf6';
        }
        return '#10b981';
    }

    function getDealDarkHex(dealType) {
        if (dealType === 'rent') {
            return '#1d4ed8';
        }
        if (dealType === 'both') {
            return '#6d28d9';
        }
        return '#047857';
    }

    function getPropertyTypeKey(propertyType) {
        const normalized = String(propertyType || '').toLowerCase();

        if (normalized.includes('condo') || normalized.includes('apartment') || normalized.includes('кварт')) {
            return 'condo';
        }
        if (normalized.includes('townhouse') || normalized.includes('town house') || normalized.includes('таун')) {
            return 'townhouse';
        }
        if (normalized.includes('villa') || normalized.includes('вилл')) {
            return 'villa';
        }
        if (normalized.includes('land') || normalized.includes('зем')) {
            return 'land';
        }

        return 'default';
    }

    function getPropertyIconName(propertyType, dealType) {
        const typeKey = getPropertyTypeKey(propertyType);
        const dealKey = dealType === 'rent' || dealType === 'both' ? dealType : 'sale';
        return `property-icon-${typeKey}-${dealKey}`;
    }

    function createSvgIconMarkup(type, color, darkColor) {
        const pinColor = '#474b57';
        const pinDarkColor = '#333847';
        return `
            <svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 40 40">
                <defs>
                    <filter id="pinShadow" x="-40%" y="-40%" width="180%" height="180%">
                        <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="${pinDarkColor}" flood-opacity="0.24"/>
                    </filter>
                </defs>
                <circle cx="20" cy="20" r="16" fill="#fff" filter="url(#pinShadow)"/>
                <circle cx="20" cy="20" r="14" fill="#fff" stroke="${pinColor}" stroke-width="3"/>
                <circle cx="20" cy="20" r="10.5" fill="${pinColor}" fill-opacity="0.12"/>
                <path d="M12.5 19.1 20 12.9l7.5 6.2v8.2h-4.7v-5.4h-5.6v5.4h-4.7v-8.2Z" fill="none" stroke="${pinColor}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M10.8 20.1 20 12l9.2 8.1" fill="none" stroke="${pinColor}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `.trim();
    }

    function loadMapImage(map, name, svgMarkup) {
        return new Promise((resolve, reject) => {
        const image = new Image(80, 80);
            image.onload = () => {
                if (!map.hasImage(name)) {
                    map.addImage(name, image, { pixelRatio: 2 });
                }
                resolve();
            };
            image.onerror = reject;
            image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgMarkup)}`;
        });
    }

    async function registerPropertyIcons() {
        if (!state.map) {
            return;
        }

        const jobs = PROPERTY_ICON_NAMES.map((name) => {
            if (state.map.hasImage(name)) {
                return Promise.resolve();
            }

            const [, , type, dealType] = name.split('-');
            return loadMapImage(state.map, name, createSvgIconMarkup(type, getDealHex(dealType), getDealDarkHex(dealType)));
        });

        await Promise.all(jobs);
    }

    function createPopup({ anchor = 'bottom' } = {}) {
        if (state.popup && state.popupAnchor !== anchor) {
            state.popup.remove();
            state.popup = null;
            state.popupAnchor = null;
        }

        if (!state.popup) {
            state.popup = new maplibregl.Popup({
                anchor,
                closeButton: true,
                closeOnClick: false,
                maxWidth: '320px',
                offset: 18,
                focusAfterOpen: false,
            });
            state.popupAnchor = anchor;

            state.popup.on('close', () => {
                clearHoverPopupTimer();
                state.hoveredPropertyId = null;
                state.isPointerOverPopup = false;
                state.isPinnedPopup = false;
                state.lastPopupPropertyId = null;
                state.popupAnchor = null;
                setSelectedFeature(null);
            });
        }

        return state.popup;
    }

    function clearHoverPopupTimer() {
        if (state.hoverCloseTimer) {
            window.clearTimeout(state.hoverCloseTimer);
            state.hoverCloseTimer = null;
        }
    }

    function closePropertyPopup({ clearPinned = false } = {}) {
        clearHoverPopupTimer();

        if (clearPinned) {
            state.isPinnedPopup = false;
        }

        state.hoveredPropertyId = null;
        state.isPointerOverPopup = false;
        state.lastPopupPropertyId = null;

        if (state.popup && state.popup.isOpen() && (!state.isPinnedPopup || clearPinned)) {
            state.popup.remove();
        }

        if (clearPinned) {
            setSelectedFeature(null);
        }
    }

    function scheduleHoverPopupClose() {
        clearHoverPopupTimer();

        if (state.isPinnedPopup) {
            return;
        }

        state.hoverCloseTimer = window.setTimeout(() => {
            if (!state.hoveredPropertyId && !state.isPointerOverPopup) {
                closePropertyPopup();
            }
        }, HOVER_POPUP_CLOSE_DELAY);
    }

    function bindPopupHoverGuards(popup) {
        requestAnimationFrame(() => {
            const popupElement = popup.getElement();
            if (!popupElement) {
                return;
            }

            if (popupElement.dataset.popupInteractionGuardsBound !== 'true') {
                popupElement.dataset.popupInteractionGuardsBound = 'true';

                const handlePopupWheel = (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                };

                ['wheel', 'mousewheel', 'DOMMouseScroll'].forEach((eventName) => {
                    popupElement.addEventListener(eventName, handlePopupWheel, { passive: false });
                });

                popupElement.addEventListener('touchmove', (event) => {
                    event.stopPropagation();
                }, { passive: true });

                ['pointerdown', 'mousedown', 'touchstart'].forEach((eventName) => {
                    popupElement.addEventListener(eventName, (event) => {
                        event.stopPropagation();
                    });
                });
            }

            if (isHoverPopupEnabled() && popupElement.dataset.hoverGuardsBound !== 'true') {
                popupElement.dataset.hoverGuardsBound = 'true';
                popupElement.addEventListener('mouseenter', () => {
                    state.isPointerOverPopup = true;
                    clearHoverPopupTimer();
                });
                popupElement.addEventListener('mouseleave', () => {
                    state.isPointerOverPopup = false;
                    scheduleHoverPopupClose();
                });
            }
        });
    }

    function getPopupAnchor(coordinates) {
        if (!state.map || !coordinates) {
            return 'bottom';
        }

        const container = state.map.getContainer();
        if (!container) {
            return 'bottom';
        }

        const point = state.map.project(coordinates);
        const popupWidth = Math.min(320, Math.max(240, container.clientWidth - POPUP_VIEWPORT_PADDING * 2));
        const estimatedHeight = Math.min(430, Math.max(280, container.clientHeight * 0.72));
        const spaceAbove = point.y - POPUP_VIEWPORT_PADDING - 18;
        const spaceBelow = container.clientHeight - point.y - POPUP_VIEWPORT_PADDING - 18;
        const verticalAnchor = spaceAbove >= estimatedHeight || spaceAbove > spaceBelow ? 'bottom' : 'top';
        const halfWidth = popupWidth / 2;

        let horizontalAnchor = '';
        if (point.x < halfWidth + POPUP_VIEWPORT_PADDING) {
            horizontalAnchor = 'left';
        } else if (point.x > container.clientWidth - halfWidth - POPUP_VIEWPORT_PADDING) {
            horizontalAnchor = 'right';
        }

        return horizontalAnchor ? `${verticalAnchor}-${horizontalAnchor}` : verticalAnchor;
    }

    function updatePopupLayoutState(popup, { pinned = false, coordinates = null, anchor = 'bottom' } = {}) {
        if (!state.map || !popup) {
            return;
        }

        const popupElement = popup.getElement();
        const container = state.map.getContainer();
        if (!popupElement || !container) {
            return;
        }

        popupElement.classList.add('property-map-popup');
        popupElement.classList.toggle('property-map-popup--hover', !pinned);
        popupElement.classList.toggle('property-map-popup--pinned', pinned);
        popupElement.style.setProperty('--property-map-popup-shift-x', '0px');
        popupElement.style.setProperty('--property-map-popup-shift-y', '0px');
    }

    function clampPopupToMapFrame(popup) {
        if (!state.map || !popup) {
            return;
        }

        const popupElement = popup.getElement();
        const container = state.map.getContainer();
        if (!popupElement || !container) {
            return;
        }

        popupElement.style.setProperty('--property-map-popup-shift-x', '0px');
        popupElement.style.setProperty('--property-map-popup-shift-y', '0px');

        const popupRect = popupElement.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const minLeft = containerRect.left + POPUP_VIEWPORT_PADDING;
        const maxRight = containerRect.right - POPUP_VIEWPORT_PADDING;
        const minTop = containerRect.top + POPUP_VIEWPORT_PADDING;
        const maxBottom = containerRect.bottom - POPUP_VIEWPORT_PADDING;

        let shiftX = 0;
        let shiftY = 0;

        if (popupRect.left < minLeft) {
            shiftX = minLeft - popupRect.left;
        } else if (popupRect.right > maxRight) {
            shiftX = maxRight - popupRect.right;
        }

        const shiftedLeft = popupRect.left + shiftX;
        const shiftedRight = popupRect.right + shiftX;
        if (shiftedLeft < minLeft) {
            shiftX += minLeft - shiftedLeft;
        } else if (shiftedRight > maxRight) {
            shiftX += maxRight - shiftedRight;
        }

        if (popupRect.top < minTop) {
            shiftY = minTop - popupRect.top;
        } else if (popupRect.bottom > maxBottom) {
            shiftY = maxBottom - popupRect.bottom;
        }

        const shiftedTop = popupRect.top + shiftY;
        const shiftedBottom = popupRect.bottom + shiftY;
        if (shiftedTop < minTop) {
            shiftY += minTop - shiftedTop;
        } else if (shiftedBottom > maxBottom) {
            shiftY += maxBottom - shiftedBottom;
        }

        popupElement.style.setProperty('--property-map-popup-shift-x', `${Math.round(shiftX)}px`);
        popupElement.style.setProperty('--property-map-popup-shift-y', `${Math.round(shiftY)}px`);
    }

    function getPopupMaxWidth() {
        if (!state.map) {
            return '320px';
        }

        const containerWidth = state.map.getContainer().clientWidth || 0;
        const safeWidth = Math.max(240, Math.min(320, containerWidth - POPUP_VIEWPORT_PADDING * 2));
        return `${safeWidth}px`;
    }

    function emitMapEvent(name, detail = {}) {
        document.dispatchEvent(new CustomEvent(name, { detail }));
    }

    function getStablePropertySortKey(property) {
        const id = String(property?.id || '');
        const slug = String(property?.slug || '');
        return `${id.padStart(12, '0')}:${slug}`;
    }

    function getSpreadRadius(pointCount) {
        if (pointCount <= 2) {
            return 26;
        }
        if (pointCount <= 4) {
            return 34;
        }
        if (pointCount <= 8) {
            return 44;
        }

        return Math.min(MARKER_SPREAD_MAX_RADIUS_PX, MARKER_SPREAD_BASE_RADIUS_PX + pointCount * 3);
    }

    function getSpreadOffset(index, pointCount) {
        if (pointCount <= 10) {
            const angle = (-Math.PI / 2) + (index / pointCount) * Math.PI * 2;
            const radius = getSpreadRadius(pointCount);
            return {
                x: Math.cos(angle) * radius,
                y: Math.sin(angle) * radius,
            };
        }

        const angle = (-Math.PI / 2) + index * 0.92;
        const radius = Math.min(
            MARKER_SPREAD_MAX_RADIUS_PX,
            MARKER_SPREAD_BASE_RADIUS_PX + Math.floor(index / 6) * 18
        );

        return {
            x: Math.cos(angle) * radius,
            y: Math.sin(angle) * radius,
        };
    }

    function groupProjectedProperties(entries) {
        const groups = [];
        const visited = new Set();
        const cellSize = MARKER_SPREAD_GROUP_RADIUS_PX;
        const grid = new Map();

        entries.forEach((entry, index) => {
            entry.index = index;
            const cellX = Math.floor(entry.point.x / cellSize);
            const cellY = Math.floor(entry.point.y / cellSize);
            entry.cellX = cellX;
            entry.cellY = cellY;
            const key = `${cellX}:${cellY}`;
            if (!grid.has(key)) {
                grid.set(key, []);
            }
            grid.get(key).push(entry);
        });

        entries.forEach((entry) => {
            if (visited.has(entry.index)) {
                return;
            }

            const group = [entry];
            visited.add(entry.index);

            for (let dx = -1; dx <= 1; dx += 1) {
                for (let dy = -1; dy <= 1; dy += 1) {
                    const candidates = grid.get(`${entry.cellX + dx}:${entry.cellY + dy}`) || [];
                    candidates.forEach((candidate) => {
                        if (visited.has(candidate.index)) {
                            return;
                        }

                        const distance = Math.hypot(candidate.point.x - entry.point.x, candidate.point.y - entry.point.y);
                        if (distance <= MARKER_SPREAD_GROUP_RADIUS_PX) {
                            visited.add(candidate.index);
                            group.push(candidate);
                        }
                    });
                }
            }

            groups.push(group);
        });

        return groups;
    }

    function prepareDisplayCoordinates(properties) {
        const behavior = getMapBehaviorConfig();
        const prepared = properties.map((property) => {
            const lat = parseFloat(property.lat);
            const lng = parseFloat(property.lng);

            return {
                ...property,
                lat,
                lng,
                original_lat: property.original_lat ?? lat,
                original_lng: property.original_lng ?? lng,
                map_lat: lat,
                map_lng: lng,
            };
        });

        if (!behavior.enableMarkerSpread || !state.map) {
            return prepared;
        }

        const entries = prepared.map((property) => ({
            property,
            point: state.map.project([property.lng, property.lat]),
        })).sort((a, b) => getStablePropertySortKey(a.property).localeCompare(getStablePropertySortKey(b.property)));

        groupProjectedProperties(entries).forEach((group) => {
            if (group.length < 2) {
                return;
            }

            const sortedGroup = group
                .slice()
                .sort((a, b) => getStablePropertySortKey(a.property).localeCompare(getStablePropertySortKey(b.property)));
            const center = sortedGroup.reduce((acc, entry) => ({
                x: acc.x + entry.point.x,
                y: acc.y + entry.point.y,
            }), { x: 0, y: 0 });

            center.x /= sortedGroup.length;
            center.y /= sortedGroup.length;

            sortedGroup.forEach((entry, index) => {
                const offset = getSpreadOffset(index, sortedGroup.length);
                const spreadLngLat = state.map.unproject([
                    center.x + offset.x,
                    center.y + offset.y,
                ]);

                entry.property.map_lng = spreadLngLat.lng;
                entry.property.map_lat = spreadLngLat.lat;
            });
        });

        return prepared;
    }

    function propertiesToGeoJson(properties) {
        const normalized = prepareDisplayCoordinates(
            properties
                .filter((property) => !Number.isNaN(parseFloat(property.lat)) && !Number.isNaN(parseFloat(property.lng)))
                .map((property) => ({ ...property }))
        );

        return {
            type: 'FeatureCollection',
            features: normalized.map((property) => ({
                type: 'Feature',
                id: property.id,
                geometry: {
                    type: 'Point',
                    coordinates: [parseFloat(property.map_lng), parseFloat(property.map_lat)],
                },
                properties: {
                    ...property,
                    is_aggregate: property.is_aggregate === true,
                    icon_name: getPropertyIconName(property.property_type, property.deal_type),
                },
            })),
        };
    }

    function ensureSourceAndLayers() {
        if (!state.map || state.map.getSource(SOURCE_ID)) {
            return;
        }

        const behavior = getMapBehaviorConfig();
        const sourceOptions = {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
            generateId: true,
        };

        if (behavior.enablePropertyClusters) {
            sourceOptions.cluster = true;
            sourceOptions.clusterRadius = 55;
            sourceOptions.clusterMaxZoom = 14;
        }

        state.map.addSource(SOURCE_ID, sourceOptions);

        state.map.addSource(HOVER_SOURCE_ID, {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
        });

        state.map.addSource(SELECTED_SOURCE_ID, {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
        });

        state.map.addSource(HOVER_CLUSTER_SOURCE_ID, {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
        });

        state.map.addSource(DISTRICT_SOURCE_ID, {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
        });

        state.map.addSource(DISTRICT_HOVER_SOURCE_ID, {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
        });

        state.map.addSource(SPIDER_POINT_SOURCE_ID, {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
        });

        state.map.addSource(SPIDER_LEG_SOURCE_ID, {
            type: 'geojson',
            data: createEmptyFeatureCollection(),
        });

        state.map.addLayer({
            id: DISTRICT_FILL_LAYER_ID,
            type: 'fill',
            source: DISTRICT_SOURCE_ID,
            paint: {
                'fill-color': '#F1B400',
                'fill-opacity': 0.065,
            },
        });

        state.map.addLayer({
            id: DISTRICT_OUTLINE_LAYER_ID,
            type: 'line',
            source: DISTRICT_SOURCE_ID,
            paint: {
                'line-color': 'rgba(148, 163, 184, 0.68)',
                'line-width': 1.35,
                'line-opacity': 0.92,
            },
        });

        state.map.addLayer({
            id: DISTRICT_HOVER_LAYER_ID,
            type: 'fill',
            source: DISTRICT_HOVER_SOURCE_ID,
            paint: {
                'fill-color': '#F1B400',
                'fill-opacity': 0.2,
            },
        });

        state.map.addLayer({
            id: DISTRICT_HOVER_OUTLINE_LAYER_ID,
            type: 'line',
            source: DISTRICT_HOVER_SOURCE_ID,
            paint: {
                'line-color': '#F1B400',
                'line-width': 3.2,
                'line-opacity': 0.98,
            },
        });

        // Overview aggregates are rendered as DOM markers to avoid relying on
        // legacy GeoJSON style-layer state during dynamic catalog loading.
        const aggregateFilter = ['==', ['get', 'aggregate_render_mode'], 'maplibre'];
        state.map.addLayer({
            id: AGGREGATE_GLOW_LAYER_ID,
            type: 'circle',
            source: SOURCE_ID,
            filter: aggregateFilter,
            paint: {
                'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 24, 50, 38],
                'circle-color': '#F1B400',
                'circle-opacity': 0.2,
                'circle-blur': 0.8,
            },
        });
        state.map.addLayer({
            id: AGGREGATE_RING_LAYER_ID,
            type: 'circle',
            source: SOURCE_ID,
            filter: aggregateFilter,
            paint: {
                'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 16, 50, 30],
                'circle-color': '#ffffff',
                'circle-opacity': 0.98,
            },
        });
        state.map.addLayer({
            id: AGGREGATE_LAYER_ID,
            type: 'circle',
            source: SOURCE_ID,
            filter: aggregateFilter,
            paint: {
                'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 12, 50, 24],
                'circle-color': '#F1B400',
                'circle-stroke-color': 'rgba(51, 56, 71, 0.1)',
                'circle-stroke-width': 2,
            },
        });
        state.map.addLayer({
            id: AGGREGATE_LABEL_LAYER_ID,
            type: 'symbol',
            source: SOURCE_ID,
            filter: aggregateFilter,
            layout: {
                'text-field': ['get', 'count'],
                'text-size': 12,
            },
            paint: {
                'text-color': '#333847',
            },
        });

        const propertyFilter = ['==', ['get', 'is_aggregate'], false];

        if (behavior.enablePropertyClusters) {
            state.map.addLayer({
                id: CLUSTER_GLOW_LAYER_ID,
                type: 'circle',
                source: SOURCE_ID,
                filter: ['has', 'point_count'],
                paint: {
                    'circle-color': '#F1B400',
                    'circle-radius': [
                        'step',
                        ['get', 'point_count'],
                        26,
                        20, 33,
                        50, 40
                    ],
                    'circle-opacity': 0.18,
                    'circle-blur': 0.8,
                },
            });

            state.map.addLayer({
                id: CLUSTER_RING_LAYER_ID,
                type: 'circle',
                source: SOURCE_ID,
                filter: ['has', 'point_count'],
                paint: {
                    'circle-color': '#ffffff',
                    'circle-radius': [
                        'step',
                        ['get', 'point_count'],
                        20,
                        20, 26,
                        50, 32
                    ],
                    'circle-opacity': 0.95,
                },
            });

            state.map.addLayer({
                id: CLUSTER_LAYER_ID,
                type: 'circle',
                source: SOURCE_ID,
                filter: ['has', 'point_count'],
                paint: {
                    'circle-color': getClusterCoreColorExpression(),
                    'circle-radius': [
                        'step',
                        ['get', 'point_count'],
                        16,
                        20, 21,
                        50, 26
                    ],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': 'rgba(17,24,39,0.08)',
                    'circle-opacity': 0.98,
                },
            });

            state.map.addLayer({
                id: HOVER_CLUSTER_LAYER_ID,
                type: 'circle',
                source: HOVER_CLUSTER_SOURCE_ID,
                paint: {
                    'circle-color': '#F1B400',
                    'circle-radius': 36,
                    'circle-opacity': 0.2,
                    'circle-blur': 0.75,
                },
            });
        }

        state.map.addLayer({
            id: SPIDER_LEG_LAYER_ID,
            type: 'line',
            source: SPIDER_LEG_SOURCE_ID,
            layout: {
                'line-cap': 'round',
                'line-join': 'round',
            },
            paint: {
                'line-color': 'rgba(71, 75, 87, 0.3)',
                'line-width': 2,
                'line-opacity': 0.92,
            },
        });

        state.map.addLayer({
            id: POINT_GLOW_LAYER_ID,
            type: 'circle',
            source: SOURCE_ID,
            filter: propertyFilter,
            paint: {
                'circle-radius': 19,
                'circle-color': '#474b57',
                'circle-opacity': 0.12,
                'circle-blur': 0.85,
            },
        });

        state.map.addLayer({
            id: POINT_RING_LAYER_ID,
            type: 'circle',
            source: SOURCE_ID,
            filter: propertyFilter,
            paint: {
                'circle-radius': 13,
                'circle-color': '#ffffff',
                'circle-opacity': 0.2,
            },
        });

        state.map.addLayer({
            id: POINT_LAYER_ID,
            type: 'circle',
            source: SOURCE_ID,
            filter: propertyFilter,
            paint: {
                'circle-radius': 11,
                'circle-color': getDealColorExpression(),
                'circle-stroke-width': 0,
                'circle-stroke-color': 'rgba(17,24,39,0)',
                'circle-opacity': 0.01,
            },
        });

        state.map.addLayer({
            id: SPIDER_POINT_GLOW_LAYER_ID,
            type: 'circle',
            source: SPIDER_POINT_SOURCE_ID,
            paint: {
                'circle-radius': 21,
                'circle-color': getDealColorExpression(),
                'circle-opacity': 0.14,
                'circle-blur': 0.82,
            },
        });

        state.map.addLayer({
            id: SPIDER_POINT_RING_LAYER_ID,
            type: 'circle',
            source: SPIDER_POINT_SOURCE_ID,
            paint: {
                'circle-radius': 13,
                'circle-color': '#ffffff',
                'circle-opacity': 0.2,
            },
        });

        state.map.addLayer({
            id: SPIDER_POINT_LAYER_ID,
            type: 'circle',
            source: SPIDER_POINT_SOURCE_ID,
            paint: {
                'circle-radius': 11,
                'circle-color': getDealColorExpression(),
                'circle-stroke-width': 0,
                'circle-stroke-color': 'rgba(17,24,39,0)',
                'circle-opacity': 0.01,
            },
        });

        state.map.addLayer({
            id: HOVER_POINT_LAYER_ID,
            type: 'circle',
            source: HOVER_SOURCE_ID,
            paint: {
                'circle-radius': 25,
                'circle-color': '#F1B400',
                'circle-opacity': 0.2,
                'circle-blur': 0.8,
            },
        });

        state.map.addLayer({
            id: SELECTED_POINT_LAYER_ID,
            type: 'circle',
            source: SELECTED_SOURCE_ID,
            paint: {
                'circle-radius': 29,
                'circle-color': '#F1B400',
                'circle-opacity': 0.3,
                'circle-blur': 0.78,
            },
        });

        state.map.addLayer({
            id: POINT_ICON_LAYER_ID,
            type: 'symbol',
            source: SOURCE_ID,
            filter: propertyFilter,
            layout: {
                'icon-image': ['get', 'icon_name'],
                'icon-size': 1,
                'icon-anchor': 'center',
                'icon-allow-overlap': true,
                'icon-ignore-placement': true,
            },
        });

        state.map.addLayer({
            id: SPIDER_POINT_ICON_LAYER_ID,
            type: 'symbol',
            source: SPIDER_POINT_SOURCE_ID,
            layout: {
                'icon-image': ['get', 'icon_name'],
                'icon-size': 0.78,
                'icon-anchor': 'center',
                'icon-allow-overlap': true,
                'icon-ignore-placement': true,
            },
        });
    }

    function setSourceData(sourceId, data) {
        if (!state.map || !state.map.getSource(sourceId)) {
            return;
        }

        state.map.getSource(sourceId).setData(data);
    }

    function setSingleFeatureSource(sourceId, feature) {
        if (!state.map || !state.map.getSource(sourceId)) {
            return;
        }

        const collection = feature ? {
            type: 'FeatureCollection',
            features: [feature],
        } : createEmptyFeatureCollection();

        setSourceData(sourceId, collection);
    }

    function getExistingLayerIds(layerIds) {
        if (!state.map) {
            return [];
        }

        return layerIds.filter((layerId) => state.map.getLayer(layerId));
    }

    function setDistrictsGeoJson(geoJson) {
        state.districtGeoJson = geoJson || createEmptyFeatureCollection();
        setSourceData(DISTRICT_SOURCE_ID, state.districtGeoJson);
    }

    function getDistrictFeatureFromSource(feature) {
        const districtSlug = feature?.properties?.slug;
        if (!districtSlug || !Array.isArray(state.districtGeoJson?.features)) {
            return feature || null;
        }

        return state.districtGeoJson.features.find((item) => item?.properties?.slug === districtSlug) || feature || null;
    }

    function clearHoverState() {
        setSingleFeatureSource(HOVER_SOURCE_ID, null);
        setSingleFeatureSource(HOVER_CLUSTER_SOURCE_ID, null);
        setSingleFeatureSource(DISTRICT_HOVER_SOURCE_ID, null);
        state.hoveredClusterId = null;
        state.hoveredPropertyId = null;
    }

    function clearSpiderfy() {
        setSourceData(SPIDER_POINT_SOURCE_ID, createEmptyFeatureCollection());
        setSourceData(SPIDER_LEG_SOURCE_ID, createEmptyFeatureCollection());
        state.spiderClusterId = null;
    }

    function setSelectedFeature(feature) {
        state.selectedPropertyId = feature?.properties?.id || null;
        setSingleFeatureSource(SELECTED_SOURCE_ID, feature || null);
    }

    function shouldSpiderfyCluster(clusterFeature, expansionZoom) {
        const pointCount = parseInt(clusterFeature?.properties?.point_count, 10) || 0;
        return pointCount > 1 && pointCount <= SPIDERFY_MAX_POINTS;
    }

    function showPropertyPopup(feature, { pinned = false, trackClick = false } = {}) {
        if (!feature) {
            return;
        }

        const propertyId = feature.properties?.id || null;
        if (!pinned && state.lastPopupPropertyId === propertyId && state.popup?.isOpen()) {
            return;
        }

        const coordinates = feature.geometry.coordinates.slice();
        const popupAnchor = getPopupAnchor(coordinates);
        const popup = createPopup({ anchor: popupAnchor });
        const popupHtml = window.mapPopupUtils?.buildPropertyPopupHtml(feature.properties) || '';

        clearHoverPopupTimer();
        state.isPinnedPopup = pinned;
        state.lastPopupPropertyId = propertyId;

        if (pinned) {
            setSelectedFeature(feature);
        }

        popup.setMaxWidth(getPopupMaxWidth());

        popup
            .setLngLat(coordinates)
            .setHTML(popupHtml)
            .addTo(state.map);

        updatePopupLayoutState(popup, { pinned, coordinates, anchor: popupAnchor });

        if (typeof window.syncFavoriteIcons === 'function') {
            window.syncFavoriteIcons();
        }

        requestAnimationFrame(() => {
            clampPopupToMapFrame(popup);
        });
        setTimeout(() => {
            clampPopupToMapFrame(popup);
        }, 120);

        bindPopupHoverGuards(popup);

        if (trackClick && typeof window.dispatchMetrikaGoal === 'function') {
            window.dispatchMetrikaGoal('catalog_map_marker_click', {
                id: feature.properties.id,
                slug: feature.properties.slug,
                type: feature.properties.property_type,
            });
        }
    }

    function openPropertyPopup(feature) {
        showPropertyPopup(feature, { pinned: true, trackClick: true });
    }

    function openHoverPropertyPopup(feature) {
        if (!isHoverPopupEnabled() || state.isPinnedPopup) {
            return;
        }

        showPropertyPopup(feature, { pinned: false, trackClick: false });
    }

    function spiderfyCluster(clusterFeature) {
        if (!state.map || !clusterFeature) {
            return;
        }

        const clusterId = clusterFeature.properties.cluster_id;
        const clusterSource = state.map.getSource(SOURCE_ID);
        if (!clusterSource) {
            return;
        }

        if (state.spiderClusterId === clusterId) {
            clearSpiderfy();
            return;
        }

        Promise.resolve(clusterSource.getClusterLeaves(clusterId, SPIDERFY_MAX_POINTS, 0))
            .then((leaves) => {
                if (!Array.isArray(leaves) || !leaves.length) {
                    return;
                }

                clearSpiderfy();

                const centerCoordinates = clusterFeature.geometry.coordinates.slice();
                const centerPoint = state.map.project(centerCoordinates);
                const pointCount = leaves.length;
                const radius = Math.max(52, Math.min(96, 32 + pointCount * 4));
                const pointFeatures = [];
                const legFeatures = [];

                leaves.forEach((leaf, index) => {
                    const angle = (-Math.PI / 2) + (index / pointCount) * Math.PI * 2;
                    const spiderPoint = state.map.unproject([
                        centerPoint.x + Math.cos(angle) * radius,
                        centerPoint.y + Math.sin(angle) * radius,
                    ]);

                    const pointFeature = {
                        type: 'Feature',
                        id: leaf.id,
                        geometry: {
                            type: 'Point',
                            coordinates: [spiderPoint.lng, spiderPoint.lat],
                        },
                        properties: {
                            ...leaf.properties,
                        },
                    };

                    pointFeatures.push(pointFeature);
                    legFeatures.push({
                        type: 'Feature',
                        geometry: {
                            type: 'LineString',
                            coordinates: [
                                centerCoordinates,
                                [spiderPoint.lng, spiderPoint.lat],
                            ],
                        },
                        properties: {},
                    });
                });

                setSourceData(SPIDER_POINT_SOURCE_ID, {
                    type: 'FeatureCollection',
                    features: pointFeatures,
                });
                setSourceData(SPIDER_LEG_SOURCE_ID, {
                    type: 'FeatureCollection',
                    features: legFeatures,
                });
                state.spiderClusterId = clusterId;
            })
            .catch(() => {});
    }

    function bindInteractions() {
        if (!state.map) {
            return;
        }

        const propertyInteractiveLayerIds = getExistingLayerIds(POINT_INTERACTIVE_LAYER_IDS);
        const aggregateInteractiveLayerIds = getExistingLayerIds(AGGREGATE_INTERACTIVE_LAYER_IDS);
        const clusterInteractiveLayerIds = isPropertyClusteringEnabled()
            ? getExistingLayerIds(CLUSTER_INTERACTIVE_LAYER_IDS)
            : [];
        const cursorLayerIds = getExistingLayerIds([
            ...aggregateInteractiveLayerIds,
            ...clusterInteractiveLayerIds,
            ...propertyInteractiveLayerIds,
            ...DISTRICT_INTERACTIVE_LAYER_IDS,
        ]);

        const navigateToDistrictFeature = (feature) => {
            if (!feature?.properties?.slug) {
                return;
            }
            window.location.href = buildDistrictFilterUrl(feature.properties.slug);
        };

        state.map.on('click', (event) => {
            const propertyClickLayerIds = [
                ...aggregateInteractiveLayerIds,
                ...propertyInteractiveLayerIds,
                ...clusterInteractiveLayerIds,
            ];
            const interactiveFeatures = propertyClickLayerIds.length
                ? state.map.queryRenderedFeatures(event.point, { layers: propertyClickLayerIds })
                : [];
            const targetFeature = interactiveFeatures[0];

            if (!targetFeature) {
                const districtFeatures = state.map.queryRenderedFeatures(event.point, {
                    layers: DISTRICT_INTERACTIVE_LAYER_IDS,
                });
                const districtFeature = districtFeatures[0];
                if (districtFeature) {
                    navigateToDistrictFeature(districtFeature);
                    return;
                }

                clearSpiderfy();
                clearHoverState();
                closePropertyPopup({ clearPinned: true });
                return;
            }

            if (targetFeature.properties?.is_aggregate === true || targetFeature.properties?.is_aggregate === 'true') {
                clearSpiderfy();
                state.map.once('zoomend', () => {
                    emitMapEvent('catalog-map:aggregate-selected');
                });
                state.map.easeTo({
                    center: targetFeature.geometry.coordinates,
                    zoom: Math.min(state.map.getZoom() + 2, 15),
                    duration: 500,
                });
                return;
            }

            if (targetFeature.properties && Object.prototype.hasOwnProperty.call(targetFeature.properties, 'point_count')) {
                setSingleFeatureSource(HOVER_CLUSTER_SOURCE_ID, targetFeature);

                const clusterId = targetFeature.properties.cluster_id;
                Promise.resolve(state.map.getSource(SOURCE_ID).getClusterExpansionZoom(clusterId))
                    .then((zoom) => {
                        if (shouldSpiderfyCluster(targetFeature, zoom)) {
                            spiderfyCluster(targetFeature);
                            return;
                        }

                        clearSpiderfy();

                        state.map.easeTo({
                            center: targetFeature.geometry.coordinates,
                            zoom,
                            duration: 500,
                        });
                    })
                    .catch(() => {});
                return;
            }

            openPropertyPopup(targetFeature);
        });

        cursorLayerIds.forEach((layerId) => {
            state.map.on('mouseenter', layerId, () => {
                state.map.getCanvas().style.cursor = 'pointer';
            });

            state.map.on('mouseleave', layerId, () => {
                state.map.getCanvas().style.cursor = '';
            });
        });

        const handleClusterMouseMove = (event) => {
            const feature = event.features && event.features[0];
            if (!feature) {
                clearHoverState();
                return;
            }

            if (state.hoveredClusterId === feature.properties.cluster_id) {
                return;
            }

            state.hoveredClusterId = feature.properties.cluster_id;
            setSingleFeatureSource(HOVER_CLUSTER_SOURCE_ID, feature);
        };

        const handleClusterMouseLeave = () => {
            setSingleFeatureSource(HOVER_CLUSTER_SOURCE_ID, null);
            state.hoveredClusterId = null;
        };

        clusterInteractiveLayerIds.forEach((layerId) => {
            state.map.on('mousemove', layerId, handleClusterMouseMove);
            state.map.on('mouseleave', layerId, handleClusterMouseLeave);
        });

        const handlePointMouseMove = (event) => {
            const feature = event.features && event.features[0];
            if (!feature) {
                setSingleFeatureSource(HOVER_SOURCE_ID, null);
                return;
            }

            state.hoveredPropertyId = feature.properties.id || null;
            clearHoverPopupTimer();

            if (state.selectedPropertyId && state.selectedPropertyId === feature.properties.id) {
                return;
            }

            setSingleFeatureSource(HOVER_SOURCE_ID, feature);
            openHoverPropertyPopup(feature);
        };

        const handlePointMouseLeave = () => {
            state.hoveredPropertyId = null;
            setSingleFeatureSource(HOVER_SOURCE_ID, null);
            scheduleHoverPopupClose();
        };

        propertyInteractiveLayerIds.forEach((layerId) => {
            state.map.on('mousemove', layerId, handlePointMouseMove);
            state.map.on('mouseleave', layerId, handlePointMouseLeave);
        });

        const handleDistrictMouseMove = (event) => {
            const feature = event.features && event.features[0];
            if (!feature) {
                setSingleFeatureSource(DISTRICT_HOVER_SOURCE_ID, null);
                return;
            }

            setSingleFeatureSource(DISTRICT_HOVER_SOURCE_ID, getDistrictFeatureFromSource(feature));
        };

        const handleDistrictMouseLeave = () => {
            setSingleFeatureSource(DISTRICT_HOVER_SOURCE_ID, null);
        };

        DISTRICT_INTERACTIVE_LAYER_IDS.forEach((layerId) => {
            state.map.on('mousemove', layerId, handleDistrictMouseMove);
            state.map.on('mouseleave', layerId, handleDistrictMouseLeave);
        });
    }

    function fitToProperties(geoJson) {
        if (!state.map) {
            return;
        }

        if (!geoJson.features.length) {
            state.map.easeTo({
                center: DEFAULT_CENTER,
                zoom: DEFAULT_ZOOM,
                duration: 500,
            });
            return;
        }

        const bounds = new maplibregl.LngLatBounds();
        geoJson.features.forEach((feature) => {
            bounds.extend(feature.geometry.coordinates);
        });

        state.map.fitBounds(bounds, {
            padding: 64,
            maxZoom: 14,
            duration: 700,
        });
    }

    function resetView() {
        if (!state.map) {
            return;
        }

        fitToProperties(state.lastGeoJson);
    }

    function normalizeLng(lng) {
        if (!Number.isFinite(lng)) {
            return lng;
        }

        return ((((lng + 180) % 360) + 360) % 360) - 180;
    }

    function clampLat(lat) {
        if (!Number.isFinite(lat)) {
            return lat;
        }

        return Math.max(-90, Math.min(90, lat));
    }

    function getBoundsParams(options = {}) {
        if (!state.map || !isBoundsBasedLoadingEnabled()) {
            return null;
        }

        const bounds = state.map.getBounds();
        if (!bounds) {
            return null;
        }

        const behavior = getMapBehaviorConfig();
        const shouldPad = options.padded !== false;
        const paddingRatio = shouldPad ? Math.max(0, behavior.boundsPaddingRatio) : 0;
        const north = bounds.getNorth();
        const south = bounds.getSouth();
        const east = bounds.getEast();
        const west = bounds.getWest();
        const latPadding = Math.abs(north - south) * paddingRatio;
        const lngPadding = Math.abs(east - west) * paddingRatio;

        return {
            bounds_north: Number(clampLat(north + latPadding).toFixed(6)),
            bounds_south: Number(clampLat(south - latPadding).toFixed(6)),
            bounds_east: Number(normalizeLng(east + lngPadding).toFixed(6)),
            bounds_west: Number(normalizeLng(west - lngPadding).toFixed(6)),
        };
    }

    function getZoom() {
        return state.map ? state.map.getZoom() : DEFAULT_ZOOM;
    }

    function renderProperties({ fit = false } = {}) {
        if (!state.loaded || !state.map || !state.map.getSource(SOURCE_ID)) {
            return;
        }

        const geoJson = propertiesToGeoJson(state.pendingProperties);
        state.lastGeoJson = geoJson;
        state.map.getSource(SOURCE_ID).setData(geoJson);
        renderAggregateMarkers(state.pendingProperties);

        if (fit) {
            fitToProperties(geoJson);
        }
    }

    function setProperties(properties, options = {}) {
        const shouldFit = options.fit !== false;
        state.pendingProperties = Array.isArray(properties) ? properties : [];
        clearSpiderfy();
        clearHoverState();
        closePropertyPopup({ clearPinned: true });
        setSelectedFeature(null);

        renderProperties({ fit: shouldFit });
    }

    function initialize(containerId = 'map-container') {
        if (state.map) {
            refreshSize();
            return state.map;
        }

        const container = document.getElementById(containerId);
        if (!container || typeof maplibregl === 'undefined') {
            return null;
        }

        state.map = new maplibregl.Map({
            container: containerId,
            style: getBaseMapStyle(),
            center: DEFAULT_CENTER,
            zoom: DEFAULT_ZOOM,
            attributionControl: true,
        });

        state.map.addControl(new maplibregl.NavigationControl(), 'top-right');

        state.map.on('load', () => {
            state.loaded = true;
            registerPropertyIcons().then(() => {
                ensureSourceAndLayers();
                bindInteractions();
                setProperties(state.pendingProperties);
                loadDistrictOverlay();
                syncDistrictMarkersVisibility();
                emitMapEvent('catalog-map:ready');
            }).catch((error) => {
                emitMapEvent('catalog-map:error', { error });
            });
        });

        state.map.on('zoom', () => {
            syncDistrictMarkersVisibility();
        });

        state.map.on('zoomend', () => {
            renderProperties({ fit: false });
        });

        state.map.on('moveend', () => {
            if (!state.loaded || !isBoundsBasedLoadingEnabled()) {
                return;
            }

            emitMapEvent('catalog-map:bounds-changed', {
                bounds: getBoundsParams({ padded: true }),
                visibleBounds: getBoundsParams({ padded: false }),
            });
        });

        state.map.on('error', (event) => {
            emitMapEvent('catalog-map:error', { error: event?.error || null });
        });

        return state.map;
    }

    function refreshSize() {
        if (!state.map) {
            return;
        }

        requestAnimationFrame(() => {
            state.map.resize();
        });
    }

    window.propertiesMapBridge = {
        initialize,
        setProperties,
        refreshSize,
        resetView,
        getBoundsParams,
        getZoom,
        getMap() {
            return state.map;
        },
    };
})();
