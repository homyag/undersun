import os
import time
import re
from urllib.parse import urljoin, urlparse
from decimal import Decimal
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.utils import timezone
from apps.properties.models import Property, PropertyType, PropertyImage, Developer, Agent
from apps.locations.models import District, Location


class Command(BaseCommand):
    help = 'Парсинг объектов недвижимости с сайта undersunestate.com'

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = 'https://undersunestate.com'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['all', 'villa', 'condo', 'townhouse', 'land', 'investment', 'business'],
            default='all',
            help='Тип недвижимости для парсинга'
        )
        parser.add_argument(
            '--deal-type',
            type=str,
            choices=['all', 'buy', 'rent'],
            default='all',
            help='Тип сделки (покупка/аренда)'
        )
        parser.add_argument(
            '--test-single',
            type=str,
            help='Парсить только один объект по URL для тестирования'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=5,
            help='Максимальное количество страниц для парсинга'
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

        property_type = options['type']
        deal_type = options['deal_type']
        max_pages = options['max_pages']

        self.stdout.write(f"Начинаем парсинг недвижимости: тип={property_type}, сделка={deal_type}")

        # Получаем URL всех объектов
        property_urls = self.get_property_urls(property_type, deal_type, max_pages)
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
        self.stdout.write(f"Всего обработано: {len(property_urls)}")

    def get_property_urls(self, property_type, deal_type, max_pages):
        """Получить все URL объектов недвижимости"""
        property_urls = []

        # Формируем базовый URL каталога
        if property_type == 'all':
            if deal_type == 'buy':
                catalog_url = f"{self.base_url}/ru/real-estate/buy"
            elif deal_type == 'rent':
                catalog_url = f"{self.base_url}/ru/real-estate/rent"
            else:
                catalog_url = f"{self.base_url}/ru/real-estate"
        else:
            # Карта типов недвижимости к URL
            type_urls = {
                'villa': 'villa',
                'condo': 'condo',
                'townhouse': 'townhouse',
                'land': 'land',
                'investment': 'for-investment',
                'business': 'ready-made-business'
            }
            type_slug = type_urls.get(property_type, property_type)
            catalog_url = f"{self.base_url}/ru/real-estate/{type_slug}"

        page_number = 1
        items_per_page = 20  # Количество объектов на странице
        start_offset = 0

        while page_number <= max_pages:
            # Формируем URL для текущей страницы с offset
            if page_number == 1:
                page_url = catalog_url
            else:
                page_url = f"{catalog_url}?start={start_offset}"

            self.stdout.write(f"Загружаем страницу {page_number} (offset={start_offset}): {page_url}")

            response = self.session.get(page_url)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Ошибка загрузки страницы {page_number}: {response.status_code}"))
                break

            soup = BeautifulSoup(response.content, 'html.parser')

            # Ищем ссылки на объекты на текущей странице
            page_properties = self.extract_properties_from_page(soup)

            # Если объектов на странице не найдено - прекращаем
            if not page_properties:
                if page_number == 1:
                    self.stdout.write(self.style.WARNING(f"На первой странице не найдено объектов"))
                else:
                    self.stdout.write(f"Страница {page_number} пустая, достигнут конец каталога")
                break

            # Добавляем найденные объекты
            new_properties = 0
            for property_url in page_properties:
                if property_url not in property_urls:
                    property_urls.append(property_url)
                    new_properties += 1

            self.stdout.write(f"Найдено {new_properties} новых объектов на странице {page_number}")

            # Если на странице меньше объектов чем обычно - это последняя страница
            if len(page_properties) < items_per_page:
                self.stdout.write(f"Найдено {len(page_properties)} объектов (меньше {items_per_page}), достигнута последняя страница")
                break

            # Если не было новых объектов - прекращаем (все дубликаты)
            if new_properties == 0:
                self.stdout.write(f"Все объекты на странице {page_number} уже были обработаны, прекращаем")
                break

            # Увеличиваем offset для следующей страницы
            start_offset += items_per_page
            page_number += 1

            # Пауза между запросами страниц
            time.sleep(0.5)

        self.stdout.write(f"Всего найдено {len(property_urls)} уникальных объектов на {page_number} страницах")
        return property_urls

    def extract_properties_from_page(self, soup):
        """Извлечение ссылок на объекты с одной страницы"""
        property_urls = []

        # Различные селекторы для ссылок на объекты
        selectors = [
            'a[href*="/ru/real-estate/"]',
            '.property-card a',
            '.listing-item a',
            '.property-link',
            'a[href*="/property/"]'
        ]

        for selector in selectors:
            links = soup.select(selector)
            if links:
                for link in links:
                    href = link.get('href', '')
                    if self.is_valid_property_url(href):
                        full_url = urljoin(self.base_url, href)
                        if full_url not in property_urls:
                            property_urls.append(full_url)

                # Если нашли объекты с первым селектором - используем только их
                if property_urls:
                    break

        return property_urls

    def has_next_page(self, soup, current_page):
        """Проверить есть ли следующая страница"""
        # Ищем пагинацию
        pagination_selectors = [
            '.pagination',
            '.pager',
            '.page-nav',
            '.uk-pagination'
        ]

        for selector in pagination_selectors:
            pagination = soup.select_one(selector)
            if pagination:
                # Ищем ссылку на следующую страницу
                next_page = current_page + 1
                next_links = pagination.find_all('a', string=str(next_page))
                if next_links:
                    return True

                # Ищем кнопку "Далее" или "Next"
                next_buttons = pagination.find_all('a', string=re.compile(r'(Далее|Next|>)', re.I))
                if next_buttons:
                    return True

        return False

    def is_valid_property_url(self, url):
        """Проверка, является ли URL действительным объектом недвижимости"""
        if not url or '/ru/real-estate/' not in url:
            return False

        # URL должен содержать ID объекта (число в начале последнего сегмента)
        path_parts = url.split('/')
        if len(path_parts) >= 4:
            last_part = path_parts[-1]
            # Проверяем, что есть ID в начале (например, 450-1-bedroom-apartment...)
            if re.match(r'\d+-', last_part):
                return True

        return False

    def parse_single_property(self, url):
        """Парсинг одного объекта недвижимости"""
        response = self.session.get(url)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        soup = BeautifulSoup(response.content, 'html.parser')

        # Извлекаем данные объекта
        data = self.extract_property_data(soup, url)

        # Отладочная информация
        if self.verbose:
            self.stdout.write(f"Извлеченные данные:")
            for key, value in data.items():
                if key not in ['description', 'images']:
                    self.stdout.write(f"  {key}: {value}")
            if 'description' in data:
                self.stdout.write(f"  description: {len(data['description'])} символов")
            if 'images' in data:
                self.stdout.write(f"  images: {len(data['images'])} изображений")

        # Создаем или обновляем объект в БД
        property_obj = self.save_property(data)

        # Сохраняем удобства
        if data.get('features'):
            self.save_property_features(property_obj, data['features'])

        # Сохраняем изображения
        if data.get('images'):
            self.save_property_images(property_obj, data['images'])

        return property_obj

    def extract_property_data(self, soup, url):
        """Извлечение данных объекта из HTML страницы"""
        data = {'original_url': url}

        # Извлекаем ID из URL
        original_id_match = re.search(r'/(\d+)-', url)
        if original_id_match:
            data['legacy_id'] = original_id_match.group(1)

        # Заголовок
        title_element = soup.find('h1') or soup.select_one('.property-title') or soup.find('title')
        if title_element:
            data['title'] = title_element.get_text().strip()
        else:
            data['title'] = 'Объект недвижимости'

        # Генерируем slug
        data['slug'] = self.generate_slug(url, data['title'])

        # Описание - ищем по itemprop="description"
        description_content, excerpt = self.extract_property_description(soup)
        data['description'] = description_content
        data['short_description'] = excerpt

        # Извлекаем характеристики
        self.extract_property_characteristics(soup, data)

        # Извлекаем удобства
        data['features'] = self.extract_property_features(soup)

        # Извлекаем цену
        self.extract_property_price(soup, data)

        # Извлекаем изображения
        data['images'] = self.extract_property_images(soup)

        # Определяем тип недвижимости и район
        self.extract_property_type_and_location(soup, url, data)

        # Извлекаем координаты
        self.extract_property_coordinates(soup, data)

        return data

    def extract_property_description(self, soup):
        """Извлечение описания объекта недвижимости с сохранением форматирования"""
        content = ""
        excerpt = ""

        # Ищем описание по itemprop="description"
        description_element = soup.find('div', {'itemprop': 'description'})

        if description_element:
            # Удаляем ненужные элементы, но сохраняем структуру
            for unwanted in description_element(['script', 'style', 'noscript']):
                unwanted.decompose()

            # Получаем все содержимое внутри div с itemprop="description"
            text_content = ''

            # Извлекаем содержимое, сохраняя HTML-теги
            for element in description_element.descendants:
                if hasattr(element, 'name') and element.name:
                    # Это HTML-элемент
                    if element.name in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'br', 'strong', 'b', 'em', 'i', 'u', 'span']:
                        # Сохраняем важные HTML-теги для форматирования
                        continue
                elif hasattr(element, 'string') and element.string and element.string.strip():
                    # Это текстовый узел
                    text_content += element.string.strip() + ' '

            # Берем внутренний HTML, исключая внешний div
            inner_elements = list(description_element.children)
            if inner_elements:
                content_parts = []
                for child in inner_elements:
                    if hasattr(child, 'name') and child.name:
                        # HTML-элемент - сохраняем с тегами
                        content_parts.append(str(child))
                    elif hasattr(child, 'string') and child.string and child.string.strip():
                        # Текстовый узел - оборачиваем в параграф
                        clean_text = child.string.strip()
                        if len(clean_text) > 10:
                            content_parts.append(f'<p>{clean_text}</p>')

                content = '\n'.join(content_parts)

            # Если получили пустой контент, используем весь элемент
            if not content.strip():
                content = ''.join(str(child) for child in description_element.children if str(child).strip())

            # Создаем краткое описание из очищенного текста (максимум 300 символов)
            clean_text = description_element.get_text(separator=' ', strip=True)
            if clean_text:
                if len(clean_text) > 297:  # Оставляем место для "..."
                    excerpt = clean_text[:297] + '...'
                else:
                    excerpt = clean_text

        else:
            # Fallback - ищем описание другими способами
            fallback_selectors = [
                '.property-description',
                '.description',
                '.desc-rea',
                '.uk-panel.desc-rea',
                '[itemprop="description"]'
            ]

            for selector in fallback_selectors:
                element = soup.select_one(selector)
                if element:
                    # Удаляем скрипты и стили
                    for unwanted in element(['script', 'style']):
                        unwanted.decompose()

                    content = str(element)
                    text_content = element.get_text(separator=' ', strip=True)
                    excerpt = text_content[:297] + '...' if len(text_content) > 297 else text_content
                    break

            # Если ничего не найдено - ищем содержательные параграфы
            if not content:
                paragraphs = soup.find_all('p')
                content_paragraphs = []
                for p in paragraphs:
                    text = p.get_text().strip()
                    if len(text) > 50:  # Только содержательные параграфы
                        content_paragraphs.append(str(p))
                        if len(content_paragraphs) >= 5:  # Не более 5 параграфов
                            break

                if content_paragraphs:
                    content = '\n'.join(content_paragraphs)
                    first_p_text = soup.find('p').get_text().strip() if soup.find('p') else ''
                    excerpt = first_p_text[:297] + '...' if len(first_p_text) > 297 else first_p_text

        return content, excerpt

    def extract_property_characteristics(self, soup, data):
        """Извлечение характеристик объекта"""
        # Ищем спальни и ванные комнаты в тексте
        text = soup.get_text().lower()

        # Спальни
        bedroom_patterns = [
            r'(\d+)\s*спальн',
            r'(\d+)\s*bedroom',
            r'(\d+)\s*bed\b'
        ]
        for pattern in bedroom_patterns:
            match = re.search(pattern, text)
            if match:
                data['bedrooms'] = int(match.group(1))
                break

        # Ванные комнаты
        bathroom_patterns = [
            r'(\d+)\s*ванн',
            r'(\d+)\s*bathroom',
            r'(\d+)\s*bath\b'
        ]
        for pattern in bathroom_patterns:
            match = re.search(pattern, text)
            if match:
                data['bathrooms'] = int(match.group(1))
                break

        # Площадь
        area_patterns = [
            r'(\d+(?:\.\d+)?)\s*м²',
            r'(\d+(?:\.\d+)?)\s*m²',
            r'(\d+(?:\.\d+)?)\s*кв\.?\s*м',
            r'(\d+(?:\.\d+)?)\s*sqm'
        ]
        for pattern in area_patterns:
            match = re.search(pattern, text)
            if match:
                data['area_total'] = Decimal(match.group(1))
                break

        # Дополнительные удобства
        amenities_text = text
        data['pool'] = any(word in amenities_text for word in ['бассейн', 'pool', 'swimming'])
        data['parking'] = any(word in amenities_text for word in ['парковка', 'parking', 'garage'])
        data['security'] = any(word in amenities_text for word in ['охрана', 'security', 'guard'])
        data['gym'] = any(word in amenities_text for word in ['спортзал', 'gym', 'fitness'])
        data['furnished'] = any(word in amenities_text for word in ['мебель', 'furnished', 'меблированн'])

    def extract_property_features(self, soup):
        """Извлечение удобств объекта из блоков с иконками"""
        features = []

        # Создаем маппинг alt-текстов иконок к названиям удобств
        feature_mapping = {
            # Английские названия
            'air conditioning': 'Кондиционер',
            'wifi': 'WiFi',
            'pool': 'Бассейн',
            'swimming pool': 'Бассейн',
            'kitchen': 'Кухня',
            'workplace': 'Рабочее место',
            'gym': 'Спортзал',
            'free parking': 'Бесплатная парковка',
            'parking': 'Парковка',
            'shower': 'Душ',
            'elevator': 'Лифт',
            'video surveillance': 'Видеонаблюдение',
            'security': 'Охрана',
            'bath': 'Ванна',
            'bathtub': 'Ванна',
            # Русские названия
            'кондиционер': 'Кондиционер',
            'бассейн': 'Бассейн',
            'кухня': 'Кухня',
            'парковка': 'Парковка',
            'душ': 'Душ',
            'лифт': 'Лифт',
            'видеонаблюдение': 'Видеонаблюдение',
            'охрана': 'Охрана',
            'ванна': 'Ванна',
            'спортзал': 'Спортзал',
        }

        # Ищем блоки с иконками удобств - используем более широкий поиск
        amenity_selectors = [
            '.amenities img',           # Основной блок удобств
            '.amenities-icons img',     # Альтернативный селектор
            '.property-amenities img',  # Возможный вариант
            '.features img',            # Блок характеристик
            '.property-features img',   # Альтернативный вариант
            'img[src*="icon-"]',        # Все изображения с "icon-" в пути
            'img[src*="/icons/"]',      # Все изображения из папки icons
            'img[src*="yootheme"]',     # YooTheme иконки
            'img[src*="UE/ICONS"]',     # UE иконки
        ]

        for selector in amenity_selectors:
            amenity_images = soup.select(selector)
            if self.verbose:
                self.stdout.write(f"    Селектор '{selector}': найдено {len(amenity_images)} изображений")

            for img in amenity_images:
                alt_text = img.get('alt', '').lower().strip()
                src = img.get('src', '')

                if self.verbose:
                    self.stdout.write(f"      img: alt='{alt_text}', src='{src}'")

                # Сначала пробуем по alt-атрибуту
                feature_name = None
                if alt_text in feature_mapping:
                    feature_name = feature_mapping[alt_text]
                else:
                    # Если alt пустой, пробуем определить по имени файла в src
                    src_filename = src.lower()
                    src_mapping = {
                        'icon-air-conditioning': 'Кондиционер',
                        'icon-wifi': 'WiFi',
                        'icon-pool': 'Бассейн',
                        'icon-kitchen': 'Кухня',
                        'icon-workplace': 'Рабочее место',
                        'icon-gym': 'Спортзал',
                        'icon-free-parking': 'Бесплатная парковка',
                        'icon-shower': 'Душ',
                        'elevator': 'Лифт',
                        'cctv': 'Видеонаблюдение',
                        'security-worker': 'Охрана',
                    }

                    for file_key, feature_value in src_mapping.items():
                        if file_key in src_filename:
                            feature_name = feature_value
                            break

                if feature_name and feature_name not in features:
                    features.append(feature_name)
                    if self.verbose:
                        self.stdout.write(f"        ✓ Добавлено: {feature_name}")
                elif not feature_name and (alt_text or 'icon-' in src or '/icons/' in src.lower()) and self.verbose:
                    self.stdout.write(f"        ❌ Не найден маппинг для: alt='{alt_text}', src='{src}'")

        # Дополнительный поиск по тексту для удобств, которые могут быть не в иконках
        text_content = soup.get_text().lower()
        text_features = {
            'Кондиционер': ['кондиционер', 'air conditioning', 'aircon'],
            'WiFi': ['wifi', 'wi-fi', 'вай-фай', 'интернет'],
            'Бассейн': ['бассейн', 'pool', 'swimming pool'],
            'Бесплатная парковка': ['парковка', 'parking', 'garage', 'гараж'],
            'Охрана': ['охрана', 'security', 'guard', 'безопасность'],
            'Спортзал': ['спортзал', 'gym', 'fitness', 'фитнес'],
            'Видеонаблюдение': ['видеонаблюдение', 'cctv', 'surveillance', 'камеры'],
        }

        for feature_name, keywords in text_features.items():
            if feature_name not in features and any(keyword in text_content for keyword in keywords):
                features.append(feature_name)

        # Нормализуем названия удобств к единому стандарту
        normalized_features = []
        feature_normalize_map = {
            'кондиционер': 'Кондиционер',
            'парковка': 'Бесплатная парковка',
            'parking': 'Бесплатная парковка',
            'free parking': 'Бесплатная парковка',
            'спортзал': 'Спортзал',
            'gym': 'Спортзал',
        }

        for feature in features:
            normalized = feature_normalize_map.get(feature.lower(), feature)
            if normalized not in normalized_features:
                normalized_features.append(normalized)

        features = normalized_features

        if self.verbose:
            self.stdout.write(f"  Найденные удобства: {', '.join(features) if features else 'нет'}")

        return features

    def extract_property_price(self, soup, data):
        """Извлечение цены объекта с улучшенной обработкой THB"""
        text = soup.get_text()

        if self.verbose:
            self.stdout.write(f"  Поиск цены в тексте...")

        # Сначала ищем основную цену объекта - точный селектор имеет высший приоритет
        main_price_elements = soup.select('.uk-text-lead.price, .uk-text-lead, .property-price, .price-main, h1, h2')
        specific_price_blocks = []

        for element in main_price_elements:
            element_text = element.get_text().strip()
            if element_text and any(char.isdigit() for char in element_text):
                # Проверяем контекст - исключаем блоки похожих объектов
                element_context = str(element.parent.parent if element.parent and element.parent.parent else element.parent if element.parent else element)

                # Исключаем блоки с похожими объектами
                exclude_indicators = [
                    'similar', 'related', 'other', 'recommendation', 'похожие', 'другие',
                    'property-card', 'property-item', 'listing-item', 'объекты'
                ]

                # Проверяем, что это не блок с множественными объектами
                is_excluded = any(indicator in element_context.lower() for indicator in exclude_indicators)

                # Дополнительная проверка по расположению - основная цена обычно в начале страницы
                element_position = len(soup.get_text()[:soup.get_text().find(element_text)])
                page_length = len(soup.get_text())
                is_in_top_part = element_position < page_length * 0.3  # Первые 30% страницы

                if not is_excluded and is_in_top_part:
                    specific_price_blocks.append(element_text)
                    if self.verbose:
                        self.stdout.write(f"    Найден основной блок цены: '{element_text}' (позиция: {element_position}, исключен: {is_excluded})")

        # Дополнительные блоки цены
        price_elements = soup.select('.price, [class*="price"]')
        general_price_blocks = []

        for element in price_elements:
            element_text = element.get_text().strip()
            if element_text and any(char.isdigit() for char in element_text):
                general_price_blocks.append(element_text)
                if self.verbose:
                    self.stdout.write(f"    Найден блок цены: '{element_text}'")

        # Приоритизируем поиск: сначала основные блоки, потом общие, затем весь текст
        price_text_blocks = specific_price_blocks + general_price_blocks
        if not price_text_blocks:
            price_text_blocks = [text]

        # Улучшенные паттерны для парсинга THB цен
        price_patterns = [
            # THB с символом ฿ (высокий приоритет)
            (r'฿\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)', 'THB', 100),
            (r'(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)\s*฿', 'THB', 100),

            # THB текстом (высокий приоритет)
            (r'(\d{1,3}(?:[,\s]\d{3})*)\s*(?:baht|бат)', 'THB', 90),

            # USD с символом $ (средний приоритет)
            (r'\$\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)', 'USD', 70),
            (r'(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)\s*\$', 'USD', 70),

            # RUB с символом ₽ (средний приоритет)
            (r'₽\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)', 'RUB', 60),
            (r'(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)\s*₽', 'RUB', 60),

            # Миллионы THB (специальные паттерны)
            (r'(\d{1,3}(?:\.\d{1,2})?)\s*(?:million|млн|mil)?\s*(?:baht|฿|бат)', 'THB_MILLION', 95),

            # Большие числа без символов (низкий приоритет, но учитываем контекст)
            (r'(\d{1,3}(?:[,\s]\d{3}){2,})', 'UNKNOWN', 30),  # 7+ цифр с разделителями
            (r'(\d{7,})', 'UNKNOWN', 20),  # Просто большие числа
        ]

        found_prices = []

        for text_block in price_text_blocks:
            for pattern, currency, priority in price_patterns:
                matches = re.findall(pattern, text_block, re.IGNORECASE)
                for match in matches:
                    # Очищаем цену от пробелов и запятых
                    price_str = str(match).replace(' ', '').replace(',', '').replace('.', '')
                    try:
                        price = int(price_str)

                        # Обработка миллионов
                        if currency == 'THB_MILLION':
                            price = price * 1000000
                            currency = 'THB'

                        # Фильтруем разумные цены
                        if currency == 'THB' and 50000 <= price <= 100000000:  # THB: 50k - 100M
                            found_prices.append((price, currency, priority))
                        elif currency == 'USD' and 10000 <= price <= 5000000:  # USD: 10k - 5M
                            found_prices.append((price, currency, priority))
                        elif currency == 'RUB' and 500000 <= price <= 500000000:  # RUB: 500k - 500M
                            found_prices.append((price, currency, priority))
                        elif currency == 'UNKNOWN' and 100000 <= price <= 100000000:  # Неизвестная валюта
                            found_prices.append((price, currency, priority))

                        if self.verbose:
                            self.stdout.write(f"    Найдена цена: {price:,} {currency} (приоритет: {priority})")

                    except ValueError:
                        continue

        if not found_prices:
            if self.verbose:
                self.stdout.write(f"    Цена не найдена")
            data['deal_type'] = 'sale'
            return

        # Для цен с одинаковым приоритетом, выбираем ту которая ближе к заголовку
        if len(found_prices) > 1:
            # Найдем H1 заголовок и его позицию
            h1_element = soup.find('h1')
            if h1_element:
                h1_text = h1_element.get_text()
                h1_position = soup.get_text().find(h1_text)

                # Для каждой цены найдем расстояние до H1
                price_distances = []
                for price, currency, priority in found_prices:
                    # Найдем позицию этой цены в тексте
                    price_str = f"{price:,}".replace(",", " ")  # Формат с пробелами
                    price_position = soup.get_text().find(str(price))
                    if price_position == -1:
                        price_position = soup.get_text().find(price_str)

                    distance = abs(price_position - h1_position) if price_position != -1 else float('inf')
                    price_distances.append((price, currency, priority, distance))

                    if self.verbose:
                        self.stdout.write(f"    Цена {price:,} {currency}: позиция {price_position}, расстояние до H1: {distance}")

                # Сортируем по приоритету, потом по расстоянию до H1 (меньше = лучше)
                price_distances.sort(key=lambda x: (-x[2], x[3]))
                best_price, best_currency, _, best_distance = price_distances[0]

                if self.verbose:
                    self.stdout.write(f"    Выбрана цена ближайшая к H1: {best_price:,} {best_currency} (расстояние: {best_distance})")
            else:
                # Сортируем по приоритету, потом по размеру цены
                found_prices.sort(key=lambda x: (-x[2], -x[0]))
                best_price, best_currency, _ = found_prices[0]
        else:
            best_price, best_currency, _ = found_prices[0]

        if self.verbose:
            self.stdout.write(f"    Все найденные цены: {found_prices}")
            self.stdout.write(f"    Выбранная цена: {best_price:,} {best_currency}")

        # Определяем тип сделки по контексту (приоритет URL)
        url_lower = data.get('original_url', '').lower()
        text_lower = text.lower()

        # Сначала проверяем URL - наиболее надежный источник
        if 'for-sale' in url_lower or '/buy/' in url_lower or '/real-estate/buy' in url_lower:
            is_rent = False
            if self.verbose:
                self.stdout.write(f"    Тип сделки из URL: ПРОДАЖА")
        elif 'for-rent' in url_lower or '/rent/' in url_lower or '/real-estate/rent' in url_lower or 'rental' in url_lower:
            is_rent = True
            if self.verbose:
                self.stdout.write(f"    Тип сделки из URL: АРЕНДА")
        else:
            # Если в URL структура /real-estate/villa/123-... - по умолчанию считаем продажей
            # так как undersunestate.com использует /real-estate/rent для аренды
            if '/real-estate/' in url_lower and '/rent' not in url_lower:
                is_rent = False
                if self.verbose:
                    self.stdout.write(f"    Тип сделки по умолчанию (структура URL): ПРОДАЖА")
            else:
                # Только если URL совсем не помог, ищем в тексте
                is_rent = any(word in text_lower for word in [
                    'аренд', 'rent', 'rental', 'lease', '/мес', 'monthly',
                    'per month', 'в месяц', 'за месяц'
                ])
                if self.verbose:
                    self.stdout.write(f"    Тип сделки из текста: {'АРЕНДА' if is_rent else 'ПРОДАЖА'}")

        # Логика сохранения цены
        if is_rent:
            data['deal_type'] = 'rent'

            # Конвертируем в THB если нужно (примерные курсы)
            if best_currency == 'USD':
                thb_price = best_price * 35  # Примерный курс USD -> THB
            elif best_currency == 'RUB':
                thb_price = best_price * 0.5  # Примерный курс RUB -> THB
            elif best_currency == 'UNKNOWN':
                # Если цена большая, предполагаем что это годовая аренда в THB
                if best_price > 500000:
                    thb_price = best_price // 12  # Делим на 12 месяцев
                else:
                    thb_price = best_price
            else:
                thb_price = best_price

            data['price_rent_monthly_thb'] = Decimal(str(int(thb_price)))

            if self.verbose:
                self.stdout.write(f"    Аренда: {thb_price:,.0f} THB/месяц")
        else:
            data['deal_type'] = 'sale'

            # Конвертируем в THB если нужно
            if best_currency == 'USD':
                thb_price = best_price * 35  # Примерный курс USD -> THB
            elif best_currency == 'RUB':
                thb_price = best_price * 0.5  # Примерный курс RUB -> THB
            elif best_currency == 'UNKNOWN':
                # Предполагаем что это THB
                thb_price = best_price
            else:
                thb_price = best_price

            data['price_sale_thb'] = Decimal(str(int(thb_price)))

            if self.verbose:
                self.stdout.write(f"    Продажа: {thb_price:,.0f} THB")

        # Сохраняем также оригинальную цену если она в другой валюте
        if best_currency == 'USD':
            if is_rent:
                data['price_rent_monthly'] = Decimal(str(best_price))
            else:
                data['price_sale_usd'] = Decimal(str(best_price))
        elif best_currency == 'RUB':
            if is_rent:
                data['price_rent_monthly_rub'] = Decimal(str(best_price))
            else:
                data['price_sale_rub'] = Decimal(str(best_price))

    def extract_property_images(self, soup):
        """Извлечение изображений объекта"""
        images = []
        image_variants = {}  # Храним варианты: {base_name: [(url, width_hint), ...]}
        # width_hint - размер из srcset (например 1479 для "1479w") или 0 если неизвестен

        # Сначала удаляем блоки "похожие предложения" из DOM
        # Ищем секцию с заголовком "Похожие предложения" или "Similar offers"
        similar_headers = soup.find_all(['h2', 'h3', 'h4'], string=lambda text: text and ('похожие' in text.lower() or 'similar' in text.lower()))

        for header in similar_headers:
            # Ищем следующий блок ПОСЛЕ заголовка (обычно это сам блок с похожими)
            next_sibling = header.find_next_sibling()
            if next_sibling:
                # Проверяем что это блок с несколькими объектами
                property_links = next_sibling.select('a[href*="/real-estate/"]')
                if len(property_links) > 1:
                    if self.verbose:
                        self.stdout.write(f"  Удаляем блок похожих предложений после заголовка: {len(next_sibling.select('img'))} изображений, {len(property_links)} объектов")
                    next_sibling.decompose()

            # Удаляем сам заголовок
            header.decompose()

        # Дополнительно удаляем блоки с классами, указывающими на похожие объекты
        similar_selectors = [
            '.similar-properties',
            '.related-properties',
            '[class*="similar"]',
            '[class*="related"]'
        ]

        for selector in similar_selectors:
            similar_blocks = soup.select(selector)
            for block in similar_blocks:
                # Проверяем что это действительно блок с несколькими объектами
                property_links = block.select('a[href*="/real-estate/"]')
                if len(property_links) > 1:  # Если есть ссылки на несколько объектов
                    if self.verbose:
                        self.stdout.write(f"  Удаляем блок с селектором '{selector}': {len(block.select('img'))} изображений, {len(property_links)} объектов")
                    block.decompose()

        # Удаляем все блоки с множественными ссылками на объекты (это явно похожие предложения)
        all_divs = soup.find_all(['div', 'section', 'article'])
        for div in all_divs:
            property_links = div.find_all('a', href=lambda href: href and '/real-estate/' in href and re.search(r'/\d+-', href))
            # Если в блоке больше 2 ссылок на разные объекты недвижимости - это похожие предложения
            if len(property_links) > 2:
                unique_links = set([link.get('href') for link in property_links])
                if len(unique_links) > 2:
                    if self.verbose:
                        self.stdout.write(f"  Удаляем блок с множественными ссылками: {len(div.select('img'))} изображений, {len(unique_links)} уникальных объектов")
                    div.decompose()

        # Сначала парсим <picture><source> элементы (приоритет - здесь обычно лучшее качество!)
        picture_sources = soup.select('picture source[srcset]')
        if self.verbose:
            self.stdout.write(f"  Найдено <picture><source> элементов: {len(picture_sources)}")

        for source in picture_sources:
            srcset = source.get('srcset', '')
            if srcset:
                # Парсим srcset: "image1.webp 768w, image2.webp 1024w, image3.webp 1920w"
                for srcset_item in srcset.split(','):
                    srcset_item = srcset_item.strip()
                    # Извлекаем URL и размер
                    parts = srcset_item.split()
                    if parts:
                        src = parts[0]
                        if src and self.is_valid_property_image(src):
                            full_url = urljoin(self.base_url, src)
                            base_name = self.get_image_base_name(src)

                            if base_name:
                                if base_name not in image_variants:
                                    image_variants[base_name] = []
                                if full_url not in image_variants[base_name]:
                                    image_variants[base_name].append(full_url)
                                    if self.verbose:
                                        self.stdout.write(f"    Добавлено из <source srcset>: {full_url}")

        # Ищем изображения в различных местах - расширенный список селекторов
        image_selectors = [
            # Основные изображения в контенте
            'img[src*="/images/"]',
            'img[data-src*="/images/"]',

            # Галереи и слайдеры
            '.gallery img',
            '.slider img',
            '.property-gallery img',
            '.swiper img',
            '.carousel img',

            # YooTheme и Joomla структуры
            'img[src*="yootheme"]',
            'img[src*="templates"]',
            'img[src*="cache"]',

            # Общие изображения в контенте
            'main img',
            'article img',
            '.content img',

            # Lazy loading изображения
            'img[data-lazy]',
            'img[loading="lazy"]',

            # Все изображения с большими размерами в URL
            'img[src*="800"]',
            'img[src*="1200"]',
            'img[src*="1920"]',

            # Общий поиск изображений
            'img'
        ]

        for selector in image_selectors:
            img_elements = soup.select(selector)
            for img in img_elements:
                # Собираем все возможные источники изображения
                sources = []

                # Основной src
                if img.get('src'):
                    sources.append(img.get('src'))

                # data-src (lazy loading)
                if img.get('data-src'):
                    sources.append(img.get('data-src'))

                # data-lazy
                if img.get('data-lazy'):
                    sources.append(img.get('data-lazy'))

                # data-original
                if img.get('data-original'):
                    sources.append(img.get('data-original'))

                # srcset - ВАЖНО: здесь могут быть версии в лучшем качестве!
                if img.get('srcset'):
                    srcset = img.get('srcset')
                    # Парсим srcset: "image1.webp 800w, image2.webp 1200w, image3.webp 1920w"
                    for srcset_item in srcset.split(','):
                        srcset_item = srcset_item.strip()
                        # Извлекаем URL (первая часть до пробела)
                        url_parts = srcset_item.split()
                        if url_parts:
                            sources.append(url_parts[0])

                # data-srcset
                if img.get('data-srcset'):
                    srcset = img.get('data-srcset')
                    for srcset_item in srcset.split(','):
                        srcset_item = srcset_item.strip()
                        url_parts = srcset_item.split()
                        if url_parts:
                            sources.append(url_parts[0])

                # Обрабатываем все найденные источники
                for src in sources:
                    if src and self.is_valid_property_image(src):
                        full_url = urljoin(self.base_url, src)

                        # Извлекаем базовое имя файла без кэш-хеша
                        # Пример: /templates/yootheme/cache/d2/40_LIVING1-d201ddf5.webp -> 40_LIVING1
                        base_name = self.get_image_base_name(src)

                        if base_name:
                            # Группируем варианты одного изображения
                            if base_name not in image_variants:
                                image_variants[base_name] = []
                            if full_url not in image_variants[base_name]:  # Избегаем дубликатов
                                image_variants[base_name].append(full_url)
                        else:
                            # Если не смогли определить базовое имя, добавляем напрямую
                            if full_url not in images:
                                images.append(full_url)

        # Выбираем лучшее качество для каждого изображения
        for base_name, variants in image_variants.items():
            best_image = self.select_best_image_quality(variants)
            if best_image and best_image not in images:
                images.append(best_image)
                if self.verbose and len(variants) > 1:
                    self.stdout.write(f"  Выбрано лучшее качество для {base_name}: {best_image}")
                    self.stdout.write(f"    Из вариантов: {variants}")

        return images

    def get_image_base_name(self, src):
        """Извлекает базовое имя файла без кэш-хеша и расширения"""
        # Пример: /templates/yootheme/cache/d2/40_LIVING1-d201ddf5.webp -> 40_LIVING1
        # Пример: /templates/yootheme/cache/d8/40_LIVING1-d87d1c3c.jpeg -> 40_LIVING1

        filename = os.path.basename(src)

        # Удаляем расширение
        name_without_ext = os.path.splitext(filename)[0]

        # Удаляем кэш-хеш (обычно после последнего дефиса)
        # 40_LIVING1-d201ddf5 -> 40_LIVING1
        if '-' in name_without_ext:
            base_name = name_without_ext.rsplit('-', 1)[0]
            return base_name

        return name_without_ext

    def select_best_image_quality(self, image_urls):
        """Выбирает изображение лучшего качества из вариантов"""
        if not image_urls:
            return None

        if len(image_urls) == 1:
            return image_urls[0]

        # Приоритеты форматов (webp обычно лучше)
        format_priority = {'.webp': 3, '.png': 2, '.jpg': 1, '.jpeg': 1}

        # Оцениваем каждое изображение
        scored_images = []
        for url in image_urls:
            score = 0
            url_lower = url.lower()

            # Приоритет формата
            for ext, priority in format_priority.items():
                if ext in url_lower:
                    score += priority * 100
                    break

            # Приоритет более короткому хешу в пути (обычно это оригинал или лучшее качество)
            # /cache/d2/... лучше чем /cache/d87d1c3c/...
            cache_match = re.search(r'/cache/([a-f0-9]+)/', url_lower)
            if cache_match:
                hash_len = len(cache_match.group(1))
                # Чем короче хеш, тем выше приоритет
                score += (10 - min(hash_len, 10)) * 10

            # Приоритет размерам в URL
            if '1920' in url_lower or '1200' in url_lower:
                score += 50
            elif '800' in url_lower:
                score += 30

            scored_images.append((score, url))

        # Сортируем по убываниюScore и возвращаем лучший
        scored_images.sort(reverse=True, key=lambda x: x[0])

        if self.verbose and len(scored_images) > 1:
            self.stdout.write(f"    Оценки изображений:")
            for score, url in scored_images:
                self.stdout.write(f"      {score}: {url}")

        return scored_images[0][1]

    def extract_property_type_and_location(self, soup, url, data):
        """Определение типа недвижимости и локации"""
        # Извлекаем из URL
        url_parts = url.split('/')

        # Тип недвижимости из URL или контента - порядок важен (от более специфичного к общему)
        type_mapping = [
            ('apartment', 'condo'),
            ('condominium', 'condo'),
            ('condo', 'condo'),
            ('townhouse', 'townhouse'),
            ('villa', 'villa'),
            ('house', 'villa'),
            ('land-plot', 'land'),  # Более специфичное сначала
            ('land', 'land'),
        ]

        # Ищем в URL - приоритет более специфичным терминам
        for url_type, db_type in type_mapping:
            if url_type in url.lower():
                data['property_type'] = db_type
                if self.verbose:
                    self.stdout.write(f"  Тип недвижимости из URL: '{url_type}' -> {db_type}")
                break

        # Если не найдено в URL, ищем в тексте
        if 'property_type' not in data:
            text = soup.get_text().lower()
            for text_type, db_type in type_mapping:
                if text_type in text:
                    data['property_type'] = db_type
                    if self.verbose:
                        self.stdout.write(f"  Тип недвижимости из текста: '{text_type}' -> {db_type}")
                    break

        # По умолчанию - вилла
        if 'property_type' not in data:
            data['property_type'] = 'villa'

        # Извлекаем район из URL - правильная структура:
        # https://undersunestate.com/ru/real-estate/thalang/cherng-talay/450-1-bedroom-apartment
        # url_parts = ['https:', '', 'undersunestate.com', 'ru', 'real-estate', 'thalang', 'cherng-talay', '450-...']
        if len(url_parts) >= 8 and 'real-estate' in url_parts:
            real_estate_index = url_parts.index('real-estate')
            if real_estate_index + 2 < len(url_parts):
                district_slug = url_parts[real_estate_index + 1]  # thalang
                location_slug = url_parts[real_estate_index + 2]  # cherng-talay

                data['district_slug'] = district_slug
                data['location_slug'] = location_slug

    def extract_property_coordinates(self, soup, data):
        """Извлечение координат объекта из ссылки на Google Maps"""
        if self.verbose:
            self.stdout.write(f"  Поиск координат...")

        # Ищем ссылки на Google Maps с координатами
        map_selectors = [
            'a[href*="google.com/maps"]',
            'a[href*="maps.google.com"]',
            'a[href*="goo.gl/maps"]',
            '.map-link',
            '.location-link'
        ]

        coordinates_found = False

        for selector in map_selectors:
            map_links = soup.select(selector)

            for link in map_links:
                href = link.get('href', '')
                if not href:
                    continue

                if self.verbose:
                    self.stdout.write(f"    Проверяем ссылку: {href}")

                # Паттерны для извлечения координат из различных форматов Google Maps ссылок
                coordinate_patterns = [
                    # Формат: http://www.google.com/maps/place/8.020924818147838,98.3133195880343
                    r'/place/(-?\d+\.\d+),(-?\d+\.\d+)',
                    # Формат: https://maps.google.com/maps?q=8.020924818147838,98.3133195880343
                    r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)',
                    # Формат: https://www.google.com/maps/@8.020924818147838,98.3133195880343,17z
                    r'/@(-?\d+\.\d+),(-?\d+\.\d+)',
                    # Формат: https://maps.google.com/?ll=8.020924818147838,98.3133195880343
                    r'[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)',
                    # Общий формат: любые два числа через запятую
                    r'(-?\d+\.\d{6,}),(-?\d+\.\d{6,})'
                ]

                for pattern in coordinate_patterns:
                    match = re.search(pattern, href)
                    if match:
                        try:
                            latitude = float(match.group(1))
                            longitude = float(match.group(2))

                            # Проверяем разумность координат (примерно для Таиланда/Юго-Восточной Азии)
                            if 5.0 <= latitude <= 20.0 and 95.0 <= longitude <= 105.0:
                                data['latitude'] = Decimal(str(latitude))
                                data['longitude'] = Decimal(str(longitude))
                                coordinates_found = True

                                if self.verbose:
                                    self.stdout.write(f"    ✅ Найдены координаты: {latitude}, {longitude}")

                                break
                            else:
                                if self.verbose:
                                    self.stdout.write(f"    ❌ Координаты вне допустимого диапазона: {latitude}, {longitude}")

                        except (ValueError, TypeError):
                            continue

                if coordinates_found:
                    break

            if coordinates_found:
                break

        if not coordinates_found:
            if self.verbose:
                self.stdout.write(f"    ❌ Координаты не найдены")

    def is_valid_property_image(self, src):
        """Проверка изображения объекта недвижимости"""
        if not src:
            return False

        src_lower = src.lower()

        # Исключаем служебные изображения
        exclude_patterns = [
            '.svg', 'icon-', 'logo', 'avatar', 'social',
            'telegram', 'whatsapp', 'phone', 'email',
            'button', 'btn-', 'arrow', 'flag-', 'flags/',
        ]

        for pattern in exclude_patterns:
            if pattern in src_lower:
                return False

        # Включаем только подходящие форматы
        include_patterns = ['.jpg', '.jpeg', '.png', '.webp']
        return any(pattern in src_lower for pattern in include_patterns)

    def generate_slug(self, url, title):
        """Генерация slug из URL или заголовка"""
        # Сначала пробуем извлечь slug из URL (после ID)
        url_match = re.search(r'/(\d+)-(.+?)(?:/|$)', url)
        if url_match:
            url_slug = url_match.group(2)
            cleaned_slug = slugify(url_slug)
            if cleaned_slug and len(cleaned_slug) > 3:
                return cleaned_slug[:200]

        # Генерируем из заголовка
        title_slug = slugify(title)
        if title_slug:
            return title_slug[:200]

        # В крайнем случае используем ID
        original_id_match = re.search(r'/(\d+)-', url)
        if original_id_match:
            return f"property-{original_id_match.group(1)}"

        return "no-slug"

    def get_or_create_property_type(self, property_type_name):
        """Получить или создать тип недвижимости"""
        type_mapping = {
            'villa': ('villa', 'Вилла'),
            'condo': ('condo', 'Кондоминиум'),
            'townhouse': ('townhouse', 'Таунхаус'),
            'land': ('land', 'Земельный участок'),
            'investment': ('investment', 'Инвестиции'),
            'business': ('business', 'Готовый бизнес')
        }

        type_name, display_name = type_mapping.get(property_type_name, ('villa', 'Вилла'))

        property_type, created = PropertyType.objects.get_or_create(
            name=type_name,
            defaults={'name_display': display_name}
        )

        if created and self.verbose:
            self.stdout.write(f"Создан новый тип недвижимости: {display_name}")

        return property_type

    def get_or_create_district(self, district_slug, location_slug=None):
        """Получить или создать район и локацию"""
        # Карта районов
        district_mapping = {
            'thalang': 'Thalang',
            'kathu': 'Kathu',
            'muang-phuket': 'Muang Phuket',
            'phuket': 'Phuket'
        }

        district_name = district_mapping.get(district_slug, district_slug.replace('-', ' ').title())

        district, created = District.objects.get_or_create(
            slug=district_slug,
            defaults={'name': district_name}
        )

        if created and self.verbose:
            self.stdout.write(f"Создан новый район: {district_name}")

        location = None
        if location_slug and location_slug != district_slug:
            location_name = location_slug.replace('-', ' ').title()
            location, created = Location.objects.get_or_create(
                slug=location_slug,
                district=district,
                defaults={'name': location_name}
            )

            if created and self.verbose:
                self.stdout.write(f"Создана новая локация: {location_name}")

        return district, location

    def find_duplicate_property(self, data):
        """Поиск дубликатов объектов"""
        # Ищем по legacy_id
        if data.get('legacy_id'):
            existing = Property.objects.filter(legacy_id=data['legacy_id']).first()
            if existing:
                return existing

        # Ищем по заголовку
        if data.get('title'):
            existing = Property.objects.filter(title=data['title']).first()
            if existing:
                return existing

        return None

    def save_property(self, data):
        """Сохранение объекта недвижимости в базе данных"""
        # Убираем поля, которых нет в модели
        clean_data = {k: v for k, v in data.items() if k not in ['images', 'original_url', 'property_type', 'district_slug', 'location_slug', 'features']}

        # Ищем дубликаты
        duplicate = self.find_duplicate_property(data)
        if duplicate:
            self._is_duplicate = True
            if self.verbose:
                self.stdout.write(self.style.WARNING(f"Найден дубликат: {duplicate.title}"))

            # Обновляем данные дубликата
            updated = False
            for key, value in clean_data.items():
                if value and (not getattr(duplicate, key, None) or key in ['description']):
                    setattr(duplicate, key, value)
                    updated = True

            if updated:
                duplicate.save()
                if self.verbose:
                    self.stdout.write(self.style.SUCCESS(f"Обновлены данные объекта"))

            return duplicate

        # Создаем новый объект
        self._is_duplicate = False

        # Получаем или создаем тип недвижимости
        property_type = self.get_or_create_property_type(data.get('property_type', 'villa'))
        clean_data['property_type'] = property_type

        # Получаем или создаем район и локацию
        district, location = self.get_or_create_district(
            data.get('district_slug', 'phuket'),
            data.get('location_slug')
        )
        clean_data['district'] = district
        if location:
            clean_data['location'] = location

        # Устанавливаем значения по умолчанию
        clean_data['status'] = 'available'
        clean_data['is_active'] = True

        property_obj = Property.objects.create(**clean_data)

        if self.verbose:
            self.stdout.write(self.style.SUCCESS(f"Создан новый объект: {property_obj.title}"))

        return property_obj

    def save_property_features(self, property_obj, feature_names):
        """Сохранение связей объекта с удобствами"""
        from apps.properties.models import PropertyFeature, PropertyFeatureRelation

        if not feature_names:
            return

        # Очищаем существующие связи для этого объекта
        PropertyFeatureRelation.objects.filter(property=property_obj).delete()

        for feature_name in feature_names:
            # Ищем или создаем удобство
            feature, created = PropertyFeature.objects.get_or_create(
                name=feature_name,
                defaults={'icon': self.get_default_icon_for_feature(feature_name)}
            )

            if created and self.verbose:
                self.stdout.write(f"    Создано новое удобство: {feature_name}")

            # Создаем связь, если её ещё нет
            relation, created = PropertyFeatureRelation.objects.get_or_create(
                property=property_obj,
                feature=feature
            )

        if self.verbose:
            self.stdout.write(f"  Сохранено удобств: {len(feature_names)}")

    def get_default_icon_for_feature(self, feature_name):
        """Получение иконки по умолчанию для удобства"""
        icon_mapping = {
            'Кондиционер': 'fas fa-snowflake',
            'WiFi': 'fas fa-wifi',
            'Бассейн': 'fas fa-swimming-pool',
            'Кухня': 'fas fa-utensils',
            'Парковка': 'fas fa-parking',
            'Бесплатная парковка': 'fas fa-parking',
            'Душ': 'fas fa-shower',
            'Лифт': 'fas fa-elevator',
            'Видеонаблюдение': 'fas fa-video',
            'Охрана': 'fas fa-shield-alt',
            'Ванна': 'fas fa-bath',
            'Спортзал': 'fas fa-dumbbell',
            'Рабочее место': 'fas fa-laptop',
        }
        return icon_mapping.get(feature_name, 'fas fa-check')

    def save_property_images(self, property_obj, image_urls):
        """Сохранение изображений объекта"""
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
                    filename = f"property_{property_obj.id}_{i}.jpg"

                # Создаем объект изображения
                property_image = PropertyImage.objects.create(
                    property=property_obj,
                    title=f"Изображение {i+1}",
                    is_main=(i == 0),  # Первое изображение делаем главным
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