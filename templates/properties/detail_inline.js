{% load i18n %}
{% load l10n %}
{% load currency_tags %}

// ============================================
// Configuration Objects (Django Template Data)
// ============================================

// Property images
const PROPERTY_IMAGES = [
    {% for image in property.images.all %}
        "{{ image.medium.url }}"{% if not forloop.last %},{% endif %}
    {% endfor %}
];

// Property data for JavaScript
const PROPERTY_ID = {{ property.id }};
const PROPERTY_TITLE = '{{ property.title|escapejs }}';
const PROPERTY_SLUG = '{{ property.title|slugify }}';
const PROPERTY_DEAL_TYPE = '{{ property.deal_type }}';

// Property pricing data
const PROPERTY_DATA = {
    price_sale_usd: {% if property.price_sale_thb %}{% convert_price property.price_sale_thb 'THB' 'USD' as sale_usd %}{% if sale_usd %}{{ sale_usd|unlocalize }}{% else %}null{% endif %}{% else %}null{% endif %},
    price_sale_thb: {% if property.price_sale_thb %}{{ property.price_sale_thb|unlocalize }}{% else %}null{% endif %},
    price_sale_rub: {% if property.price_sale_thb %}{% convert_price property.price_sale_thb 'THB' 'RUB' as sale_rub %}{% if sale_rub %}{{ sale_rub|unlocalize }}{% else %}null{% endif %}{% else %}null{% endif %},
    price_rent_monthly_usd: {% if property.price_rent_monthly_thb %}{% convert_price property.price_rent_monthly_thb 'THB' 'USD' as rent_usd %}{% if rent_usd %}{{ rent_usd|unlocalize }}{% else %}null{% endif %}{% else %}null{% endif %},
    price_rent_monthly_thb: {% if property.price_rent_monthly_thb %}{{ property.price_rent_monthly_thb|unlocalize }}{% else %}null{% endif %},
    price_rent_monthly_rub: {% if property.price_rent_monthly_thb %}{% convert_price property.price_rent_monthly_thb 'THB' 'RUB' as rent_rub %}{% if rent_rub %}{{ rent_rub|unlocalize }}{% else %}null{% endif %}{% else %}null{% endif %},
    area_total: {% if property.area_total %}{{ property.area_total|unlocalize }}{% else %}null{% endif %},
    deal_type: '{{ property.deal_type }}'
};

// Map data
const MAP_DATA = {% if property.latitude and property.longitude %}{
    lat: {{ property.latitude|unlocalize }},
    lng: {{ property.longitude|unlocalize }},
    title: '{{ property.title|escapejs }}'
}{% else %}null{% endif %};

// API endpoints
const INQUIRY_ENDPOINT = '{% url "properties:property_inquiry" property.pk %}';

// Translations
const TRANSLATIONS = {
    shareText: '{% trans "Посмотрите на эту недвижимость" %}',
    linkCopied: '{% trans "Ссылка скопирована в буфер обмена" %}',
    copyError: '{% trans "Ошибка при копировании ссылки" %}',
    removedFromFavorites: '{% trans "Удалено из избранного" %}',
    addedToFavorites: '{% trans "Добавлено в избранное" %}',
    collapse: '{% trans "Свернуть" %}',
    showFull: '{% trans "Показать полностью" %}',
    sending: '{% trans "Отправляем..." %}',
    formError: '{% trans "Произошла ошибка. Попробуйте еще раз." %}',
    subscribing: '{% trans "Подписываем..." %}',
    subscribeSuccess: '{% trans "Спасибо за подписку! Мы будем держать вас в курсе последних новостей." %}',
    subscribe: '{% trans "Подписаться" %}'
};

// ============================================
// Django-specific Initialization
// ============================================

document.addEventListener('DOMContentLoaded', function () {
    // Map initialization (requires MAP_DATA from Django)
    if (MAP_DATA && MAP_DATA.lat && MAP_DATA.lng) {
        const map = L.map('property-map').setView([MAP_DATA.lat, MAP_DATA.lng], 20);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        L.marker([MAP_DATA.lat, MAP_DATA.lng])
            .addTo(map)
            .bindPopup(MAP_DATA.title);
    }

    // Favorite toggle (uses PROPERTY_ID from Django)
    const favoriteBtn = document.querySelector('.favorite-btn');
    if (favoriteBtn) {
        favoriteBtn.addEventListener('click', function () {
            toggleFavoriteDetail(PROPERTY_ID);
        });
    }
});
