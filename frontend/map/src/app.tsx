import { Component, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { MapAppBootstrap } from './bootstrap';
import { clearMapResponseCache, useMapProperties, useMapPropertiesByIds, useMapPropertyCards } from './features/search/api';
import type { MapViewport } from './features/search/api';
import { getActiveFilterChips } from './features/search/active-filters';
import { FilterSidebar } from './features/search/filter-sidebar';
import { replaceMapSearchState } from './features/search/state';
import { MobileFilterSheet } from './features/search/mobile-filter-sheet';
import { MapContentState } from './features/search/map-content-state';
import { MapAdapter } from './map/map-adapter';
import { MobilePropertySheet } from './map/mobile-property-sheet';
import { PropertySelection } from './map/property-selection';
import { ResultsPanel } from './map/results-panel';
import { trackMapEvent, trackMapTiming } from './analytics';
import { EMPTY_MAP_SEARCH_STATE, parseMapSearchState, subscribeToMapSearchState } from './features/search/state';
import { recordMapSessionUsage } from './map-usage';

const MAP_SIDEBAR_COLLAPSED_KEY = 'map-filter-drawer-collapsed';
const MAP_CATALOG_SIDEBAR_COLLAPSED_KEY = 'map-catalog-filter-drawer-collapsed';

type CurrencyChangedDetail = { currency?: unknown; symbol?: unknown };

function getChangedCurrency(event: Event, currentCurrency: MapAppBootstrap['currency']): MapAppBootstrap['currency'] | null {
  const detail = (event as CustomEvent<CurrencyChangedDetail>).detail;
  if (!detail || typeof detail.currency !== 'string') return null;
  const code = detail.currency.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(code)) return null;
  return {
    ...currentCurrency,
    code,
    symbol: typeof detail.symbol === 'string' && detail.symbol ? detail.symbol : currentCurrency.symbol,
  };
}

type MapAppProps = {
  bootstrap: MapAppBootstrap;
  queryEnabled?: boolean;
  mapEnabled?: boolean;
};

type MapErrorBoundaryProps = {
  fallback: ReactNode;
  children: ReactNode;
};

type MapErrorBoundaryState = {
  hasError: boolean;
};

export class MapErrorBoundary extends Component<MapErrorBoundaryProps, MapErrorBoundaryState> {
  state: MapErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): MapErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch() {
    // Error reporting is connected with map telemetry in a later sprint.
  }

  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}

export function MapFallback({ message }: { message: string }) {
  return <div className="map-app-fallback" role="status">{message}</div>;
}

function FilterIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="9" cy="6" r="2" fill="currentColor" /><circle cx="15" cy="12" r="2" fill="currentColor" /><circle cx="7" cy="18" r="2" fill="currentColor" /></svg>;
}

