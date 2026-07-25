import type { MapAppBootstrap } from '../../bootstrap';
import type { MapSearchState } from './state';

export type ActiveFilterChip = {
  id: string;
  label: string;
  nextState: MapSearchState;
};

export function getActiveFilterChips(
  bootstrap: MapAppBootstrap,
  state: MapSearchState,
): ActiveFilterChip[] {
  const { filters } = state;
  const chips: ActiveFilterChip[] = [];
  const removeListValue = (key: 'propertyTypes' | 'bedrooms' | 'bathrooms' | 'amenities', value: string) => ({
    ...state,
    filters: { ...filters, [key]: filters[key].filter((item) => item !== value) },
  });

  if (filters.dealType) {
    chips.push({ id: 'deal_type', label: filters.dealType === 'sale' ? bootstrap.translations.sale : bootstrap.translations.rent, nextState: { ...state, filters: { ...filters, dealType: '' } } });
  }
  filters.propertyTypes.forEach((value) => {
    const label = bootstrap.filters.propertyTypes.find((option) => option.value === value)?.label || value;
    chips.push({ id: `property_type:${value}`, label, nextState: removeListValue('propertyTypes', value) });
  });
  filters.bedrooms.forEach((value) => chips.push({ id: `bedrooms:${value}`, label: `${value} ${bootstrap.translations.bedrooms}`, nextState: removeListValue('bedrooms', value) }));
  filters.bathrooms.forEach((value) => chips.push({ id: `bathrooms:${value}`, label: `${value} ${bootstrap.translations.bathrooms || 'Bathrooms'}`, nextState: removeListValue('bathrooms', value) }));
  if (filters.district) {
    const label = bootstrap.filters.districts.find((option) => option.value === filters.district)?.label || filters.district;
    chips.push({ id: 'district', label, nextState: { ...state, filters: { ...filters, district: '', location: '' } } });
  }
  if (filters.location) chips.push({ id: 'location', label: filters.location, nextState: { ...state, filters: { ...filters, location: '' } } });
  if (filters.minPrice) chips.push({ id: 'min_price', label: `${bootstrap.translations.priceFrom} ${filters.minPrice}`, nextState: { ...state, filters: { ...filters, minPrice: '' } } });
  if (filters.maxPrice) chips.push({ id: 'max_price', label: `${bootstrap.translations.priceTo} ${filters.maxPrice}`, nextState: { ...state, filters: { ...filters, maxPrice: '' } } });
  if (filters.minArea) chips.push({ id: 'min_area', label: `${bootstrap.translations.areaFrom || 'Area from'} ${filters.minArea}`, nextState: { ...state, filters: { ...filters, minArea: '' } } });
  if (filters.maxArea) chips.push({ id: 'max_area', label: `${bootstrap.translations.areaTo || 'Area to'} ${filters.maxArea}`, nextState: { ...state, filters: { ...filters, maxArea: '' } } });
  if (filters.buildStatus) {
    const label = bootstrap.filters.buildStatuses.find((option) => option.value === filters.buildStatus)?.label || filters.buildStatus;
    chips.push({ id: 'build_status', label, nextState: { ...state, filters: { ...filters, buildStatus: '' } } });
  }
  filters.amenities.forEach((value) => {
    const label = bootstrap.filters.amenities.find((option) => option.value === value)?.label || value;
    chips.push({ id: `amenities:${value}`, label, nextState: removeListValue('amenities', value) });
  });
  if (filters.query) chips.push({ id: 'q', label: filters.query, nextState: { ...state, filters: { ...filters, query: '' } } });
  return chips;
}
