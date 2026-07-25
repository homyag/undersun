import { useEffect, useRef, useState } from 'react';
import type { ExpressionSpecification, GeoJSONSource, Map, Point } from 'maplibre-gl';

import type { MapAppBootstrap } from '../bootstrap';
import type { MapPropertiesResponse, MapProperty } from '../features/search/api';
import type { MapViewport } from '../features/search/api';
import { getSelectedMapPosition, toMapFeatureCollection } from './map-data';
import { createBasemapFailover } from './map-basemap-failover';
import { classifyMapError, createMapErrorReporter } from './map-error-policy';
import { rewriteOpenFreeMapGlyphUrl } from './openfreemap-glyphs';
import type { PropertyPopupTranslations } from './property-popup-content';
import { createPropertyPopupContent } from './property-popup-dom';
import { trackMapEvent } from '../analytics';

const SOURCE_ID = 'map-app-results';
const AGGREGATE_GLOW_LAYER_ID = 'map-app-aggregate-glow';
const AGGREGATE_RING_LAYER_ID = 'map-app-aggregate-ring';
const AGGREGATE_LAYER_ID = 'map-app-aggregate';
const AGGREGATE_LABEL_LAYER_ID = 'map-app-aggregate-label';
const PROPERTY_PIN_LAYER_ID = 'map-app-property-pin';
const PROPERTY_PIN_IMAGE_ID = 'map-app-property-pin';
const SELECTED_PROPERTY_PIN_IMAGE_ID = 'map-app-property-pin-selected';
const HIGHLIGHTED_PROPERTY_PIN_IMAGE_ID = 'map-app-property-pin-highlighted';
const DISTRICT_SOURCE_ID = 'map-app-districts';
const DISTRICT_FILL_LAYER_ID = 'map-app-district-fill';
const DISTRICT_OUTLINE_LAYER_ID = 'map-app-district-outline';
const SELECTED_DISTRICT_FILL_LAYER_ID = 'map-app-selected-district-fill';
const SELECTED_DISTRICT_OUTLINE_LAYER_ID = 'map-app-selected-district-outline';
const stylesInstalling = new WeakSet<Map>();

const FALLBACK_BASEMAP_STYLE = {
  version: 8 as const,
  sources: {
    'fallback-osm': {
      type: 'raster' as const,
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    },
  },
  layers: [{ id: 'fallback-osm', type: 'raster' as const, source: 'fallback-osm' }],
};

type DistrictFeatureCollection = {
  type: 'FeatureCollection';
  features: Array<{ geometry?: { coordinates?: unknown }; properties?: { slug?: string } }>;
};

