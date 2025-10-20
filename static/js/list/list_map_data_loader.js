// Update map markers based on all filtered properties (optimized loading)
function updateMapMarkers() {
    if (!markersGroup) return;
    
    // Clear existing markers
    markersGroup.clearLayers();
    
    
    // Get current filter parameters
    const form = document.getElementById('filter-form');
    const formData = new FormData(form);
    const params = new URLSearchParams();
    
    // Convert FormData to URLSearchParams
    for (const [key, value] of formData.entries()) {
        if (typeof value === 'string') {
            params.append(key, value);
        }
    }
    
    // Fetch all filtered properties via optimized JSON API
    fetch(`${window.djangoUrls.mapPropertiesJson}?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                console.error('Error loading map properties:', data.error);
                // Fallback to current page properties
                loadCurrentPageProperties();
                return;
            }
            
            const properties = data.properties;
            const bounds = [];
            
            
            properties.forEach((property, index) => {
                const lat = property.lat;
                const lng = property.lng;
                
                if (!lat || !lng || isNaN(lat) || isNaN(lng)) {
                    return; // Skip if no valid coordinates
                }
                
                // Apply small jitter for overlapping coordinates
                let adjustedLat = lat;
                let adjustedLng = lng;
                
                if (lat % 1 === 0 && lng % 1 === 0) {
                    const jitter = 0.001;
                    adjustedLat = lat + (Math.random() - 0.5) * jitter;
                    adjustedLng = lng + (Math.random() - 0.5) * jitter;
                }
                
                // Create marker with property data
                const marker = createCustomMarker(
                    adjustedLat, 
                    adjustedLng, 
                    property.property_type, 
                    property.deal_type, 
                    property.price
                ).addTo(markersGroup);
                
                // Create popup content with real image data
                const imageUrl = property.image_url || window.djangoUrls.noImageSvg;
                const popupContent = `
                    <div class="property-popup">
                        <!-- Main Image -->
                        <div class="popup-image-container">
                            <img src="${imageUrl}" alt="${property.title}" class="popup-image" />
                        </div>
                        
                        <!-- Content -->
                        <div class="popup-content">
                            <!-- Title and Price -->
                            <div class="popup-title">${property.title}</div>
                            <div class="popup-price">${property.price}</div>
                            
                            <!-- Location -->
                            <div class="popup-location">
                                <i class="fas fa-map-marker-alt"></i>
                                ${property.location}
                            </div>
                            
                            <!-- Property Details Grid -->
                            <div class="popup-details-grid">
                                <div class="popup-detail-item">
                                    <i class="fas fa-home"></i>
                                    <span>${property.property_type}</span>
                                </div>
                                <div class="popup-detail-item">
                                    <i class="fas fa-tag"></i>
                                    <span>${property.deal_type}</span>
                                </div>
                            </div>
                            
                            <!-- Action Buttons -->
                            <div class="popup-actions">
                                <button class="popup-button-icon" onclick="toggleFavorite(${property.id})" title="В избранное">
                                    <i class="far fa-heart" id="favorite-${property.id}"></i>
                                </button>
                                
                                <a href="https://wa.me/66123456789?text=Здравствуйте! Меня интересует объект: ${encodeURIComponent(property.title)}" 
                                   class="popup-button popup-button-secondary" 
                                   target="_blank">
                                    <i class="fab fa-whatsapp"></i> WhatsApp
                                </a>
                                
                                <a href="${property.url}" class="popup-button popup-button-primary">
                                    Подробнее
                                </a>
                            </div>
                        </div>
                    </div>
                `;
                
                marker.bindPopup(popupContent, {
                    maxWidth: 280,
                    className: 'enhanced-popup',
                    autoPan: true,
                    autoPanPadding: [20, 20],
                    keepInView: true,
                    closeButton: true
                });
                
                bounds.push([adjustedLat, adjustedLng]);
            });
            
            // Fit map to bounds if we have markers
            if (bounds.length > 0) {
                const group = new L.featureGroup(markersGroup.getLayers());
                propertiesMap.fitBounds(group.getBounds().pad(0.1));
            }
        })
        .catch(error => {
            console.error('Error fetching map properties:', error);
            // Fallback to current page properties
            loadCurrentPageProperties();
        });
}

// Fallback function to load current page properties
function loadCurrentPageProperties() {
    const propertyCards = document.querySelectorAll('.property-card');
    const bounds = [];
    
    propertyCards.forEach((card, index) => {
        // Extract property data from card attributes
        const propertyId = card.dataset.propertyId;
        let lat = parseFloat(card.dataset.latitude);
        let lng = parseFloat(card.dataset.longitude);
        
        // Handle potential comma-separated decimals (localization issue)
        if (isNaN(lat) || isNaN(lng)) {
            lat = parseFloat(card.dataset.latitude.replace(',', '.'));
            lng = parseFloat(card.dataset.longitude.replace(',', '.'));
        }
        
        if (!lat || !lng || isNaN(lat) || isNaN(lng)) {
            return; // Skip if no coordinates
        }
        
        // Get property details from data attributes and elements
        const title = card.dataset.title || 'Property';
        const propertyType = card.dataset.propertyType || '';
        const dealType = card.dataset.dealType || '';
        const location = card.dataset.location || '';
        const link = card.dataset.url || '#';
        const mainImage = card.dataset.mainImage || '/media/no-image.jpg';
        const imagesString = card.dataset.images || '';
        const images = imagesString ? imagesString.split(',').filter(img => img.trim()) : [mainImage];
        const bedrooms = card.dataset.bedrooms || '';
        const bathrooms = card.dataset.bathrooms || '';
        const area = card.dataset.area || '';
        
        // Get current price from price element (respects currency conversion)
        const priceElement = card.querySelector(`[class*="card-price-${propertyId}"]`);
        const price = priceElement ? priceElement.textContent.trim() : '';
        
        // Get current currency
        const currencyElement = card.querySelector(`[class*="current-currency-code-${propertyId}"]`);
        const currency = currencyElement ? currencyElement.textContent.trim() : '';
        
        const formattedPrice = price && currency ? `${price} ${currency}` : price;
        
        // Check if coordinates are too simplified and add small jitter to avoid overlapping
        let adjustedLat = lat;
        let adjustedLng = lng;
        
        // If coordinates are whole numbers (like 7, 8, 98), they're likely simplified
        if (lat % 1 === 0 && lng % 1 === 0) {
            // Add small random offset to prevent markers from stacking
            const jitter = 0.001; // ~100 meters
            adjustedLat = lat + (Math.random() - 0.5) * jitter;
            adjustedLng = lng + (Math.random() - 0.5) * jitter;
        }
        
        // Create marker with adjusted coordinates using custom marker (include price)
        const marker = createCustomMarker(adjustedLat, adjustedLng, propertyType, dealType, formattedPrice).addTo(markersGroup);
        
        // Create enhanced popup content
        const popupContent = `
            <div class="property-popup">
                <!-- Main Image -->
                <div class="popup-image-container">
                    <img src="${mainImage}" alt="${title}" class="popup-image" />
                </div>
                
                <!-- Content -->
                <div class="popup-content">
                    <!-- Title and Price -->
                    <div class="popup-title">${title}</div>
                    <div class="popup-price">${formattedPrice}</div>
                    
                    <!-- Location -->
                    <div class="popup-location">
                        <i class="fas fa-map-marker-alt"></i>
                        ${location}
                    </div>
                    
                    <!-- Property Details Grid -->
                    <div class="popup-details-grid">
                        <div class="popup-detail-item">
                            <i class="fas fa-home"></i>
                            <span>${propertyType}</span>
                        </div>
                        <div class="popup-detail-item">
                            <i class="fas fa-tag"></i>
                            <span>${dealType}</span>
                        </div>
                    </div>
                    
                    <!-- Action Buttons -->
                    <div class="popup-actions">
                        <button class="popup-button-icon" onclick="toggleFavorite(${propertyId})" title="В избранное">
                            <i class="far fa-heart" id="favorite-${propertyId}"></i>
                        </button>
                        
                        <a href="https://wa.me/66123456789?text=Здравствуйте! Меня интересует объект: ${encodeURIComponent(title)}" 
                           class="popup-button popup-button-secondary" 
                           target="_blank">
                            <i class="fab fa-whatsapp"></i> WhatsApp
                        </a>
                        
                        <a href="${link}" class="popup-button popup-button-primary">
                            Подробнее
                        </a>
                    </div>
                </div>
            </div>
        `;
        
        marker.bindPopup(popupContent, {
            maxWidth: 280,
            className: 'enhanced-popup',
            autoPan: true,
            autoPanPadding: [20, 20],
            keepInView: true,
            closeButton: true
        });
        bounds.push([adjustedLat, adjustedLng]);
    });
    
    // Fit map to bounds if we have markers
    if (bounds.length > 0) {
        const group = new L.featureGroup(markersGroup.getLayers());
        propertiesMap.fitBounds(group.getBounds().pad(0.1));
    }
}
