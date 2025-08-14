import json
import os
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils.text import slugify
from .models import BlogPost, BlogCategory, BlogTag


def blog_list(request):
    """Список всех статей блога"""
    posts = BlogPost.get_published().prefetch_related('tags')
    
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
    
    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'categories': categories,
        'featured_posts': featured_posts,
        'current_category': category,
        'current_tag': tag,
        'search_query': search_query,
        'meta_title': 'Блог',
        'meta_description': 'Статьи и новости о недвижимости',
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
    
    context = {
        'post': post,
        'related_posts': related_posts,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': post.get_meta_title(),
        'meta_description': post.get_meta_description(),
        'meta_keywords': post.meta_keywords,
    }
    
    return render(request, 'blog/blog_detail.html', context)


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
    
    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'category': category,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': category.meta_title or f'Статьи в категории {category.name}',
        'meta_description': category.meta_description or category.description,
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
    
    context = {
        'page_obj': page_obj,
        'posts': page_obj.object_list,
        'tag': tag,
        'categories': categories,
        'featured_posts': featured_posts,
        'meta_title': f'Статьи с тегом {tag.name}',
        'meta_description': f'Все статьи с тегом {tag.name}',
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
