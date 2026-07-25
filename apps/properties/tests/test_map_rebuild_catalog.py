from django.test import TestCase, override_settings


@override_settings(MAP_REBUILD_ENABLED=True, MAP_REBUILD_STAFF_ONLY=False)
class CatalogMapRebuildTests(TestCase):
    def test_catalog_map_route_keeps_the_legacy_catalog_shell(self):
        response = self.client.get('/en/property/', {'map_view': 'true', 'district': 'kathu'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'properties/list.html')
        self.assertContains(response, 'js/list/list_view_toggle.js')
