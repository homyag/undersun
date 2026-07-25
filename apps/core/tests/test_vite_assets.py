import json
import os
import tempfile
from unittest.mock import patch

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings


class ViteAssetTemplateTagTests(SimpleTestCase):
    @patch('apps.core.templatetags.vite_assets.finders.find')
    def test_renders_manifest_assets(self, find):
        find.return_value = self._write_manifest({
            'src/main.tsx': {
                'file': 'assets/main-abc.js',
                'css': ['assets/main-def.css'],
            },
        })

        rendered = Template(
            '{% load vite_assets %}{% vite_assets "src/main.tsx" %}'
        ).render(Context())

        self.assertIn('href="/static/map-app/assets/main-def.css"', rendered)
        self.assertIn('src="/static/map-app/assets/main-abc.js"', rendered)

    @patch('apps.core.templatetags.vite_assets.finders.find', return_value=None)
    def test_returns_empty_string_when_manifest_is_missing(self, find):
        rendered = Template(
            '{% load vite_assets %}{% vite_assets "src/main.tsx" %}'
        ).render(Context())

        self.assertEqual(rendered, '')

    @override_settings(DEBUG=True, VITE_DEV_SERVER_URL='http://127.0.0.1:5173')
    def test_renders_dev_server_assets_only_when_explicitly_enabled(self):
        rendered = Template(
            '{% load vite_assets %}{% vite_assets "src/main.tsx" %}'
        ).render(Context())

        self.assertIn('src="http://127.0.0.1:5173/@vite/client"', rendered)
        self.assertIn('src="http://127.0.0.1:5173/src/main.tsx"', rendered)

    def _write_manifest(self, payload):
        manifest = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(payload, manifest)
        manifest.close()
        self.addCleanup(os.unlink, manifest.name)
        return manifest.name
