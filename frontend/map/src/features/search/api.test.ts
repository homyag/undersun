import { createElement, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { MapAppBootstrap } from '../../bootstrap';
import {
  buildMapPropertiesUrl,
  fetchMapProperties,
  getMapResponseCacheKey,
  MapResponseCache,
  type MapPropertiesResponse,
  useMapProperties,
} from './api';
import { EMPTY_MAP_SEARCH_STATE } from './state';

const bootstrap: MapAppBootstrap = {
  schemaVersion: 1,
  language: 'ru',
  currency: { code: 'RUB', symbol: 'RUB', decimalPlaces: 0 },
  endpoints: { properties: '/ru/property/ajax/map/', cards: '/ru/property/ajax/map/cards/', districts: '/ru/property/ajax/map-districts/' },
  map: { center: [98.3923, 7.8804], zoom: 10, aggregateMaxZoom: 10, styleUrl: 'https://tiles.openfreemap.org/styles/liberty' },
  featureFlags: { mapRebuild: true },
  filters: { propertyTypes: [], districts: [], buildStatuses: [], amenities: [] },
  translations: { loading: 'Loading', unavailable: 'Unavailable', viewCatalog: 'Catalog', filters: 'Filters', all: 'All', sale: 'Sale', rent: 'Rent', propertyType: 'Type', buildStatus: 'Status', district: 'District', location: 'Location', search: 'Search', searchPlaceholder: 'Search properties', bedrooms: 'Bedrooms', amenities: 'Amenities', amenitiesSearch: 'Find an amenity', priceFrom: 'From', priceTo: 'To', reset: 'Reset', results: 'Results', close: 'Close', showResults: 'Show results', noResults: 'Empty', retry: 'Retry', findLocation: 'Locate', locating: 'Locating', locationDenied: 'Denied', locationUnavailable: 'Unavailable', searchThisArea: 'Search this area', resetView: 'Reset map view', addFavorite: 'Save', removeFavorite: 'Remove' },
};

describe('map properties query', () => {
  it('builds a same-origin auto-mode request from typed state', () => {
    const url = buildMapPropertiesUrl(bootstrap, {
      ...EMPTY_MAP_SEARCH_STATE,
      filters: { ...EMPTY_MAP_SEARCH_STATE.filters, district: 'kathu' },
    }, { north: 8.1, south: 7.8, east: 98.5, west: 98.2, zoom: 9 });

    expect(url).toContain('/ru/property/ajax/map/?district=kathu');
    expect(url).toContain('map_mode=auto');
    expect(url).toContain('zoom=9');
  });

  it('uses a short-lived LRU response cache', () => {
    const cache = new MapResponseCache();
    const value: MapPropertiesResponse = { success: true, mode: 'aggregates', properties: [], aggregates: [], total_count: 0, viewport_count: 0, visible_count: 0, aggregate_count: 0, truncated: false, next_action: 'none', server_timing_ms: 1 };
    cache.set('a', value, 100);

    expect(cache.get('a', 101)).toBe(value);
    expect(cache.get('a', 20_101)).toBeNull();
  });

  it('keeps cached responses separate for each currency', () => {
    const cache = new MapResponseCache();
    const value: MapPropertiesResponse = { success: true, mode: 'aggregates', properties: [], aggregates: [], total_count: 0, viewport_count: 0, visible_count: 0, aggregate_count: 0, truncated: false, next_action: 'none', server_timing_ms: 1 };
    const url = 'https://example.test/map';
    cache.set(getMapResponseCacheKey(url, 'USD'), value);

    expect(cache.get(getMapResponseCacheKey(url, 'USD'))).toBe(value);
    expect(cache.get(getMapResponseCacheKey(url, 'THB'))).toBeNull();
  });

  it('passes an abort signal to fetch', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      success: true, mode: 'aggregates', properties: [], aggregates: [], total_count: 0,
      viewport_count: 0, visible_count: 0, aggregate_count: 0, truncated: false, next_action: 'none',
    })));
    const controller = new AbortController();

    await fetchMapProperties('https://example.test/map', controller.signal);

    expect(fetchMock).toHaveBeenCalledWith('https://example.test/map', expect.objectContaining({ signal: controller.signal }));
    fetchMock.mockRestore();
  });

  it('keeps the last successful response visible during a new request', async () => {
    const initialResponse: MapPropertiesResponse = { success: true, mode: 'properties', properties: [], aggregates: [], total_count: 4, viewport_count: 4, visible_count: 4, aggregate_count: 0, truncated: false, next_action: 'none', server_timing_ms: 1 };
    const nextResponse: MapPropertiesResponse = { ...initialResponse, total_count: 2, viewport_count: 2, visible_count: 2 };
    let resolveNextResponse: ((response: Response) => void) | undefined;
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(initialResponse)))
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveNextResponse = resolve; }));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client: queryClient }, children);
    const viewport = { zoom: 10 };
    const { result, rerender } = renderHook(
      ({ state }) => useMapProperties(bootstrap, state, viewport, 'RUB'),
      { initialProps: { state: EMPTY_MAP_SEARCH_STATE }, wrapper },
    );

    await waitFor(() => expect(result.current.data).toEqual(initialResponse));
    rerender({ state: { ...EMPTY_MAP_SEARCH_STATE, filters: { ...EMPTY_MAP_SEARCH_STATE.filters, district: 'kathu' } } });

    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.data).toEqual(initialResponse);

    resolveNextResponse?.(new Response(JSON.stringify(nextResponse)));
    await waitFor(() => expect(result.current.data).toEqual(nextResponse));
    fetchMock.mockRestore();
  });

  it('keeps the last successful response after a replacement request fails', async () => {
    const initialResponse: MapPropertiesResponse = { success: true, mode: 'properties', properties: [], aggregates: [], total_count: 4, viewport_count: 4, visible_count: 4, aggregate_count: 0, truncated: false, next_action: 'none', server_timing_ms: 1 };
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(initialResponse)))
      .mockResolvedValueOnce(new Response('', { status: 400 }));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client: queryClient }, children);
    const viewport = { zoom: 10 };
    const { result, rerender } = renderHook(
      ({ state }) => useMapProperties(bootstrap, state, viewport, 'THB'),
      { initialProps: { state: EMPTY_MAP_SEARCH_STATE }, wrapper },
    );

    await waitFor(() => expect(result.current.data).toEqual(initialResponse));
    rerender({ state: { ...EMPTY_MAP_SEARCH_STATE, filters: { ...EMPTY_MAP_SEARCH_STATE.filters, district: 'kathu' } } });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toEqual(initialResponse);
    fetchMock.mockRestore();
  });
});
