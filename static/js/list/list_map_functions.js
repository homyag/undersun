// Global map variables
let propertiesMap = null;
let markersGroup = null;

function escapeHtml(str = '') {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttribute(value = '') {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function createCustomMarker({ lat, lng, dealType, priceText, imageUrl, title }) {
    const safeTitle = escapeHtml(title || 'Undersun Estate');
    const safeImage = escapeAttribute(imageUrl || window.djangoUrls.noImageSvg);
    const priceDisplay = priceText || window.djangoTranslations?.priceOnRequest || 'Price on request';

    const customIcon = L.divIcon({
        html: `
            <div class="marker-card marker-${dealType || 'sale'}">
                <div class="marker-image-wrapper">
                    <div class="marker-image" role="presentation" style="background-image: url('${safeImage}');" aria-label="${safeTitle}"></div>
                    <span class="marker-price-chip">${escapeHtml(priceDisplay)}</span>
                </div>
            </div>
        `,
        className: 'property-marker-wrapper',
        iconSize: [132, 118],
        iconAnchor: [66, 118],
        popupAnchor: [0, -110]
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
    
    // Create cluster group for markers
    markersGroup = L.markerClusterGroup({
        showCoverageOnHover: false,
        spiderfyDistanceMultiplier: 2.8,
        spiderLegPolylineOptions: {
            weight: 0,
            opacity: 0
        },
        maxClusterRadius: 55,
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();
            let sizeClass = 'small';
            if (count > 50) {
                sizeClass = 'large';
            } else if (count > 20) {
                sizeClass = 'medium';
            }
            return L.divIcon({
                html: `<div><span>${count}</span></div>`,
                className: 'marker-cluster marker-cluster-' + sizeClass,
                iconSize: L.point(40, 40)
            });
        }
    });
    propertiesMap.addLayer(markersGroup);
    
    // Add markers for properties
    updateMapMarkers();
    
    // Force map resize after container is visible
    setTimeout(() => {
        propertiesMap.invalidateSize();
    }, 100);
}
