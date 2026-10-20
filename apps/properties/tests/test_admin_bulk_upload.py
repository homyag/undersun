from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import PropertyMock, patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.locations.models import District
from apps.properties.models import Property, PropertyImage, PropertyType


class AdminBulkUploadTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.property = Property.objects.create(
            title='Upload test',
            slug='upload-test',
            property_type=PropertyType.objects.create(name='condo'),
            district=District.objects.create(name='Upload district', slug='upload-district'),
        )
        self.url = reverse('admin_bulk_upload_images')
        self.csrf_token = 'a' * 32

    def upload(self, client, *, csrf=True):
        buffer = BytesIO()
        Image.new('RGB', (32, 24), 'blue').save(buffer, format='PNG')
        headers = {'HTTP_X_CSRFTOKEN': self.csrf_token} if csrf else {}
        return client.post(
            self.url,
            {
                'property_id': self.property.pk,
                'images': SimpleUploadedFile(
                    'townhouse.png', buffer.getvalue(), content_type='image/png'
                ),
            },
            **headers,
        )

    def test_staff_with_permission_can_upload_with_csrf(self):
        user = User.objects.create_superuser('upload-admin', 'admin@example.test', 'password')
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        client.cookies['csrftoken'] = self.csrf_token

        with patch.object(PropertyImage, 'thumbnail_url', new_callable=PropertyMock) as thumbnail:
            thumbnail.side_effect = AssertionError('Thumbnail must not be generated during upload')
            response = self.upload(client)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(self.property.images.count(), 1)
        self.assertEqual(response.json()['images'][0]['thumbnail_url'], response.json()['images'][0]['image_url'])

    def test_upload_rejects_missing_csrf_and_staff_without_permission(self):
        user = User.objects.create_user('upload-staff', 'staff@example.test', 'password', is_staff=True)
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        self.assertEqual(self.upload(client, csrf=False).status_code, 403)
        client.cookies['csrftoken'] = self.csrf_token
        response = self.upload(client)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['success'])
        self.assertFalse(self.property.images.exists())
