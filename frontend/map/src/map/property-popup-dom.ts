import type { MapProperty } from '../features/search/api';
import type { PropertyPopupTranslations } from './property-popup-content';

function appendElement(parent: Node, tagName: string, className?: string, text?: string): HTMLElement {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  parent.appendChild(element);
  return element;
}

function addPopupMetaItem(list: HTMLDListElement, label: string, value: number) {
  const item = appendElement(list, 'div');
  appendElement(item, 'dt', undefined, label);
  appendElement(item, 'dd', undefined, String(value));
}

/**
 * MapLibre owns the popup lifecycle, so keep its desktop content outside React.
 * This avoids nested-root cleanup errors when Edge removes a popup DOM node.
 */
export function createPropertyPopupContent(property: MapProperty, translations: PropertyPopupTranslations): DocumentFragment {
  const phone = (property.agent_phone || '66633033133').replace(/[^0-9]/g, '') || '66633033133';
  const fragment = document.createDocumentFragment();
  const media = appendElement(fragment, 'div', 'map-property-popup__media');
  const mediaLink = appendElement(media, 'a') as HTMLAnchorElement;
  mediaLink.href = property.url;
  mediaLink.setAttribute('aria-label', translations.moreDetails);
  if (property.image_url) {
    const image = document.createElement('img');
    image.src = property.image_url;
    image.alt = '';
    image.loading = 'lazy';
    mediaLink.appendChild(image);
  }
  appendElement(media, 'span', 'map-property-popup__type', property.property_type_label);

  const body = appendElement(fragment, 'div', 'map-property-popup__body');
  appendElement(body, 'strong', 'map-property-popup__price', property.price);
  const title = appendElement(body, 'a', 'map-property-popup__title', property.title) as HTMLAnchorElement;
  title.href = property.url;
  appendElement(body, 'p', 'map-property-popup__location', property.location);
  const meta = appendElement(body, 'dl', 'map-property-popup__meta') as HTMLDListElement;
  if (property.bedrooms > 0) addPopupMetaItem(meta, translations.bedroomsLabel, property.bedrooms);
  if (property.bathrooms > 0) addPopupMetaItem(meta, translations.bathroomsLabel, property.bathrooms);
  if (property.area > 0) addPopupMetaItem(meta, translations.areaLabel, Math.round(property.area));
  if (property.area > 0) meta.lastElementChild?.querySelector('dd')?.append(' m2');

  const actions = appendElement(body, 'div', 'map-property-popup__actions');
  const whatsapp = appendElement(actions, 'a', 'map-property-popup__whatsapp', 'WhatsApp') as HTMLAnchorElement;
  whatsapp.href = `https://wa.me/${phone}?text=${encodeURIComponent(`Hello! I am interested in: ${property.title}`)}`;
  whatsapp.target = '_blank';
  whatsapp.rel = 'noreferrer';
  const details = appendElement(actions, 'a', 'map-property-popup__details', translations.moreDetails) as HTMLAnchorElement;
  details.href = property.url;
  return fragment;
}
