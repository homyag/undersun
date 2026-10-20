from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.arealisting.exceptions import ArealistingConfigurationError
from apps.arealisting.models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingLocationMapping,
    ArealistingPaymentPlan,
    ArealistingProject,
    ArealistingPriceReview,
    ArealistingSyncRun,
    ArealistingSyncEvent,
    ArealistingSyncState,
    ArealistingUnit,
)
from apps.arealisting.services.sync import ArealistingSyncService
from apps.locations.models import District
from apps.properties.models import Property, PropertyType


PROJECT_PAYLOAD = {
    'external_id': 'project-1',
    'name_en': 'Lavisco Living',
    'name_ru': 'Lavisco Living',
    'description_en': 'Project description',
    'description_ru': 'Описание проекта',
    'developer': 'Lavisco',
    'project_type': 'CONDO',
    'construction_status': 'UNDER_CONSTRUCTION',
    'completion_date': '2026-12-30T21:00:00.000Z',
    'ownership': {
        'freehold_available': False,
        'leasehold_available': True,
    },
    'maintenance_fee': None,
    'maintenance_fee_mode': 'PER_SQM_PER_MONTH',
    'sinking_fund': None,
    'sinking_fund_mode': 'PER_SQM',
    'coordinates': {'lat': 8.092268, 'lng': 98.305334},
    'districts': [
        {
            'external_id': 'location-nai-yang',
            'name': 'Nai Yang',
            'description_en': 'Nai Yang source description',
            'description_ru': 'Описание Nai Yang',
            'gallery': ['https://cdn.example.test/nai-yang.jpg'],
        }
    ],
    'amenities': [{'name_en': 'Pool', 'name_ru': 'Бассейн'}],
    'gallery': ['https://cdn.example.test/project.jpg'],
    'documents': [
        {
            'type': 'FLOOR_PLAN',
            'url': 'https://cdn.example.test/floor-plan.jpg',
        }
    ],
    'updated_at': '2026-03-04T19:43:48.454Z',
}

UNIT_PAYLOAD = {
    'external_id': 'unit-709',
    'project_id': 'project-1',
    'unit_number': '709',
    'bedrooms': 1,
    'bathrooms': None,
    'floor': 7,
    'internal_area_sqm': 34.31,
    'plot_size_sqm': None,
    'sea_view': False,
    'availability_status': 'AVAILABLE',
    'property_type': 'CONDO',
    'price': 5151646.5,
    'currency': 'THB',
    'price_per_sqm': 150150,
    'maintenance_fee': None,
    'maintenance_fee_mode': 'PER_SQM_PER_MONTH',
    'sinking_fund': None,
    'sinking_fund_mode': 'PER_SQM',
    'furnishing': [],
    'gallery': ['https://cdn.example.test/unit-709.jpg'],
    'updated_at': '2026-03-04T07:19:58.634Z',
}

PAYMENT_PLAN_PAYLOAD = {
    'external_id': 'payment-plan-1',
    'project_id': 'project-1',
    'name': 'Standard plan',
    'description': 'Construction-linked payments',
    'items': [
        {
            'stage': 'Reservation',
            'type': 'FIXED_AMOUNT',
            'value': 200000,
            'currency': 'THB',
            'due': 'On reservation',
        }
    ],
    'updated_at': '2026-03-04T08:00:00.000Z',
}


class FakeArealistingClient:
    def __init__(self, *, projects=None, units=None, payment_plans=None, deletions=None):
        self.projects = list(projects or [])
        self.units = list(units or [])
        self.payment_plans = list(payment_plans or [])
        self.deletions = list(deletions or [])
        self.calls = []

    def iter_projects(self, **kwargs):
        self.calls.append(('projects', kwargs))
        return iter(deepcopy(self.projects))

    def iter_units(self, **kwargs):
        self.calls.append(('units', kwargs))
        return iter(deepcopy(self.units))

    def iter_payment_plans(self, **kwargs):
        self.calls.append(('payment_plans', kwargs))
        return iter(deepcopy(self.payment_plans))

    def iter_deletions(self, **kwargs):
        self.calls.append(('deletions', kwargs))
        return iter(deepcopy(self.deletions))


