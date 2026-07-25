import { describe, expect, it, vi } from 'vitest';

import {
  buildMapSearchUrl,
  parseMapSearchState,
  replaceMapSearchState,
  serializeMapSearchState,
  subscribeToMapSearchState,
} from './state';

describe('MapSearchState URL contract', () => {
  it('parses and serializes supported map filters deterministically', () => {
    const state = parseMapSearchState(
      '?deal_type=sale&property_type=villa&property_type=condo&district=thalang' +
      '&bedrooms=3&bedrooms=2&bathrooms=4%2B&bathrooms=2&min_area=80&max_area=200&amenities=9&amenities=4&q=  sea+view  &selected=42',
    );

    expect(state).toMatchObject({
      filters: {
        dealType: 'sale',
        propertyTypes: ['condo', 'villa'],
        district: 'thalang',
        bedrooms: ['2', '3'],
        bathrooms: ['2', '4+'],
        minArea: '80',
        maxArea: '200',
        amenities: ['4', '9'],
        query: 'sea view',
      },
      sort: 'recommended',
      selectedPropertyId: 42,
    });
    expect(serializeMapSearchState(state).toString())
      .toBe('deal_type=sale&property_type=condo&property_type=villa&district=thalang&bedrooms=2&bedrooms=3&bathrooms=2&bathrooms=4%2B&min_area=80&max_area=200&amenities=4&amenities=9&q=sea+view&selected=42');
  });

  it('persists only supported server-side sort values', () => {
    expect(parseMapSearchState('?sort=price_desc').sort).toBe('price_desc');
    expect(parseMapSearchState('?sort=not-a-sort').sort).toBe('recommended');
    expect(serializeMapSearchState({ ...parseMapSearchState(''), sort: 'newest' }).toString())
      .toBe('sort=newest');
  });

  it('does not expose viewport data and discards invalid selected ids', () => {
    const state = parseMapSearchState('?selected=abc&zoom=9&bounds_north=8.2');

    expect(state.selectedPropertyId).toBeNull();
    expect(buildMapSearchUrl(state, new URL('https://example.test/ru/map/?zoom=9')))
      .toBe('/ru/map/');
  });

  it('restores state on browser back-forward navigation', () => {
    window.history.replaceState(null, '', '/ru/map/?district=kathu');
    const callback = vi.fn();
    const unsubscribe = subscribeToMapSearchState(callback);

    window.history.pushState(null, '', '/ru/map/?district=thalang&selected=7');
    window.dispatchEvent(new PopStateEvent('popstate'));

    expect(callback).toHaveBeenCalledWith(expect.objectContaining({
      selectedPropertyId: 7,
      filters: expect.objectContaining({ district: 'thalang' }),
    }));
    unsubscribe();
  });

  it('replaces the current URL without a page reload', () => {
    const state = parseMapSearchState('?location=rawai');
    replaceMapSearchState(state);

    expect(window.location.search).toBe('?location=rawai');
  });

  it('keeps the catalogue map mode while changing filters', () => {
    const state = parseMapSearchState('?map_view=true&district=kathu');

    expect(buildMapSearchUrl(state, new URL('https://example.test/en/property/?map_view=true&district=kathu')))
      .toBe('/en/property/?district=kathu&map_view=true');
  });
});
