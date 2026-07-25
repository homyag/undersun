import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useRef } from 'react';

import type { MapAppBootstrap } from '../../bootstrap';
import { serializeMapSearchState, type MapSearchState } from './state';

const CACHE_TTL_MS = 20_000;
const CACHE_MAX_ENTRIES = 24;

export type MapViewport = {
  north?: number;
  south?: number;
  east?: number;
  west?: number;
  zoom: number;
};

export type MapAggregate = {
  id: string;
  lat: number;
  lng: number;
  count: number;
};

export type MapMarker = {
  id: number;
  lat: number;
  lng: number;
};

export type MapProperty = MapMarker & {
  slug: string;
  title: string;
  price: string;
  property_type_label: string;
  location: string;
  image_url: string;
  bedrooms: number;
  bathrooms: number;
  area: number;
  agent_phone?: string;
  url: string;
};

export type MapPropertiesResponse = {
  success: true;
  mode: 'properties' | 'aggregates';
  sort?: 'recommended' | 'price_asc' | 'price_desc' | 'newest';
  properties: MapMarker[];
  selected_property_id?: number | null;
  selected_property?: MapProperty | null;
  aggregates: MapAggregate[];
  total_count: number;
  viewport_count: number;
  visible_count: number;
  aggregate_count: number;
  truncated: boolean;
  next_action: 'none' | 'zoom_in';
  server_timing_ms: number;
};

export type MapCardsResponse = {
  success: true;
  properties: MapProperty[];
  page: number;
  page_size: number;
  has_next: boolean;
  next_page: number | null;
  server_timing_ms: number;
};

export class MapApiError extends Error {
  constructor(public readonly status: number) {
    super(`Map properties request failed: ${status}`);
  }
}

type CacheEntry = {
  value: MapPropertiesResponse;
  expiresAt: number;
};

export class MapResponseCache {
  private entries = new Map<string, CacheEntry>();

  get(key: string, now = Date.now()): MapPropertiesResponse | null {
    const entry = this.entries.get(key);
    if (!entry || entry.expiresAt <= now) {
      this.entries.delete(key);
      return null;
    }
    this.entries.delete(key);
    this.entries.set(key, entry);
    return entry.value;
  }

  set(key: string, value: MapPropertiesResponse, now = Date.now()): void {
    this.entries.delete(key);
    this.entries.set(key, { value, expiresAt: now + CACHE_TTL_MS });
    while (this.entries.size > CACHE_MAX_ENTRIES) {
      const oldestKey = this.entries.keys().next().value;
      if (!oldestKey) {
        return;
      }
      this.entries.delete(oldestKey);
    }
  }

  clear(): void {
    this.entries.clear();
  }
}

const responseCache = new MapResponseCache();

export function clearMapResponseCache(): void {
  responseCache.clear();
}

export function getMapResponseCacheKey(url: string, currencyCode: string): string {
  return `${currencyCode}:${url}`;
}

function addViewportParams(params: URLSearchParams, viewport: MapViewport): void {
  const bounds = [viewport.north, viewport.south, viewport.east, viewport.west];
  if (bounds.every((value) => Number.isFinite(value))) {
    params.set('bounds_north', String(viewport.north));
    params.set('bounds_south', String(viewport.south));
    params.set('bounds_east', String(viewport.east));
    params.set('bounds_west', String(viewport.west));
  }
  params.set('zoom', String(viewport.zoom));
  params.set('map_mode', 'auto');
}

export function buildMapPropertiesUrl(
  bootstrap: MapAppBootstrap,
  searchState: MapSearchState,
  viewport: MapViewport,
): string {
  const url = new URL(bootstrap.endpoints.properties, window.location.origin);
  const params = serializeMapSearchState(searchState);
  addViewportParams(params, viewport);
  url.search = params.toString();
  return url.toString();
}