class ArealistingSyncTests(TestCase):
    def create_project(self):
        return ArealistingProject.objects.create(
            external_id='project-1',
            name_en='Lavisco Living',
        )

    def test_full_project_sync_is_idempotent_and_preserves_raw_source_data(self):
        client = FakeArealistingClient(projects=[PROJECT_PAYLOAD])
        service = ArealistingSyncService(client=client)

        first = service.sync(resources=('projects',), full=True)
        second = service.sync(resources=('projects',), full=True)

        self.assertEqual(first['projects']['created'], 1)
        self.assertEqual(second['projects']['updated'], 1)
        self.assertEqual(ArealistingProject.objects.count(), 1)
        project = ArealistingProject.objects.get(external_id='project-1')
        self.assertEqual(project.raw_payload['developer'], 'Lavisco')
        self.assertEqual(project.latitude, Decimal('8.092268'))
        self.assertEqual(ArealistingLocationMapping.objects.count(), 1)
        self.assertEqual(ArealistingAsset.objects.count(), 2)
        self.assertEqual(ArealistingSyncRun.objects.count(), 2)
        self.assertEqual(
            ArealistingSyncState.objects.get(key='resource:projects').status,
            ArealistingSyncState.Status.SUCCESS,
        )

    def test_project_sync_extracts_developer_name_and_preserves_metadata(self):
        payload = deepcopy(PROJECT_PAYLOAD)
        developer = {
            'name': 'Lavisco',
            'logo': 'https://cdn.example.test/logo.png',
            'description_en': 'Developer description. ' * 100,
            'description_ru': 'Описание застройщика. ' * 100,
        }
        payload['developer'] = developer
        service = ArealistingSyncService(
            client=FakeArealistingClient(projects=[payload])
        )
        service.sync(resources=('projects',), full=True)
        project = ArealistingProject.objects.get(external_id=payload['external_id'])
        self.assertEqual(project.developer_name, 'Lavisco')
        self.assertEqual(project.raw_payload['developer'], developer)

        developer['name'] = 'Updated developer'
        service.sync(resources=('projects',), full=True)
        project.refresh_from_db()
        self.assertEqual(project.developer_name, 'Updated developer')
        self.assertEqual(project.raw_payload['developer'], developer)

    def test_project_sync_accepts_empty_developer(self):
        for developer in (None, '', {}, {'name': None, 'description_en': 'x' * 300}):
            with self.subTest(developer=developer):
                payload = {**PROJECT_PAYLOAD, 'developer': developer}
                ArealistingSyncService(
                    client=FakeArealistingClient(projects=[payload])
                ).sync(resources=('projects',), full=True)
                project = ArealistingProject.objects.get(external_id=payload['external_id'])
                self.assertEqual(project.developer_name, '')
                self.assertEqual(project.raw_payload['developer'], developer)

    def test_source_refresh_does_not_overwrite_manual_location_mapping(self):
        service = ArealistingSyncService(
            client=FakeArealistingClient(projects=[PROJECT_PAYLOAD])
        )
        service.sync(resources=('projects',), full=True)
        mapping = ArealistingLocationMapping.objects.get(
            external_id='location-nai-yang'
        )
        mapping.mapping_mode = ArealistingLocationMapping.MappingMode.IGNORE
        mapping.is_confirmed = True
        mapping.save()

        updated_payload = deepcopy(PROJECT_PAYLOAD)
        updated_payload['districts'][0]['name'] = 'Nai Yang Beach'
        service.client.projects = [updated_payload]
        service.sync(resources=('projects',), full=True)

        mapping.refresh_from_db()
        self.assertEqual(mapping.source_name, 'Nai Yang Beach')
        self.assertEqual(
            mapping.mapping_mode,
            ArealistingLocationMapping.MappingMode.IGNORE,
        )
        self.assertTrue(mapping.is_confirmed)

    def test_dry_run_validates_feed_without_database_writes(self):
        service = ArealistingSyncService(
            client=FakeArealistingClient(projects=[PROJECT_PAYLOAD])
        )

        summary = service.sync(resources=('projects',), full=True, dry_run=True)

        self.assertEqual(summary['projects']['seen'], 1)
        self.assertFalse(ArealistingProject.objects.exists())
        self.assertFalse(ArealistingSyncRun.objects.exists())
        self.assertFalse(ArealistingSyncState.objects.exists())

    def test_unit_sync_stores_inventory_and_asset_metadata(self):
        self.create_project()
        service = ArealistingSyncService(
            client=FakeArealistingClient(units=[UNIT_PAYLOAD])
        )

        summary = service.sync(
            resources=('units',),
            full=True,
            project_ids=('project-1',),
        )

        self.assertEqual(summary['units']['created'], 1)
        self.assertEqual(summary['units']['available_created'], 1)
        self.assertEqual(ArealistingSyncEvent.objects.get().kind, ArealistingSyncEvent.Kind.NEW_UNIT)
        unit = ArealistingUnit.objects.get(external_id='unit-709')
        self.assertEqual(unit.price, Decimal('5151646.50'))
        self.assertEqual(unit.internal_area_sqm, Decimal('34.31'))
        self.assertEqual(unit.project.external_id, 'project-1')
        self.assertEqual(unit.assets.count(), 1)
        resource, kwargs = service.client.calls[0]
        self.assertEqual(resource, 'units')
        self.assertEqual(kwargs['project_ids'], ['project-1'])

    def test_unit_sync_reports_source_price_and_sold_changes(self):
        project = self.create_project()
        ArealistingUnit.objects.create(
            external_id='unit-709',
            project=project,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
            price=Decimal('5000000'),
            currency='THB',
        )
        sold_payload = deepcopy(UNIT_PAYLOAD)
        sold_payload['availability_status'] = 'SOLD'
        service = ArealistingSyncService(
            client=FakeArealistingClient(units=[sold_payload])
        )

        summary = service.sync(
            resources=('units',),
            full=True,
            project_ids=('project-1',),
        )

        self.assertEqual(summary['units']['available_created'], 0)
        self.assertEqual(summary['units']['price_changed'], 1)
        self.assertEqual(summary['units']['became_sold'], 1)
        events = ArealistingSyncEvent.objects.filter(run=ArealistingSyncRun.objects.latest('started_at'))
        self.assertCountEqual(
            events.values_list('kind', flat=True),
            [ArealistingSyncEvent.Kind.SOLD, ArealistingSyncEvent.Kind.UNIT_PRICE],
        )
        self.assertEqual(events.get(kind=ArealistingSyncEvent.Kind.UNIT_PRICE).details['before']['price'], '5000000.00')

    def test_linked_unit_characteristic_change_enters_review_queue(self):
        project = self.create_project()
        property_type = PropertyType.objects.create(name='Queue condo')
        district = District.objects.create(name='Queue district', slug='queue-sync-district')
        prop = Property.objects.create(title='Queue card', slug='queue-sync-card',
                                       property_type=property_type, district=district, is_active=False)
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        ArealistingUnit.objects.create(
            external_id='unit-709', project=project, listing_group=group,
            bedrooms=1, internal_area_sqm=Decimal('30.00'),
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
            price=Decimal('5151646.50'), currency='THB',
        )
        service = ArealistingSyncService(client=FakeArealistingClient(units=[UNIT_PAYLOAD]))
        service.sync(resources=('units',), full=True, project_ids=('project-1',))
        event = ArealistingSyncEvent.objects.get(kind=ArealistingSyncEvent.Kind.UNIT_FIELDS)
        self.assertEqual(event.property_id, prop.pk)
        self.assertIn({'field': 'internal_area_sqm', 'before': '30.00', 'after': '34.31'},
                      event.details['changed_fields'])

    def test_sold_unit_is_excluded_from_group_aggregates(self):
        project = self.create_project()
        group = ArealistingListingGroup.objects.create(
            project=project,
            grouping_mode=ArealistingListingGroup.GroupingMode.PROJECT,
            name='Project offer',
        )
        ArealistingUnit.objects.create(
            external_id='available-unit',
            project=project,
            listing_group=group,
            unit_number='101',
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
            price=Decimal('5000000'),
            currency='THB',
            internal_area_sqm=Decimal('30'),
        )
        ArealistingUnit.objects.create(
            external_id='sold-unit',
            project=project,
            listing_group=group,
            unit_number='102',
            availability_status=ArealistingUnit.AvailabilityStatus.SOLD,
            price=Decimal('4000000'),
            currency='THB',
            internal_area_sqm=Decimal('25'),
        )

        ArealistingSyncService.recalculate_listing_group(group)

        group.refresh_from_db()
        self.assertEqual(group.available_units_count, 1)
        self.assertEqual(group.min_price, Decimal('5000000'))
        self.assertEqual(group.max_price, Decimal('5000000'))
        self.assertEqual(group.min_area_sqm, Decimal('30'))
        self.assertEqual(group.currency, 'THB')

    def test_unit_becoming_sold_deactivates_empty_group(self):
        project = self.create_project()
        group = ArealistingListingGroup.objects.create(
            project=project,
            name='One unit',
            is_ready_for_publication=True,
        )
        unit = ArealistingUnit.objects.create(
            external_id='unit-709',
            project=project,
            listing_group=group,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
        )
        sold_payload = deepcopy(UNIT_PAYLOAD)
        sold_payload['availability_status'] = 'SOLD'
        service = ArealistingSyncService(
            client=FakeArealistingClient(units=[sold_payload])
        )

        service.sync(
            resources=('units',),
            full=True,
            project_ids=('project-1',),
        )

        unit.refresh_from_db()
        group.refresh_from_db()
        self.assertEqual(unit.availability_status, 'SOLD')
        self.assertEqual(group.available_units_count, 0)
        self.assertFalse(group.is_active)
        self.assertFalse(group.is_ready_for_publication)

    def test_sold_last_unit_flags_active_card_for_review(self):
        project = self.create_project()
        prop = Property.objects.create(
            title='Linked card', slug='linked-card', deal_type='sale', is_active=True,
            property_type=PropertyType.objects.create(name='condo'),
            district=District.objects.create(name='Sync district', slug='sync-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        ArealistingUnit.objects.create(
            external_id='unit-709', project=project, listing_group=group,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
            price=Decimal('5000000'), currency='THB',
        )
        sold_payload = deepcopy(UNIT_PAYLOAD)
        sold_payload['availability_status'] = 'SOLD'
        ArealistingSyncService(client=FakeArealistingClient(units=[sold_payload])).sync(
            resources=('units',), full=True, project_ids=('project-1',),
        )
        run = ArealistingSyncRun.objects.latest('started_at')
        self.assertTrue(ArealistingSyncEvent.objects.filter(
            run=run, kind=ArealistingSyncEvent.Kind.ACTIVE_WITHOUT_UNITS, property=prop,
        ).exists())
        prop.refresh_from_db()
        self.assertTrue(prop.is_active)

    def test_sync_marks_large_price_change_for_review(self):
        project = self.create_project()
        prop = Property.objects.create(
            title='Price review card', slug='price-review-card', deal_type='sale',
            price_sale_thb=Decimal('1000000'),
            property_type=PropertyType.objects.create(name='condo'),
            district=District.objects.create(name='Review district', slug='review-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        ArealistingUnit.objects.create(
            external_id='unit-709', project=project, listing_group=group,
            availability_status='AVAILABLE', price=Decimal('1000000'), currency='THB',
        )
        payload = deepcopy(UNIT_PAYLOAD)
        payload['price'] = '1400000'
        payload['currency'] = 'THB'
        with patch('apps.arealisting.services.pricing.CurrencyService.convert_price',
                   side_effect=lambda amount, source, target: amount if target == 'THB' else amount / 2):
            summary = ArealistingSyncService(client=FakeArealistingClient(units=[payload])).sync(
                resources=('units',), full=True, project_ids=('project-1',),
            )
        self.assertEqual(summary['price_updates'][0]['status'], 'review')
        review = ArealistingPriceReview.objects.get(status='PENDING')
        event = ArealistingSyncEvent.objects.get(kind=ArealistingSyncEvent.Kind.PRICE_REVIEW)
        self.assertEqual(event.details['review_id'], review.pk)
        self.assertEqual(event.run_id, review.sync_run_id)
        prop.refresh_from_db()
        self.assertEqual(prop.price_sale_thb, Decimal('1000000'))

    def test_empty_full_feed_does_not_deactivate_existing_units(self):
        project = self.create_project()
        unit = ArealistingUnit.objects.create(
            external_id='unit-709',
            project=project,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
        )
        service = ArealistingSyncService(client=FakeArealistingClient(units=[]))

        with self.assertRaises(ArealistingConfigurationError):
            service.sync(
                resources=('units',),
                full=True,
                project_ids=('project-1',),
            )

        unit.refresh_from_db()
        self.assertFalse(unit.is_deleted)
        run = ArealistingSyncRun.objects.latest('started_at')
        self.assertEqual(run.status, ArealistingSyncRun.Status.FAILED)

    def test_incremental_sync_requires_a_watermark(self):
        service = ArealistingSyncService(
            client=FakeArealistingClient(projects=[PROJECT_PAYLOAD])
        )

        with self.assertRaises(ArealistingConfigurationError):
            service.sync(resources=('projects',))

        self.assertFalse(ArealistingProject.objects.exists())

    def test_payment_plan_sync_and_deletion_are_idempotent(self):
        self.create_project()
        service = ArealistingSyncService(
            client=FakeArealistingClient(payment_plans=[PAYMENT_PLAN_PAYLOAD])
        )
        service.sync(
            resources=('payment_plans',),
            full=True,
            project_ids=('project-1',),
        )
        service.sync(
            resources=('payment_plans',),
            full=True,
            project_ids=('project-1',),
        )

        plan = ArealistingPaymentPlan.objects.get(external_id='payment-plan-1')
        self.assertEqual(plan.items[0]['stage'], 'Reservation')
        self.assertFalse(plan.is_deleted)
        self.assertEqual(ArealistingPaymentPlan.objects.count(), 1)

        service.client = FakeArealistingClient(
            deletions=[
                {
                    'external_id': 'payment-plan-1',
                    'entity_type': 'payment_plan',
                    'deleted_at': '2026-03-05T08:00:00.000Z',
                }
            ]
        )
        first = service.sync(resources=('deletions',), full=True)
        second = service.sync(resources=('deletions',), full=True)

        plan.refresh_from_db()
        self.assertTrue(plan.is_deleted)
        self.assertEqual(first['deletions']['deleted'], 1)
        self.assertEqual(second['deletions']['skipped'], 1)

    def test_project_deletion_deactivates_source_children_and_assets(self):
        project = self.create_project()
        unit = ArealistingUnit.objects.create(
            external_id='unit-709',
            project=project,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
        )
        asset = ArealistingAsset.objects.create(
            source_key='asset-key',
            project=project,
            unit=unit,
            source_url='https://cdn.example.test/unit.jpg',
        )
        service = ArealistingSyncService(
            client=FakeArealistingClient(
                deletions=[
                    {
                        'external_id': 'project-1',
                        'entity_type': 'project',
                        'deleted_at': '2026-03-05T08:00:00.000Z',
                    }
                ]
            )
        )

        service.sync(resources=('deletions',), full=True)

        project.refresh_from_db()
        unit.refresh_from_db()
        asset.refresh_from_db()
        self.assertTrue(project.is_deleted)
        self.assertTrue(unit.is_deleted)
        self.assertFalse(asset.is_active)
