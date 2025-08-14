import json
import re
import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.properties.models import Property, PropertyType, PropertyImage, PropertyFeature
from apps.locations.models import District, Location
from django.core.files import File
from django.core.files.base import ContentFile
import requests
from urllib.parse import urljoin
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Migrate data from PostgreSQL Joomla database to Django'
    
    def __init__(self):
        super().__init__()
        self.field_mapping = {
            # Основные поля недвижимости
            'price': 66,  # Price (baht)
            'land_size_rai': 76,  # Land size (rai)
            'buildings_number': 77,  # Buildings number
            'foundation_date': 78,  # Foundation date
            'completion_date': 79,  # Completion date
            'bathrooms': 80,  # Bathrooms
            'bedrooms': 81,  # Bedrooms
            'living_area': 82,  # Living area (sqm)
            'floor_number': 83,  # Floor number
            'total_floors': 84,  # Total floors
            'furnished': 85,  # Furnished
            'rental_guarantee': 86,  # Rental guarantee
            'resale': 87,  # Resale
            'leasehold_freehold': 88,  # Leasehold/Freehold
            'property_type': 89,  # Property type
            'deal_type': 90,  # Deal type
            'price_usd': 91,  # Price (USD)
            
            # Дополнительные поля
            'location': 17,  # Location (coordinates)
            'images': 3,  # Images
            'amenities': 6,  # Amenities
            'characteristics': 7,  # Features
            'double_beds': 60,  # Double Beds
            'single_beds': 61,  # Single Beds
            'sofa_beds': 62,  # Sofa Beds
        }
        
        # Маппинг категорий районов
        self.district_mapping = {
            9: 'Mueang Phuket',
            14: 'Kathu',
            15: 'Thalang'
        }
        
        # Маппинг локаций
        self.location_mapping = {
            10: ('Ko Kaeo', 9),
            12: ('Wichit', 9),
            13: ('Rawai', 9),
            28: ('Chalong', 9),
            29: ('Ratsada', 9),
            34: ('Karon', 9),
            40: ('Talad Nuea', 9),
            47: ('Talad Yai', 9),
            30: ('Patong', 14),
            31: ('Kamala', 14),
            33: ('Kathu', 14),
            35: ('Pa Khlok', 15),
            36: ('Thep Krasattri', 15),
            37: ('Si Sunthon', 15),
            38: ('Cherng Talay', 15),
            39: ('Mai Khao', 15),
            41: ('Sakhu', 15),
        }
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--db-name',
            type=str,
            help='PostgreSQL database name',
            default='joomla_import'
        )
        parser.add_argument(
            '--host',
            type=str,
            help='PostgreSQL host',
            default='localhost'
        )
        parser.add_argument(
            '--port',
            type=str,
            help='PostgreSQL port',
            default='5432'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='PostgreSQL user',
            default=''
        )
        parser.add_argument(
            '--password',
            type=str,
            help='PostgreSQL password',
            default=''
        )
        parser.add_argument(
            '--media-url',
            type=str,
            help='Base URL for downloading media files',
            default='https://undersunestate.com/'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it'
        )
    
    def handle(self, *args, **options):
        self.db_name = options['db_name']
        self.host = options['host']
        self.port = options['port']
        self.user = options['user']
        self.password = options['password']
        self.media_url = options['media_url']
        self.dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('Starting migration from PostgreSQL Joomla database'))
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be saved'))
        
        try:
            # Подключаемся к PostgreSQL
            conn = psycopg2.connect(
                dbname=self.db_name,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            
            # Проверяем подключение
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            self.stdout.write(f'Connected to PostgreSQL: {version}')
            
            # Миграция объектов недвижимости
            self.migrate_properties(conn)
            
            conn.close()
            
            self.stdout.write(
                self.style.SUCCESS('Migration completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Migration failed: {str(e)}')
            )
            raise
    
    def migrate_properties(self, conn):
        """Миграция объектов недвижимости"""
        self.stdout.write('Migrating properties...')
        
        cursor = conn.cursor()
        
        # Получаем все активные объекты недвижимости
        cursor.execute("""
            SELECT c.* FROM ec9oj_content c
            WHERE c.state = 1
            AND c.title IS NOT NULL
            ORDER BY c.id
        """)
        
        properties = cursor.fetchall()
        
        self.stdout.write(f'Found {len(properties)} properties to migrate')
        
        # Получаем названия колонок
        column_names = [desc[0] for desc in cursor.description]
        
        for prop_row in properties:
            # Конвертируем в словарь для удобства
            prop_data = dict(zip(column_names, prop_row))
            self.migrate_single_property(conn, prop_data)
    
    def migrate_single_property(self, conn, prop_data):
        """Миграция одного объекта недвижимости"""
        cursor = conn.cursor()
        
        # Получаем значения кастомных полей
        field_values = self.get_field_values(cursor, prop_data['id'])
        
        # Определяем локацию по категории
        location = self.get_property_location(cursor, prop_data['catid'])
        
        # Генерируем slug из title
        slug = self.generate_slug(prop_data['title'], prop_data['id'])
        
        # Извлекаем основные данные
        property_data = {
            'title': prop_data['title'],
            'description': self.clean_html(prop_data.get('introtext', '')),
            'slug': slug,
            'is_active': prop_data.get('state', 1) == 1,
            'district': location.district if location else None,
        }
        
        # Добавляем данные из кастомных полей
        if 'price' in field_values:
            try:
                property_data['price_sale_thb'] = float(field_values['price'])
            except (ValueError, TypeError):
                pass
        
        if 'price_usd' in field_values:
            try:
                property_data['price_sale_usd'] = float(field_values['price_usd'])
            except (ValueError, TypeError):
                pass
        
        if 'bedrooms' in field_values:
            try:
                property_data['bedrooms'] = int(field_values['bedrooms'])
            except (ValueError, TypeError):
                pass
        
        if 'bathrooms' in field_values:
            try:
                property_data['bathrooms'] = int(field_values['bathrooms'])
            except (ValueError, TypeError):
                pass
        
        if 'living_area' in field_values:
            try:
                property_data['area_total'] = float(field_values['living_area'])
            except (ValueError, TypeError):
                pass
        
        # Координаты
        if 'location' in field_values:
            coords = field_values['location'].split(',')
            if len(coords) == 2:
                try:
                    property_data['latitude'] = float(coords[0])
                    property_data['longitude'] = float(coords[1])
                except (ValueError, TypeError):
                    pass
        
        # Определяем тип недвижимости
        property_type = self.determine_property_type(field_values, prop_data['catid'])
        
        if not self.dry_run:
            # Создаем объект недвижимости
            property_obj = Property.objects.create(
                location=location,
                property_type=property_type,
                **property_data
            )
            
            # Добавляем изображения
            self.migrate_property_images(cursor, prop_data['id'], property_obj, field_values)
            
            # Добавляем характеристики
            self.migrate_property_features(cursor, prop_data['id'], property_obj, field_values)
            
            self.stdout.write(f'  Created property: {property_data["title"]}')
        else:
            self.stdout.write(f'  Would create property: {property_data["title"]}')
    
    def get_field_values(self, cursor, item_id):
        """Получение значений кастомных полей для объекта"""
        cursor.execute("""
            SELECT f.name, fv.value
            FROM ec9oj_fields_values fv
            JOIN ec9oj_fields f ON fv.field_id = f.id
            WHERE fv.item_id = %s
        """, (str(item_id),))
        
        values = {}
        for row in cursor.fetchall():
            field_name = row[0]
            field_value = row[1]
            
            # Маппинг названий полей
            if field_name == 'price':
                values['price'] = field_value
            elif field_name == 'price-usd':
                values['price_usd'] = field_value
            elif field_name == 'accommodation-location':
                values['location'] = field_value
            elif field_name == 'accommodation-images':
                values['images'] = field_value
            elif field_name == 'characteristics-multilingual':
                values['characteristics'] = field_value
            elif field_name in ['bedrooms', 'bathrooms', 'living-area']:
                values[field_name.replace('-', '_')] = field_value
        
        return values
    
    def get_property_location(self, cursor, catid):
        """Определение локации объекта по категории"""
        if not self.dry_run:
            for location_id, (location_name, district_id) in self.location_mapping.items():
                if location_id == catid:
                    try:
                        return Location.objects.get(name=location_name)
                    except Location.DoesNotExist:
                        pass
            
            # Если не найдено, возвращаем первую локацию или None
            return Location.objects.first()
        return None
    
    def determine_property_type(self, field_values, catid):
        """Определение типа недвижимости"""
        if not self.dry_run:
            # Пытаемся определить тип по кастомным полям или названию категории
            # По умолчанию - вилла
            property_type, created = PropertyType.objects.get_or_create(
                name='villa',
                defaults={'name_display': 'Вилла', 'icon': ''}
            )
            return property_type
        return None
    
    def migrate_property_images(self, cursor, item_id, property_obj, field_values):
        """Миграция изображений объекта"""
        if 'images' in field_values and field_values['images']:
            try:
                # Парсим JSON с изображениями
                images_data = json.loads(field_values['images'])
                
                for i, (key, image_info) in enumerate(images_data.items()):
                    if 'Image' in image_info and image_info['Image']:
                        image_path = image_info['Image']
                        
                        # Скачиваем и сохраняем изображение
                        if self.download_and_save_image(image_path, property_obj, i):
                            self.stdout.write(f'    Added image: {image_path}')
                            
            except (json.JSONDecodeError, KeyError) as e:
                self.stdout.write(
                    self.style.WARNING(f'    Error parsing images for property {item_id}: {e}')
                )
    
    def migrate_property_features(self, cursor, item_id, property_obj, field_values):
        """Миграция характеристик объекта"""
        if 'characteristics' in field_values and field_values['characteristics']:
            try:
                # Парсим JSON с характеристиками
                features_data = json.loads(field_values['characteristics'])
                
                for key, feature_info in features_data.items():
                    feature_en = feature_info.get('Feature EN', '')
                    feature_ru = feature_info.get('Feature RU', '')
                    
                    if feature_en or feature_ru:
                        PropertyFeature.objects.create(
                            property=property_obj,
                            name=feature_en or feature_ru,
                            description=feature_ru if feature_en else ''
                        )
                        
            except (json.JSONDecodeError, KeyError) as e:
                self.stdout.write(
                    self.style.WARNING(f'    Error parsing features for property {item_id}: {e}')
                )
    
    def download_and_save_image(self, image_path, property_obj, order):
        """Скачивание и сохранение изображения"""
        try:
            # Формируем полный URL
            image_url = urljoin(self.media_url, image_path)
            
            # Скачиваем изображение
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Получаем имя файла
            filename = os.path.basename(image_path)
            
            # Создаем объект PropertyImage
            property_image = PropertyImage.objects.create(
                property=property_obj,
                order=order,
                is_main=(order == 0)
            )
            
            # Сохраняем файл
            property_image.image.save(
                filename,
                ContentFile(response.content),
                save=True
            )
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'    Failed to download image {image_path}: {e}')
            )
            return False
    
    def generate_slug(self, title, property_id):
        """Генерация уникального slug из title"""
        if not title:
            return f'property-{property_id}'
        
        # Убираем лишние символы и конвертируем в нижний регистр
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        # Заменяем пробелы на дефисы
        slug = re.sub(r'[-\s]+', '-', slug)
        # Убираем дефисы в начале и конце
        slug = slug.strip('-')
        
        # Ограничиваем длину (оставляем место для ID)
        if len(slug) > 40:
            slug = slug[:40].rstrip('-')
        
        # Если slug пустой, используем ID
        if not slug:
            slug = f'property-{property_id}'
        else:
            # Добавляем ID для уникальности
            slug = f'{slug}-{property_id}'
        
        return slug
    
    def clean_html(self, html_content):
        """Очистка HTML контента"""
        if not html_content:
            return ''
        
        # Убираем HTML теги
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        
        # Убираем лишние пробелы
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text