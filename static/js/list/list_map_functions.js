// Global map variables
let propertiesMap = null;
let markersGroup = null;

// Function to get marker color based on deal type
function getMarkerColor(dealType) {
    switch(dealType) {
        case 'sale': return '#10b981'; // green
        case 'rent': return '#3b82f6'; // blue
        case 'both': return '#8b5cf6'; // purple
        default: return '#6b7280'; // gray
    }
}

// Function to get property type icon SVG content
function getPropertyIconSVG(propertyType) {
    const iconSVGs = {
        'villa': `
            <g transform="translate(6, 6)">
                <path d="M10 4L2 10h2v8h12v-8h2L10 4z" fill="white"/>
                <rect x="4" y="10" width="12" height="8" fill="white"/>
                <rect x="8.5" y="14" width="3" height="4" fill="currentColor"/>
                <rect x="5.5" y="12" width="2" height="2" fill="currentColor"/>
                <rect x="12.5" y="12" width="2" height="2" fill="currentColor"/>
                <rect x="13" y="6" width="1.5" height="4" fill="white"/>
            </g>
        `,
        'apartment': `
            <g transform="translate(6, 4)">
                <rect x="2" y="4" width="16" height="16" fill="white"/>
                <polygon points="1,4 10,1 19,4" fill="white"/>
                <rect x="4" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="7" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="11" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="14" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="4" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="7" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="11" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="14" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="4" y="15" width="2" height="2" fill="currentColor"/>
                <rect x="14" y="15" width="2" height="2" fill="currentColor"/>
                <rect x="8" y="15" width="4" height="5" fill="currentColor"/>
            </g>
        `,
        'condominium': `
            <g transform="translate(6, 4)">
                <rect x="2" y="4" width="16" height="16" fill="white"/>
                <polygon points="1,4 10,1 19,4" fill="white"/>
                <rect x="4" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="7" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="11" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="14" y="7" width="2" height="2" fill="currentColor"/>
                <rect x="4" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="7" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="11" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="14" y="11" width="2" height="2" fill="currentColor"/>
                <rect x="4" y="15" width="2" height="2" fill="currentColor"/>
                <rect x="14" y="15" width="2" height="2" fill="currentColor"/>
                <rect x="8" y="15" width="4" height="5" fill="currentColor"/>
            </g>
        `,
        'townhouse': `
            <g transform="translate(4, 5)">
                <rect x="0" y="8" width="7" height="10" fill="white"/>
                <polygon points="0,8 3.5,4 7,8" fill="white"/>
                <rect x="6" y="6" width="7" height="12" fill="white"/>
                <polygon points="6,6 9.5,2 13,6" fill="white"/>
                <rect x="12" y="9" width="7" height="9" fill="white"/>
                <polygon points="12,9 15.5,5 19,9" fill="white"/>
                <rect x="2" y="14" width="2" height="4" fill="currentColor"/>
                <rect x="8" y="14" width="2" height="4" fill="currentColor"/>
                <rect x="14" y="14" width="2" height="4" fill="currentColor"/>
                <rect x="1" y="11" width="1.5" height="1.5" fill="currentColor"/>
                <rect x="4.5" y="11" width="1.5" height="1.5" fill="currentColor"/>
                <rect x="7" y="9" width="1.5" height="1.5" fill="currentColor"/>
                <rect x="10.5" y="9" width="1.5" height="1.5" fill="currentColor"/>
                <rect x="13" y="12" width="1.5" height="1.5" fill="currentColor"/>
                <rect x="16.5" y="12" width="1.5" height="1.5" fill="currentColor"/>
            </g>
        `,
        'land': `
            <g transform="translate(5, 6)">
                <rect x="1" y="2" width="18" height="14" fill="none" stroke="white" stroke-width="1.5" stroke-dasharray="2,1"/>
                <circle cx="6" cy="8" r="3" fill="white"/>
                <rect x="5.5" y="11" width="1" height="3" fill="white"/>
                <circle cx="14" cy="6" r="2.5" fill="white"/>
                <rect x="13.5" y="8.5" width="1" height="2.5" fill="white"/>
                <circle cx="4" cy="13" r="1.5" fill="white"/>
                <circle cx="16" cy="12" r="1.5" fill="white"/>
                <circle cx="2" cy="3" r="1" fill="white"/>
                <circle cx="18" cy="3" r="1" fill="white"/>
                <circle cx="2" cy="15" r="1" fill="white"/>
                <circle cx="18" cy="15" r="1" fill="white"/>
            </g>
        `,
        'business': `
            <g transform="translate(6, 5)">
                <rect x="2" y="6" width="16" height="12" fill="white"/>
                <polygon points="1,6 10,3 19,6" fill="white"/>
                <rect x="3" y="14" width="6" height="4" fill="currentColor"/>
                <rect x="11" y="14" width="6" height="4" fill="currentColor"/>
                <rect x="4" y="9" width="2" height="2" fill="currentColor"/>
                <rect x="7" y="9" width="2" height="2" fill="currentColor"/>
                <rect x="11" y="9" width="2" height="2" fill="currentColor"/>
                <rect x="14" y="9" width="2" height="2" fill="currentColor"/>
                <rect x="3" y="12" width="14" height="1" fill="white"/>
                <rect x="9" y="15" width="2" height="3" fill="white"/>
            </g>
        `
    };
    
    return iconSVGs[propertyType.toLowerCase()] || `
        <g transform="translate(7, 6)">
            <rect x="2" y="10" width="14" height="10" fill="white"/>
            <polygon points="1,10 9,4 17,10" fill="white"/>
            <rect x="7" y="15" width="4" height="5" fill="currentColor"/>
            <rect x="4" y="13" width="2.5" height="2" fill="currentColor"/>
            <rect x="11.5" y="13" width="2.5" height="2" fill="currentColor"/>
        </g>
    `;
}

