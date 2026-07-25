import { useEffect, useState } from 'react';

import type { MapProperty } from './features/search/api';

type MobilePropertySheetProps = { property: MapProperty; onClose: () => void; closeLabel: string; addFavoriteLabel: string; removeFavoriteLabel: string };

function getFavorites(): number[] {
  try { return JSON.parse(localStorage.getItem('favorites') || '[]'); } catch { return []; }
}

export function MobilePropertySheet({ property, onClose, closeLabel, addFavoriteLabel, removeFavoriteLabel }: MobilePropertySheetProps) {
  const [isFavorite, setFavorite] = useState(() => getFavorites().includes(property.id));
  useEffect(() => setFavorite(getFavorites().includes(property.id)), [property.id]);
  const toggleFavorite = () => {
    const favorites = getFavorites();
    const next = favorites.includes(property.id) ? favorites.filter((id) => id !== property.id) : [...favorites, property.id];
    localStorage.setItem('favorites', JSON.stringify(next));
    setFavorite(next.includes(property.id));
  };
  return <section className="map-mobile-property-sheet" aria-label={property.title}>
    <button type="button" className="map-mobile-property-sheet__close" onClick={onClose} aria-label={closeLabel}>×</button>
    {property.image_url && <img src={property.image_url} alt="" loading="lazy" />}
    <div><p>{property.property_type_label} · {property.location}</p><h2>{property.title}</h2><strong>{property.price}</strong><span>{property.bedrooms} / {property.bathrooms} / {property.area}</span></div>
    <footer><button type="button" onClick={toggleFavorite}>{isFavorite ? removeFavoriteLabel : addFavoriteLabel}</button><a href={property.url}>{property.title}</a></footer>
  </section>;
}
