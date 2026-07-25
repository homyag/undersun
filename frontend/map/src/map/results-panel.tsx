import { useEffect, useRef } from 'react';

import type { MapPropertiesResponse, MapProperty } from '../features/search/api';

type ResultsPanelProps = {
  properties: MapProperty[];
  response: MapPropertiesResponse | undefined;
  selectedPropertyId: number | null;
  highlightedPropertyId: number | null;
  resultsLabel: string;
  inListLabel: string;
  onMapLabel: string;
  inAreaLabel: string;
  totalLabel: string;
  zoomToSeeAllLabel: string;
  sort: 'recommended' | 'price_asc' | 'price_desc' | 'newest';
  sortLabel: string;
  sortOptions: Record<'recommended' | 'price_asc' | 'price_desc' | 'newest', string>;
  onSortChange: (sort: 'recommended' | 'price_asc' | 'price_desc' | 'newest') => void;
  onSelect: (propertyId: number) => void;
  onHover: (propertyId: number | null) => void;
  onFocusProperty: (propertyId: number | null) => void;
  hasNextPage: boolean;
  isLoadingNextPage: boolean;
  onLoadNextPage: () => void;
};

export function ResultsPanel({ properties, response, selectedPropertyId, highlightedPropertyId, resultsLabel, inListLabel, onMapLabel, inAreaLabel, totalLabel, zoomToSeeAllLabel, sort, sortLabel, sortOptions, onSortChange, onSelect, onHover, onFocusProperty, hasNextPage, isLoadingNextPage, onLoadNextPage }: ResultsPanelProps) {
  const selectedCardRef = useRef<HTMLButtonElement>(null);
  const nextPageRequestedRef = useRef(false);
  useEffect(() => {
    selectedCardRef.current?.scrollIntoView({ block: 'nearest' });
  }, [selectedPropertyId]);
  useEffect(() => { if (!isLoadingNextPage) nextPageRequestedRef.current = false; }, [isLoadingNextPage]);
  const renderedCount = properties.length;
  const isAggregateMode = response?.mode === 'aggregates';
  const mapCount = response?.visible_count;
  const areaCount = response?.viewport_count;
  const totalCount = response?.total_count;

  return <aside className="map-results-panel" aria-label={resultsLabel} onScroll={(event) => {
    const panel = event.currentTarget;
    if (hasNextPage && !isLoadingNextPage && !nextPageRequestedRef.current && panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 120) {
      nextPageRequestedRef.current = true;
      onLoadNextPage();
    }
  }}>
    <header className="map-results-panel__summary">
      <div className="map-results-panel__summary-top"><strong>{isAggregateMode ? `${areaCount ?? '...'} ${inAreaLabel}` : `${response ? renderedCount : '...'} ${inListLabel}`}</strong><label>{sortLabel}<select aria-label={sortLabel} value={sort} onChange={(event) => onSortChange(event.target.value as ResultsPanelProps['sort'])}>{Object.entries(sortOptions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
      <div>
        {!isAggregateMode && mapCount !== undefined && mapCount !== renderedCount && <span>{mapCount} {onMapLabel}</span>}
        {areaCount !== undefined && (!isAggregateMode && areaCount !== mapCount) && <span>{areaCount} {inAreaLabel}</span>}
        {totalCount !== undefined && totalCount !== areaCount && <span>{totalCount} {totalLabel}</span>}
      </div>
      {(isAggregateMode || response?.truncated) && <p>{zoomToSeeAllLabel}</p>}
    </header>
    {properties.map((property) => <button ref={property.id === selectedPropertyId ? selectedCardRef : undefined} type="button" key={property.id} className={`map-results-panel__card${property.id === selectedPropertyId ? ' is-selected' : ''}${property.id === highlightedPropertyId ? ' is-highlighted' : ''}`} onClick={() => onSelect(property.id)} onMouseEnter={() => onHover(property.id)} onMouseLeave={() => onHover(null)} onFocus={() => onFocusProperty(property.id)} onBlur={() => onFocusProperty(null)}>
      {property.image_url && <img src={property.image_url} alt="" loading="lazy" />}
      <span><strong>{property.price}</strong><span>{property.title}</span><small>{property.property_type_label} - {property.location}</small></span>
    </button>)}
    {isLoadingNextPage && <p className="map-results-panel__loading">Loading...</p>}
  </aside>;
}
