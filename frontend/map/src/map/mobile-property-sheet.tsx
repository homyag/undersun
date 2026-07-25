import type { MapProperty } from '../features/search/api';
import { PropertyPopupContent, type PropertyPopupTranslations } from './property-popup-content';

type MobilePropertySheetProps = {
  property: MapProperty;
  onClose: () => void;
  closeLabel: string;
  translations?: PropertyPopupTranslations;
};

export function MobilePropertySheet({ property, onClose, closeLabel, translations }: MobilePropertySheetProps) {
  return <section className="map-mobile-property-sheet" aria-label={property.title}>
    <button type="button" className="map-mobile-property-sheet__close" onClick={onClose} aria-label={closeLabel}>×</button>
    <PropertyPopupContent property={property} translations={translations} />
  </section>;
}
