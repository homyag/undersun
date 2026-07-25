import { useCallback, useEffect, useRef, useState } from 'react';

import type { MapAppBootstrap } from '../../bootstrap';
import { EMPTY_MAP_SEARCH_STATE, type MapSearchState } from './state';

type FilterSidebarProps = {
  bootstrap: MapAppBootstrap;
  state: MapSearchState;
  resultCount: number | undefined;
  resultCountLabel: string;
  onChange: (state: MapSearchState) => void;
  className?: string;
};

function DebouncedPriceInput({ label, value, onChange, className = '' }: { label: string; value: string; onChange: (value: string) => void; className?: string }) {
  const [draft, setDraft] = useState(value);
  const timeoutRef = useRef<number | null>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    setDraft(value);
  }, [value]);
  useEffect(() => { onChangeRef.current = onChange; }, [onChange]);
  useEffect(() => {
    return () => { if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current); };
  }, []);

  const updateDraft = (nextValue: string) => {
    setDraft(nextValue);
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => onChangeRef.current(nextValue), 450);
  };

  return <label className={className}>{label}<input inputMode="numeric" value={draft} onChange={(event) => updateDraft(event.target.value)} /></label>;
}

function DebouncedTextInput({ label, placeholder, value, onChange }: { label: string; placeholder: string; value: string; onChange: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  const timeoutRef = useRef<number | null>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    setDraft(value);
  }, [value]);
  useEffect(() => { onChangeRef.current = onChange; }, [onChange]);
  useEffect(() => {
    return () => { if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current); };
  }, []);

  const updateDraft = (nextValue: string) => {
    setDraft(nextValue);
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => onChangeRef.current(nextValue), 450);
  };

  return <label>{label}<input type="search" value={draft} placeholder={placeholder} onChange={(event) => updateDraft(event.target.value)} /></label>;
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function FilterSidebar({ bootstrap, state, resultCount, resultCountLabel, onChange, className = '' }: FilterSidebarProps) {
  const { filters, translations } = bootstrap;
  const [amenityQuery, setAmenityQuery] = useState('');
  const selectedDistrict = filters.districts.find((district) => district.value === state.filters.district);
  const locations = selectedDistrict?.locations || [];
  const update = useCallback(
    (nextFilters: MapSearchState['filters']) => onChange({ ...state, filters: nextFilters }),
    [onChange, state],
  );
  const updateMinPrice = useCallback(
    (minPrice: string) => update({ ...state.filters, minPrice }),
    [state.filters, update],
  );
  const updateMaxPrice = useCallback(
    (maxPrice: string) => update({ ...state.filters, maxPrice }),
    [state.filters, update],
  );
  const updateQuery = useCallback(
    (query: string) => update({ ...state.filters, query }),
    [state.filters, update],
  );
  const updateMinArea = useCallback(
    (minArea: string) => update({ ...state.filters, minArea }),
    [state.filters, update],
  );
  const updateMaxArea = useCallback(
    (maxArea: string) => update({ ...state.filters, maxArea }),
    [state.filters, update],
  );
  const buildStatuses = filters.buildStatuses || [];
  const amenities = filters.amenities || [];
  const matchingAmenities = amenities.filter((amenity) => amenity.label.toLocaleLowerCase().includes(amenityQuery.toLocaleLowerCase()));

  return (
    <aside className={`map-filter-sidebar ${className}`.trim()} aria-label={translations.filters}>
      <header className="map-filter-sidebar__header">
        <strong>{translations.filters}</strong>
        <button type="button" onClick={() => onChange(EMPTY_MAP_SEARCH_STATE)}>{translations.reset}</button>
      </header>
      <p className="map-filter-sidebar__count">{resultCount ?? '...'} {resultCountLabel}</p>
      <fieldset>
        <legend>{translations.all}</legend>
        {(['', 'sale', 'rent'] as const).map((dealType) => (
          <label key={dealType || 'all'}>
            <input type="radio" name="deal_type" checked={state.filters.dealType === dealType}
              onChange={() => update({ ...state.filters, dealType })} />
            {dealType === '' ? translations.all : dealType === 'sale' ? translations.sale : translations.rent}
          </label>
        ))}
      </fieldset>
      <fieldset><legend>{translations.propertyType}</legend>
        {filters.propertyTypes.map((type) => <label key={type.value}><input type="checkbox"
          checked={state.filters.propertyTypes.includes(type.value)} onChange={() => update({ ...state.filters, propertyTypes: toggleValue(state.filters.propertyTypes, type.value) })} />{type.label}</label>)}
      </fieldset>
      {state.filters.dealType !== 'rent' && buildStatuses.length > 0 && <fieldset><legend>{translations.buildStatus}</legend>
        <label><input type="radio" name="build_status" checked={!state.filters.buildStatus} onChange={() => update({ ...state.filters, buildStatus: '' })} />{translations.all}</label>
        {buildStatuses.map((status) => <label key={status.value}><input type="radio" name="build_status" checked={state.filters.buildStatus === status.value} onChange={() => update({ ...state.filters, buildStatus: status.value })} />{status.label}</label>)}
      </fieldset>}
      <div className="map-filter-sidebar__price"><DebouncedPriceInput label={translations.priceFrom} value={state.filters.minPrice} onChange={updateMinPrice} /><DebouncedPriceInput label={translations.priceTo} value={state.filters.maxPrice} onChange={updateMaxPrice} /></div>
      <DebouncedTextInput label={translations.search} placeholder={translations.searchPlaceholder} value={state.filters.query} onChange={updateQuery} />
      <fieldset className="map-filter-sidebar__area"><legend>{translations.area || 'Area'}, m²</legend><div className="map-filter-sidebar__price map-filter-sidebar__range"><DebouncedPriceInput className="map-filter-sidebar__range-input" label={translations.areaFrom || 'Area from'} value={state.filters.minArea} onChange={updateMinArea} /><DebouncedPriceInput className="map-filter-sidebar__range-input" label={translations.areaTo || 'Area to'} value={state.filters.maxArea} onChange={updateMaxArea} /></div></fieldset>
      <fieldset className="map-filter-sidebar__option-group"><legend>{translations.bedrooms}</legend>{['1', '2', '3', '4+'].map((bedroom) => <label key={bedroom}><input type="checkbox" checked={state.filters.bedrooms.includes(bedroom)} onChange={() => update({ ...state.filters, bedrooms: toggleValue(state.filters.bedrooms, bedroom) })} />{bedroom}</label>)}</fieldset>
      <fieldset className="map-filter-sidebar__option-group"><legend>{translations.bathrooms || 'Bathrooms'}</legend>{['1', '2', '3', '4+'].map((bathroom) => <label key={bathroom}><input type="checkbox" checked={state.filters.bathrooms.includes(bathroom)} onChange={() => update({ ...state.filters, bathrooms: toggleValue(state.filters.bathrooms, bathroom) })} />{bathroom}</label>)}</fieldset>
      <label>{translations.district}<select value={state.filters.district} onChange={(event) => update({ ...state.filters, district: event.target.value, location: '' })}><option value="">{translations.all}</option>{filters.districts.map((district) => <option key={district.value} value={district.value}>{district.label}</option>)}</select></label>
      <label>{translations.location}<select value={state.filters.location} disabled={!state.filters.district} onChange={(event) => update({ ...state.filters, location: event.target.value })}><option value="">{translations.all}</option>{locations.map((location) => <option key={location.value} value={location.value}>{location.label}</option>)}</select></label>
      <fieldset><legend>{translations.amenities}</legend>
        <input className="map-filter-sidebar__amenity-search" type="search" value={amenityQuery} placeholder={translations.amenitiesSearch} onChange={(event) => setAmenityQuery(event.target.value)} />
        <div className="map-filter-sidebar__amenities">
          {matchingAmenities.map((amenity) => <label key={amenity.value}><input type="checkbox" checked={state.filters.amenities.includes(amenity.value)} onChange={() => update({ ...state.filters, amenities: toggleValue(state.filters.amenities, amenity.value) })} />{amenity.label}</label>)}
        </div>
      </fieldset>
    </aside>
  );
}
