import { describe, expect, it } from 'vitest';
import { buildSaveRow, rowChanged, sourceFieldValue } from './model';
import type { MatchingData, Property, Unit } from './model';

const property: Property = {
  id: 3, title: 'Карточка', is_active: true, original_units: [1], managed_fields: ['bedrooms'],
  locked_fields: ['area_total'], photo: '', url: '', values: { bedrooms: 2, area_total: 80, year_built: null },
};
const units: Unit[] = [
  { id: 1, number: 'A', bedrooms: 2, area_total: 80, floor: 1, price: 100, currency: 'THB',
    property_type: 'CONDO', status: 'AVAILABLE', skipped: false, skip_reason: '', property: 3, occupied: true },
  { id: 2, number: 'B', bedrooms: 3, area_total: 81, floor: 2, price: 110, currency: 'THB',
    property_type: 'CONDO', status: 'AVAILABLE', skipped: false, skip_reason: '', property: null, occupied: false },
];
const data: MatchingData = {
  project: 7, user: 9, project_values: { year_built: 2026 }, project_field_keys: ['year_built'],
  can_create_draft: true, fields: { bedrooms: 'Спальни', area_total: 'Площадь', year_built: 'Год' },
  properties: [property], units,
};

describe('matching payload', () => {
  it('rejects a field when selected units disagree', () => {
    expect(sourceFieldValue(data, 'bedrooms', units)).toMatchObject({ available: false });
    expect(sourceFieldValue(data, 'year_built', units)).toEqual({ available: true, value: 2026 });
  });

  it('sends only unlocked available values while retaining ownership choices', () => {
    const row = buildSaveRow(data, property, { title: property.title, units: [1], active: false,
      fields: ['bedrooms', 'area_total', 'year_built'] });
    expect(row.fields).toEqual(['bedrooms', 'year_built']);
    expect(row.managed_fields).toEqual(['bedrooms', 'area_total', 'year_built']);
    expect(row.expected).toEqual({ bedrooms: { before: 2, after: 2 }, year_built: { before: null, after: 2026 } });
    expect(row.expected_is_active).toBe(true);
  });

  it('keeps a changed link even when no field is selected', () => {
    expect(rowChanged(property, { title: property.title, units: [2], active: true, fields: ['bedrooms'] })).toBe(true);
    expect(rowChanged(property, { title: property.title, units: [1], active: true, fields: ['bedrooms'] })).toBe(false);
  });
});
