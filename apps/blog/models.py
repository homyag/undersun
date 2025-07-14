from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from tinymce.models import HTMLField


class BlogCategory(models.Model):
    """Категории для блога"""
    
    name = models.CharField(_('Название'), max_length=100)
    slug = models.SlugField(_('URL-адрес'), max_length=100, unique=True)
    description = models.TextField(_('Описание'), blank=True)
    color = models.CharField(_('Цвет'), max_length=7, default='#007bff',
                           help_text=_('Цвет категории в формате HEX (#ffffff)'))
    
    # SEO поля
    meta_title = models.CharField(_('SEO заголовок'), max_length=200, blank=True)
    meta_description = models.TextField(_('SEO описание'), max_length=300, blank=True)
    meta_keywords = models.TextField(_('SEO ключевые слова'), blank=True)
    
    # Настройки
    is_active = models.BooleanField(_('Активно'), default=True)
    order = models.IntegerField(_('Порядок'), default=100)
    
    # Даты
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('Категория блога')
        verbose_name_plural = _('Категории блога')
        ordering = ['order', 'name']
        
    def __str__(self):
        return self.name
        
    def get_absolute_url(self):
        """Получить URL категории"""
        from django.urls import reverse
        return reverse('blog:category', kwargs={'slug': self.slug})


class BlogPost(models.Model):
    """Статьи блога"""
    
    STATUS_CHOICES = [
        ('draft', _('Черновик')),
        ('published', _('Опубликовано')),
        ('archived', _('В архиве')),
    ]
    
    # Основная информация
    title = models.CharField(_('Заголовок'), max_length=200)
    slug = models.SlugField(_('URL-адрес'), max_length=200, unique=True)
    excerpt = models.TextField(_('Краткое описание'), max_length=500,
                             help_text=_('Краткое описание статьи для превью'))
    content = HTMLField(_('Содержание статьи'))
    
    # Связи
    category = models.ForeignKey(BlogCategory, on_delete=models.CASCADE, 
                               related_name='posts', verbose_name=_('Категория'))
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='blog_posts', verbose_name=_('Автор'))
    
    # Изображения
    featured_image = models.ImageField(_('Главное изображение'), upload_to='blog/featured/', 
                                     blank=True, help_text=_('Главное изображение статьи'))
    featured_image_alt = models.CharField(_('Alt текст изображения'), max_length=200, blank=True)
    
    # SEO поля
    meta_title = models.CharField(_('SEO заголовок'), max_length=200, blank=True)
    meta_description = models.TextField(_('SEO описание'), max_length=300, blank=True)
    meta_keywords = models.TextField(_('SEO ключевые слова'), blank=True)
    
    # Настройки публикации
    status = models.CharField(_('Статус'), max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(_('Рекомендуемая'), default=False,
                                    help_text=_('Отображать в блоке рекомендуемых статей'))
    allow_comments = models.BooleanField(_('Разрешить комментарии'), default=True)
    
    # Даты
    published_at = models.DateTimeField(_('Дата публикации'), blank=True, null=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    # Счетчики
    views_count = models.PositiveIntegerField(_('Количество просмотров'), default=0)
    
    class Meta:
        verbose_name = _('Статья блога')
        verbose_name_plural = _('Статьи блога')
        ordering = ['-published_at', '-created_at']
        
    def __str__(self):
        return self.title
        
    def get_absolute_url(self):
        """Получить URL статьи"""
        from django.urls import reverse
        return reverse('blog:detail', kwargs={'slug': self.slug})
        
    def get_meta_title(self):
        """Получить SEO заголовок или основной заголовок"""
        return self.meta_title if self.meta_title else self.title
        
    def get_meta_description(self):
        """Получить SEO описание или краткое описание"""
        return self.meta_description if self.meta_description else self.excerpt
        
    def save(self, *args, **kwargs):
        """Автоматически устанавливаем дату публикации при смене статуса"""
        if self.status == 'published' and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        elif self.status != 'published':
            self.published_at = None
        super().save(*args, **kwargs)
        
    @classmethod
    def get_published(cls):
        """Получить опубликованные статьи"""
        return cls.objects.filter(status='published').select_related('category', 'author')
        
    @classmethod
    def get_featured(cls, limit=3):
        """Получить рекомендуемые статьи"""
        return cls.get_published().filter(is_featured=True)[:limit]
        
    def increment_views(self):
        """Увеличить счетчик просмотров"""
        self.views_count += 1
        self.save(update_fields=['views_count'])
        
    def get_reading_time(self):
        """Оценить время чтения статьи (слов в минуту)"""
        words_per_minute = 200
        word_count = len(self.content.split())
        reading_time = max(1, round(word_count / words_per_minute))
        return reading_time


class BlogTag(models.Model):
    """Теги для статей блога"""
    
    name = models.CharField(_('Название'), max_length=50, unique=True)
    slug = models.SlugField(_('URL-адрес'), max_length=50, unique=True)
    
    # Связи
    posts = models.ManyToManyField(BlogPost, related_name='tags', 
                                 verbose_name=_('Статьи'), blank=True)
    
    # Даты
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Тег блога')
        verbose_name_plural = _('Теги блога')
        ordering = ['name']
        
    def __str__(self):
        return self.name
        
    def get_absolute_url(self):
        """Получить URL тега"""
        from django.urls import reverse
        return reverse('blog:tag', kwargs={'slug': self.slug})
