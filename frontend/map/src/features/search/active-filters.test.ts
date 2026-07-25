import { describe, expect, it } from 'vitest';

import type { MapAppBootstrap } from '../../bootstrap';
import { getActiveFilterChips } from './active-filters';
import { EMPTY_MAP_SEARCH_STATE } from './state';

const bootstrap = { filters: { propertyTypes: [{ value: 'villa', label: 'Villa' }], districts: [{ value: 'kathu', label: 'Kathu', locations: [] }], buildStatuses: [{ value: 'ready', label: 'Ready' }], amenities: [{ value: 'pool', label: 'Pool' }] }, translations: { sale: 'Sale', rent: 'Rent', bedrooms: 'Bedrooms', priceFrom: 'From', priceTo: 'To' } } as unknown as MapAppBootstrap;

describe('active map filters', () => {
  it('creates independently removable chips', () => {
    const state = { ...EMPTY_MAP_SEARCH_STATE, filters: { ...EMPTY_MAP_SEARCH_STATE.filters, dealType: 'sale' as const, propertyTypes: ['villa'], district: 'kathu', location: 'rawai' } };
    const chips = getActiveFilterChips(bootstrap, state);

    expect(chips.map((chip) => chip.label)).toEqual(['Sale', 'Villa', 'Kathu', 'rawai']);
    expect(chips.find((chip) => chip.id === 'district')?.nextState.filters.location).toBe('');
  });

  it('keeps build status, amenities, and text search removable', () => {
    const state = {
      ...EMPTY_MAP_SEARCH_STATE,
      filters: {
        ...EMPTY_MAP_SEARCH_STATE.filters,
        buildStatus: 'ready',
        amenities: ['pool'],
        query: 'Kamala',
      },
    };
    const chips = getActiveFilterChips(bootstrap, state);

    expect(chips.map((chip) => chip.id)).toEqual(['build_status', 'amenities:pool', 'q']);
    expect(chips.find((chip) => chip.id === 'q')?.nextState.filters.query).toBe('');
  });
});
