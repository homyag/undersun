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
                const marker = createCustomMarker({
                    lat: adjustedLat,
                    lng: adjustedLng,
                    dealType: property.deal_type,
                    priceText: property.price,
                    imageUrl: property.image_url || window.djangoUrls.noImageSvg,
                    title: property.title
                }).addTo(markersGroup);
                
                const imageUrl = property.image_url || window.djangoUrls.noImageSvg;
                const propertyTypeLabel = property.property_type_label || property.property_type || '';
                const locationLabel = property.location || '';
                const bedrooms = parseInt(property.bedrooms, 10) || 0;
                const bathrooms = parseInt(property.bathrooms, 10) || 0;
                const areaValue = parseFloat(property.area) || 0;
                const priceLabel = property.price || window.djangoTranslations.priceOnRequest;
                const cleanPhone = (property.agent_phone || '+66633033133').replace(/[^0-9]/g, '') || '66633033133';

                const popupContent = `
                    <div class="property-popup">
                        <div class="popup-media" data-property-id="${property.id}">
                            <img src="${imageUrl}" alt="${escapeHtml(property.title)}" class="popup-image" loading="lazy">
                            ${propertyTypeLabel ? `<span class="popup-media-chip">${escapeHtml(propertyTypeLabel)}</span>` : ''}
                            <button class="favorite-toggle" type="button" onclick="toggleFavorite(${property.id})" title="${window.djangoTranslations.addToFavorites}">
                                <i class="far fa-heart" id="favorite-${property.id}"></i>
                            </button>
                        </div>
                        <div class="popup-body">
                            <div class="popup-price-row">
                                <div class="popup-price">${priceLabel}</div>
                                <a href="${property.url}" class="popup-link" target="_blank" rel="noopener">
                                    ${window.djangoTranslations.moreDetails}
                                    <i class="fas fa-arrow-right text-xs"></i>
                                </a>
                            </div>
                            <p class="popup-title">${escapeHtml(property.title)}</p>
                            <div class="popup-location">
                                <i class="fas fa-map-marker-alt"></i>
                                ${escapeHtml(locationLabel)}
                            </div>
                            <div class="popup-meta">
                                ${bedrooms ? `<span><i class="fas fa-bed"></i>${bedrooms} ${window.djangoTranslations.bedroomsShort}</span>` : ''}
                                ${bathrooms ? `<span><i class="fas fa-shower"></i>${bathrooms} ${window.djangoTranslations.bathroomsShort}</span>` : ''}
                                ${areaValue ? `<span><i class="fas fa-ruler-combined"></i>${Math.round(areaValue)} ${window.djangoTranslations.areaShort}</span>` : ''}
                            </div>
                            <div class="popup-actions">
                                <a href="https://wa.me/${cleanPhone}?text=${encodeURIComponent(window.djangoTranslations.whatsappText + ': ' + property.title)}" class="popup-action whatsapp" target="_blank" rel="noopener">
                                    <i class="fab fa-whatsapp"></i>
                                    WhatsApp
                                </a>
                                <a href="${property.url}" class="popup-action primary" target="_blank" rel="noopener">
                                    ${window.djangoTranslations.moreDetails}
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
        const areaValue = parseFloat(area) || 0;
        
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
        const marker = createCustomMarker({
            lat: adjustedLat,
            lng: adjustedLng,
            dealType,
            priceText: formattedPrice,
            imageUrl: images[0] || window.djangoUrls.noImageSvg,
            title
        }).addTo(markersGroup);
        
        const propertyTypeLabel = card.dataset.propertyTypeLabel || propertyType;
        const cleanPhone = (card.dataset.agentPhone || '+66633033133').replace(/[^0-9]/g, '') || '66633033133';
        const priceLabel = formattedPrice || window.djangoTranslations.priceOnRequest;

        // Create enhanced popup content
        const popupContent = `
            <div class="property-popup">
                <div class="popup-media" data-property-id="${propertyId}">
                    <img src="${mainImage}" alt="${escapeHtml(title)}" class="popup-image" loading="lazy">
                    ${propertyTypeLabel ? `<span class="popup-media-chip">${escapeHtml(propertyTypeLabel)}</span>` : ''}
                    <button class="favorite-toggle" type="button" onclick="toggleFavorite(${propertyId})" title="${window.djangoTranslations.addToFavorites}">
                        <i class="far fa-heart" id="favorite-${propertyId}"></i>
                    </button>
                </div>
                <div class="popup-body">
                    <div class="popup-price-row">
                        <div class="popup-price">${priceLabel}</div>
                        <a href="${link}" class="popup-link" target="_blank" rel="noopener">
                            ${window.djangoTranslations.moreDetails}
                            <i class="fas fa-arrow-right text-xs"></i>
                        </a>
                    </div>
                    <p class="popup-title">${escapeHtml(title)}</p>
                    <div class="popup-location">
                        <i class="fas fa-map-marker-alt"></i>
                        ${escapeHtml(location)}
                    </div>
                    <div class="popup-meta">
                        ${bedrooms ? `<span><i class="fas fa-bed"></i>${bedrooms} ${window.djangoTranslations.bedroomsShort}</span>` : ''}
                        ${bathrooms ? `<span><i class="fas fa-shower"></i>${bathrooms} ${window.djangoTranslations.bathroomsShort}</span>` : ''}
                        ${areaValue ? `<span><i class="fas fa-ruler-combined"></i>${Math.round(areaValue)} ${window.djangoTranslations.areaShort}</span>` : ''}
                    </div>
                    <div class="popup-actions">
                        <a href="https://wa.me/${cleanPhone}?text=${encodeURIComponent(window.djangoTranslations.whatsappText + ': ' + title)}" class="popup-action whatsapp" target="_blank" rel="noopener">
                            <i class="fab fa-whatsapp"></i>
                            WhatsApp
                        </a>
                        <a href="${link}" class="popup-action primary" target="_blank" rel="noopener">
                            ${window.djangoTranslations.moreDetails}
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
