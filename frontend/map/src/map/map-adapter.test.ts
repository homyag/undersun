import { describe, expect, it } from 'vitest';

import { getSelectedMapPosition, toMapFeatureCollection } from './map-data';

describe('map feature collection', () => {
  it('prefers aggregate points at far zoom', () => {
    const collection = toMapFeatureCollection({ success: true, mode: 'aggregates', properties: [{ id: 4, lat: 7.8, lng: 98.2 }], aggregates: [{ id: 'grid:1', lat: 7.9, lng: 98.3, count: 8 }], total_count: 8, viewport_count: 8, visible_count: 0, aggregate_count: 1, truncated: false, next_action: 'zoom_in', server_timing_ms: 1 });
    expect(collection.features[0]).toMatchObject({ geometry: { coordinates: [98.3, 7.9] }, properties: { count: 8, propertyId: 0, isAggregate: true } });
    expect(collection.features).toHaveLength(1);
  });

  it('includes the explicitly selected property alongside far-zoom aggregates', () => {
    const selectedProperty = { id: 7, slug: 'selected', lat: 7.7, lng: 98.4, title: 'Selected', price: '$1', property_type_label: 'Villa', location: 'Kathu', image_url: '', bedrooms: 3, bathrooms: 2, area: 100, url: '/en/property/selected/' };
    const collection = toMapFeatureCollection({ success: true, mode: 'aggregates', properties: [], selected_property: selectedProperty, aggregates: [{ id: 'grid:1', lat: 7.9, lng: 98.3, count: 8 }], total_count: 8, viewport_count: 8, visible_count: 0, aggregate_count: 1, truncated: false, next_action: 'zoom_in', server_timing_ms: 1 });

    expect(collection.features).toHaveLength(2);
    expect(collection.features[1]).toMatchObject({ geometry: { coordinates: [98.4, 7.7] }, properties: { propertyId: 7, isAggregate: false } });
  });

  it('keeps selected points clear of desktop and mobile cards', () => {
    expect(getSelectedMapPosition(98.3, 7.9, 1000, 600, false)).toEqual({ center: [98.3, 7.9], offset: [200, 0] });
    expect(getSelectedMapPosition(98.3, 7.9, 390, 800, true)).toEqual({ center: [98.3, 7.9], offset: [0, -144] });
  });
});
