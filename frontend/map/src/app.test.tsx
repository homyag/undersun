import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { MapApp } from './app';

describe('MapApp', () => {
  it('renders the bootstrap shell', () => {
    render(<QueryClientProvider client={new QueryClient()}><MapApp queryEnabled={false} mapEnabled={false} bootstrap={{
      schemaVersion: 1,
      language: 'en',
      currency: { code: 'USD', symbol: '$', decimalPlaces: 2 },
      endpoints: { properties: '/en/property/ajax/map/', cards: '/en/property/ajax/map/cards/', districts: '/en/property/ajax/map-districts/' },
      map: {
        center: [98.3923, 7.8804],
        zoom: 10,
        aggregateMaxZoom: 10,
        styleUrl: 'https://tiles.openfreemap.org/styles/liberty',
      },
      featureFlags: { mapRebuild: true },
      filters: { propertyTypes: [], districts: [], buildStatuses: [], amenities: [] },
      translations: {
        loading: 'Loading map',
        unavailable: 'Map unavailable',
        viewCatalog: 'View catalog',
        filters: 'Filters', all: 'All', sale: 'Sale', rent: 'Rent', propertyType: 'Type', buildStatus: 'Status',
        district: 'District', location: 'Location', search: 'Search', searchPlaceholder: 'Search properties', bedrooms: 'Bedrooms', amenities: 'Amenities', amenitiesSearch: 'Find an amenity', priceFrom: 'From',
        priceTo: 'To', reset: 'Reset', results: 'Results',
        close: 'Close', showResults: 'Show results',
        noResults: 'Empty', retry: 'Retry', findLocation: 'Locate', locating: 'Locating',
        locationDenied: 'Denied', locationUnavailable: 'Unavailable',
        searchThisArea: 'Search this area', resetView: 'Reset map view',
        addFavorite: 'Save', removeFavorite: 'Remove',
      },
    }} /></QueryClientProvider>);

    expect(screen.getByText('Loading map')).toBeInTheDocument();
  });

  it('adopts the current header currency without resetting the map shell', () => {
    const { container } = render(<QueryClientProvider client={new QueryClient()}><MapApp queryEnabled={false} mapEnabled={false} bootstrap={{
      schemaVersion: 1,
      language: 'en',
      currency: { code: 'USD', symbol: '$', decimalPlaces: 2 },
      endpoints: { properties: '/en/property/ajax/map/', cards: '/en/property/ajax/map/cards/', districts: '/en/property/ajax/map-districts/' },
      map: { center: [98.3923, 7.8804], zoom: 10, aggregateMaxZoom: 10, styleUrl: 'https://tiles.openfreemap.org/styles/liberty' },
      featureFlags: { mapRebuild: true },
      filters: { propertyTypes: [], districts: [], buildStatuses: [], amenities: [] },
      translations: {
        loading: 'Loading map', unavailable: 'Map unavailable', viewCatalog: 'View catalog', filters: 'Filters', all: 'All', sale: 'Sale', rent: 'Rent', propertyType: 'Type', buildStatus: 'Status',
        district: 'District', location: 'Location', search: 'Search', searchPlaceholder: 'Search properties', bedrooms: 'Bedrooms', amenities: 'Amenities', amenitiesSearch: 'Find an amenity', priceFrom: 'From',
        priceTo: 'To', reset: 'Reset', results: 'Results', close: 'Close', showResults: 'Show results', noResults: 'Empty', retry: 'Retry', findLocation: 'Locate', locating: 'Locating',
        locationDenied: 'Denied', locationUnavailable: 'Unavailable', searchThisArea: 'Search this area', resetView: 'Reset map view', addFavorite: 'Save', removeFavorite: 'Remove',
      },
    }} /></QueryClientProvider>);

    const map = container.querySelector('main');
    expect(map).not.toBeNull();
    expect(map).toHaveAttribute('data-map-currency', 'USD');
    fireEvent(window, new CustomEvent('currencyChanged', { detail: { currency: 'THB', symbol: '฿' } }));
    expect(map).toHaveAttribute('data-map-currency', 'THB');
  });
});
