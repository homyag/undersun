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
    team_author = models.ForeignKey('core.Team', on_delete=models.SET_NULL, null=True, blank=True,
                                   default=5, related_name='blog_posts', verbose_name=_('Автор (сотрудник)'),
                                   help_text=_('Сотрудник компании - автор статьи (по умолчанию: Tatiana)'))
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='blog_posts', verbose_name=_('Автор (legacy)'),
                             help_text=_('Пользователь системы - автор статьи (устаревшее поле)'))
    
    # Изображения
    featured_image = models.ImageField(_('Главное изображение'), upload_to='blog/featured/', 
                                     blank=True, help_text=_('Главное изображение статьи'))
    featured_image_alt = models.CharField(_('Alt текст изображения'), max_length=200, blank=True)
    
    # Дополнительные поля для событий
    event_date = models.DateTimeField(_('Дата события'), blank=True, null=True,
                                    help_text=_('Для мероприятий - дата проведения'))
    event_location = models.CharField(_('Место проведения'), max_length=200, blank=True,
                                    help_text=_('Для мероприятий - место проведения'))
    event_price = models.CharField(_('Стоимость участия'), max_length=100, blank=True,
                                 help_text=_('Для мероприятий - стоимость участия'))
    
    # Дополнительные поля для кейсов и обзоров
    project_url = models.URLField(_('Ссылка на проект'), blank=True,
                                help_text=_('Для кейсов - ссылка на проект'))
    rating = models.PositiveIntegerField(_('Рейтинг'), blank=True, null=True,
                                       help_text=_('Для обзоров - рейтинг от 1 до 5'))
    
    # Поля миграции из внешнего сайта
    original_url = models.URLField(_('Оригинальный URL'), blank=True,
                                 help_text=_('URL статьи на исходном сайте'))
    original_id = models.CharField(_('Оригинальный ID'), max_length=50, blank=True,
                                 help_text=_('ID статьи на исходном сайте'))
    
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
        
    def get_author_display(self):
        """Получить автора для отображения (приоритет team_author > author)"""
        if self.team_author:
            return self.team_author.full_name
        elif self.author:
            return f"{self.author.first_name} {self.author.last_name}".strip() or self.author.username
        return "Неизвестный автор"
    
    def get_author_photo(self):
        """Получить фото автора"""
        if self.team_author and self.team_author.photo:
            return self.team_author.photo
        return None
    
    def get_author_bio(self):
        """Получить биографию автора"""
        if self.team_author and self.team_author.bio:
            return self.team_author.bio
        return None
    
    def get_author_contact(self):
        """Получить контактную информацию автора"""
        if self.team_author:
            return {
                'phone': self.team_author.phone,
                'email': self.team_author.email,
                'whatsapp_url': self.team_author.whatsapp_url,
            }
        return None
        
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
        return cls.objects.filter(status='published').select_related('category', 'author', 'team_author')
        
    @classmethod
    def get_featured(cls, limit=3):
        """Получить рекомендуемые статьи"""
        return cls.get_published().filter(is_featured=True)[:limit]
    
    @classmethod
    def get_by_content_type(cls, content_type):
        """Получить статьи по типу контента"""
        return cls.get_published().filter(content_type=content_type)
    
    @classmethod
    def get_upcoming_events(cls):
        """Получить будущие мероприятия"""
        from django.utils import timezone
        return cls.get_published().filter(
            content_type='upcoming_event',
            event_date__gte=timezone.now()
        ).order_by('event_date')
    
    @classmethod
    def get_past_events(cls):
        """Получить прошедшие мероприятия"""
        from django.utils import timezone
        return cls.get_published().filter(
            content_type='past_event',
            event_date__lt=timezone.now()
        ).order_by('-event_date')
        
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
    
    def get_content_type_display_with_icon(self):
        """Получить отображение типа контента с иконкой"""
        icons = {
            'article': '<i class="fas fa-file-alt mr-2"></i>',
            'news': '<i class="fas fa-newspaper mr-2"></i>',
            'case': '<i class="fas fa-briefcase mr-2"></i>',
            'review': '<i class="fas fa-star mr-2"></i>',
            'place_activity': '<i class="fas fa-map-marker-alt mr-2"></i>',
            'upcoming_event': '<i class="fas fa-calendar-plus mr-2"></i>',
            'past_event': '<i class="fas fa-calendar-check mr-2"></i>',
        }
        icon = icons.get(self.content_type, '<i class="fas fa-file mr-2"></i>')
        return f"{icon}{self.get_content_type_display()}"
    
    def get_content_type_color(self):
        """Получить цвет для типа контента"""
        colors = {
            'article': 'primary',
            'news': 'accent', 
            'case': 'green-600',
            'review': 'yellow-500',
            'place_activity': 'blue-500',
            'upcoming_event': 'purple-600',
            'past_event': 'gray-500',
        }
        return colors.get(self.content_type, 'primary')
    
    def is_event(self):
        """Проверить, является ли контент мероприятием"""
        return self.content_type in ['upcoming_event', 'past_event']


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
