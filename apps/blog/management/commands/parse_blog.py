import os
import time
import re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.utils import timezone
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
        
        if options['test_single']:
            self.parse_single_article(options['test_single'])
            return

        category = options['category']
        
        # Создаем или получаем категорию блога
        blog_category = self.get_or_create_blog_category(category)
        
        self.stdout.write(f"Начинаем парсинг категории: {category}")
        
        # Получаем URL всех статей в категории
        article_urls = self.get_category_articles(category)
        self.stdout.write(f"Найдено {len(article_urls)} статей для парсинга")
        
        success_count = 0
        error_count = 0
        duplicate_count = 0
        
        for i, url in enumerate(article_urls):
            self.stdout.write(f"Парсинг {i+1}/{len(article_urls)}: {url}")
            try:
                article_obj = self.parse_single_article(url, blog_category)
                if hasattr(self, '_is_duplicate') and self._is_duplicate:
                    duplicate_count += 1
                else:
                    success_count += 1
                    
                # Пауза между запросами
                time.sleep(1) 
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"Ошибка при парсинге {url}: {e}"))
        
        # Итоговая статистика
        self.stdout.write(self.style.SUCCESS(f"\n=== РЕЗУЛЬТАТЫ ПАРСИНГА ==="))
        self.stdout.write(f"Успешно обработано: {success_count}")
        self.stdout.write(f"Найдено дубликатов: {duplicate_count}")  
        self.stdout.write(f"Ошибок: {error_count}")
        self.stdout.write(f"Всего обработано: {len(article_urls)}")

    def get_category_articles(self, category):
        """Получить все URL статей из определенной категории блога с поддержкой пагинации"""
        article_urls = []
        page_number = 1
        start_param = 0
        
        while True:
            # Формируем URL для текущей страницы
            if page_number == 1:
                page_url = f"{self.base_url}/ru/blog/{category}"
            else:
                page_url = f"{self.base_url}/ru/blog/{category}?start={start_param}"
            
            self.stdout.write(f"Загружаем страницу {page_number}: {page_url}")
            
            response = self.session.get(page_url)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Ошибка загрузки страницы {page_number}: {response.status_code}"))
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем ссылки на статьи на текущей странице
            page_articles = self.extract_articles_from_page(soup, category)
            
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
            next_page_url = self.get_next_page_url(soup, category, start_param)
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

    def extract_articles_from_page(self, soup, category):
        """Извлечение ссылок на статьи с одной страницы"""
        article_urls = []
        
        # Пробуем разные селекторы для ссылок на статьи
        selectors = [
            f'a[href*="/ru/blog/{category}/"]',
            f'a[href^="/ru/blog/{category}/"]',
            '.el-item a',
            'article a',
            '.uk-article a'
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                for link in links:
                    href = link.get('href', '')
                    if self.is_valid_article_url(href, category):
                        full_url = urljoin(self.base_url, href)
                        if full_url not in article_urls:
                            article_urls.append(full_url)
                
                # Если нашли статьи с первым селектором - используем только их
                if article_urls:
                    break
        
        return article_urls
    
    def get_next_page_url(self, soup, category, current_start=0):
        """Получить URL следующей страницы пагинации"""
        # Ищем различные варианты ссылок на следующую страницу
        next_selectors = [
            # Классические ссылки пагинации
            f'a[href*="/ru/blog/{category}?start="]',
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
                        if f'/blog/{category}' in href or f'blog/{category}' in href:
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
            if (link_text.isdigit() and 
                int(link_text) > 1 and 
                'start=' in href and 
                f'blog/{category}' in href):
                return urljoin(self.base_url, href)
        
        return None

    def is_valid_article_url(self, url, category):
        """Проверка, является ли URL действительной статьей"""
        if not url or f'/ru/blog/{category}/' not in url:
            return False
        
        # URL должен содержать ID статьи (число)
        path_parts = url.split('/')
        if len(path_parts) >= 4:
            last_part = path_parts[-1]
            # Проверяем, что есть ID в начале (например, 1094-article-title)
            if re.match(r'\d+-', last_part):
                return True
        
        return False

    def parse_single_article(self, url, category=None):
        """Парсинг одной статьи блога"""
        response = self.session.get(url)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Извлекаем данные
        data = self.extract_article_data(soup, url)
        
        # Если категория не указана, определяем из URL
        if not category:
            category_slug = self.extract_category_from_url(url)
            category = self.get_or_create_blog_category(category_slug)
        
        data['category'] = category
        
        # Отладочная информация
        if self.verbose:
            self.stdout.write(f"Извлеченные данные:")
            for key, value in data.items():
                if key not in ['content', 'featured_image_url']:
                    self.stdout.write(f"  {key}: {value}")
            if 'content' in data:
                self.stdout.write(f"  content: {len(data['content'])} символов")
            if 'featured_image_url' in data:
                self.stdout.write(f"  featured_image_url: {data['featured_image_url']}")
        
        # Создаем или обновляем статью в БД
        article_obj = self.save_article(data)
        
        # Сохраняем изображение
        if data.get('featured_image_url'):
            self.save_featured_image(article_obj, data['featured_image_url'])
        
        return article_obj

    def extract_article_data(self, soup, url):
        """Извлечение данных из HTML страницы статьи"""
        data = {'original_url': url}
        
        # Извлекаем original_id из URL
        original_id_match = re.search(r'/(\d+)-', url)
        if original_id_match:
            data['original_id'] = original_id_match.group(1)
        
        # Заголовок статьи
        title_element = soup.find('h1') or soup.select_one('.uk-article-title') or soup.find('title')
        if title_element:
            data['title'] = title_element.get_text().strip()
        else:
            data['title'] = 'Без названия'
        
        # Генерируем slug из URL (более надёжно) или из заголовка
        data['slug'] = self.generate_slug(url, data['title'])
        
        # Дата публикации - ищем в различных местах
        data['published_at'] = self.extract_publication_date(soup, url)
        
        # Основное содержимое статьи
        content, excerpt = self.extract_content(soup)
        data['content'] = content
        data['excerpt'] = excerpt
        
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
            data['content'] += video_html
        
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

    def extract_publication_date(self, soup, url):
        """Извлечение даты публикации"""
        # Попробуем найти дату в различных местах
        date_patterns = [
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # "22 мая 2025"
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # "22.05.2025"
            r'(\d{4})-(\d{1,2})-(\d{1,2})'   # "2025-05-22"
        ]
        
        # Ищем дату в тексте страницы
        page_text = soup.get_text()
        
        # Словарь для преобразования месяцев
        months_ru = {
            'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
            'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
            'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
        }
        
        # Поиск русского формата даты
        ru_date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', page_text)
        if ru_date_match:
            day, month_ru, year = ru_date_match.groups()
            month = months_ru.get(month_ru.lower())
            if month:
                try:
                    date_str = f"{year}-{month}-{day.zfill(2)}"
                    parsed_date = timezone.datetime.strptime(date_str, "%Y-%m-%d")
                    return timezone.make_aware(parsed_date)
                except:
                    pass
        
        # Если дату не нашли, возвращаем текущую
        return timezone.now()

    def extract_content(self, soup):
        """Извлечение содержимого статьи"""
        content = ""
        excerpt = ""
        
        # Удаляем ненужные элементы
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Ищем основной контент в различных контейнерах
        content_selectors = [
            'article',
            '.article-content',
            '.post-content',
            '.content',
            'main',
            '.uk-article'
        ]
        
        content_element = None
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                content_element = element
                break
        
        # Если не нашли специальный контейнер, ищем параграфы
        if not content_element:
            paragraphs = soup.find_all('p')
            if paragraphs:
                content_div = soup.new_tag('div')
                for p in paragraphs:
                    if len(p.get_text().strip()) > 50:  # Только содержательные параграфы
                        content_div.append(p)
                content_element = content_div
        
        if content_element:
            # Очищаем и форматируем HTML
            content = str(content_element)
            
            # Создаем краткое описание из первого абзаца
            first_p = content_element.find('p')
            if first_p:
                excerpt_text = first_p.get_text().strip()
                excerpt = excerpt_text[:500] + '...' if len(excerpt_text) > 500 else excerpt_text
        
        return content, excerpt

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

    def get_or_create_blog_category(self, category_slug):
        """Получить или создать категорию блога"""
        category_names = {
            'news': 'Новости',
            'articles': 'Статьи',
            'cases': 'Кейсы',
            'reviews': 'Обзоры',
            'places': 'Места и активности',
            'events': 'Мероприятия'
        }
        
        category_name = category_names.get(category_slug, category_slug.title())
        
        category, created = BlogCategory.objects.get_or_create(
            slug=category_slug,
            defaults={
                'name': category_name,
                'description': f'Категория {category_name}',
                'color': '#007bff'
            }
        )
        
        if created and self.verbose:
            self.stdout.write(f"Создана новая категория: {category_name}")
            
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
        # Убираем поля, которых нет в модели
        clean_data = {k: v for k, v in data.items() if k != 'featured_image_url'}
        
        # Ищем дубликаты
        duplicate = self.find_duplicate_article(data)
        if duplicate:
            self._is_duplicate = True
            if self.verbose:
                self.stdout.write(self.style.WARNING(f"Найден дубликат: {duplicate.title}"))
            
            # Обновляем данные дубликата
            updated = False
            for key, value in clean_data.items():
                if value and (not getattr(duplicate, key, None) or key in ['content', 'excerpt']):
                    setattr(duplicate, key, value)
                    updated = True
            
            if updated:
                duplicate.save()
                if self.verbose:
                    self.stdout.write(self.style.SUCCESS(f"Обновлены данные статьи"))
            
            return duplicate
        
        # Создаем новую статью
        self._is_duplicate = False
        clean_data['author'] = self.get_default_author()
        clean_data['status'] = 'published'
        
        article = BlogPost.objects.create(**clean_data)
        
        if self.verbose:
            self.stdout.write(self.style.SUCCESS(f"Создана новая статья: {article.title}"))
        
        return article

    def save_featured_image(self, article, image_url):
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
            article.featured_image.save(
                filename,
                File(img_temp),
                save=True
            )
            
            self.stdout.write(f"Сохранено изображение: {filename}")
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Ошибка сохранения изображения {image_url}: {e}"))