// Function to format price for marker display
function formatPriceForMarker(priceText) {
    if (!priceText || priceText === 'По запросу' || priceText === 'Price on request') {
        return null;
    }
    
    // Extract price and currency from formatted text
    // Expected formats: "$1,500,000", "฿45,000,000", "₽85,000,000", etc.
    const match = priceText.match(/([₽$฿€£¥])?([\d,\s]+)([₽$฿€£¥])?/);
    if (!match) return null;
    
    const currencyStart = match[1];
    const priceStr = match[2];
    const currencyEnd = match[3];
    const currency = currencyStart || currencyEnd || '$';
    
    // Convert to number
    const price = parseInt(priceStr.replace(/[,\s]/g, ''));
    if (isNaN(price) || price <= 0) return null;
    
    // Format for display
    if (price >= 1000000) {
        return `${currency}${(price / 1000000).toFixed(1)}M`;
    } else if (price >= 1000) {
        return `${currency}${Math.round(price / 1000)}K`;
    } else {
        return `${currency}${price}`;
    }
}

// Function to create custom marker
function createCustomMarker(lat, lng, propertyType, dealType, priceText = null) {
    const markerColor = getMarkerColor(dealType);
    const priceDisplay = formatPriceForMarker(priceText);
    
    // Create custom icon with price indicator
    const customIcon = L.divIcon({
        html: `
            <div class="property-marker-container">
                <!-- Price indicator (like Booking.com) -->
                ${priceDisplay ? `
                <div class="price-indicator" style="background: ${markerColor};">
                    <span class="price-text">${priceDisplay}</span>
                    <div class="price-arrow"></div>
                </div>
                ` : ''}
                
                <!-- Property icon marker -->
                <div class="custom-marker" style="color: ${markerColor};">
                    <svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">
                        <path d="M16 0C7.16 0 0 7.16 0 16c0 12 16 24 16 24s16-12 16-24C32 7.16 24.84 0 16 0z" fill="${markerColor}"/>
                        ${getPropertyIconSVG(propertyType)}
                    </svg>
                </div>
            </div>
        `,
        className: 'property-marker-wrapper',
        iconSize: [140, 60], // Увеличиваем размер для размещения цены
        iconAnchor: [70, 60], // Центрируем по горизонтали, привязка к низу
        popupAnchor: [0, -60]
    });
    
    return L.marker([lat, lng], { icon: customIcon });
}

// Initialize Properties Map
function initializePropertiesMap() {
    if (propertiesMap) {
        // Map already exists, just refresh markers
        updateMapMarkers();
        return;
    }
    
    const mapContainer = document.getElementById('map-container');
    if (!mapContainer) return;
    
    // Initialize map centered on Phuket
    propertiesMap = L.map('map-container').setView([7.9519, 98.3381], 11);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(propertiesMap);
    
    // Create marker group
    markersGroup = L.layerGroup().addTo(propertiesMap);
    
    // Add markers for properties
    updateMapMarkers();
    
    // Force map resize after container is visible
    setTimeout(() => {
        propertiesMap.invalidateSize();
    }, 100);
}