export type MapAppBootstrap = {
  schemaVersion: 1;
  language: 'ru' | 'en' | 'th';
  currency: {
    code: string;
    symbol: string;
    decimalPlaces: number;
  };
  endpoints: {
    properties: string;
    cards: string;
    districts: string;
  };
  map: {
    center: [number, number];
    zoom: number;
    aggregateMaxZoom: number;
    styleUrl: string;
  };
  featureFlags: {
    mapRebuild: boolean;
  };
  catalog?: {
    url: string;
    label: string;
    filterDrawerInitiallyCollapsed: boolean;
  };
  initialDealType?: 'sale' | 'rent';
  filters: {
    propertyTypes: MapFilterOption[];
    districts: MapDistrictOption[];
    buildStatuses: MapFilterOption[];
    amenities: MapFilterOption[];
  };
  translations: {
    loading: string;
    unavailable: string;
    viewCatalog: string;
    filters: string;
    all: string;
    sale: string;
    rent: string;
    propertyType: string;
    buildStatus: string;
    district: string;
    location: string;
    search: string;
    searchPlaceholder: string;
    bedrooms: string;
    bathrooms?: string;
    area?: string;
    areaFrom?: string;
    areaTo?: string;
    amenities: string;
    amenitiesSearch: string;
    priceFrom: string;
    priceTo: string;
    reset: string;
    results: string;
    inList?: string;
    onMap?: string;
    inArea?: string;
    total?: string;
    zoomToSeeAll?: string;
    selectedPropertyUnavailable?: string;
    mapView?: string;
    listView?: string;
    sort?: string;
    recommended?: string;
    priceLowToHigh?: string;
    priceHighToLow?: string;
    newest?: string;
    close: string;
    showResults: string;
    noResults: string;
    retry: string;
    findLocation: string;
    locating: string;
    locationDenied: string;
    locationUnavailable: string;
    searchThisArea: string;
    resetView: string;
    addFavorite: string;
    removeFavorite: string;
    moreDetails?: string;
    bedroomsLabel?: string;
    bathroomsLabel?: string;
    areaLabel?: string;
  };
};

export type MapFilterOption = { value: string; label: string };
export type MapDistrictOption = MapFilterOption & { locations: MapFilterOption[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function parseMapBootstrap(raw: string): MapAppBootstrap {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('Map bootstrap is not valid JSON.');
  }

  if (!isRecord(parsed) || parsed.schemaVersion !== 1) {
    throw new Error('Map bootstrap schema version is not supported.');
  }

  if (!['ru', 'en', 'th'].includes(String(parsed.language))) {
    throw new Error('Map bootstrap language is invalid.');
  }

  const currency = parsed.currency;
  const endpoints = parsed.endpoints;
  const map = parsed.map;
  const featureFlags = parsed.featureFlags;
  const catalog = parsed.catalog;
  const translations = parsed.translations;
  const filters = parsed.filters;
  if (
    !isRecord(currency) || typeof currency.code !== 'string' ||
    typeof currency.symbol !== 'string' || !isFiniteNumber(currency.decimalPlaces) ||
    !isRecord(endpoints) || typeof endpoints.properties !== 'string' || typeof endpoints.cards !== 'string' ||
    typeof endpoints.districts !== 'string' ||
    !isRecord(map) || !Array.isArray(map.center) || map.center.length !== 2 ||
    !map.center.every(isFiniteNumber) || !isFiniteNumber(map.zoom) ||
    !isFiniteNumber(map.aggregateMaxZoom) || typeof map.styleUrl !== 'string' ||
    !isRecord(featureFlags) || featureFlags.mapRebuild !== true ||
    !isRecord(filters) || !Array.isArray(filters.propertyTypes) || !Array.isArray(filters.districts) ||
    !Array.isArray(filters.buildStatuses) || !Array.isArray(filters.amenities) ||
    !isRecord(translations) || typeof translations.loading !== 'string' ||
    typeof translations.unavailable !== 'string' || typeof translations.viewCatalog !== 'string'
  ) {
    throw new Error('Map bootstrap has an invalid shape.');
  }

  if (catalog !== undefined && (!isRecord(catalog) || typeof catalog.url !== 'string' || typeof catalog.label !== 'string' || typeof catalog.filterDrawerInitiallyCollapsed !== 'boolean')) {
    throw new Error('Map bootstrap catalog has an invalid shape.');
  }
  if (parsed.initialDealType !== undefined && parsed.initialDealType !== 'sale' && parsed.initialDealType !== 'rent') {
    throw new Error('Map bootstrap initial deal type is invalid.');
  }

  return parsed as MapAppBootstrap;
}

export function getMapBootstrap(documentRoot: Document): MapAppBootstrap {
  const bootstrapNode = documentRoot.getElementById('map-app-bootstrap');
  if (!bootstrapNode?.textContent) {
    throw new Error('Map bootstrap is missing.');
  }
  return parseMapBootstrap(bootstrapNode.textContent);
}
