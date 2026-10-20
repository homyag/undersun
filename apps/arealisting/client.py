import time
from collections.abc import Iterable
from datetime import datetime
from urllib.parse import urljoin

import requests
from django.conf import settings

from .exceptions import (
    ArealistingAPIError,
    ArealistingConfigurationError,
    ArealistingForbiddenError,
    ArealistingInvalidResponseError,
    ArealistingRateLimitError,
    ArealistingTransportError,
    ArealistingUnauthorizedError,
)


class ArealistingClient:
    """Small API v1 client with safe errors and cursor pagination."""

    MAX_PAGE_SIZE = 500

    def __init__(
        self,
        *,
        api_key=None,
        base_url=None,
        timeout=None,
        max_retries=None,
        session=None,
        sleep=None,
    ):
        self.api_key = api_key if api_key is not None else settings.AREALISTING_API_KEY
        self.base_url = (
            base_url if base_url is not None else settings.AREALISTING_API_URL
        ).rstrip('/') + '/'
        self.timeout = timeout if timeout is not None else settings.AREALISTING_TIMEOUT
        self.max_retries = (
            max_retries
            if max_retries is not None
            else settings.AREALISTING_MAX_RETRIES
        )
        self.session = session or requests.Session()
        self.sleep = sleep or time.sleep

        if not self.api_key:
            raise ArealistingConfigurationError(
                'AREALISTING_API_KEY is not configured.'
            )
        if self.timeout <= 0:
            raise ArealistingConfigurationError(
                'AREALISTING_TIMEOUT must be greater than zero.'
            )
        if self.max_retries < 0:
            raise ArealistingConfigurationError(
                'AREALISTING_MAX_RETRIES cannot be negative.'
            )

        self.session.headers.update(
            {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.api_key}',
                'User-Agent': 'UndersunEstate-ArealistingSync/1.0',
            }
        )

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @staticmethod
    def _format_datetime(value):
        if value is None or value == '':
            return None
        if isinstance(value, datetime):
            rendered = value.isoformat()
            if rendered.endswith('+00:00'):
                return f'{rendered[:-6]}Z'
            return rendered
        return str(value)

    @staticmethod
    def _format_ids(value):
        if value is None or value == '':
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, Iterable):
            return ','.join(str(item) for item in value if item not in (None, ''))
        return str(value)

    @classmethod
    def _validate_limit(cls, limit):
        try:
            normalized = int(limit)
        except (TypeError, ValueError) as exc:
            raise ArealistingConfigurationError('limit must be an integer.') from exc
        if not 1 <= normalized <= cls.MAX_PAGE_SIZE:
            raise ArealistingConfigurationError(
                f'limit must be between 1 and {cls.MAX_PAGE_SIZE}.'
            )
        return normalized

    @staticmethod
    def _retry_after(response):
        value = response.headers.get('Retry-After')
        if value is None:
            return None
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _error_payload(response):
        try:
            payload = response.json()
        except ValueError:
            return '', ''
        if not isinstance(payload, dict):
            return '', ''
        error = payload.get('error')
        if not isinstance(error, dict):
            return '', ''
        return str(error.get('code') or ''), str(error.get('message') or '')

    def _raise_for_response(self, response):
        code, remote_message = self._error_payload(response)
        message = remote_message or f'AREALISTING API returned HTTP {response.status_code}.'
        if self.api_key:
            message = message.replace(self.api_key, '[redacted]')
        kwargs = {'status_code': response.status_code, 'code': code}

        if response.status_code == 401:
            raise ArealistingUnauthorizedError(message, **kwargs)
        if response.status_code == 403:
            raise ArealistingForbiddenError(message, **kwargs)
        if response.status_code == 429:
            raise ArealistingRateLimitError(
                message,
                retry_after=self._retry_after(response),
                **kwargs,
            )
        raise ArealistingAPIError(message, **kwargs)

    def _request(self, path, *, params=None):
        url = urljoin(self.base_url, path.lstrip('/'))

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise ArealistingTransportError(
                        'AREALISTING API request failed after retries.'
                    ) from exc
                self.sleep(2**attempt)
                continue

            if response.status_code == 429 and attempt < self.max_retries:
                self.sleep(self._retry_after(response) or 2**attempt)
                continue

            if 500 <= response.status_code <= 599 and attempt < self.max_retries:
                self.sleep(2**attempt)
                continue

            if not 200 <= response.status_code <= 299:
                self._raise_for_response(response)

            try:
                payload = response.json()
            except ValueError as exc:
                raise ArealistingInvalidResponseError(
                    'AREALISTING API returned invalid JSON.',
                    status_code=response.status_code,
                ) from exc

            if not isinstance(payload, dict):
                raise ArealistingInvalidResponseError(
                    'AREALISTING API returned a non-object JSON response.',
                    status_code=response.status_code,
                )
            return payload

        raise ArealistingTransportError('AREALISTING API request failed.')

    def _iter_collection(self, path, *, params=None, limit=100):
        request_params = {
            key: value for key, value in (params or {}).items() if value not in (None, '')
        }
        request_params['limit'] = self._validate_limit(limit)
        seen_cursors = set()

        while True:
            payload = self._request(path, params=request_params.copy())
            data = payload.get('data')
            meta = payload.get('meta')

            if not isinstance(data, list) or not isinstance(meta, dict):
                raise ArealistingInvalidResponseError(
                    f'AREALISTING {path} response must contain data[] and meta{{}}.'
                )

            for item in data:
                if not isinstance(item, dict):
                    raise ArealistingInvalidResponseError(
                        f'AREALISTING {path} returned a non-object data item.'
                    )
                yield item

            has_more = meta.get('has_more')
            next_cursor = meta.get('next_cursor')
            if has_more is not True:
                break
            if not isinstance(next_cursor, str) or not next_cursor:
                raise ArealistingInvalidResponseError(
                    f'AREALISTING {path} has_more=true without next_cursor.'
                )
            if next_cursor in seen_cursors:
                raise ArealistingInvalidResponseError(
                    f'AREALISTING {path} repeated a pagination cursor.'
                )
            seen_cursors.add(next_cursor)
            request_params['cursor'] = next_cursor

    def iter_projects(self, *, updated_since=None, ids=None, limit=100):
        return self._iter_collection(
            '/projects',
            params={
                'updated_since': self._format_datetime(updated_since),
                'ids': self._format_ids(ids),
            },
            limit=limit,
        )

    def iter_units(
        self,
        *,
        project_ids=None,
        updated_since=None,
        ids=None,
        limit=100,
    ):
        return self._iter_collection(
            '/units',
            params={
                'project_id': self._format_ids(project_ids),
                'updated_since': self._format_datetime(updated_since),
                'ids': self._format_ids(ids),
            },
            limit=limit,
        )

    def iter_payment_plans(
        self,
        *,
        project_ids=None,
        updated_since=None,
        ids=None,
        limit=100,
    ):
        return self._iter_collection(
            '/payment-plans',
            params={
                'project_id': self._format_ids(project_ids),
                'updated_since': self._format_datetime(updated_since),
                'ids': self._format_ids(ids),
            },
            limit=limit,
        )

    def iter_deletions(self, *, since, limit=100):
        formatted_since = self._format_datetime(since)
        if not formatted_since:
            raise ArealistingConfigurationError('since is required for /deletions.')
        return self._iter_collection(
            '/deletions',
            params={'since': formatted_since},
            limit=limit,
        )
