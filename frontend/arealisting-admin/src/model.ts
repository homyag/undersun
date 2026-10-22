export type FieldValue = string | number | boolean | null;
export type Unit = {
  id: number; number: string; bedrooms: number | null; bathrooms?: number | null;
  area_total: number | null; floor: number | null; price: number | null;
  currency: string; property_type: string; status: string; skipped: boolean;
  skip_reason: string; property: number | null; occupied: boolean;
  [key: string]: FieldValue | undefined;
};
export type Property = {
  id: number; title: string; is_active: boolean; original_units: number[];
  managed_fields: string[]; locked_fields: string[]; photo: string; url: string;
  values: Record<string, FieldValue>;
};
export type MatchingData = {
  project: number; user: number; project_values: Record<string, FieldValue>;
  project_field_keys: string[]; can_create_draft: boolean;
  fields: Record<string, string>; properties: Property[]; units: Unit[];
};
export type RowState = { title: string; units: number[]; active: boolean; fields: string[] };
export type SavedRows = Record<string, RowState>;
export type SourceValue = { available: true; value: FieldValue } | { available: false; reason: string };

export function sourceFieldValue(data: MatchingData, key: string, units: Unit[]): SourceValue {
  if (data.project_field_keys.includes(key)) {
    if (Object.hasOwn(data.project_values, key)) return { available: true, value: data.project_values[key] };
    return { available: false, reason: key === 'year_built'
      ? 'Год доступен только для завершённого проекта с датой окончания.'
      : 'У проекта нет данных для этого поля.' };
  }
  if (!units.length) return { available: false, reason: 'Сначала выберите предложение.' };
  const values = units.map(unit => unit[key]);
  if (values.some(value => value === null || value === undefined || value === '')) {
    return { available: false, reason: 'Нет значения у одного или нескольких предложений.' };
  }
  if (new Set(values).size !== 1) return { available: false, reason: 'У выбранных предложений разные значения.' };
  return { available: true, value: values[0] as FieldValue };
}

export function fieldLocked(property: Property, key: string): boolean {
  return property.locked_fields.includes(key) || property.locked_fields.includes(key.replace(/_(ru|en)$/, ''));
}

export function rowChanged(property: Property, row: RowState, projectUnits = property.original_units): boolean {
  const original = [...projectUnits].sort((a, b) => a - b);
  const selected = [...row.units].sort((a, b) => a - b);
  return selected.join(',') !== original.join(',')
    || (selected.length > 0 && row.active !== property.is_active)
    || (selected.length > 0 && [...row.fields].sort().join(',') !== [...property.managed_fields].sort().join(','));
}

export function buildSaveRow(data: MatchingData, property: Property, row: RowState) {
  const units = data.units.filter(unit => row.units.includes(unit.id));
  const managedFields = [...new Set(row.fields)].filter(key => Object.hasOwn(data.fields, key));
  const expected: Record<string, { before: FieldValue; after: FieldValue }> = {};
  for (const key of managedFields) {
    const source = sourceFieldValue(data, key, units);
    if (source.available && !fieldLocked(property, key)) {
      expected[key] = { before: property.values[key], after: source.value };
    }
  }
  return {
    property: property.id, original_units: property.original_units,
    original_managed_fields: property.managed_fields, units: row.units,
    fields: Object.keys(expected), managed_fields: managedFields,
    expected, is_active: row.active, expected_is_active: property.is_active,
  };
}
