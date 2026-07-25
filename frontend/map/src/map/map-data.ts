import type { GeoJSONSource } from 'maplibre-gl';

import type { MapPropertiesResponse } from '../features/search/api';

type MapSourceData = Parameters<GeoJSONSource['setData']>[0];

export function toMapFeatureCollection(response: MapPropertiesResponse | undefined): MapSourceData {
  const aggregates = response?.aggregates || [];
  const properties = response?.properties || [];
  const selectedProperty = response?.selected_property;
  const mapItems = aggregates.length ? aggregates : properties;
  const features = mapItems.map((item) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [item.lng, item.lat] },
    properties: {
      count: 'count' in item ? item.count : 1,
      propertyId: 'count' in item ? 0 : item.id,
      isAggregate: 'count' in item,
    },
  }));
  if (selectedProperty && !properties.some((property) => property.id === selectedProperty.id)) {
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [selectedProperty.lng, selectedProperty.lat] },
      properties: { count: 1, propertyId: selectedProperty.id, isAggregate: false },
    });
  }
  return { type: 'FeatureCollection', features } as MapSourceData;
}

export function getSelectedMapPosition(lng: number, lat: number, width: number, height: number, isMobile: boolean) {
  return {
    center: [lng, lat] as [number, number],
    offset: isMobile ? [0, -Math.round(height * 0.18)] as [number, number] : [Math.round(width * 0.2), 0] as [number, number],
  };
}
