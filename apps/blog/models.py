import re

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit
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
    featured_image = models.ImageField(
        _('Главное изображение (RU)'),
        upload_to='blog/featured/',
        blank=True,
        help_text=_('Главное изображение статьи для русской версии')
    )
    featured_image_en = models.ImageField(
        _('Главное изображение (EN)'),
        upload_to='blog/featured/',
        blank=True,
        help_text=_('Локализованное изображение статьи для английской версии')
    )
    featured_image_th = models.ImageField(
        _('Главное изображение (TH)'),
        upload_to='blog/featured/',
        blank=True,
        help_text=_('Локализованное изображение статьи для тайской версии')
    )
    featured_image_card = ImageSpecField(
        source='featured_image',
        processors=[ResizeToFill(720, 405)],
        format='WEBP',
        options={'quality': 76, 'method': 6},
    )
    featured_image_card_en = ImageSpecField(
        source='featured_image_en',
        processors=[ResizeToFill(720, 405)],
        format='WEBP',
        options={'quality': 76, 'method': 6},
    )
    featured_image_card_th = ImageSpecField(
        source='featured_image_th',
        processors=[ResizeToFill(720, 405)],
        format='WEBP',
        options={'quality': 76, 'method': 6},
    )
    featured_image_hero = ImageSpecField(
        source='featured_image',
        processors=[ResizeToFit(1200, 675)],
        format='WEBP',
        options={'quality': 80, 'method': 6},
    )
    featured_image_hero_en = ImageSpecField(
        source='featured_image_en',
        processors=[ResizeToFit(1200, 675)],
        format='WEBP',
        options={'quality': 80, 'method': 6},
    )
    featured_image_hero_th = ImageSpecField(
        source='featured_image_th',
        processors=[ResizeToFit(1200, 675)],
        format='WEBP',
        options={'quality': 80, 'method': 6},
    )
    featured_image_thumb = ImageSpecField(
        source='featured_image',
        processors=[ResizeToFill(320, 200)],
        format='WEBP',
        options={'quality': 74, 'method': 6},
    )
    featured_image_thumb_en = ImageSpecField(
        source='featured_image_en',
        processors=[ResizeToFill(320, 200)],
        format='WEBP',
        options={'quality': 74, 'method': 6},
    )
    featured_image_thumb_th = ImageSpecField(
        source='featured_image_th',
        processors=[ResizeToFill(320, 200)],
        format='WEBP',
        options={'quality': 74, 'method': 6},
    )
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
    original_url = models.URLField(
        _('Оригинальный URL (RU)'),
        blank=True,
        help_text=_('URL русской версии статьи на исходном сайте')
    )
    original_url_en = models.URLField(
        _('Оригинальный URL (EN)'),
        blank=True,
        help_text=_('URL английской версии статьи на исходном сайте')
    )
    original_url_th = models.URLField(
        _('Оригинальный URL (TH)'),
        blank=True,
        help_text=_('URL тайской версии статьи на исходном сайте')
    )
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
    
    META_DESCRIPTION_LIMIT = 180
    META_DESCRIPTION_TOLERANCE = 20
    META_DESCRIPTION_SUFFIX = " - Undersun Estate"

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
        
    def _get_translated_value(self, field_name, language_code=None):
        """Возвращает значение поля с учётом языковой версии и fallback."""
        lang = (language_code or translation.get_language() or settings.LANGUAGE_CODE or 'ru')[:2]
        default_lang = (settings.LANGUAGE_CODE or 'ru')[:2]

        if lang == default_lang:
            value = getattr(self, field_name, '')
        else:
            translated_field = f"{field_name}_{lang}"
            value = getattr(self, translated_field, '') or getattr(self, field_name, '')

        if isinstance(value, str):
            return value.strip()
        return value

    def get_meta_title(self, language_code=None):
        """Получить SEO заголовок или основной заголовок"""
        value = self._get_translated_value('meta_title', language_code)
        if value:
            return value
        return self._get_translated_value('title', language_code)
        
    def get_meta_description(self, language_code=None):
        """Получить SEO описание или краткое описание"""
        value = self._get_translated_value('meta_description', language_code)
        if value:
            return self._format_meta_description(value)
        fallback = self._get_translated_value('excerpt', language_code)
        return self._format_meta_description(fallback)

    def get_meta_keywords(self, language_code=None):
        """Получить ключевые слова для указанного языка"""
        return self._get_translated_value('meta_keywords', language_code)

    def _format_meta_description(self, text):
        """Укращает описания, сохраняя целые предложения и обязательный суффикс."""
        suffix = self.META_DESCRIPTION_SUFFIX or ''
        limit = self.META_DESCRIPTION_LIMIT
        tolerance = getattr(self, 'META_DESCRIPTION_TOLERANCE', 20)
        total_limit = limit + max(tolerance, 0)

        cleaned = (text or '').strip()
        if not cleaned:
            return suffix.strip() or ''

        if suffix and cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)].rstrip()

        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if s.strip()]
        max_base_len = max(total_limit - len(suffix), 0)
        base = ''

        for sentence in sentences:
            candidate = f"{base} {sentence}".strip() if base else sentence
            candidate_length = len(candidate) + len(suffix)

            if candidate_length <= limit + len(suffix):
                base = candidate
                continue

            if candidate_length <= total_limit:
                base = candidate
            break

        if not base:
            base = cleaned[:max_base_len]
        elif len(base) > max_base_len:
            base = base[:max_base_len].rstrip()

        if not base:
            return suffix.strip() or ''

        result = f"{base}{suffix}" if suffix else base
        if len(result) > total_limit:
            allowed = max(total_limit - len(suffix), 0)
            base = base[:allowed].rstrip()
            result = f"{base}{suffix}" if suffix else base
        return result.strip()

    def get_featured_image_for_language(self, language_code='ru'):
        """Вернуть изображение обложки с учетом локали и доступности."""
        language_code = (language_code or 'ru')[:2]
        candidates = []
        language_map = {
            'ru': self.featured_image,
            'en': self.featured_image_en,
            'th': self.featured_image_th,
        }

        # Локализованное изображение в первую очередь
        if language_code in language_map:
            candidates.append(language_map[language_code])

        # Далее — остальные локализации в предсказуемом порядке
        for code in ('ru', 'en', 'th'):
            if code != language_code:
                candidates.append(language_map.get(code))

        for field in candidates:
            if not field:
                continue
            try:
                url = field.url
            except Exception:
                url = ''
            if url:
                return url

        return ''

    def get_featured_image_field(self, language_code=None):
        """Вернуть локализованный объект ImageFieldFile с fallback между языками."""
        language_code = (language_code or translation.get_language() or settings.LANGUAGE_CODE or 'ru')[:2]
        candidates = []
        language_map = {
            'ru': self.featured_image,
            'en': self.featured_image_en,
            'th': self.featured_image_th,
        }

        if language_code in language_map:
            candidates.append(language_map[language_code])

        for code in ('ru', 'en', 'th'):
            if code != language_code:
                candidates.append(language_map.get(code))

        for field in candidates:
            if field:
                try:
                    if field.name and field.storage.exists(field.name):
                        return field
                except Exception:
                    continue

        return None

    @staticmethod
    def _deduplicate_language_codes(language_code):
        language_code = (language_code or translation.get_language() or settings.LANGUAGE_CODE or 'ru')[:2]
        codes = [language_code, 'ru', 'en', 'th']
        return list(dict.fromkeys(code for code in codes if code in {'ru', 'en', 'th'}))

    @staticmethod
    def _safe_image_url(file_field):
        try:
            return file_field.url
        except Exception:
            return ''

    def _get_featured_image_variant_url(self, variant='card', language_code=None):
        source_fields = {
            'ru': 'featured_image',
            'en': 'featured_image_en',
            'th': 'featured_image_th',
        }
        variant_fields = {
            'card': {
                'ru': 'featured_image_card',
                'en': 'featured_image_card_en',
                'th': 'featured_image_card_th',
            },
            'hero': {
                'ru': 'featured_image_hero',
                'en': 'featured_image_hero_en',
                'th': 'featured_image_hero_th',
            },
            'thumb': {
                'ru': 'featured_image_thumb',
                'en': 'featured_image_thumb_en',
                'th': 'featured_image_thumb_th',
            },
        }.get(variant, {})

        for code in self._deduplicate_language_codes(language_code):
            source_field = getattr(self, source_fields[code], None)
            if not source_field:
                continue

            try:
                if not source_field.name or not source_field.storage.exists(source_field.name):
                    continue
            except Exception:
                continue

            spec_field_name = variant_fields.get(code)
            spec_file = getattr(self, spec_field_name, None) if spec_field_name else None
            if spec_file:
                try:
                    generate = getattr(spec_file, 'generate', None)
                    if callable(generate):
                        generate()
                    storage = getattr(spec_file, 'storage', None)
                    name = getattr(spec_file, 'name', None)
                    if storage and name and storage.exists(name):
                        return storage.url(name)
                except Exception:
                    pass

            return self._safe_image_url(source_field)

        return ''

    def get_localized_featured_image_card_url(self):
        """URL WebP-обложки для карточек блога."""
        return self._get_featured_image_variant_url('card')

    def get_localized_featured_image_hero_url(self):
        """URL WebP-обложки для hero-изображения статьи."""
        return self._get_featured_image_variant_url('hero')

    def get_localized_featured_image_thumb_url(self):
        """URL WebP-обложки для сайдбаров и компактных карточек."""
        return self._get_featured_image_variant_url('thumb')

    def get_localized_featured_image(self):
        """Шаблонный helper: вернуть текущую локализованную обложку статьи."""
        return self.get_featured_image_field()

    def get_featured_image_alt_text(self, language_code=None):
        """Вернуть локализованный alt-текст обложки с fallback на заголовок статьи."""
        alt_text = self._get_translated_value('featured_image_alt', language_code)
        if alt_text:
            return alt_text
        return self._get_translated_value('title', language_code)

    def get_featured_image_absolute_url(self, request, language_code='ru'):
        """Вернуть абсолютный URL изображения обложки для OG метатегов."""
        relative_url = self.get_featured_image_for_language(language_code)
        if not relative_url:
            return ''
        try:
            return request.build_absolute_uri(relative_url)
        except Exception:
            return relative_url

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


