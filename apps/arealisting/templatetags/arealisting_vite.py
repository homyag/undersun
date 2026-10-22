"""Vite assets for the isolated AREALISTING admin interface."""

import json

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join


register = template.Library()
MANIFEST = 'arealisting-app/manifest.json'
ENTRY = 'src/main.ts'


def _dev_server_url():
    if not settings.DEBUG:
        return ''
    return str(getattr(settings, 'AREALISTING_VITE_DEV_SERVER_URL', '')).rstrip('/')


def _entry():
    path = finders.find(MANIFEST)
    if not path:
        return None
    try:
        with open(path, encoding='utf-8') as source:
            entry = json.load(source).get(ENTRY)
        return entry if isinstance(entry, dict) and entry.get('file') else None
    except (OSError, ValueError, TypeError):
        return None


def matching_vue_available():
    return bool(_dev_server_url() or _entry())


@register.simple_tag
def arealisting_vite_assets():
    dev_url = _dev_server_url()
    if dev_url:
        return format_html(
            '<script type="module" src="{}/@vite/client"></script>'
            '<script type="module" src="{}/{}"></script>', dev_url, dev_url, ENTRY,
        )
    entry = _entry()
    if not entry:
        return ''
    css = format_html_join('', '<link rel="stylesheet" href="{}">', (
        (static(f'arealisting-app/{path}'),) for path in entry.get('css', [])
    ))
    return format_html('{}<script type="module" src="{}"></script>',
                       css, static(f"arealisting-app/{entry['file']}"))
