import json
import os

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from urllib.parse import urlparse, parse_qs

from apps.core.models import SEOPage

from .models import BlogPost, BlogCategory, BlogTag


PAGE_LABELS = {
    'ru': 'Страница {page}',
    'en': 'Page {page}',
    'th': 'หน้า {page}',
}


BLOG_SEO_DEFAULTS = {
    'ru': {
        'title': 'Блог Undersun Estate: недвижимость Пхукета и инвестиции',
        'description': 'Аналитика рынка Пхукета, советы по покупке вилл и апартаментов, истории сделок и новости от экспертов Undersun Estate.',
    },
    'en': {
        'title': 'Undersun Estate Blog — Phuket Real Estate & Investment Insights',
        'description': 'Market news, purchase guides, ROI tips and agency stories about Phuket property investments from the Undersun Estate team.',
    },
    'th': {
        'title': 'บล็อก Undersun Estate – อินไซต์อสังหาริมทรัพย์ภูเก็ตและการลงทุน',
        'description': 'อัปเดตตลาด คู่มือการซื้อ และเคล็ดลับการลงทุนอสังหาริมทรัพย์ในภูเก็ตที่คัดสรรโดยทีม Undersun Estate.',
    },
}


def _append_suffix_if_needed(value, suffix):
    if not suffix:
        return value

    if not value:
        return suffix.strip(' |')

    normalized_value = value.lower()
    normalized_suffix = suffix.lower().strip()
    if normalized_suffix and normalized_suffix in normalized_value:
        return value

    return f"{value}{suffix}"


def _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj):
    if not page_obj:
        return meta_title, meta_description

    try:
        page_number = int(page_obj.number)
    except (TypeError, ValueError, AttributeError):
        page_number = 1

    if page_number <= 1:
        return meta_title, meta_description

    language = (language_code or 'ru')[:2]
    label_template = PAGE_LABELS.get(language, PAGE_LABELS['en'])
    pagination_label = label_template.format(page=page_number)
    pagination_suffix = f" | {pagination_label}"

    updated_title = _append_suffix_if_needed(meta_title, pagination_suffix)
    updated_description = _append_suffix_if_needed(meta_description, pagination_suffix)

    return updated_title, updated_description


def _get_seo_page_meta(page_name, language_code='ru'):
    """Забираем title/description/keywords для указанной SEO страницы."""
    try:
        seo_page = SEOPage.objects.get(page_name=page_name, is_active=True)
    except SEOPage.DoesNotExist:
        return {}

    return {
        'title': seo_page.get_title(language_code),
        'description': seo_page.get_description(language_code),
        'keywords': seo_page.get_keywords(language_code),
    }


def blog_list(request):
    """Список всех статей блога"""
    posts = BlogPost.get_published().prefetch_related('tags')
    language_code = getattr(request, 'LANGUAGE_CODE', 'ru')[:2]
    
    # Фильтрация по категории
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(BlogCategory, slug=category_slug, is_active=True)
        posts = posts.filter(category=category)
    else:
        category = None
    
    # Фильтрация по тегу
    tag_slug = request.GET.get('tag')
    if tag_slug:
        tag = get_object_or_404(BlogTag, slug=tag_slug)
        posts = posts.filter(tags=tag)
    else:
        tag = None
    
    
    # Поиск
    search_query = request.GET.get('search')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query) |
            Q(content__icontains=search_query)
        )
    
    # Пагинация
    paginator = Paginator(posts, getattr(settings, 'PAGINATE_BY', 12))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()
    
    seo_meta = _get_seo_page_meta('blog', language_code)
    defaults = BLOG_SEO_DEFAULTS.get(language_code, BLOG_SEO_DEFAULTS['ru'])

    meta_title = seo_meta.get('title') or defaults['title']
    meta_description = seo_meta.get('description') or defaults['description']
    meta_title, meta_description = _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj)

    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'categories': categories,
        'featured_posts': featured_posts,
        'current_category': category,
        'current_tag': tag,
        'search_query': search_query,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': seo_meta.get('keywords'),
        'page_keywords': seo_meta.get('keywords'),
    }
    
    return render(request, 'blog/blog_list.html', context)


def blog_detail(request, slug):
    """Детальная страница статьи"""
    post = get_object_or_404(
        BlogPost.objects.select_related('category', 'author').prefetch_related('tags'),
        slug=slug,
        status='published'
    )
    
    # Увеличиваем счетчик просмотров
    post.increment_views()
    
    # Получаем похожие статьи (из той же категории)
    related_posts = BlogPost.get_published().filter(
        category=post.category
    ).exclude(id=post.id)[:3]
    
    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()
    
    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title = post.get_meta_title(language_code)
    meta_description = post.get_meta_description(language_code)
    meta_keywords = post.get_meta_keywords(language_code)

    amp_url = request.build_absolute_uri(
        reverse('blog:detail_amp', kwargs={'slug': slug})
    )

    context = {
        'post': post,
        'related_posts': related_posts,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'page_description': meta_description,
        'page_keywords': meta_keywords,
        'amp_url': amp_url,
    }

    og_image_url = post.get_featured_image_absolute_url(request, getattr(request, 'LANGUAGE_CODE', 'ru'))
    if og_image_url:
        context['og_image_url'] = og_image_url

    return render(request, 'blog/blog_detail.html', context)


