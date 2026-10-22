from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override

from apps.arealisting.models import ArealistingListingGroup, ArealistingProject, ArealistingUnit
from apps.locations.models import District
from apps.properties.models import Property, PropertyFeature, PropertyFeatureRelation, PropertyType
from apps.properties.sea_view import sea_view_property_queryset


class SeaViewLandingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        district = District.objects.create(name='Kathu', slug='kathu-sea-view-test')
        property_type = PropertyType.objects.create(name='villa', name_display='Villa')
        cls.manual = Property.objects.create(
            title='Verified sea-view villa', slug='verified-sea-view-villa',
            property_type=property_type, district=district, description='Actual listing',
            price_sale_thb=10000000,
        )
        cls.text_only = Property.objects.create(
            title='Sea view in title only', slug='sea-view-title-only',
            property_type=property_type, district=district, description='No confirmed view',
        )
        cls.linked = Property.objects.create(
            title='Sea-view unit', slug='linked-sea-view-unit',
            property_type=property_type, district=district, description='Source-backed listing',
        )
        cls.sold = Property.objects.create(
            title='Sold sea-view villa', slug='sold-sea-view-villa',
            property_type=property_type, district=district, description='No longer for sale',
            status='sold',
        )
        feature, _ = PropertyFeature.objects.get_or_create(
            name_ru='Вид на море',
            defaults={'name': 'Вид на море', 'name_en': 'Sea view', 'name_th': 'วิวทะเล'},
        )
        cls.feature = feature
        PropertyFeatureRelation.objects.create(property=cls.manual, feature=feature)
        PropertyFeatureRelation.objects.create(property=cls.sold, feature=feature)

        project = ArealistingProject.objects.create(external_id='sea-view-project')
        group = ArealistingListingGroup.objects.create(
            project=project, property=cls.linked, source_owned_fields=['features'],
        )
        cls.unit = ArealistingUnit.objects.create(
            external_id='sea-view-unit', project=project, listing_group=group,
            availability_status='AVAILABLE', sea_view=True,
        )

    def test_only_explicit_current_sea_view_listings_appear(self):
        self.assertEqual(
            set(sea_view_property_queryset().values_list('pk', flat=True)),
            {self.manual.pk, self.linked.pk},
        )

        self.unit.sea_view = False
        self.unit.save(update_fields=['sea_view'])
        PropertyFeatureRelation.objects.create(property=self.linked, feature=self.feature)
        self.assertEqual(
            list(sea_view_property_queryset().values_list('pk', flat=True)),
            [self.manual.pk],
        )

    def test_all_locales_have_their_own_canonical_and_copy(self):
        for language, heading in (
            ('ru', 'Недвижимость с видом на море на Пхукете'),
            ('en', 'Sea-view properties in Phuket'),
            ('th', 'อสังหาริมทรัพย์วิวทะเลในภูเก็ต'),
        ):
            with self.subTest(language=language), override(language):
                url = reverse('properties:property_sea_view')
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading)
                self.assertContains(response, f'<link rel="canonical" href="http://testserver{url}">', html=True)
                for alternate in ('ru', 'en', 'th'):
                    self.assertContains(
                        response,
                        f'<link rel="alternate" hreflang="{alternate}" href="http://testserver/{alternate}/property/sea-view/">',
                        html=True,
                    )
                self.assertContains(response, self.manual.get_absolute_url())
                self.assertNotContains(response, self.text_only.get_absolute_url())

    def test_empty_selection_is_not_indexed(self):
        PropertyFeatureRelation.objects.all().delete()
        self.unit.sea_view = False
        self.unit.save(update_fields=['sea_view'])

        response = self.client.get('/en/property/sea-view/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<meta name="robots" content="noindex, follow">', html=True)

    def test_sitemap_lists_sea_view_only_when_inventory_exists(self):
        url = 'http://testserver/en/property/sea-view/'
        response = self.client.get('/sitemap-static.xml')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, url)

        PropertyFeatureRelation.objects.all().delete()
        self.unit.sea_view = False
        self.unit.save(update_fields=['sea_view'])
        response = self.client.get('/sitemap-static.xml')
        self.assertNotContains(response, url)
