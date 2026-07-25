import { describe, expect, it } from 'vitest';

import { createPropertyPopupContent } from './property-popup-dom';

describe('property popup DOM content', () => {
  it('creates a complete static popup without a nested React root', () => {
    const container = document.createElement('div');
    container.appendChild(createPropertyPopupContent({
      id: 7,
      slug: 'test-property',
      lat: 7.8,
      lng: 98.3,
      title: 'Test property',
      price: '$100,000',
      property_type_label: 'Villa',
      location: 'Kathu',
      image_url: 'https://example.test/image.jpg',
      bedrooms: 3,
      bathrooms: 2,
      area: 99.8,
      url: '/en/property/test-property/',
      agent_phone: '+66 63 303 3133',
    }, {
      addFavorite: 'Save',
      removeFavorite: 'Remove',
      moreDetails: 'Details',
      bedroomsLabel: 'Bedrooms',
      bathroomsLabel: 'Bathrooms',
      areaLabel: 'Area',
    }));

    expect(container.querySelector('.map-property-popup__title')?.textContent).toBe('Test property');
    expect(container.querySelector('.map-property-popup__meta')?.textContent).toContain('Area100 m2');
    expect(container.querySelector<HTMLAnchorElement>('.map-property-popup__whatsapp')?.href).toContain('wa.me/66633033133');
  });
});
