import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import 'maplibre-gl/dist/maplibre-gl.css';

import './styles.css';

import { MapApp } from './app';
import type { MapAppBootstrap } from './bootstrap';

const bootstrap: MapAppBootstrap = {
  schemaVersion: 1, language: 'en', currency: { code: 'USD', symbol: '$', decimalPlaces: 2 },
  endpoints: { properties: '/en/property/ajax/map/', cards: '/en/property/ajax/map/cards/', districts: '/en/property/ajax/map-districts/' },
  map: { center: [98.3923, 7.8804], zoom: 10, aggregateMaxZoom: 10, styleUrl: 'https://tiles.openfreemap.org/styles/liberty' },
  featureFlags: { mapRebuild: true },
  filters: { propertyTypes: [{ value: 'villa', label: 'Villa' }, { value: 'condo', label: 'Condo' }], districts: [{ value: 'kathu', label: 'Kathu', locations: [{ value: 'kamala', label: 'Kamala' }] }], buildStatuses: [{ value: 'ready', label: 'Ready' }], amenities: [{ value: '1', label: 'Pool' }] },
  translations: { loading: 'Loading', unavailable: 'Unavailable', viewCatalog: 'Catalog', filters: 'Filters', all: 'All', sale: 'Sale', rent: 'Rent', propertyType: 'Property type', buildStatus: 'Status', district: 'District', location: 'Location', search: 'Search', searchPlaceholder: 'Search properties', bedrooms: 'Bedrooms', amenities: 'Amenities', amenitiesSearch: 'Find an amenity', priceFrom: 'From', priceTo: 'To', reset: 'Reset', results: 'Results', inList: 'In list', onMap: 'On map', inArea: 'In area', total: 'Total', zoomToSeeAll: 'Zoom in to see all properties', close: 'Close', showResults: 'Show results', noResults: 'Empty', retry: 'Retry', findLocation: 'Locate', locating: 'Locating', locationDenied: 'Denied', locationUnavailable: 'Unavailable', searchThisArea: 'Search this area', resetView: 'Reset map view', addFavorite: 'Save', removeFavorite: 'Remove' },
};

createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MapApp bootstrap={bootstrap} /></QueryClientProvider>);
