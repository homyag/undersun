import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { MapAppBootstrap } from '../../bootstrap';
import { MobileFilterSheet } from './mobile-filter-sheet';
import { EMPTY_MAP_SEARCH_STATE } from './state';

const bootstrap = { filters: { propertyTypes: [], districts: [] }, translations: { filters: 'Filters', close: 'Close', showResults: 'Show results', reset: 'Reset', results: 'Results', all: 'All', sale: 'Sale', rent: 'Rent', propertyType: 'Type', priceFrom: 'From', priceTo: 'To', bedrooms: 'Bedrooms', district: 'District', location: 'Location' } } as unknown as MapAppBootstrap;

describe('MobileFilterSheet', () => {
  it('locks scrolling and closes on Escape', () => {
    const onClose = vi.fn();
    render(<MobileFilterSheet bootstrap={bootstrap} state={EMPTY_MAP_SEARCH_STATE} resultCount={3} resultCountLabel="On map" onChange={vi.fn()} onClose={onClose} />);

    expect(document.body.style.overflow).toBe('hidden');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