function createPropertyPinSvg(color: string, darkColor: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 40 40">
    <defs>
      <filter id="pin-shadow" x="-40%" y="-40%" width="180%" height="180%">
        <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="${darkColor}" flood-opacity="0.24"/>
      </filter>
    </defs>
    <circle cx="20" cy="20" r="16" fill="#fff" filter="url(#pin-shadow)"/>
    <circle cx="20" cy="20" r="14" fill="#fff" stroke="${color}" stroke-width="3"/>
    <circle cx="20" cy="20" r="10.5" fill="${color}" fill-opacity="0.12"/>
    <path d="M12.5 19.1 20 12.9l7.5 6.2v8.2h-4.7v-5.4h-5.6v5.4h-4.7v-8.2Z" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M10.8 20.1 20 12l9.2 8.1" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

function loadMapImage(map: Map, name: string, svgMarkup: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const image = new Image(80, 80);
    image.onload = () => {
      if (!map.hasImage(name)) map.addImage(name, image, { pixelRatio: 2 });
      resolve();
    };
    image.onerror = () => reject(new Error(`Unable to load ${name}.`));
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgMarkup)}`;
  });
}

function propertyPinImageExpression(selectedPropertyId: number | null, highlightedPropertyId: number | null): ExpressionSpecification {
  return ['case', ['==', ['get', 'propertyId'], selectedPropertyId || -1], SELECTED_PROPERTY_PIN_IMAGE_ID, ['==', ['get', 'propertyId'], highlightedPropertyId || -1], HIGHLIGHTED_PROPERTY_PIN_IMAGE_ID, PROPERTY_PIN_IMAGE_ID];
}

function getInteractiveFeature(map: Map, point: Point) {
  return map.queryRenderedFeatures(point, {
    layers: [PROPERTY_PIN_LAYER_ID, AGGREGATE_LAYER_ID],
  })[0];
}

function districtBounds(feature: DistrictFeatureCollection['features'][number]): [[number, number], [number, number]] | null {
  const coordinates: number[][] = [];
  const collect = (value: unknown) => {
    if (!Array.isArray(value)) return;
    if (value.length === 2 && value.every((item) => typeof item === 'number')) coordinates.push(value as number[]);
    else value.forEach(collect);
  };
  collect(feature.geometry?.coordinates);
  if (!coordinates.length) return null;
  const lng = coordinates.map((point) => point[0]);
  const lat = coordinates.map((point) => point[1]);
  return [[Math.min(...lng), Math.min(...lat)], [Math.max(...lng), Math.max(...lat)]];
}

function applyDistrictHighlight(map: Map, districtData: DistrictFeatureCollection | null, districtSlug: string) {
  if (!map.getLayer(SELECTED_DISTRICT_FILL_LAYER_ID)) return;
  if (districtSlug) map.getContainer().setAttribute('data-selected-district', districtSlug);
  else map.getContainer().removeAttribute('data-selected-district');
  map.setFilter(SELECTED_DISTRICT_FILL_LAYER_ID, ['==', ['get', 'slug'], districtSlug || '__none__']);
  map.setFilter(SELECTED_DISTRICT_OUTLINE_LAYER_ID, ['==', ['get', 'slug'], districtSlug || '__none__']);
  const feature = districtData?.features.find((item) => item.properties?.slug === districtSlug);
  const bounds = feature && districtBounds(feature);
  if (bounds) map.fitBounds(bounds, { padding: 48, maxZoom: 13, duration: mapMotionDuration() });
}

function getPopupWidth(map: Map) {
  const container = map.getContainer();
  return Math.min(344, Math.max(0, container.clientWidth - 72));
}

function positionDesktopPinForPopup(map: Map, lng: number, lat: number, popupWidth: number) {
  const container = map.getContainer();
  const current = map.project([lng, lat]);
  const edgeGap = 48;
  const target = {
    x: Math.min(Math.max(current.x, popupWidth / 2 + edgeGap), container.clientWidth - popupWidth / 2 - edgeGap),
    y: container.clientHeight - edgeGap,
  };
  const viewportCenter = { x: container.clientWidth / 2, y: container.clientHeight / 2 };
  map.jumpTo({
    center: map.unproject([
      viewportCenter.x - (target.x - current.x),
      viewportCenter.y - (target.y - current.y),
    ]),
  });
}

function mapMotionDuration(): number {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 350;
}

type MapAdapterProps = {
  bootstrap: MapAppBootstrap;
  response: MapPropertiesResponse | undefined;
  selectedPropertyId: number | null;
  highlightedPropertyId: number | null;
  selectedProperty: MapProperty | null;
  selectedDistrict: string;
  onSelectProperties: (propertyIds: number[]) => void;
  onPropertyHover: (propertyId: number | null) => void;
  onViewportChange: (viewport: MapViewport) => void;
  onAggregateSelect: (viewport: MapViewport) => void;
  onPopupClose: () => void;
  popupTranslations: PropertyPopupTranslations;
  resetViewToken: number;
  userLocation: [number, number] | null;
  isVisible?: boolean;
  onError: (duringInitialization: boolean) => void;
};

function updateSource(map: Map, response: MapPropertiesResponse | undefined) {
  const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(toMapFeatureCollection(response));
}

type InstallMapLayersOptions = {
  bootstrap: MapAppBootstrap;
  response: MapPropertiesResponse | undefined;
  selectedPropertyId: number | null;
  highlightedPropertyId: number | null;
  selectedDistrict: string;
  districtData: DistrictFeatureCollection | null;
  isDisposed: () => boolean;
  onDistrictData: (data: DistrictFeatureCollection) => void;
  onReady: () => void;
  onFailure: () => void;
};

function installMapLayers(map: Map, options: InstallMapLayersOptions) {
  if (map.getSource(SOURCE_ID)) {
    updateSource(map, options.response);
    return;
  }
  if (stylesInstalling.has(map)) return;
  stylesInstalling.add(map);
  void Promise.all([
    loadMapImage(map, PROPERTY_PIN_IMAGE_ID, createPropertyPinSvg('#474b57', '#333847')),
    loadMapImage(map, SELECTED_PROPERTY_PIN_IMAGE_ID, createPropertyPinSvg('#f1b400', '#d7a108')),
    loadMapImage(map, HIGHLIGHTED_PROPERTY_PIN_IMAGE_ID, createPropertyPinSvg('#d7a108', '#9d7400')),
  ]).then(() => {
    if (options.isDisposed()) return;
    map.addSource(SOURCE_ID, { type: 'geojson', data: toMapFeatureCollection(options.response) });
    map.addLayer({ id: AGGREGATE_GLOW_LAYER_ID, type: 'circle', source: SOURCE_ID, filter: ['==', ['get', 'isAggregate'], true], paint: { 'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 24, 50, 38], 'circle-color': '#f1b400', 'circle-opacity': 0.2, 'circle-blur': 0.8 } });
    map.addLayer({ id: AGGREGATE_RING_LAYER_ID, type: 'circle', source: SOURCE_ID, filter: ['==', ['get', 'isAggregate'], true], paint: { 'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 16, 50, 30], 'circle-color': '#ffffff', 'circle-opacity': 0.98 } });
    map.addLayer({ id: AGGREGATE_LAYER_ID, type: 'circle', source: SOURCE_ID, filter: ['==', ['get', 'isAggregate'], true], paint: { 'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 12, 50, 24], 'circle-color': '#f1b400', 'circle-stroke-color': 'rgba(51, 56, 71, 0.1)', 'circle-stroke-width': 2 } });
    map.addLayer({ id: AGGREGATE_LABEL_LAYER_ID, type: 'symbol', source: SOURCE_ID, filter: ['==', ['get', 'isAggregate'], true], layout: { 'text-field': ['get', 'count'], 'text-size': 12 }, paint: { 'text-color': '#333847' } });
    map.addLayer({ id: PROPERTY_PIN_LAYER_ID, type: 'symbol', source: SOURCE_ID, filter: ['==', ['get', 'isAggregate'], false], layout: { 'icon-image': propertyPinImageExpression(options.selectedPropertyId, options.highlightedPropertyId), 'icon-anchor': 'center', 'icon-allow-overlap': true, 'icon-ignore-placement': true } });
    const addDistrictLayers = (districtData: DistrictFeatureCollection) => {
      if (options.isDisposed() || map.getSource(DISTRICT_SOURCE_ID)) return;
      map.addSource(DISTRICT_SOURCE_ID, { type: 'geojson', data: districtData });
      map.addLayer({ id: DISTRICT_FILL_LAYER_ID, type: 'fill', source: DISTRICT_SOURCE_ID, paint: { 'fill-color': '#f1b400', 'fill-opacity': 0.045 } }, AGGREGATE_GLOW_LAYER_ID);
      map.addLayer({ id: DISTRICT_OUTLINE_LAYER_ID, type: 'line', source: DISTRICT_SOURCE_ID, paint: { 'line-color': '#616677', 'line-width': 1.1, 'line-opacity': 0.55 } }, AGGREGATE_GLOW_LAYER_ID);
      map.addLayer({ id: SELECTED_DISTRICT_FILL_LAYER_ID, type: 'fill', source: DISTRICT_SOURCE_ID, filter: ['==', ['get', 'slug'], options.selectedDistrict || '__none__'], paint: { 'fill-color': '#f1b400', 'fill-opacity': 0.22 } }, AGGREGATE_GLOW_LAYER_ID);
      map.addLayer({ id: SELECTED_DISTRICT_OUTLINE_LAYER_ID, type: 'line', source: DISTRICT_SOURCE_ID, filter: ['==', ['get', 'slug'], options.selectedDistrict || '__none__'], paint: { 'line-color': '#f1b400', 'line-width': 3, 'line-opacity': 1 } }, AGGREGATE_GLOW_LAYER_ID);
      if (options.selectedDistrict) applyDistrictHighlight(map, districtData, options.selectedDistrict);
    };
    if (options.districtData) addDistrictLayers(options.districtData);
    else void fetch(options.bootstrap.endpoints.districts, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then((response) => response.ok ? response.json() : null)
      .then((payload: { success?: boolean; geojson?: DistrictFeatureCollection } | null) => {
        if (!payload?.success || payload.geojson?.type !== 'FeatureCollection') return;
        options.onDistrictData(payload.geojson);
        addDistrictLayers(payload.geojson);
      })
      .catch(() => undefined);
    options.onReady();
    stylesInstalling.delete(map);
  }).catch(() => {
    stylesInstalling.delete(map);
    options.onFailure();
  });
}

export function MapAdapter({ bootstrap, response, selectedPropertyId, highlightedPropertyId, selectedProperty, selectedDistrict, onSelectProperties, onPropertyHover, onViewportChange, onAggregateSelect, onPopupClose, popupTranslations, resetViewToken, userLocation, isVisible = true, onError }: MapAdapterProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mapReady, setMapReady] = useState(false);
  const mapRef = useRef<Map | null>(null);
  const responseRef = useRef(response);
  const selectedPropertyIdRef = useRef<number | null>(null);
  const onSelectPropertiesRef = useRef<(propertyIds: number[]) => void>(() => undefined);
  const onPropertyHoverRef = useRef<(propertyId: number | null) => void>(() => undefined);
  const hoveredPropertyIdRef = useRef<number | null>(null);
  const onViewportChangeRef = useRef<(viewport: MapViewport) => void>(() => undefined);
  const onAggregateSelectRef = useRef<(viewport: MapViewport) => void>(() => undefined);
  const districtDataRef = useRef<DistrictFeatureCollection | null>(null);
  const selectedDistrictRef = useRef('');
  const maplibreRef = useRef<typeof import('maplibre-gl') | null>(null);
  const popupRef = useRef<import('maplibre-gl').Popup | null>(null);
  const hasMapReadyRef = useRef(false);
  const suppressPopupCloseRef = useRef(false);
  const onPopupCloseRef = useRef<() => void>(() => undefined);
  responseRef.current = response;
  selectedPropertyIdRef.current = selectedPropertyId;
  onSelectPropertiesRef.current = onSelectProperties;
  onPropertyHoverRef.current = onPropertyHover;
  onViewportChangeRef.current = onViewportChange;
  onAggregateSelectRef.current = onAggregateSelect;
  selectedDistrictRef.current = selectedDistrict;
  onPopupCloseRef.current = onPopupClose;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let disposed = false;
    void import('maplibre-gl').then(({ default: maplibregl }) => {
      if (disposed || !containerRef.current) return;
      const map = new maplibregl.Map({
        container: containerRef.current,
        style: bootstrap.map.styleUrl,
        center: bootstrap.map.center,
        zoom: bootstrap.map.zoom,
        transformRequest: (url, resourceType) => ({ url: rewriteOpenFreeMapGlyphUrl(url, resourceType) }),
      });
      maplibreRef.current = maplibregl;
      mapRef.current = map;
      const errorReporter = createMapErrorReporter((name, params) => trackMapEvent(name, params));
      const installCurrentStyleLayers = () => installMapLayers(map, {
        bootstrap,
        response: responseRef.current,
        selectedPropertyId: selectedPropertyIdRef.current,
        highlightedPropertyId: hoveredPropertyIdRef.current,
        selectedDistrict: selectedDistrictRef.current,
        districtData: districtDataRef.current,
        isDisposed: () => disposed,
        onDistrictData: (data) => { districtDataRef.current = data; },
        onReady: () => {
          hasMapReadyRef.current = true;
          containerRef.current?.setAttribute('data-map-ready', 'true');
          setMapReady(true);
        },
        onFailure: () => onError(!hasMapReadyRef.current),
      });
      const basemapFailover = createBasemapFailover({
        map,
        fallbackStyle: FALLBACK_BASEMAP_STYLE,
        report: (decision, provider) => errorReporter.report(decision, provider),
        trackFallback: (reason) => trackMapEvent('map_rebuild_basemap_fallback', { from: 'openfreemap', to: 'openstreetmap', reason }),
        onStyleReady: installCurrentStyleLayers,
        onFatal: () => onError(!hasMapReadyRef.current),
      });
      map.on('error', (event) => {
        const decision = classifyMapError(event, Boolean(map.isStyleLoaded()));
        basemapFailover.handle(decision);
      });
      map.getCanvas().addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        const decision = { kind: 'webgl' as const, fatal: true };
        basemapFailover.handle(decision);
      });
      map.on('load', () => {
        installCurrentStyleLayers();
        map.getCanvas().style.cursor = 'grab';
        map.on('mousemove', (event) => {
          const feature = getInteractiveFeature(map, event.point);
          map.getCanvas().style.cursor = feature ? 'pointer' : 'grab';
          const propertyId = Number(feature?.properties?.propertyId);
          const nextPropertyId = Number.isSafeInteger(propertyId) && propertyId > 0 ? propertyId : null;
          if (nextPropertyId === hoveredPropertyIdRef.current) return;
          hoveredPropertyIdRef.current = nextPropertyId;
          onPropertyHoverRef.current(nextPropertyId);
        });
        map.on('mouseleave', () => { map.getCanvas().style.cursor = 'grab'; hoveredPropertyIdRef.current = null; onPropertyHoverRef.current(null); });
        map.on('dragstart', () => { map.getCanvas().style.cursor = 'grabbing'; });
        map.on('dragend', () => { map.getCanvas().style.cursor = 'grab'; });
        map.on('click', (event) => {
          const features = map.queryRenderedFeatures(event.point, { layers: [PROPERTY_PIN_LAYER_ID, AGGREGATE_LAYER_ID] });
          const propertyIds = [...new Set(features.map((feature) => Number(feature.properties?.propertyId)).filter((propertyId) => Number.isSafeInteger(propertyId) && propertyId > 0))];
          if (propertyIds.length) {
            onSelectPropertiesRef.current(propertyIds);
          } else {
            const targetFeature = features[0];
            if (!targetFeature) return;
            // `moveend` can be emitted by an unrelated resize/pan on touch devices.
            // An aggregate drill-down always changes zoom, so wait for that specific
            // transition before committing bounds to the marker query.
            map.once('zoomend', () => {
              const bounds = map.getBounds();
              onAggregateSelectRef.current({
                north: bounds.getNorth(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                west: bounds.getWest(),
                zoom: map.getZoom(),
              });
            });
            map.easeTo({ center: event.lngLat, zoom: Math.min(map.getZoom() + 2, 15), duration: mapMotionDuration() });
          }
        });
        map.on('moveend', () => {
          const bounds = map.getBounds();
          onViewportChangeRef.current({ north: bounds.getNorth(), south: bounds.getSouth(), east: bounds.getEast(), west: bounds.getWest(), zoom: map.getZoom() });
        });
      });
    }).catch(() => onError(true));
    return () => {
      disposed = true;
      hasMapReadyRef.current = false;
      suppressPopupCloseRef.current = true;
      popupRef.current?.remove();
      popupRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, [bootstrap, onError]);

  useEffect(() => {
    const map = mapRef.current;
    if (map?.isStyleLoaded()) updateSource(map, response);
  }, [response]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (highlightedPropertyId) map.getContainer().setAttribute('data-highlighted-property', String(highlightedPropertyId));
    else map.getContainer().removeAttribute('data-highlighted-property');
    if (!map.getLayer(PROPERTY_PIN_LAYER_ID)) return;
    map.setLayoutProperty(PROPERTY_PIN_LAYER_ID, 'icon-image', propertyPinImageExpression(selectedPropertyId, highlightedPropertyId));
  }, [highlightedPropertyId, mapReady, selectedPropertyId]);

  useEffect(() => {
    if (mapRef.current) applyDistrictHighlight(mapRef.current, districtDataRef.current, selectedDistrict);
  }, [selectedDistrict]);

  useEffect(() => {
    const map = mapRef.current;
    if (!selectedProperty || !map) return;
    const container = map.getContainer();
    const position = getSelectedMapPosition(
      selectedProperty.lng,
      selectedProperty.lat,
      container.clientWidth,
      container.clientHeight,
      window.matchMedia('(max-width: 1023px)').matches,
    );
    if (window.matchMedia('(max-width: 1023px)').matches) map.easeTo({ ...position, duration: mapMotionDuration() });
    else positionDesktopPinForPopup(map, selectedProperty.lng, selectedProperty.lat, getPopupWidth(map));
  }, [mapReady, selectedProperty]);

  useEffect(() => {
    const map = mapRef.current;
    const maplibregl = maplibreRef.current;
    if (!map || !maplibregl) return;
    suppressPopupCloseRef.current = true;
    popupRef.current?.remove();
    popupRef.current = null;
    suppressPopupCloseRef.current = false;
    if (!selectedProperty || window.matchMedia('(max-width: 1023px)').matches) return;

    const contentContainer = document.createElement('div');
    const maxWidth = getPopupWidth(map);
    contentContainer.appendChild(createPropertyPopupContent(selectedProperty, popupTranslations));
    const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: false, maxWidth: `${maxWidth}px`, anchor: 'bottom', offset: 18 })
      .setLngLat([selectedProperty.lng, selectedProperty.lat])
      .setDOMContent(contentContainer)
      .addTo(map);
    popup.getElement()?.style.setProperty('--map-popup-max-width', `${maxWidth}px`);
    popup.on('close', () => {
      // A close initiated by the user must release this instance immediately.
      // Otherwise the next selection attempts to remove an already detached
      // MapLibre popup, which can throw in Edge.
      if (popupRef.current === popup) popupRef.current = null;
      if (!suppressPopupCloseRef.current) onPopupCloseRef.current();
    });
    popupRef.current = popup;
  }, [mapReady, popupTranslations, selectedProperty]);

  useEffect(() => {
    if (!resetViewToken) return;
    mapRef.current?.easeTo({ center: bootstrap.map.center, zoom: bootstrap.map.zoom, duration: mapMotionDuration() });
  }, [bootstrap, resetViewToken]);

  useEffect(() => {
    if (userLocation) mapRef.current?.easeTo({ center: userLocation, zoom: 13, duration: mapMotionDuration() });
  }, [userLocation]);

  useEffect(() => {
    if (!isVisible) return;
    const map = mapRef.current;
    if (!map) return;
    const frame = window.requestAnimationFrame(() => map.resize());
    return () => window.cancelAnimationFrame(frame);
  }, [isVisible]);

  return <div className="map-canvas" ref={containerRef} aria-label="Property map" />;
}
