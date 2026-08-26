from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.currency.models import Currency, CurrencyPreference, ExchangeRate
from apps.locations.models import District
from apps.properties.models import Property, PropertyType


class MapPropertiesEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        thb = Currency.objects.create(
            code='THB',
            name='Thai baht',
            symbol='฿',
            decimal_places=0,
            is_base=True,
        )
        rub = Currency.objects.create(
            code='RUB',
            name='Russian ruble',
            symbol='₽',
            decimal_places=0,
        )
        usd = Currency.objects.create(
            code='USD',
            name='US dollar',
            symbol='$',
            decimal_places=2,
        )
        CurrencyPreference.objects.create(language='ru', default_currency=rub)
        CurrencyPreference.objects.create(language='en', default_currency=usd)
        CurrencyPreference.objects.create(language='th', default_currency=thb)
        ExchangeRate.objects.create(
            base_currency=thb,
            target_currency=rub,
            rate=Decimal('2'),
            date='2026-07-10',
        )
        ExchangeRate.objects.create(
            base_currency=thb,
            target_currency=usd,
            rate=Decimal('0.03'),
            date='2026-07-10',
        )

        property_type = PropertyType.objects.create(
            name='villa',
            name_display='Villa',
        )
        district = District.objects.create(name='Kathu', slug='kathu')
        cls.property = Property.objects.create(
            title='Map test villa',
            title_en='Map test villa EN',
            slug='map-test-villa',
            property_type=property_type,
            district=district,
            description='',
            latitude=Decimal('7.900000000000000'),
            longitude=Decimal('98.300000000000000'),
            price_sale_thb=Decimal('100'),
            bathrooms=2,
            area_total=Decimal('120'),
        )
        cls.second_property = Property.objects.create(
            title='Second map test villa',
            title_en='Second map test villa EN',
            slug='second-map-test-villa',
            property_type=property_type,
            district=district,
            description='',
            latitude=Decimal('7.910000000000000'),
            longitude=Decimal('98.310000000000000'),
            price_sale_thb=Decimal('200'),
            bathrooms=4,
            area_total=Decimal('220'),
        )

    def _set_currency(self, currency):
        session = self.client.session
        session['currency'] = currency
        session.save()

    def test_returns_compact_marker_payload(self):
        self._set_currency('RUB')

        response = self.client.get(
            '/ru/property/ajax/map/',
            {
                'bounds_north': '8.0',
                'bounds_south': '7.8',
                'bounds_east': '98.4',
                'bounds_west': '98.2',
                'zoom': '11',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Server-Timing'].startswith('app;dur='))
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['total_count'], 2)
        self.assertEqual(payload['viewport_count'], 2)
        self.assertEqual(payload['visible_count'], 2)
        self.assertFalse(payload['truncated'])
        self.assertEqual(payload['next_action'], 'none')
        self.assertEqual(payload['zoom'], 11.0)
        self.assertTrue(payload['request_id'])

        property_payload = next(item for item in payload['properties'] if item['id'] == self.property.id)
        self.assertEqual(property_payload, {
            'id': self.property.id,
            'lat': 7.9,
            'lng': 98.3,
        })

    def test_returns_popup_details_when_requested_by_legacy_catalog_map(self):
        self._set_currency('RUB')

        response = self.client.get(
            '/ru/property/ajax/map/',
            {
                'bounds_north': '8.0',
                'bounds_south': '7.8',
                'bounds_east': '98.4',
                'bounds_west': '98.2',
                'zoom': '12',
                'map_mode': 'properties',
                'include_details': '1',
            },
        )

        self.assertEqual(response.status_code, 200)
        property_payload = next(item for item in response.json()['properties'] if item['id'] == self.property.id)
        self.assertEqual(property_payload['title'], 'Map test villa')
        self.assertEqual(property_payload['bathrooms'], 2)
        self.assertEqual(property_payload['area'], 120.0)
        self.assertIn('price', property_payload)

    def test_returns_localized_currency_aware_card_payload(self):
        self._set_currency('USD')

        response = self.client.get('/en/property/ajax/map/cards/')

        self.assertEqual(response.status_code, 200)
        property_payload = next(
            item for item in response.json()['properties'] if item['slug'] == self.property.slug
        )
        self.assertEqual(property_payload['title'], 'Map test villa EN')
        self.assertEqual(property_payload['price'], '$3.00')
        self.assertEqual(property_payload['url'], '/en/property/map-test-villa/')
        self.assertEqual(response.json()['page_size'], 30)
        self.assertFalse(response.json()['has_next'])

    def test_map_endpoints_accept_get_only_and_bound_expensive_input(self):
        self.assertEqual(self.client.post('/ru/property/ajax/map/').status_code, 405)
        self.assertEqual(self.client.post('/ru/property/ajax/map/cards/').status_code, 405)
        self.assertEqual(self.client.get('/ru/property/ajax/map/cards/', {'page': '101'}).status_code, 400)
        self.assertEqual(self.client.get('/ru/property/ajax/map/', {'q': 'x' * 161}).status_code, 400)

    def test_cards_endpoint_uses_page_size_and_same_server_side_filters(self):
        response = self.client.get('/ru/property/ajax/map/cards/', {'bathrooms': '4+', 'min_area': '200'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['page'], 1)
        self.assertEqual(payload['properties'][0]['id'], self.second_property.id)
        self.assertNotIn('image_url', self.client.get('/ru/property/ajax/map/').json()['properties'][0])

    def test_cards_endpoint_paginates_without_expanding_the_marker_payload(self):
        for index in range(30):
            Property.objects.create(
                title=f'Paged map property {index}',
                slug=f'paged-map-property-{index}',
                property_type=self.property.property_type,
                district=self.property.district,
                description='',
                latitude=Decimal(f'7.7{index:02d}'),
                longitude=Decimal(f'98.2{index:02d}'),
                price_sale_thb=Decimal('300'),
            )

        first_page = self.client.get('/ru/property/ajax/map/cards/', {'page': '1'}).json()
        second_page = self.client.get('/ru/property/ajax/map/cards/', {'page': '2'}).json()

        self.assertEqual(len(first_page['properties']), 30)
        self.assertTrue(first_page['has_next'])
        self.assertEqual(second_page['page'], 2)
        self.assertEqual(len(second_page['properties']), 2)
        self.assertFalse(second_page['has_next'])

    def test_filters_by_bathrooms_and_total_area(self):
        response = self.client.get(
            '/ru/property/ajax/map/',
            {
                'bathrooms': '4+',
                'min_area': '200',
                'max_area': '250',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['total_count'], 1)
        self.assertEqual(payload['viewport_count'], 1)
        self.assertEqual([item['id'] for item in payload['properties']], [self.second_property.id])

    def test_usd_price_filter_converts_thb_when_saved_usd_price_is_missing(self):
        self._set_currency('USD')

        marker_response = self.client.get('/en/property/ajax/map/', {'max_price': '4'})
        cards_response = self.client.get('/en/property/ajax/map/cards/', {'max_price': '4'})
        count_response = self.client.get('/en/property/ajax/search-count/', {'max_price': '4'})
        list_response = self.client.get(
            '/en/property/',
            {'currency': 'USD', 'max_price': '4'},
        )
        home_search_response = self.client.get(
            '/en/search/',
            {'type': 'villa', 'max_price': '4'},
        )

        self.assertEqual(marker_response.status_code, 200)
        self.assertEqual(
            [item['id'] for item in marker_response.json()['properties']],
            [self.property.id],
        )
        self.assertEqual(
            [item['id'] for item in cards_response.json()['properties']],
            [self.property.id],
        )
        self.assertEqual(count_response.json()['count'], 1)
        self.assertEqual(
            [property_obj.id for property_obj in list_response.context['properties']],
            [self.property.id],
        )
        self.assertEqual(
            [property_obj.id for property_obj in home_search_response.context['properties']],
            [self.property.id],
        )

    def test_price_filter_url_makes_currency_explicit_and_shareable(self):
        self._set_currency('RUB')

        legacy_response = self.client.get(
            '/ru/property/type/villa/',
            {'max_price': '4'},
        )

        self.assertEqual(legacy_response.status_code, 301)
        self.assertEqual(
            legacy_response['Location'],
            '/ru/property/type/villa/?currency=USD&max_price=4',
        )

        shared_usd_response = self.client.get(legacy_response['Location'])
        shared_rub_response = self.client.get(
            '/ru/property/type/villa/',
            {'currency': 'RUB', 'max_price': '250'},
        )

        self.assertEqual(shared_usd_response.status_code, 200)
        self.assertEqual(
            [property_obj.id for property_obj in shared_usd_response.context['properties']],
            [self.property.id],
        )
        self.assertContains(
            shared_usd_response,
            'name="currency" value="USD" data-price-filter-currency',
            html=False,
        )
        self.assertEqual(shared_rub_response.status_code, 200)
        self.assertEqual(
            [property_obj.id for property_obj in shared_rub_response.context['properties']],
            [self.property.id],
        )

    def test_usd_price_sort_converts_thb_when_saved_usd_price_is_missing(self):
        self._set_currency('USD')
        self.property.price_sale_usd = Decimal('7')
        self.property.save(update_fields=['price_sale_usd'])

        response = self.client.get('/en/property/ajax/map/', {'sort': 'price_asc'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['id'] for item in response.json()['properties']],
            [self.second_property.id, self.property.id],
        )

    def test_rejects_partial_or_invalid_viewport_parameters(self):
        partial_response = self.client.get(
            '/ru/property/ajax/map/',
            {'bounds_north': '8.0'},
        )
        invalid_zoom_response = self.client.get(
            '/ru/property/ajax/map/',
            {'zoom': '25'},
        )

        self.assertEqual(partial_response.status_code, 400)
        self.assertEqual(partial_response.json()['error'], 'invalid_bounds')
        self.assertEqual(invalid_zoom_response.status_code, 400)
        self.assertEqual(invalid_zoom_response.json()['error'], 'invalid_zoom')

    def test_returns_grid_aggregates_for_auto_mode_at_far_zoom(self):
        response = self.client.get(
            '/ru/property/ajax/map/',
            {
                'bounds_north': '8.0',
                'bounds_south': '7.8',
                'bounds_east': '98.4',
                'bounds_west': '98.2',
                'zoom': '9',
                'map_mode': 'auto',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['mode'], 'aggregates')
        self.assertEqual(payload['properties'], [])
        self.assertEqual(payload['aggregate_count'], 1)
        self.assertEqual(payload['aggregates'][0]['count'], 2)
        self.assertEqual(payload['next_action'], 'zoom_in')

    def test_keeps_auto_mode_aggregated_at_catalog_overview_zoom(self):
        response = self.client.get(
            '/ru/property/ajax/map/',
            {
                'bounds_north': '8.0',
                'bounds_south': '7.8',
                'bounds_east': '98.4',
                'bounds_west': '98.2',
                'zoom': '11',
                'map_mode': 'auto',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'aggregates')

    def test_applies_stable_server_side_price_sorting(self):
        ascending = self.client.get('/ru/property/ajax/map/', {'sort': 'price_asc'}).json()
        descending = self.client.get('/ru/property/ajax/map/', {'sort': 'price_desc'}).json()

        self.assertEqual(ascending['sort'], 'price_asc')
        self.assertEqual(descending['sort'], 'price_desc')
        self.assertEqual([item['id'] for item in ascending['properties']], [self.property.id, self.second_property.id])
        self.assertEqual([item['id'] for item in descending['properties']], [self.second_property.id, self.property.id])

    def test_accepts_the_legacy_catalog_date_sort_for_map_requests(self):
        response = self.client.get('/ru/property/ajax/map/', {'sort': '-created_at', 'map_mode': 'aggregates', 'zoom': '10'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sort'], 'newest')
        self.assertEqual(response.json()['mode'], 'aggregates')

    def test_rejects_unknown_map_sort(self):
        response = self.client.get('/ru/property/ajax/map/', {'sort': 'random'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_sort')

    def test_resolves_selected_property_outside_current_viewport_and_aggregate_payload(self):
        response = self.client.get(
            '/en/property/ajax/map/',
            {
                'bounds_north': '7.1',
                'bounds_south': '7.0',
                'bounds_east': '98.1',
                'bounds_west': '98.0',
                'zoom': '9',
                'map_mode': 'auto',
                'selected': str(self.property.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['mode'], 'aggregates')
        self.assertEqual(payload['viewport_count'], 0)
        self.assertEqual(payload['properties'], [])
        self.assertEqual(payload['selected_property_id'], self.property.id)
        self.assertEqual(payload['selected_property']['id'], self.property.id)
        self.assertEqual(payload['selected_property']['title'], 'Map test villa EN')

    def test_returns_null_selected_property_for_unavailable_listing(self):
        response = self.client.get('/ru/property/ajax/map/', {'selected': '999999'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['selected_property_id'], 999999)
        self.assertIsNone(response.json()['selected_property'])

    def test_sale_only_endpoints_exclude_rent_and_mixed_deal_properties(self):
        hidden_properties = [
            Property.objects.create(
                title=f'Hidden {deal_type} map property',
                slug=f'hidden-{deal_type}-map-property',
                property_type=self.property.property_type,
                district=self.property.district,
                description='',
                deal_type=deal_type,
                latitude=Decimal('7.920000000000000'),
                longitude=Decimal('98.320000000000000'),
                price_sale_thb=Decimal('250'),
                price_rent_monthly_thb=Decimal('25'),
            )
            for deal_type in ('rent', 'both')
        ]
        hidden_properties.append(Property.objects.create(
            title='Legacy sale property with a stale URL',
            slug='legacy-sale-property-for-rent',
            property_type=self.property.property_type,
            district=self.property.district,
            description='',
            deal_type='sale',
            latitude=Decimal('7.930000000000000'),
            longitude=Decimal('98.330000000000000'),
            price_sale_thb=Decimal('275'),
        ))

        marker_payload = self.client.get('/ru/property/ajax/map/').json()
        card_payload = self.client.get('/ru/property/ajax/map/cards/').json()
        visible_ids = {
            item['id']
            for item in marker_payload['properties'] + card_payload['properties']
        }

        for property_obj in hidden_properties:
            self.assertNotIn(property_obj.id, visible_ids)

    def test_rejects_invalid_selected_property_id(self):
        response = self.client.get('/ru/property/ajax/map/', {'selected': 'not-an-id'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_selected_property')

    def test_property_payload_query_count_is_constant_for_multiple_results(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/ru/property/ajax/map/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['visible_count'], 2)
        self.assertLessEqual(len(queries), 11)

    @patch('apps.properties.views._load_phuket_district_boundaries')
    def test_district_overlay_returns_verified_boundary_with_provenance(self, load_boundaries):
        geometry = {
            'type': 'Polygon',
            'coordinates': [[[98.2, 7.8], [98.4, 7.8], [98.4, 8.0], [98.2, 7.8]]],
        }
        load_boundaries.return_value = {
            'kathu': {
                'type': 'Feature',
                'properties': {'slug': 'kathu', 'name': 'Kathu', 'province': 'Phuket'},
                'geometry': geometry,
            },
        }

        response = self.client.get('/ru/property/ajax/map-districts/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['boundary_provenance']['dataset'], 'geoBoundaries Thailand ADM2')
        self.assertEqual(payload['boundary_provenance']['admin_level'], 'ADM2')
        self.assertEqual(len(payload['geojson']['features']), 1)
        feature = payload['geojson']['features'][0]
        self.assertEqual(feature['geometry'], geometry)
        self.assertFalse(feature['properties']['is_approximate'])
        self.assertEqual(feature['properties']['boundary_source'], 'geoBoundaries Thailand ADM2')

    @patch('apps.properties.views._load_phuket_district_boundaries', return_value={})
    def test_district_overlay_never_generates_geometry_from_listing_coordinates(self, _load_boundaries):
        response = self.client.get('/ru/property/ajax/map-districts/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['districts'], [])
        self.assertEqual(payload['geojson']['features'], [])
