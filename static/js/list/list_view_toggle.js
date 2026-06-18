function syncCatalogViewUrl(viewType) {
    const currentUrl = new URL(window.location.href);

    if (viewType === 'map') {
        currentUrl.searchParams.set('map_view', 'true');
    } else {
        currentUrl.searchParams.delete('map_view');
    }

    window.history.replaceState(window.history.state, '', `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`);
}

const catalogMapAssetState = {
    promise: null,
    loadedStyles: new Set(),
    loadedScripts: new Set(),
};

function loadCatalogMapStylesheet(href) {
    if (!href || catalogMapAssetState.loadedStyles.has(href) || document.querySelector(`link[href="${href}"]`)) {
        catalogMapAssetState.loadedStyles.add(href);
        return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.onload = () => {
            catalogMapAssetState.loadedStyles.add(href);
            resolve();
        };
        link.onerror = () => reject(new Error(`Failed to load stylesheet: ${href}`));
        document.head.appendChild(link);
    });
}

function loadCatalogMapScript(src) {
    if (!src || catalogMapAssetState.loadedScripts.has(src) || document.querySelector(`script[src="${src}"]`)) {
        catalogMapAssetState.loadedScripts.add(src);
        return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.async = false;
        script.onload = () => {
            catalogMapAssetState.loadedScripts.add(src);
            resolve();
        };
        script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
        document.body.appendChild(script);
    });
}

function ensureCatalogMapAssets() {
    if (catalogMapAssetState.promise) {
        return catalogMapAssetState.promise;
    }

    const assets = window.catalogMapAssets || {};
    const styles = Array.isArray(assets.styles) ? assets.styles : [];
    const scripts = Array.isArray(assets.scripts) ? assets.scripts : [];

    catalogMapAssetState.promise = Promise.all(styles.map(loadCatalogMapStylesheet))
        .then(() => scripts.reduce((chain, src) => chain.then(() => loadCatalogMapScript(src)), Promise.resolve()));

    return catalogMapAssetState.promise;
}

function initializeCatalogMapView() {
    if (typeof window.setMapStatus === 'function') {
        window.setMapStatus('loading');
    }

    ensureCatalogMapAssets()
        .then(() => {
            const mapContainer = document.getElementById('properties-map');
            if (!mapContainer || mapContainer.classList.contains('hidden')) {
                return;
            }

            if (typeof window.initializePropertiesMap === 'function') {
                window.initializePropertiesMap();
            }
        })
        .catch((error) => {
            console.error('Catalog map assets failed to load:', error);
            if (typeof window.setMapStatus === 'function') {
                window.setMapStatus('error');
            }
        });
}

function setView(viewType) {
    // Update button states
    const toggleButtons = document.querySelectorAll('#grid-view, #map-view');
    toggleButtons.forEach(btn => {
        btn.classList.remove('view-toggle-btn--active');
        btn.setAttribute('aria-pressed', 'false');
    });
    
    const activeBtn = document.getElementById(viewType + '-view');
    if (activeBtn) {
        activeBtn.classList.add('view-toggle-btn--active');
        activeBtn.setAttribute('aria-pressed', 'true');
    }
    
    // Show/hide views
    const grid = document.getElementById('properties-grid');
    const map = document.getElementById('properties-map');
    const pagination = document.querySelector('.pagination-container');
    
    if (viewType === 'map') {
        // Hide grid and pagination, show map
        grid.classList.add('hidden');
        if (pagination) pagination.classList.add('hidden');
        map.classList.remove('hidden');

        if (typeof window.setMapStatus === 'function') {
            window.setMapStatus('loading');
        }
        
        // Initialize map if not already done
        initializeCatalogMapView();
    } else {
        // Show grid and pagination, hide map
        grid.classList.remove('hidden');
        if (pagination) pagination.classList.remove('hidden');
        map.classList.add('hidden');
        
        // Set grid layout
        grid.className = 'properties-grid grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6';
    }

    // Save preference
    localStorage.setItem('propertyViewType', viewType);
    syncCatalogViewUrl(viewType);

    // Update dropdown label if present
    const selectEl = document.querySelector('[data-view-select]');
    if (selectEl) {
        selectEl.value = viewType;
    }
}

function changeView(viewType) {
    if (typeof window.dispatchMetrikaGoal === 'function') {
        window.dispatchMetrikaGoal('catalog_view_change', { view: viewType });
    }
    setView(viewType);
}

window.setView = setView;
window.changeView = changeView;
window.ensureCatalogMapAssets = ensureCatalogMapAssets;
