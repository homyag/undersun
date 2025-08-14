import os
import time
import re
from decimal import Decimal
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.utils.text import slugify
from apps.properties.models import Property, PropertyType, PropertyImage, Agent
from apps.locations.models import District, Location


class Command(BaseCommand):
    help = 'Парсинг недвижимости с сайта undersunestate.com'

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = 'https://undersunestate.com'
        self.catalog_url = 'https://undersunestate.com/ru/real-estate'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-page',
            type=int,
            default=0,
            help='Начальная страница каталога (default: 0)'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=10,
            help='Максимальное количество страниц для парсинга (default: 10)'
        )
        parser.add_argument(
            '--test-single',
            type=str,
            help='Парсить только одну страницу объекта по URL для тестирования'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод отладочной информации'
        )

    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        
        if options['test_single']:
            self.parse_single_property(options['test_single'])
            return

        start_page = options['start_page']
        max_pages = options['max_pages']
        
        self.stdout.write(f"Начинаем парсинг каталога с страницы {start_page}, максимум {max_pages} страниц")
        
        property_urls = self.get_all_property_urls(start_page, max_pages)
        self.stdout.write(f"Найдено {len(property_urls)} объектов для парсинга")
        
        success_count = 0
        error_count = 0
        duplicate_count = 0
        
        for i, url in enumerate(property_urls):
            self.stdout.write(f"Парсинг {i+1}/{len(property_urls)}: {url}")
            try:
                property_obj = self.parse_single_property(url)
                if hasattr(self, '_is_duplicate') and self._is_duplicate:
                    duplicate_count += 1
                else:
                    success_count += 1
                    
                # Уменьшенная пауза для ускорения
                time.sleep(0.5) 
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"Ошибка при парсинге {url}: {e}"))
        
        # Итоговая статистика
        self.stdout.write(self.style.SUCCESS(f"\n=== РЕЗУЛЬТАТЫ ПАРСИНГА ==="))
        self.stdout.write(f"Успешно обработано: {success_count}")
        self.stdout.write(f"Найдено дубликатов: {duplicate_count}")  
        self.stdout.write(f"Ошибок: {error_count}")
        self.stdout.write(f"Всего обработано: {len(property_urls)}")

    def get_all_property_urls(self, start_page=0, max_pages=10):
        """Получить все URL объектов недвижимости из каталога"""
        property_urls = []
        page = start_page
        
        while len(property_urls) < max_pages * 12:  # ~12 объектов на страницу
            catalog_page_url = f"{self.catalog_url}?start={page * 12}"
            self.stdout.write(f"Загружаем каталог: {catalog_page_url}")
            
            response = self.session.get(catalog_page_url)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Ошибка загрузки каталога: {response.status_code}"))
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем карточки объектов
            property_links = []
            
            # Попробуем разные селекторы для карточек
            selectors = [
                'a[href*="/real-estate/"]',
                '.property-card a',
                '.listing-card a',
                'article a[href*="/real-estate/"]'
            ]
            
            for selector in selectors:
                links = soup.select(selector)
                if links:
                    property_links = links
                    break
            
            if not property_links:
                self.stdout.write(self.style.WARNING(f"Не найдены ссылки на объекты на странице {page}"))
                break
            
            # Собираем URL
            page_urls = []
            for link in property_links:
                href = link.get('href', '')
                if self.is_property_detail_url(href) and href not in property_urls:
                    full_url = urljoin(self.base_url, href)
                    page_urls.append(full_url)
            
            if not page_urls:
                self.stdout.write(f"Достигнут конец каталога на странице {page}")
                break
                
            property_urls.extend(page_urls)
            self.stdout.write(f"Найдено {len(page_urls)} объектов на странице {page}")
            
            page += 1
            if page >= start_page + max_pages:
                break
                
        return property_urls

    def parse_single_property(self, url):
        """Парсинг одного объекта недвижимости"""
        response = self.session.get(url)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Извлекаем данные
        data = self.extract_property_data(soup, url)
        
        # Отладочная информация (только в verbose режиме)
        if self.verbose:
            self.stdout.write(f"Извлеченные данные:")
            for key, value in data.items():
                if key != 'images':
                    self.stdout.write(f"  {key}: {value}")
            self.stdout.write(f"  images: {len(data.get('images', []))} изображений")
        
        # Создаем или обновляем объект в БД
        property_obj = self.save_property(data)
        
        # Сохраняем изображения
        if data.get('images'):
            self.save_images(property_obj, data['images'])
        
        return property_obj

    def extract_property_data(self, soup, url):
        """Извлечение данных из HTML страницы"""
        # Сохраняем URL для анализа типа недвижимости
        self._current_url = url
        data = {'url': url}
        
        # H1 заголовок
        h1 = soup.find('h1')
        data['title'] = h1.get_text().strip() if h1 else 'Без названия'
        
        # Генерируем slug из URL
        path = urlparse(url).path
        data['slug'] = path.split('/')[-1] if path.split('/')[-1] else slugify(data['title'])
        
        # Тип недвижимости
        property_type_text = self.extract_property_type(soup)
        data['property_type'] = self.get_or_create_property_type(property_type_text)
        
        # Проверка на инвестиционность
        data['is_for_investment'] = self.is_investment_property(url, soup)
        
        # Район и локация
        district_name, location_name = self.extract_location(soup, url)
        data['district'] = self.get_or_create_district(district_name)
        if location_name:
            data['location'] = self.get_or_create_location(location_name, data['district'])
        
        # Характеристики (спальни, ванные, площадь)
        characteristics = self.extract_characteristics(soup)
        data.update(characteristics)
        
        # Цена
        data['price_sale_thb'] = self.extract_price(soup)
        
        # Описание
        data['description'] = self.extract_description(soup)
        
        # Координаты карты
        coordinates = self.extract_coordinates(soup)
        data.update(coordinates)
        
        # Изображения
        data['images'] = self.extract_images(soup)
        
        # Legacy ID из URL
        legacy_match = re.search(r'/(\d+)-', url)
        if legacy_match:
            data['legacy_id'] = f"VS{legacy_match.group(1)}"
        
        return data

    def extract_property_type(self, soup):
        """Извлечение типа недвижимости"""
        
        # 1. Ищем в заголовке H1 (УСИЛЕННЫЙ приоритет)
        h1 = soup.find('h1')
        if h1:
            h1_text = h1.get_text().lower()
            # Расширенные ключевые слова с приоритетом
            type_keywords = {
                # Виллы - высокий приоритет
                'вилла': 'вилла',
                'villa': 'вилла',
                # Таунхаусы - высокий приоритет  
                'таунхаус': 'таунхаус',
                'townhouse': 'таунхаус',
                'таунхауса': 'таунхаус',
                # Кондоминиумы
                'кондо': 'кондоминиум',
                'квартир': 'кондоминиум', 
                'apartment': 'кондоминиум',
                'апартамент': 'кондоминиум',
                'студи': 'кондоминиум',
                'studio': 'кондоминиум',
                # Земля
                'земл': 'земельный участок',
                'участок': 'земельный участок',
                'land': 'земельный участок',
                # Бизнес
                'бизнес': 'готовый бизнес',
                'business': 'готовый бизнес'
            }
            
            # Проверяем точные совпадения сначала
            for keyword, prop_type in type_keywords.items():
                if keyword in h1_text:
                    if self.verbose:
                        self.stdout.write(f"Найден тип по H1 '{keyword}': {prop_type}")
                    return prop_type
        
        # 2. Ищем в URL (более надежно чем навигация)
        current_url = getattr(self, '_current_url', '')
        url_keywords = {
            '/townhouse': 'таунхаус',
            '/villa': 'вилла', 
            '/condo': 'кондоминиум',
            '/apartment': 'кондоминиум',
            '/land': 'земельный участок',
            '/business': 'готовый бизнес'
        }
        for url_part, prop_type in url_keywords.items():
            if url_part in current_url:
                return prop_type
        
        # 3. Ищем в breadcrumb или навигационных элементах
        breadcrumbs = soup.find_all(['nav', 'ol', 'ul'], class_=lambda x: x and ('breadcrumb' in x.lower() or 'nav' in x.lower()))
        for breadcrumb in breadcrumbs:
            text = breadcrumb.get_text().lower()
            if 'таунхаус' in text or 'townhouse' in text:
                return 'таунхаус'
            elif 'вилл' in text or 'villa' in text:
                return 'вилла'
            elif any(word in text for word in ['кондо', 'квартир', 'apartment', 'condo']):
                return 'кондоминиум'
        
        # 4. Анализ контента описания
        description_divs = soup.find_all(['div', 'p'], class_=lambda x: x and any(word in x.lower() for word in ['desc', 'content', 'text']))
        for div in description_divs:
            text = div.get_text().lower()
            # Ищем характерные слова в начале описания (первые 200 символов)
            text_start = text[:200]
            if any(word in text_start for word in ['таунхаус', 'townhouse']):
                return 'таунхаус'
            elif any(word in text_start for word in ['вилла', 'villa']):
                return 'вилла'
            elif any(word in text_start for word in ['апартамент', 'квартир', 'apartment', 'studio', 'студи']):
                return 'кондоминиум'
        
        # 5. Ищем в метатегах
        meta_title = soup.find('meta', property='og:title') or soup.find('title')
        if meta_title:
            title_text = meta_title.get('content', '') if meta_title.name == 'meta' else meta_title.get_text()
            title_lower = title_text.lower()
            if 'таунхаус' in title_lower or 'townhouse' in title_lower:
                return 'таунхаус'
            elif 'вилл' in title_lower or 'villa' in title_lower:
                return 'вилла'
            elif any(word in title_lower for word in ['апартамент', 'квартир', 'apartment', 'condo']):
                return 'кондоминиум'
        
        # 6. Анализ по характеристикам (эвристика)
        # Если нашли все предыдущие методы не сработали, попробуем определить по площади и этажности
        area_text = soup.get_text().lower()
        
        # Если упоминается несколько этажей - вероятно вилла или таунхаус
        if any(word in area_text for word in ['этаж', 'floor', 'двухэтажн', 'трехэтажн']):
            # Если площадь большая (>200 м²) - скорее вилла
            area_match = re.search(r'(\d{3,})\s*(?:кв\.?\s*м|m²|кв\. м)', area_text)
            if area_match and int(area_match.group(1)) > 200:
                return 'вилла'
            else:
                return 'таунхаус'
        
        # Если студия или маленькая площадь - кондоминиум  
        if 'студи' in area_text or re.search(r'([1-9]\d)\s*(?:кв\.?\s*м|m²)', area_text):
            return 'кондоминиум'
        
        return 'недвижимость'

    def is_investment_property(self, url, soup):
        """Определение инвестиционного объекта"""
        # 1. Проверка URL - если пришли из раздела for-investment
        if '/for-investment' in url or 'for-investment' in url:
            return True
            
        # 2. Проверка в тексте страницы
        page_text = soup.get_text().lower()
        investment_keywords = [
            'инвест',
            'investment',
            'доходность',
            'рентабельность',
            'rental income',
            'roi',
            'возврат инвестиций'
        ]
        
        for keyword in investment_keywords:
            if keyword in page_text:
                return True
                
        return False

    def extract_location(self, soup, url):
        """Извлечение района и локации"""
        # Извлекаем из URL path
        path_parts = url.split('/')
        district_name = 'Пхукет'
        location_name = None
        
        # Ищем индекс real-estate в URL
        try:
            re_index = path_parts.index('real-estate')
            if len(path_parts) > re_index + 2:
                district_slug = path_parts[re_index + 1]
                location_slug = path_parts[re_index + 2]
                
                # Преобразуем slug в название
                district_name = district_slug.replace('-', ' ').title()
                location_name = location_slug.replace('-', ' ').title()
        except (ValueError, IndexError):
            pass
        
        return district_name, location_name

    def extract_characteristics(self, soup):
        """Извлечение характеристик (спальни, ванные, площадь)"""
        data = {}
        
        # Ищем в grid с характеристиками
        grid = soup.find('div', {'class': 'uk-child-width-1-2'})
        if grid:
            items = grid.find_all('div')
            for item in items:
                text = item.get_text().strip()
                
                # Спальни
                if 'спален' in text.lower():
                    match = re.search(r'(\d+)', text)
                    if match:
                        data['bedrooms'] = int(match.group(1))
                
                # Ванные
                if 'ванн' in text.lower():
                    match = re.search(r'(\d+)', text)
                    if match:
                        data['bathrooms'] = int(match.group(1))
                
                # Площадь
                if 'м²' in text or 'кв' in text.lower():
                    match = re.search(r'(\d+(?:,\d+)?)', text)
                    if match:
                        area_str = match.group(1).replace(',', '.')
                        data['area_total'] = Decimal(area_str)
        
        return data

    def extract_price(self, soup):
        """Извлечение цены"""
        # Пробуем разные селекторы для цены
        price_selectors = [
            'div.uk-text-lead.price',
            '.price',
            '[class*="price"]',
            'div[class*="uk-h1"]'
        ]
        
        for selector in price_selectors:
            price_div = soup.select_one(selector)
            if price_div:
                price_text = price_div.get_text().strip()
                # Ищем числа с возможными разделителями
                price_match = re.search(r'([\d\s,]+)', price_text.replace(' ', ''))
                if price_match:
                    price_str = price_match.group(1).replace(',', '').replace(' ', '')
                    if price_str.isdigit():
                        return Decimal(price_str)
        
        return None

    def extract_description(self, soup):
        """Извлечение описания"""
        # Пробуем разные селекторы для описания
        desc_selectors = [
            'div.uk-panel.desc-rea',
            '[itemprop="description"]',
            '.desc-rea',
            'div[class*="desc"]',
            'div[class*="description"]'
        ]
        
        for selector in desc_selectors:
            desc_div = soup.select_one(selector)
            if desc_div:
                desc_text = desc_div.get_text().strip()
                if len(desc_text) > 50:  # Проверяем, что это не пустое описание
                    return desc_text
        
        # Если не нашли описание в специальных блоках, ищем в параграфах
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            # Ищем параграфы с описанием недвижимости (длинные тексты)
            if len(text) > 100 and any(word in text.lower() for word in ['недвижим', 'дом', 'квартир', 'таунхаус', 'вилла', 'комплекс']):
                return text
        
        return ''

    def extract_coordinates(self, soup):
        """Извлечение координат карты"""
        data = {}
        
        # Ищем данные карты в JavaScript или data атрибутах
        map_div = soup.find('div', {'uk-map': True})
        if map_div:
            # Попробуем найти координаты в атрибутах или скриптах
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'lat' in script.string and 'lng' in script.string:
                    lat_match = re.search(r'"lat":\s*([\d.]+)', script.string)
                    lng_match = re.search(r'"lng":\s*([\d.]+)', script.string)
                    if lat_match and lng_match:
                        data['latitude'] = Decimal(lat_match.group(1))
                        data['longitude'] = Decimal(lng_match.group(1))
                        break
        
        return data

    def extract_images(self, soup):
        """Извлечение URL изображений"""
        images = []
        
        # Ищем галерею изображений в разных контейнерах
        gallery_selectors = [
            '.tm-grid-expand img',
            '.uk-slider-items img', 
            '.el-item img',
            '.gallery img',
            'div[class*="grid"] img',
            'div[class*="slider"] img'
        ]
        
        for selector in gallery_selectors:
            img_tags = soup.select(selector)
            if img_tags:
                for img in img_tags:
                    src = img.get('src') or img.get('data-src')
                    if src and self.is_property_image(src):
                        full_url = urljoin(self.base_url, src)
                        if full_url not in images:  # Избегаем дубликатов
                            images.append(full_url)
                
                # Если нашли изображения в этом селекторе, используем их
                if images:
                    break
        
        # Если ничего не нашли, ищем все изображения на странице
        if not images:
            all_imgs = soup.find_all('img')
            for img in all_imgs:
                src = img.get('src') or img.get('data-src')
                if src and self.is_property_image(src):
                    full_url = urljoin(self.base_url, src)
                    if full_url not in images:
                        images.append(full_url)
        
        return images
    
    def is_property_image(self, src):
        """Проверка, является ли изображение фотографией недвижимости"""
        if not src:
            return False
            
        # Исключаем иконки и служебные изображения
        exclude_patterns = [
            '.svg',
            'icon-',
            'logo',
            'avatar',
            'telegram',
            'whatsapp',
            'phone',
            'email',
            'facebook',
            'instagram'
        ]
        
        src_lower = src.lower()
        for pattern in exclude_patterns:
            if pattern in src_lower:
                return False
        
        # Включаем только изображения недвижимости
        include_patterns = [
            '.jpg',
            '.jpeg', 
            '.png',
            '.webp'
        ]
        
        return any(pattern in src_lower for pattern in include_patterns)
    
    def is_property_detail_url(self, url):
        """Проверка, является ли URL детальной страницей объекта недвижимости"""
        if not url or '/real-estate/' not in url:
            return False
        
        # Исключаем служебные страницы
        exclude_patterns = [
            '/real-estate/buy',
            '/real-estate/rent', 
            '/real-estate/villa',
            '/real-estate/condo',
            '/real-estate/townhouse',
            '/real-estate/land',
            '/real-estate/for-investment',
            '/real-estate/mueang-phuket$',
            '/real-estate/thalang$',
            '/real-estate/kathu$'
        ]
        
        for pattern in exclude_patterns:
            if pattern.endswith('$'):
                # Точное соответствие
                if url.rstrip('/').endswith(pattern[:-1]):
                    return False
            elif pattern in url:
                return False
        
        # Включаем только URL с цифрами (ID объекта) или длинными slug
        path_parts = url.split('/')
        if len(path_parts) >= 6:  # /ru/real-estate/district/location/id-title
            last_part = path_parts[-1]
            # Проверяем, что есть ID в начале или очень длинный slug с описанием
            if re.match(r'\d+-.+', last_part) or len(last_part) > 50:
                return True
        
        return False

    def get_or_create_property_type(self, type_text):
        """Получить или создать тип недвижимости"""
        type_mapping = {
            'таунхаус': 'townhouse',
            'вилла': 'villa', 
            'кондо': 'condo',
            'кондоминиум': 'condo',
            'земельный участок': 'land',
            'земля': 'land',
            'участок': 'land',
            'готовый бизнес': 'business',
            'бизнес': 'business',
            'инвест': 'investment'
        }
        
        # Ищем точное совпадение
        property_type_key = None
        type_text_lower = type_text.lower()
        
        for key, value in type_mapping.items():
            if key in type_text_lower:
                property_type_key = value
                break
        
        # Если тип не найден, оставляем общий
        if not property_type_key:
            property_type_key = 'villa'  # default для неопределенных
            
        property_type, created = PropertyType.objects.get_or_create(
            name=property_type_key,
            defaults={'name_display': type_text.title()}
        )
        
        if self.verbose and created:
            self.stdout.write(f"Создан новый тип: {property_type_key} -> {type_text}")
            
        return property_type

    def get_or_create_district(self, district_name):
        """Получить или создать район"""
        district, created = District.objects.get_or_create(
            name=district_name,
            defaults={
                'slug': slugify(district_name),
                'description': f'Район {district_name}'
            }
        )
        return district

    def get_or_create_location(self, location_name, district):
        """Получить или создать локацию"""
        location, created = Location.objects.get_or_create(
            name=location_name,
            district=district,
            defaults={
                'slug': slugify(location_name),
                'description': f'Локация {location_name} в районе {district.name}'
            }
        )
        return location

    def find_duplicate_property(self, data):
        """Поиск дубликатов по стоимости, спальням, площади и заголовку"""
        from django.db.models import Q
        
        # Критерии для поиска дубликатов
        title = data.get('title', '').strip()
        price = data.get('price_sale_thb')
        bedrooms = data.get('bedrooms')
        area = data.get('area_total')
        
        if not any([title, price, bedrooms, area]):
            return None
        
        # Строим запрос для поиска дубликатов
        query = Q()
        match_count = 0
        
        # Точное совпадение по цене (если есть)
        if price:
            query &= Q(price_sale_thb=price)
            match_count += 1
        
        # Точное совпадение по количеству спален (если есть)
        if bedrooms:
            query &= Q(bedrooms=bedrooms)
            match_count += 1
            
        # Точное совпадение по площади (если есть)
        if area:
            query &= Q(area_total=area)
            match_count += 1
        
        # Частичное совпадение по заголовку (если есть и достаточно критериев)
        if title and match_count >= 2:
            # Убираем общие слова для сравнения
            title_clean = self.clean_title_for_comparison(title)
            if len(title_clean) > 10:  # Только если заголовок достаточно уникальный
                similar_titles = Property.objects.filter(query).exclude(title='')
                for prop in similar_titles:
                    prop_title_clean = self.clean_title_for_comparison(prop.title)
                    # Если более 70% слов совпадают
                    if self.titles_similarity(title_clean, prop_title_clean) > 0.7:
                        return prop
        
        # Поиск по основным критериям
        if match_count >= 2:
            duplicates = Property.objects.filter(query)
            if duplicates.exists():
                return duplicates.first()
        
        return None
    
    def clean_title_for_comparison(self, title):
        """Очистка заголовка от общих слов для сравнения"""
        # Убираем общие слова, которые не несут уникальной информации
        stop_words = [
            'с', 'в', 'на', 'для', 'и', 'или', 'от', 'до', 'по', 'за', 'под', 'над', 'при',
            'пхукет', 'пхукете', 'таиланд', 'комплекс', 'комплексе', 'район', 'районе',
            'недвижимость', 'продажа', 'аренда', 'купить', 'снять', 'новый', 'новом', 'новая',
            'готовый', 'готовая', 'современный', 'современная', 'просторный', 'просторная'
        ]
        
        words = [word.lower().strip('.,!?:;()[]') for word in title.split()]
        clean_words = [word for word in words if word not in stop_words and len(word) > 2]
        return ' '.join(clean_words)
    
    def titles_similarity(self, title1, title2):
        """Вычисление схожести заголовков"""
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return 0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)

    def save_property(self, data):
        """Сохранение объекта недвижимости в БД с проверкой дубликатов"""
        # Убираем поля, которых нет в модели
        clean_data = {k: v for k, v in data.items() if k not in ['images', 'url']}
        
        # Сначала ищем по legacy_id
        if data.get('legacy_id'):
            try:
                property_obj = Property.objects.get(legacy_id=data['legacy_id'])
                # Обновляем существующий объект
                self._is_duplicate = True
                for key, value in clean_data.items():
                    if value:
                        setattr(property_obj, key, value)
                property_obj.save()
                if self.verbose:
                    self.stdout.write(self.style.WARNING(f"Обновлен объект по legacy_id: {property_obj.legacy_id}"))
                return property_obj
            except Property.DoesNotExist:
                pass
        
        # Поиск дубликатов по характеристикам
        duplicate = self.find_duplicate_property(data)
        if duplicate:
            self._is_duplicate = True
            if self.verbose:
                self.stdout.write(self.style.WARNING(f"Найден дубликат: {duplicate.title} (ID: {duplicate.legacy_id or duplicate.id})"))
            
            # Обновляем данные дубликата, если они более полные
            updated = False
            for key, value in clean_data.items():
                if value and (not getattr(duplicate, key, None) or getattr(duplicate, key, None) != value):
                    setattr(duplicate, key, value)
                    updated = True
            
            if updated:
                duplicate.save()
                if self.verbose:
                    self.stdout.write(self.style.SUCCESS(f"Обновлены данные дубликата"))
            
            return duplicate
        
        # Создаем новый объект
        self._is_duplicate = False
        property_obj = Property.objects.create(**clean_data)
        if self.verbose:
            self.stdout.write(self.style.SUCCESS(f"Создан новый объект: {property_obj.legacy_id or property_obj.id}"))
        return property_obj

    def save_images(self, property_obj, image_urls):
        """Сохранение изображений"""
        # Удаляем старые изображения
        property_obj.images.all().delete()
        
        for i, image_url in enumerate(image_urls):
            try:
                # Скачиваем изображение
                response = self.session.get(image_url, timeout=30)
                if response.status_code != 200:
                    continue
                
                # Создаем временный файл
                img_temp = NamedTemporaryFile(delete=True)
                img_temp.write(response.content)
                img_temp.flush()
                
                # Получаем имя файла из URL
                filename = os.path.basename(urlparse(image_url).path)
                if not filename or '.' not in filename:
                    filename = f"image_{i+1}.jpg"
                
                # Создаем объект изображения
                property_image = PropertyImage.objects.create(
                    property=property_obj,
                    title=f"Image {i+1}",
                    is_main=(i == 0),  # Первое изображение - главное
                    order=i
                )
                
                # Сохраняем файл
                property_image.image.save(
                    filename,
                    File(img_temp),
                    save=True
                )
                
                self.stdout.write(f"Сохранено изображение: {filename}")
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Ошибка сохранения изображения {image_url}: {e}"))