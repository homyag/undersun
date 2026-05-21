from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import translation


logger = logging.getLogger(__name__)


GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_REVIEWS_URL = 'https://mybusiness.googleapis.com/v4/{account_id}/{location_id}/reviews'
PLACE_DETAILS_URL = 'https://places.googleapis.com/v1/{place_resource}'
PLACE_FIELD_MASK = 'id,displayName,rating,userRatingCount,googleMapsUri,reviews'
DEFAULT_MAPS_URL = 'https://maps.google.com/maps?cid=15686779743811846375'
ERROR_CACHE_TIMEOUT = 300
AVATAR_COLORS = (
    'from-blue-400 to-blue-600',
    'from-purple-400 to-pink-600',
    'from-green-400 to-teal-600',
    'from-orange-400 to-red-600',
    'from-indigo-400 to-blue-600',
    'from-pink-400 to-purple-600',
)
STAR_RATING_VALUES = {
    'ONE': 1,
    'TWO': 2,
    'THREE': 3,
    'FOUR': 4,
    'FIVE': 5,
}


def get_homepage_google_reviews(language_code: Optional[str] = None) -> Dict[str, Any]:
    config = getattr(settings, 'GOOGLE_REVIEWS', {})
    language_code = (language_code or translation.get_language() or settings.LANGUAGE_CODE or 'en')[:2]
    maps_url = config.get('MAPS_URL') or DEFAULT_MAPS_URL
    result = _empty_result(maps_url)

    if not config.get('ENABLED'):
        return result

    source = config.get('SOURCE', 'business_profile')
    cache_key = f'google_reviews:{source}:{language_code}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        reviews_data = _fetch_reviews(config, source, language_code, maps_url)
    except requests.RequestException:
        logger.exception('Failed to fetch Google reviews')
        cache.set(cache_key, result, timeout=ERROR_CACHE_TIMEOUT)
        return result

    reviews_data['enabled'] = True
    reviews_data['configured'] = True
    cache.set(cache_key, reviews_data, timeout=int(config.get('CACHE_TIMEOUT', 43200)))
    return reviews_data


def _fetch_reviews(
    config: Dict[str, Any],
    source: str,
    language_code: str,
    maps_url: str,
) -> Dict[str, Any]:
    if source == 'places':
        return _fetch_places_reviews(config, language_code, maps_url)
    return _fetch_business_profile_reviews(config, language_code, maps_url)


def _fetch_business_profile_reviews(
    config: Dict[str, Any],
    language_code: str,
    maps_url: str,
) -> Dict[str, Any]:
    account_id = _resource_name(config.get('BUSINESS_PROFILE_ACCOUNT_ID'), 'accounts')
    location_id = _resource_name(config.get('BUSINESS_PROFILE_LOCATION_ID'), 'locations')
    client_id = config.get('OAUTH_CLIENT_ID')
    client_secret = config.get('OAUTH_CLIENT_SECRET')
    refresh_token = config.get('OAUTH_REFRESH_TOKEN')

    if not all([account_id, location_id, client_id, client_secret, refresh_token]):
        return _empty_result(maps_url)

    access_token = _get_business_profile_access_token(config, client_id, client_secret, refresh_token)
    url = GOOGLE_REVIEWS_URL.format(account_id=account_id, location_id=location_id)
    response = requests.get(
        url,
        params={
            'pageSize': int(config.get('PAGE_SIZE', 10)),
            'orderBy': config.get('ORDER_BY', 'updateTime desc'),
        },
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=float(config.get('REQUEST_TIMEOUT', 4)),
    )
    response.raise_for_status()
    return _normalise_business_profile_response(response.json(), maps_url, language_code)


def _get_business_profile_access_token(
    config: Dict[str, Any],
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> str:
    cache_key = 'google_reviews:business_profile:access_token'
    cached = cache.get(cache_key)
    if cached:
        return cached

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        },
        timeout=float(config.get('REQUEST_TIMEOUT', 4)),
    )
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data['access_token']
    expires_in = int(token_data.get('expires_in') or 3600)
    cache.set(cache_key, access_token, timeout=max(expires_in - 120, 60))
    return access_token


def _normalise_business_profile_response(
    data: Dict[str, Any],
    maps_url: str,
    language_code: str,
) -> Dict[str, Any]:
    rating = _as_float(data.get('averageRating'))
    return {
        'enabled': True,
        'configured': True,
        'business_name': 'Undersun Estate',
        'rating': rating,
        'rating_display': f'{rating:.1f}' if rating else '',
        'user_rating_count': data.get('totalReviewCount'),
        'maps_url': maps_url,
        'reviews': _normalise_business_profile_reviews(data.get('reviews') or [], language_code),
    }