class BlogPostPropertyLink(models.Model):
    """Объекты недвижимости, вручную связанные со статьей блога."""

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='property_links',
        verbose_name=_('Статья'),
    )
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='blog_links',
        verbose_name=_('Объект недвижимости'),
    )
    order = models.PositiveIntegerField(
        _('Порядок'),
        default=100,
        help_text=_('Чем меньше число, тем выше объект в блоке статьи'),
    )
    editor_note = models.CharField(
        _('Комментарий редактора'),
        max_length=180,
        blank=True,
        help_text=_('Короткое пояснение, почему объект связан со статьей. Показывается на странице статьи.'),
    )
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)

    class Meta:
        verbose_name = _('Объект в статье блога')
        verbose_name_plural = _('Объекты в статье блога')
        ordering = ['order', 'id']
        unique_together = ('post', 'property')

    def __str__(self):
        return f'{self.post} → {self.property}'


class BlogPostFAQ(models.Model):
    """Вопросы и ответы, которые редактор добавляет в конце статьи."""

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='faq_items',
        verbose_name=_('Статья'),
    )
    question = models.CharField(_('Вопрос'), max_length=300)
    answer = models.TextField(_('Ответ'))
    order = models.PositiveIntegerField(
        _('Порядок'),
        default=100,
        help_text=_('Чем меньше число, тем выше вопрос в блоке FAQ'),
    )
    is_active = models.BooleanField(
        _('Показывать на странице'),
        default=True,
    )
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('Вопрос и ответ статьи')
        verbose_name_plural = _('FAQ статьи')
        ordering = ['order', 'id']

    def __str__(self):
        return self.question


