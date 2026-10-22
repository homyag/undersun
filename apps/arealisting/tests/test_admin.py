from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal

from apps.arealisting.models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingMediaJob,
    ArealistingLocationMapping,
    ArealistingPaymentPlan,
    ArealistingPropertyAsset,
    ArealistingProject,
    ArealistingPriceReview,
    ArealistingPropertyChange,
    ArealistingSkippedUnit,
    ArealistingSyncRun,
    ArealistingSyncState,
    ArealistingSyncJob,
    ArealistingSyncEvent,
    ArealistingUnit,
)
from apps.locations.models import District, Location
from apps.properties.models import Property, PropertyImage, PropertyType
from django.utils import timezone


@override_settings(AREALISTING_VUE_ENABLED=False)
class ArealistingAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='arealisting-admin',
            email='admin@example.test',
            password='test-password',
        )
        self.client.force_login(self.user)

    def test_project_queue_has_sync_button_and_source_data(self):
        ArealistingProject.objects.create(
            external_id='project-1',
            name_en='Lavisco Living',
            developer_name='Lavisco',
            districts=[{'external_id': 'nai-yang', 'name': 'Nai Yang'}],
        )

        response = self.client.get(
            reverse('admin:arealisting_arealistingproject_changelist')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Обновить список проектов')
        self.assertContains(response, 'Lavisco Living')
        self.assertContains(response, 'Nai Yang')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_project_detail_keeps_navigation_with_related_records(self, _available):
        project = ArealistingProject.objects.create(
            external_id='detail-project', name_en='Detail project', name_ru='Проект',
            developer_name='Developer', gallery=['https://cdn.example.test/project.jpg'],
            districts=[{'name': 'Bang Tao'}],
        )
        other = ArealistingProject.objects.create(external_id='other-project', name_en='Other project')
        ArealistingUnit.objects.create(
            external_id='detail-unit', project=project,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
        )
        ArealistingListingGroup.objects.create(project=project, name='Project group')
        ArealistingPaymentPlan.objects.create(external_id='detail-plan', project=project, name='Installments')
        ArealistingAsset.objects.create(
            source_key='detail-asset', project=project, source_url='https://cdn.example.test/asset.jpg',
        )
        ArealistingAsset.objects.create(
            source_key='other-asset', project=other, source_url='https://cdn.example.test/other.jpg',
        )
        overview = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'),
                                   {'q': 'Detail'})
        detail_url = reverse('admin:arealisting_arealistingproject_change', args=[project.pk])
        self.assertContains(overview, detail_url)
        response = self.client.get(detail_url, {'return_q': 'Detail', 'return_page': '2'})
        self.assertTemplateUsed(response, 'admin/arealisting/project_detail_vue.html')
        data = response.context['project_detail_data']
        self.assertEqual(data['available_units'], 1)
        self.assertEqual(data['group_count'], 1)
        self.assertEqual(data['payment_count'], 1)
        self.assertEqual(data['asset_count'], 1)
        self.assertIn('q=Detail', data['back_url'])
        self.assertIn('page=2', data['back_url'])
        self.assertIn(f'project={project.pk}', data['groups_url'])
        self.assertIn(f'project={project.pk}', data['assets_url'])
        self.assertIn(f'project={project.pk}', data['payments_url'])
        self.assertIn(f'project={project.pk}', data['matching_url'])
        groups = self.client.get(data['groups_url'])
        self.assertTemplateUsed(groups, 'admin/arealisting/group_list_vue.html')
        self.assertEqual(groups.context['group_list_data']['result_count'], 1)
        assets = self.client.get(data['assets_url'])
        self.assertTemplateUsed(assets, 'admin/arealisting/asset_list_vue.html')
        self.assertEqual(assets.context['asset_list_data']['result_count'], 1)
        self.assertEqual(self.client.post(detail_url, {'name_en': 'Changed'}).status_code, 403)
        project.refresh_from_db()
        self.assertEqual(project.name_en, 'Detail project')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_project_detail_hides_actions_without_permission(self, _available):
        project = ArealistingProject.objects.create(external_id='viewer-project', name_en='Viewer project')
        viewer = User.objects.create_user('project-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingproject'))
        self.client.force_login(viewer)
        detail_url = reverse('admin:arealisting_arealistingproject_change', args=[project.pk])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        data = response.context['project_detail_data']
        self.assertEqual(data['load_url'], '')
        self.assertEqual(data['matching_url'], '')
        self.assertEqual(data['units_url'], '')
        self.assertEqual(data['groups_url'], '')
        self.assertEqual(self.client.post(detail_url, {'name_en': 'Changed'}).status_code, 403)

    def test_sync_projects_button_queues_background_job_without_duplicate(self):
        url = reverse('admin:arealisting_arealistingproject_sync_projects')
        with patch('apps.arealisting.admin.start_sync_worker') as worker:
            response = self.client.post(url)
            repeated = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(repeated.status_code, 302)
        job = ArealistingSyncJob.objects.get()
        self.assertEqual(job.status, ArealistingSyncJob.Status.PENDING)
        self.assertEqual(job.resources, ['projects'])
        self.assertTrue(job.full)
        self.assertEqual(job.requested_by, self.user)
        worker.assert_called_once_with(job.pk)

        page = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
        self.assertContains(page, 'Обновление идёт в фоне')
        self.assertTrue(page.context['sync_running'])

    def test_sync_projects_reports_worker_start_failure(self):
        url = reverse('admin:arealisting_arealistingproject_sync_projects')
        with patch('apps.arealisting.admin.start_sync_worker', side_effect=OSError('spawn failed')):
            response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        job = ArealistingSyncJob.objects.get()
        self.assertEqual(job.status, ArealistingSyncJob.Status.FAILED)
        self.assertContains(response, 'Не удалось запустить фоновый обработчик')

    def test_integration_has_one_menu_entry_and_internal_pages_remain_accessible(self):
        response = self.client.get(reverse('admin:index'))
        app = next(item for item in response.context['app_list'] if item['app_label'] == 'arealisting')
        self.assertEqual([model['object_name'] for model in app['models']], ['ArealistingProject'])
        response = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
        self.assertContains(response, 'Настройки и данные интеграции')
        url = reverse('admin:arealisting_arealistingunit_changelist')
        self.assertContains(response, url)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_workspace_guides_user_to_loading_selected_complex(self):
        project = ArealistingProject.objects.create(external_id='guided', name_en='Example')
        response = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
        self.assertContains(response, '1. Выберите комплекс')
        self.assertContains(response, 'Загрузить предложения')
        self.assertNotContains(response, 'action-checkbox')
        url = reverse('admin:arealisting_load_inventory', args=[project.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch('apps.arealisting.admin.ArealistingProjectAdmin._run_sync', return_value=True) as sync:
            response = self.client.post(url, {
                'return_q': 'Example',
                'return_page': '3',
            })
        self.assertEqual(
            response.url,
            reverse('admin:arealisting_arealistingproject_changelist')
            + f'?q=Example&page=3#project-{project.pk}',
        )
        self.assertEqual(sync.call_args.kwargs['project_ids'], ['guided'])

    def test_workspace_search_and_no_results_help(self):
        ArealistingProject.objects.create(external_id='guided', name_en='Example')
        response = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'), {'q': 'missing'})
        self.assertContains(response, 'Комплекс не найден')

    def test_workspace_displays_operational_dashboard(self):
        project = ArealistingProject.objects.create(
            external_id='dashboard-project',
            name_en='Dashboard project',
        )
        ArealistingUnit.objects.create(
            external_id='available-unit',
            project=project,
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
        )
        mapping = ArealistingLocationMapping.objects.create(
            external_id='unmapped-location',
            source_name='Unknown place',
        )
        asset = ArealistingAsset.objects.create(
            source_key='broken-asset',
            project=project,
            source_url='https://cdn.example.test/broken.jpg',
            last_error='Download failed',
        )
        run = ArealistingSyncRun.objects.create(
            mode=ArealistingSyncRun.Mode.FULL,
            status=ArealistingSyncRun.Status.SUCCESS,
            resources=['projects', 'units'],
            summary={
                'projects': {'created': 2},
                'units': {
                    'available_created': 14,
                    'price_changed': 5,
                    'became_sold': 3,
                },
                'price_updates': [{'status': 'updated'}, {'status': 'unchanged'}],
            },
            finished_at=timezone.now(),
        )

        response = self.client.get(
            reverse('admin:arealisting_arealistingproject_changelist')
        )

        self.assertContains(response, 'Состояние интеграции')
        self.assertEqual(response.context['latest_successful_run'], run)
        self.assertEqual(response.context['recent_changes']['new_projects'], 2)
        self.assertEqual(response.context['recent_changes']['new_available_units'], 14)
        self.assertEqual(response.context['recent_changes']['price_changed'], 5)
        self.assertEqual(response.context['recent_changes']['became_sold'], 3)
        self.assertEqual(response.context['recent_changes']['property_prices_updated'], 1)
        self.assertEqual(response.context['source_totals']['available_units'], 1)
        self.assertEqual(response.context['attention']['mapping_required'], 1)
        self.assertEqual(response.context['attention']['asset_errors'], 1)
        self.assertGreaterEqual(response.context['attention_actionable_count'], 2)
        self.assertContains(response, 'Рекомендуется проверить')
        self.assertContains(response, 'id="needs-attention"')
        self.assertContains(response, 'id="project-search"')
        self.assertContains(response, reverse('admin:arealisting_review_queue'))
        self.assertContains(response, 'Все черновики')
        self.assertNotContains(response, 'Полные списки доступны в блоке')
        self.assertContains(response, reverse('admin:arealisting_arealistinglocationmapping_change', args=[mapping.pk]))
        self.assertContains(response, reverse('admin:arealisting_arealistingasset_change', args=[asset.pk]))
        self.assertContains(response, 'inventory-counters')
        self.assertContains(response, 'Доступно')
        self.assertContains(response, 'Продано')

    def test_work_queue_links_to_unlinked_property_and_draft(self):
        project = ArealistingProject.objects.create(external_id='queue', name_en='Queue project')
        property_type = PropertyType.objects.create(name='condo')
        district = District.objects.create(name='Queue district', slug='queue-district')
        unlinked = Property.objects.create(
            title='Needs matching', slug='needs-matching',
            property_type=property_type, district=district, is_active=True,
        )
        draft = Property.objects.create(
            title='Needs review', slug='needs-review',
            property_type=property_type, district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=draft,
            catalog_origin=ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT,
        )

        response = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))

        self.assertContains(response, 'Needs matching')
        self.assertContains(response, 'Needs review')
        self.assertEqual(response.context['attention_actionable_count'], 2)
        self.assertContains(response, f"{reverse('admin:arealisting_unlinked')}?property={unlinked.pk}")
        self.assertContains(response, reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk]))

        viewer = User.objects.create_user(username='arealisting-viewer', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='arealisting', codename='view_arealistingproject',
        ))
        self.client.force_login(viewer)
        viewer_response = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
        self.assertEqual(viewer_response.status_code, 200)
        self.assertEqual(viewer_response.context['attention_actionable_count'], 0)

    @override_settings(AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_sync_event_queue_shows_latest_run_and_full_list(self, _available):
        project = ArealistingProject.objects.create(external_id='events', name_en='Events project')
        old_run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        ArealistingSyncEvent.objects.create(
            run=old_run, project=project, kind=ArealistingSyncEvent.Kind.NEW_UNIT,
            details={'unit_external_id': 'old-unit'},
        )
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        event = ArealistingSyncEvent.objects.create(
            run=run, project=project, kind=ArealistingSyncEvent.Kind.SOLD,
            details={'unit_external_id': 'sold-unit'},
        )

        response = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
        self.assertEqual(response.context['latest_successful_run'], run)
        self.assertEqual([item['detail'] for item in response.context['sync_events']], ['Предложение sold-unit'])
        self.assertContains(response, 'Что изменилось после синхронизации')
        self.assertContains(response, 'sold-unit')
        self.assertContains(response, f"{reverse('admin:arealisting_arealistingsyncevent_changelist')}?run={run.pk}")
        full = self.client.get(reverse('admin:arealisting_arealistingsyncevent_changelist'), {'run': run.pk})
        self.assertTemplateUsed(full, 'admin/arealisting/sync_event_list_vue.html')
        self.assertEqual(full.context['sync_event_list_data']['result_count'], 1)
        self.assertIn(reverse('admin:arealisting_arealistingsyncevent_change', args=[event.pk]),
                      full.context['sync_event_list_data']['events'][0]['url'])

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_sync_event_journal_filters_and_detail(self, _available):
        project = ArealistingProject.objects.create(external_id='event-project', name_en='Event project')
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        unit = ArealistingUnit.objects.create(external_id='event-unit', project=project, unit_number='C42')
        event = ArealistingSyncEvent.objects.create(
            run=run, project=project, unit=unit, kind=ArealistingSyncEvent.Kind.UNIT_FIELDS,
            details={'changed_fields': [{'field': 'bedrooms', 'before': 1, 'after': 2}]},
        )
        ArealistingSyncEvent.objects.create(
            run=run, project=project, kind=ArealistingSyncEvent.Kind.SOLD,
            reviewed_at=timezone.now(), reviewed_by=self.user,
        )
        list_url = reverse('admin:arealisting_arealistingsyncevent_changelist')
        response = self.client.get(list_url, {
            'vue': '1', 'state': 'open', 'kind': event.kind,
            'run': str(run.pk), 'q': 'C42',
        })
        self.assertTemplateUsed(response, 'admin/arealisting/sync_event_list_vue.html')
        data = response.context['sync_event_list_data']
        self.assertEqual(data['counts'], {'all': 1, 'open': 1, 'checked': 0})
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['events'][0]['id'], event.pk)
        self.assertIn('vue=1', data['events'][0]['url'])

        detail = self.client.get(data['events'][0]['url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/sync_event_detail_vue.html')
        detail_data = detail.context['sync_event_detail_data']
        self.assertIn('bedrooms', detail_data['details'])
        self.assertIn('q=C42', detail_data['back_url'])
        self.assertIn(f'run={run.pk}', detail_data['back_url'])
        self.assertIn('vue=1', detail_data['run_url'])
        self.assertIn('vue=1', detail_data['unit_url'])
        self.assertEqual(self.client.post(data['events'][0]['url'], {'kind': 'SOLD'}).status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.kind, ArealistingSyncEvent.Kind.UNIT_FIELDS)

        checked = self.client.get(list_url, {'vue': '1', 'state': 'checked'})
        self.assertEqual(checked.context['sync_event_list_data']['result_count'], 1)
        legacy = self.client.get(list_url, {'run': str(run.pk)})
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingsyncevent/change_list.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_sync_event_journal_respects_view_permission(self, _available):
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        event = ArealistingSyncEvent.objects.create(run=run, kind=ArealistingSyncEvent.Kind.NEW_UNIT)
        viewer = User.objects.create_user('event-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingsyncevent'))
        self.client.force_login(viewer)
        list_url = reverse('admin:arealisting_arealistingsyncevent_changelist')
        detail_url = reverse('admin:arealisting_arealistingsyncevent_change', args=[event.pk])
        self.assertEqual(self.client.get(list_url, {'vue': '1'}).status_code, 200)
        response = self.client.get(detail_url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sync_event_detail_data']['run_url'], '')
        self.assertEqual(self.client.post(detail_url + '?vue=1', {'kind': 'SOLD'}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_sync_state_shows_lock_resources_and_stale_warning(self, _available):
        lock = ArealistingSyncState.objects.create(
            key='global-lock', status=ArealistingSyncState.Status.RUNNING,
            current_started_at=timezone.now() - timezone.timedelta(hours=3),
        )
        cursor = timezone.now() - timezone.timedelta(days=1)
        resource = ArealistingSyncState.objects.create(
            key='resource:units', status=ArealistingSyncState.Status.FAILED,
            last_successful_sync_at=cursor, last_error='API временно недоступен',
        )
        ArealistingSyncRun.objects.create(
            mode='FULL', status='SUCCESS', finished_at=timezone.now() - timezone.timedelta(days=1),
        )
        run = ArealistingSyncRun.objects.create(mode='FULL', status='FAILED', error='API error')
        ArealistingSyncJob.objects.create(status=ArealistingSyncJob.Status.PENDING,
                                          resources=['projects'])
        list_url = reverse('admin:arealisting_arealistingsyncstate_changelist')
        response = self.client.get(list_url, {'vue': '1'})
        self.assertTemplateUsed(response, 'admin/arealisting/sync_state_list_vue.html')
        data = response.context['sync_state_list_data']
        self.assertEqual(data['lock']['id'], lock.pk)
        self.assertTrue(data['lock']['stale'])
        self.assertEqual(data['lock']['status_label'], 'Возможное зависание')
        self.assertEqual(data['resources'][0]['name'], 'Предложения')
        self.assertIn('API временно недоступен', data['resources'][0]['last_error'])
        self.assertTrue(data['resources'][0]['last_successful_sync_at'])
        self.assertEqual(data['latest_run']['id'], run.pk)
        self.assertIn('vue=1', data['latest_run']['url'])
        self.assertEqual(data['latest_job']['status'], ArealistingSyncJob.Status.PENDING)
        self.assertTrue(data['last_successful_at'])

        detail = self.client.get(data['resources'][0]['url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/sync_state_detail_vue.html')
        self.assertEqual(detail.context['sync_state_detail_data']['row']['id'], resource.pk)
        self.assertIn('vue=1', detail.context['sync_state_detail_data']['back_url'])
        self.assertEqual(self.client.post(data['resources'][0]['url'], {'status': 'SUCCESS'}).status_code, 403)
        resource.refresh_from_db()
        self.assertEqual(resource.status, ArealistingSyncState.Status.FAILED)
        self.assertTemplateUsed(self.client.get(list_url),
                                'admin/arealisting/arealistingsyncstate/change_list.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_sync_state_empty_and_view_only(self, _available):
        list_url = reverse('admin:arealisting_arealistingsyncstate_changelist')
        empty = self.client.get(list_url, {'vue': '1'})
        self.assertIsNone(empty.context['sync_state_list_data']['lock'])
        self.assertEqual(empty.context['sync_state_list_data']['resources'], [])
        self.assertIsNone(empty.context['sync_state_list_data']['latest_job'])
        resource = ArealistingSyncState.objects.create(key='resource:projects')
        viewer = User.objects.create_user('state-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingsyncstate'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(list_url, {'vue': '1'}).status_code, 200)
        detail_url = reverse('admin:arealisting_arealistingsyncstate_change', args=[resource.pk])
        detail = self.client.get(detail_url, {'vue': '1'})
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context['sync_state_detail_data']['history_url'], '')
        self.assertEqual(self.client.post(detail_url + '?vue=1', {'status': 'FAILED'}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_property_asset_list_and_detail(self, _available):
        project = ArealistingProject.objects.create(external_id='photo-project', name_en='Photo project')
        property_type = PropertyType.objects.create(name='Photo condo')
        district = District.objects.create(name='Photo district', slug='photo-district')
        property_obj = Property.objects.create(
            title='Photo card', slug='photo-card', property_type=property_type, district=district,
        )
        group = ArealistingListingGroup.objects.create(project=project, property=property_obj, name='Gallery')
        asset = ArealistingAsset.objects.create(
            source_key='photo-source', project=project,
            source_url='https://cdn.example.test/photo.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        image = PropertyImage.objects.bulk_create([
            PropertyImage(property=property_obj, image='properties/photo.jpg', is_main=True),
        ])[0]
        link = ArealistingPropertyAsset.objects.create(
            listing_group=group, asset=asset, property_image=image,
            role=ArealistingPropertyAsset.Role.GALLERY,
        )
        missing_asset = ArealistingAsset.objects.create(
            source_key='photo-missing', project=project,
            source_url='https://cdn.example.test/missing.jpg',
            asset_type=ArealistingAsset.AssetType.FLOOR_PLAN,
        )
        ArealistingPropertyAsset.objects.create(
            listing_group=group, asset=missing_asset,
            role=ArealistingPropertyAsset.Role.FLOOR_PLAN,
        )
        list_url = reverse('admin:arealisting_arealistingpropertyasset_changelist')
        response = self.client.get(list_url, {
            'vue': '1', 'role': 'GALLERY', 'image_state': 'linked',
            'project': str(project.pk), 'q': 'Photo card',
        })
        self.assertTemplateUsed(response, 'admin/arealisting/property_asset_list_vue.html')
        data = response.context['property_asset_list_data']
        self.assertEqual(data['counts'], {'all': 1, 'linked': 1, 'missing': 0})
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['links'][0]['id'], link.pk)
        self.assertTrue(data['links'][0]['is_main'])
        self.assertIn('vue=1', data['links'][0]['url'])

        detail = self.client.get(data['links'][0]['url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/property_asset_detail_vue.html')
        detail_data = detail.context['property_asset_detail_data']
        self.assertEqual(detail_data['source_key'], 'photo-source')
        self.assertTrue(detail_data['card_image_url'].endswith('properties/photo.jpg'))
        self.assertIn(f'project={project.pk}', detail_data['back_url'])
        self.assertIn('q=Photo+card', detail_data['back_url'])
        self.assertIn('vue=1', detail_data['asset_url'])
        self.assertIn('vue=1', detail_data['group_url'])
        self.assertEqual(self.client.post(data['links'][0]['url'], {'role': 'FLOOR_PLAN'}).status_code, 403)
        link.refresh_from_db()
        self.assertEqual(link.role, ArealistingPropertyAsset.Role.GALLERY)

        missing = self.client.get(list_url, {'vue': '1', 'image_state': 'missing'})
        self.assertEqual(missing.context['property_asset_list_data']['result_count'], 1)
        self.assertTemplateUsed(self.client.get(list_url),
                                'admin/arealisting/arealistingpropertyasset/change_list.html')
        with override_settings(AREALISTING_VUE_ENABLED=True):
            self.assertTemplateUsed(self.client.get(list_url),
                                    'admin/arealisting/property_asset_list_vue.html')
            overview = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
            self.assertContains(overview, f'href="{list_url}"')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_property_asset_respects_view_permission(self, _available):
        project = ArealistingProject.objects.create(external_id='photo-viewer', name_en='Viewer project')
        group = ArealistingListingGroup.objects.create(project=project, name='Viewer group')
        asset = ArealistingAsset.objects.create(
            source_key='photo-viewer-asset', project=project,
            source_url='https://cdn.example.test/viewer.jpg',
        )
        link = ArealistingPropertyAsset.objects.create(
            listing_group=group, asset=asset, role=ArealistingPropertyAsset.Role.GALLERY,
        )
        viewer = User.objects.create_user('photo-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingpropertyasset'))
        self.client.force_login(viewer)
        list_url = reverse('admin:arealisting_arealistingpropertyasset_changelist')
        detail_url = reverse('admin:arealisting_arealistingpropertyasset_change', args=[link.pk])
        self.assertEqual(self.client.get(list_url, {'vue': '1'}).status_code, 200)
        detail = self.client.get(detail_url, {'vue': '1'})
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context['property_asset_detail_data']['asset_url'], '')
        self.assertEqual(detail.context['property_asset_detail_data']['group_url'], '')
        self.assertEqual(self.client.post(detail_url + '?vue=1', {'role': 'FLOOR_PLAN'}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_sync_state_sidebar_link_opens_vue_without_query_param(self, _available):
        list_url = reverse('admin:arealisting_arealistingsyncstate_changelist')
        overview = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
        self.assertContains(overview, f'href="{list_url}"')
        response = self.client.get(list_url)
        self.assertTemplateUsed(response, 'admin/arealisting/sync_state_list_vue.html')

    def test_review_queue_shows_changes_and_remembers_checked_events(self):
        project = ArealistingProject.objects.create(external_id='review-queue-project', name_en='Review project')
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        event = ArealistingSyncEvent.objects.create(
            run=run, project=project, kind=ArealistingSyncEvent.Kind.UNIT_FIELDS,
            details={'changed_fields': [{'field': 'bedrooms', 'before': '1', 'after': '2'}]},
        )
        url = reverse('admin:arealisting_review_queue')
        response = self.client.get(url)
        self.assertContains(response, 'Очередь изменений AREALISTING')
        self.assertContains(response, 'Было в AREALISTING')
        self.assertContains(response, 'Спальни')
        self.assertContains(response, reverse('admin:arealisting_review_event', args=[event.pk]))
        self.assertEqual(self.client.get(reverse('admin:arealisting_review_event', args=[event.pk])).status_code, 405)

        self.assertEqual(self.client.post(reverse('admin:arealisting_review_event', args=[event.pk])).status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.reviewed_by, self.user)
        self.assertIsNotNone(event.reviewed_at)
        self.assertNotContains(self.client.get(url), f'event-{event.pk}')
        self.assertContains(self.client.get(url, {'state': 'checked'}), f'event-{event.pk}')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_review_queue_keeps_filters_after_checking(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-review-project', name_en='Vue review')
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        event = ArealistingSyncEvent.objects.create(
            run=run, project=project, kind=ArealistingSyncEvent.Kind.UNIT_FIELDS,
            details={'changed_fields': [{'field': 'bedrooms', 'before': '1', 'after': '2'}]},
        )
        url = reverse('admin:arealisting_review_queue')
        response = self.client.get(url, {'vue': '1', 'kind': event.kind})
        self.assertTemplateUsed(response, 'admin/arealisting/review_queue_vue.html')
        data = response.context['review_queue_data']
        self.assertEqual(data['events'][0]['id'], event.pk)
        self.assertEqual(data['events'][0]['field_changes'][0]['label'], 'Спальни')
        self.assertEqual(data['return_fields']['return_kind'], event.kind)
        checked = self.client.post(reverse('admin:arealisting_review_event', args=[event.pk]), {
            'return_kind': event.kind, 'return_page': '1', 'return_vue': '1',
        })
        self.assertIn('kind=UNIT_FIELDS', checked['Location'])
        self.assertIn('vue=1', checked['Location'])
        self.assertTemplateUsed(self.client.get(checked['Location']), 'admin/arealisting/review_queue_vue.html')
        self.assertEqual(self.client.get(checked['Location']).context['review_queue_data']['event_count'], 0)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_review_queue_respects_read_only_permissions(self, _available):
        viewer = User.objects.create_user(username='vue-review-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingsyncevent'))
        self.client.force_login(viewer)
        response = self.client.get(reverse('admin:arealisting_review_queue'), {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['review_queue_data']['can_mark_checked'])
        self.assertEqual(response.context['review_queue_data']['price_reviews'], [])

    def test_review_queue_compares_card_and_can_protect_its_value(self):
        project = ArealistingProject.objects.create(external_id='compare-project', name_en='Compare project')
        property_type = PropertyType.objects.create(name='Compare condo')
        district = District.objects.create(name='Compare district', slug='compare-district')
        prop = Property.objects.create(title='Compare card', slug='compare-card',
                                       property_type=property_type, district=district,
                                       bedrooms=1, is_active=False)
        group = ArealistingListingGroup.objects.create(
            project=project, property=prop, source_owned_fields=['bedrooms'],
        )
        unit = ArealistingUnit.objects.create(external_id='compare-unit', project=project,
                                              listing_group=group, bedrooms=2)
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        event = ArealistingSyncEvent.objects.create(
            run=run, project=project, property=prop, unit=unit,
            kind=ArealistingSyncEvent.Kind.UNIT_FIELDS,
            details={'changed_fields': [
                {'field': 'bedrooms', 'before': '1', 'after': '2'},
                {'field': 'sea_view', 'before': 'False', 'after': 'True'},
            ]},
        )
        response = self.client.get(reverse('admin:arealisting_review_queue'))
        self.assertContains(response, 'Сейчас в Undersun')
        self.assertContains(response, 'Под управлением AREALISTING')
        self.assertContains(response, 'Не переносится в карточку автоматически')
        self.assertContains(response, 'Сохранить значение Undersun')
        keep_url = reverse('admin:arealisting_keep_card_value', args=[event.pk])
        self.assertEqual(self.client.get(keep_url).status_code, 405)
        self.assertEqual(self.client.post(keep_url, {
            'source_field': 'bedrooms', 'expected_card_value': '1', 'expected_source_value': '2',
        }).status_code, 302)
        group.refresh_from_db()
        prop.refresh_from_db()
        self.assertIn('bedrooms', group.locked_fields)
        self.assertEqual(prop.bedrooms, 1)
        audit = ArealistingPropertyChange.objects.get(property=prop)
        self.assertEqual(audit.actor, self.user)
        self.assertEqual(audit.details['locked_fields_added'], ['bedrooms'])
        self.assertContains(self.client.get(reverse('admin:arealisting_review_queue')),
                            'Защищено от обновления')
        self.assertEqual(self.client.post(keep_url, {
            'source_field': 'sea_view', 'expected_card_value': '1', 'expected_source_value': 'True',
        }).status_code, 404)

    def test_keep_card_value_rejects_stale_comparison(self):
        project = ArealistingProject.objects.create(external_id='stale-compare', name_en='Stale compare')
        property_type = PropertyType.objects.create(name='Stale compare condo')
        district = District.objects.create(name='Stale compare district', slug='stale-compare-district')
        prop = Property.objects.create(title='Stale compare card', slug='stale-compare-card',
                                       property_type=property_type, district=district,
                                       bedrooms=1, is_active=False)
        group = ArealistingListingGroup.objects.create(
            project=project, property=prop, source_owned_fields=['bedrooms'],
        )
        unit = ArealistingUnit.objects.create(external_id='stale-compare-unit', project=project,
                                              listing_group=group, bedrooms=2)
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        event = ArealistingSyncEvent.objects.create(
            run=run, project=project, property=prop, unit=unit,
            kind=ArealistingSyncEvent.Kind.UNIT_FIELDS,
            details={'changed_fields': [{'field': 'bedrooms', 'before': '1', 'after': '2'}]},
        )
        unit.bedrooms = 3
        unit.save(update_fields=('bedrooms',))
        keep_url = reverse('admin:arealisting_keep_card_value', args=[event.pk])
        stale_source = self.client.post(keep_url, {
            'source_field': 'bedrooms', 'expected_card_value': '1', 'expected_source_value': '2',
        }, follow=True)
        self.assertContains(stale_source, 'Данные AREALISTING изменились')
        unit.bedrooms = 2
        unit.save(update_fields=('bedrooms',))
        prop.bedrooms = 3
        prop.save(update_fields=('bedrooms',))
        response = self.client.post(keep_url, {
            'source_field': 'bedrooms', 'expected_card_value': '1', 'expected_source_value': '2',
        }, follow=True)
        self.assertContains(response, 'Значение карточки изменилось')
        group.refresh_from_db()
        self.assertEqual(group.locked_fields, [])

    def test_review_queue_explains_protected_price_and_links_to_group(self):
        project = ArealistingProject.objects.create(external_id='reason-price', name_en='Reason project')
        property_type = PropertyType.objects.create(name='Reason condo')
        district = District.objects.create(name='Reason district', slug='reason-district')
        prop = Property.objects.create(title='Reason card', slug='reason-card',
                                       property_type=property_type, district=district, is_active=False)
        group = ArealistingListingGroup.objects.create(
            project=project, property=prop, locked_fields=['price_sale_thb'],
            validation_errors=['Цена AREALISTING: цена защищена от обновлений. Сохранена прежняя цена.'],
        )
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        ArealistingSyncEvent.objects.create(
            run=run, project=project, property=prop,
            kind=ArealistingSyncEvent.Kind.PRICE_SKIPPED,
            details={'reason': 'цена защищена от обновлений'},
        )
        response = self.client.get(reverse('admin:arealisting_review_queue'))
        self.assertContains(response, 'Цена карточки защищена от обновления AREALISTING')
        self.assertContains(response, 'Оставлено намеренно')
        self.assertContains(response, 'Проверить защиту цены')
        self.assertContains(response, reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk]))
        group.validation_errors = []
        group.save(update_fields=('validation_errors', 'updated_at'))
        refreshed = self.client.get(reverse('admin:arealisting_review_queue'))
        self.assertContains(refreshed, 'Причина больше не числится в замечаниях группы')

    def test_review_queue_explains_divergent_values_and_missing_rate(self):
        project = ArealistingProject.objects.create(external_id='reason-mixed', name_en='Mixed project')
        property_type = PropertyType.objects.create(name='Mixed condo')
        district = District.objects.create(name='Mixed district', slug='mixed-reason-district')
        prop = Property.objects.create(title='Mixed card', slug='mixed-reason-card',
                                       property_type=property_type, district=district, is_active=False,
                                       bedrooms=1)
        group = ArealistingListingGroup.objects.create(
            project=project, property=prop, source_owned_fields=['bedrooms'],
            validation_errors=['mixed_unit_currencies',
                               'Цена AREALISTING: нет курса валюты или цены. Сохранена прежняя цена.'],
        )
        first = ArealistingUnit.objects.create(
            external_id='mixed-first', project=project, listing_group=group, bedrooms=2,
            availability_status='AVAILABLE', price=1000000, currency='THB',
        )
        ArealistingUnit.objects.create(
            external_id='mixed-second', project=project, listing_group=group, bedrooms=3,
            availability_status='AVAILABLE', price=1200000, currency='USD',
        )
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        ArealistingSyncEvent.objects.create(
            run=run, project=project, property=prop, unit=first,
            kind=ArealistingSyncEvent.Kind.UNIT_FIELDS,
            details={'changed_fields': [{'field': 'bedrooms', 'before': '1', 'after': '2'}]},
        )
        response = self.client.get(reverse('admin:arealisting_review_queue'))
        self.assertContains(response, 'У выбранных предложений разные валюты')
        self.assertContains(response, 'У выбранных предложений разные значения')
        self.assertContains(response, 'Не удалось пересчитать цену между валютами')
        self.assertContains(response, reverse('admin:currency_exchangerate_changelist'))
        self.assertContains(response, reverse('admin:arealisting_matching') + f'?project={project.pk}')

    def test_review_queue_requires_event_permissions(self):
        viewer = User.objects.create_user(username='review-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingsyncevent'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('admin:arealisting_review_queue')).status_code, 200)
        self.assertEqual(self.client.post(reverse('admin:arealisting_review_event', args=[9999])).status_code, 403)

    def test_price_review_page_confirms_large_change(self):
        from apps.arealisting.services.pricing import update_group_price
        project = ArealistingProject.objects.create(external_id='price-project', name_en='Price project')
        prop = Property.objects.create(
            title='Price card', slug='price-card', deal_type='sale',
            price_sale_thb=Decimal('1000000'),
            property_type=PropertyType.objects.create(name='condo'),
            district=District.objects.create(name='Price district', slug='price-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        ArealistingUnit.objects.create(
            project=project, listing_group=group, external_id='price-unit',
            unit_number='A101', availability_status='AVAILABLE',
            price=Decimal('1400000'), currency='THB',
        )
        with patch('apps.arealisting.services.pricing.CurrencyService.convert_price',
                   side_effect=lambda amount, source, target: amount if target == 'THB' else amount / 2):
            update_group_price(group.pk)
            review = ArealistingPriceReview.objects.get(status='PENDING')
            url = reverse('admin:arealisting_arealistingpricereview_review', args=[review.pk])
            response = self.client.get(url)
            self.assertContains(response, 'Подтвердить новую цену')
            self.assertContains(response, 'A101')
            dashboard = self.client.get(reverse('admin:arealisting_arealistingproject_changelist'))
            self.assertContains(dashboard, 'Цены на подтверждении')
            self.assertContains(dashboard, url)
            readiness = self.client.get(reverse(
                'admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk],
            ))
            self.assertContains(readiness, 'Подтверждение изменения цены')
            self.assertContains(readiness, url)
            response = self.client.post(url, {'decision': 'approve'})
        self.assertEqual(response.status_code, 302)
        prop.refresh_from_db()
        self.assertEqual(prop.price_sale_thb, Decimal('1400000'))
        self.assertEqual(self.client.get(url).context['review'].status, 'APPROVED')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_readiness_shows_checks_and_preserves_preview_navigation(self, _available):
        project = ArealistingProject.objects.create(external_id='readiness-project', name_en='Ready project')
        prop = Property.objects.create(
            title='Draft card', slug='draft-card', is_active=False,
            property_type=PropertyType.objects.create(name='readiness condo'),
            district=District.objects.create(name='Readiness district', slug='readiness-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        url = reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk])

        response = self.client.get(url, {'vue': '1'})
        self.assertTemplateUsed(response, 'admin/arealisting/readiness_vue.html')
        data = response.context['readiness_data']
        self.assertEqual(data['property_title'], 'Draft card')
        self.assertFalse(data['ready'])
        self.assertEqual(data['required_missing'], sum(
            not check['ok'] for check in data['checks'] if check['required']))
        self.assertEqual(data['group_url'], reverse(
            'admin:arealisting_arealistinglistinggroup_change', args=[group.pk]) + '?vue=1')
        actions = {check['key']: check['action_url'] for check in data['checks']}
        self.assertTrue(actions['units'].endswith('&vue=1'))
        self.assertTrue(actions['photo'].endswith('?vue=1'))
        self.assertEqual(self.client.post(url + '?vue=1', {}).status_code, 403)
        self.assertTemplateUsed(self.client.get(url), 'admin/arealisting/readiness.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_readiness_respects_viewer_permissions(self, _available):
        project = ArealistingProject.objects.create(external_id='readiness-viewer', name_en='Viewer project')
        prop = Property.objects.create(
            title='Viewer card', slug='viewer-card',
            property_type=PropertyType.objects.create(name='viewer condo'),
            district=District.objects.create(name='Viewer district', slug='viewer-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        viewer = User.objects.create_user('readiness-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistinglistinggroup'))
        self.client.force_login(viewer)
        url = reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk])
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'admin/arealisting/readiness_vue.html')
        data = response.context['readiness_data']
        self.assertEqual(data['property_url'], '')
        self.assertTrue(all(not check['action_url'] for check in data['checks']))

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_detach_confirms_current_group_and_preserves_preview(self, _available):
        project = ArealistingProject.objects.create(external_id='detach-project', name_en='Detach project')
        prop = Property.objects.create(
            title='Detach card', slug='detach-card',
            property_type=PropertyType.objects.create(name='detach condo'),
            district=District.objects.create(name='Detach district', slug='detach-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        unit = ArealistingUnit.objects.create(external_id='detach-unit', project=project, listing_group=group)
        group_url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        detach_url = reverse('admin:arealisting_detach_property', args=[prop.pk])

        detail = self.client.get(group_url, {'vue': '1'})
        self.assertEqual(detail.context['group_detail_data']['detach_url'], detach_url + '?vue=1')
        confirm = self.client.get(detach_url, {'vue': '1'})
        self.assertTemplateUsed(confirm, 'admin/arealisting/detach_property_vue.html')
        data = confirm.context['detach_property_data']
        self.assertEqual(data['group_id'], group.pk)
        self.assertEqual(data['unit_count'], 1)
        self.assertEqual(data['group_url'], group_url + '?vue=1')
        self.assertTemplateUsed(self.client.get(detach_url), 'admin/arealisting/detach_property.html')
        self.assertEqual(self.client.post(detach_url + '?vue=1', {'group_id': group.pk + 1}).status_code, 404)
        self.assertTrue(ArealistingListingGroup.objects.filter(pk=group.pk).exists())

        detached = self.client.post(detach_url + '?vue=1', {'group_id': group.pk})
        self.assertEqual(detached.status_code, 302)
        self.assertIn('vue=1', detached['Location'])
        self.assertIn(f'property={prop.pk}', detached['Location'])
        self.assertFalse(ArealistingListingGroup.objects.filter(pk=group.pk).exists())
        unit.refresh_from_db()
        self.assertIsNone(unit.listing_group_id)
        self.assertTrue(Property.objects.filter(pk=prop.pk).exists())
        self.assertEqual(ArealistingPropertyChange.objects.filter(property=prop, kind='DETACH').count(), 1)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_detach_is_hidden_without_delete_permission(self, _available):
        project = ArealistingProject.objects.create(external_id='detach-viewer', name_en='Viewer project')
        prop = Property.objects.create(
            title='Viewer detach card', slug='viewer-detach-card',
            property_type=PropertyType.objects.create(name='viewer detach condo'),
            district=District.objects.create(name='Viewer detach district', slug='viewer-detach-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        viewer = User.objects.create_user('detach-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistinglistinggroup'))
        self.client.force_login(viewer)
        group_url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        detail = self.client.get(group_url)
        self.assertEqual(detail.context['group_detail_data']['detach_url'], '')
        detach_url = reverse('admin:arealisting_detach_property', args=[prop.pk])
        self.assertEqual(self.client.get(detach_url).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_group_create_validates_and_saves(self, _available):
        project = ArealistingProject.objects.create(external_id='create-group-project', name_en='Create project')
        prop = Property.objects.create(
            title='Free card', slug='free-card',
            property_type=PropertyType.objects.create(name='create condo'),
            district=District.objects.create(name='Create district', slug='create-district'),
        )
        url = reverse('admin:arealisting_arealistinglistinggroup_add')
        response = self.client.get(url, {'vue': '1', 'project': project.pk})
        self.assertTemplateUsed(response, 'admin/arealisting/group_create_vue.html')
        self.assertEqual(response.context['group_create_data']['project']['id'], project.pk)
        lookup = self.client.get(url, {'vue': '1', 'lookup': 'properties', 'q': 'Free card'})
        self.assertEqual(lookup.json()['results'][0]['id'], prop.pk)

        invalid = self.client.post(url + '?vue=1', {'name': 'New group', 'grouping_mode': 'PROJECT'})
        self.assertTemplateUsed(invalid, 'admin/arealisting/group_create_vue.html')
        self.assertIn('project', invalid.context['group_create_data']['errors'])
        payload = {'project': project.pk, 'property': prop.pk, 'grouping_mode': 'PROJECT',
                   'name': 'New group', 'is_active': 'on'}
        saved = self.client.post(url + '?vue=1', payload)
        group = ArealistingListingGroup.objects.get(project=project, name='New group')
        self.assertEqual(group.property_id, prop.pk)
        self.assertIn(f'/{group.pk}/change/?vue=1', saved['Location'])
        self.assertTemplateUsed(self.client.get(saved['Location']), 'admin/arealisting/group_detail_vue.html')
        duplicate = self.client.post(url + '?vue=1', {**payload, 'property': ''})
        self.assertTemplateUsed(duplicate, 'admin/arealisting/group_create_vue.html')
        self.assertIn('__all__', duplicate.context['group_create_data']['errors'])
        self.assertEqual(ArealistingListingGroup.objects.filter(project=project).count(), 1)
        self.assertTemplateUsed(self.client.get(url), 'admin/arealisting/arealistinglistinggroup/change_form.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_group_create_requires_add_permission(self, _available):
        viewer = User.objects.create_user('group-create-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistinglistinggroup'))
        self.client.force_login(viewer)
        url = reverse('admin:arealisting_arealistinglistinggroup_add')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(url, {'lookup': 'projects', 'q': 'a'}).status_code, 403)
        self.assertEqual(self.client.post(url, {'project': '1'}).status_code, 403)

        viewer.user_permissions.add(
            Permission.objects.get(codename='add_arealistinglistinggroup'),
            Permission.objects.get(codename='view_arealistingproject'),
        )
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'admin/arealisting/group_create_vue.html')
        self.assertFalse(response.context['group_create_data']['can_choose_property'])
        self.assertEqual(self.client.get(url, {'lookup': 'properties', 'q': 'card'}).status_code, 403)
        self.assertEqual(self.client.post(url, {'project': '1', 'property': '1'}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_workspace_navigation_keeps_preview_across_core_flow(self, _available):
        project = ArealistingProject.objects.create(external_id='navigation-project', name_en='Navigation project')
        prop = Property.objects.create(
            title='Navigation draft', slug='navigation-draft', is_active=False,
            property_type=PropertyType.objects.create(name='navigation condo'),
            district=District.objects.create(name='Navigation district', slug='navigation-district'),
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=prop,
            catalog_origin=ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT,
        )
        run = ArealistingSyncRun.objects.create(mode='FULL', status='SUCCESS')
        ArealistingSyncEvent.objects.create(
            run=run, project=project, kind=ArealistingSyncEvent.Kind.NEW_UNIT,
        )
        overview_url = reverse('admin:arealisting_arealistingproject_changelist')
        overview = self.client.get(overview_url, {'vue': '1'})
        self.assertContains(overview, overview_url + '?vue=1#project-search')
        draft_item = next(item for item in overview.context['work_items'] if item['kind'] == 'Черновик')
        self.assertEqual(draft_item['url'], reverse(
            'admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk]) + '?vue=1')
        self.assertContains(overview, 'name="vue" value="1"', html=False)
        self.assertIn('vue=1', overview.context['sync_events_url'])
        self.assertIn('vue=1', overview.context['sync_events'][0]['url'])

        group_list = self.client.get(reverse('admin:arealisting_arealistinglistinggroup_changelist'),
                                     {'vue': '1', 'project': project.pk})
        self.assertEqual(group_list.context['group_list_data']['overview_url'], overview_url + '?vue=1')
        with patch('apps.arealisting.admin.price_report_context', return_value={}):
            matching = self.client.get(reverse('admin:arealisting_matching'), {'project': project.pk, 'vue': '1'})
        self.assertTemplateUsed(matching, 'admin/arealisting/matching_vue.html')
        self.assertContains(matching, f'data-projects-url="{overview_url}?vue=1"')
        detail = self.client.get(reverse('admin:arealisting_arealistingproject_change', args=[project.pk]),
                                 {'vue': '1'})
        self.assertTrue(detail.context['project_detail_data']['vue_preview'])

        with patch('apps.arealisting.admin.ArealistingProjectAdmin._run_sync', return_value=True):
            load = self.client.post(reverse('admin:arealisting_load_inventory', args=[project.pk]), {'vue': '1'})
            sync = self.client.post(reverse('admin:arealisting_arealistingproject_sync_projects'), {'vue': '1'})
        self.assertIn('vue=1', load['Location'])
        self.assertEqual(sync['Location'], overview_url + '?vue=1')

    def test_price_review_requires_property_change_permission_to_decide(self):
        project = ArealistingProject.objects.create(external_id='restricted-price', name_en='Restricted')
        prop = Property.objects.create(
            title='Restricted card', slug='restricted-card',
            property_type=PropertyType.objects.create(name='condo'),
            district=District.objects.create(name='Restricted district', slug='restricted-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        review = ArealistingPriceReview.objects.create(
            group=group, project=project, property=prop,
            before={'price_sale_thb': '1000000.00'},
            after={'price_sale_thb': '1400000.00'},
            change_percent=Decimal('40'),
        )
        staff = User.objects.create_user('price-viewer', password='test-password', is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(codename='view_arealistingpricereview'),
            Permission.objects.get(codename='change_arealistingpricereview'),
        )
        self.client.force_login(staff)
        url = reverse('admin:arealisting_arealistingpricereview_review', args=[review.pk])
        self.assertNotContains(self.client.get(url), 'Подтвердить новую цену')
        self.assertEqual(self.client.post(url, {'decision': 'approve'}).status_code, 403)
        review.refresh_from_db()
        self.assertEqual(review.status, 'PENDING')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_price_review_shows_proposal_and_keeps_vue_after_rejection(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-price-project', name_en='Vue price')
        prop = Property.objects.create(
            title='Vue price card', slug='vue-price-card',
            property_type=PropertyType.objects.create(name='Vue condo'),
            district=District.objects.create(name='Vue price district', slug='vue-price-district'),
        )
        group = ArealistingListingGroup.objects.create(project=project, property=prop)
        review = ArealistingPriceReview.objects.create(
            group=group, project=project, property=prop,
            before={'price_sale_thb': '1000000.00'},
            after={'price_sale_thb': '1400000.00'}, change_percent=Decimal('40'),
            units=[{'number': 'A101', 'source_price': '1400000', 'currency': 'THB', 'price_thb': '1400000'}],
        )
        url = reverse('admin:arealisting_arealistingpricereview_review', args=[review.pk])
        response = self.client.get(url, {'vue': '1'})
        self.assertTemplateUsed(response, 'admin/arealisting/price_review_vue.html')
        self.assertEqual(response.context['price_review_data']['units'][0]['number'], 'A101')
        self.assertTrue(response.context['price_review_data']['can_decide'])
        decision = self.client.post(url, {'decision': 'reject', 'vue': '1'})
        self.assertEqual(decision['Location'], url + '?vue=1')
        review.refresh_from_db()
        self.assertEqual(review.status, ArealistingPriceReview.Status.REJECTED)
        self.assertFalse(self.client.get(decision['Location']).context['price_review_data']['can_decide'])

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_price_review_list_filters_and_keeps_preview_links(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-list-project', name_en='Vue list complex')
        property_type = PropertyType.objects.create(name='Vue list condo')
        district = District.objects.create(name='Vue list district', slug='vue-list-district')
        first = Property.objects.create(title='Alpha price card', slug='alpha-price-card',
                                        property_type=property_type, district=district)
        second = Property.objects.create(title='Beta price card', slug='beta-price-card',
                                         property_type=property_type, district=district)
        pending = ArealistingPriceReview.objects.create(
            project=project, property=first, change_percent=Decimal('40'),
            before={'price_sale_thb': '1000000'}, after={'price_sale_thb': '1400000'},
        )
        ArealistingPriceReview.objects.create(
            project=project, property=second, status=ArealistingPriceReview.Status.APPROVED,
            change_percent=Decimal('20'), before={'price_sale_thb': '1000000'},
            after={'price_sale_thb': '1200000'},
        )
        url = reverse('admin:arealisting_arealistingpricereview_changelist')
        response = self.client.get(url, {'vue': '1', 'status__exact': 'PENDING', 'q': 'Alpha'})
        self.assertTemplateUsed(response, 'admin/arealisting/price_review_list_vue.html')
        data = response.context['price_review_list_data']
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['reviews'][0]['id'], pending.pk)
        self.assertEqual(data['all_count'], 1)
        self.assertEqual(next(item['count'] for item in data['statuses'] if item['value'] == 'PENDING'), 1)
        self.assertIn('vue=1', data['reviews'][0]['url'])
        detail = self.client.get(data['reviews'][0]['url'])
        self.assertIn('q=Alpha', detail.context['price_review_data']['back_url'])
        self.assertIn('status__exact=PENDING', detail.context['price_review_data']['back_url'])
        self.assertIn('q=Alpha', data['all_url'])
        self.assertNotContains(self.client.get(url, {'vue': '1', 'status__exact': 'PENDING', 'q': 'Beta'}),
                               'Beta price card')
        legacy = self.client.get(url, {'status__exact': 'PENDING'})
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingpricereview/change_list.html')
        self.assertContains(legacy, 'Открыть новый интерфейс проверки цен')
        ArealistingPriceReview.objects.filter(property=second).update(
            created_at=timezone.now() - timezone.timedelta(days=40),
        )
        recent = self.client.get(url, {'vue': '1', 'period': '7d'})
        self.assertEqual(recent.context['price_review_list_data']['result_count'], 1)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_price_review_list_hides_property_link_without_property_permission(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-list-viewer', name_en='Viewer complex')
        prop = Property.objects.create(
            title='Viewer price card', slug='viewer-price-card',
            property_type=PropertyType.objects.create(name='Viewer condo'),
            district=District.objects.create(name='Viewer district', slug='viewer-district'),
        )
        ArealistingPriceReview.objects.create(project=project, property=prop, change_percent=Decimal('40'))
        viewer = User.objects.create_user('price-list-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingpricereview'))
        self.client.force_login(viewer)
        response = self.client.get(reverse('admin:arealisting_arealistingpricereview_changelist'), {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['price_review_list_data']['reviews'][0]['property_url'], '')

    def test_asset_page_explains_error_and_offers_retry(self):
        project = ArealistingProject.objects.create(external_id='asset-project', name_en='Asset project')
        asset = ArealistingAsset.objects.create(
            source_key='retry-image', project=project,
            source_url='https://cdn.example.test/image.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
            last_error='Image server returned 504',
        )
        list_url = reverse('admin:arealisting_arealistingasset_changelist')
        response = self.client.get(list_url, {'download_state': 'error'})
        self.assertContains(response, 'Как работать с материалами')
        self.assertContains(response, 'Image server returned 504')
        self.assertContains(response, 'Повторить скачивание выбранных изображений')
        self.assertEqual(response.context['cl'].result_count, 1)

        response = self.client.get(reverse('admin:arealisting_arealistingasset_change', args=[asset.pk]))
        self.assertContains(response, 'Что делать с этим материалом')
        self.assertContains(response, 'Повторить скачивание изображения')
        self.assertContains(response, 'Связи с карточками')

    def test_asset_retry_downloads_image_and_skips_documents(self):
        project = ArealistingProject.objects.create(external_id='retry-project', name_en='Retry project')
        image = ArealistingAsset.objects.create(
            source_key='image', project=project,
            source_url='https://cdn.example.test/image.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
            last_error='Timeout',
        )
        document = ArealistingAsset.objects.create(
            source_key='document', project=project,
            source_url='https://cdn.example.test/brochure.pdf',
            asset_type=ArealistingAsset.AssetType.DOCUMENT,
        )
        url = reverse('admin:arealisting_arealistingasset_retry_download', args=[image.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch('apps.arealisting.services.media.download_asset', return_value=True) as download:
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        download.assert_called_once()
        self.assertEqual(download.call_args.args[0], image)

        document_url = reverse('admin:arealisting_arealistingasset_retry_download', args=[document.pk])
        with patch('apps.arealisting.services.media.download_asset') as download:
            self.client.post(document_url)
        download.assert_not_called()
        response = self.client.get(reverse('admin:arealisting_arealistingasset_change', args=[document.pk]))
        self.assertNotContains(response, 'Повторить скачивание изображения')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_asset_list_filters_errors_and_shows_retryable_images(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-assets', name_en='Vue assets project')
        image = ArealistingAsset.objects.create(
            source_key='vue-image', project=project,
            source_url='https://cdn.example.test/image.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
            last_error='Image server returned 504',
        )
        ArealistingAsset.objects.create(
            source_key='vue-document', project=project,
            source_url='https://cdn.example.test/file.pdf',
            asset_type=ArealistingAsset.AssetType.DOCUMENT,
        )
        url = reverse('admin:arealisting_arealistingasset_changelist')
        response = self.client.get(url, {'vue': '1', 'download_state': 'error'})
        self.assertTemplateUsed(response, 'admin/arealisting/asset_list_vue.html')
        data = response.context['asset_list_data']
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['counts'], {'all': 2, 'error': 1, 'downloaded': 0, 'url': 1})
        self.assertEqual(data['assets'][0]['id'], image.pk)
        self.assertTrue(data['assets'][0]['can_retry'])
        self.assertIn('vue=1', data['assets'][0]['detail_url'])
        detail = self.client.get(data['assets'][0]['detail_url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/asset_detail_vue.html')
        self.assertIn('download_state=error', detail.context['asset_detail_data']['back_url'])
        self.assertIn('vue=1', detail.context['asset_detail_data']['back_url'])
        self.assertEqual(detail.context['asset_detail_data']['error'], 'Image server returned 504')
        self.assertIn('vue=1', data['state_urls']['downloaded'])
        filtered = self.client.get(url, {'vue': '1', 'asset_type__exact': 'DOCUMENT'})
        self.assertEqual(filtered.context['asset_list_data']['result_count'], 1)
        self.assertFalse(filtered.context['asset_list_data']['assets'][0]['can_retry'])
        legacy = self.client.get(url, {'download_state': 'error'})
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingasset/change_list.html')
        self.assertContains(legacy, 'Открыть новый список материалов')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_asset_retry_reports_result_and_respects_permissions(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-retry-assets', name_en='Vue retry')
        image = ArealistingAsset.objects.create(
            source_key='vue-retry-image', project=project,
            source_url='https://cdn.example.test/image.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
            last_error='Timeout',
        )
        retry_url = reverse('admin:arealisting_arealistingasset_retry_download', args=[image.pk])
        def successful_download(asset, **_kwargs):
            asset.last_error = ''
            asset.downloaded_at = timezone.now()
            asset.save(update_fields=('last_error', 'downloaded_at', 'updated_at'))
            return True
        with patch('apps.arealisting.services.media.download_asset', side_effect=successful_download):
            response = self.client.post(retry_url, {'format': 'json'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['downloaded'], 1)
        self.assertEqual(response.json()['state'], 'downloaded')

        viewer = User.objects.create_user('vue-asset-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingasset'))
        self.client.force_login(viewer)
        list_response = self.client.get(reverse('admin:arealisting_arealistingasset_changelist'), {'vue': '1'})
        self.assertEqual(list_response.status_code, 200)
        self.assertFalse(list_response.context['asset_list_data']['can_retry'])
        self.assertFalse(list_response.context['asset_list_data']['assets'][0]['can_retry'])
        detail = self.client.get(reverse('admin:arealisting_arealistingasset_change', args=[image.pk]), {'vue': '1'})
        self.assertFalse(detail.context['asset_detail_data']['can_retry'])
        self.assertEqual(self.client.post(retry_url, {'format': 'json'}).status_code, 403)

    def test_asset_links_to_group_with_direct_media_import(self):
        project = ArealistingProject.objects.create(external_id='media-project', name_en='Media project')
        property_type = PropertyType.objects.create(name='Media condo')
        district = District.objects.create(name='Media district', slug='media-admin-district')
        property_obj = Property.objects.create(
            title='Media card', slug='media-admin-card',
            property_type=property_type, district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=property_obj, name='Media group',
        )
        asset = ArealistingAsset.objects.create(
            source_key='media-image', project=project,
            source_url='https://cdn.example.test/media.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
            last_error='Previous download failed',
        )
        group_url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        asset_url = reverse('admin:arealisting_arealistingasset_change', args=[asset.pk])

        response = self.client.get(asset_url)
        self.assertContains(response, 'Подходящие группы')
        self.assertContains(response, group_url)
        with override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False), patch(
            'apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True,
        ):
            vue = self.client.get(asset_url, {'vue': '1'})
        self.assertTemplateUsed(vue, 'admin/arealisting/asset_detail_vue.html')
        self.assertEqual(vue.context['asset_detail_data']['groups'][0]['url'], group_url + '?vue=1')
        self.assertIn('preview-media/', vue.context['asset_detail_data']['groups'][0]['preview_url'])
        response = self.client.get(group_url)
        self.assertContains(response, 'Проверить и импортировать фотографии и планировки')
        self.assertContains(response, 'Previous download failed')
        self.assertContains(response, asset_url)

        import_url = reverse('admin:arealisting_arealistinglistinggroup_import_media', args=[group.pk])
        preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
        self.assertEqual(self.client.get(import_url).status_code, 405)
        preview = self.client.get(preview_url)
        self.assertContains(preview, 'Добавится: 1')
        self.assertContains(preview, 'Какие фото импортировать')
        self.assertContains(preview, 'Сделать главным')
        self.assertContains(preview, f'href="{asset.source_url}" target="_blank"')
        self.assertNotContains(preview, 'media-preview-items')
        fingerprint = preview.context['previews'][0]['fingerprint']
        with patch('apps.arealisting.services.media_jobs.start_media_worker') as worker, \
                patch('apps.arealisting.services.media.sync_group_media') as sync:
            response = self.client.post(import_url, {
                'selection_confirmed': '1', 'preview_fingerprint': fingerprint,
                'asset': [str(asset.pk)],
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Импорт фото: Ожидает')
        job = ArealistingMediaJob.objects.get(group=group)
        self.assertEqual(job.selected_asset_ids, [asset.pk])
        sync.assert_not_called()
        worker.assert_called_once()

    def test_group_import_saves_selected_main_photo(self):
        project = ArealistingProject.objects.create(external_id='main-choice-admin', name_en='Main choice')
        property_type = PropertyType.objects.create(name='Main choice condo')
        district = District.objects.create(name='Main choice district', slug='main-choice-district')
        property_obj = Property.objects.create(
            title='Main choice card', slug='main-choice-card', property_type=property_type,
            district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(project=project, property=property_obj, name='Main choice')
        asset = ArealistingAsset.objects.create(
            source_key='main-choice-asset', project=project,
            source_url='https://cdn.example.test/main-choice.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
        import_url = reverse('admin:arealisting_arealistinglistinggroup_import_media', args=[group.pk])
        selected = self.client.post(preview_url, {
            'asset': [str(asset.pk)], 'preferred_main_asset_id': str(asset.pk),
        })
        fingerprint = selected.context['previews'][0]['fingerprint']
        with patch('apps.arealisting.services.media_jobs.start_media_worker'):
            response = self.client.post(import_url, {
                'selection_confirmed': '1', 'preview_fingerprint': fingerprint,
                'asset': [str(asset.pk)], 'preferred_main_asset_id': str(asset.pk),
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ArealistingMediaJob.objects.get(group=group).preferred_main_asset_id, asset.pk)

    def test_group_import_does_not_run_without_candidates(self):
        project = ArealistingProject.objects.create(external_id='empty-media', name_en='Empty media')
        property_type = PropertyType.objects.create(name='Empty media condo')
        district = District.objects.create(name='Empty media district', slug='empty-media-admin')
        property_obj = Property.objects.create(
            title='Empty media card', slug='empty-media-admin-card',
            property_type=property_type, district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=property_obj, name='Empty media group',
        )
        import_url = reverse('admin:arealisting_arealistinglistinggroup_import_media', args=[group.pk])
        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            response = self.client.post(import_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Сначала выберите фото')
        sync.assert_not_called()

        ArealistingAsset.objects.create(
            source_key='locked-media-image', project=project,
            source_url='https://cdn.example.test/locked.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        group.locked_fields = ['images', 'floorplans']
        group.save(update_fields=['locked_fields'])
        group_url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        response = self.client.get(group_url)
        self.assertNotContains(response, 'Проверить и импортировать фотографии и планировки')
        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            response = self.client.post(import_url, follow=True)
        self.assertContains(response, 'Сначала выберите фото')
        sync.assert_not_called()

    def test_photo_import_requires_current_preview(self):
        project = ArealistingProject.objects.create(external_id='preview-stale', name_en='Preview stale')
        property_type = PropertyType.objects.create(name='Preview stale condo')
        district = District.objects.create(name='Preview stale district', slug='preview-stale-district')
        property_obj = Property.objects.create(
            title='Preview stale card', slug='preview-stale-card',
            property_type=property_type, district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=property_obj, name='Preview stale group',
        )
        ArealistingAsset.objects.create(
            source_key='preview-stale-one', project=project,
            source_url='https://cdn.example.test/one.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
        import_url = reverse('admin:arealisting_arealistinglistinggroup_import_media', args=[group.pk])
        fingerprint = self.client.get(preview_url).context['previews'][0]['fingerprint']
        ArealistingAsset.objects.create(
            source_key='preview-stale-two', project=project,
            source_url='https://cdn.example.test/two.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )

        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            response = self.client.post(import_url, {
                'selection_confirmed': '1', 'preview_fingerprint': fingerprint,
                'asset': [str(ArealistingAsset.objects.get(source_key='preview-stale-one').pk)],
            }, follow=True)

        self.assertContains(response, 'Состав фото изменился')
        self.assertContains(response, 'Какие фото импортировать')
        sync.assert_not_called()

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    def test_vue_media_preview_keeps_selected_photos_after_recalculation(self):
        project = ArealistingProject.objects.create(external_id='vue-media', name_en='Vue media')
        property_type = PropertyType.objects.create(name='Vue media condo')
        district = District.objects.create(name='Vue media district', slug='vue-media-district')
        property_obj = Property.objects.create(
            title='Vue media card', slug='vue-media-card', property_type=property_type,
            district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(project=project, property=property_obj, name='Vue media group')
        first = ArealistingAsset.objects.create(
            source_key='vue-media-one', project=project,
            source_url='https://cdn.example.test/vue-one.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        ArealistingAsset.objects.create(
            source_key='vue-media-two', project=project,
            source_url='https://cdn.example.test/vue-two.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True):
            response = self.client.get(preview_url + '?vue=1')
            selected = self.client.post(preview_url + '?vue=1', {
                'asset': [str(first.pk)], 'preferred_main_asset_id': str(first.pk),
            })
        self.assertTemplateUsed(response, 'admin/arealisting/media_preview_vue.html')
        self.assertEqual(len(response.context['media_preview_data']['available']), 2)
        self.assertTemplateUsed(selected, 'admin/arealisting/media_preview_vue.html')
        self.assertEqual(selected.context['media_preview_data']['additions'], 1)
        self.assertEqual(selected.context['media_preview_data']['preferred_main_asset_id'], first.pk)
        self.assertEqual(selected.context['media_preview_data']['preview_url'], preview_url + '?vue=1')
        with patch('apps.arealisting.services.media_jobs.start_media_worker'):
            confirmed = self.client.post(selected.context['confirm_url'], {
                'selection_confirmed': '1',
                'preview_fingerprint': selected.context['previews'][0]['fingerprint'],
                'asset': [str(first.pk)], 'preferred_main_asset_id': str(first.pk),
            })
        self.assertEqual(confirmed.status_code, 302)
        self.assertTrue(confirmed.url.endswith('?vue=1'))

    def test_media_preview_recalculates_selected_photos_without_importing(self):
        project = ArealistingProject.objects.create(external_id='preview-choice', name_en='Preview choice')
        property_type = PropertyType.objects.create(name='Preview choice condo')
        district = District.objects.create(name='Preview choice district', slug='preview-choice-district')
        property_obj = Property.objects.create(
            title='Preview choice card', slug='preview-choice-card',
            property_type=property_type, district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=property_obj, name='Preview choice group',
        )
        first = ArealistingAsset.objects.create(
            source_key='preview-choice-one', project=project,
            source_url='https://cdn.example.test/choice-one.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        second = ArealistingAsset.objects.create(
            source_key='preview-choice-two', project=project,
            source_url='https://cdn.example.test/choice-two.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        preview_url = reverse('admin:arealisting_arealistinglistinggroup_preview_media', args=[group.pk])
        import_url = reverse('admin:arealisting_arealistinglistinggroup_import_media', args=[group.pk])
        initial = self.client.get(preview_url)
        self.assertContains(initial, 'Добавится: 2')
        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            selected = self.client.post(preview_url, {'asset': [str(first.pk)]})
        self.assertContains(selected, 'Добавится: 1')
        self.assertEqual(selected.context['previews'][0]['selected_ids'], [first.pk])
        sync.assert_not_called()
        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            changed = self.client.post(import_url, {
                'selection_confirmed': '1',
                'preview_fingerprint': initial.context['previews'][0]['fingerprint'],
                'asset': [str(first.pk)],
            })
        self.assertContains(changed, 'Состав фото изменился')
        sync.assert_not_called()
        with patch('apps.arealisting.services.media_jobs.start_media_worker') as worker, \
                patch('apps.arealisting.services.media.sync_group_media') as sync:
            confirmed = self.client.post(import_url, {
                'selection_confirmed': '1',
                'preview_fingerprint': selected.context['previews'][0]['fingerprint'],
                'asset': [str(first.pk)],
            })
        self.assertEqual(confirmed.status_code, 302)
        self.assertEqual(ArealistingMediaJob.objects.get(group=group).selected_asset_ids, [first.pk])
        sync.assert_not_called()
        worker.assert_called_once()
        group.refresh_from_db()
        self.assertEqual(group.excluded_media_source_keys, [second.source_key])
        refreshed = self.client.get(preview_url)
        self.assertEqual(refreshed.context['previews'][0]['selected_ids'], [first.pk])
        none_selected = self.client.post(preview_url, {})
        self.assertContains(none_selected, 'Сохранить выбор')
        active_job = ArealistingMediaJob.objects.get(group=group)
        blocked = self.client.post(import_url, {
            'selection_confirmed': '1',
            'preview_fingerprint': none_selected.context['previews'][0]['fingerprint'],
        }, follow=True)
        self.assertContains(blocked, 'Импорт этой группы уже выполняется')
        group.refresh_from_db()
        self.assertEqual(group.excluded_media_source_keys, [second.source_key])
        active_job.status = ArealistingMediaJob.Status.SUCCESS
        active_job.save(update_fields=('status', 'updated_at'))
        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            saved = self.client.post(import_url, {
                'selection_confirmed': '1',
                'preview_fingerprint': none_selected.context['previews'][0]['fingerprint'],
            }, follow=True)
        self.assertContains(saved, 'Выбор фото сохранён')
        sync.assert_not_called()
        group.refresh_from_db()
        self.assertEqual(group.excluded_media_source_keys, sorted([first.source_key, second.source_key]))

    def test_bulk_photo_import_shows_preview_before_running(self):
        project = ArealistingProject.objects.create(external_id='preview-bulk', name_en='Preview bulk')
        property_type = PropertyType.objects.create(name='Preview bulk condo')
        district = District.objects.create(name='Preview bulk district', slug='preview-bulk-district')
        property_obj = Property.objects.create(
            title='Preview bulk card', slug='preview-bulk-card',
            property_type=property_type, district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=property_obj, name='Preview bulk group',
        )
        ArealistingAsset.objects.create(
            source_key='preview-bulk-one', project=project,
            source_url='https://cdn.example.test/bulk.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        url = reverse('admin:arealisting_arealistinglistinggroup_changelist')
        selection = {'action': 'import_media', '_selected_action': [str(group.pk)]}
        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            response = self.client.post(url, selection)
        self.assertContains(response, 'Проверьте изменения фотографий')
        sync.assert_not_called()
        fingerprint = response.context['previews'][0]['fingerprint']
        with patch('apps.arealisting.services.media_jobs.start_media_worker') as worker, \
                patch('apps.arealisting.services.media.sync_group_media') as sync:
            response = self.client.post(url, {
                **selection, 'confirm_media_import': '1',
                f'fingerprint_{group.pk}': fingerprint,
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Импорт фото: Ожидает')
        self.assertEqual(ArealistingMediaJob.objects.filter(group=group).count(), 1)
        sync.assert_not_called()
        worker.assert_called_once()

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_group_list_filters_issues_and_opens_bulk_media_preview(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-group-list', name_en='Vue group project')
        property_type = PropertyType.objects.create(name='Vue group condo')
        district = District.objects.create(name='Vue group district', slug='vue-group-district')
        prop = Property.objects.create(title='Vue group card', slug='vue-group-card',
                                       property_type=property_type, district=district, is_active=False)
        group = ArealistingListingGroup.objects.create(
            project=project, property=prop, name='Needs review',
            validation_errors=['mixed_unit_currencies'],
        )
        ArealistingListingGroup.objects.create(project=project, name='No issues')
        ArealistingAsset.objects.create(
            source_key='vue-group-photo', project=project,
            source_url='https://cdn.example.test/group.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        url = reverse('admin:arealisting_arealistinglistinggroup_changelist')
        response = self.client.get(url, {'vue': '1', 'attention': 'issues'})
        self.assertTemplateUsed(response, 'admin/arealisting/group_list_vue.html')
        data = response.context['group_list_data']
        self.assertEqual(data['counts']['all'], 2)
        self.assertEqual(data['counts']['issues'], 1)
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['groups'][0]['id'], group.pk)
        self.assertEqual(data['groups'][0]['issues'][0]['reason'], 'У выбранных предложений разные валюты.')
        self.assertIn('vue=1', data['groups'][0]['preview_url'])
        self.assertTrue(data['can_change'])

        with patch('apps.arealisting.services.media.sync_group_media') as sync:
            preview = self.client.post(url, {
                'action': 'import_media', '_selected_action': [str(group.pk)], 'vue': '1',
            })
        self.assertTemplateUsed(preview, 'admin/arealisting/media_preview_bulk_vue.html')
        self.assertIn('vue=1', preview.context['bulk_media_preview_data']['back_url'])
        sync.assert_not_called()

        with patch('apps.arealisting.admin.ArealistingSyncService.recalculate_listing_group') as recalculate:
            recalculated = self.client.post(url + '?vue=1', {
                'action': 'recalculate_groups', '_selected_action': [str(group.pk)], 'vue': '1',
            })
        self.assertEqual(recalculated.status_code, 302)
        self.assertIn('vue=1', recalculated['Location'])
        recalculate.assert_called_once()

        legacy = self.client.get(url)
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistinglistinggroup/change_list.html')
        self.assertContains(legacy, 'Открыть новый список связей с карточками')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_group_list_hides_actions_for_viewer(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-group-viewer', name_en='Viewer project')
        ArealistingListingGroup.objects.create(project=project, name='Viewer group')
        viewer = User.objects.create_user('vue-group-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistinglistinggroup'))
        self.client.force_login(viewer)
        response = self.client.get(reverse('admin:arealisting_arealistinglistinggroup_changelist'), {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        data = response.context['group_list_data']
        self.assertFalse(data['can_change'])
        self.assertEqual(data['groups'][0]['preview_url'], '')
        self.assertEqual(data['groups'][0]['matching_url'], '')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_group_detail_saves_settings_and_rejects_invalid_input(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-group-detail', name_en='Detail project')
        group = ArealistingListingGroup.objects.create(
            project=project, name='Original name', source_owned_fields=['bedrooms', 'images'],
            locked_fields=['bedrooms'],
        )
        url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        response = self.client.get(url, {'vue': '1'})
        self.assertTemplateUsed(response, 'admin/arealisting/group_detail_vue.html')
        data = response.context['group_detail_data']
        self.assertEqual(data['name'], 'Original name')
        self.assertEqual(data['protected_fields'], ['bedrooms'])
        self.assertEqual({choice['value'] for choice in data['protection_choices']}, {'bedrooms', 'images'})
        self.assertIn('vue=1', data['back_url'])

        saved = self.client.post(url, {
            'vue': '1', 'name': 'New name', 'protected_fields': ['images'],
        })
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(saved['Location'], url + '?vue=1')
        group.refresh_from_db()
        self.assertEqual(group.name, 'New name')
        self.assertFalse(group.is_active)
        self.assertEqual(group.locked_fields, ['images'])
        self.assertEqual(group.source_owned_fields, ['bedrooms', 'images'])

        invalid = self.client.post(url, {
            'vue': '1', 'name': 'Ignored', 'is_active': 'on',
            'protected_fields': ['unknown_field'],
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertIn('protected_fields', invalid.context['group_detail_data']['errors'])
        group.refresh_from_db()
        self.assertEqual(group.name, 'New name')

        other = ArealistingListingGroup.objects.create(project=project, name='Existing name')
        duplicate = self.client.post(url, {'vue': '1', 'name': other.name})
        self.assertEqual(duplicate.status_code, 200)
        self.assertIn('name', duplicate.context['group_detail_data']['errors'])

        legacy = self.client.get(url)
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistinglistinggroup/change_form.html')

        with override_settings(AREALISTING_VUE_ENABLED=True):
            enabled = self.client.get(url)
            self.assertTemplateUsed(enabled, 'admin/arealisting/group_detail_vue.html')
            saved_without_preview = self.client.post(url, {
                'name': 'Enabled name', 'is_active': 'on',
                'protected_fields': ['bedrooms'],
            })
            self.assertEqual(saved_without_preview['Location'], url)
            group.refresh_from_db()
            self.assertEqual(group.name, 'Enabled name')
            self.assertTrue(group.is_active)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_group_detail_is_read_only_for_viewer(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-group-detail-view', name_en='View project')
        group = ArealistingListingGroup.objects.create(project=project, name='View group')
        viewer = User.objects.create_user('vue-group-detail-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistinglistinggroup'))
        self.client.force_login(viewer)
        url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        response = self.client.get(url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['group_detail_data']['can_change'])
        blocked = self.client.post(url, {'vue': '1', 'name': 'Changed'})
        self.assertEqual(blocked.status_code, 403)
        group.refresh_from_db()
        self.assertEqual(group.name, 'View group')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_sync_run_history_filters_and_shows_summary(self, _available):
        run = ArealistingSyncRun.objects.create(
            mode=ArealistingSyncRun.Mode.FULL, status=ArealistingSyncRun.Status.FAILED,
            resources=['projects', 'units'], project_ids=['project-42'],
            summary={'projects': {'seen': 4, 'created': 1, 'errors': 0},
                     'units': {'seen': 12, 'updated': 5, 'errors': 1},
                     'property_updates': [{'property_id': 1}]},
            error='API не ответил',
        )
        ArealistingSyncRun.objects.create(
            mode=ArealistingSyncRun.Mode.INCREMENTAL, status=ArealistingSyncRun.Status.SUCCESS,
        )
        url = reverse('admin:arealisting_arealistingsyncrun_changelist')
        response = self.client.get(url, {'vue': '1', 'status': 'FAILED', 'q': str(run.pk)})
        self.assertTemplateUsed(response, 'admin/arealisting/sync_run_list_vue.html')
        data = response.context['sync_run_list_data']
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['runs'][0]['id'], run.pk)
        self.assertEqual(data['runs'][0]['resources'], ['Комплексы', 'Предложения'])
        self.assertIn('vue=1', data['runs'][0]['url'])
        self.assertEqual(next(item['count'] for item in data['statuses'] if item['value'] == 'FAILED'), 1)

        detail_url = reverse('admin:arealisting_arealistingsyncrun_change', args=[run.pk])
        detail = self.client.get(detail_url, {'vue': '1'})
        self.assertTemplateUsed(detail, 'admin/arealisting/sync_run_detail_vue.html')
        detail_data = detail.context['sync_run_detail_data']
        self.assertEqual(detail_data['resources'][0]['created'], 1)
        self.assertEqual(detail_data['resources'][1]['errors'], 1)
        self.assertEqual(detail_data['property_update_count'], 1)
        self.assertEqual(detail_data['error'], 'API не ответил')
        detail_from_list = self.client.get(data['runs'][0]['url'])
        self.assertIn('status=FAILED', detail_from_list.context['sync_run_detail_data']['back_url'])

        legacy = self.client.get(url)
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingsyncrun/change_list.html')
        self.assertContains(legacy, 'Открыть новую историю обновлений')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_sync_run_history_respects_view_permission(self, _available):
        run = ArealistingSyncRun.objects.create(mode=ArealistingSyncRun.Mode.TARGETED)
        viewer = User.objects.create_user('vue-run-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingsyncrun'))
        self.client.force_login(viewer)
        detail_url = reverse('admin:arealisting_arealistingsyncrun_change', args=[run.pk])
        response = self.client.get(detail_url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sync_run_detail_data']['status'], 'RUNNING')
        self.assertEqual(self.client.post(detail_url + '?vue=1', {}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_location_mapping_filters_and_saves_valid_mapping(self, _available):
        district = District.objects.create(name='Bang Tao', slug='vue-bang-tao')
        location = Location.objects.create(name='Laguna', slug='vue-laguna', district=district)
        mapping = ArealistingLocationMapping.objects.create(
            external_id='vue-location-1', source_name='Laguna from source', source_type='locality',
        )
        ArealistingLocationMapping.objects.create(
            external_id='vue-location-2', source_name='Confirmed source', is_confirmed=True,
        )
        list_url = reverse('admin:arealisting_arealistinglocationmapping_changelist')
        response = self.client.get(list_url, {'vue': '1', 'is_confirmed__exact': '0'})
        self.assertTemplateUsed(response, 'admin/arealisting/location_mapping_list_vue.html')
        data = response.context['location_mapping_list_data']
        self.assertEqual(data['counts']['pending'], 1)
        self.assertEqual(data['counts']['confirmed'], 1)
        self.assertEqual(data['result_count'], 1)
        self.assertIn('vue=1', data['mappings'][0]['url'])

        detail_url = reverse('admin:arealisting_arealistinglocationmapping_change', args=[mapping.pk])
        detail = self.client.get(data['mappings'][0]['url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/location_mapping_detail_vue.html')
        self.assertIn('is_confirmed__exact=0', detail.context['location_mapping_detail_data']['back_url'])

        invalid = self.client.post(detail_url, {
            'vue': '1', 'mapping_mode': 'LOCATION', 'is_confirmed': 'on',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertIn('location', invalid.context['location_mapping_detail_data']['errors'])
        mapping.refresh_from_db()
        self.assertEqual(mapping.mapping_mode, ArealistingLocationMapping.MappingMode.UNMAPPED)

        saved = self.client.post(detail_url, {
            'vue': '1', 'mapping_mode': 'LOCATION', 'location': str(location.pk),
            'is_confirmed': 'on', 'return_confirmed': '0', 'return_deleted': '0',
        })
        self.assertEqual(saved.status_code, 302)
        self.assertIn('vue=1', saved['Location'])
        mapping.refresh_from_db()
        self.assertEqual(mapping.location_id, location.pk)
        self.assertEqual(mapping.district_id, district.pk)
        self.assertTrue(mapping.is_confirmed)

        ignored = self.client.post(detail_url, {'vue': '1', 'mapping_mode': 'IGNORE'})
        self.assertEqual(ignored.status_code, 302)
        mapping.refresh_from_db()
        self.assertIsNone(mapping.location_id)
        self.assertIsNone(mapping.district_id)
        self.assertFalse(mapping.is_confirmed)

        legacy = self.client.get(list_url)
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistinglocationmapping/change_list.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=True)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_location_mappings_are_created_by_sync_only(self, _available):
        add_url = reverse('admin:arealisting_arealistinglocationmapping_add')
        self.assertEqual(self.client.get(add_url).status_code, 403)
        self.assertEqual(self.client.post(add_url, {
            'external_id': 'manual-source', 'source_name': 'Manual', 'mapping_mode': 'IGNORE',
        }).status_code, 403)
        self.assertFalse(ArealistingLocationMapping.objects.filter(external_id='manual-source').exists())
        list_url = reverse('admin:arealisting_arealistinglocationmapping_changelist')
        response = self.client.get(list_url)
        self.assertTemplateUsed(response, 'admin/arealisting/location_mapping_list_vue.html')
        self.assertEqual(response.context['location_mapping_list_data']['sync_overview_url'],
                         reverse('admin:arealisting_arealistingproject_changelist'))

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_location_mapping_is_read_only_for_viewer(self, _available):
        mapping = ArealistingLocationMapping.objects.create(
            external_id='vue-location-viewer', source_name='Source location',
        )
        viewer = User.objects.create_user('vue-location-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistinglocationmapping'))
        self.client.force_login(viewer)
        url = reverse('admin:arealisting_arealistinglocationmapping_change', args=[mapping.pk])
        response = self.client.get(url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['location_mapping_detail_data']['can_change'])
        self.assertEqual(self.client.post(url, {'vue': '1', 'mapping_mode': 'IGNORE'}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_property_change_history_filters_card_and_shows_diff(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-history-project', name_en='History project')
        property_type = PropertyType.objects.create(name='History type')
        district = District.objects.create(name='History district', slug='vue-history-district')
        prop = Property.objects.create(title='History card', slug='vue-history-card',
                                       property_type=property_type, district=district)
        other = Property.objects.create(title='Other card', slug='vue-history-other',
                                        property_type=property_type, district=district)
        group = ArealistingListingGroup.objects.create(project=project, property=prop, name='History group')
        run = ArealistingSyncRun.objects.create(mode=ArealistingSyncRun.Mode.FULL)
        change = ArealistingPropertyChange.objects.create(
            property=prop, project=project, kind=ArealistingPropertyChange.Kind.FIELDS,
            sync_run=run, details={'changed_fields': [{'field': 'bedrooms', 'before': 2, 'after': 3}]},
        )
        ArealistingPropertyChange.objects.create(
            property=other, project=project, kind=ArealistingPropertyChange.Kind.PRICE,
        )
        url = reverse('admin:arealisting_arealistingpropertychange_changelist')
        response = self.client.get(url, {'vue': '1', 'card': str(prop.pk)})
        self.assertTemplateUsed(response, 'admin/arealisting/property_change_list_vue.html')
        data = response.context['property_change_list_data']
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['changes'][0]['id'], change.pk)
        self.assertIn('Спальни', data['changes'][0]['summary'])
        self.assertIn('vue=1', data['changes'][0]['url'])

        detail = self.client.get(data['changes'][0]['url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/property_change_detail_vue.html')
        detail_data = detail.context['property_change_detail_data']
        self.assertEqual(detail_data['rows'][0], {'label': 'Спальни', 'before': '2', 'after': '3'})
        self.assertIn(f'card={prop.pk}', detail_data['back_url'])
        self.assertIn('vue=1', detail_data['sync_run_url'])

        group_url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        group_page = self.client.get(group_url, {'vue': '1'})
        self.assertIn('vue=1', group_page.context['group_detail_data']['history_url'])

        legacy = self.client.get(url, {'card': str(prop.pk)})
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingpropertychange/change_list.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_property_change_history_respects_view_permission(self, _available):
        property_type = PropertyType.objects.create(name='History viewer type')
        district = District.objects.create(name='History viewer district', slug='vue-history-viewer-district')
        prop = Property.objects.create(title='Viewer history card', slug='vue-viewer-history-card',
                                       property_type=property_type, district=district)
        change = ArealistingPropertyChange.objects.create(property=prop, kind=ArealistingPropertyChange.Kind.PRICE)
        viewer = User.objects.create_user('vue-history-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingpropertychange'))
        self.client.force_login(viewer)
        url = reverse('admin:arealisting_arealistingpropertychange_change', args=[change.pk])
        response = self.client.get(url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['property_change_detail_data']['property_url'], '')
        self.assertEqual(self.client.post(url + '?vue=1', {}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_unit_list_and_detail_save_group_settings(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-unit-project', name_en='Unit project')
        other_project = ArealistingProject.objects.create(external_id='vue-unit-other', name_en='Other project')
        group = ArealistingListingGroup.objects.create(project=project, name='Linked group')
        replacement_group = ArealistingListingGroup.objects.create(project=project, name='Replacement group')
        other_group = ArealistingListingGroup.objects.create(project=other_project, name='Wrong group')
        unit = ArealistingUnit.objects.create(
            external_id='vue-unit-1', project=project, unit_number='A101',
            availability_status=ArealistingUnit.AvailabilityStatus.AVAILABLE,
            price=Decimal('1200000'), currency='THB', bedrooms=2,
        )
        ArealistingUnit.objects.create(
            external_id='vue-unit-2', project=project, unit_number='A102',
            availability_status=ArealistingUnit.AvailabilityStatus.SOLD,
        )
        list_url = reverse('admin:arealisting_arealistingunit_changelist')
        response = self.client.get(list_url, {'vue': '1', 'availability_status__exact': 'AVAILABLE'})
        self.assertTemplateUsed(response, 'admin/arealisting/unit_list_vue.html')
        data = response.context['unit_list_data']
        self.assertEqual(data['counts']['all'], 2)
        self.assertEqual(data['counts']['available'], 1)
        self.assertEqual(data['result_count'], 1)
        self.assertIn('vue=1', data['units'][0]['url'])

        detail = self.client.get(data['units'][0]['url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/unit_detail_vue.html')
        detail_data = detail.context['unit_detail_data']
        self.assertEqual(detail_data['number'], 'A101')
        self.assertEqual(detail_data['source_fields'][0]['value'], 2)
        self.assertIn('availability_status__exact=AVAILABLE', detail_data['back_url'])
        self.assertEqual({row['id'] for row in detail_data['group_choices']},
                         {str(group.pk), str(replacement_group.pk)})

        detail_url = reverse('admin:arealisting_arealistingunit_change', args=[unit.pk])
        invalid = self.client.post(detail_url, {
            'vue': '1', 'listing_group': str(other_group.pk), 'sync_enabled': 'on',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertIn('listing_group', invalid.context['unit_detail_data']['errors'])
        unit.refresh_from_db()
        self.assertIsNone(unit.listing_group_id)

        saved = self.client.post(detail_url, {
            'vue': '1', 'listing_group': str(group.pk),
            'return_status': 'AVAILABLE', 'return_project': str(project.pk),
        })
        self.assertEqual(saved.status_code, 302)
        self.assertIn('vue=1', saved['Location'])
        unit.refresh_from_db()
        group.refresh_from_db()
        self.assertEqual(unit.listing_group_id, group.pk)
        self.assertFalse(unit.sync_enabled)
        self.assertEqual(group.available_units_count, 1)

        moved = self.client.post(detail_url, {
            'vue': '1', 'listing_group': str(replacement_group.pk),
        })
        self.assertEqual(moved.status_code, 302)
        group.refresh_from_db()
        replacement_group.refresh_from_db()
        self.assertEqual(group.available_units_count, 0)
        self.assertEqual(replacement_group.available_units_count, 1)

        legacy = self.client.get(list_url)
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingunit/change_list.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_unit_detail_is_read_only_for_viewer(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-unit-viewer', name_en='Unit viewer')
        unit = ArealistingUnit.objects.create(external_id='vue-unit-view', project=project)
        viewer = User.objects.create_user('vue-unit-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingunit'))
        self.client.force_login(viewer)
        url = reverse('admin:arealisting_arealistingunit_change', args=[unit.pk])
        response = self.client.get(url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['unit_detail_data']['can_change'])
        self.assertEqual(self.client.post(url, {'vue': '1', 'sync_enabled': 'on'}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_skipped_unit_list_detail_and_restore(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-skipped-project', name_en='Skipped project')
        unit = ArealistingUnit.objects.create(external_id='vue-skipped-unit', project=project, unit_number='B11')
        skipped = ArealistingSkippedUnit.objects.create(unit=unit, skipped_by=self.user, reason='Не подходит')
        other = ArealistingUnit.objects.create(external_id='vue-skipped-old', project=project,
                                               unit_number='Old', is_deleted=True)
        old_skipped = ArealistingSkippedUnit.objects.create(unit=other, reason='Устарело')
        list_url = reverse('admin:arealisting_arealistingskippedunit_changelist')
        response = self.client.get(list_url, {'vue': '1', 'project': str(project.pk), 'q': 'B11'})
        self.assertTemplateUsed(response, 'admin/arealisting/skipped_unit_list_vue.html')
        data = response.context['skipped_unit_list_data']
        self.assertEqual(data['result_count'], 1)
        self.assertTrue(data['rows'][0]['can_restore'])
        self.assertIn('vue=1', data['rows'][0]['detail_url'])

        detail = self.client.get(data['rows'][0]['detail_url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/skipped_unit_detail_vue.html')
        detail_data = detail.context['skipped_unit_detail_data']
        self.assertEqual(detail_data['reason'], 'Не подходит')
        self.assertIn(f'project={project.pk}', detail_data['back_url'])
        self.assertIn('vue=1', detail_data['matching_url'])
        unit_url = reverse('admin:arealisting_arealistingunit_change', args=[unit.pk])
        unit_detail = self.client.get(unit_url, {'vue': '1'})
        self.assertTrue(unit_detail.context['unit_detail_data']['is_skipped'])
        self.assertIn('vue=1', unit_detail.context['unit_detail_data']['skipped_url'])

        old_detail_url = reverse('admin:arealisting_arealistingskippedunit_change', args=[old_skipped.pk])
        old_detail = self.client.get(old_detail_url, {'vue': '1'})
        self.assertFalse(old_detail.context['skipped_unit_detail_data']['can_restore'])
        old_restore_url = reverse('admin:arealisting_arealistingskippedunit_restore', args=[old_skipped.pk])
        self.assertEqual(self.client.post(old_restore_url, {'vue': '1'}).status_code, 403)

        restore_url = reverse('admin:arealisting_arealistingskippedunit_restore', args=[skipped.pk])
        restored = self.client.post(restore_url, {
            'vue': '1', 'return_project': str(project.pk), 'return_q': 'B11',
        })
        self.assertEqual(restored.status_code, 302)
        self.assertIn('vue=1', restored['Location'])
        self.assertIn(f'project={project.pk}', restored['Location'])
        self.assertFalse(ArealistingSkippedUnit.objects.filter(pk=skipped.pk).exists())
        self.assertTrue(ArealistingUnit.objects.filter(pk=unit.pk).exists())

        legacy = self.client.get(list_url)
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingskippedunit/change_list.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_skipped_unit_restore_requires_matching_permissions(self, _available):
        project = ArealistingProject.objects.create(external_id='vue-skipped-viewer', name_en='Viewer project')
        unit = ArealistingUnit.objects.create(external_id='vue-skipped-view', project=project)
        skipped = ArealistingSkippedUnit.objects.create(unit=unit)
        viewer = User.objects.create_user('vue-skipped-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingskippedunit'))
        self.client.force_login(viewer)
        detail_url = reverse('admin:arealisting_arealistingskippedunit_change', args=[skipped.pk])
        response = self.client.get(detail_url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['skipped_unit_detail_data']['can_restore'])
        restore_url = reverse('admin:arealisting_arealistingskippedunit_restore', args=[skipped.pk])
        self.assertEqual(self.client.post(restore_url, {'vue': '1'}).status_code, 403)
        self.assertTrue(ArealistingSkippedUnit.objects.filter(pk=skipped.pk).exists())

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_payment_plan_list_and_detail(self, _available):
        project = ArealistingProject.objects.create(external_id='payment-project', name_en='Payment project')
        plan = ArealistingPaymentPlan.objects.create(
            external_id='payment-plan', project=project, name='Installments',
            description='Three payments', items=[
                {'stage': 'Reservation', 'type': 'FIXED_AMOUNT', 'value': 200000,
                 'currency': 'THB', 'due': 'On reservation', 'custom_note': 'Deposit'},
            ],
        )
        ArealistingPaymentPlan.objects.create(
            external_id='payment-old', project=project, name='Old plan', is_deleted=True,
        )
        list_url = reverse('admin:arealisting_arealistingpaymentplan_changelist')
        response = self.client.get(list_url, {'vue': '1', 'project': str(project.pk), 'q': 'Installments'})
        self.assertTemplateUsed(response, 'admin/arealisting/payment_plan_list_vue.html')
        data = response.context['payment_plan_list_data']
        self.assertEqual(data['result_count'], 1)
        self.assertEqual(data['counts'], {'all': 1, 'active': 1, 'deleted': 0})
        self.assertEqual(data['plans'][0]['item_count'], 1)
        self.assertIn('vue=1', data['plans'][0]['url'])

        detail = self.client.get(data['plans'][0]['url'])
        self.assertTemplateUsed(detail, 'admin/arealisting/payment_plan_detail_vue.html')
        detail_data = detail.context['payment_plan_detail_data']
        self.assertEqual(detail_data['id'], plan.pk)
        self.assertEqual(detail_data['items'][0]['title'], 'Reservation')
        self.assertIn({'label': 'Когда оплачивается', 'value': 'On reservation'},
                      detail_data['items'][0]['fields'])
        self.assertIn({'label': 'custom_note', 'value': 'Deposit'},
                      detail_data['items'][0]['fields'])
        self.assertIn(f'project={project.pk}', detail_data['back_url'])
        self.assertIn('q=Installments', detail_data['back_url'])
        self.assertIn('vue=1', detail_data['back_url'])
        self.assertEqual(self.client.post(data['plans'][0]['url'], {'name': 'Changed'}).status_code, 403)
        plan.refresh_from_db()
        self.assertEqual(plan.name, 'Installments')

        deleted = self.client.get(list_url, {'vue': '1', 'is_deleted__exact': '1'})
        self.assertEqual(deleted.context['payment_plan_list_data']['result_count'], 1)
        legacy = self.client.get(list_url)
        self.assertTemplateUsed(legacy, 'admin/arealisting/arealistingpaymentplan/change_list.html')

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    @patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True)
    def test_vue_payment_plan_respects_view_permission(self, _available):
        project = ArealistingProject.objects.create(external_id='payment-viewer', name_en='Viewer project')
        plan = ArealistingPaymentPlan.objects.create(external_id='payment-view-plan', project=project)
        viewer = User.objects.create_user('payment-viewer', password='test-password', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_arealistingpaymentplan'))
        self.client.force_login(viewer)
        list_url = reverse('admin:arealisting_arealistingpaymentplan_changelist')
        detail_url = reverse('admin:arealisting_arealistingpaymentplan_change', args=[plan.pk])
        self.assertEqual(self.client.get(list_url, {'vue': '1'}).status_code, 200)
        response = self.client.get(detail_url, {'vue': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['payment_plan_detail_data']['project_url'], '')
        self.assertEqual(self.client.post(detail_url, {'vue': '1', 'name': 'Changed'}).status_code, 403)

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    def test_vue_bulk_media_preview_handles_stale_selection_and_queued_jobs(self):
        project = ArealistingProject.objects.create(external_id='vue-bulk', name_en='Vue bulk')
        property_type = PropertyType.objects.create(name='Vue bulk condo')
        district = District.objects.create(name='Vue bulk district', slug='vue-bulk-district')
        groups = []
        for index in (1, 2):
            property_obj = Property.objects.create(
                title=f'Vue bulk card {index}', slug=f'vue-bulk-card-{index}',
                property_type=property_type, district=district, is_active=False,
            )
            groups.append(ArealistingListingGroup.objects.create(
                project=project, property=property_obj, name=f'Vue bulk group {index}',
            ))
        ArealistingAsset.objects.create(
            source_key='vue-bulk-asset', project=project,
            source_url='https://cdn.example.test/vue-bulk.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        url = reverse('admin:arealisting_arealistinglistinggroup_changelist')
        selection = {'action': 'import_media', '_selected_action': [str(group.pk) for group in groups], 'vue': '1'}
        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True):
            preview = self.client.post(url, selection)
            stale = self.client.post(url, {
                **selection, 'confirm_media_import': '1',
                **{f'fingerprint_{group.pk}': 'stale' for group in groups},
            })
        self.assertTemplateUsed(preview, 'admin/arealisting/media_preview_bulk_vue.html')
        self.assertEqual(len(preview.context['bulk_media_preview_data']['groups']), 2)
        self.assertTemplateUsed(stale, 'admin/arealisting/media_preview_bulk_vue.html')
        self.assertContains(stale, 'Состав фото изменился')
        self.assertFalse(ArealistingMediaJob.objects.exists())

        fingerprints = {f'fingerprint_{item["group"].pk}': item['fingerprint']
                        for item in preview.context['previews']}
        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True), \
                patch('apps.arealisting.services.media_jobs.start_media_worker') as worker:
            queued = self.client.post(url, {**selection, **fingerprints, 'confirm_media_import': '1'})
        self.assertTemplateUsed(queued, 'admin/arealisting/media_jobs_queued_vue.html')
        self.assertEqual(len(queued.context['queued_media_data']['jobs']), 2)
        self.assertTrue(all(item['url'].endswith('?vue=1') for item in queued.context['queued_media_data']['jobs']))
        self.assertEqual(ArealistingMediaJob.objects.count(), 2)
        worker.assert_called_once()

    def test_failed_media_job_shows_error_and_retries_only_failed_asset(self):
        project = ArealistingProject.objects.create(external_id='job-retry-admin', name_en='Job retry')
        property_type = PropertyType.objects.create(name='Job retry condo')
        district = District.objects.create(name='Job retry district', slug='job-retry-district')
        property_obj = Property.objects.create(
            title='Job retry card', slug='job-retry-card',
            property_type=property_type, district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(
            project=project, property=property_obj, name='Job retry group',
        )
        asset = ArealistingAsset.objects.create(
            source_key='job-retry-asset', project=project,
            source_url='https://cdn.example.test/retry.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        previous = ArealistingMediaJob.objects.create(
            group=group, status=ArealistingMediaJob.Status.PARTIAL,
            selected_asset_ids=[asset.pk], preview_fingerprint='0' * 64,
            total=1, processed=1, totals={'errors': 1},
            results=[{'asset_id': asset.pk, 'title': str(asset),
                      'source_url': asset.source_url, 'role': 'GALLERY',
                      'status': 'error', 'error': 'Недоступно', 'image_id': None}],
        )
        job_url = reverse('admin:arealisting_arealistinglistinggroup_media_job',
                          args=[group.pk, previous.pk])
        response = self.client.get(job_url)
        self.assertContains(response, 'Ошибка загрузки')
        self.assertContains(response, 'Повторить только фото с ошибками')

        retry_url = reverse('admin:arealisting_arealistinglistinggroup_retry_media_job',
                            args=[group.pk, previous.pk])
        with patch('apps.arealisting.services.media_jobs.start_media_worker') as worker:
            response = self.client.post(retry_url)
        self.assertEqual(response.status_code, 302)
        retry = ArealistingMediaJob.objects.exclude(pk=previous.pk).get(group=group)
        self.assertEqual(retry.selected_asset_ids, [asset.pk])
        self.assertFalse(retry.prune_missing)
        worker.assert_called_once()

    @override_settings(DEBUG=True, AREALISTING_VUE_ENABLED=False)
    def test_vue_media_job_exposes_progress_and_keeps_retry_navigation(self):
        project = ArealistingProject.objects.create(external_id='vue-job', name_en='Vue job')
        property_type = PropertyType.objects.create(name='Vue job condo')
        district = District.objects.create(name='Vue job district', slug='vue-job-district')
        property_obj = Property.objects.create(
            title='Vue job card', slug='vue-job-card', property_type=property_type,
            district=district, is_active=False,
        )
        group = ArealistingListingGroup.objects.create(project=project, property=property_obj, name='Vue job group')
        asset = ArealistingAsset.objects.create(
            source_key='vue-job-asset', project=project,
            source_url='https://cdn.example.test/vue-job.jpg',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        job = ArealistingMediaJob.objects.create(
            group=group, status=ArealistingMediaJob.Status.PENDING,
            selected_asset_ids=[asset.pk], preview_fingerprint='0' * 64,
            total=1, processed=0,
        )
        job_url = reverse('admin:arealisting_arealistinglistinggroup_media_job', args=[group.pk, job.pk])
        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True):
            page = self.client.get(job_url + '?vue=1')
        self.assertTemplateUsed(page, 'admin/arealisting/media_job_vue.html')
        self.assertEqual(page.context['media_job_data']['status'], 'PENDING')
        self.assertEqual(page.context['media_job_data']['poll_url'], job_url + '?format=json')
        progress = self.client.get(job_url + '?format=json')
        self.assertEqual(progress.json()['processed'], 0)
        self.assertIn('no-store', progress['Cache-Control'])

        job.status = ArealistingMediaJob.Status.PARTIAL
        job.processed = 1
        job.totals = {'errors': 1}
        job.results = [{'asset_id': asset.pk, 'title': str(asset),
                        'source_url': asset.source_url, 'role': 'GALLERY',
                        'status': 'error', 'error': 'Недоступно'}]
        job.save(update_fields=['status', 'processed', 'totals', 'results'])
        result = self.client.get(job_url + '?format=json').json()
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertEqual(result['results'][0]['error'], 'Недоступно')
        self.assertTrue(result['can_retry'])
        retry_url = reverse('admin:arealisting_arealistinglistinggroup_retry_media_job', args=[group.pk, job.pk])
        with patch('apps.arealisting.services.media_jobs.start_media_worker'):
            retried = self.client.post(retry_url + '?vue=1')
        self.assertEqual(retried.status_code, 302)
        self.assertTrue(retried.url.endswith('?vue=1'))
        self.assertEqual(ArealistingMediaJob.objects.exclude(pk=job.pk).get(group=group).selected_asset_ids, [asset.pk])

    def test_workspace_warns_about_latest_failed_sync_attempt(self):
        successful_run = ArealistingSyncRun.objects.create(
            mode=ArealistingSyncRun.Mode.FULL,
            status=ArealistingSyncRun.Status.SUCCESS,
            resources=['projects'],
            summary={'projects': {'created': 3}},
            finished_at=timezone.now(),
        )
        ArealistingSyncRun.objects.create(
            mode=ArealistingSyncRun.Mode.INCREMENTAL,
            status=ArealistingSyncRun.Status.FAILED,
            resources=['units'],
            error='Partner API is temporarily unavailable.',
            finished_at=timezone.now(),
        )

        response = self.client.get(
            reverse('admin:arealisting_arealistingproject_changelist')
        )

        self.assertEqual(response.context['latest_successful_run'], successful_run)
        self.assertEqual(
            response.context['latest_sync_error'],
            'Partner API is temporarily unavailable.',
        )
        self.assertContains(response, 'Последняя попытка завершилась ошибкой')
        self.assertContains(response, 'Partner API is temporarily unavailable.')

    def test_workspace_reports_running_sync(self):
        ArealistingSyncRun.objects.create(
            mode=ArealistingSyncRun.Mode.FULL,
            status=ArealistingSyncRun.Status.RUNNING,
            resources=['projects'],
        )

        response = self.client.get(
            reverse('admin:arealisting_arealistingproject_changelist')
        )

        self.assertTrue(response.context['sync_running'])
        self.assertContains(response, 'Синхронизация выполняется')

    @override_settings(DEBUG=True)
    def test_matching_displays_saved_price_report(self):
        project = ArealistingProject.objects.create(external_id='report', name_en='Report complex')
        ArealistingSyncRun.objects.create(mode='full', status='success', resources=['units'],
            summary={'price_updates': [{'project_id': project.pk, 'property_id': 123,
                'title': 'Проверенная квартира', 'checked_at': timezone.now().isoformat(),
                'status': 'skipped', 'reason': 'нет доступных выбранных предложений',
                'before': {'price_sale_thb': '1000000.00'}, 'after': {'price_sale_thb': '1000000.00'}}]})
        response = self.client.get(reverse('admin:arealisting_matching'), {'project': project.pk})
        self.assertContains(response, 'Результат последнего обновления цен')
        self.assertContains(response, 'Проверенная квартира')
        self.assertContains(response, 'нет доступных выбранных предложений')

        with patch('apps.arealisting.templatetags.arealisting_vite.matching_vue_available', return_value=True):
            vue = self.client.get(reverse('admin:arealisting_matching'), {
                'project': project.pk, 'vue': '1',
            })
        self.assertContains(vue, '<details class="price-report-panel">')
        self.assertContains(vue, 'Карточек: 1')
        self.assertContains(vue, 'Проверенная квартира')
        self.assertLess(vue.content.index(b'price-report-panel'),
                        vue.content.index(b'arealisting-vue-root'))
