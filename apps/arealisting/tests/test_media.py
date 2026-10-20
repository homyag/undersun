from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from apps.arealisting.models import (
    ArealistingAsset,
    ArealistingListingGroup,
    ArealistingMediaJob,
    ArealistingProject,
    ArealistingPropertyAsset,
    ArealistingUnit,
)
from apps.arealisting.services.media import preview_group_media, sync_group_media
from apps.arealisting.services.media_jobs import process_media_job, queue_media_job
from apps.locations.models import District
from apps.properties.models import Property, PropertyType


def image_bytes(image_format='PNG'):
    buffer = BytesIO()
    Image.new('RGB', (32, 24), '#2563eb').save(buffer, format=image_format)
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, url, body, content_type='image/png'):
        self.url = url
        self.body = body
        self.headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(body)),
        }

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        return None


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses[url]


class ArealistingMediaTests(TestCase):
    def setUp(self):
        self.temporary_media = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temporary_media.name,
            AREALISTING_MEDIA_HOSTS=['cdn.example.test'],
            AREALISTING_MEDIA_MAX_BYTES=1024 * 1024,
        )
        self.settings_override.enable()
        project_type = PropertyType.objects.create(name='condo')
        district = District.objects.create(name='Media district', slug='media-district')
        self.project = ArealistingProject.objects.create(
            external_id='media-project',
            name_en='Media project',
        )
        self.property = Property.objects.create(
            title='Media card',
            slug='media-card',
            property_type=project_type,
            district=district,
            is_active=False,
        )
        self.group = ArealistingListingGroup.objects.create(
            project=self.project,
            property=self.property,
            name='Media group',
            source_owned_fields=['images', 'floorplans'],
        )
        self.unit = ArealistingUnit.objects.create(
            external_id='media-unit',
            project=self.project,
            listing_group=self.group,
        )

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_media.cleanup()

    def test_imports_gallery_and_floor_plan_separately_and_is_idempotent(self):
        gallery_url = 'https://cdn.example.test/project-photo.png'
        floor_plan_url = 'https://cdn.example.test/unit-floor-plan.png'
        ArealistingAsset.objects.create(
            source_key='a' * 64,
            project=self.project,
            source_url=gallery_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        ArealistingAsset.objects.create(
            source_key='b' * 64,
            project=self.project,
            unit=self.unit,
            source_url=floor_plan_url,
            asset_type=ArealistingAsset.AssetType.UNIT_GALLERY,
        )
        session = FakeSession({
            gallery_url: FakeResponse(gallery_url, image_bytes()),
            floor_plan_url: FakeResponse(floor_plan_url, image_bytes()),
        })

        first = sync_group_media(self.group.pk, session=session)
        second = sync_group_media(self.group.pk, session=session)

        self.assertEqual(first['created'], 2)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['updated'], 2)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(self.property.images.count(), 2)
        self.assertTrue(self.property.images.get(image_type='main').is_main)
        floor_plan = self.property.images.get(image_type='floorplan')
        self.assertEqual(floor_plan.frame_type, 'floorplan')
        self.assertEqual(
            floor_plan.arealisting_property_asset.role,
            ArealistingPropertyAsset.Role.FLOOR_PLAN,
        )

    def test_imports_only_explicitly_selected_assets(self):
        selected_url = 'https://cdn.example.test/selected.png'
        unselected_url = 'https://cdn.example.test/unselected.png'
        selected = ArealistingAsset.objects.create(
            source_key='selected-media-asset',
            project=self.project,
            source_url=selected_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        unselected = ArealistingAsset.objects.create(
            source_key='unselected-media-asset',
            project=self.project,
            source_url=unselected_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        session = FakeSession({
            selected_url: FakeResponse(selected_url, image_bytes()),
        })

        report = sync_group_media(
            self.group.pk,
            session=session,
            selected_asset_ids=[selected.pk],
        )

        self.assertEqual(report['created'], 1)
        self.assertEqual([call[0] for call in session.calls], [selected_url])
        self.assertTrue(
            ArealistingPropertyAsset.objects.filter(
                listing_group=self.group,
                asset=selected,
            ).exists()
        )
        self.assertFalse(
            ArealistingPropertyAsset.objects.filter(
                listing_group=self.group,
                asset=unselected,
            ).exists()
        )

    def test_pdf_floor_plan_stays_source_only_without_download_error(self):
        url = 'https://cdn.example.test/floor-plan.pdf'
        asset = ArealistingAsset.objects.create(
            source_key='c' * 64,
            project=self.project,
            source_url=url,
            asset_type=ArealistingAsset.AssetType.FLOOR_PLAN,
        )
        session = FakeSession({
            url: FakeResponse(url, b'%PDF-1.7', content_type='application/pdf'),
        })

        report = sync_group_media(self.group.pk, session=session)

        asset.refresh_from_db()
        self.assertEqual(report['errors'], 0)
        self.assertFalse(self.property.images.exists())
        self.assertEqual(asset.last_error, '')
        self.assertEqual(session.calls, [])

    def test_manual_media_lock_skips_download(self):
        self.group.locked_fields = ['images', 'floorplans']
        self.group.save(update_fields=('locked_fields', 'updated_at'))
        url = 'https://cdn.example.test/project-photo.png'
        ArealistingAsset.objects.create(
            source_key='d' * 64,
            project=self.project,
            source_url=url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        session = FakeSession({url: FakeResponse(url, image_bytes())})

        report = sync_group_media(self.group.pk, session=session)

        self.assertEqual(report['skipped'], 1)
        self.assertEqual(session.calls, [])
        self.assertFalse(self.property.images.exists())

    def test_removed_source_asset_deletes_only_imported_image(self):
        url = 'https://cdn.example.test/project-photo.png'
        asset = ArealistingAsset.objects.create(
            source_key='e' * 64,
            project=self.project,
            source_url=url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        session = FakeSession({url: FakeResponse(url, image_bytes())})
        sync_group_media(self.group.pk, session=session)
        imported_image = self.property.images.get(
            arealisting_property_asset__isnull=False
        )
        manual_image = self.property.images.create(
            image=ContentFile(image_bytes(), name='manual.png'),
            title='Manual image',
            order=50,
        )

        asset.is_active = False
        asset.save(update_fields=('is_active', 'updated_at'))
        preview = preview_group_media(self.group.pk, enable=True)
        self.assertTrue(preview['can_import'])
        self.assertEqual([item['asset'].pk for item in preview['removals']], [asset.pk])
        self.assertEqual([item['asset'].pk for item in preview['missing_removals']], [asset.pk])
        report = sync_group_media(self.group.pk, session=session)

        self.assertEqual(report['deleted'], 1)
        self.assertFalse(self.property.images.filter(pk=imported_image.pk).exists())
        self.assertTrue(self.property.images.filter(pk=manual_image.pk).exists())

    def test_preview_is_read_only_and_shows_add_update_remove_and_main(self):
        old_url = 'https://cdn.example.test/old.png'
        kept_url = 'https://cdn.example.test/kept.png'
        new_url = 'https://cdn.example.test/new.png'
        old = ArealistingAsset.objects.create(
            source_key='preview-old', project=self.project, source_url=old_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        kept = ArealistingAsset.objects.create(
            source_key='preview-kept', project=self.project, source_url=kept_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        session = FakeSession({
            old_url: FakeResponse(old_url, image_bytes()),
            kept_url: FakeResponse(kept_url, image_bytes()),
        })
        sync_group_media(self.group.pk, session=session)
        old_image = ArealistingPropertyAsset.objects.get(asset=old).property_image
        old.is_active = False
        old.save(update_fields=('is_active', 'updated_at'))
        new = ArealistingAsset.objects.create(
            source_key='preview-new', project=self.project, source_url=new_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        before = self.property.images.count()

        preview = preview_group_media(self.group.pk, enable=True)

        self.assertEqual([item['asset'].pk for item in preview['additions']], [new.pk])
        self.assertEqual([item['asset'].pk for item in preview['updates']], [kept.pk])
        self.assertEqual([item['asset'].pk for item in preview['removals']], [old.pk])
        self.assertTrue(preview['main_changes'])
        self.assertTrue(preview['can_import'])
        self.assertEqual(self.property.images.count(), before)
        self.assertTrue(self.property.images.filter(pk=old_image.pk).exists())

    def test_preview_respects_locked_roles(self):
        ArealistingAsset.objects.create(
            source_key='preview-locked', project=self.project,
            source_url='https://cdn.example.test/locked.png',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        self.group.locked_fields = ['images']
        self.group.save(update_fields=('locked_fields', 'updated_at'))

        preview = preview_group_media(self.group.pk, enable=True)

        self.assertEqual(preview['additions'], [])
        self.assertFalse(preview['can_import'])

    def test_unselected_imported_photo_is_removed_after_confirmed_selection(self):
        first_url = 'https://cdn.example.test/selected-first.png'
        second_url = 'https://cdn.example.test/excluded-second.png'
        first = ArealistingAsset.objects.create(
            source_key='selected-first', project=self.project, source_url=first_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        second = ArealistingAsset.objects.create(
            source_key='excluded-second', project=self.project, source_url=second_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        session = FakeSession({
            first_url: FakeResponse(first_url, image_bytes()),
            second_url: FakeResponse(second_url, image_bytes()),
        })
        sync_group_media(self.group.pk, session=session)

        preview = preview_group_media(self.group.pk, enable=True, selected_asset_ids=[first.pk])
        self.assertEqual([item['asset'].pk for item in preview['updates']], [first.pk])
        self.assertEqual([item['asset'].pk for item in preview['removals']], [second.pk])
        self.assertEqual([item['selected'] for item in preview['available']], [True, False])
        self.assertEqual(self.property.images.count(), 2)

        result = sync_group_media(self.group.pk, session=session, selected_asset_ids=[first.pk])
        self.assertEqual(result['deleted'], 1)
        self.assertEqual(self.property.images.count(), 1)
        self.assertTrue(ArealistingPropertyAsset.objects.filter(asset=first).exists())
        self.assertFalse(ArealistingPropertyAsset.objects.filter(asset=second).exists())

        self.group.excluded_media_source_keys = [second.source_key]
        self.group.save(update_fields=('excluded_media_source_keys', 'updated_at'))
        repeated = sync_group_media(self.group.pk, session=session)
        self.assertEqual(repeated['created'], 0)
        self.assertFalse(ArealistingPropertyAsset.objects.filter(asset=second).exists())
        self.assertEqual(preview_group_media(self.group.pk)['selected_ids'], [first.pk])
        self.assertEqual(
            [(item['asset'].pk, item['selected']) for item in preview_group_media(self.group.pk)['available']],
            [(first.pk, True), (second.pk, False)],
        )

    def test_background_job_records_progress_and_result_per_photo(self):
        url = 'https://cdn.example.test/job-photo.png'
        asset = ArealistingAsset.objects.create(
            source_key='job-photo', project=self.project, source_url=url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        job, created = queue_media_job(self.group.pk, selected_asset_ids=[asset.pk])
        self.assertTrue(created)
        self.assertFalse(self.property.images.exists())

        processed = process_media_job(
            job.pk, session=FakeSession({url: FakeResponse(url, image_bytes())}),
        )

        job.refresh_from_db()
        self.assertTrue(processed)
        self.assertEqual(job.status, ArealistingMediaJob.Status.SUCCESS)
        self.assertEqual((job.processed, job.total), (1, 1))
        self.assertEqual(job.results[0]['status'], 'created')
        self.assertEqual(job.results[0]['asset_id'], asset.pk)
        self.assertEqual(job.totals['created'], 1)
        self.assertEqual(self.property.images.count(), 1)
        self.assertFalse(process_media_job(job.pk))

    def test_retry_job_only_processes_failed_photo_without_pruning_gallery(self):
        first_url = 'https://cdn.example.test/retry-first.png'
        failed_url = 'https://cdn.example.test/retry-failed.png'
        first = ArealistingAsset.objects.create(
            source_key='retry-first', project=self.project, source_url=first_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        failed = ArealistingAsset.objects.create(
            source_key='retry-failed', project=self.project, source_url=failed_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        job, _ = queue_media_job(self.group.pk, selected_asset_ids=[first.pk, failed.pk])
        process_media_job(job.pk, session=FakeSession({
            first_url: FakeResponse(first_url, image_bytes()),
            failed_url: FakeResponse(failed_url, b'not an image'),
        }))
        job.refresh_from_db()
        self.assertEqual(job.status, ArealistingMediaJob.Status.PARTIAL)
        self.assertEqual([row['asset_id'] for row in job.results if row['status'] == 'error'], [failed.pk])
        self.assertTrue(ArealistingPropertyAsset.objects.filter(asset=first, property_image__isnull=False).exists())

        retry, created = queue_media_job(
            self.group.pk, selected_asset_ids=[failed.pk], prune_missing=False,
        )
        self.assertTrue(created)
        process_media_job(retry.pk, session=FakeSession({
            failed_url: FakeResponse(failed_url, image_bytes()),
        }))
        retry.refresh_from_db()
        self.assertEqual(retry.status, ArealistingMediaJob.Status.SUCCESS)
        self.assertEqual(retry.totals['deleted'], 0)
        self.assertEqual(self.property.images.count(), 2)

    def test_background_job_stops_if_source_changes_after_queueing(self):
        asset = ArealistingAsset.objects.create(
            source_key='stale-background-photo', project=self.project,
            source_url='https://cdn.example.test/before.png',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        job, _ = queue_media_job(self.group.pk, selected_asset_ids=[asset.pk])
        asset.source_url = 'https://cdn.example.test/after.png'
        asset.save(update_fields=('source_url', 'updated_at'))

        process_media_job(job.pk, session=FakeSession({}))

        job.refresh_from_db()
        self.assertEqual(job.status, ArealistingMediaJob.Status.FAILED)
        self.assertIn('Состав фото изменился', job.error)
        self.assertFalse(self.property.images.exists())

    def test_selected_gallery_photo_becomes_main_after_background_import(self):
        first_url = 'https://cdn.example.test/main-first.png'
        chosen_url = 'https://cdn.example.test/main-chosen.png'
        first = ArealistingAsset.objects.create(
            source_key='main-first', project=self.project, source_url=first_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        chosen = ArealistingAsset.objects.create(
            source_key='main-chosen', project=self.project, source_url=chosen_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        job, _ = queue_media_job(
            self.group.pk, selected_asset_ids=[first.pk, chosen.pk],
            preferred_main_asset_id=chosen.pk,
        )
        process_media_job(job.pk, session=FakeSession({
            first_url: FakeResponse(first_url, image_bytes()),
            chosen_url: FakeResponse(chosen_url, image_bytes()),
        }))
        job.refresh_from_db()
        self.assertEqual(job.status, ArealistingMediaJob.Status.SUCCESS)
        self.assertEqual(job.preferred_main_asset_id, chosen.pk)
        self.assertEqual(self.property.images.get(is_main=True).arealisting_property_asset.asset_id, chosen.pk)

    def test_failed_chosen_photo_keeps_current_main_for_retry(self):
        current_url = 'https://cdn.example.test/main-current.png'
        chosen_url = 'https://cdn.example.test/main-failed.png'
        current = ArealistingAsset.objects.create(
            source_key='main-current', project=self.project, source_url=current_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        chosen = ArealistingAsset.objects.create(
            source_key='main-failed', project=self.project, source_url=chosen_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        sync_group_media(self.group.pk, session=FakeSession({
            current_url: FakeResponse(current_url, image_bytes()),
            chosen_url: FakeResponse(chosen_url, b'invalid image'),
        }), selected_asset_ids=[current.pk])
        self.group.excluded_media_source_keys = [current.source_key]
        self.group.save(update_fields=('excluded_media_source_keys', 'updated_at'))
        job, _ = queue_media_job(
            self.group.pk, selected_asset_ids=[chosen.pk],
            preferred_main_asset_id=chosen.pk,
        )
        process_media_job(job.pk, session=FakeSession({
            chosen_url: FakeResponse(chosen_url, b'invalid image'),
        }))
        job.refresh_from_db()
        self.assertEqual(job.status, ArealistingMediaJob.Status.PARTIAL)
        self.assertEqual(self.property.images.get(is_main=True).arealisting_property_asset.asset_id, current.pk)
        self.assertEqual(job.totals['deleted'], 0)

        retry, _ = queue_media_job(
            self.group.pk, selected_asset_ids=[chosen.pk], prune_missing=False,
            preferred_main_asset_id=chosen.pk,
        )
        process_media_job(retry.pk, session=FakeSession({
            chosen_url: FakeResponse(chosen_url, image_bytes()),
        }))
        retry.refresh_from_db()
        self.assertEqual(retry.totals['deleted'], 1)
        self.assertFalse(ArealistingPropertyAsset.objects.filter(asset=current).exists())
        self.assertEqual(self.property.images.get(is_main=True).arealisting_property_asset.asset_id, chosen.pk)

    def test_main_choice_must_be_selected_gallery_photo(self):
        gallery = ArealistingAsset.objects.create(
            source_key='main-validation', project=self.project,
            source_url='https://cdn.example.test/main-validation.png',
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        with self.assertRaises(ValidationError):
            preview_group_media(self.group.pk, enable=True, selected_asset_ids=[],
                                preferred_main_asset_id=gallery.pk)

    def test_replaced_main_is_removed_only_after_chosen_photo_loads(self):
        old_url = 'https://cdn.example.test/replaced-main.png'
        new_url = 'https://cdn.example.test/new-main.png'
        old = ArealistingAsset.objects.create(
            source_key='replaced-main', project=self.project, source_url=old_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        new = ArealistingAsset.objects.create(
            source_key='new-main', project=self.project, source_url=new_url,
            asset_type=ArealistingAsset.AssetType.PROJECT_GALLERY,
        )
        sync_group_media(self.group.pk, session=FakeSession({
            old_url: FakeResponse(old_url, image_bytes()),
        }), selected_asset_ids=[old.pk])
        job, _ = queue_media_job(self.group.pk, selected_asset_ids=[new.pk],
                                 preferred_main_asset_id=new.pk)
        process_media_job(job.pk, session=FakeSession({
            new_url: FakeResponse(new_url, image_bytes()),
        }))
        job.refresh_from_db()
        self.assertEqual(job.status, ArealistingMediaJob.Status.SUCCESS)
        self.assertEqual((job.processed, job.total), (2, 2))
        self.assertEqual(job.totals['deleted'], 1)
        self.assertFalse(ArealistingPropertyAsset.objects.filter(asset=old).exists())
        self.assertEqual(self.property.images.get(is_main=True).arealisting_property_asset.asset_id, new.pk)
