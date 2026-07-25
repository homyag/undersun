import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PropertyPreview } from './property-preview';

describe('PropertyPreview', () => {
  it('focuses its close button and links to detail', () => {
    render(<PropertyPreview closeLabel="Close" onClose={vi.fn()} property={{ id: 1, slug: 'villa', lat: 7.9, lng: 98.3, title: 'Villa', price: '$100', property_type_label: 'Villa', location: 'Kathu', image_url: '', bedrooms: 3, bathrooms: 2, area: 120, url: '/en/property/villa/' }} />);
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
    expect(screen.getByRole('link', { name: 'Villa' })).toHaveAttribute('href', '/en/property/villa/');
  });
});
