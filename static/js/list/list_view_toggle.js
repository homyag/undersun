function setView(viewType) {
    // Update button states
    document.querySelectorAll('#grid-view, #map-view').forEach(btn => {
        btn.classList.remove('text-primary', 'bg-primary/10');
        btn.classList.add('text-gray-600');
    });
    
    const activeBtn = document.getElementById(viewType + '-view');
    activeBtn.classList.add('text-primary', 'bg-primary/10');
    activeBtn.classList.remove('text-gray-600');
    
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
}