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
        
        // Initialize map if not already done
        initializePropertiesMap();
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

    // Update dropdown label if present
    const selectEl = document.querySelector('[data-view-select]');
    if (selectEl) {
        selectEl.value = viewType;
    }
}

function changeView(viewType) {
    setView(viewType);
}
