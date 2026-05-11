// Load saved view preference
document.addEventListener('DOMContentLoaded', function() {
    // Update results counter on page load
    updateResultsCounter();

    const currentUrl = new URL(window.location.href);

    if (currentUrl.searchParams.get('map_view') === 'true') {
        setView('map');
    } else if (localStorage.getItem('returnToMapView') === 'true') {
        localStorage.removeItem('returnToMapView');
        setView('map');
    } else {
        const savedView = localStorage.getItem('propertyViewType') || 'grid';
        setView(savedView);
    }
});

// Mobile filters toggle
document.addEventListener('DOMContentLoaded', function() {
    const mobileFiltersToggle = document.getElementById('mobile-filters-toggle');
    const mobileFiltersArrow = document.getElementById('mobile-filters-arrow');
    const filtersSidebar = document.getElementById('filters-sidebar');
    const form = document.getElementById('filter-form');
    const propertiesContainer = document.querySelector('.properties-container');
    const loadingOverlay = document.getElementById('catalog-loading-overlay');
    const manualApplyInputs = new Set(['district', 'q', 'min_price', 'max_price']);
    const applyLabels = Array.from(document.querySelectorAll('[data-filters-apply-label]'));
    const pendingCatalogRestoreKey = 'catalogPendingRestore';
    let applyCountRequestId = 0;
    let applyCountTimeout = null;

    const getCurrentViewType = () => {
        const currentUrl = new URL(window.location.href);
        if (currentUrl.searchParams.get('map_view') === 'true') {
            return 'map';
        }
        return localStorage.getItem('propertyViewType') || 'grid';
    };

    const getCatalogStateKey = (urlString = window.location.href) => {
        const currentUrl = new URL(urlString, window.location.origin);
        return `catalogState:${currentUrl.pathname}${currentUrl.search}`;
    };

    const showCatalogLoadingState = () => {
        if (!propertiesContainer) {
            return;
        }
        if (loadingOverlay && window.djangoTranslations?.loadingCatalog) {
            const textNode = loadingOverlay.querySelector('.loading-overlay-text');
            if (textNode) {
                textNode.textContent = window.djangoTranslations.loadingCatalog;
            }
        }
        propertiesContainer.classList.add('loading');
    };

    const hideCatalogLoadingState = () => {
        if (!propertiesContainer) {
            return;
        }
        propertiesContainer.classList.remove('loading');
    };

    const applyCatalogState = (state) => {
        if (!state || typeof state !== 'object') {
            return;
        }

        if (state.viewType === 'map') {
            setView('map');
        }

        if (typeof state.scrollY !== 'number') {
            return;
        }

        const targetScrollY = Math.max(0, state.scrollY);
        const restoreScroll = () => window.scrollTo(0, targetScrollY);

        window.requestAnimationFrame(restoreScroll);
        window.setTimeout(restoreScroll, 80);
    };

    const savePendingCatalogRestore = () => {
        try {
            const payload = {
                scrollY: window.scrollY || window.pageYOffset || 0,
                viewType: getCurrentViewType(),
                timestamp: Date.now()
            };
            sessionStorage.setItem(pendingCatalogRestoreKey, JSON.stringify(payload));
        } catch (error) {
            // Ignore storage issues silently.
        }
    };

    const restorePendingCatalogState = () => {
        try {
            const rawState = sessionStorage.getItem(pendingCatalogRestoreKey);
            if (!rawState) {
                return;
            }

            sessionStorage.removeItem(pendingCatalogRestoreKey);
            const parsedState = JSON.parse(rawState);
            if (!parsedState || typeof parsedState !== 'object') {
                return;
            }

            const stateAge = Date.now() - (parsedState.timestamp || 0);
            if (stateAge > 20000) {
                return;
            }

            applyCatalogState(parsedState);
        } catch (error) {
            try {
                sessionStorage.removeItem(pendingCatalogRestoreKey);
            } catch (removeError) {
                // Ignore storage issues silently.
            }
        }
    };

    const ensureViewModeInput = () => {
        if (!form) {
            return null;
        }

        let mapViewInput = form.querySelector('input[name="map_view"]');
        if (!mapViewInput) {
            mapViewInput = document.createElement('input');
            mapViewInput.type = 'hidden';
            mapViewInput.name = 'map_view';
            form.appendChild(mapViewInput);
        }

        return mapViewInput;
    };

    const syncViewModeInput = () => {
        if (!form) {
            return;
        }

        if (getCurrentViewType() === 'map') {
            const mapViewInput = ensureViewModeInput();
            if (!mapViewInput) {
                return;
            }
            mapViewInput.value = 'true';
        } else {
            const mapViewInput = form.querySelector('input[name="map_view"]');
            if (mapViewInput) {
                mapViewInput.remove();
            }
        }
    };

    const saveCatalogState = () => {
        try {
            const payload = {
                scrollY: window.scrollY || window.pageYOffset || 0,
                viewType: getCurrentViewType()
            };
            sessionStorage.setItem(getCatalogStateKey(), JSON.stringify(payload));
        } catch (error) {
            // Ignore storage issues silently.
        }
    };

    const restoreCatalogState = () => {
        try {
            hideCatalogLoadingState();
            const rawState = sessionStorage.getItem(getCatalogStateKey());
            if (!rawState) {
                return;
            }

            const parsedState = JSON.parse(rawState);
            applyCatalogState(parsedState);
        } catch (error) {
            // Ignore malformed state silently.
        }
    };

    const appendCurrentViewToUrl = (urlString) => {
        const targetUrl = new URL(urlString, window.location.href);
        if (getCurrentViewType() === 'map') {
            targetUrl.searchParams.set('map_view', 'true');
        } else {
            targetUrl.searchParams.delete('map_view');
        }
        return `${targetUrl.pathname}${targetUrl.search}${targetUrl.hash}`;
    };

    const trackCatalogGoal = (goalName, params) => {
        if (typeof window.dispatchMetrikaGoal === 'function' && goalName) {
            window.dispatchMetrikaGoal(goalName, params);
        }
    };

    const submitFilters = (options = {}) => {
        if (!form) {
            return;
        }
        const trigger = options.trigger || '';
        const origin = options.origin || '';
        form.dataset.lastFilterTrigger = trigger;
        form.dataset.lastFilterOrigin = origin;
        syncViewModeInput();
        saveCatalogState();
        savePendingCatalogRestore();
        showCatalogLoadingState();

        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            trackCatalogGoal('catalog_filters_submit', {
                trigger: trigger || 'auto',
                origin: origin || (trigger ? 'auto' : 'manual')
            });
            form.submit();
        }
    };

    const updateApplyButtonLabel = (text) => {
        if (!applyLabels.length) {
            return;
        }
        applyLabels.forEach(label => {
            label.textContent = text;
        });
    };

    const buildApplyButtonText = (count) => {
        const primaryLabel = applyLabels[0];
        if (!primaryLabel) {
            return '';
        }
        const baseLabel = primaryLabel.dataset.showResultsLabel || primaryLabel.dataset.defaultLabel || 'Apply';
        const parsedCount = Number.isFinite(count) ? count : parseInt(count, 10);
        if (!Number.isFinite(parsedCount)) {
            return baseLabel;
        }
        return `${baseLabel} (${parsedCount})`;
    };

    const updateApplyButtonCount = (options = {}) => {
        const primaryLabel = applyLabels[0];
        if (!form || !primaryLabel || !window.djangoUrls?.ajaxSearchCount) {
            return;
        }

        const requestId = ++applyCountRequestId;
        const loadingLabel = primaryLabel.dataset.loadingLabel || primaryLabel.dataset.defaultLabel || 'Apply';
        updateApplyButtonLabel(loadingLabel);

        const formData = new FormData(form);
        formData.delete('sort');
        const params = new URLSearchParams();

        for (const [key, value] of formData.entries()) {
            if (typeof value !== 'string') {
                continue;
            }
            const trimmedValue = value.trim();
            if (trimmedValue === '') {
                continue;
            }
            params.append(key, trimmedValue);
        }

        const currentPropertyType = (form.dataset.currentPropertyType || '').trim();
        const hasSelectedPropertyTypes = params.has('property_type');
        if (currentPropertyType && !hasSelectedPropertyTypes) {
            params.set('current_property_type', currentPropertyType);
        }

        const routeDealType = (form.dataset.routeDealType || '').trim();
        if (routeDealType && !params.has('deal_type')) {
            params.set('deal_type', routeDealType);
        }

        fetch(`${window.djangoUrls.ajaxSearchCount}?${params.toString()}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (requestId !== applyCountRequestId) {
                    return;
                }
                if (data && data.success) {
                    updateApplyButtonLabel(buildApplyButtonText(data.count));
                    return;
                }
                updateApplyButtonLabel(primaryLabel.dataset.defaultLabel || 'Apply');
            })
            .catch(() => {
                if (requestId !== applyCountRequestId) {
                    return;
                }
                updateApplyButtonLabel(primaryLabel.dataset.defaultLabel || 'Apply');
            });
    };

    const scheduleApplyButtonCount = (delay = 250) => {
        if (!applyLabels.length) {
            return;
        }
        clearTimeout(applyCountTimeout);
        applyCountTimeout = setTimeout(() => {
            updateApplyButtonCount();
        }, delay);
    };

    window.submitPropertyFilters = submitFilters;

    if (form) {
        form.addEventListener('submit', function() {
            const trigger = form.dataset.lastFilterTrigger || 'manual';
            const origin = form.dataset.lastFilterOrigin || (trigger === 'manual' ? 'manual' : 'auto');
            trackCatalogGoal('catalog_filters_submit', { trigger, origin });
            form.dataset.lastFilterTrigger = '';
            form.dataset.lastFilterOrigin = '';
            syncViewModeInput();
            saveCatalogState();
            savePendingCatalogRestore();
            showCatalogLoadingState();
        });
    }

    hideCatalogLoadingState();
    restorePendingCatalogState();

    window.addEventListener('pagehide', function() {
        saveCatalogState();
    });

    window.addEventListener('pageshow', function(event) {
        hideCatalogLoadingState();
        const navigationEntry = performance.getEntriesByType('navigation')[0];
        const isBackForwardNavigation = navigationEntry?.type === 'back_forward';
        if (event.persisted || isBackForwardNavigation) {
            restoreCatalogState();
        }
    });

    document.addEventListener('click', function(event) {
        const catalogNavLink = event.target.closest('[data-catalog-nav-link]');
        if (!catalogNavLink) {
            return;
        }

        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }

        const href = catalogNavLink.getAttribute('href');
        if (!href || href.startsWith('#') || catalogNavLink.target === '_blank' || catalogNavLink.hasAttribute('download')) {
            return;
        }

        catalogNavLink.href = appendCurrentViewToUrl(href);
        saveCatalogState();
        showCatalogLoadingState();
    });
    
    if (mobileFiltersToggle) {
        mobileFiltersToggle.addEventListener('click', function() {
            const isHidden = filtersSidebar.classList.contains('hidden');
            const nextState = isHidden ? 'open' : 'close';

            if (isHidden) {
                filtersSidebar.classList.remove('hidden');
                filtersSidebar.classList.add('mobile-open');
                mobileFiltersArrow.style.transform = 'rotate(180deg)';
            } else {
                filtersSidebar.classList.add('hidden');
                filtersSidebar.classList.remove('mobile-open');
                mobileFiltersArrow.style.transform = 'rotate(0deg)';
            }

            trackCatalogGoal('catalog_mobile_filters_toggle', { state: nextState });
        });
    }

    syncViewModeInput();
    
    // Dynamic location updates based on district selection
    const districtSelect = document.getElementById('district-select');
    const locationSelect = document.getElementById('location-select');
    
    if (districtSelect && locationSelect) {
        const getListTranslation = (key, fallback) => {
            return window.djangoTranslations?.[key] || fallback;
        };

        const setSingleLocationOption = (label) => {
            locationSelect.innerHTML = '';
            const option = document.createElement('option');
            option.value = '';
            option.textContent = label;
            locationSelect.appendChild(option);
        };

        const populateLocations = (locations) => {
            const defaultLabel = getListTranslation('allLocations', 'All locations');
            locationSelect.innerHTML = '';

            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = defaultLabel;
            locationSelect.appendChild(defaultOption);

            locations.forEach(location => {
                const option = document.createElement('option');
                option.value = location.slug;
                option.textContent = location.name;
                locationSelect.appendChild(option);
            });
        };

        const fetchLocations = (districtSlug = '') => {
            const loadingLabel = getListTranslation('loadingLocations', 'Loading locations...');
            const emptyLabel = getListTranslation('noLocationsAvailable', 'No locations found');
            const params = new URLSearchParams();
            if (districtSlug) {
                params.set('district', districtSlug);
            }

            locationSelect.disabled = true;
            setSingleLocationOption(loadingLabel);

            const queryString = params.toString();
            const endpoint = queryString
                ? `${window.djangoUrls.getLocationsForDistrict}?${queryString}`
                : window.djangoUrls.getLocationsForDistrict;

            fetch(endpoint)
                .then(response => response.json())
                .then(data => {
                    if (data.success && Array.isArray(data.locations) && data.locations.length > 0) {
                        populateLocations(data.locations);
                    } else {
                        setSingleLocationOption(emptyLabel);
                    }
                })
                .catch(error => {
                    console.error('Error fetching locations:', error);
                    setSingleLocationOption(getListTranslation('allLocations', 'All locations'));
                })
                .finally(() => {
                    locationSelect.disabled = false;
                    updateApplyButtonCount();
                });
        };

        districtSelect.addEventListener('change', function() {
            fetchLocations(this.value);
        });
    }

    const amenitiesSearchInput = document.querySelector('[data-amenities-search]');
    const amenityItems = Array.from(document.querySelectorAll('[data-amenity-item]'));
    const amenitiesToggle = document.querySelector('[data-amenities-toggle]');
    const amenitiesToggleLabel = document.querySelector('[data-amenities-toggle-label]');
    const amenitiesToggleIcon = document.querySelector('[data-amenities-toggle-icon]');
    const amenitiesEmptyState = document.querySelector('[data-amenities-empty]');
    let amenitiesExpanded = false;

    const updateAmenitiesVisibility = () => {
        if (!amenityItems.length) {
            return;
        }

        const query = (amenitiesSearchInput?.value || '').trim().toLowerCase();
        let visibleCount = 0;
        let hasCollapsedItems = false;

        amenityItems.forEach(item => {
            const label = item.querySelector('[data-amenity-label]');
            const checkbox = item.querySelector('input[type="checkbox"]');
            const text = (label?.textContent || '').trim().toLowerCase();
            const matchesQuery = !query || text.includes(query);
            const isChecked = Boolean(checkbox?.checked);
            const isDefaultHidden = item.dataset.defaultHidden === 'true';

            if (isDefaultHidden) {
                hasCollapsedItems = true;
            }

            const shouldShow = matchesQuery && (query || amenitiesExpanded || !isDefaultHidden || isChecked);
            item.classList.toggle('hidden', !shouldShow);

            if (shouldShow) {
                visibleCount += 1;
            }
        });

        if (amenitiesEmptyState) {
            amenitiesEmptyState.classList.toggle('hidden', visibleCount > 0);
        }

        if (amenitiesToggle) {
            const hasSearchQuery = Boolean(query);
            amenitiesToggle.classList.toggle('hidden', hasSearchQuery || !hasCollapsedItems);
            if (amenitiesToggleLabel) {
                amenitiesToggleLabel.textContent = amenitiesExpanded
                    ? (amenitiesToggle.dataset.lessLabel || 'Collapse')
                    : (amenitiesToggle.dataset.moreLabel || 'Show more');
            }
            if (amenitiesToggleIcon) {
                amenitiesToggleIcon.style.transform = amenitiesExpanded ? 'rotate(180deg)' : 'rotate(0deg)';
            }
        }
    };

    if (amenityItems.length) {
        if (amenitiesSearchInput) {
            amenitiesSearchInput.addEventListener('input', updateAmenitiesVisibility);
        }

        if (amenitiesToggle) {
            amenitiesToggle.addEventListener('click', function() {
                amenitiesExpanded = !amenitiesExpanded;
                updateAmenitiesVisibility();
            });
        }

        amenityItems.forEach(item => {
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (!checkbox) {
                return;
            }
            checkbox.addEventListener('change', updateAmenitiesVisibility);
        });

        updateAmenitiesVisibility();
    }

    // Auto-submit form when any filter changes
    if (form) {
        // Get all form inputs
        const inputs = Array.from(form.querySelectorAll('input, select'));
        const checkboxes = form.querySelectorAll('input[type="checkbox"]');
        const currentTypeField = form.querySelector('input[name="current_property_type"]');
        const typeUrlPrefix = form.dataset.typeUrlPrefix || '';
        
        inputs.forEach(input => {
            if (input.name === 'sort' || input.name === 'current_property_type') return; // Skip service fields
            if (manualApplyInputs.has(input.name)) {
                const manualEventType = input.tagName === 'SELECT' || input.type === 'radio' || input.type === 'checkbox' ? 'change' : 'input';
                const delay = input.name === 'q' ? 350 : 500;
                input.addEventListener(manualEventType, function() {
                    scheduleApplyButtonCount(delay);
                });
                return;
            }
            
            const eventType = input.type === 'checkbox' || input.type === 'radio' ? 'change' : 
                            input.tagName === 'SELECT' ? 'change' : 'input';
            const delay = 300;
            
            input.addEventListener(eventType, function() {
                if (input.name === 'property_type' && typeUrlPrefix && currentTypeField && currentTypeField.value) {
                    if (input.checked && input.value && input.value !== currentTypeField.value) {
                        const formData = new FormData(form);
                        formData.delete('property_type');
                        formData.delete('current_property_type');
                        const params = new URLSearchParams(formData);
                        const queryString = params.toString();
                        const normalizedPrefix = typeUrlPrefix.endsWith('/') ? typeUrlPrefix : `${typeUrlPrefix}/`;
                        const targetUrl = `${normalizedPrefix}${input.value}/`;
                        savePendingCatalogRestore();
                        window.location.href = queryString ? `${targetUrl}?${queryString}` : targetUrl;
                        return;
                    }
                }
                // Clear any existing timeout for this specific input
                const timeoutKey = `filterTimeout_${input.name}`;
                clearTimeout(window[timeoutKey]);

                // Set new timeout
                window[timeoutKey] = setTimeout(() => {
                    // Check if we're in map view and need to preserve it after page reload
                    const currentView = localStorage.getItem('propertyViewType') || 'grid';
                    if (currentView === 'map') {
                        // Store that we want to return to map view after form submission
                        localStorage.setItem('returnToMapView', 'true');
                    }

                    submitFilters({
                        trigger: input.name || 'input',
                        origin: 'auto'
                    });
                }, delay);
            });
        });

    }
    
    // Fix pagination to work with filters using event delegation  
    // document.addEventListener('click', function(e) {
    //     const paginationLink = e.target.closest('.pagination-container a');
    //     if (!paginationLink) {
    //         return;
    //     }
    //
    //     if (paginationLink.hasAttribute('data-page')) {
    //         return;
    //     }
    //
    //     e.preventDefault();
    //
    //     const targetUrl = new URL(paginationLink.href);
    //     const targetPage = targetUrl.searchParams.get('page') || '1';
    //
    //     const formElement = document.getElementById('filter-form');
    //     if (!formElement) {
    //         window.location.href = targetUrl.toString();
    //         return;
    //     }
    //
    //     const formData = new FormData(formElement);
    //     const params = new URLSearchParams();
    //
    //     for (const [key, value] of formData.entries()) {
    //         if (typeof value !== 'string' || value.trim() === '') {
    //             continue;
    //         }
    //         if (key === 'page') {
    //             continue;
    //         }
    //         params.append(key, value);
    //     }
    //
    //     params.set('page', targetPage);
    //     const queryString = params.toString();
    //     const basePath = window.location.pathname;
    //     const newUrl = queryString ? `${basePath}?${queryString}` : `${basePath}?page=${targetPage}`;
    //
    //     window.location.href = newUrl;
    // });
    
    // Initialize favorites on page load
    let favorites = [];
    if (typeof window.getFavorites === 'function') {
        favorites = window.getFavorites();
    } else {
        favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
        favorites = favorites.map(id => parseInt(id, 10)).filter(id => Number.isInteger(id));
    }

    favorites.forEach(propertyId => {
        const id = parseInt(propertyId, 10);
        if (!Number.isInteger(id)) {
            return;
        }

        if (typeof window.updateFavoriteButtons === 'function') {
            window.updateFavoriteButtons(id, true);
        } else {
            const icon = document.getElementById(`favorite-${id}`);
            if (icon) {
                icon.classList.remove('far');
                icon.classList.add('fas');
            }
        }
    });
    
    // Update favorites counter on page load
    if (typeof window.updateFavoritesCounter === 'function') {
        window.updateFavoritesCounter();
    }

    updateApplyButtonCount();
});
