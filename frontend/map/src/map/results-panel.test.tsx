import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ResultsPanel } from './results-panel';

const property = { id: 1, slug: 'villa', lat: 7.9, lng: 98.3, title: 'Villa', price: '$100', property_type_label: 'Villa', location: 'Kathu', image_url: '', bedrooms: 3, bathrooms: 2, area: 120, url: '/en/property/villa/' };

const labels = {
  resultsLabel: 'Results', inListLabel: 'In list', onMapLabel: 'On map', inAreaLabel: 'In area', totalLabel: 'Total', zoomToSeeAllLabel: 'Zoom in to see all properties', onSelect: vi.fn(), onHover: vi.fn(), onFocusProperty: vi.fn(),
  sort: 'recommended' as const, sortLabel: 'Sort', sortOptions: { recommended: 'Recommended', price_asc: 'Price: low to high', price_desc: 'Price: high to low', newest: 'Newest' }, onSortChange: vi.fn(),
  hasNextPage: false, isLoadingNextPage: false, onLoadNextPage: vi.fn(),
};

describe('ResultsPanel', () => {
  it('separates list, map-area, and filter-total counts', () => {
    render(<ResultsPanel {...labels} properties={[property]} selectedPropertyId={null} highlightedPropertyId={null} response={{ success: true, mode: 'properties', properties: [property], aggregates: [], total_count: 12, viewport_count: 8, visible_count: 4, aggregate_count: 0, truncated: false, next_action: 'none', server_timing_ms: 1 }} />);

    expect(screen.getByText('1 In list')).toBeInTheDocument();
    expect(screen.getByText('4 On map')).toBeInTheDocument();
    expect(screen.getByText('8 In area')).toBeInTheDocument();
    expect(screen.getByText('12 Total')).toBeInTheDocument();
  });

  it('does not present aggregate mode as an empty list', () => {
    render(<ResultsPanel {...labels} properties={[]} selectedPropertyId={null} highlightedPropertyId={null} response={{ success: true, mode: 'aggregates', properties: [], aggregates: [{ id: 'grid:1', lat: 7.9, lng: 98.3, count: 50 }], total_count: 80, viewport_count: 50, visible_count: 0, aggregate_count: 1, truncated: false, next_action: 'zoom_in', server_timing_ms: 1 }} />);

    expect(screen.getByText('50 In area')).toBeInTheDocument();
    expect(screen.getByText('80 Total')).toBeInTheDocument();
    expect(screen.getByText('Zoom in to see all properties')).toBeInTheDocument();
    expect(screen.queryByText('0 In list')).not.toBeInTheDocument();
  });

  it('uses a server-backed sort control', () => {
    const onSortChange = vi.fn();
    const { container } = render(<ResultsPanel {...labels} onSortChange={onSortChange} properties={[property]} selectedPropertyId={null} highlightedPropertyId={null} response={undefined} />);
    const sortSelect = container.querySelector('select');

    expect(sortSelect).not.toBeNull();
    fireEvent.change(sortSelect!, { target: { value: 'price_desc' } });
    expect(onSortChange).toHaveBeenCalledWith('price_desc');
  });

  it('links card hover and keyboard focus to marker highlighting without selecting', () => {
    const onHover = vi.fn();
    const onFocusProperty = vi.fn();
    const { container } = render(<ResultsPanel {...labels} onHover={onHover} onFocusProperty={onFocusProperty} properties={[property]} selectedPropertyId={null} highlightedPropertyId={property.id} response={undefined} />);
    const card = container.querySelector<HTMLButtonElement>('.map-results-panel__card')!;

    expect(card).toHaveClass('is-highlighted');
    fireEvent.mouseEnter(card);
    fireEvent.focus(card);
    fireEvent.mouseLeave(card);
    fireEvent.blur(card);

    expect(onHover).toHaveBeenNthCalledWith(1, property.id);
    expect(onFocusProperty).toHaveBeenNthCalledWith(1, property.id);
    expect(onHover).toHaveBeenNthCalledWith(2, null);
    expect(onFocusProperty).toHaveBeenNthCalledWith(2, null);
  });

  it('loads the next server page only when the list reaches its end', () => {
    const onLoadNextPage = vi.fn();
    const { container } = render(<ResultsPanel {...labels} onLoadNextPage={onLoadNextPage} hasNextPage properties={[property]} selectedPropertyId={null} highlightedPropertyId={null} response={undefined} />);
    const panel = container.querySelector<HTMLElement>('.map-results-panel')!;
    Object.defineProperties(panel, {
      scrollTop: { configurable: true, value: 400 },
      clientHeight: { configurable: true, value: 200 },
      scrollHeight: { configurable: true, value: 700 },
    });

    fireEvent.scroll(panel);
    expect(onLoadNextPage).toHaveBeenCalledOnce();
  });
});
