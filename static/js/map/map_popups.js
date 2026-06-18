(function () {
    function escapeHtml(str = '') {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttribute(value = '') {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function buildMapGoalAttrs(propertyId, propertySlug, propertyTypeKey, linkKind) {
        return `
            data-ym-goal="catalog_map_popup_click"
            data-ym-param-id="${escapeAttribute(propertyId)}"
            data-ym-param-slug="${escapeAttribute(propertySlug)}"
            data-ym-param-type="${escapeAttribute(propertyTypeKey)}"
            data-ym-param-link="${escapeAttribute(linkKind)}"
        `.trim();
    }

    function buildPropertyPopupHtml(property) {
        const imageUrl = property.image_url || window.djangoUrls?.noImageSvg || '';
        const propertyTypeLabel = property.property_type_label || property.property_type || '';
        const locationLabel = property.location || '';
        const bedrooms = parseInt(property.bedrooms, 10) || 0;
        const bathrooms = parseInt(property.bathrooms, 10) || 0;
        const areaValue = parseFloat(property.area) || 0;
        const priceLabel = property.price || window.djangoTranslations?.priceOnRequest || 'Price on request';
        const cleanPhone = (property.agent_phone || '+66633033133').replace(/[^0-9]/g, '') || '66633033133';
        const propertySlug = property.slug || '';
        const propertyTypeKey = property.property_type || '';
        const propertyId = property.id || '';
        const detailsUrl = property.url || '#';
        const detailsLinkAttrs = buildMapGoalAttrs(propertyId, propertySlug, propertyTypeKey, 'cta');
        const mediaLinkAttrs = buildMapGoalAttrs(propertyId, propertySlug, propertyTypeKey, 'media');
        const titleLinkAttrs = buildMapGoalAttrs(propertyId, propertySlug, propertyTypeKey, 'title');

        return `
            <div class="property-popup">
                <div class="popup-media" data-property-id="${propertyId}">
                    <a href="${escapeAttribute(detailsUrl)}" class="popup-media-link" ${mediaLinkAttrs}>
                        <img src="${escapeAttribute(imageUrl)}" alt="${escapeHtml(property.title || '')}" class="popup-image" loading="lazy" decoding="async">
                        <span class="popup-media-scrim"></span>
                        <span class="popup-media-cta">
                            <span>${window.djangoTranslations?.moreDetails || 'More details'}</span>
                            <i class="fas fa-arrow-right"></i>
                        </span>
                    </a>
                    <div class="popup-media-chips">
                        ${propertyTypeLabel ? `<span class="popup-media-chip">${escapeHtml(propertyTypeLabel)}</span>` : ''}
                    </div>
                    <button class="favorite-toggle" type="button" onclick="toggleFavorite(${propertyId})" title="${window.djangoTranslations?.addToFavorites || 'Add to favorites'}" aria-label="${window.djangoTranslations?.addToFavorites || 'Add to favorites'}">
                        <i class="far fa-heart" id="favorite-${propertyId}"></i>
                    </button>
                </div>
                <div class="popup-body">
                    <div class="popup-price-row">
                        <div class="popup-price">${escapeHtml(priceLabel)}</div>
                    </div>
                    <a href="${escapeAttribute(detailsUrl)}" class="popup-title-link" ${titleLinkAttrs}>
                        <p class="popup-title">${escapeHtml(property.title || '')}</p>
                    </a>
                    ${locationLabel ? `<div class="popup-location"><i class="fas fa-location-dot"></i>${escapeHtml(locationLabel)}</div>` : ''}
                    <div class="popup-meta">
                        ${bedrooms ? `<span><i class="fas fa-bed"></i>${bedrooms} ${window.djangoTranslations?.bedroomsShort || ''}</span>` : ''}
                        ${bathrooms ? `<span><i class="fas fa-shower"></i>${bathrooms} ${window.djangoTranslations?.bathroomsShort || ''}</span>` : ''}
                        ${areaValue ? `<span><i class="fas fa-ruler-combined"></i>${Math.round(areaValue)} ${window.djangoTranslations?.areaShort || 'm²'}</span>` : ''}
                    </div>
                    <div class="popup-actions">
                        <a href="https://wa.me/${cleanPhone}?text=${encodeURIComponent((window.djangoTranslations?.whatsappText || 'Здравствуйте! Меня интересует объект') + ': ' + (property.title || ''))}" class="popup-action whatsapp" target="_blank" rel="noopener"
                           data-ym-goal="catalog_map_whatsapp_click"
                           data-ym-param-id="${escapeAttribute(propertyId)}"
                           data-ym-param-slug="${escapeAttribute(propertySlug)}"
                           data-ym-param-type="${escapeAttribute(propertyTypeKey)}">
                            <i class="fab fa-whatsapp"></i>
                            WhatsApp
                        </a>
                        <a href="${escapeAttribute(detailsUrl)}" class="popup-action primary" ${detailsLinkAttrs}>
                            ${window.djangoTranslations?.moreDetails || 'More details'}
                        </a>
                    </div>
                </div>
            </div>
        `;
    }

    window.mapPopupUtils = {
        escapeHtml,
        escapeAttribute,
        buildPropertyPopupHtml,
    };
})();
