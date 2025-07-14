from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings
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
