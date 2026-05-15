import json
from django.templatetags.static import static


BUSINESS_PROFILE = {
    'name': 'Undersun Estate',
    'phone_e164': '+66633033133',
    'phone_display': '+66 63 303 3133',
    'email': 'info@undersunestate.com',
    'street_address': '59/358 ตำบล กะทู้ อำเภอกะทู้, Kathu, Phuket, 83120',
    'address_line_1': '59/358 ตำบล กะทู้ อำเภอกะทู้,',
    'address_country_code': 'TH',
    'locality': 'Kathu',
    'region': 'Phuket',
    'postal_code': '83120',
    'latitude': '7.9138837',
    'longitude': '98.3417095',
    'opens': '10:00',
    'closes': '20:00',
    'opening_hours_compact': 'Mo-Fr 10:00-20:00',
    'same_as': [
        'https://www.google.com/maps/place/Undersun+Estate/@7.9138326,98.3420203,17z/data=!3m1!4b1!4m6!3m5!1s0x60e8893a2e97b515:0xd9b2a3109bb2c0e7!8m2!3d7.9138326!4d98.3420203!16s%2Fg%2F11tjdw25jm?entry=ttu&g_ep=EgoyMDI2MDUxMi4wIKXMDSoASAFQAw%3D%3D',
        'https://www.facebook.com/mr.undersunestate/',
        'https://www.instagram.com/undersun.estate/',
        'https://www.youtube.com/@undersun_estate',
        'https://t.me/undersunestate',
        'https://linkedin.com/company/undersunestate',
    ],
}


BUSINESS_PROFILE_I18N = {
    'ru': {
        'address_line_2': 'Kathu, Phuket, 83120, Таиланд',
        'address_full': '59/358 ตำบล กะทู้ อำเภอกะทู้, Kathu, Phuket, 83120, Таиланд',
        'address_country_name': 'Таиланд',
        'hours_label': 'Пн-Пт: 10:00-20:00',
        'map_heading': 'Наше расположение',
        'map_subtitle': 'Наш офис находится в районе Кату, Провинция Пхукет',
        'area_served': 'Пхукет, Таиланд',
    },
    'en': {
        'address_line_2': 'Kathu, Phuket, 83120, Thailand',
        'address_full': '59/358 ตำบล กะทู้ อำเภอกะทู้, Kathu, Phuket, 83120, Thailand',
        'address_country_name': 'Thailand',
        'hours_label': 'Mon-Fri: 10:00-20:00',
        'map_heading': 'Our location',
        'map_subtitle': 'Our office is located in Kathu District, Phuket Province',
        'area_served': 'Phuket, Thailand',
    },
    'th': {
        'address_line_2': 'Kathu, Phuket, 83120, ประเทศไทย',
        'address_full': '59/358 ตำบล กะทู้ อำเภอกะทู้, Kathu, Phuket, 83120, ประเทศไทย',
        'address_country_name': 'ประเทศไทย',
        'hours_label': 'จันทร์-ศุกร์: 10:00-20:00',
        'map_heading': 'ที่ตั้งของเรา',
        'map_subtitle': 'สำนักงานของเราตั้งอยู่ในเขตกะทู้ จังหวัดภูเก็ต',
        'area_served': 'ภูเก็ต ประเทศไทย',
    },
}


def get_business_profile(language_code='ru'):
    language_code = (language_code or 'ru')[:2]
    localized = BUSINESS_PROFILE_I18N.get(language_code, BUSINESS_PROFILE_I18N['ru'])
    payload = dict(BUSINESS_PROFILE)
    payload.update(localized)
    payload['whatsapp_url'] = f"https://wa.me/{BUSINESS_PROFILE['phone_e164'].lstrip('+')}"
    payload['google_maps_url'] = BUSINESS_PROFILE['same_as'][0]
    return payload


def build_business_schema_json(site_root_url, page_url, language_code='ru'):
    profile = get_business_profile(language_code)
    working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    logo_url = f"{site_root_url.rstrip('/')}{static('images/logo_fullscreen.svg')}"
    schema = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'RealEstateAgent',
                '@id': f'{site_root_url}#real-estate-agent',
                'name': profile['name'],
                'url': site_root_url,
                'logo': logo_url,
                'image': logo_url,
                'telephone': profile['phone_display'],
                'email': profile['email'],
                'priceRange': '$$',
                'contactPoint': [{
                    '@type': 'ContactPoint',
                    'telephone': profile['phone_display'],
                    'email': profile['email'],
                    'contactType': 'customer service',
                    'areaServed': ['TH', 'RU', 'GB', 'US'],
                    'availableLanguage': ['English', 'Russian', 'Thai'],
                }],
                'address': {
                    '@type': 'PostalAddress',
                    'streetAddress': profile['street_address'],
                    'addressLocality': profile['locality'],
                    'addressRegion': profile['region'],
                    'postalCode': profile['postal_code'],
                    'addressCountry': profile['address_country_code'],
                },
                'geo': {
                    '@type': 'GeoCoordinates',
                    'latitude': profile['latitude'],
                    'longitude': profile['longitude'],
                },
                'openingHoursSpecification': [{
                    '@type': 'OpeningHoursSpecification',
                    'dayOfWeek': working_days,
                    'opens': profile['opens'],
                    'closes': profile['closes'],
                }],
                'areaServed': {
                    '@type': 'Place',
                    'name': profile['area_served'],
                },
                'availableLanguage': ['ru', 'en', 'th'],
                'sameAs': profile['same_as'],
            },
            {
                '@type': 'LocalBusiness',
                '@id': f'{site_root_url}#local-business',
                'name': profile['name'],
                'url': page_url,
                'logo': logo_url,
                'image': logo_url,
                'telephone': profile['phone_display'],
                'email': profile['email'],
                'priceRange': '$$',
                'address': {
                    '@type': 'PostalAddress',
                    'streetAddress': profile['street_address'],
                    'addressLocality': profile['locality'],
                    'addressRegion': profile['region'],
                    'postalCode': profile['postal_code'],
                    'addressCountry': profile['address_country_code'],
                },
                'geo': {
                    '@type': 'GeoCoordinates',
                    'latitude': profile['latitude'],
                    'longitude': profile['longitude'],
                },
                'openingHoursSpecification': [{
                    '@type': 'OpeningHoursSpecification',
                    'dayOfWeek': working_days,
                    'opens': profile['opens'],
                    'closes': profile['closes'],
                }],
                'sameAs': profile['same_as'],
            },
        ],
    }
    return json.dumps(schema, ensure_ascii=False)
