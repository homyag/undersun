function initializePropertiesMap() {
    if (!window.propertiesMapBridge) {
        return;
    }

    window.propertiesMapBridge.initialize('map-container');
    updateMapMarkers();

    setTimeout(() => {
        window.propertiesMapBridge.refreshSize();
    }, 120);
}

window.initializePropertiesMap = initializePropertiesMap;