def _extract_youtube_id(src):
    if not src:
        return None
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


DEFAULT_IMG_WIDTH = 1200
DEFAULT_IMG_HEIGHT = 675
DEFAULT_VIDEO_WIDTH = 560
DEFAULT_VIDEO_HEIGHT = 315


def _convert_content_to_amp(html_content):
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

    # Wrap video tags
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

    # Remove UIkit attributes (uk-grid, uk-scrollspy, etc.) that AMP не поддерживает
    for tag in soup.find_all(True):
        attrs = list(tag.attrs.keys())
        for attr in attrs:
            attr_lower = attr.lower()
            if attr_lower == 'uk-grid' or attr_lower.startswith('uk-') or attr_lower.startswith('data-uk-'):
                del tag.attrs[attr]

    # Ensure figcaption placement
    for fig in soup.find_all('figure'):
        fig['style'] = fig.get('style', '')

    return mark_safe(str(soup))


def blog_detail_amp(request, slug):
    post = get_object_or_404(
        BlogPost.objects.select_related('category', 'author').prefetch_related('tags'),
        slug=slug,
        status='published'
    )

    related_posts = BlogPost.get_published().filter(
        category=post.category
    ).exclude(id=post.id)[:3]

    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title = post.get_meta_title(language_code)
    meta_description = post.get_meta_description(language_code)
    meta_keywords = post.get_meta_keywords(language_code)

    canonical_url = request.build_absolute_uri(
        reverse('blog:detail', kwargs={'slug': slug})
    )

    og_image_url = post.get_featured_image_absolute_url(request, getattr(request, 'LANGUAGE_CODE', 'ru'))
    default_amp_image = request.build_absolute_uri(static('images/og-image.jpg'))

    context = {
        'post': post,
        'related_posts': related_posts,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
        'page_description': meta_description,
        'canonical_url': canonical_url,
        'amp_content': _convert_content_to_amp(post.content),
        'og_image_url': og_image_url,
        'default_amp_image': default_amp_image,
        'author_anchor_url': f"{canonical_url}#author",
    }

    return render(request, 'blog/blog_detail_amp.html', context)


def blog_category(request, slug):
    """Статьи определенной категории"""
    category = get_object_or_404(BlogCategory, slug=slug, is_active=True)
    posts = BlogPost.get_published().filter(category=category).prefetch_related('tags')
    
    # Пагинация
    paginator = Paginator(posts, getattr(settings, 'PAGINATE_BY', 12))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()
    
    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title = category.meta_title or f'Статьи в категории {category.name}'
    meta_description = category.meta_description or category.description
    meta_title, meta_description = _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj)

    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'category': category,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'meta_keywords': category.meta_keywords,
    }
    
    return render(request, 'blog/blog_category.html', context)


def blog_tag(request, slug):
    """Статьи с определенным тегом"""
    tag = get_object_or_404(BlogTag, slug=slug)
    posts = BlogPost.get_published().filter(tags=tag).prefetch_related('tags')
    
    # Пагинация
    paginator = Paginator(posts, getattr(settings, 'PAGINATE_BY', 12))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем категории и рекомендуемые статьи для сайдбара
    categories = BlogCategory.objects.filter(is_active=True)
    featured_posts = BlogPost.get_featured()
    
    language_code = (getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    meta_title = f'Статьи с тегом {tag.name}'
    meta_description = f'Все статьи с тегом {tag.name}'
    meta_title, meta_description = _apply_pagination_suffix(meta_title, meta_description, language_code, page_obj)

    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'tag': tag,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': meta_title,
        'meta_description': meta_description,
    }
    
    return render(request, 'blog/blog_tag.html', context)


@csrf_exempt
@require_POST
def tinymce_upload(request):
    """
    Загрузка изображений для TinyMCE редактора
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    
    # Проверяем тип файла
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    file_extension = os.path.splitext(file.name)[1].lower()
    
    if file_extension not in allowed_extensions:
        return JsonResponse({
            'error': 'Invalid file type. Allowed: JPG, PNG, GIF, WebP'
        }, status=400)
    
    # Проверяем размер файла (максимум 5MB)
    if file.size > 5 * 1024 * 1024:
        return JsonResponse({
            'error': 'File too large. Maximum size: 5MB'
        }, status=400)
    
    try:
        # Создаем безопасное имя файла
        name, ext = os.path.splitext(file.name)
        safe_name = slugify(name) + ext
        
        # Путь для сохранения
        upload_path = f'blog/editor/{safe_name}'
        
        # Сохраняем файл
        file_path = default_storage.save(upload_path, ContentFile(file.read()))
        
        # Возвращаем URL для TinyMCE
        file_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)
        
        return JsonResponse({
            'location': file_url
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Upload failed: {str(e)}'
        }, status=500)
