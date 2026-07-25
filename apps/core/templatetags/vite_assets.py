"""Template tags for hashed assets produced by the isolated Vite map app."""

import json

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe


register = template.Library()
VITE_MANIFEST_PATH = 'map-app/manifest.json'


def _get_manifest_entry(entry_name):
    manifest_path = finders.find(VITE_MANIFEST_PATH)
    if not manifest_path:
        return None

    try:
        with open(manifest_path, encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
    except (OSError, json.JSONDecodeError):
        return None

    entry = manifest.get(entry_name)
    return entry if isinstance(entry, dict) else None


def _asset_url(asset_path):
    return static(f'map-app/{asset_path}')


def _get_dev_server_url():
    if not settings.DEBUG:
        return ''
    return str(getattr(settings, 'VITE_DEV_SERVER_URL', '')).rstrip('/')


@register.simple_tag
def vite_asset(entry_name):
    """Return an entry JavaScript URL, or an empty string when the build is absent."""
    dev_server_url = _get_dev_server_url()
    if dev_server_url:
        return f'{dev_server_url}/{entry_name.lstrip("/")}'

    entry = _get_manifest_entry(entry_name)
    asset_path = entry.get('file') if entry else None
    return _asset_url(asset_path) if asset_path else ''


@register.simple_tag
def vite_assets(entry_name):
    """Render CSS and a module script tag for a Vite entry without a CDN fallback."""
    dev_server_url = _get_dev_server_url()
    if dev_server_url:
        return mark_safe('\n'.join([
            format_html('<script type="module" src="{}/@vite/client"></script>', dev_server_url),
            format_html(
                '<script type="module" src="{}/{}"></script>',
                dev_server_url,
                entry_name.lstrip('/'),
            ),
        ]))

    entry = _get_manifest_entry(entry_name)
    asset_path = entry.get('file') if entry else None
    if not asset_path:
        return ''

    tags = [
        format_html('<link rel="stylesheet" href="{}">', _asset_url(css_path))
        for css_path in entry.get('css', [])
    ]
    tags.append(format_html('<script type="module" src="{}"></script>', _asset_url(asset_path)))
    return mark_safe('\n'.join(tags))
