from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from apps.locations.models import District
from apps.properties.models import Property, PropertyType
from apps.arealisting.exceptions import ArealistingTransportError
from apps.arealisting.models import ArealistingProject, ArealistingListingGroup


class ScheduledPriceTests(TestCase):
    def add_linked_project(self, external_id):
        project = ArealistingProject.objects.create(external_id=external_id)
        prop = Property.objects.create(
            title=external_id, slug=external_id,
            property_type=PropertyType.objects.get_or_create(name='condo')[0],
            district=District.objects.get_or_create(slug='test', defaults={'name': 'Test'})[0],
        )
        ArealistingListingGroup.objects.create(project=project, property=prop)
        return project

    @patch('apps.arealisting.management.commands.update_arealisting_prices.ArealistingClient')
    def test_no_links_does_not_call_api(self, client):
        ArealistingProject.objects.create(external_id='unlinked')
        call_command('update_arealisting_prices', stdout=StringIO())
        client.assert_not_called()

    @patch('apps.arealisting.management.commands.update_arealisting_prices.ArealistingClient')
    @patch('apps.arealisting.management.commands.update_arealisting_prices.ArealistingSyncService')
    def test_only_linked_projects_are_refreshed_with_full_inventory(self, service, client):
        self.add_linked_project('linked')
        ArealistingProject.objects.create(external_id='unlinked')
        deleted = self.add_linked_project('deleted')
        deleted.is_deleted = True
        deleted.save()
        service.return_value.sync.return_value = {'price_updates': []}
        call_command('update_arealisting_prices', stdout=StringIO())
        service.return_value.sync.assert_called_once_with(
            resources=('units',), project_ids=['linked'], full=True, skip_assets=True,
        )

    @patch('apps.arealisting.management.commands.update_arealisting_prices.ArealistingClient')
    @patch('apps.arealisting.management.commands.update_arealisting_prices.ArealistingSyncService')
    def test_failed_project_does_not_stop_other_projects_and_returns_failure(self, service, client):
        self.add_linked_project('a')
        self.add_linked_project('b')
        service.return_value.sync.side_effect = [ArealistingTransportError('Unavailable'), {'price_updates': []}]
        with self.assertRaises(CommandError):
            call_command('update_arealisting_prices', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(service.return_value.sync.call_count, 2)