class BlogTranslationJob(models.Model):
    """Очередь переводов статей блога для выполнения вне HTTP-запроса."""

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, _('Ожидает')),
        (STATUS_RUNNING, _('В работе')),
        (STATUS_SUCCEEDED, _('Завершено')),
        (STATUS_FAILED, _('Ошибка')),
        (STATUS_CANCELLED, _('Отменено')),
    ]

    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='translation_jobs',
        verbose_name=_('Статья'),
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blog_translation_jobs',
        verbose_name=_('Поставил в очередь'),
    )
    status = models.CharField(
        _('Статус'),
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    target_languages = models.JSONField(
        _('Языки перевода'),
        default=list,
        blank=True,
    )
    force_retranslate = models.BooleanField(
        _('Перезаписать существующие переводы'),
        default=False,
    )
    provider = models.CharField(
        _('Провайдер'),
        max_length=50,
        blank=True,
        default='yandex',
    )
    total_fields = models.PositiveIntegerField(_('Всего полей'), default=0)
    completed_fields = models.PositiveIntegerField(_('Переведено полей'), default=0)
    skipped_fields = models.PositiveIntegerField(_('Пропущено полей'), default=0)
    failed_fields = models.PositiveIntegerField(_('Ошибок полей'), default=0)
    current_language = models.CharField(_('Текущий язык'), max_length=10, blank=True)
    current_field = models.CharField(_('Текущее поле'), max_length=80, blank=True)
    error_message = models.TextField(_('Ошибка'), blank=True)
    log = models.TextField(_('Журнал'), blank=True)
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    started_at = models.DateTimeField(_('Начато'), blank=True, null=True)
    finished_at = models.DateTimeField(_('Завершено'), blank=True, null=True)

    class Meta:
        verbose_name = _('Задание перевода статьи')
        verbose_name_plural = _('Задания перевода статей')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['post', '-created_at']),
        ]

    def __str__(self):
        return f'#{self.pk} {self.post} ({self.get_status_display()})'

    @property
    def progress_percent(self):
        if self.total_fields <= 0:
            return 100 if self.status == self.STATUS_SUCCEEDED else 0
        return min(100, int((self.completed_fields / self.total_fields) * 100))

    @property
    def is_active(self):
        return self.status in {self.STATUS_PENDING, self.STATUS_RUNNING}


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
