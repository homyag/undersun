import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { MapAppBootstrap } from '../../bootstrap';
import { FilterSidebar } from './filter-sidebar';
import { EMPTY_MAP_SEARCH_STATE } from './state';

const bootstrap = {
  filters: { propertyTypes: [], districts: [], buildStatuses: [], amenities: [] },
  translations: {
    filters: 'Filters', reset: 'Reset', results: 'Results', all: 'All', sale: 'Sale', rent: 'Rent',
    propertyType: 'Type', buildStatus: 'Status', priceFrom: 'From', priceTo: 'To', search: 'Search',
    searchPlaceholder: 'Search properties', bedrooms: 'Bedrooms', bathrooms: 'Bathrooms', area: 'Area', areaFrom: 'Area from', areaTo: 'Area to', district: 'District', location: 'Location',
    amenities: 'Amenities', amenitiesSearch: 'Find an amenity',
  },
} as unknown as MapAppBootstrap;

afterEach(() => vi.useRealTimers());

describe('FilterSidebar debounce', () => {
  it('does not emit a filter change merely because the sidebar mounted', () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<FilterSidebar bootstrap={bootstrap} state={EMPTY_MAP_SEARCH_STATE} resultCount={1} resultCountLabel="On map" onChange={onChange} />);

    act(() => vi.advanceTimersByTime(500));
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '1000000' } });
    act(() => vi.advanceTimersByTime(450));
    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange.mock.calls[0][0].filters.minPrice).toBe('1000000');
  });

  it('adds bathroom and total-area filters to the map state', () => {
    const onChange = vi.fn();
    const { container } = render(<FilterSidebar bootstrap={bootstrap} state={EMPTY_MAP_SEARCH_STATE} resultCount={1} resultCountLabel="On map" onChange={onChange} />);

    fireEvent.click(within(container.querySelectorAll<HTMLElement>('.map-filter-sidebar__option-group')[1]).getByLabelText('4+'));
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      filters: expect.objectContaining({ bathrooms: ['4+'] }),
    }));
    expect(within(container.querySelector('.map-filter-sidebar__area')!).getByText('Area, m²')).toBeInTheDocument();
  });
});
