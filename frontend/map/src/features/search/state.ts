export type MapFilters = {
  dealType: '' | 'sale' | 'rent';
  propertyTypes: string[];
  buildStatus: string;
  district: string;
  location: string;
  minPrice: string;
  maxPrice: string;
  bedrooms: string[];
  bathrooms: string[];
  minArea: string;
  maxArea: string;
  amenities: string[];
  query: string;
};

export type MapSearchState = {
  filters: MapFilters;
  sort: 'recommended' | 'price_asc' | 'price_desc' | 'newest';
  selectedPropertyId: number | null;
};

export const EMPTY_MAP_SEARCH_STATE: MapSearchState = {
  filters: {
    dealType: '',
    propertyTypes: [],
    buildStatus: '',
    district: '',
    location: '',
    minPrice: '',
    maxPrice: '',
    bedrooms: [],
    bathrooms: [],
    minArea: '',
    maxArea: '',
    amenities: [],
    query: '',
  },
  sort: 'recommended',
  selectedPropertyId: null,
};

function readText(value: string | null): string {
  return (value || '').trim();
}

function readList(params: URLSearchParams, key: string): string[] {
  return [...new Set(params.getAll(key).map(readText).filter(Boolean))].sort();
}

function readSelectedProperty(value: string | null): number | null {
  const propertyId = Number(value);
  return Number.isSafeInteger(propertyId) && propertyId > 0 ? propertyId : null;
}

function readSort(value: string | null): MapSearchState['sort'] {
  return ['recommended', 'price_asc', 'price_desc', 'newest'].includes(value || '')
    ? value as MapSearchState['sort']
    : 'recommended';
}

export function parseMapSearchState(search: string): MapSearchState {
  const params = new URLSearchParams(search);
  const dealType = readText(params.get('deal_type'));

  return {
    filters: {
      dealType: dealType === 'sale' || dealType === 'rent' ? dealType : '',
      propertyTypes: readList(params, 'property_type'),
      buildStatus: readText(params.get('build_status')),
      district: readText(params.get('district')),
      location: readText(params.get('location')),
      minPrice: readText(params.get('min_price')),
      maxPrice: readText(params.get('max_price')),
      bedrooms: readList(params, 'bedrooms'),
      bathrooms: readList(params, 'bathrooms'),
      minArea: readText(params.get('min_area')),
      maxArea: readText(params.get('max_area')),
      amenities: readList(params, 'amenities'),
      query: readText(params.get('q')),
    },
    sort: readSort(params.get('sort')),
    selectedPropertyId: readSelectedProperty(params.get('selected')),
  };
}

function appendScalar(params: URLSearchParams, key: string, value: string): void {
  if (value) {
    params.set(key, value);
  }
}

function appendList(params: URLSearchParams, key: string, values: string[]): void {
  values.map(readText).filter(Boolean).sort().forEach((value) => params.append(key, value));
}

export function serializeMapSearchState(state: MapSearchState): URLSearchParams {
  const params = new URLSearchParams();
  const { filters } = state;

  appendScalar(params, 'deal_type', filters.dealType);
  appendList(params, 'property_type', filters.propertyTypes);
  appendScalar(params, 'build_status', filters.buildStatus);
  appendScalar(params, 'district', filters.district);
  appendScalar(params, 'location', filters.location);
  appendScalar(params, 'min_price', filters.minPrice);
  appendScalar(params, 'max_price', filters.maxPrice);
  appendList(params, 'bedrooms', filters.bedrooms);
  appendList(params, 'bathrooms', filters.bathrooms);
  appendScalar(params, 'min_area', filters.minArea);
  appendScalar(params, 'max_area', filters.maxArea);
  appendList(params, 'amenities', filters.amenities);
  appendScalar(params, 'q', filters.query);
  if (state.sort !== 'recommended') {
    appendScalar(params, 'sort', state.sort);
  }
  if (state.selectedPropertyId) {
    params.set('selected', String(state.selectedPropertyId));
  }
  return params;
}

export function buildMapSearchUrl(state: MapSearchState, currentUrl: URL): string {
  const url = new URL(currentUrl);
  const params = serializeMapSearchState(state);
  // The map app also powers the catalogue's ?map_view=true route. Keep that
  // presentation mode while replacing only the map-search state.
  if (url.searchParams.get('map_view') === 'true') {
    params.set('map_view', 'true');
  }
  url.search = params.toString();
  return `${url.pathname}${url.search}${url.hash}`;
}

export function replaceMapSearchState(state: MapSearchState): void {
  window.history.replaceState(null, '', buildMapSearchUrl(state, new URL(window.location.href)));
}

export function subscribeToMapSearchState(
  callback: (state: MapSearchState) => void,
): () => void {
  const onPopState = () => callback(parseMapSearchState(window.location.search));
  window.addEventListener('popstate', onPopState);
  return () => window.removeEventListener('popstate', onPopState);
}
