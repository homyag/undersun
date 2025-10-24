// Load saved view preference
document.addEventListener('DOMContentLoaded', function() {
    // Update results counter on page load
    updateResultsCounter();
    
    // Check if we need to return to map view after filter changes
    if (localStorage.getItem('returnToMapView') === 'true') {
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
    
    if (mobileFiltersToggle) {
        mobileFiltersToggle.addEventListener('click', function() {
            const isHidden = filtersSidebar.classList.contains('hidden');
            
            if (isHidden) {
                filtersSidebar.classList.remove('hidden');
                filtersSidebar.classList.add('mobile-open');
                mobileFiltersArrow.style.transform = 'rotate(180deg)';
            } else {
                filtersSidebar.classList.add('hidden');
                filtersSidebar.classList.remove('mobile-open');
                mobileFiltersArrow.style.transform = 'rotate(0deg)';
            }
        });
    }
    
    // Dynamic location updates based on district selection
    const districtSelect = document.getElementById('district-select');
    const locationSelect = document.getElementById('location-select');
    
    if (districtSelect && locationSelect) {
        districtSelect.addEventListener('change', function() {
            const districtSlug = this.value;
            
            // Clear current location selection
            locationSelect.innerHTML = '<option value="">Все локации</option>';
            
            if (districtSlug) {
                // Fetch locations for the selected district
                fetch(`${window.djangoUrls.getLocationsForDistrict}?district=${districtSlug}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            data.locations.forEach(location => {
                                const option = document.createElement('option');
                                option.value = location.slug;
                                option.textContent = location.name;
                                locationSelect.appendChild(option);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching locations:', error);
                    });
            }
            
            // Auto-submit form after updating locations
            setTimeout(() => {
                document.getElementById('filter-form').submit();
            }, 100);
        });
    }
    
    // Auto-submit form when any filter changes
    const form = document.getElementById('filter-form');
    if (form) {
        // Get all form inputs
        const inputs = form.querySelectorAll('input, select');
        
        inputs.forEach(input => {
            if (input.name === 'sort') return; // Skip sort field
            
            const eventType = input.type === 'checkbox' || input.type === 'radio' ? 'change' : 
                            input.tagName === 'SELECT' ? 'change' : 'input';
            
            // Different delays for different input types
            let delay = 300; // Default delay
            
            // Price inputs need longer delay to allow user to finish typing
            if (input.name === 'min_price' || input.name === 'max_price') {
                delay = 1200; // 1.2 seconds for price inputs
            }
            
            input.addEventListener(eventType, function() {
                // Clear any existing timeout for this specific input
                const timeoutKey = `filterTimeout_${input.name}`;
                clearTimeout(window[timeoutKey]);
                
                // Show loading indicator for price inputs
                if (input.name === 'min_price' || input.name === 'max_price') {
                    const indicator = input.nextElementSibling;
                    if (indicator && indicator.classList.contains('price-loading-indicator')) {
                        indicator.classList.remove('hidden');
                    }
                }
                
                // Set new timeout
                window[timeoutKey] = setTimeout(() => {
                    // Hide loading indicator before submit
                    if (input.name === 'min_price' || input.name === 'max_price') {
                        const indicator = input.nextElementSibling;
                        if (indicator && indicator.classList.contains('price-loading-indicator')) {
                            indicator.classList.add('hidden');
                        }
                    }
                    
                    // Check if we're in map view and need to preserve it after page reload
                    const currentView = localStorage.getItem('propertyViewType') || 'grid';
                    if (currentView === 'map') {
                        // Store that we want to return to map view after form submission
                        localStorage.setItem('returnToMapView', 'true');
                    }
                    
                    form.submit();
                }, delay);
            });
        });
    }
    
    // Fix pagination to work with filters using event delegation  
    document.addEventListener('click', function(e) {
        // Check if clicked element is a pagination link
        if (e.target.closest('.pagination-container a')) {
            e.preventDefault();
            
            const link = e.target.closest('.pagination-container a');
            
            // Check if this is an AJAX-generated pagination link (has data-page)
            if (link.hasAttribute('data-page')) {
                // Let AJAX handler from main.js handle this
                return;
            }
            
            // Handle Django-generated pagination links
            const url = new URL(link.href);
            const page = url.searchParams.get('page');
            
            // Get current form data
            const form = document.getElementById('filter-form');
            const formData = new FormData(form);
            
            // Convert FormData to URLSearchParams
            const params = new URLSearchParams();
            for (const [key, value] of formData.entries()) {
                if (typeof value === 'string') {
                    params.append(key, value);
                }
            }
            
            // Add/update page parameter
            params.set('page', page);
            
            // Navigate to new URL with all parameters
            window.location.href = '?' + params.toString();
        }
    });
    
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
});
