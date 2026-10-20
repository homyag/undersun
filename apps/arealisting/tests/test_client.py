from datetime import datetime, timezone
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.arealisting.client import ArealistingClient
from apps.arealisting.exceptions import (
    ArealistingConfigurationError,
    ArealistingInvalidResponseError,
    ArealistingUnauthorizedError,
)


class FakeResponse:
    def __init__(self, status_code, payload, *, headers=None):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class ArealistingClientTests(SimpleTestCase):
    def make_client(self, responses, *, max_retries=0, sleep=None):
        session = Mock()
        session.headers = {}
        session.get.side_effect = responses
        client = ArealistingClient(
            api_key='secret-partner-token',
            base_url='https://example.test/api/v1',
            timeout=7,
            max_retries=max_retries,
            session=session,
            sleep=sleep or Mock(),
        )
        return client, session

    def test_requires_api_key(self):
        with self.assertRaises(ArealistingConfigurationError):
            ArealistingClient(api_key='', base_url='https://example.test/api/v1')

    def test_uses_bearer_auth_and_follows_cursor_pagination(self):
        responses = [
            FakeResponse(
                200,
                {
                    'data': [{'external_id': 'project-1'}],
                    'meta': {'has_more': True, 'next_cursor': 'next-page'},
                },
            ),
            FakeResponse(
                200,
                {
                    'data': [{'external_id': 'project-2'}],
                    'meta': {'has_more': False, 'next_cursor': None},
                },
            ),
        ]
        client, session = self.make_client(responses)

        items = list(
            client.iter_projects(
                updated_since=datetime(2026, 3, 1, tzinfo=timezone.utc),
                ids=['project-1', 'project-2'],
                limit=50,
            )
        )

        self.assertEqual([item['external_id'] for item in items], ['project-1', 'project-2'])
        self.assertEqual(session.headers['Authorization'], 'Bearer secret-partner-token')
        first_params = session.get.call_args_list[0].kwargs['params']
        second_params = session.get.call_args_list[1].kwargs['params']
        self.assertEqual(first_params['ids'], 'project-1,project-2')
        self.assertEqual(first_params['limit'], 50)
        self.assertEqual(first_params['updated_since'], '2026-03-01T00:00:00Z')
        self.assertNotIn('cursor', first_params)
        self.assertEqual(second_params['cursor'], 'next-page')

    def test_retries_rate_limit_using_retry_after(self):
        sleep = Mock()
        client, session = self.make_client(
            [
                FakeResponse(
                    429,
                    {'error': {'code': 'RATE_LIMITED', 'message': 'Slow down'}},
                    headers={'Retry-After': '4'},
                ),
                FakeResponse(
                    200,
                    {'data': [], 'meta': {'has_more': False, 'next_cursor': None}},
                ),
            ],
            max_retries=1,
            sleep=sleep,
        )

        self.assertEqual(list(client.iter_projects()), [])
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(4)

    def test_rejects_repeated_pagination_cursor(self):
        page = {
            'data': [],
            'meta': {'has_more': True, 'next_cursor': 'same-cursor'},
        }
        client, _ = self.make_client([FakeResponse(200, page), FakeResponse(200, page)])

        with self.assertRaises(ArealistingInvalidResponseError):
            list(client.iter_projects())

    def test_unauthorized_error_does_not_expose_local_token(self):
        client, _ = self.make_client(
            [
                FakeResponse(
                    401,
                    {
                        'error': {
                            'code': 'UNAUTHORIZED',
                            'message': 'Invalid secret-partner-token',
                        }
                    },
                )
            ]
        )

        with self.assertRaises(ArealistingUnauthorizedError) as raised:
            list(client.iter_projects())

        self.assertNotIn('secret-partner-token', str(raised.exception))

    def test_rejects_malformed_collection_response(self):
        client, _ = self.make_client([FakeResponse(200, {'data': []})])

        with self.assertRaises(ArealistingInvalidResponseError):
            list(client.iter_projects())
