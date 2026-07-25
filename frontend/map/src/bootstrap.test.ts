import { describe, expect, it } from 'vitest';

import { parseMapBootstrap } from './bootstrap';

const validBootstrap = {
  schemaVersion: 1,
  language: 'ru',
  currency: { code: 'RUB', symbol: 'RUB', decimalPlaces: 0 },
  endpoints: { properties: '/ru/property/ajax/map/', cards: '/ru/property/ajax/map/cards/', districts: '/ru/property/ajax/map-districts/' },
  map: {
    center: [98.3923, 7.8804],
    zoom: 10,
    aggregateMaxZoom: 10,
    styleUrl: 'https://tiles.openfreemap.org/styles/liberty',
  },
  featureFlags: { mapRebuild: true },
  filters: { propertyTypes: [], districts: [], buildStatuses: [], amenities: [] },
  translations: {
    loading: 'Loading',
    unavailable: 'Unavailable',
    viewCatalog: 'Catalog',
    filters: 'Filters', all: 'All', sale: 'Sale', rent: 'Rent', propertyType: 'Type', buildStatus: 'Status',
    district: 'District', location: 'Location', search: 'Search', searchPlaceholder: 'Search properties', bedrooms: 'Bedrooms', amenities: 'Amenities', amenitiesSearch: 'Find an amenity', priceFrom: 'From',
    priceTo: 'To', reset: 'Reset', results: 'Results',
    close: 'Close', showResults: 'Show results',
    noResults: 'Empty', retry: 'Retry', findLocation: 'Locate', locating: 'Locating',
    locationDenied: 'Denied', locationUnavailable: 'Unavailable',
    searchThisArea: 'Search this area', resetView: 'Reset map view',
    addFavorite: 'Save', removeFavorite: 'Remove',
  },
};

describe('parseMapBootstrap', () => {
  it('accepts the server bootstrap contract', () => {
    expect(parseMapBootstrap(JSON.stringify(validBootstrap))).toMatchObject(validBootstrap);
  });

  it('rejects an unsupported schema version', () => {
    expect(() => parseMapBootstrap(JSON.stringify({ ...validBootstrap, schemaVersion: 2 })))
      .toThrow('schema version');
  });

  it('accepts catalog-mode defaults', () => {
    const catalogBootstrap = {
      ...validBootstrap,
      initialDealType: 'sale',
      catalog: { url: '/ru/property/sale/', label: 'List', filterDrawerInitiallyCollapsed: false },
    };

    expect(parseMapBootstrap(JSON.stringify(catalogBootstrap))).toMatchObject(catalogBootstrap);
  });
});