function SidebarChevron({ collapsed }: { collapsed: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d={collapsed ? 'm9 18 6-6-6-6' : 'm15 18-6-6 6-6'} /></svg>;
}

function sidebarStorageKey(bootstrap: MapAppBootstrap): string {
  return bootstrap.catalog ? MAP_CATALOG_SIDEBAR_COLLAPSED_KEY : MAP_SIDEBAR_COLLAPSED_KEY;
}

function initialSidebarCollapsed(bootstrap: MapAppBootstrap): boolean {
  try {
    const savedValue = localStorage.getItem(sidebarStorageKey(bootstrap));
    if (savedValue !== null) return savedValue === '1';
  } catch {
    // Storage may be unavailable in private browsing contexts.
  }
  return bootstrap.catalog?.filterDrawerInitiallyCollapsed ?? true;
}

function applyBootstrapDefaults(state: ReturnType<typeof parseMapSearchState>, bootstrap: MapAppBootstrap) {
  if (!bootstrap.initialDealType || state.filters.dealType) return state;
  return {
    ...state,
    filters: { ...state.filters, dealType: bootstrap.initialDealType },
  };
}

export function MapApp({ bootstrap, queryEnabled = true, mapEnabled = true }: MapAppProps) {
  const [searchState, setSearchState] = useState(() => applyBootstrapDefaults(parseMapSearchState(window.location.search), bootstrap));
  const [runtimeCurrency, setRuntimeCurrency] = useState(bootstrap.currency);
  const [isMobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [mobileView, setMobileView] = useState<'map' | 'list'>('map');
  const [isDesktopSidebarCollapsed, setDesktopSidebarCollapsed] = useState(() => initialSidebarCollapsed(bootstrap));
  const [geolocationState, setGeolocationState] = useState<'idle' | 'locating' | 'denied' | 'unavailable'>('idle');
  const [mapError, setMapError] = useState(false);
  const [selectedPropertyUnavailable, setSelectedPropertyUnavailable] = useState(false);
  const [overlappingPropertyIds, setOverlappingPropertyIds] = useState<number[]>([]);
  const [hoveredPropertyId, setHoveredPropertyId] = useState<number | null>(null);
  const [focusedPropertyId, setFocusedPropertyId] = useState<number | null>(null);
  const initialViewport: MapViewport = { zoom: bootstrap.map.zoom };
  const [pendingViewport, setPendingViewport] = useState<MapViewport>(initialViewport);
  const [appliedViewport, setAppliedViewport] = useState<MapViewport>(initialViewport);
  const [resetViewToken, setResetViewToken] = useState(0);
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
  const requestStartedAt = useRef(performance.now());
  const propertiesQuery = useMapProperties(bootstrap, searchState, appliedViewport, runtimeCurrency.code, queryEnabled);
  const cardsQuery = useMapPropertyCards(bootstrap, searchState, appliedViewport, runtimeCurrency.code, queryEnabled);
  const overlapCardsQuery = useMapPropertiesByIds(bootstrap, overlappingPropertyIds, runtimeCurrency.code, queryEnabled);

  useEffect(() => subscribeToMapSearchState((state) => setSearchState(applyBootstrapDefaults(state, bootstrap))), [bootstrap]);
  useEffect(() => {
    const usage = recordMapSessionUsage();
    if (!usage) return;
    trackMapEvent('map_rebuild_session_started', {
      is_returning: usage.isReturning,
      visit_count: usage.visitCount,
    });
  }, []);
  useEffect(() => {
    const handleCurrencyChanged = (event: Event) => {
      setRuntimeCurrency((currentCurrency) => {
        const nextCurrency = getChangedCurrency(event, currentCurrency);
        if (!nextCurrency || nextCurrency.code === currentCurrency.code) return currentCurrency;
        clearMapResponseCache();
        return nextCurrency;
      });
    };
    window.addEventListener('currencyChanged', handleCurrencyChanged);
    return () => window.removeEventListener('currencyChanged', handleCurrencyChanged);
  }, []);
  useEffect(() => {
    try { localStorage.setItem(sidebarStorageKey(bootstrap), isDesktopSidebarCollapsed ? '1' : '0'); } catch { /* Ignore unavailable storage. */ }
  }, [bootstrap, isDesktopSidebarCollapsed]);
  useEffect(() => {
    if (propertiesQuery.isFetching) requestStartedAt.current = performance.now();
  }, [propertiesQuery.isFetching]);
  useEffect(() => {
    if (!propertiesQuery.data) return;
    trackMapTiming('api', propertiesQuery.data.server_timing_ms, { mode: propertiesQuery.data.mode });
    trackMapTiming('client_results', performance.now() - requestStartedAt.current, { mode: propertiesQuery.data.mode });
  }, [propertiesQuery.data]);

  const updateSearchState = (nextState: typeof searchState) => {
    const normalizedState = applyBootstrapDefaults(nextState, bootstrap);
    replaceMapSearchState(normalizedState);
    setSearchState(normalizedState);
    trackMapEvent('map_rebuild_filters_changed', { active_filter_count: Object.values(normalizedState.filters).flat().filter(Boolean).length });
  };
  const activeChips = getActiveFilterChips(bootstrap, searchState);
  const highlightedPropertyId = focusedPropertyId || hoveredPropertyId;
  const resultCount = propertiesQuery.data?.mode === 'properties'
    ? propertiesQuery.data.visible_count
    : propertiesQuery.data?.viewport_count;
  const resultCountLabel = propertiesQuery.data?.mode === 'properties'
    ? bootstrap.translations.onMap || 'On map'
    : bootstrap.translations.inArea || 'In this area';
  const popupTranslations = useMemo(() => ({
    addFavorite: bootstrap.translations.addFavorite,
    removeFavorite: bootstrap.translations.removeFavorite,
    moreDetails: bootstrap.translations.moreDetails || 'Details',
    bedroomsLabel: bootstrap.translations.bedroomsLabel || 'Bedrooms',
    bathroomsLabel: bootstrap.translations.bathroomsLabel || 'Bathrooms',
    areaLabel: bootstrap.translations.areaLabel || 'Area',
  }), [bootstrap.translations]);
  const hasSelectedPropertyResolution = propertiesQuery.data?.selected_property_id === searchState.selectedPropertyId;
  const selectedProperty = hasSelectedPropertyResolution
    ? propertiesQuery.data?.selected_property || null
    : null;
  useEffect(() => {
    if (!searchState.selectedPropertyId || !hasSelectedPropertyResolution) return;
    if (selectedProperty) {
      setSelectedPropertyUnavailable(false);
      return;
    }
    setSelectedPropertyUnavailable(true);
    const nextState = { ...searchState, selectedPropertyId: null };
    replaceMapSearchState(nextState);
    setSearchState(nextState);
  }, [hasSelectedPropertyResolution, searchState, selectedProperty]);
  const cardProperties = cardsQuery.data?.pages.flatMap((page) => page.properties) || [];
  const overlappingProperties = overlapCardsQuery.data?.properties || [];
  const locateUser = () => {
    if (!navigator.geolocation) {
      setGeolocationState('unavailable');
      return;
    }
    setGeolocationState('locating');
    navigator.geolocation.getCurrentPosition(
      (position) => { setUserLocation([position.coords.longitude, position.coords.latitude]); setGeolocationState('idle'); },
      (error) => setGeolocationState(error.code === error.PERMISSION_DENIED ? 'denied' : 'unavailable'),
      { enableHighAccuracy: false, timeout: 8_000 },
    );
  };
  const handleMapError = useCallback((duringInitialization: boolean) => {
    trackMapEvent('map_rebuild_map_error', { stage: duringInitialization ? 'initialization' : 'runtime' });
    // A loaded map can emit non-fatal runtime errors while MapLibre disposes DOM
    // controls. Keep the existing working map visible and reserve fallback for
    // an initialization failure only.
    if (duringInitialization) setMapError(true);
  }, []);
  const viewportChanged = JSON.stringify(pendingViewport) !== JSON.stringify(appliedViewport);
  const resetMapView = () => { setPendingViewport(initialViewport); setAppliedViewport(initialViewport); setResetViewToken((token) => token + 1); };
  const closeSelectedProperty = () => {
    setSelectedPropertyUnavailable(false);
    updateSearchState({ ...searchState, selectedPropertyId: null });
  };
  const changeMobileView = (nextView: 'map' | 'list') => {
    if (nextView === mobileView) return;
    setMobileView(nextView);
    trackMapEvent('map_rebuild_mobile_view_changed', { view: nextView });
  };
  const selectProperty = (propertyId: number, source: 'list' | 'map' | 'overlap_list') => {
    updateSearchState({ ...searchState, selectedPropertyId: propertyId });
    trackMapEvent('map_rebuild_property_selected', { source });
    if (window.matchMedia('(max-width: 1023px)').matches) setMobileView('map');
  };
  const changeSort = (sort: typeof searchState.sort) => {
    if (sort === searchState.sort) return;
    updateSearchState({ ...searchState, sort });
    trackMapEvent('map_rebuild_sort_changed', { sort });
  };
  const sortOptions = {
    recommended: bootstrap.translations.recommended || 'Recommended',
    price_asc: bootstrap.translations.priceLowToHigh || 'Price: low to high',
    price_desc: bootstrap.translations.priceHighToLow || 'Price: high to low',
    newest: bootstrap.translations.newest || 'Newest',
  };

  return (
    <main
      aria-label="Property map"
      data-map-language={bootstrap.language}
      data-map-currency={runtimeCurrency.code}
      data-map-schema-version={bootstrap.schemaVersion}
      data-map-selected-property={searchState.selectedPropertyId || ''}
      data-map-response-mode={propertiesQuery.data?.mode || ''}
    ><div className="map-mobile-view-toggle" role="tablist" aria-label={bootstrap.translations.results}>
      <button type="button" role="tab" aria-selected={mobileView === 'map'} onClick={() => changeMobileView('map')}>{bootstrap.translations.mapView || 'Map'}</button>
      <button type="button" role="tab" aria-selected={mobileView === 'list'} onClick={() => changeMobileView('list')}>{bootstrap.translations.listView || 'List'}</button>
    </div><div className={`map-app-layout${mobileView === 'list' ? ' is-mobile-list' : ''}`}>
      <div className="map-results-shell">
        <ResultsPanel properties={cardProperties} response={propertiesQuery.data} selectedPropertyId={searchState.selectedPropertyId} highlightedPropertyId={highlightedPropertyId} resultsLabel={bootstrap.translations.results} inListLabel={bootstrap.translations.inList || 'In list'} onMapLabel={bootstrap.translations.onMap || 'On map'} inAreaLabel={bootstrap.translations.inArea || 'In this area'} totalLabel={bootstrap.translations.total || 'Total'} zoomToSeeAllLabel={bootstrap.translations.zoomToSeeAll || 'Zoom in to see all properties'} sort={searchState.sort} sortLabel={bootstrap.translations.sort || 'Sort'} sortOptions={sortOptions} onSortChange={changeSort} onSelect={(propertyId) => selectProperty(propertyId, 'list')} onHover={setHoveredPropertyId} onFocusProperty={setFocusedPropertyId} hasNextPage={Boolean(cardsQuery.hasNextPage)} isLoadingNextPage={cardsQuery.isFetchingNextPage} onLoadNextPage={() => void cardsQuery.fetchNextPage()} />
        {!isDesktopSidebarCollapsed && <FilterSidebar bootstrap={bootstrap} state={searchState} resultCount={resultCount} resultCountLabel={resultCountLabel} onChange={updateSearchState} className="map-filter-sidebar--drawer" />}
      </div>
      <section className="map-app-main">
        <div className="map-active-filters" aria-live="polite">
          {bootstrap.catalog && <a className="map-catalog-return" href={bootstrap.catalog.url}>{bootstrap.catalog.label}</a>}
          <button className="map-mobile-filter-trigger" type="button" onClick={() => setMobileFiltersOpen(true)}>{bootstrap.translations.filters}</button>
          <button className="map-sidebar-toggle" type="button" title={bootstrap.translations.filters} aria-label={bootstrap.translations.filters} aria-expanded={!isDesktopSidebarCollapsed} onClick={() => setDesktopSidebarCollapsed((collapsed) => !collapsed)}><FilterIcon /><SidebarChevron collapsed={isDesktopSidebarCollapsed} />{activeChips.length > 0 && <span>{activeChips.length}</span>}</button>
          <button className="map-geolocation-trigger" type="button" onClick={locateUser} disabled={geolocationState === 'locating'}>{geolocationState === 'locating' ? bootstrap.translations.locating : bootstrap.translations.findLocation}</button>
          {viewportChanged && <button className="map-viewport-trigger" type="button" onClick={() => { setAppliedViewport(pendingViewport); trackMapEvent('map_rebuild_viewport_search'); }}>{bootstrap.translations.searchThisArea}</button>}
          <button className="map-reset-trigger" type="button" onClick={resetMapView}>{bootstrap.translations.resetView}</button>
          {activeChips.map((chip) => <button type="button" key={chip.id} onClick={() => updateSearchState(chip.nextState)}>{chip.label} ×</button>)}
          {propertiesQuery.isFetching && <span>{bootstrap.translations.loading}</span>}
        </div>
        {geolocationState === 'denied' && <p className="map-geolocation-message" role="status">{bootstrap.translations.locationDenied}</p>}
        {geolocationState === 'unavailable' && <p className="map-geolocation-message" role="status">{bootstrap.translations.locationUnavailable}</p>}
        {selectedPropertyUnavailable && <p className="map-selection-message" role="status">{bootstrap.translations.selectedPropertyUnavailable || 'Selected property is no longer available'}</p>}
        <div className="map-stage-canvas">
          {mapEnabled && <MapAdapter bootstrap={bootstrap} response={propertiesQuery.data} selectedPropertyId={searchState.selectedPropertyId} highlightedPropertyId={highlightedPropertyId} selectedProperty={selectedProperty || null} selectedDistrict={searchState.filters.district} onSelectProperties={(propertyIds) => { if (propertyIds.length === 1) { setOverlappingPropertyIds([]); selectProperty(propertyIds[0], 'map'); } else { setOverlappingPropertyIds(propertyIds); } }} onPropertyHover={setHoveredPropertyId} onViewportChange={setPendingViewport} onAggregateSelect={(viewport) => { setPendingViewport(viewport); setAppliedViewport(viewport); trackMapEvent('map_rebuild_viewport_search', { source: 'aggregate' }); }} onPopupClose={closeSelectedProperty} popupTranslations={popupTranslations} resetViewToken={resetViewToken} userLocation={userLocation} isVisible={mobileView === 'map'} onError={handleMapError} />}
          {overlappingProperties.length > 1 && <PropertySelection properties={overlappingProperties} closeLabel={bootstrap.translations.close} onClose={() => setOverlappingPropertyIds([])} onSelect={(propertyId) => { setOverlappingPropertyIds([]); selectProperty(propertyId, 'overlap_list'); }} />}
        </div>
        <MapContentState isPending={propertiesQuery.isPending} isError={(!propertiesQuery.data && propertiesQuery.isError) || mapError} resultCount={propertiesQuery.data?.viewport_count} loadingLabel={bootstrap.translations.loading} unavailableLabel={bootstrap.translations.unavailable} noResultsLabel={bootstrap.translations.noResults} retryLabel={bootstrap.translations.retry} resetLabel={bootstrap.translations.reset} onRetry={() => void propertiesQuery.refetch()} onReset={() => updateSearchState(EMPTY_MAP_SEARCH_STATE)} />
      </section>
    </div>
    {isMobileFiltersOpen && <MobileFilterSheet bootstrap={bootstrap} state={searchState} resultCount={resultCount} resultCountLabel={resultCountLabel} onChange={updateSearchState} onClose={() => setMobileFiltersOpen(false)} />}
    {selectedProperty && mobileView === 'map' && <MobilePropertySheet property={selectedProperty} closeLabel={bootstrap.translations.close} translations={popupTranslations} onClose={closeSelectedProperty} />}
    </main>
  );
}
