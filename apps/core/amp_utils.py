from bs4 import BeautifulSoup
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

DEFAULT_IMG_WIDTH = 1200
DEFAULT_IMG_HEIGHT = 675
DEFAULT_VIDEO_WIDTH = 560
DEFAULT_VIDEO_HEIGHT = 315


def _extract_youtube_id(src):
    if not src:
        return None
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(src)
    if 'youtu.be' in parsed.netloc:
        return parsed.path.lstrip('/') or None
    if 'youtube.com' in parsed.netloc:
        if parsed.path.startswith('/embed/'):
            return parsed.path.split('/')[-1]
        query = parse_qs(parsed.query)
        video_ids = query.get('v')
        if video_ids:
            return video_ids[0]
    return None


def convert_html_to_amp(html_content):
    """Простой конвертер HTML → AMP, избавляется от скриптов и добавляет amp-img."""
    if not html_content:
        return ''

    soup = BeautifulSoup(html_content, 'html.parser')

    for script in soup.find_all('script'):
        script.decompose()

    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '')
        youtube_id = _extract_youtube_id(src)
        if youtube_id:
            amp_tag = soup.new_tag('amp-youtube')
            amp_tag['data-videoid'] = youtube_id
            amp_tag['layout'] = 'responsive'
            amp_tag['width'] = iframe.get('width', DEFAULT_VIDEO_WIDTH) or DEFAULT_VIDEO_WIDTH
            amp_tag['height'] = iframe.get('height', DEFAULT_VIDEO_HEIGHT) or DEFAULT_VIDEO_HEIGHT
            iframe.replace_with(amp_tag)
        else:
            link = soup.new_tag('a', href=src or '#')
            link.string = strip_tags(iframe.text) or 'Open embedded content'
            iframe.replace_with(link)

    for img in soup.find_all('img'):
        amp_img = soup.new_tag('amp-img')
        for attr in ['src', 'alt', 'srcset', 'sizes']:
            if img.has_attr(attr):
                amp_img[attr] = img[attr]

        width = img.get('width') or DEFAULT_IMG_WIDTH
        height = img.get('height') or DEFAULT_IMG_HEIGHT

        try:
            width = int(str(width).replace('px', '').strip()) or DEFAULT_IMG_WIDTH
        except Exception:
            width = DEFAULT_IMG_WIDTH

        try:
            height = int(str(height).replace('px', '').strip()) or DEFAULT_IMG_HEIGHT
        except Exception:
            height = DEFAULT_IMG_HEIGHT

        amp_img['width'] = width
        amp_img['height'] = height
        amp_img['layout'] = 'responsive'

        img.replace_with(amp_img)

    for video in soup.find_all('video'):
        amp_video = soup.new_tag('amp-video', controls='', layout='responsive')
        amp_video['width'] = video.get('width', DEFAULT_VIDEO_WIDTH)
        amp_video['height'] = video.get('height', DEFAULT_VIDEO_HEIGHT)
        for source in video.find_all('source'):
            amp_source = soup.new_tag('source')
            if source.get('src'):
                amp_source['src'] = source['src']
            if source.get('type'):
                amp_source['type'] = source['type']
            amp_video.append(amp_source)
        video.replace_with(amp_video)

    for tag in soup.find_all(True):
        attrs = list(tag.attrs.keys())
        for attr in attrs:
            attr_lower = attr.lower()
            if attr_lower == 'uk-grid' or attr_lower.startswith('uk-') or attr_lower.startswith('data-uk-'):
                del tag.attrs[attr]
        if tag.name in ('ul', 'ol') and 'type' in tag.attrs:
            del tag.attrs['type']

    for fig in soup.find_all('figure'):
        fig['style'] = fig.get('style', '')

    return mark_safe(str(soup))
