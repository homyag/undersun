from unittest.mock import patch

from django.test import TestCase

from apps.arealisting.models import ArealistingSyncJob
from apps.arealisting.services.sync_jobs import process_sync_job


class SyncJobTests(TestCase):
    @patch('apps.arealisting.services.sync_jobs.ArealistingSyncService')
    @patch('apps.arealisting.services.sync_jobs.ArealistingClient')
    def test_worker_finishes_queued_job_and_saves_result(self, client, service):
        job = ArealistingSyncJob.objects.create(resources=['projects'])
        service.return_value.sync.return_value = {'projects': {'seen': 401, 'errors': 0}}

        self.assertTrue(process_sync_job(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, ArealistingSyncJob.Status.SUCCESS)
        self.assertEqual(job.summary['projects']['seen'], 401)
        self.assertIsNotNone(job.finished_at)
        service.return_value.sync.assert_called_once_with(
            resources=['projects'], project_ids=[], full=True,
        )
        client.return_value.close.assert_called_once()
        self.assertFalse(process_sync_job(job.pk))

    @patch('apps.arealisting.services.sync_jobs.ArealistingSyncService')
    @patch('apps.arealisting.services.sync_jobs.ArealistingClient')
    def test_worker_records_failure(self, client, service):
        job = ArealistingSyncJob.objects.create(resources=['projects'])
        service.return_value.sync.side_effect = ValueError('Partner API unavailable')

        self.assertTrue(process_sync_job(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, ArealistingSyncJob.Status.FAILED)
        self.assertIn('Partner API unavailable', job.error)
        self.assertIsNotNone(job.finished_at)
        client.return_value.close.assert_called_once()
