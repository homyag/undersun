import type { MapProperty } from '../features/search/api';

export function PropertySelection({ properties, closeLabel, onClose, onSelect }: { properties: MapProperty[]; closeLabel: string; onClose: () => void; onSelect: (propertyId: number) => void }) {
  return <section className="map-property-selection" aria-label="Properties at this location">
    <button type="button" className="map-property-selection__close" onClick={onClose} aria-label={closeLabel}>x</button>
    <div className="map-property-selection__list">
      {properties.map((property) => <button type="button" key={property.id} className="map-property-selection__item" onClick={() => onSelect(property.id)}>
        {property.image_url && <img src={property.image_url} alt="" loading="lazy" />}
        <span><strong>{property.price}</strong><span>{property.title}</span><small>{property.property_type_label} - {property.location}</small></span>
      </button>)}
    </div>
  </section>;
}
