import type { MapProperty } from '../features/search/api';

export type PropertyPopupTranslations = {
  addFavorite: string;
  removeFavorite: string;
  moreDetails: string;
  bedroomsLabel: string;
  bathroomsLabel: string;
  areaLabel: string;
};

const DEFAULT_TRANSLATIONS: PropertyPopupTranslations = {
  addFavorite: 'Save', removeFavorite: 'Remove', moreDetails: 'Details', bedroomsLabel: 'Bedrooms', bathroomsLabel: 'Bathrooms', areaLabel: 'Area',
};

export function PropertyPopupContent({ property, translations = DEFAULT_TRANSLATIONS }: { property: MapProperty; translations?: PropertyPopupTranslations }) {
  const phone = (property.agent_phone || '66633033133').replace(/[^0-9]/g, '') || '66633033133';
  const whatsappText = `Hello! I am interested in: ${property.title}`;
  return <>
    <div className="map-property-popup__media"><a href={property.url} aria-label={translations.moreDetails}>{property.image_url && <img src={property.image_url} alt="" loading="lazy" />}</a><span className="map-property-popup__type">{property.property_type_label}</span></div>
    <div className="map-property-popup__body"><strong className="map-property-popup__price">{property.price}</strong><a className="map-property-popup__title" href={property.url}>{property.title}</a><p className="map-property-popup__location">{property.location}</p><dl className="map-property-popup__meta">{property.bedrooms > 0 && <div><dt>{translations.bedroomsLabel}</dt><dd>{property.bedrooms}</dd></div>}{property.bathrooms > 0 && <div><dt>{translations.bathroomsLabel}</dt><dd>{property.bathrooms}</dd></div>}{property.area > 0 && <div><dt>{translations.areaLabel}</dt><dd>{Math.round(property.area)} m2</dd></div>}</dl><div className="map-property-popup__actions"><a className="map-property-popup__whatsapp" href={`https://wa.me/${phone}?text=${encodeURIComponent(whatsappText)}`} target="_blank" rel="noreferrer">WhatsApp</a><a className="map-property-popup__details" href={property.url}>{translations.moreDetails}</a></div></div>
  </>;
}
