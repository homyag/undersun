from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal

from apps.arealisting.models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingMediaJob,
    ArealistingLocationMapping,
    ArealistingProject,
    ArealistingPriceReview,
    ArealistingPropertyChange,
    ArealistingSyncRun,
    ArealistingSyncEvent,
    ArealistingUnit,
)
from apps.locations.models import District
from apps.properties.models import Property, PropertyType
from django.utils import timezone


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
        self.assertContains(response, 'Рекомендуется проверить')
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
        self.assertContains(response, f"{reverse('admin:arealisting_unlinked')}?property={unlinked.pk}")
        self.assertContains(response, reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk]))

    def test_sync_event_queue_shows_latest_run_and_full_list(self):
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
        self.assertEqual(full.context['cl'].result_count, 1)
        self.assertContains(full, reverse('admin:arealisting_arealistingsyncevent_change', args=[event.pk]))

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
