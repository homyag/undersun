import json
from types import SimpleNamespace

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.test import override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from decimal import Decimal

from apps.locations.models import District, Location
from apps.properties.admin import PropertyAdmin
from apps.properties.models import Developer, Property, PropertyImage, PropertyType
from apps.arealisting.admin import ArealistingListingGroupAdminForm
from apps.arealisting.models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingMediaJob,
    ArealistingLocationMapping,
    ArealistingManualProperty,
    ArealistingProject,
    ArealistingPriceReview,
    ArealistingPropertyChange,
    ArealistingSkippedUnit,
    ArealistingSyncRun,
    ArealistingUnit,
)
from apps.arealisting.services.drafts import (
    create_draft,
    preview_draft,
    refresh_group_property,
    restore_units,
    skip_units,
)
from apps.arealisting.services.field_ownership import (
    PRICE_FIELDS,
    protect_property_manual_changes,
)
from apps.arealisting.services.matching import proposals, save_links
from apps.arealisting.services.media import MAX_SELECTED_MEDIA_ASSETS
from apps.arealisting.services.sync import ArealistingSyncService


class MatchingTests(TestCase):
    def setUp(self):
        self.project = ArealistingProject.objects.create(external_id='match-project', name_en='Example')
        self.unit = ArealistingUnit.objects.create(external_id='match-unit', project=self.project, bedrooms=2)
        self.prop = Property.objects.create(title='Example', slug='existing', complex_name_en='Example',
            property_type=PropertyType.objects.create(name='condo'),
            district=District.objects.create(name='Test', slug='test'), is_active=True)
        self.row = {'property': self.prop.pk, 'units': [self.unit.pk], 'fields': []}

    def test_link_only_preserves_card_and_is_repeatable(self):
        save_links(self.project.pk, [self.row])
        save_links(self.project.pk, [self.row])
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_active)
        self.assertEqual(self.prop.slug, 'existing')
        self.assertEqual(ArealistingListingGroup.objects.count(), 1)
        self.assertEqual(Property.objects.count(), 1)
        self.assertEqual(ArealistingPropertyChange.objects.filter(kind='MATCH').count(), 1)

    def test_matching_history_records_actor_links_and_field_changes(self):
        actor = User.objects.create_superuser('history-admin', 'history@example.test', 'password')
        save_links(self.project.pk, [{**self.row, 'fields': ['bedrooms']}], actor=actor)
        change = ArealistingPropertyChange.objects.get(kind='MATCH')
        self.assertEqual(change.actor, actor)
        self.assertEqual(change.details['units_before'], [])
        self.assertEqual(change.details['units_after'], [self.unit.pk])
        self.assertEqual(change.details['changed_fields'][0]['field'], 'bedrooms')
        self.assertEqual(change.details['changed_fields'][0]['after'], 2)

        self.client.force_login(actor)
        url = reverse('admin:arealisting_arealistingpropertychange_changelist')
        response = self.client.get(url, {'card': self.prop.pk})
        self.assertContains(response, 'связанные предложения')
        self.assertContains(response, str(self.prop))
        detail = self.client.get(reverse(
            'admin:arealisting_arealistingpropertychange_change', args=[change.pk],
        ))
        self.assertContains(detail, 'Предложения')
        self.assertContains(detail, self.unit.external_id)

    def test_detach_allows_relink_to_another_project(self):
        self.login_unlinked_admin()
        save_links(self.project.pk, [self.row])
        group = self.prop.arealisting_group
        url = reverse('admin:arealisting_detach_property', args=[self.prop.pk])

        property_response = self.client.get(
            reverse('admin:properties_property_change', args=[self.prop.pk])
        )
        self.assertContains(property_response, 'Синхронизация AREALISTING')
        self.assertContains(property_response, url)

        response = self.client.get(url)
        self.assertContains(response, 'Отвязать карточку')
        self.assertContains(response, str(self.project))
        self.assertEqual(ArealistingListingGroup.objects.count(), 1)

        response = self.client.post(url, {'group_id': group.pk})
        self.assertRedirects(response, reverse('admin:arealisting_unlinked') + f'?property={self.prop.pk}')
        self.assertFalse(ArealistingListingGroup.objects.exists())
        self.assertEqual(ArealistingPropertyChange.objects.filter(kind='DETACH').count(), 1)
        self.unit.refresh_from_db()
        self.assertIsNone(self.unit.listing_group_id)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.slug, 'existing')
        self.assertTrue(self.prop.is_active)

        other_project = ArealistingProject.objects.create(external_id='other-project', name_en='Other phase')
        other_unit = ArealistingUnit.objects.create(external_id='other-unit', project=other_project)
        save_links(other_project.pk, [{**self.row, 'units': [other_unit.pk]}])
        self.assertEqual(self.prop.arealisting_group.project_id, other_project.pk)

    def test_detach_requires_post_and_current_group(self):
        self.login_unlinked_admin()
        save_links(self.project.pk, [self.row])
        group = self.prop.arealisting_group
        url = reverse('admin:arealisting_detach_property', args=[self.prop.pk])
        response = self.client.post(url, {'group_id': group.pk + 1})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.post(url, {'group_id': 'invalid'}).status_code, 404)
        self.assertTrue(ArealistingListingGroup.objects.filter(pk=group.pk).exists())

    def login_unlinked_admin(self):
        user = User.objects.create_superuser('unlinked-admin', 'admin@example.test', 'password')
        self.client.force_login(user)
        return user

    def test_unlinked_property_admin_shows_project_picker(self):
        self.login_unlinked_admin()
        response = self.client.get(
            reverse('admin:properties_property_change', args=[self.prop.pk])
        )
        self.assertContains(response, 'Карточка не связана с AREALISTING')
        self.assertContains(
            response,
            reverse('admin:arealisting_unlinked') + f'?property={self.prop.pk}',
        )

    def test_unlinked_manual_roundtrip_and_link_removes_manual_marker(self):
        self.login_unlinked_admin()
        url = reverse('admin:arealisting_unlinked')
        manual_url = reverse('admin:arealisting_manual_property', args=[self.prop.pk])
        response = self.client.get(url)
        self.assertEqual(list(response.context['page']), [self.prop])
        self.assertEqual(self.client.get(manual_url).status_code, 405)
        self.client.post(manual_url, {'action': 'manual'})
        self.assertEqual(list(self.client.get(url).context['page']), [])
        self.assertEqual(list(self.client.get(url, {'state': 'manual'}).context['page']), [self.prop])
        self.client.post(manual_url, {'action': 'pending'})
        self.assertFalse(ArealistingManualProperty.objects.exists())
        self.client.post(manual_url, {'action': 'manual'})
        save_links(self.project.pk, [self.row])
        self.assertFalse(ArealistingManualProperty.objects.exists())
        self.assertEqual(list(self.client.get(url).context['page']), [])
        self.client.post(manual_url, {'action': 'manual'})
        self.assertFalse(ArealistingManualProperty.objects.exists())

    def test_unlinked_search_and_exact_property_handoff(self):
        self.login_unlinked_admin()
        self.prop.complex_name_en = 'Different spelling'
        self.prop.save()
        url = reverse('admin:arealisting_unlinked')
        response = self.client.get(url, {'q': str(self.prop.pk)})
        self.assertEqual(list(response.context['page']), [self.prop])
        self.assertEqual(list(self.client.get(url, {'q': 'missing'}).context['page']), [])
        response = self.client.get(url, {'property': self.prop.pk, 'project_q': 'Example'})
        self.assertEqual(list(response.context['project_page']), [self.project])
        matching_url = reverse('admin:arealisting_matching')
        response = self.client.get(matching_url, {
            'property': self.prop.pk,
            'project': self.project.pk,
            'source_state': 'pending',
            'source_activity': 'active',
            'source_q': 'Example',
            'source_page': '2',
        })
        self.assertEqual([p['id'] for p in response.context['matching_data']['properties']], [self.prop.pk])
        self.assertEqual(
            response.context['unlinked_back_url'],
            reverse('admin:arealisting_unlinked')
            + f'?property={self.prop.pk}&state=pending&activity=active&q=Example&page=2',
        )
        with patch('apps.arealisting.admin.ArealistingProjectAdmin._run_sync', return_value=True):
            response = self.client.post(
                reverse('admin:arealisting_load_inventory', args=[self.project.pk]),
                {
                    'property': self.prop.pk,
                    'source_state': 'pending',
                    'source_activity': 'active',
                    'source_q': 'Example',
                    'source_page': '2',
                    'source_project_q': 'Example project',
                },
            )
        self.assertRedirects(
            response,
            reverse('admin:arealisting_unlinked')
            + f'?property={self.prop.pk}&state=pending&activity=active'
              '&q=Example&page=2&project_q=Example+project',
        )

    def test_unlinked_project_picker_waits_for_explicit_search(self):
        self.login_unlinked_admin()

        response = self.client.get(
            reverse('admin:arealisting_unlinked'),
            {'property': self.prop.pk},
        )

        self.assertIsNone(response.context['project_page'])
        self.assertContains(
            response,
            'Введите название комплекса или застройщика',
        )

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_unlinked_selection_search_and_manual_roundtrip(self, _available):
        self.login_unlinked_admin()
        url = reverse('admin:arealisting_unlinked')
        response = self.client.get(url, {'vue': '1', 'activity': 'active', 'q': 'Example',
                                         'property': self.prop.pk})
        self.assertTemplateUsed(response, 'admin/arealisting/unlinked_vue.html')
        data = response.context['unlinked_data']
        self.assertEqual(data['cards'][0]['id'], self.prop.pk)
        self.assertIsNone(data['selected']['project_page'])
        self.assertIn('vue=1', data['cards'][0]['select_url'])

        response = self.client.get(url, {'vue': '1', 'property': self.prop.pk,
                                         'project_q': 'Example', 'activity': 'active'})
        data = response.context['unlinked_data']
        self.assertEqual(data['selected']['projects'][0]['id'], self.project.pk)
        matching_url = data['selected']['projects'][0]['matching_url']
        self.assertIn('source_vue=1', matching_url)
        self.assertIn('vue=1', matching_url)
        with patch('apps.arealisting.admin.price_report_context', return_value={}):
            matching = self.client.get(matching_url)
        self.assertTemplateUsed(matching, 'admin/arealisting/matching_vue.html')
        self.assertIn('vue=1', matching.context['unlinked_back_url'])
        self.assertIn('vue=1', matching.context['unlinked_done_url'])
        self.assertNotIn('property=', matching.context['unlinked_done_url'])

        manual = self.client.post(reverse('admin:arealisting_manual_property', args=[self.prop.pk]), {
            'action': 'manual', 'activity': 'active', 'q': 'Example', 'page': '1', 'vue': '1',
        })
        self.assertIn('vue=1', manual['Location'])
        self.assertIn('activity=active', manual['Location'])
        self.assertTemplateUsed(self.client.get(manual['Location']), 'admin/arealisting/unlinked_vue.html')

        with patch('apps.arealisting.admin.ArealistingProjectAdmin._run_sync', return_value=True):
            loaded = self.client.post(reverse('admin:arealisting_load_inventory', args=[self.project.pk]), {
                'property': self.prop.pk, 'source_state': 'pending', 'source_activity': 'active',
                'source_q': 'Example', 'source_page': '1', 'source_project_q': 'Example',
                'source_vue': '1',
            })
        self.assertIn('property=', loaded['Location'])
        self.assertIn('vue=1', loaded['Location'])

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=False)
    def test_unlinked_falls_back_when_vue_bundle_unavailable(self, _available):
        self.login_unlinked_admin()
        response = self.client.get(reverse('admin:arealisting_unlinked'), {'vue': '1'})
        self.assertTemplateUsed(response, 'admin/arealisting/unlinked.html')

    def test_unlinked_filters_by_property_activity(self):
        self.login_unlinked_admin()
        inactive = Property.objects.create(
            title='Inactive property',
            slug='inactive-property',
            property_type=self.prop.property_type,
            district=self.prop.district,
            is_active=False,
        )
        url = reverse('admin:arealisting_unlinked')

        active_response = self.client.get(url, {'activity': 'active'})
        inactive_response = self.client.get(url, {'activity': 'inactive'})

        self.assertEqual(list(active_response.context['page']), [self.prop])
        self.assertEqual(list(inactive_response.context['page']), [inactive])
        self.assertEqual(inactive_response.context['activity_counts'], {
            'all': 2,
            'active': 1,
            'inactive': 1,
        })
        self.assertContains(inactive_response, 'Все (2)')
        self.assertContains(inactive_response, 'Активные (1)')
        self.assertContains(inactive_response, 'Неактивные (1)')
        self.assertContains(
            inactive_response,
            'name="activity" value="inactive"',
        )
        self.assertEqual(inactive_response.context['activity'], 'inactive')

    def test_unlinked_manual_action_preserves_activity_filter(self):
        self.login_unlinked_admin()
        url = reverse('admin:arealisting_manual_property', args=[self.prop.pk])

        response = self.client.post(url, {
            'action': 'manual',
            'activity': 'active',
        })

        self.assertRedirects(
            response,
            reverse('admin:arealisting_unlinked') + '?state=pending&activity=active',
        )

    def test_unlinked_permissions_and_csrf(self):
        from django.test import Client
        from django.contrib.auth.models import Permission
        user = User.objects.create_user('unlinked-reader', password='password', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_arealistingproject'))
        self.client.force_login(user)
        url = reverse('admin:arealisting_unlinked')
        manual_url = reverse('admin:arealisting_manual_property', args=[self.prop.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(manual_url, {'action': 'manual'}).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename='change_property'))
        self.assertEqual(self.client.get(url).status_code, 200)
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.post(manual_url, {'action': 'manual'}).status_code, 403)
        self.assertFalse(ArealistingManualProperty.objects.exists())

    def test_only_selected_fields_change(self):
        save_links(self.project.pk, [{**self.row, 'fields': ['bedrooms']}])
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.bedrooms, 2)
        self.assertEqual(self.prop.slug, 'existing')
        with self.assertRaises(ValidationError):
            save_links(self.project.pk, [{**self.row, 'fields': ['slug']}])

    def test_unchecking_managed_field_stops_future_updates(self):
        self.unit.bathrooms = Decimal('2')
        self.unit.save(update_fields=['bathrooms'])
        save_links(self.project.pk, [{
            **self.row, 'fields': ['bedrooms', 'bathrooms'],
        }])
        group = self.prop.arealisting_group
        self.login_unlinked_admin()
        response = self.client.get(reverse('admin:arealisting_matching'), {
            'project': self.project.pk, 'property': self.prop.pk,
        })
        self.assertCountEqual(
            response.context['matching_data']['properties'][0]['managed_fields'],
            ['bedrooms', 'bathrooms'],
        )

        save_links(self.project.pk, [{
            **self.row,
            'original_units': [self.unit.pk],
            'fields': [],
            'managed_fields': ['bathrooms'],
            'original_managed_fields': ['bedrooms', 'bathrooms'],
        }])
        group.refresh_from_db()
        self.assertNotIn('bedrooms', group.source_owned_fields)
        self.assertIn('bathrooms', group.source_owned_fields)
        self.assertTrue(set(PRICE_FIELDS) <= set(group.source_owned_fields))

        self.unit.bedrooms = 4
        self.unit.bathrooms = Decimal('3')
        self.unit.save(update_fields=['bedrooms', 'bathrooms'])
        refresh_group_property(group.pk)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.bedrooms, 2)
        self.assertEqual(self.prop.bathrooms, 3)

    def test_save_report_shows_changes_and_field_ownership(self):
        reports = []
        save_links(self.project.pk, [{
            **self.row,
            'fields': ['bedrooms'],
            'managed_fields': ['bedrooms'],
            'original_managed_fields': [],
        }], reports=reports)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['changed_fields'], [
            {'field': 'bedrooms', 'before': None, 'after': 2},
        ])
        self.assertEqual(reports[0]['managed_added'], ['bedrooms'])
        self.assertEqual(reports[0]['managed_removed'], [])

        reports = []
        save_links(self.project.pk, [{
            **self.row,
            'original_units': [self.unit.pk],
            'fields': [],
            'managed_fields': [],
            'original_managed_fields': ['bedrooms'],
        }], reports=reports)
        self.assertEqual(reports[0]['managed_removed'], ['bedrooms'])
        self.assertEqual(reports[0]['changed_fields'], [])

    def test_save_report_explains_owned_field_without_source_value(self):
        self.unit.bathrooms = Decimal('2')
        self.unit.save(update_fields=['bathrooms'])
        save_links(self.project.pk, [{**self.row, 'fields': ['bathrooms']}])
        self.unit.bathrooms = None
        self.unit.save(update_fields=['bathrooms'])
        reports = []
        save_links(self.project.pk, [{
            **self.row,
            'original_units': [self.unit.pk],
            'fields': [],
            'managed_fields': ['bathrooms'],
            'original_managed_fields': ['bathrooms'],
        }], reports=reports)
        self.assertEqual(reports[0]['not_applied'][0]['field'], 'bathrooms')
        self.assertIn('Нет значения', reports[0]['not_applied'][0]['reason'])
        self.assertIn(
            'build_status',
            [item['field'] for item in reports[0]['unavailable_fields']],
        )

    def test_explicit_managed_fields_reject_stale_selection(self):
        save_links(self.project.pk, [{**self.row, 'fields': ['bedrooms']}])
        with self.assertRaisesMessage(ValidationError, 'Поля под управлением AREALISTING изменились'):
            save_links(self.project.pk, [{
                **self.row,
                'original_units': [self.unit.pk],
                'fields': [],
                'managed_fields': [],
                'original_managed_fields': [],
            }])
        self.assertIn('bedrooms', self.prop.arealisting_group.source_owned_fields)

        group = self.prop.arealisting_group
        group.locked_fields = ['bathrooms']
        group.save(update_fields=['locked_fields'])
        with self.assertRaisesMessage(ValidationError, 'защищённого поля'):
            save_links(self.project.pk, [{
                **self.row,
                'original_units': [self.unit.pk],
                'fields': [],
                'managed_fields': ['bedrooms', 'bathrooms'],
                'original_managed_fields': ['bedrooms'],
            }])

    def test_additional_matching_fields_have_preview_and_update_card(self):
        self.project.construction_status = 'COMPLETED'
        self.project.completion_date = timezone.now().replace(year=2027)
        self.project.save(update_fields=['construction_status', 'completion_date'])
        self.unit.bathrooms = Decimal('2')
        self.unit.plot_size_sqm = Decimal('64.25')
        self.unit.save(update_fields=['bathrooms', 'plot_size_sqm'])
        self.login_unlinked_admin()
        response = self.client.get(reverse('admin:arealisting_matching'), {
            'project': self.project.pk, 'property': self.prop.pk,
        })
        data = response.context['matching_data']
        self.assertEqual(data['fields']['bathrooms'], 'Ванные')
        self.assertEqual(data['fields']['area_land'], 'Площадь участка')
        self.assertEqual(data['project_values']['build_status'], 'completed')
        self.assertEqual(data['project_values']['year_built'], 2027)
        self.assertEqual(data['units'][0]['bathrooms'], 2)
        self.assertEqual(data['units'][0]['area_land'], Decimal('64.25'))
        self.assertContains(response, 'снятая галочка отключит обновление')

        save_links(self.project.pk, [{
            **self.row,
            'fields': ['bathrooms', 'area_land', 'build_status', 'year_built'],
        }])
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.bathrooms, 2)
        self.assertEqual(self.prop.area_land, Decimal('64.25'))
        self.assertEqual(self.prop.build_status, 'completed')
        self.assertEqual(self.prop.year_built, 2027)

        self.unit.bathrooms = Decimal('3')
        self.unit.plot_size_sqm = Decimal('70')
        self.unit.save(update_fields=['bathrooms', 'plot_size_sqm'])
        refresh_group_property(self.prop.arealisting_group.pk)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.bathrooms, 3)
        self.assertEqual(self.prop.area_land, Decimal('70'))

    def test_matching_rejects_ambiguous_new_unit_fields(self):
        self.unit.bathrooms = Decimal('1.5')
        self.unit.plot_size_sqm = Decimal('50')
        self.unit.save(update_fields=['bathrooms', 'plot_size_sqm'])
        self.assertNotIn('bathrooms', proposals(self.project, [self.unit]))
        with self.assertRaisesMessage(ValidationError, 'Нет однозначного значения'):
            save_links(self.project.pk, [{**self.row, 'fields': ['bathrooms']}])

        second = ArealistingUnit.objects.create(
            external_id='different-land', project=self.project,
            plot_size_sqm=Decimal('75'),
        )
        self.assertNotIn('area_land', proposals(self.project, [self.unit, second]))

    def test_activity_change_is_explicit_and_checks_stale_value(self):
        save_links(self.project.pk, [{
            **self.row,
            'is_active': False,
            'expected_is_active': True,
        }])
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.is_active)

        with self.assertRaisesMessage(ValidationError, 'Активность карточки изменена'):
            save_links(self.project.pk, [{
                **self.row,
                'is_active': True,
                'expected_is_active': True,
            }])

    def test_locked_activity_cannot_be_changed(self):
        save_links(self.project.pk, [self.row])
        group = ArealistingListingGroup.objects.get(property=self.prop)
        group.locked_fields = ['is_active']
        group.save(update_fields=('locked_fields', 'updated_at'))

        with self.assertRaisesMessage(ValidationError, 'Активность карточки защищена'):
            save_links(self.project.pk, [{
                **self.row,
                'is_active': False,
                'expected_is_active': True,
            }])

        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_active)

    def test_conflicting_batch_rolls_back(self):
        with self.assertRaises(ValidationError):
            save_links(self.project.pk, [self.row, self.row])
        self.assertFalse(ArealistingListingGroup.objects.exists())
        self.unit.refresh_from_db()
        self.assertIsNone(self.unit.listing_group_id)

    def test_stale_preview_rejected(self):
        with self.assertRaises(ValidationError):
            save_links(self.project.pk, [{**self.row, 'fields': ['bedrooms'],
                'expected': {'bedrooms': {'before': None, 'after': 9}}}])
        self.assertFalse(ArealistingListingGroup.objects.exists())

    def test_existing_selection_can_be_replaced(self):
        save_links(self.project.pk, [self.row])
        second = ArealistingUnit.objects.create(project=self.project, external_id='replacement')
        save_links(self.project.pk, [{**self.row, 'original_units': [self.unit.pk], 'units': [second.pk]}])
        self.unit.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNone(self.unit.listing_group_id)
        self.assertEqual(second.listing_group.property_id, self.prop.pk)
        self.assertEqual(ArealistingListingGroup.objects.count(), 1)
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_active)

    def test_stale_selection_cannot_replace_newer_link(self):
        save_links(self.project.pk, [self.row])
        second = ArealistingUnit.objects.create(project=self.project, external_id='replacement')
        with self.assertRaisesMessage(ValidationError, 'Связь изменена после открытия страницы'):
            save_links(self.project.pk, [{**self.row, 'original_units': [], 'units': [second.pk]}])
        self.unit.refresh_from_db()
        self.assertIsNotNone(self.unit.listing_group_id)
        second.refresh_from_db()
        self.assertIsNone(second.listing_group_id)

    def test_prices_use_only_selected_available_units_and_preserve_card(self):
        from apps.arealisting.services.pricing import update_group_price
        save_links(self.project.pk, [self.row])
        self.unit.refresh_from_db()
        self.unit.price = Decimal('1000000')
        self.unit.currency = 'THB'
        self.unit.availability_status = 'AVAILABLE'
        self.unit.save()
        ArealistingUnit.objects.create(project=self.project, external_id='unselected-cheap',
            price=1, currency='THB', availability_status='AVAILABLE')
        group = ArealistingListingGroup.objects.get()
        reports = []
        with patch('apps.arealisting.services.pricing.CurrencyService.convert_price',
                   side_effect=lambda amount, source, target: amount if target == 'THB' else amount / 2):
            self.assertTrue(update_group_price(group.pk, reports=reports))
            self.assertTrue(update_group_price(group.pk, reports=reports))
        self.assertEqual([r['status'] for r in reports], ['updated', 'unchanged'])
        price_changes = ArealistingPropertyChange.objects.filter(kind='PRICE', property=self.prop)
        self.assertEqual(price_changes.count(), 1)
        self.assertEqual(price_changes.first().details['changed_fields'][0]['field'], 'price_sale_thb')
        self.assertIsNone(reports[0]['before']['price_sale_thb'])
        self.assertEqual(reports[0]['after']['price_sale_thb'], '1000000.00')
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.price_sale_thb, Decimal('1000000'))
        self.assertEqual(self.prop.price_sale_usd, Decimal('500000'))
        self.assertTrue(self.prop.is_active)
        self.unit.availability_status = 'SOLD'
        self.unit.save()
        self.assertFalse(update_group_price(group.pk, reports=reports))
        self.assertEqual(reports[-1]['status'], 'skipped')
        self.assertEqual(reports[-1]['reason'], 'нет доступных выбранных предложений')
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.price_sale_thb, Decimal('1000000'))

    def test_missing_exchange_rate_preserves_all_prices(self):
        from apps.arealisting.services.pricing import update_group_price
        save_links(self.project.pk, [self.row])
        self.unit.refresh_from_db()
        self.unit.price = 100
        self.unit.currency = 'THB'
        self.unit.availability_status = 'AVAILABLE'
        self.unit.save()
        with patch('apps.arealisting.services.pricing.CurrencyService.convert_price', return_value=None):
            self.assertFalse(update_group_price(ArealistingListingGroup.objects.get().pk))
        self.prop.refresh_from_db()
        self.assertIsNone(self.prop.price_sale_thb)

    @override_settings(AREALISTING_PRICE_REVIEW_PERCENT=30)
    def test_large_price_change_waits_for_explicit_approval(self):
        from apps.arealisting.services.pricing import approve_price_review, update_group_price
        save_links(self.project.pk, [self.row])
        self.unit.price = Decimal('1400000')
        self.unit.currency = 'THB'
        self.unit.availability_status = 'AVAILABLE'
        self.unit.save(update_fields=['price', 'currency', 'availability_status'])
        Property.objects.filter(pk=self.prop.pk).update(
            price_sale_thb=Decimal('1000000'),
            price_sale_usd=Decimal('500000'),
            price_sale_rub=Decimal('500000'),
        )
        group = self.prop.arealisting_group
        reports = []
        actor = User.objects.create_superuser('price-admin', 'price@example.test', 'password')
        with patch('apps.arealisting.services.pricing.CurrencyService.convert_price',
                   side_effect=lambda amount, source, target: amount if target == 'THB' else amount / 2):
            self.assertFalse(update_group_price(group.pk, reports=reports))
            self.assertFalse(update_group_price(group.pk, reports=reports))
            self.assertEqual(ArealistingPriceReview.objects.filter(status='PENDING').count(), 1)
            review = ArealistingPriceReview.objects.get(status='PENDING')
            self.assertEqual(review.change_percent, Decimal('40.00'))
            self.assertEqual(reports[-1]['status'], 'review')
            self.assertEqual(reports[-1]['review_id'], review.pk)
            self.prop.refresh_from_db()
            self.assertEqual(self.prop.price_sale_thb, Decimal('1000000'))
            self.assertEqual(ArealistingPropertyChange.objects.filter(kind='PRICE').count(), 0)
            approve_price_review(review.pk, user=actor)
        self.prop.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(self.prop.price_sale_thb, Decimal('1400000'))
        self.assertEqual(review.status, 'APPROVED')
        self.assertEqual(review.reviewed_by, actor)
        self.assertEqual(ArealistingPropertyChange.objects.get(kind='PRICE').actor, actor)

    @override_settings(AREALISTING_PRICE_REVIEW_PERCENT=30)
    def test_price_review_rechecks_source_and_rejection_is_not_requeued(self):
        from apps.arealisting.services.pricing import (
            approve_price_review, reject_price_review, update_group_price,
        )
        save_links(self.project.pk, [self.row])
        self.unit.price = Decimal('1400000')
        self.unit.currency = 'THB'
        self.unit.availability_status = 'AVAILABLE'
        self.unit.save(update_fields=['price', 'currency', 'availability_status'])
        Property.objects.filter(pk=self.prop.pk).update(price_sale_thb=Decimal('1000000'))
        group = self.prop.arealisting_group
        actor = User.objects.create_superuser('reject-admin', 'reject@example.test', 'password')
        with patch('apps.arealisting.services.pricing.CurrencyService.convert_price',
                   side_effect=lambda amount, source, target: amount if target == 'THB' else amount / 2):
            update_group_price(group.pk)
            review = ArealistingPriceReview.objects.get(status='PENDING')
            self.unit.price = Decimal('1500000')
            self.unit.save(update_fields=['price'])
            with self.assertRaisesMessage(ValidationError, 'изменились'):
                approve_price_review(review.pk, user=actor)
            self.prop.refresh_from_db()
            self.assertEqual(self.prop.price_sale_thb, Decimal('1000000'))
            update_group_price(group.pk)
            review.refresh_from_db()
            self.assertEqual(review.status, 'SUPERSEDED')
            replacement = ArealistingPriceReview.objects.get(status='PENDING')
            reject_price_review(replacement.pk, user=actor)
            update_group_price(group.pk)
        self.assertFalse(ArealistingPriceReview.objects.filter(status='PENDING').exists())
        self.assertEqual(ArealistingPriceReview.objects.filter(status='REJECTED').count(), 1)

    def test_source_recalculation_does_not_unpublish(self):
        save_links(self.project.pk, [self.row])
        ArealistingSyncService.recalculate_listing_group(ArealistingListingGroup.objects.get())
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_active)

    def prepare_draft_source(self):
        self.project.project_type = 'CONDO'
        self.project.name_ru = 'Тестовый комплекс'
        self.project.name_en = 'Test project'
        self.project.districts = [{'external_id': 'draft-location'}]
        self.project.save()
        self.unit.property_type = 'CONDO'
        self.unit.availability_status = ArealistingUnit.AvailabilityStatus.AVAILABLE
        self.unit.unit_number = 'A101'
        self.unit.internal_area_sqm = Decimal('42.50')
        self.unit.price = Decimal('5000000')
        self.unit.currency = 'THB'
        self.unit.save()
        ArealistingLocationMapping.objects.create(
            external_id='draft-location',
            mapping_mode=ArealistingLocationMapping.MappingMode.DISTRICT,
            district=self.prop.district,
            is_confirmed=True,
        )

    def test_draft_readiness_explains_missing_work_and_updates_after_edits(self):
        self.prepare_draft_source()
        prop = create_draft(self.project.pk, [self.unit.pk])
        group = prop.arealisting_group
        self.login_unlinked_admin()
        url = reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['report']['ready'])
        self.assertContains(response, 'Проверка перед публикацией')
        self.assertContains(response, 'В карточке нет фотографии')
        self.assertContains(response, 'Добавьте описание')
        self.assertContains(response, reverse('admin:properties_property_change', args=[prop.pk]))

        prop.description = '<p><br></p>'
        prop.save(update_fields=['description'])
        self.assertFalse(self.client.get(url).context['report']['ready'])

        prop.description = 'Описание объекта'
        prop.price_sale_thb = Decimal('5000000')
        prop.save(update_fields=['description', 'price_sale_thb'])
        PropertyImage.objects.bulk_create([
            PropertyImage(property=prop, image='properties/readiness.jpg'),
        ])
        response = self.client.get(url)
        self.assertTrue(response.context['report']['ready'])
        self.assertContains(response, 'Основные пункты выполнены')
        card_response = self.client.get(reverse('admin:properties_property_change', args=[prop.pk]))
        self.assertContains(card_response, url)

    def test_preview_and_create_inactive_draft(self):
        self.prepare_draft_source()
        self.project.description_ru = 'Описание из источника'
        self.project.developer_name = 'Arealisting Developer'
        self.project.construction_status = 'READY_TO_MOVE_IN'
        self.project.amenities = [
            {'name_ru': 'Бассейн', 'name_en': 'Swimming Pool'},
            {'name_ru': 'Спортзал', 'name_en': 'Gym'},
        ]
        self.project.gallery = [
            'https://cdn.example.test/project.jpg',
            'https://cdn.example.test/project.jpg',
            'data:image/png;base64,unsafe',
        ]
        self.project.save()
        self.unit.bathrooms = Decimal('2')
        self.unit.plot_size_sqm = Decimal('64.25')
        self.unit.furnishing = [{'name': 'Fully Furnished', 'is_default': True}]
        self.unit.sea_view = True
        self.unit.gallery = [
            'https://cdn.example.test/unit-a101.jpg',
            'https://cdn.example.test/unit-a101.jpg',
            'http://cdn.example.test/insecure.jpg',
            42,
        ]
        self.unit.save()
        project_asset = ArealistingAsset.objects.create(
            source_key='preview-project-image',
            project=self.project,
            source_url='https://cdn.example.test/project.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        unit_asset = ArealistingAsset.objects.create(
            source_key='preview-unit-image',
            project=self.project,
            unit=self.unit,
            source_url='https://cdn.example.test/unit-a101.jpg',
            asset_type=ArealistingAsset.AssetType.UNIT_GALLERY,
        )

        preview = preview_draft(self.project.pk, [self.unit.pk])
        prop = create_draft(self.project.pk, [self.unit.pk])

        self.assertEqual(preview['property_type'], str(self.prop.property_type))
        self.assertEqual(preview['district'], str(self.prop.district))
        self.assertFalse(preview['is_active'])
        self.assertIn('A101', preview['title_en'])
        self.assertEqual(preview['project_images'], [{
            'id': project_asset.pk,
            'url': 'https://cdn.example.test/project.jpg',
            'role': 'GALLERY',
        }])
        self.assertEqual(preview['project_images_total'], 1)
        self.assertEqual(preview['unit_images'], [{
            'id': self.unit.pk,
            'number': 'A101',
            'status': ArealistingUnit.AvailabilityStatus.AVAILABLE,
            'images': [{
                'id': unit_asset.pk,
                'url': 'https://cdn.example.test/unit-a101.jpg',
                'role': 'GALLERY',
            }],
            'images_total': 1,
        }])
        self.assertEqual(preview['media_assets_total'], 2)
        self.assertFalse(prop.is_active)
        self.assertEqual(prop.deal_type, 'sale')
        self.assertEqual(prop.property_type, self.prop.property_type)
        self.assertEqual(prop.district, self.prop.district)
        self.assertEqual(prop.area_total, Decimal('42.50'))
        self.assertEqual(prop.area_land, Decimal('64.25'))
        self.assertEqual(prop.bathrooms, 2)
        self.assertTrue(prop.furnished)
        self.assertTrue(prop.pool)
        self.assertTrue(prop.gym)
        self.assertEqual(prop.description_ru, 'Описание из источника')
        self.assertEqual(prop.developer.name, 'Arealisting Developer')
        self.assertEqual(Developer.objects.count(), 1)
        self.assertEqual(
            set(prop.features.values_list('feature__name_en', flat=True)),
            {'Swimming Pool', 'Gym', 'Sea view'},
        )
        self.assertEqual(prop.arealisting_group.units.get(), self.unit)
        self.assertEqual(
            prop.arealisting_group.catalog_origin,
            ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT,
        )
        self.assertIn('description_ru', prop.arealisting_group.source_owned_fields)
        self.assertIn('features', prop.arealisting_group.source_owned_fields)
        self.assertTrue(set(PRICE_FIELDS) <= set(prop.arealisting_group.source_owned_fields))
        self.assertIn('arealisting', prop.slug)

    def test_draft_preview_keeps_selected_unit_media_when_project_gallery_hits_limit(self):
        self.prepare_draft_source()
        for index in range(MAX_SELECTED_MEDIA_ASSETS):
            ArealistingAsset.objects.create(
                source_key=f'project-preview-{index}',
                project=self.project,
                source_url=f'https://cdn.example.test/project-{index}.jpg',
                asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
                position=index,
            )
        unit_asset = ArealistingAsset.objects.create(
            source_key='unit-floor-plan-preview',
            project=self.project,
            unit=self.unit,
            source_url='https://cdn.example.test/a101-floorplan.jpg',
            asset_type=ArealistingAsset.AssetType.UNIT_GALLERY,
        )

        preview = preview_draft(self.project.pk, [self.unit.pk])

        self.assertEqual(preview['media_assets_total'], MAX_SELECTED_MEDIA_ASSETS + 1)
        self.assertEqual(preview['unit_images'][0]['images'], [{
            'id': unit_asset.pk,
            'url': 'https://cdn.example.test/a101-floorplan.jpg',
            'role': 'FLOOR_PLAN',
        }])
        self.assertEqual(len(preview['project_images']), MAX_SELECTED_MEDIA_ASSETS - 1)

    def test_draft_preview_attributes_shared_project_image_to_selected_unit(self):
        self.prepare_draft_source()
        shared_url = 'https://cdn.example.test/townhouse-01.jpg'
        project_asset = ArealistingAsset.objects.create(
            source_key='shared-project-image',
            project=self.project,
            source_url=shared_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        ArealistingAsset.objects.create(
            source_key='shared-unit-image',
            project=self.project,
            unit=self.unit,
            source_url=shared_url,
            asset_type=ArealistingAsset.AssetType.UNIT_GALLERY,
        )

        preview = preview_draft(self.project.pk, [self.unit.pk])

        self.assertEqual(preview['media_assets_total'], 1)
        self.assertEqual(preview['project_images'], [])
        self.assertEqual(preview['project_images_total'], 0)
        self.assertEqual(preview['unit_images'][0]['images_total'], 1)
        self.assertEqual(preview['unit_images'][0]['images'], [{
            'id': project_asset.pk,
            'url': shared_url,
            'role': 'GALLERY',
        }])

    def test_source_refresh_updates_owned_fields_and_preserves_manual_override(self):
        self.prepare_draft_source()
        self.project.description_ru = 'Первая версия'
        self.project.save(update_fields=('description_ru',))
        prop = create_draft(self.project.pk, [self.unit.pk])

        prop.description_ru = 'Текст редактора'
        prop.save(update_fields=('description_ru',))
        protected = protect_property_manual_changes(prop, {'description_ru'})
        self.assertEqual(protected, {'description', 'description_ru'})

        self.project.description_ru = 'Новая версия AREALISTING'
        self.project.name_en = 'Updated project'
        self.project.save(update_fields=('description_ru', 'name_en'))
        self.unit.internal_area_sqm = Decimal('45.00')
        self.unit.save(update_fields=('internal_area_sqm',))

        run = ArealistingSyncRun.objects.create(mode='FULL', status='RUNNING')
        self.assertTrue(refresh_group_property(prop.arealisting_group.pk, sync_run=run))
        field_change = ArealistingPropertyChange.objects.filter(kind='FIELDS', property=prop).first()
        self.assertIsNotNone(field_change)
        self.assertEqual(field_change.sync_run, run)
        self.assertIn('area_total', [item['field'] for item in field_change.details['changed_fields']])
        prop.refresh_from_db()
        self.assertEqual(prop.description_ru, 'Текст редактора')
        self.assertEqual(prop.complex_name_en, 'Updated project')
        self.assertEqual(prop.area_total, Decimal('45.00'))

    def test_empty_source_value_does_not_erase_draft_field(self):
        self.prepare_draft_source()
        self.project.description_en = 'Initial source text'
        self.project.save(update_fields=('description_en',))
        prop = create_draft(self.project.pk, [self.unit.pk])

        self.project.description_en = ''
        self.project.save(update_fields=('description_en',))
        refresh_group_property(prop.arealisting_group.pk)

        prop.refresh_from_db()
        self.assertEqual(prop.description_en, 'Initial source text')

    def test_manual_price_change_locks_complete_converted_price_set(self):
        self.prepare_draft_source()
        prop = create_draft(self.project.pk, [self.unit.pk])

        protected = protect_property_manual_changes(prop, {'price_sale_thb'})

        self.assertEqual(protected, set(PRICE_FIELDS))
        prop.arealisting_group.refresh_from_db()
        self.assertTrue(set(PRICE_FIELDS) <= set(prop.arealisting_group.locked_fields))

    def test_existing_card_refreshes_only_explicitly_managed_fields(self):
        self.unit.availability_status = ArealistingUnit.AvailabilityStatus.AVAILABLE
        self.unit.price = Decimal('5000000')
        self.unit.currency = 'THB'
        self.unit.save()
        self.project.name_en = 'Initial project'
        self.project.description_en = 'Must not overwrite local text'
        self.project.save()
        row = {**self.row, 'fields': ['complex_name_en']}
        save_links(self.project.pk, [row])
        group = self.prop.arealisting_group

        self.project.name_en = 'Updated project'
        self.project.save(update_fields=('name_en',))
        refresh_group_property(group.pk)

        self.prop.refresh_from_db()
        self.assertEqual(self.prop.complex_name_en, 'Updated project')
        self.assertEqual(self.prop.description_en or '', '')
        self.assertEqual(group.catalog_origin, ArealistingListingGroup.CatalogOrigin.EXISTING)
        group.refresh_from_db()
        self.assertNotIn('description_en', group.source_owned_fields)

    def test_property_admin_edit_automatically_locks_managed_field(self):
        self.unit.availability_status = ArealistingUnit.AvailabilityStatus.AVAILABLE
        self.unit.price = Decimal('5000000')
        self.unit.currency = 'THB'
        self.unit.save()
        save_links(self.project.pk, [{
            **self.row,
            'fields': ['complex_name_en'],
        }])
        self.prop.complex_name_en = 'Manual project name'
        model_admin = PropertyAdmin(Property, admin.site)
        request = RequestFactory().post('/admin/properties/property/')

        with patch.object(model_admin, 'message_user') as message_user:
            model_admin.save_model(
                request,
                self.prop,
                SimpleNamespace(changed_data=['complex_name_en']),
                change=True,
            )

        group = ArealistingListingGroup.objects.get(property=self.prop)
        self.assertIn('complex_name_en', group.locked_fields)
        message_user.assert_called_once()

    def test_listing_group_form_explicitly_removes_field_protection(self):
        self.unit.availability_status = ArealistingUnit.AvailabilityStatus.AVAILABLE
        self.unit.price = Decimal('5000000')
        self.unit.currency = 'THB'
        self.unit.save()
        save_links(self.project.pk, [{
            **self.row,
            'fields': ['complex_name_en'],
        }])
        group = ArealistingListingGroup.objects.get(property=self.prop)
        group.locked_fields = ['complex_name_en']
        group.save(update_fields=('locked_fields', 'updated_at'))
        data = {
            'project': group.project_id,
            'property': group.property_id,
            'grouping_mode': group.grouping_mode,
            'name': group.name,
            'currency': group.currency,
            'min_price': group.min_price or '',
            'max_price': group.max_price or '',
            'min_area_sqm': group.min_area_sqm or '',
            'max_area_sqm': group.max_area_sqm or '',
            'available_units_count': group.available_units_count,
            'is_ready_for_publication': group.is_ready_for_publication,
            'is_active': group.is_active,
            'catalog_origin': group.catalog_origin,
            'validation_errors': json.dumps(group.validation_errors),
        }

        form = ArealistingListingGroupAdminForm(data=data, instance=group)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        group.refresh_from_db()
        self.assertEqual(group.locked_fields, [])

    def test_listing_group_admin_shows_field_protection_controls(self):
        self.unit.availability_status = ArealistingUnit.AvailabilityStatus.AVAILABLE
        self.unit.price = Decimal('5000000')
        self.unit.currency = 'THB'
        self.unit.save()
        save_links(self.project.pk, [self.row])
        group = ArealistingListingGroup.objects.get(property=self.prop)
        user = User.objects.create_superuser(
            'field-protection-admin', 'field-protection@example.test', 'password'
        )
        self.client.force_login(user)

        response = self.client.get(reverse(
            'admin:arealisting_arealistinglistinggroup_change',
            args=[group.pk],
        ))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Защищено от обновления AREALISTING')
        self.assertContains(response, 'Чтобы снова разрешить обновление')

    def test_house_draft_uses_townhouse_property_type(self):
        self.prepare_draft_source()
        townhouse = PropertyType.objects.create(name='townhouse')
        self.project.project_type = 'HOUSE'
        self.project.save(update_fields=('project_type',))
        self.unit.property_type = 'HOUSE'
        self.unit.save(update_fields=('property_type',))

        preview = preview_draft(self.project.pk, [self.unit.pk])
        prop = create_draft(self.project.pk, [self.unit.pk])

        self.assertEqual(preview['property_type'], str(townhouse))
        self.assertEqual(prop.property_type, townhouse)
        self.assertFalse(prop.is_active)

    def test_draft_rejects_sold_or_unmapped_units(self):
        self.project.project_type = 'CONDO'
        self.project.districts = [{'external_id': 'missing-location'}]
        self.project.save()
        self.unit.property_type = 'CONDO'
        self.unit.availability_status = ArealistingUnit.AvailabilityStatus.SOLD
        self.unit.save()

        with self.assertRaisesMessage(ValidationError, 'хотя бы одно доступное'):
            create_draft(self.project.pk, [self.unit.pk])

        self.unit.availability_status = ArealistingUnit.AvailabilityStatus.AVAILABLE
        self.unit.save()
        with self.assertRaisesMessage(ValidationError, 'не настроен подтверждённый район'):
            create_draft(self.project.pk, [self.unit.pk])

    def test_draft_rejects_mixed_layout_selection(self):
        self.prepare_draft_source()
        second = ArealistingUnit.objects.create(
            external_id='different-layout',
            project=self.project,
            property_type='CONDO',
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
            bedrooms=3,
            internal_area_sqm=Decimal('90'),
            price=Decimal('9000000'),
            currency='THB',
        )

        with self.assertRaisesMessage(ValidationError, 'одной планировки'):
            preview_draft(self.project.pk, [self.unit.pk, second.pk])

    def test_draft_requires_explicit_choice_for_multiple_mapped_locations(self):
        self.prepare_draft_source()
        first_location = Location.objects.create(
            name='First location',
            slug='first-location',
            district=self.prop.district,
        )
        second_location = Location.objects.create(
            name='Second location',
            slug='second-location',
            district=self.prop.district,
        )
        first_mapping = ArealistingLocationMapping.objects.get(
            external_id='draft-location'
        )
        first_mapping.source_name = 'Source first'
        first_mapping.mapping_mode = ArealistingLocationMapping.MappingMode.LOCATION
        first_mapping.location = first_location
        first_mapping.save()
        second_mapping = ArealistingLocationMapping.objects.create(
            external_id='draft-location-2',
            source_name='Source second',
            mapping_mode=ArealistingLocationMapping.MappingMode.LOCATION,
            location=second_location,
            is_confirmed=True,
        )
        self.project.districts.append({'external_id': 'draft-location-2'})
        self.project.save(update_fields=('districts',))

        preview = preview_draft(self.project.pk, [self.unit.pk])

        self.assertTrue(preview['location_choice_required'])
        self.assertEqual(preview['district'], '')
        self.assertEqual(preview['location'], '')
        self.assertEqual(
            {option['id'] for option in preview['location_options']},
            {str(first_mapping.pk), str(second_mapping.pk)},
        )
        with self.assertRaisesMessage(ValidationError, 'Выберите локацию'):
            create_draft(self.project.pk, [self.unit.pk])

        prop = create_draft(
            self.project.pk,
            [self.unit.pk],
            location_choice=str(second_mapping.pk),
        )

        self.assertEqual(prop.district, self.prop.district)
        self.assertEqual(prop.location, second_location)
        self.assertNotIn('district', prop.arealisting_group.source_owned_fields)
        self.assertNotIn('location', prop.arealisting_group.source_owned_fields)

    def test_skip_and_restore_unlinked_unit(self):
        user = User.objects.create_user('skip-user')

        self.assertEqual(skip_units(
            self.project.pk,
            [self.unit.pk],
            user=user,
            reason='Не создаём карточку',
        ), 1)
        decision = ArealistingSkippedUnit.objects.get(unit=self.unit)
        self.assertEqual(decision.skipped_by, user)
        self.assertEqual(decision.reason, 'Не создаём карточку')
        self.assertEqual(restore_units(self.project.pk, [self.unit.pk]), 1)
        self.assertFalse(ArealistingSkippedUnit.objects.exists())
        self.assertTrue(ArealistingUnit.objects.filter(pk=self.unit.pk).exists())

    def test_screen_and_permissions(self):
        user = User.objects.create_superuser('matcher', 'matcher@example.test', 'password')
        self.client.force_login(user)
        url = reverse('admin:arealisting_matching')
        response = self.client.get(url, {'project': self.project.pk})
        self.assertContains(response, 'matching-data')
        self.assertContains(response, 'Ещё не связаны')
        self.assertContains(response, 'unmatched-status-filter')
        self.assertContains(response, 'data-unit-status="AVAILABLE"')
        self.assertContains(response, 'data-unit-status="SOLD"')
        self.assertTrue(response.context['matching_data']['properties'][0]['is_active'])
        self.assertFalse(response.context['matching_data']['units'][0]['skipped'])
        user.is_superuser = False
        user.save()
        self.assertEqual(self.client.get(url).status_code, 403)

    @override_settings(DEBUG=True)
    def test_vue_matching_is_opt_in_and_uses_same_server_data(self):
        user = User.objects.create_superuser('vue-matcher', 'vue@example.test', 'password')
        self.client.force_login(user)
        url = reverse('admin:arealisting_matching')
        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True):
            legacy = self.client.get(url, {'project': self.project.pk})
            vue = self.client.get(url, {'project': self.project.pk, 'vue': '1'})
        self.assertTemplateUsed(legacy, 'admin/arealisting/matching.html')
        self.assertContains(legacy, 'Открыть новую версию экрана на Vue')
        self.assertTemplateUsed(vue, 'admin/arealisting/matching_vue.html')
        self.assertContains(vue, 'arealisting-vue-root')
        self.assertEqual(vue.context['matching_data']['project'], self.project.pk)

    @override_settings(DEBUG=True)
    def test_vue_matching_without_project_opens_project_picker(self):
        user = User.objects.create_superuser('matching-picker', 'picker@example.test', 'password')
        self.client.force_login(user)
        url = reverse('admin:arealisting_matching')
        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True):
            response = self.client.get(url, {'vue': '1'})
        self.assertTemplateUsed(response, 'admin/arealisting/matching_select_vue.html')
        self.assertContains(response, 'arealisting-matching-select-root')
        rows = response.context['matching_select_data']['rows']
        self.assertEqual(next(row['url'] for row in rows if row['id'] == self.project.pk),
                         f'{url}?project={self.project.pk}&vue=1')

    @override_settings(DEBUG=True)
    def test_vue_matching_falls_back_without_built_assets(self):
        user = User.objects.create_superuser('vue-fallback', 'fallback@example.test', 'password')
        self.client.force_login(user)
        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=False):
            response = self.client.get(reverse('admin:arealisting_matching'), {
                'project': self.project.pk, 'vue': '1',
            })
        self.assertTemplateUsed(response, 'admin/arealisting/matching.html')

    def test_admin_preview_and_create_draft_actions(self):
        self.prepare_draft_source()
        user = User.objects.create_superuser('draft-admin', 'draft@example.test', 'password')
        self.client.force_login(user)
        url = reverse('admin:arealisting_matching') + f'?project={self.project.pk}'

        preview_response = self.client.post(
            url,
            json.dumps({
                'action': 'preview_draft',
                'project': self.project.pk,
                'units': [self.unit.pk],
            }),
            content_type='application/json',
        )
        self.assertEqual(preview_response.status_code, 200)
        self.assertFalse(preview_response.json()['preview']['is_active'])

        create_response = self.client.post(
            url,
            json.dumps({
                'action': 'create_draft',
                'project': self.project.pk,
                'units': [self.unit.pk],
            }),
            content_type='application/json',
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()['media_job_url'], '')
        draft = Property.objects.get(pk=create_response.json()['property'])
        self.assertFalse(draft.is_active)
        self.assertEqual(draft.arealisting_group.units.get(), self.unit)
        self.assertFalse(draft.images.exists())

    def test_admin_draft_with_photos_returns_background_job(self):
        self.prepare_draft_source()
        asset = ArealistingAsset.objects.create(
            source_key='draft-background-photo', project=self.project,
            source_url='https://cdn.example.test/draft-photo.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        user = User.objects.create_superuser('draft-media-admin', 'draft-media@example.test', 'password')
        self.client.force_login(user)
        url = reverse('admin:arealisting_matching') + f'?project={self.project.pk}'

        with patch('apps.arealisting.services.media_jobs.start_media_worker') as worker:
            response = self.client.post(
                url,
                json.dumps({'action': 'create_draft', 'project': self.project.pk,
                            'units': [self.unit.pk], 'media_assets': [asset.pk]}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        draft = Property.objects.get(pk=response.json()['property'])
        job = ArealistingMediaJob.objects.get(group=draft.arealisting_group)
        self.assertEqual(job.selected_asset_ids, [asset.pk])
        self.assertEqual(response.json()['media_job_url'], reverse(
            'admin:arealisting_arealistinglistinggroup_media_job',
            args=[draft.arealisting_group.pk, job.pk],
        ))
        self.assertFalse(draft.images.exists())
        worker.assert_called_once()

    def test_admin_skip_and_restore_actions(self):
        user = User.objects.create_superuser('skip-admin', 'skip@example.test', 'password')
        self.client.force_login(user)
        url = reverse('admin:arealisting_matching') + f'?project={self.project.pk}'

        skip_response = self.client.post(
            url,
            json.dumps({
                'action': 'skip_units',
                'project': self.project.pk,
                'units': [self.unit.pk],
            }),
            content_type='application/json',
        )
        self.assertEqual(skip_response.status_code, 200)
        self.assertTrue(ArealistingSkippedUnit.objects.filter(unit=self.unit).exists())

        restore_response = self.client.post(
            url,
            json.dumps({
                'action': 'restore_units',
                'project': self.project.pk,
                'units': [self.unit.pk],
            }),
            content_type='application/json',
        )
        self.assertEqual(restore_response.status_code, 200)
        self.assertFalse(ArealistingSkippedUnit.objects.exists())

    def test_admin_activity_change_is_logged(self):
        from django.contrib.admin.models import LogEntry

        user = User.objects.create_superuser(
            'activity-admin',
            'activity@example.test',
            'password',
        )
        self.client.force_login(user)
        url = reverse('admin:arealisting_matching') + f'?project={self.project.pk}'

        response = self.client.post(
            url,
            json.dumps({
                'action': 'save_links',
                'project': self.project.pk,
                'rows': [{
                    **self.row,
                    'expected': {},
                    'is_active': False,
                    'expected_is_active': True,
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        report = response.json()['rows'][0]
        self.assertEqual(report['property_id'], self.prop.pk)
        self.assertEqual(
            report['url'], reverse('admin:properties_property_change', args=[self.prop.pk]),
        )
        self.assertEqual(
            report['media_preview_url'],
            reverse('admin:arealisting_arealistinglistinggroup_preview_media',
                    args=[self.prop.arealisting_group.pk]),
        )
        self.assertEqual(report['activity_change'], {'before': True, 'after': False})
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.is_active)
        self.assertTrue(LogEntry.objects.filter(
            object_id=str(self.prop.pk),
            change_message__contains='Активность изменена через AREALISTING',
        ).exists())