def _normalise_business_profile_reviews(
    raw_reviews: List[Dict[str, Any]],
    language_code: str,
) -> List[Dict[str, Any]]:
    reviews = []
    for index, review in enumerate(raw_reviews):
        text = _business_profile_review_text(review.get('comment') or '', language_code)
        if not text:
            continue

        reviewer = review.get('reviewer') or {}
        author_name = reviewer.get('displayName') or 'Google user'
        rating = _business_profile_rating(review.get('starRating'))
        if not rating:
            continue

        reviews.append({
            'name': author_name,
            'author_url': '',
            'profile_photo_url': reviewer.get('profilePhotoUrl') or '',
            'text': text,
            'short_text': _shorten(text, 118),
            'rating': rating,
            'rating_display': f'{rating:.1f}',
            'relative_time': _format_review_date(review.get('updateTime') or review.get('createTime')),
            'publish_time': review.get('createTime') or '',
            'avatar': _initial(author_name),
            'avatar_color': AVATAR_COLORS[index % len(AVATAR_COLORS)],
        })
    return reviews


def _fetch_places_reviews(
    config: Dict[str, Any],
    language_code: str,
    maps_url: str,
) -> Dict[str, Any]:
    api_key = config.get('API_KEY')
    place_id = config.get('PLACE_ID')
    if not api_key or not place_id:
        return _empty_result(maps_url)

    place_resource = place_id if place_id.startswith('places/') else f'places/{place_id}'
    url = PLACE_DETAILS_URL.format(place_resource=place_resource)
    response = requests.get(
        url,
        params={'languageCode': language_code},
        headers={
            'X-Goog-Api-Key': api_key,
            'X-Goog-FieldMask': PLACE_FIELD_MASK,
        },
        timeout=float(config.get('REQUEST_TIMEOUT', 4)),
    )
    response.raise_for_status()
    return _normalise_place_details(response.json(), maps_url)


def _normalise_place_details(place_data: Dict[str, Any], fallback_maps_url: str) -> Dict[str, Any]:
    maps_url = place_data.get('googleMapsUri') or fallback_maps_url
    rating = _as_float(place_data.get('rating'))
    user_rating_count = place_data.get('userRatingCount')
    display_name = (place_data.get('displayName') or {}).get('text') or 'Undersun Estate'
    reviews = _normalise_place_reviews(place_data.get('reviews') or [])

    return {
        'enabled': True,
        'configured': True,
        'business_name': display_name,
        'rating': rating,
        'rating_display': f'{rating:.1f}' if rating else '',
        'user_rating_count': user_rating_count,
        'maps_url': maps_url,
        'reviews': reviews,
    }


def _normalise_place_reviews(raw_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reviews = []
    for index, review in enumerate(raw_reviews):
        text = _place_review_text(review)
        if not text:
            continue

        author = review.get('authorAttribution') or {}
        author_name = author.get('displayName') or 'Google user'
        rating = _as_float(review.get('rating'))
        if not rating:
            continue

        reviews.append({
            'name': author_name,
            'author_url': author.get('uri') or '',
            'profile_photo_url': author.get('photoUri') or '',
            'text': text,
            'short_text': _shorten(text, 118),
            'rating': rating,
            'rating_display': f'{rating:.1f}',
            'relative_time': review.get('relativePublishTimeDescription') or '',
            'publish_time': review.get('publishTime') or '',
            'avatar': _initial(author_name),
            'avatar_color': AVATAR_COLORS[index % len(AVATAR_COLORS)],
        })
    return reviews


def _business_profile_review_text(comment: str, language_code: str) -> str:
    comment = (comment or '').strip()
    if not comment:
        return ''

    original_marker = '(Original)'
    translated_marker = '(Translated by Google)'

    if original_marker in comment and language_code == 'ru':
        return comment.split(original_marker, 1)[1].strip()

    if comment.startswith(translated_marker):
        comment = comment.replace(translated_marker, '', 1).strip()
        if original_marker in comment:
            comment = comment.split(original_marker, 1)[0].strip()

    return comment


def _place_review_text(review: Dict[str, Any]) -> str:
    for field_name in ('text', 'originalText'):
        value = review.get(field_name)
        if isinstance(value, dict):
            text = (value.get('text') or '').strip()
            if text:
                return text
    return ''


def _business_profile_rating(star_rating: str) -> Optional[float]:
    if not star_rating:
        return None
    return float(STAR_RATING_VALUES.get(star_rating, 0) or 0) or None


def _format_review_date(value: Optional[str]) -> str:
    if not value:
        return ''
    normalized = re.sub(r'Z$', '+00:00', value)
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        return value[:10]


def _resource_name(value: Optional[str], prefix: str) -> str:
    value = (value or '').strip().strip('/')
    if not value:
        return ''
    if value.startswith(f'{prefix}/'):
        return value
    return f'{prefix}/{value}'


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f'{text[:limit].rstrip()}...'


def _initial(name: str) -> str:
    cleaned = (name or '').strip()
    if not cleaned:
        return 'G'
    return cleaned[0].upper()


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _empty_result(maps_url: str) -> Dict[str, Any]:
    return {
        'enabled': False,
        'configured': False,
        'business_name': 'Undersun Estate',
        'rating': None,
        'rating_display': '',
        'user_rating_count': None,
        'maps_url': maps_url,
        'reviews': [],
    }
