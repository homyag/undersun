import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MobilePropertySheet } from './mobile-property-sheet';

describe('MobilePropertySheet', () => {
  it('renders the property actions without an in-popup favorite button', () => {
    render(<MobilePropertySheet closeLabel="Close" onClose={() => undefined} property={{ id: 8, slug: 'villa', lat: 7.9, lng: 98.3, title: 'Villa', price: '$100', property_type_label: 'Villa', location: 'Kathu', image_url: '', bedrooms: 3, bathrooms: 2, area: 120, url: '/en/property/villa/' }} />);
    expect(screen.getByRole('link', { name: 'WhatsApp' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
  });
});
