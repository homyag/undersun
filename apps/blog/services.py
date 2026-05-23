import logging
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags

from apps.core.services import translation_service


BLOG_WEBSITE_NAMES = {
    'ru': 'Блог Undersun Estate',
    'en': 'Undersun Estate Blog',
    'th': 'บล็อก Undersun Estate',
}

BLOG_WEBSITE_DESCRIPTIONS = {
    'ru': 'Новости и статьи об инвестициях и недвижимости Пхукета от агентства Undersun Estate.',
    'en': 'News and articles about Phuket real estate and investments by Undersun Estate.',
    'th': 'ข่าวและบทความเกี่ยวกับอสังหาริมทรัพย์และการลงทุนในภูเก็ตจาก Undersun Estate.',
}

logger = logging.getLogger(__name__)


def translate_blog_post(blog_post, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит статью блога на указанные языки
    
    Args:
        blog_post: Объект BlogPost
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода
    fields_to_translate = ['title', 'excerpt', 'content', 'meta_title', 'meta_description', 'meta_keywords', 'featured_image_alt']
    
    for lang in target_languages:
        logger.info(f"Translating blog post '{blog_post.title}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(blog_post, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(blog_post, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Определяем, нужно ли сохранять HTML
            preserve_html = field_name == 'content' and '<' in russian_value
            
            # Переводим
            translated_text = translation_service.translate_text(
                russian_value, 
                lang, 
                preserve_html=preserve_html
            )
            
            if translated_text:
                setattr(blog_post, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    blog_post.save()
    logger.info(f"Translation completed for blog post '{blog_post.title}'")


def translate_blog_category(blog_category, target_languages=None, force_retranslate=False):
    """
    Автоматически переводит категорию блога на указанные языки
    
    Args:
        blog_category: Объект BlogCategory
        target_languages: Список языков для перевода (по умолчанию ['en', 'th'])
        force_retranslate: Принудительно перезаписать существующие переводы
    """
    if target_languages is None:
        target_languages = translation_service.translation_settings['target_languages']
    
    if not translation_service.is_configured():
        raise Exception("Translation service is not configured. Please set API keys in settings.")
    
    # Определяем поля для перевода
    fields_to_translate = ['name', 'description', 'meta_title', 'meta_description', 'meta_keywords']
    
    for lang in target_languages:
        logger.info(f"Translating blog category '{blog_category.name}' to {lang}")
        
        for field_name in fields_to_translate:
            # Проверяем, есть ли значение в русском поле
            russian_value = getattr(blog_category, field_name, '')
            if not russian_value:
                continue
                
            # Проверяем, нужно ли переводить (существует ли уже перевод)
            translated_field_name = f"{field_name}_{lang}"
            existing_translation = getattr(blog_category, translated_field_name, '')
            
            if existing_translation and not force_retranslate:
                logger.info(f"Skipping {translated_field_name} - already translated")
                continue
            
            # Переводим
            translated_text = translation_service.translate_text(russian_value, lang)
            
            if translated_text:
                setattr(blog_category, translated_field_name, translated_text)
                logger.info(f"Translated {field_name} to {lang}")
            else:
                logger.warning(f"Failed to translate {field_name} to {lang}")
    
    # Сохраняем изменения
    blog_category.save()
    logger.info(f"Translation completed for blog category '{blog_category.name}'")


DEFAULT_LOGO_PATH = 'images/logo_fullscreen.svg'
DEFAULT_OG_IMAGE_PATH = 'images/og-image.jpg'


def _absolute_url(url, request=None):
    """Build absolute URL similar to template filter behaviour."""
    if not url:
        return ''

    if isinstance(url, str) and url.startswith(('http://', 'https://')):
        return url

    if request is None:
        return url

    try:
        return request.build_absolute_uri(url)
    except Exception:
        return url


def _clean_text(value):
    cleaned = strip_tags(value or '').strip()
    if not cleaned:
        return ''
    return ' '.join(cleaned.split())


def _build_author_schema(post, request=None, publisher=None):
    author_name = post.get_author_display()
    if not author_name:
        return None

    author_data = {
        '@type': 'Person',
        'name': author_name,
    }

    if post.team_author:
        if post.team_author.position:
            author_data['jobTitle'] = post.team_author.position
        if post.team_author.photo:
            try:
                author_data['image'] = _absolute_url(post.team_author.photo.url, request)
            except Exception:
                author_data['image'] = None
        if post.team_author.email:
            author_data['email'] = post.team_author.email
        if post.team_author.phone:
            author_data['telephone'] = post.team_author.phone

    if publisher:
        works_for = {
            '@type': 'Organization',
            'name': publisher.get('name'),
        }
        if publisher.get('url'):
            works_for['url'] = publisher['url']
        if publisher.get('logo'):
            works_for['logo'] = publisher['logo']
        author_data['worksFor'] = works_for
        author_data['affiliation'] = works_for

    return {k: v for k, v in author_data.items() if v}


def _build_publisher_schema(request=None):
    return {
        '@type': 'Organization',
        'name': 'Undersun Estate',
        'url': _absolute_url(reverse('core:home'), request) if request else None,
        'logo': {
            '@type': 'ImageObject',
            'url': _absolute_url(static(DEFAULT_LOGO_PATH), request),
        }
    }


def build_blog_post_schema(
    post,
    request=None,
    *,
    language_code='ru',
    meta_description=None,
    image_url=None,
):
    """Собираем JSON-LD BlogPosting для статьи."""
    language = (language_code or getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    canonical_url = _absolute_url(post.get_absolute_url(), request)
    description = meta_description or post.get_meta_description(language)

    if not image_url:
        image_url = post.get_featured_image_absolute_url(request, language)
    if not image_url:
        image_url = _absolute_url(static(DEFAULT_OG_IMAGE_PATH), request)

    content_text = _clean_text(post.content)
    keywords = post.get_meta_keywords(language)
    if not keywords:
        keywords = ', '.join(post.tags.values_list('name', flat=True))

    publisher_schema = _build_publisher_schema(request)
    author_schema = _build_author_schema(post, request, publisher_schema)
    if publisher_schema and author_schema:
        publisher_schema['employee'] = author_schema

    schema = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'url': canonical_url,
        'mainEntityOfPage': {
            '@type': 'WebPage',
            '@id': canonical_url,
        },
        'headline': post.get_meta_title(language),
        'description': description,
        'image': [image_url] if image_url else None,
        'datePublished': post.published_at.isoformat() if post.published_at else None,
        'dateModified': post.updated_at.isoformat() if post.updated_at else None,
        'inLanguage': language,
        'isAccessibleForFree': True,
        'articleSection': post.category.name if post.category else None,
        'articleBody': content_text or None,
        'wordCount': len(content_text.split()) if content_text else None,
        'timeRequired': f"PT{post.get_reading_time()}M",
        'keywords': keywords or None,
        'author': author_schema,
        'publisher': {k: v for k, v in publisher_schema.items() if v not in (None, '', [], {})} if publisher_schema else None,
        'interactionStatistic': {
            '@type': 'InteractionCounter',
            'interactionType': {
                '@type': 'ReadAction',
            },
            'userInteractionCount': post.views_count,
        } if post.views_count else None,
    }

    return {k: v for k, v in schema.items() if v not in (None, '', [], {})}


def build_breadcrumb_schema(items, request=None):
    """Построить BreadcrumbList по списку (название, url)."""
    if not items:
        return None

    element = []
    for position, (name, url) in enumerate(items, start=1):
        if not name:
            continue
        element.append({
            '@type': 'ListItem',
            'position': position,
            'name': name,
            'item': _absolute_url(url, request) if url else None,
        })

    if not element:
        return None

    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': element,
    }


def build_blog_item_list_schema(
    posts,
    request=None,
    *,
    language_code='ru',
    title=None,
    description=None,
    page_url=None,
    about=None,
):
    """CollectionPage + ItemList для индексируемых списков блога."""
    if not posts:
        return None

    language = (language_code or getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru')[:2]
    page_absolute_url = page_url or _absolute_url(getattr(request, 'get_full_path', lambda: '')(), request)
    blog_root_url = _absolute_url(reverse('blog:list'), request) if request else None
    blog_name = BLOG_WEBSITE_NAMES.get(language, BLOG_WEBSITE_NAMES['en'])
    blog_description = BLOG_WEBSITE_DESCRIPTIONS.get(language, BLOG_WEBSITE_DESCRIPTIONS['en'])

    items = []
    for idx, post in enumerate(posts, start=1):
        post_url = _absolute_url(post.get_absolute_url(), request)
        image_url = post.get_featured_image_absolute_url(request, language)
        items.append({
            '@type': 'ListItem',
            'position': idx,
            'url': post_url,
            'name': post.title,
            'item': {
                '@type': 'WebPage',
                '@id': post_url,
                'url': post_url,
                'name': post.title,
                'description': post.get_meta_description(language) or None,
                'inLanguage': language,
                'image': image_url or None,
                'datePublished': post.published_at.isoformat() if post.published_at else None,
                'dateModified': post.updated_at.isoformat() if post.updated_at else None,
            },
        })

    schema = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': title,
        'description': description,
        'url': page_absolute_url,
        'inLanguage': language,
        'isPartOf': {
            '@type': 'Blog',
            'name': blog_name,
            'description': blog_description,
            'url': blog_root_url,
        },
        'mainEntity': {
            '@type': 'ItemList',
            'itemListElement': items,
            'itemListOrder': 'https://schema.org/ItemListOrderDescending',
            'numberOfItems': len(items),
        },
    }

    return {k: v for k, v in schema.items() if v not in (None, '', [], {})}


def build_blog_search_schema(request=None):
    """WebSite schema с SearchAction для поиска по блогу."""
    if request is None:
        return None

    blog_url = _absolute_url(reverse('blog:list'), request)
    if not blog_url:
        return None

    target = f"{blog_url}?search={{search_term_string}}"
    language = getattr(request, 'LANGUAGE_CODE', 'ru')[:2]
    name = BLOG_WEBSITE_NAMES.get(language, BLOG_WEBSITE_NAMES['en'])
    description = BLOG_WEBSITE_DESCRIPTIONS.get(language, BLOG_WEBSITE_DESCRIPTIONS['en'])

    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': name,
        'description': description,
        'url': blog_url,
        'potentialAction': {
            '@type': 'SearchAction',
            'target': target,
            'query-input': 'required name=search_term_string',
        }
    }
