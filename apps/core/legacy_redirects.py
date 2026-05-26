import re
from urllib.parse import parse_qsl, urlencode


LEGACY_REAL_ESTATE_PATTERN = re.compile(
    r'^/(?:(?P<lang>ru|en|th)/)?real-estate(?:/(?P<rest>.*))?/?$'
)

REAL_ESTATE_CATEGORY_MAP = {
    'condo': 'type/condo/',
    'villa': 'type/villa/',
    'townhouse': 'type/townhouse/',
    'land': 'type/land/',
    'buy': 'sale/',
    'rent': 'rent/',
}

REAL_ESTATE_SPECIAL_MAP = {
    'for-investment': 'property/sale/',
    'ready-made-business': 'services/commercial-real-estate/',
    'ready-made-business-for-rent': 'services/commercial-real-estate/',
    'business': 'services/commercial-real-estate/',
}

REAL_ESTATE_LOCATION_MAP = {
    'kathu': 'locations/kathu-district/',
    'kathu/kamala': 'locations/kathu-district/kamala/',
    'kathu/kathu': 'locations/kathu-district/kathu/',
    'kathu/patong': 'locations/kathu-district/patong/',
    'kathu-district': 'locations/kathu-district/',
    'kathu-district/kamala': 'locations/kathu-district/kamala/',
    'kathu-district/kathu': 'locations/kathu-district/kathu/',
    'kathu-district/patong': 'locations/kathu-district/patong/',
    'mueang-phuket': 'locations/mueang-phuket/',
    'mueang-phuket/chalong': 'locations/mueang-phuket/chalong/',
    'mueang-phuket/karon': 'locations/mueang-phuket/karon/',
    'mueang-phuket/ko-kaeo': 'locations/mueang-phuket/ko-kaeo/',
    'mueang-phuket/ratsada': 'locations/mueang-phuket/ratsada/',
    'mueang-phuket/rawai': 'locations/mueang-phuket/rawai/',
    'mueang-phuket/talad-nuea': 'locations/mueang-phuket/talad-nuea/',
    'mueang-phuket/talad-yai': 'locations/mueang-phuket/talad-yai/',
    'mueang-phuket/wichit': 'locations/mueang-phuket/wichit/',
    'thalang': 'locations/thalang/',
    'thalang/bangtao': 'locations/thalang/bangtao/',
    'thalang/cherng-talay': 'locations/thalang/cherng-talay/',
    'thalang/mai-khao': 'locations/thalang/mai-khao/',
    'thalang/pa-khlok': 'locations/thalang/pa-khlok/',
    'thalang/sakhu': 'locations/thalang/sakhu/',
    'thalang/si-sunthon': 'locations/thalang/si-sunthon/',
    'thalang/thep-krasasttri': 'locations/thalang/thep-krasasttri/',
}

LEGACY_REAL_ESTATE_QUERY_PARAMS = {'page'}


def build_legacy_real_estate_target(path, default_language=None):
    match = LEGACY_REAL_ESTATE_PATTERN.match(path)
    if not match:
        return None

    language = match.group('lang') or default_language
    if not language:
        return None

    rest = (match.group('rest') or '').strip('/')
    if not rest:
        return f'/{language}/property/'

    if rest in REAL_ESTATE_CATEGORY_MAP:
        return f'/{language}/property/{REAL_ESTATE_CATEGORY_MAP[rest]}'

    if rest in REAL_ESTATE_SPECIAL_MAP:
        return f'/{language}/{REAL_ESTATE_SPECIAL_MAP[rest]}'

    if rest in REAL_ESTATE_LOCATION_MAP:
        return f'/{language}/{REAL_ESTATE_LOCATION_MAP[rest]}'

    last_segment = rest.rstrip('/').split('/')[-1]
    detail_match = re.match(r'^\d+-(?P<slug>.+)$', last_segment)
    if detail_match:
        return f"/{language}/property/{detail_match.group('slug')}/"

    return f'/{language}/property/'


def append_legacy_real_estate_query(target_url, query_string):
    raw_query = (query_string or '').strip()
    if not raw_query:
        return target_url

    allowed_params = {
        key: value
        for key, value in parse_qsl(raw_query, keep_blank_values=True)
        if key in LEGACY_REAL_ESTATE_QUERY_PARAMS and value
    }
    if not allowed_params:
        return target_url

    separator = '&' if '?' in target_url else '?'
    return f'{target_url}{separator}{urlencode(allowed_params)}'