export function buildMapPropertyCardsUrl(
  bootstrap: MapAppBootstrap,
  searchState: MapSearchState,
  viewport: MapViewport,
  page = 1,
  propertyIds: number[] = [],
): string {
  const url = new URL(bootstrap.endpoints.cards, window.location.origin);
  const params = serializeMapSearchState({ ...searchState, selectedPropertyId: null });
  addViewportParams(params, viewport);
  if (propertyIds.length) {
    params.delete('page');
    propertyIds.forEach((propertyId) => params.append('ids', String(propertyId)));
  } else {
    params.set('page', String(page));
  }
  url.search = params.toString();
  return url.toString();
}

export async function fetchMapProperties(
  url: string,
  signal: AbortSignal,
  currencyCode = '',
): Promise<MapPropertiesResponse> {
  const cacheKey = getMapResponseCacheKey(url, currencyCode);
  const cached = responseCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const response = await fetch(url, {
    signal,
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (!response.ok) {
    throw new MapApiError(response.status);
  }

  const payload: unknown = await response.json();
  if (!payload || typeof payload !== 'object' || !('success' in payload) || payload.success !== true) {
    throw new Error('Map properties response has an invalid shape.');
  }

  const mapResponse = payload as MapPropertiesResponse;
  responseCache.set(cacheKey, mapResponse);
  return mapResponse;
}

async function fetchMapCards(url: string, signal: AbortSignal): Promise<MapCardsResponse> {
  const response = await fetch(url, {
    signal,
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  });
  if (!response.ok) throw new MapApiError(response.status);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== 'object' || !('success' in payload) || payload.success !== true) {
    throw new Error('Map cards response has an invalid shape.');
  }
  return payload as MapCardsResponse;
}

export function useMapProperties(
  bootstrap: MapAppBootstrap,
  searchState: MapSearchState,
  viewport: MapViewport,
  currencyCode: string,
  enabled = true,
) {
  const url = buildMapPropertiesUrl(bootstrap, searchState, viewport);

  const query = useQuery({
    queryKey: ['map-properties', bootstrap.language, currencyCode, url],
    queryFn: ({ signal }) => fetchMapProperties(url, signal, currencyCode),
    enabled,
    staleTime: CACHE_TTL_MS,
    gcTime: CACHE_TTL_MS * 6,
    placeholderData: keepPreviousData,
    retry: (failureCount, error) => !(error instanceof MapApiError && error.status < 500) && failureCount < 1,
  });
  const lastSuccessfulResponse = useRef<MapPropertiesResponse | undefined>(undefined);
  if (query.data) lastSuccessfulResponse.current = query.data;

  return {
    ...query,
    data: query.data ?? lastSuccessfulResponse.current,
  };
}

export function useMapPropertyCards(
  bootstrap: MapAppBootstrap,
  searchState: MapSearchState,
  viewport: MapViewport,
  currencyCode: string,
  enabled = true,
) {
  const initialUrl = buildMapPropertyCardsUrl(bootstrap, searchState, viewport);
  return useInfiniteQuery({
    queryKey: ['map-property-cards', bootstrap.language, currencyCode, initialUrl],
    queryFn: ({ signal, pageParam }) => fetchMapCards(buildMapPropertyCardsUrl(bootstrap, searchState, viewport, pageParam), signal),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next_page || undefined,
    enabled,
    staleTime: CACHE_TTL_MS,
    gcTime: CACHE_TTL_MS * 6,
    placeholderData: keepPreviousData,
  });
}

export function useMapPropertiesByIds(
  bootstrap: MapAppBootstrap,
  propertyIds: number[],
  currencyCode: string,
  enabled = true,
) {
  const ids = [...new Set(propertyIds)].sort((left, right) => left - right);
  const url = buildMapPropertyCardsUrl(bootstrap, { filters: { dealType: '', propertyTypes: [], buildStatus: '', district: '', location: '', minPrice: '', maxPrice: '', bedrooms: [], bathrooms: [], minArea: '', maxArea: '', amenities: [], query: '' }, sort: 'recommended', selectedPropertyId: null }, { zoom: bootstrap.map.zoom }, 1, ids);
  return useQuery({
    queryKey: ['map-property-cards-by-id', bootstrap.language, currencyCode, ids],
    queryFn: ({ signal }) => fetchMapCards(url, signal),
    enabled: enabled && ids.length > 0,
    staleTime: CACHE_TTL_MS,
  });
}
