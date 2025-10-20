import os
import time
import re
import uuid
import mimetypes
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from apps.blog.models import BlogPost, BlogCategory


class Command(BaseCommand):
    help = 'Парсинг статей блога с сайта undersunestate.com'

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = 'https://undersunestate.com'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            type=str,
            default='news',
            help='Категория блога для парсинга (news, articles, cases, reviews, etc.)'
        )
        parser.add_argument(
            '--languages',
            type=str,
            default='ru,en,th',
            help='Список языков через запятую для парсинга (ru,en,th)'
        )
        parser.add_argument(
            '--language',
            type=str,
            choices=['ru', 'en', 'th'],
            help='Язык для одиночной статьи (--test-single). Если не указан, используется первый из --languages.'
        )
        parser.add_argument(
            '--test-single',
            type=str,
            help='Парсить только одну статью по URL для тестирования'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод отладочной информации'
        )

    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        languages = self._parse_languages(options.get('languages'))

        if options['test_single']:
            test_language = options.get('language') or languages[0]
            self.parse_single_article(options['test_single'], language=test_language)
            return

        category = options['category']

        for language in languages:
            self.stdout.write(f"\n=== Парсинг языка: {language.upper()} ===")

            # Создаем или получаем категорию блога (обновляем перевод названия при необходимости)
            blog_category = self.get_or_create_blog_category(category, language)

            self.stdout.write(f"Начинаем парсинг категории: {category} ({language})")

            article_urls = self.get_category_articles(category, language)
            self.stdout.write(f"Найдено {len(article_urls)} статей для парсинга ({language})")

            success_count = 0
            error_count = 0
            duplicate_count = 0

            for i, url in enumerate(article_urls):
                self.stdout.write(f"Парсинг {i+1}/{len(article_urls)} [{language}]: {url}")
                try:
                    self.parse_single_article(url, blog_category, language=language)
                    if getattr(self, '_is_duplicate', False):
                        duplicate_count += 1
                    else:
                        success_count += 1

                    time.sleep(1)
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"Ошибка при парсинге {url}: {e}"))

            self.stdout.write(self.style.SUCCESS(
                f"\n=== Итоги для {language.upper()} ===\n"
                f"Успешно обработано: {success_count}\n"
                f"Найдено дубликатов: {duplicate_count}\n"
                f"Ошибок: {error_count}\n"
                f"Всего обработано: {len(article_urls)}"
            ))

    def _parse_languages(self, languages_option):
        """Нормализовать список запрошенных языков"""
        supported = {'ru', 'en', 'th'}
        if not languages_option:
            return ['ru']

        raw_values = [lang.strip().lower() for lang in languages_option.split(',') if lang.strip()]
        languages = []
        for lang in raw_values:
            if lang not in supported:
                raise CommandError(f"Неподдерживаемый язык: {lang}. Допустимые: ru, en, th")
            if lang not in languages:
                languages.append(lang)

        return languages or ['ru']

    def _get_language_suffix(self, language):
        return '' if language == 'ru' else f'_{language}'

    def _translated_field(self, field_name, language):
        suffix = self._get_language_suffix(language)
        return f"{field_name}{suffix}" if suffix else field_name

    def _get_original_url_field(self, language):
        return 'original_url' if language == 'ru' else f'original_url_{language}'

    def _get_featured_image_field(self, language):
        return 'featured_image' if language == 'ru' else f'featured_image_{language}'

    def _parse_datetime_string(self, value):
        if not value:
            return None

        value = value.strip()
        if not value:
            return None

        parsed_dt = parse_datetime(value)
        if parsed_dt:
            if timezone.is_naive(parsed_dt):
                parsed_dt = timezone.make_aware(parsed_dt, timezone.get_current_timezone())
            return parsed_dt

        parsed_date = parse_date(value)
        if parsed_date:
            combined = datetime.combine(parsed_date, datetime.min.time())
            return timezone.make_aware(combined, timezone.get_current_timezone())

        for fmt in ("%d %B %Y", "%B %d, %Y", "%d %b %Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(value, fmt)
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                return dt
            except ValueError:
                continue

        return None

    def get_category_articles(self, category, language):
        """Получить все URL статей из определенной категории блога с поддержкой пагинации"""
        article_urls = []
        page_number = 1
        start_param = 0
        
        while True:
            # Формируем URL для текущей страницы
            if page_number == 1:
                page_url = f"{self.base_url}/{language}/blog/{category}"
            else:
                page_url = f"{self.base_url}/{language}/blog/{category}?start={start_param}"
            
            self.stdout.write(f"Загружаем страницу {page_number}: {page_url}")
            
            response = self.session.get(page_url)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Ошибка загрузки страницы {page_number}: {response.status_code}"))
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем ссылки на статьи на текущей странице
            page_articles = self.extract_articles_from_page(soup, category, language)
            
            # Если статей на странице не найдено - прекращаем
            if not page_articles:
                if page_number == 1:
                    self.stdout.write(self.style.WARNING(f"На первой странице не найдено статей"))
                break
            
            # Добавляем найденные статьи
            new_articles = 0
            for article_url in page_articles:
                if article_url not in article_urls:
                    article_urls.append(article_url)
                    new_articles += 1
            
            self.stdout.write(f"Найдено {new_articles} новых статей на странице {page_number}")
            
            # Ищем ссылку на следующую страницу
            next_page_url = self.get_next_page_url(soup, category, language, start_param)
            if not next_page_url:
                self.stdout.write(f"Достигнута последняя страница")
                break
            
            # Извлекаем параметр start для следующей страницы
            start_match = re.search(r'start=(\d+)', next_page_url)
            if start_match:
                new_start_param = int(start_match.group(1))
                # Проверяем, что мы действительно переходим на следующую страницу
                if new_start_param <= start_param:
                    self.stdout.write(f"Не удалось найти следующую страницу (start={new_start_param} <= {start_param})")
                    break
                start_param = new_start_param
                page_number += 1
            else:
                break
            
            # Пауза между запросами страниц
            time.sleep(0.5)
        
        self.stdout.write(f"Всего найдено {len(article_urls)} статей на {page_number} страницах")
        return article_urls

    def extract_articles_from_page(self, soup, category, language):
        """Извлечение ссылок на статьи с одной страницы"""
        article_urls = []
        
        # Пробуем разные селекторы для ссылок на статьи
        selectors = [
            f'a[href*="/{language}/blog/{category}/"]',
            f'a[href^="/{language}/blog/{category}/"]',
            '.el-item a',
            'article a',
            '.uk-article a'
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                for link in links:
                    href = link.get('href', '')
                    if self.is_valid_article_url(href, category, language):
                        full_url = urljoin(self.base_url, href)
                        if full_url not in article_urls:
                            article_urls.append(full_url)
                
                # Если нашли статьи с первым селектором - используем только их
                if article_urls:
                    break
        
        return article_urls
    
    def get_next_page_url(self, soup, category, language, current_start=0):
        """Получить URL следующей страницы пагинации"""
        # Ищем различные варианты ссылок на следующую страницу
        next_selectors = [
            # Классические ссылки пагинации
            f'a[href*="/{language}/blog/{category}?start="]',
            f'a[href*="blog/{category}?start="]',
            
            # Ссылки со словом "Далее", "Next", ">"
            'a:contains("Далее")',
            'a:contains("Next")',
            'a:contains(">")',
            
            # По классам пагинации
            '.pagination a[href*="start="]',
            '.uk-pagination a[href*="start="]',
            '.page-nav a[href*="start="]',
            
            # Все ссылки с параметром start
            'a[href*="start="]'
        ]
        
        for selector in next_selectors:
            try:
                if selector.startswith('a:contains('):
                    # BeautifulSoup не поддерживает :contains, используем find()
                    text_to_find = selector.split('"')[1]
                    links = soup.find_all('a', string=re.compile(text_to_find))
                else:
                    links = soup.select(selector)
                
                for link in links:
                    href = link.get('href', '')
                    if href and 'start=' in href:
                        # Проверяем что это действительно пагинация для нашей категории
                        if f'/{language}/blog/{category}' in href or f'blog/{category}' in href:
                            # Извлекаем start параметр из ссылки
                            start_match = re.search(r'start=(\d+)', href)
                            if start_match:
                                link_start = int(start_match.group(1))
                                # Ищем ссылку с start больше текущего
                                if link_start > current_start:
                                    full_url = urljoin(self.base_url, href)
                                    return full_url
                            
            except Exception as e:
                if self.verbose:
                    self.stdout.write(f"Ошибка в селекторе {selector}: {e}")
                continue
        
        # Дополнительно: ищем числовые ссылки пагинации (2, 3, 4, ...)
        number_links = soup.find_all('a', href=True)
        for link in number_links:
            href = link.get('href', '')
            link_text = link.get_text().strip()
            
            # Если ссылка содержит число и start параметр
            if (
                link_text.isdigit() and 
                int(link_text) > 1 and 
                'start=' in href and 
                (f'/{language}/blog/{category}' in href or f'blog/{category}' in href)
            ):
                return urljoin(self.base_url, href)
        
        return None

    def is_valid_article_url(self, url, category, language):
        """Проверка, является ли URL действительной статьей"""
        if not url:
            return False
        if f'/{language}/blog/{category}/' not in url:
            return False
        
        # URL должен содержать ID статьи (число)
        path_parts = url.split('/')
        if len(path_parts) >= 4:
            last_part = path_parts[-1]
            # Проверяем, что есть ID в начале (например, 1094-article-title)
            if re.match(r'\d+-', last_part):
                return True
        
        return False

    def parse_single_article(self, url, category=None, language='ru'):
        """Парсинг одной статьи блога"""
        response = self.session.get(url)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Извлекаем данные
        data = self.extract_article_data(soup, url, language)
        
        # Если категория не указана, определяем из URL
        if not category:
            category_slug = self.extract_category_from_url(url)
            category = self.get_or_create_blog_category(category_slug, language)

        data['category'] = category
        data['language'] = language

        content_field = self._translated_field('content', language)

        # Отладочная информация
        if self.verbose:
            self.stdout.write(f"Извлеченные данные:")
            for key, value in data.items():
                if key != 'featured_image_url' and not key.startswith('content'):
                    self.stdout.write(f"  {key}: {value}")
            if data.get(content_field):
                self.stdout.write(f"  {content_field}: {len(data[content_field])} символов")
            if 'featured_image_url' in data:
                self.stdout.write(f"  featured_image_url: {data['featured_image_url']}")

        # Создаем или обновляем статью в БД
        article_obj = self.save_article(data)

        # Сохраняем изображение
        if article_obj and data.get('featured_image_url'):
            self.save_featured_image(article_obj, data['featured_image_url'], language)
        
        return article_obj

    def extract_article_data(self, soup, url, language):
        """Извлечение данных из HTML страницы статьи"""
        data = {}
        original_url_field = self._get_original_url_field(language)
        data[original_url_field] = url

        # Извлекаем original_id из URL
        original_id_match = re.search(r'/(\d+)-', url)
        if original_id_match:
            data['original_id'] = original_id_match.group(1)
        
        # Заголовок статьи
        title_field = self._translated_field('title', language)
        title_element = soup.find('h1') or soup.select_one('.uk-article-title') or soup.find('title')
        if title_element:
            data[title_field] = title_element.get_text().strip()
        else:
            data[title_field] = 'Без названия'

        # Генерируем slug из URL (более надёжно) или из заголовка
        base_title = data[title_field]
        data['slug'] = self.generate_slug(url, base_title)

        # Дата публикации - ищем в различных местах
        data['published_at'] = self.extract_publication_date(soup, url, language)

        # Основное содержимое статьи
        content, excerpt = self.extract_content(soup)
        content_field = self._translated_field('content', language)
        excerpt_field = self._translated_field('excerpt', language)
        data[content_field] = content
        data[excerpt_field] = excerpt

        # Главное изображение
        data['featured_image_url'] = self.extract_featured_image(soup)

        # Извлекаем видео ссылки
        videos = self.extract_video_links(soup)
        if videos:
            # Добавляем видео в контент
            video_html = "\n\n<h3>Видео:</h3>\n"
            for video_url in videos:
                if 'youtube' in video_url or 'youtu.be' in video_url:
                    video_id = self.extract_youtube_id(video_url)
                    if video_id:
                        video_html += f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>\n'
                else:
                    video_html += f'<a href="{video_url}" target="_blank">{video_url}</a>\n'
            data[content_field] = (data.get(content_field) or '') + video_html
        
        return data

    def generate_slug(self, url, title):
        """Генерация slug из URL или заголовка"""
        # Сначала пробуем извлечь slug из URL (после ID)
        # URL формат: /ru/blog/news/1094-the-first-podcast-about-the-phuket-property-association-bohdan-dyachuk-on-sid-consultancy
        url_match = re.search(r'/(\d+)-(.+?)(?:/|$)', url)
        if url_match:
            url_slug = url_match.group(2)
            # Очищаем и валидируем slug из URL
            cleaned_slug = slugify(url_slug)
            if cleaned_slug and len(cleaned_slug) > 3:  # Минимум 4 символа
                return cleaned_slug[:200]  # Ограничиваем длину
        
        # Если не удалось извлечь из URL, генерируем из заголовка
        title_slug = slugify(title)
        if title_slug:
            return title_slug[:200]
        
        # В крайнем случае используем ID статьи
        original_id_match = re.search(r'/(\d+)-', url)
        if original_id_match:
            return f"article-{original_id_match.group(1)}"
        
        return "no-slug"

    def extract_publication_date(self, soup, url, language):
        """Извлечение даты публикации"""
        # Попробуем прочитать дату из мета-тегов/атрибутов
        meta_selectors = [
            'meta[property="article:published_time"]',
            'meta[name="article:published_time"]',
            'meta[name="pubdate"]',
            'meta[name="publish-date"]',
            'meta[name="date"]',
        ]

        for selector in meta_selectors:
            element = soup.select_one(selector)
            if not element:
                continue
            value = element.get('content') or element.get('value')
            parsed = self._parse_datetime_string(value)
            if parsed:
                return parsed

        # Ищем time теги с datetime
        for time_tag in soup.find_all('time'):
            for attr in ('datetime', 'content'):
                value = time_tag.get(attr)
                parsed = self._parse_datetime_string(value)
                if parsed:
                    return parsed

        # Фолбэк для русского текста
        if language == 'ru':
            page_text = soup.get_text()
            months_ru = {
                'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
                'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
                'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
            }

            ru_date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', page_text)
            if ru_date_match:
                day, month_ru, year = ru_date_match.groups()
                month = months_ru.get(month_ru.lower())
                if month:
                    try:
                        date_str = f"{year}-{month}-{day.zfill(2)}"
                        parsed_date = timezone.datetime.strptime(date_str, "%Y-%m-%d")
                        return timezone.make_aware(parsed_date)
                    except Exception:
                        pass

        # Если дату не нашли, возвращаем текущую
        return timezone.now()

    def extract_content(self, soup):
        """Извлечение содержимого статьи"""
        content = ""
        excerpt = ""

        # Удаляем элементы, которые точно не относятся к тексту статьи
        for element in soup(['script', 'style', 'noscript', 'svg', 'form']):
            element.decompose()

        content_selectors = [
            '[itemprop="articleBody"]',
            '.el-article',
            '.article-content',
            '.post-content',
            '.uk-article',
            'article',
            '.content',
            'main'
        ]

        content_element = None
        for selector in content_selectors:
            candidates = []
            for element in soup.select(selector):
                prepared = self.prepare_content_element(element)
                if not prepared:
                    continue
                text = prepared.get_text(separator=' ', strip=True)
                if len(text) < 200:
                    continue
                candidates.append((len(text), prepared))
            if candidates:
                # Берём самый содержательный элемент среди кандидатов
                candidates.sort(key=lambda item: item[0], reverse=True)
                content_element = candidates[0][1]
                break

        # Если подходящий контейнер не найден, собираем текст из параграфов и списков
        if not content_element:
            paragraphs = soup.find_all(['p', 'h2', 'h3', 'h4', 'ul', 'ol', 'blockquote'])
            meaningful = []
            for tag in paragraphs:
                text = tag.get_text(separator=' ', strip=True)
                if tag.name in ['h2', 'h3', 'h4'] or len(text) > 40:
                    meaningful.append(tag)
            if meaningful:
                container = soup.new_tag('div')
                for tag in meaningful:
                    container.append(tag)
                content_element = self.prepare_content_element(container)

        if content_element:
            self.make_urls_absolute(content_element)
            content = str(content_element)

            first_p = content_element.find('p')
            if first_p:
                excerpt_text = first_p.get_text(separator=' ', strip=True)
                excerpt = excerpt_text[:500] + '...' if len(excerpt_text) > 500 else excerpt_text

        return content, excerpt

    def prepare_content_element(self, element):
        """Подготовка элемента с контентом статьи"""
        if not element:
            return None

        # Удаляем блоки с шарингом, рекламой и навигацией внутри статьи
        removal_keywords = [
            'share', 'social', 'breadcrumbs', 'tags', 'related', 'comment',
            'pagination', 'author', 'meta', 'subscribe', 'read-more'
        ]
        for descendant in list(element.find_all(True)):
            classes = ' '.join(descendant.get('class', [])).lower()
            element_id = (descendant.get('id') or '').lower()
            fingerprint = f"{classes} {element_id}".strip()
            if any(keyword in fingerprint for keyword in removal_keywords):
                descendant.decompose()

        return element

    def make_urls_absolute(self, element):
        """Преобразование относительных ссылок в абсолютные"""
        for tag in element.find_all(['a', 'img']):
            if tag.name == 'a':
                attrs = ['href']
            else:
                attrs = ['src', 'data-src', 'data-srcset', 'srcset']

            for attr in attrs:
                value = tag.get(attr)
                if not value:
                    continue

                if attr.endswith('srcset'):
                    rewritten_items = []
                    for item in value.split(','):
                        item = item.strip()
                        if not item:
                            continue
                        parts = item.split()
                        url_part = parts[0]
                        descriptor = ' '.join(parts[1:])
                        if not url_part.startswith(('http://', 'https://')):
                            url_part = urljoin(self.base_url, url_part)
                        rewritten_items.append(' '.join(filter(None, [url_part, descriptor])))
                    tag[attr] = ', '.join(rewritten_items)
                    continue

                if value.startswith(('http://', 'https://')):
                    continue

                tag[attr] = urljoin(self.base_url, value)

            # Если у изображения есть data-src, копируем его в src, чтобы позже скачивать правильные файлы
            if tag.name == 'img':
                data_src = tag.get('data-src')
                if data_src:
                    tag['src'] = data_src

    def process_inline_images(self, article, field_name='content'):
        """Скачивание и локальное сохранение изображений из контента статьи"""
        html_content = getattr(article, field_name, '')
        if not html_content:
            return

        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        if not images:
            return

        content_changed = False
        media_prefix = settings.MEDIA_URL or '/media/'

        for img_tag in images:
            src = self._extract_image_source(img_tag)
            if not src:
                continue

            # Пропускаем уже локальные изображения или data-URL
            if src.startswith('data:') or src.startswith(media_prefix):
                continue

            absolute_src = urljoin(self.base_url, src)
            try:
                response = self.session.get(absolute_src, timeout=30)
                response.raise_for_status()
            except Exception as exc:
                if self.verbose:
                    self.stdout.write(self.style.WARNING(
                        f"Не удалось скачать изображение {absolute_src}: {exc}"
                    ))
                continue

            content_type = response.headers.get('Content-Type', '').split(';')[0]
            extension = self._guess_extension(content_type, absolute_src)
            filename = f"blog/content/{article.slug}-{uuid.uuid4().hex[:8]}{extension}"

            try:
                saved_path = default_storage.save(filename, ContentFile(response.content))
                stored_url = default_storage.url(saved_path)
                img_tag['src'] = stored_url
                content_changed = True
            except Exception as exc:
                if self.verbose:
                    self.stdout.write(self.style.WARNING(
                        f"Не удалось сохранить изображение {absolute_src}: {exc}"
                    ))
                continue

        if content_changed:
            setattr(article, field_name, str(soup))
            article.save(update_fields=[field_name])

    def _guess_extension(self, content_type, src):
        """Определение расширения файла по заголовку или URL"""
        if content_type:
            ext = mimetypes.guess_extension(content_type)
            if ext:
                return ext

        path_ext = os.path.splitext(urlparse(src).path)[1]
        if path_ext:
            return path_ext

        return '.jpg'

    def _extract_image_source(self, img_tag):
        """Выбор наиболее релевантного URL изображения"""
        candidates = [
            img_tag.get('src'),
            img_tag.get('data-src'),
            img_tag.get('data-original'),
        ]

        srcset = img_tag.get('srcset') or img_tag.get('data-srcset')
        if srcset:
            first_item = srcset.split(',')[0].strip()
            if first_item:
                first_url = first_item.split()[0]
                candidates.append(first_url)

        for candidate in candidates:
            if not candidate:
                continue
            candidate = candidate.strip()
            if not candidate or candidate.startswith('data:'):
                continue
            if not candidate.startswith(('http://', 'https://')):
                candidate = urljoin(self.base_url, candidate)
            return candidate

        return None

    def extract_featured_image(self, soup):
        """Извлечение главного изображения статьи"""
        # Ищем изображения в различных местах в порядке приоритета
        image_selectors = [
            # 1. Сначала проверяем meta tags
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            
            # 2. Ищем главные изображения в специальных контейнерах
            '.el-image img',  # YooTheme структура
            '.featured-image img',
            '.article-image img', 
            '.post-image img',
            '.hero-image img',
            '.main-image img',
            
            # 3. Ищем первое крупное изображение в article/main контейнере
            'article img:first-of-type',
            'main img:first-of-type',
            '.uk-article img:first-of-type',
            
            # 4. Ищем изображения из кэша yootheme (главные изображения)
            'img[src*="/templates/yootheme/cache/"]',
            
            # 5. Ищем изображения из директорий блога
            'img[src*="/images/For_blog/"]',
            'img[src*="blog"]',
            'img[src*="news"]'
        ]
        
        # Сначала проверяем meta теги
        for selector in image_selectors[:2]:
            element = soup.select_one(selector)
            if element:
                image_url = element.get('content')
                if image_url:
                    full_url = urljoin(self.base_url, image_url)
                    if self.is_valid_article_image(image_url):
                        return full_url
        
        # Затем ищем в HTML элементах
        for selector in image_selectors[2:]:
            elements = soup.select(selector)
            for element in elements:
                image_url = element.get('src') or element.get('data-src')
                if image_url and self.is_valid_article_image(image_url):
                    full_url = urljoin(self.base_url, image_url)
                    
                    # Дополнительная проверка размера изображения по URL
                    if self.is_likely_featured_image(image_url):
                        return full_url
        
        return None

    def extract_video_links(self, soup):
        """Извлечение ссылок на видео"""
        videos = []
        
        # Ищем YouTube ссылки
        youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+'
        ]
        
        page_text = soup.get_text()
        for pattern in youtube_patterns:
            matches = re.findall(pattern, page_text)
            videos.extend(matches)
        
        # Ищем ссылки в href атрибутах
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if any(pattern in href for pattern in ['youtube.com', 'youtu.be']):
                videos.append(href)
        
        return list(set(videos))  # Убираем дубликаты

    def extract_youtube_id(self, url):
        """Извлечение ID видео YouTube"""
        youtube_patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None

    def is_valid_image(self, src):
        """Проверка, является ли изображение подходящим"""
        if not src:
            return False
            
        # Исключаем иконки и служебные изображения
        exclude_patterns = [
            '.svg', 'icon-', 'logo', 'avatar', 'telegram', 'whatsapp', 
            'phone', 'email', 'facebook', 'instagram'
        ]
        
        src_lower = src.lower()
        for pattern in exclude_patterns:
            if pattern in src_lower:
                return False
        
        # Включаем только изображения
        include_patterns = ['.jpg', '.jpeg', '.png', '.webp']
        return any(pattern in src_lower for pattern in include_patterns)
    
    def is_valid_article_image(self, src):
        """Улучшенная проверка для изображений статей"""
        if not src:
            return False
            
        src_lower = src.lower()
        
        # Исключаем служебные изображения и элементы интерфейса
        exclude_patterns = [
            '.svg', 'icon-', 'logo', 'avatar', 'telegram', 'whatsapp', 
            'phone', 'email', 'facebook', 'instagram', 'twitter',
            'flag-', 'flags/', 'social', 'btn-', 'button',
            'arrow', 'chevron', 'menu', 'nav', 'header', 'footer',
            'asset%20', 'asset_', 'ue/', 'logos/', '/logos/', 
            'undersun', 'undersunestate'
        ]
        
        for pattern in exclude_patterns:
            if pattern in src_lower:
                return False
        
        # Включаем изображения подходящих форматов
        include_patterns = ['.jpg', '.jpeg', '.png', '.webp']
        return any(pattern in src_lower for pattern in include_patterns)
    
    def is_likely_featured_image(self, src):
        """Дополнительная проверка вероятности быть главным изображением"""
        if not src:
            return False
            
        src_lower = src.lower()
        
        # Приоритетные паттерны для главных изображений
        priority_patterns = [
            '/templates/yootheme/cache/',  # Кэш YooTheme - главные изображения
            '/images/for_blog/',           # Директория изображений блога
            'featured',                    # Слово "featured" в пути
            'hero',                       # Слово "hero" в пути
            'main',                       # Слово "main" в пути
            'cover',                      # Слово "cover" в пути
        ]
        
        # Если изображение содержит приоритетные паттерны - это вероятно главное изображение
        for pattern in priority_patterns:
            if pattern in src_lower:
                return True
        
        # Проверяем размер файла по имени (большие файлы вероятно главные)
        # Ищем числа в имени файла, которые могут указывать на размер
        size_match = re.search(r'(\d{3,4})x(\d{3,4})', src_lower)
        if size_match:
            width, height = int(size_match.group(1)), int(size_match.group(2))
            # Если размер больше 400x300 - вероятно главное изображение
            if width >= 400 and height >= 300:
                return True
        
        return False

    def extract_category_from_url(self, url):
        """Извлечение категории из URL"""
        # URL формат: /ru/blog/{category}/id-title
        if '/blog/' in url:
            parts = url.split('/blog/')
            if len(parts) > 1:
                category_part = parts[1].split('/')[0]
                return category_part
        return 'article'

    def get_or_create_blog_category(self, category_slug, language='ru'):
        """Получить или создать категорию блога"""
        category_names = {
            'news': {'ru': 'Новости', 'en': 'News'},
            'articles': {'ru': 'Статьи', 'en': 'Articles'},
            'cases': {'ru': 'Кейсы', 'en': 'Cases'},
            'reviews': {'ru': 'Обзоры', 'en': 'Reviews'},
            'places': {'ru': 'Места и активности', 'en': 'Places & Activities'},
            'events': {'ru': 'Мероприятия', 'en': 'Events'},
        }

        defaults = {
            'name': category_names.get(category_slug, {}).get('ru', category_slug.title()),
            'description': f'Категория {category_slug}',
            'color': '#007bff'
        }

        category, created = BlogCategory.objects.get_or_create(
            slug=category_slug,
            defaults=defaults
        )
        
        if created and self.verbose:
            self.stdout.write(f"Создана новая категория: {defaults['name']}")

        # Обновляем перевод названия категории, если знаем его значение
        localized_name = category_names.get(category_slug, {}).get(language)
        if localized_name:
            field_name = self._translated_field('name', language)
            if getattr(category, field_name, None) != localized_name:
                setattr(category, field_name, localized_name)
                category.save(update_fields=[field_name])

        return category

    def get_default_author(self):
        """Получить автора по умолчанию"""
        # Ищем пользователя по умолчанию или создаем
        author, created = User.objects.get_or_create(
            username='parser',
            defaults={
                'first_name': 'Blog',
                'last_name': 'Parser',
                'email': 'parser@undersunestate.com',
                'is_active': False  # Служебный пользователь
            }
        )
        return author

    def find_duplicate_article(self, data):
        """Поиск дубликатов статей"""
        # Ищем по original_id
        if data.get('original_id'):
            existing = BlogPost.objects.filter(original_id=data['original_id']).first()
            if existing:
                return existing
        
        # Ищем по заголовку
        if data.get('title'):
            existing = BlogPost.objects.filter(title=data['title']).first()
            if existing:
                return existing
        
        return None

    def save_article(self, data):
        """Сохранение статьи в базе данных"""
        language = data.get('language', 'ru')
        content_field = self._translated_field('content', language)
        excerpt_field = self._translated_field('excerpt', language)
        override_fields = {content_field, excerpt_field}

        clean_data = {
            k: v for k, v in data.items()
            if k not in {'featured_image_url', 'language'}
        }

        duplicate = self.find_duplicate_article(data)
        if duplicate:
            self._is_duplicate = True
            if self.verbose:
                self.stdout.write(self.style.WARNING(f"Найден дубликат: {duplicate.title}"))

            updated = False
            for key, value in clean_data.items():
                if not value:
                    continue

                current_value = getattr(duplicate, key, None)
                if not current_value or key in override_fields:
                    setattr(duplicate, key, value)
                    updated = True

            if updated:
                duplicate.save()
                if clean_data.get(content_field):
                    self.process_inline_images(duplicate, content_field)
                if self.verbose:
                    self.stdout.write(self.style.SUCCESS("Обновлены данные статьи"))

            return duplicate

        self._is_duplicate = False
        clean_data.setdefault('author', self.get_default_author())
        clean_data.setdefault('status', 'published')

        # Если статья создается впервые не на русском, заполняем базовые поля переводами
        if language != 'ru':
            for base_field in ('title', 'excerpt', 'content'):
                if not clean_data.get(base_field):
                    localized_field = self._translated_field(base_field, language)
                    localized_value = clean_data.get(localized_field)
                    if localized_value:
                        clean_data[base_field] = localized_value

        article = BlogPost.objects.create(**clean_data)
        if clean_data.get(content_field):
            self.process_inline_images(article, content_field)

        if self.verbose:
            self.stdout.write(self.style.SUCCESS(f"Создана новая статья: {article.title}"))

        return article

    def save_featured_image(self, article, image_url, language='ru'):
        """Сохранение главного изображения статьи"""
        try:
            # Скачиваем изображение
            response = self.session.get(image_url, timeout=30)
            if response.status_code != 200:
                return
            
            # Создаем временный файл
            img_temp = NamedTemporaryFile(delete=True)
            img_temp.write(response.content)
            img_temp.flush()
            
            # Получаем имя файла из URL
            filename = os.path.basename(urlparse(image_url).path)
            if not filename or '.' not in filename:
                filename = f"article_{article.id}.jpg"
            
            # Сохраняем файл
            field_name = self._get_featured_image_field(language)
            image_field = getattr(article, field_name)
            image_field.save(
                filename,
                File(img_temp),
                save=True
            )
            
            self.stdout.write(f"Сохранено изображение ({language}): {filename}")
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Ошибка сохранения изображения {image_url}: {e}"))
