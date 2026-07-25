import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


@override_settings(MAP_REBUILD_ENABLED=True, MAP_REBUILD_STAFF_ONLY=False)
class MapRebuildShellTests(TestCase):
    def test_renders_ssr_shell_and_typed_bootstrap(self):
        for language in ('ru', 'en', 'th'):
            with self.subTest(language=language):
                response = self.client.get(f'/{language}/map/')

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="property-map-app"')
                self.assertContains(response, 'id="map-app-bootstrap"')
                self.assertNotContains(response, 'js/map/map_page.js')

                content = response.content.decode()
                bootstrap_start = content.index('<script id="map-app-bootstrap" type="application/json">')
                bootstrap_end = content.index('</script>', bootstrap_start)
                bootstrap = json.loads(content[content.index('>', bootstrap_start) + 1:bootstrap_end])

                self.assertEqual(bootstrap['schemaVersion'], 1)
                self.assertEqual(bootstrap['language'], language)
                self.assertTrue(bootstrap['featureFlags']['mapRebuild'])
                self.assertEqual(
                    bootstrap['endpoints']['properties'],
                    f'/{language}/property/ajax/map/',
                )
                self.assertEqual(
                    bootstrap['endpoints']['cards'],
                    f'/{language}/property/ajax/map/cards/',
                )
                self.assertTrue(bootstrap['translations']['inList'])
                self.assertTrue(bootstrap['translations']['onMap'])
                self.assertTrue(bootstrap['translations']['inArea'])
                self.assertTrue(bootstrap['translations']['total'])
                self.assertTrue(bootstrap['translations']['zoomToSeeAll'])
                self.assertTrue(bootstrap['translations']['selectedPropertyUnavailable'])
                self.assertTrue(bootstrap['translations']['mapView'])
                self.assertTrue(bootstrap['translations']['listView'])
                self.assertTrue(bootstrap['translations']['sort'])
                self.assertTrue(bootstrap['translations']['recommended'])
                self.assertTrue(bootstrap['translations']['priceLowToHigh'])
                self.assertTrue(bootstrap['translations']['priceHighToLow'])
                self.assertTrue(bootstrap['translations']['newest'])
                self.assertTrue(bootstrap['translations']['bathrooms'])
                self.assertTrue(bootstrap['translations']['areaFrom'])
                self.assertTrue(bootstrap['translations']['areaTo'])


class LegacyMapShellTests(TestCase):
    @override_settings(MAP_REBUILD_ENABLED=False)
    def test_legacy_template_remains_default(self):
        response = self.client.get('/ru/map/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js/map/map_page.js')
        self.assertNotContains(response, 'id="property-map-app"')


@override_settings(MAP_REBUILD_ENABLED=True, MAP_REBUILD_STAFF_ONLY=True)
class StaffMapRebuildShellTests(TestCase):
    def test_anonymous_user_keeps_legacy_shell(self):
        response = self.client.get('/ru/map/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js/map/map_page.js')
        self.assertNotContains(response, 'id="property-map-app"')

    def test_staff_user_receives_rebuild_shell(self):
        staff_user = get_user_model().objects.create_user(
            username='map-rebuild-staff',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get('/ru/map/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="property-map-app"')
        self.assertNotContains(response, 'js/map/map_page.js')
