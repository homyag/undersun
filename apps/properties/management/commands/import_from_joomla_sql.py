import json
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.properties.models import Property, PropertyType, PropertyImage, PropertyFeature, Developer
from apps.locations.models import District, Location
from django.core.files.base import ContentFile
import random


class Command(BaseCommand):
    help = 'Import properties from Joomla data analysis JSON'
    
    def __init__(self):
        super().__init__()
        
        # Маппинг районов из анализа
        self.district_mapping = {
            9: 'Mueang Phuket',
            14: 'Kathu',
            15: 'Thalang'
        }
        
        # Маппинг локаций с координатами
        self.location_mapping = {
            10: ('Ko Kaeo', 9, 7.9012, 98.3345),
            12: ('Wichit', 9, 7.9324, 98.3621),
            13: ('Rawai', 9, 7.7702, 98.3158),
            28: ('Chalong', 9, 7.8184, 98.3372),
            29: ('Ratsada', 9, 7.8776, 98.3859),
            34: ('Karon', 9, 7.8169, 98.2982),
            30: ('Patong', 14, 7.8965, 98.2945),
            31: ('Kamala', 14, 7.9656, 98.2785),
            33: ('Kathu', 14, 7.9208, 98.3235),
            35: ('Pa Khlok', 15, 8.0234, 98.3856),
            36: ('Thep Krasattri', 15, 8.0123, 98.3456),
            37: ('Si Sunthon', 15, 8.0512, 98.3234),
            38: ('Cherng Talay', 15, 8.0298, 98.2876),
            39: ('Mai Khao', 15, 8.1234, 98.3087),
            40: ('Talad Nuea', 9, 7.8912, 98.3945),
            41: ('Sakhu', 15, 8.1123, 98.3298),
            47: ('Talad Yai', 9, 7.8845, 98.3876),
        }
        
        # Типы недвижимости
        self.property_types = {
            'villa': 'Вилла',
            'apartment': 'Апартаменты',
            'condo': 'Кондоминиум',
            'townhouse': 'Таунхаус',
            'studio': 'Студия',
            'house': 'Дом',
            'land': 'Земельный участок',
        }
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--json-file',
            type=str,
            help='Path to JSON file with analyzed Joomla data',
            default='joomla_properties_analysis.json'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually doing it'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing properties before import'
        )
    
    def handle(self, *args, **options):
        self.json_file = options['json_file']
        self.dry_run = options['dry_run']
        self.clear_existing = options['clear_existing']
        
        self.stdout.write(self.style.SUCCESS('Starting import from Joomla analysis JSON'))
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be saved'))
        
        # Очищаем существующие данные если нужно
        if self.clear_existing and not self.dry_run:
            self.stdout.write('Clearing existing data...')
            Property.objects.all().delete()
            Location.objects.all().delete()
            District.objects.all().delete()
            self.stdout.write('Existing data cleared')
        
        try:
            # Загружаем данные из JSON
            with open(self.json_file, 'r', encoding='utf-8') as f:
                properties_data = json.load(f)
            
            self.stdout.write(f'Loaded {len(properties_data)} properties from JSON')
            
            # Создаем районы и локации
            self.create_districts_and_locations()
            
            # Создаем типы недвижимости
            self.create_property_types()
            
            # Импортируем объекты недвижимости
            self.import_properties(properties_data)
            
            self.stdout.write(
                self.style.SUCCESS('Import completed successfully!')
            )
            
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'JSON file not found: {self.json_file}')
            )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Import failed: {str(e)}')
            )
            raise
    
    def create_districts_and_locations(self):
        """Создание районов и локаций"""
        self.stdout.write('Creating districts and locations...')
        
        if not self.dry_run:
            # Создаем районы
            for district_id, district_name in self.district_mapping.items():
                district, created = District.objects.get_or_create(
                    name=district_name,
                    defaults={
                        'description': f'Район {district_name} на Пхукете',
                        'slug': district_name.lower().replace(' ', '-'),
                    }
                )
                
                if created:
                    self.stdout.write(f'  Created district: {district_name}')
            
            # Создаем локации
            for location_id, (location_name, district_id, lat, lng) in self.location_mapping.items():
                try:
                    district = District.objects.get(name=self.district_mapping[district_id])
                    
                    location, created = Location.objects.get_or_create(
                        name=location_name,
                        district=district,
                        defaults={
                            'description': f'Локация {location_name} в районе {district.name}',
                            'slug': location_name.lower().replace(' ', '-'),
                            'latitude': lat,
                            'longitude': lng,
                        }
                    )
                    
                    if created:
                        self.stdout.write(f'  Created location: {location_name} in {district.name}')
                        
                except District.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'  District not found for location: {location_name}')
                    )
        else:
            self.stdout.write('  Would create districts and locations')
    
    def create_property_types(self):
        """Создание типов недвижимости"""
        self.stdout.write('Creating property types...')
        
        if not self.dry_run:
            for type_slug, type_name in self.property_types.items():
                property_type, created = PropertyType.objects.get_or_create(
                    name=type_slug,
                    defaults={
                        'name_display': type_name,
                        'icon': f'property-{type_slug}.svg',
                    }
                )
                
                if created:
                    self.stdout.write(f'  Created property type: {type_name}')
        else:
            self.stdout.write('  Would create property types')
    
    def import_properties(self, properties_data):
        """Импорт объектов недвижимости"""
        self.stdout.write('Importing properties...')
        
        processed = 0
        skipped = 0
        
        for prop_data in properties_data:
            if self.is_valid_property(prop_data):
                if self.import_single_property(prop_data):
                    processed += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        
        self.stdout.write(f'Processed: {processed}, Skipped: {skipped}')
    
    def is_valid_property(self, prop_data):
        """Проверка валидности данных объекта"""
        # Пропускаем статьи и служебные страницы
        title = prop_data.get('title', '').lower()
        
        # Служебные страницы
        skip_keywords = [
            'landing page', 'homepage', 'selling a land', 'purchase of real estate',
            'purchase in thailand', 'prices in phuket', 'apply for a card',
            'places to visit', 'results of the first', 'market headed', 'condo (full desc.)'
        ]
        
        for keyword in skip_keywords:
            if keyword in title:
                return False
        
        # Должно быть название и категория
        if not prop_data.get('title') or not prop_data.get('category_id'):
            return False
        
        # Категория должна быть числом и в нашем маппинге
        try:
            category_id = int(prop_data['category_id'])
            return category_id in [cat_id for cat_id, _ in self.location_mapping.values() for cat_id in [cat_id]] or \
                   category_id in self.location_mapping
        except (ValueError, TypeError):
            return False
    
    def import_single_property(self, prop_data):
        """Импорт одного объекта недвижимости"""
        try:
            # Определяем локацию
            location = self.determine_location(prop_data)
            if not location and not self.dry_run:
                # Используем случайную локацию если не определили
                location = Location.objects.order_by('?').first()
            
            # Определяем тип недвижимости
            property_type = self.determine_property_type(prop_data)
            
            # Создаем базовые данные объекта
            property_data = {
                'title': prop_data.get('title', '').strip(),
                'description': self.clean_description(prop_data.get('description', '')),
                'slug': self.generate_slug(prop_data),
                'is_active': prop_data.get('published', True),
                'deal_type': self.determine_deal_type(prop_data),
                'bedrooms': prop_data.get('bedrooms', 0) or random.randint(1, 4),
                'bathrooms': prop_data.get('bathrooms', 0) or random.randint(1, 3),
                'area_total': prop_data.get('area_total', 0) or random.randint(80, 300),
                'latitude': self.generate_latitude(location),
                'longitude': self.generate_longitude(location),
            }
            
            # Цены
            if prop_data.get('price_thb'):
                property_data['price_sale_thb'] = Decimal(str(prop_data['price_thb']))
                # Конвертируем в USD (примерный курс 1 USD = 35 THB)
                property_data['price_sale_usd'] = Decimal(str(prop_data['price_thb'])) / 35
            elif prop_data.get('price_usd'):
                property_data['price_sale_usd'] = Decimal(str(prop_data['price_usd']))
                property_data['price_sale_thb'] = Decimal(str(prop_data['price_usd'])) * 35
            else:
                # Генерируем случайную цену
                price_usd = random.randint(100000, 1000000)
                property_data['price_sale_usd'] = Decimal(str(price_usd))
                property_data['price_sale_thb'] = Decimal(str(price_usd * 35))
            
            if not self.dry_run:
                # Создаем объект недвижимости
                property_obj = Property.objects.create(
                    location=location,
                    property_type=property_type,
                    **property_data
                )
                
                # Создаем образец изображения
                self.create_sample_image(property_obj)
                
                # Создаем образцы характеристик
                self.create_sample_features(property_obj)
                
                self.stdout.write(f'  Created property: {property_data["title"]}')
                return True
            else:
                self.stdout.write(f'  Would create property: {property_data["title"]}')
                return True
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  Failed to import property {prop_data.get("title", "Unknown")}: {e}')
            )
            return False
    
    def determine_location(self, prop_data):
        """Определение локации объекта"""
        if self.dry_run:
            return None
        
        try:
            category_id = int(prop_data['category_id'])
            
            # Ищем прямое соответствие в маппинге локаций
            if category_id in self.location_mapping:
                location_name, district_id, _, _ = self.location_mapping[category_id]
                return Location.objects.get(name=location_name)
            
            # Ищем по родительскому району
            for district_id, district_name in self.district_mapping.items():
                if category_id == district_id:
                    # Возвращаем случайную локацию из этого района
                    district = District.objects.get(name=district_name)
                    return Location.objects.filter(district=district).order_by('?').first()
            
        except (ValueError, TypeError, Location.DoesNotExist, District.DoesNotExist):
            pass
        
        return None
    
    def determine_property_type(self, prop_data):
        """Определение типа недвижимости по названию"""
        if self.dry_run:
            return None
        
        title = prop_data.get('title', '').lower()
        
        # Определяем тип по ключевым словам в названии
        if 'villa' in title:
            type_slug = 'villa'
        elif 'apartment' in title or 'bedroom apartment' in title:
            type_slug = 'apartment'
        elif 'condo' in title:
            type_slug = 'condo'
        elif 'studio' in title:
            type_slug = 'studio'
        elif 'townhouse' in title or 'town house' in title:
            type_slug = 'townhouse'
        elif 'house' in title:
            type_slug = 'house'
        else:
            # По умолчанию - вилла
            type_slug = 'villa'
        
        return PropertyType.objects.get(name=type_slug)
    
    def determine_deal_type(self, prop_data):
        """Определение типа сделки"""
        title = prop_data.get('title', '').lower()
        
        if 'rent' in title or 'rental' in title:
            return 'rent'
        else:
            return 'sale'
    
    def generate_slug(self, prop_data):
        """Генерация уникального слага"""
        title = prop_data.get('title', '')
        alias = prop_data.get('alias', '')
        original_id = prop_data.get('original_id', '')
        
        if alias:
            return f"{alias}-{original_id}"
        else:
            # Генерируем из названия
            slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title)
            slug = re.sub(r'\\s+', '-', slug).lower().strip('-')
            return f"{slug}-{original_id}" if slug else f"property-{original_id}"
    
    def generate_latitude(self, location):
        """Генерация случайной широты в районе локации"""
        if location and location.latitude:
            # Добавляем небольшое случайное смещение (±0.01 градуса ≈ ±1км)
            return float(location.latitude) + random.uniform(-0.01, 0.01)
        else:
            # Случайная координата на Пхукете
            return round(random.uniform(7.7, 8.2), 6)
    
    def generate_longitude(self, location):
        """Генерация случайной долготы в районе локации"""
        if location and location.longitude:
            # Добавляем небольшое случайное смещение
            return float(location.longitude) + random.uniform(-0.01, 0.01)
        else:
            # Случайная координата на Пхукете
            return round(random.uniform(98.2, 98.4), 6)
    
    def clean_description(self, description):
        """Очистка описания от HTML и лишних символов"""
        if not description:
            return ''
        
        # Убираем HTML теги
        clean_text = re.sub(r'<[^>]+>', '', description)
        
        # Убираем лишние пробелы и переносы
        clean_text = re.sub(r'\\s+', ' ', clean_text).strip()
        
        # Ограничиваем длину
        if len(clean_text) > 1000:
            clean_text = clean_text[:997] + '...'
        
        return clean_text
    
    def create_sample_image(self, property_obj):
        """Создание образца изображения"""
        try:
            # Создаем простое placeholder изображение
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            # Создаем изображение 800x600
            img = Image.new('RGB', (800, 600), color='lightblue')
            draw = ImageDraw.Draw(img)
            
            # Добавляем текст
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            text = f"Property #{property_obj.id}\\n{property_obj.title[:30]}"
            draw.text((50, 50), text, fill='white', font=font)
            
            # Сохраняем в буфер
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG')
            img_buffer.seek(0)
            
            # Создаем объект изображения
            property_image = PropertyImage.objects.create(
                property=property_obj,
                order=0,
                is_main=True
            )
            
            property_image.image.save(
                f'property_{property_obj.id}.jpg',
                ContentFile(img_buffer.getvalue()),
                save=True
            )
            
        except Exception as e:
            # Если не получилось создать изображение, пропускаем
            pass
    
    def create_sample_features(self, property_obj):
        """Создание образцов характеристик"""
        sample_features = [
            'Парковочное место',
            'Кондиционер',
            'Интернет Wi-Fi',
            'Бассейн',
            'Сад',
            'Терраса',
            'Встроенная кухня',
            'Балкон',
        ]
        
        # Добавляем 3-5 случайных характеристик
        features_count = random.randint(3, 5)
        selected_features = random.sample(sample_features, features_count)
        
        for feature_name in selected_features:
            PropertyFeature.objects.create(
                property=property_obj,
                name=feature_name,
                description=f'Описание: {feature_name}'
            )