import { useEffect, useRef } from 'react';

import type { MapProperty } from '../features/search/api';
import { PropertyPopupContent, type PropertyPopupTranslations } from './property-popup-content';

type PropertyPreviewProps = { property: MapProperty; onClose: () => void; closeLabel: string; translations?: PropertyPopupTranslations };

export function PropertyPreview({ property, onClose, closeLabel, translations }: PropertyPreviewProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
  }, []);

  return <article className="map-property-preview" aria-label={property.title}>
    <button ref={closeRef} type="button" className="map-property-preview__close" onClick={onClose} aria-label={closeLabel}>×</button>
    <PropertyPopupContent property={property} translations={translations} />
  </article>;
}
