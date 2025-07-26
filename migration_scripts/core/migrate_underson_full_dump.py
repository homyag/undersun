#!/usr/bin/env python3
"""
Скрипт полной миграции данных из underson_bd_dump.json
Мигрирует все объекты недвижимости с полным набором полей включая агентов и изображения
"""

import os
import sys
import django
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote
import re
from datetime import datetime

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.properties.models import Property, PropertyType, PropertyImage, Agent, PropertyFeature, PropertyFeatureRelation
from apps.locations.models import District, Location


class UndersonDumpMigrator:
    """Класс для миграции данных из полного дампа underson_bd_dump.json"""
    
    def __init__(self, dump_file_path):
        self.dump_file_path = dump_file_path
        self.data = None
        self.content_data = []
        self.fields_data = []
        self.fields_map = {}
        self.categories_map = {}
        
        # Статистика
        self.stats = {
            'properties_created': 0,
            'properties_updated': 0,
            'agents_created': 0,
            'images_created': 0,
            'features_created': 0,
            'errors': []
        }
        
        # Сопоставление catid с типами недвижимости (расширенное)
        self.property_type_mapping = {
            # Основные категории
            '9': 'townhouse',    # Дома/Таунхаусы
            '28': 'villa',       # Виллы  
            '38': 'condo',   # Кондоминиумы/Апартаменты
            '57': 'land',        # Земельные участки
            
            # Дополнительные категории недвижимости  
            '10': 'villa',       # Дома в Ко Каео (villa)
            '12': 'townhouse',   # Таунхаусы в Вичит (townhouse)
            '13': 'villa',       # Недвижимость в Равай (villa)
            '15': 'villa',       # Недвижимость в Таланг (villa)
            '29': 'townhouse',   # Таунхаусы в Ратсада (townhouse)
            '30': 'condo',   # Апартаменты в Патонг (apartment)
            '31': 'condo',   # Кондо в Камала (apartment)
            '33': 'villa',       # Дома в Катху (villa)
            '34': 'villa',       # Недвижимость в Карон (villa)
            '35': 'villa',       # Виллы люкс (villa)
            '36': 'villa',       # Виллы в Таланг (villa)
            '37': 'villa',       # Дома в Таланг (villa)
            '39': 'villa',       # Виллы в Май Као (villa)
            '40': 'townhouse',   # Таунхаусы у города (townhouse)
            '41': 'villa',       # Дома у Най Янг (villa)
            
            # Исключаемые категории
            '25': None,          # Команда/Сотрудники (пропускаем)
            '26': None,          # Активности/Локации (пропускаем)
            '2': None,           # Страницы сайта (пропускаем)
        }
        
        # Сопоставление field_id с полями модели
        self.field_mapping = {
            '17': 'coordinates',     # GPS координаты "lat,lng"
            '19': 'address',         # Адрес локации
            '66': 'price_sale_thb',  # Цена в THB
            '92': 'area_total',      # Общая площадь
            '95': 'area_land',       # Площадь участка
            '93': 'bedrooms',        # Спальни
            '94': 'bathrooms',       # Ванные
            '60': 'double_beds',     # Двуспальные кровати
            '61': 'single_beds',     # Односпальные кровати
            '62': 'sofa_beds',       # Диван-кровати
            '71': 'title_ru',        # Название на русском
            '72': 'title_th',        # Название на тайском
            '68': 'description_ru',  # Описание на русском
            '69': 'description_th',  # Описание на тайском
            '26': 'agent_id',        # ID агента
            '16': 'floorplan',       # План этажа
            '28': 'intro_image',     # Интро изображение
            '3': 'gallery_images',   # Галерея изображений (JSON)
            '6': 'amenities',        # Удобства (JSON array)
        }
    
    def load_dump(self):
        """Загрузить дамп из JSON файла"""
        print(f"Загружаем дамп из {self.dump_file_path}...")
        
        try:
            with open(self.dump_file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            print(f"✓ Дамп загружен, найдено {len(self.data)} записей")
            return True
        except FileNotFoundError:
            print(f"✗ Файл {self.dump_file_path} не найден")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Ошибка парсинга JSON: {e}")
            return False
    
    def extract_tables(self):
        """Извлечь данные таблиц из дампа"""
        print("Извлекаем таблицы ec9oj_content и ec9oj_fields_values...")
        
        for record in self.data:
            if record.get('type') == 'table':
                table_name = record.get('name')
                table_data = record.get('data', [])
                
                if table_name == 'ec9oj_content':
                    self.content_data = table_data
                    print(f"✓ Найдена таблица ec9oj_content: {len(table_data)} записей")
                
                elif table_name == 'ec9oj_fields_values':
                    self.fields_data = table_data
                    print(f"✓ Найдена таблица ec9oj_fields_values: {len(table_data)} записей")
                
                elif table_name == 'ec9oj_categories':
                    # Сохраним категории для справки
                    for cat in table_data:
                        self.categories_map[cat['id']] = cat
                    print(f"✓ Найдена таблица ec9oj_categories: {len(table_data)} записей")
        
        if not self.content_data:
            print("✗ Таблица ec9oj_content не найдена")
            return False
        
        if not self.fields_data:
            print("✗ Таблица ec9oj_fields_values не найдена")
            return False
        
        return True
    
    def build_fields_mapping(self):
        """Создать сопоставление field_id → item_id → value"""
        print("Создаем сопоставление полей...")
        
        for field_record in self.fields_data:
            field_id = field_record['field_id']
            item_id = field_record['item_id']
            value = field_record['value']
            
            if item_id not in self.fields_map:
                self.fields_map[item_id] = {}
            
            # Для amenities (field_id=6) может быть несколько записей - собираем их в список
            if field_id == '6':
                if field_id not in self.fields_map[item_id]:
                    self.fields_map[item_id][field_id] = []
                self.fields_map[item_id][field_id].append(value)
            else:
                # Для остальных полей сохраняем как обычно
                self.fields_map[item_id][field_id] = value
        
        print(f"✓ Создано сопоставление для {len(self.fields_map)} объектов")
    
    def get_or_create_agent(self, agent_data):
        """Создать или получить агента из данных"""
        if not agent_data or not isinstance(agent_data, dict):
            return None
        
        # Извлекаем ID агента из данных
        agent_id = agent_data.get('id')
        if not agent_id:
            return None
        
        # Ищем существующего агента
        try:
            agent = Agent.objects.get(legacy_id=agent_id)
            return agent
        except Agent.DoesNotExist:
            pass
        
        # Создаем нового агента
        try:
            agent = Agent.objects.create(
                legacy_id=agent_id,
                name=agent_data.get('title', f'Agent {agent_id}'),
                bio=agent_data.get('introtext', ''),
                is_active=agent_data.get('state', '0') == '1'
            )
            self.stats['agents_created'] += 1
            print(f"  ✓ Создан агент: {agent.name}")
            return agent
        except Exception as e:
            self.stats['errors'].append(f"Ошибка создания агента {agent_id}: {e}")
            return None
    
    def process_property_images(self, property_obj, fields_data):
        """Обработать изображения объекта недвижимости"""
        images_created = 0
        
        # Обработка галереи изображений (field_id=3)
        gallery_data = fields_data.get('3')
        if gallery_data:
            try:
                gallery_json = json.loads(gallery_data)
                if isinstance(gallery_json, list):
                    for idx, img_item in enumerate(gallery_json):
                        if isinstance(img_item, dict) and 'image' in img_item:
                            image_path = img_item['image']
                            alt_text = img_item.get('alt', '')
                            
                            # Создаем PropertyImage
                            try:
                                PropertyImage.objects.create(
                                    property=property_obj,
                                    title=alt_text,
                                    image_type='main',
                                    order=idx,
                                    is_main=(idx == 0),
                                    alt_text=alt_text
                                    # Поле image заполним позже при загрузке файлов
                                )
                                images_created += 1
                            except Exception as e:
                                self.stats['errors'].append(f"Ошибка создания изображения галереи: {e}")
            except json.JSONDecodeError:
                self.stats['errors'].append(f"Ошибка парсинга галереи для объекта {property_obj.legacy_id}")
        
        # Обработка плана этажа (field_id=16)
        floorplan_data = fields_data.get('16')
        if floorplan_data:
            try:
                PropertyImage.objects.create(
                    property=property_obj,
                    title='План этажа',
                    image_type='floorplan',
                    order=999,
                    is_main=False
                    # Поле image заполним позже
                )
                images_created += 1
            except Exception as e:
                self.stats['errors'].append(f"Ошибка создания плана этажа: {e}")
        
        # Обработка интро изображения (field_id=28)
        intro_image_data = fields_data.get('28')
        if intro_image_data:
            try:
                PropertyImage.objects.create(
                    property=property_obj,
                    title='Интро изображение',
                    image_type='intro',
                    order=998,
                    is_main=False
                    # Поле image заполним позже
                )
                images_created += 1
            except Exception as e:
                self.stats['errors'].append(f"Ошибка создания интро изображения: {e}")
        
        self.stats['images_created'] += images_created
        return images_created
    
    def process_amenities(self, property_obj, amenities_data):
        """Обработать удобства из field_id=6 и создать PropertyFeatureRelation"""
        if not amenities_data:
            return 0
        
        amenities_created = 0
        
        # amenities_data может быть строкой или списком строк
        amenities_list = amenities_data if isinstance(amenities_data, list) else [amenities_data]
        
        # Сопоставление иконок с названиями amenities (полный список из 26 элементов)
        amenity_mapping = {
            'air-conditioning': 'Кондиционер',
            'wifi': 'WiFi',
            'pool': 'Бассейн',
            'kitchen': 'Кухня',
            'microwave': 'Микроволновая печь',
            'dishwasher': 'Посудомоечная машина',
            'washer': 'Стиральная машина',
            'sauna': 'Сауна',
            'coffee-maker': 'Кофеварка',
            'tv': 'Телевизор',
            'workplace': 'Рабочее место',
            'fireplace': 'Камин',
            'gym': 'Тренажерный зал',
            'free-parking': 'Бесплатная парковка',
            'bbq-zone': 'Зона барбекю',
            'bathtub': 'Ванна',
            'shower': 'Душ',
            'elevator': 'Лифт',
            'pets-welcome': 'Можно с животными',
            'non-smoking': 'Курение запрещено',
            'garage': 'Гараж',
            'balcony': 'Балкон',
            'fenced-area': 'Огороженная территория',
            'video-surveillance': 'Видеонаблюдение',
            'security': 'Охрана',
            'safe': 'Сейф',
            # Дополнительные варианты написания
            'fence': 'Огороженная территория',
            'cctv': 'Видеонаблюдение',
            'bbq': 'Зона барбекю',
            'coffee': 'Кофеварка',
            'parking': 'Бесплатная парковка',
        }
        
        # Обрабатываем каждое значение amenity из списка
        for amenity_str in amenities_list:
            if not amenity_str:
                continue
                
            # Сначала пытаемся обработать как JSON массив
            try:
                amenities_json = json.loads(amenity_str)
                if isinstance(amenities_json, list):
                    for amenity_item in amenities_json:
                        if isinstance(amenity_item, dict):
                            # Проверяем различные форматы данных
                            if 'image' in amenity_item:
                                # Формат с иконкой
                                image_path = amenity_item['image'].lower()
                                
                                # Находим соответствующую amenity
                                for icon_key, amenity_name in amenity_mapping.items():
                                    if icon_key in image_path:
                                        try:
                                            # Ищем PropertyFeature по названию
                                            feature = PropertyFeature.objects.get(name=amenity_name)
                                            
                                            # Создаем связь, если её ещё нет
                                            relation, created = PropertyFeatureRelation.objects.get_or_create(
                                                property=property_obj,
                                                feature=feature
                                            )
                                            
                                            if created:
                                                amenities_created += 1
                                                print(f"    ✓ Добавлен amenity: {amenity_name}")
                                            
                                        except PropertyFeature.DoesNotExist:
                                            self.stats['errors'].append(f"PropertyFeature не найден: {amenity_name}")
                                        except Exception as e:
                                            self.stats['errors'].append(f"Ошибка создания amenity {amenity_name}: {e}")
                                        break
                            
                            elif 'text' in amenity_item:
                                # Формат с мультиязычным текстом "EN==RU==TH==CHN"
                                text_data = amenity_item['text']
                                if '==' in text_data:
                                    # Парсим мультиязычный формат
                                    parts = text_data.split('==')
                                    if len(parts) >= 2:
                                        russian_name = parts[1].strip()  # Берем русское название
                                        
                                        try:
                                            # Ищем PropertyFeature по русскому названию
                                            feature = PropertyFeature.objects.get(name=russian_name)
                                            
                                            # Создаем связь, если её ещё нет
                                            relation, created = PropertyFeatureRelation.objects.get_or_create(
                                                property=property_obj,
                                                feature=feature
                                            )
                                            
                                            if created:
                                                amenities_created += 1
                                                print(f"    ✓ Добавлен amenity (мультиязычный): {russian_name}")
                                            
                                        except PropertyFeature.DoesNotExist:
                                            self.stats['errors'].append(f"PropertyFeature не найден (мультиязычный): {russian_name}")
                                        except Exception as e:
                                            self.stats['errors'].append(f"Ошибка создания amenity (мультиязычный) {russian_name}: {e}")
                                
            except json.JSONDecodeError:
                # Если JSON не парсится, обрабатываем как строку с путем к иконке
                image_path = amenity_str.lower()
                
                # Находим соответствующую amenity по пути иконки
                for icon_key, amenity_name in amenity_mapping.items():
                    if icon_key in image_path:
                        try:
                            # Ищем PropertyFeature по названию
                            feature = PropertyFeature.objects.get(name=amenity_name)
                            
                            # Создаем связь, если её ещё нет
                            relation, created = PropertyFeatureRelation.objects.get_or_create(
                                property=property_obj,
                                feature=feature
                            )
                            
                            if created:
                                amenities_created += 1
                                print(f"    ✓ Добавлен amenity: {amenity_name}")
                            
                        except PropertyFeature.DoesNotExist:
                            self.stats['errors'].append(f"PropertyFeature не найден: {amenity_name}")
                        except Exception as e:
                            self.stats['errors'].append(f"Ошибка создания amenity {amenity_name}: {e}")
                        break
        
        return amenities_created
    
    def get_property_type(self, catid, legacy_id=None, title=None):
        """Получить тип недвижимости по catid, legacy_id и названию"""
        
        # Сначала проверяем земельные участки по legacy_id
        land_legacy_ids = ['DT2042', 'DT2052', 'L1', 'L2', 'L3']
        if legacy_id and legacy_id in land_legacy_ids:
            try:
                return PropertyType.objects.get(name='land')
            except PropertyType.DoesNotExist:
                return PropertyType.objects.create(
                    name='land',
                    name_display='Земельный участок'
                )
        
        # Проверяем по названию (если содержит "land plot", "land for sale")
        if title and ('land plot' in title.lower() or 'land for sale' in title.lower()):
            try:
                return PropertyType.objects.get(name='land')
            except PropertyType.DoesNotExist:
                return PropertyType.objects.create(
                    name='land',
                    name_display='Земельный участок'
                )
        
        # Стандартная логика по catid
        type_name = self.property_type_mapping.get(catid)
        if not type_name:
            return None
        
        try:
            return PropertyType.objects.get(name=type_name)
        except PropertyType.DoesNotExist:
            # Создаем тип если не существует с ограничением названия
            display_name = type_name.title()
            if len(display_name) > 100:
                display_name = display_name[:100]
                
            return PropertyType.objects.create(
                name=type_name,
                name_display=display_name
            )
    
    def create_default_districts(self):
        """Создать основные районы Пхукета если они не существуют"""
        default_districts = [
            {
                'name': 'Таланг', 
                'slug': 'thalang', 
                'description': 'Северный район Пхукета, включает Банг Тао, Лаян, Най Янг, Черн Талай'
            },
            {
                'name': 'Катху', 
                'slug': 'kathu', 
                'description': 'Центральный район Пхукета, включает Патонг, Камала, Катху'
            },
            {
                'name': 'Муанг Пхукет', 
                'slug': 'mueang-phuket', 
                'description': 'Южный район Пхукета, включает Чалонг, Равай, Карон, Ката, Вичит, Ратсада, Ко Каео'
            },
        ]
        
        created_count = 0
        for district_data in default_districts:
            district, created = District.objects.get_or_create(
                slug=district_data['slug'],
                defaults={
                    'name': district_data['name'],
                    'description': district_data['description']
                }
            )
            if created:
                created_count += 1
                print(f"  ✓ Создан район: {district.name}")
        
        if created_count > 0:
            print(f"✓ Создано районов: {created_count}")
        return created_count

    def create_default_locations(self):
        """Создать основные локации Пхукета если они не существуют"""
        # Получаем районы для связи с локациями
        try:
            mueang_phuket = District.objects.get(slug='mueang-phuket')
            kathu = District.objects.get(slug='kathu')
            thalang = District.objects.get(slug='thalang')
        except District.DoesNotExist:
            print("✗ Районы не найдены, создайте их сначала")
            return 0
        
        # Локации по районам на основе анализа дампа
        locations_data = [
            # Mueang Phuket
            {'name': 'Chalong', 'slug': 'chalong', 'district': mueang_phuket},
            {'name': 'Karon', 'slug': 'karon', 'district': mueang_phuket},
            {'name': 'Kata', 'slug': 'kata', 'district': mueang_phuket},
            {'name': 'Ko Kaeo', 'slug': 'ko-kaeo', 'district': mueang_phuket},
            {'name': 'Rawai', 'slug': 'rawai', 'district': mueang_phuket},
            {'name': 'Ratsada', 'slug': 'ratsada', 'district': mueang_phuket},
            {'name': 'Wichit', 'slug': 'wichit', 'district': mueang_phuket},
            
            # Kathu
            {'name': 'Kamala', 'slug': 'kamala', 'district': kathu},
            {'name': 'Kathu', 'slug': 'kathu', 'district': kathu},
            {'name': 'Patong', 'slug': 'patong', 'district': kathu},
            
            # Thalang
            {'name': 'Bang Tao', 'slug': 'bang-tao', 'district': thalang},
            {'name': 'Cherng Talay', 'slug': 'cherng-talay', 'district': thalang},
            {'name': 'Choeng Thale', 'slug': 'choeng-thale', 'district': thalang},
            {'name': 'Layan', 'slug': 'layan', 'district': thalang},
            {'name': 'Mai Khao', 'slug': 'mai-khao', 'district': thalang},
            {'name': 'Nai Yang', 'slug': 'nai-yang', 'district': thalang},
            {'name': 'Nai Thon', 'slug': 'nai-thon', 'district': thalang},
            {'name': 'Sakhu', 'slug': 'sakhu', 'district': thalang},
            {'name': 'Si Sunthon', 'slug': 'si-sunthon', 'district': thalang},
            {'name': 'Surin', 'slug': 'surin', 'district': thalang},
            {'name': 'Thep Krasatti', 'slug': 'thep-krasatti', 'district': thalang},
        ]
        
        created_count = 0
        for location_data in locations_data:
            location, created = Location.objects.get_or_create(
                slug=location_data['slug'],
                district=location_data['district'],
                defaults={
                    'name': location_data['name'],
                    'description': f"Локация {location_data['name']} в районе {location_data['district'].name}"
                }
            )
            if created:
                created_count += 1
                print(f"  ✓ Создана локация: {location.name} ({location.district.name})")
        
        if created_count > 0:
            print(f"✓ Создано локаций: {created_count}")
        return created_count

    def get_location_by_address(self, address, district):
        """Определить локацию по адресу и району"""
        if not address:
            return None
        
        address_lower = address.lower()
        
        # Сопоставление ключевых слов с локациями
        location_keywords = {
            # Mueang Phuket
            'chalong': ['chalong'],
            'karon': ['karon'],
            'kata': ['kata'],
            'ko-kaeo': ['ko kaeo', 'ko-kaeo'],
            'rawai': ['rawai'],
            'ratsada': ['ratsada'],
            'wichit': ['wichit'],
            
            # Kathu
            'kamala': ['kamala'],
            'kathu': ['kathu'],
            'patong': ['patong'],
            
            # Thalang
            'bang-tao': ['bang tao', 'bangtao'],
            'cherng-talay': ['cherng talay', 'cherng-talay'],
            'choeng-thale': ['choeng thale', 'choeng-thale'],
            'layan': ['layan'],
            'mai-khao': ['mai khao', 'maikhao'],
            'nai-yang': ['nai yang', 'naiyang'],
            'nai-thon': ['nai thon', 'naithon'],
            'sakhu': ['sakhu'],
            'si-sunthon': ['si sunthon', 'si-sunthon'],
            'surin': ['surin'],
            'thep-krasatti': ['thep krasatti', 'thep-krasatti'],
        }
        
        # Поиск локации по ключевым словам
        for location_slug, keywords in location_keywords.items():
            for keyword in keywords:
                if keyword in address_lower:
                    try:
                        location = Location.objects.get(slug=location_slug, district=district)
                        return location
                    except Location.DoesNotExist:
                        continue
        
        return None

    def get_district_by_name(self, address):
        """Попытаться определить район по адресу"""
        if not address:
            return self.get_default_district()
        
        address_lower = address.lower()
        
        # Расширенное сопоставление по ключевым словам (исправлено согласно реальной географии)
        district_keywords = {
            'thalang': ['thalang', 'bang tao', 'layan', 'nai yang', 'cherng talay', 'choeng thale', 'mai khao', 'laguna', 'surin', 'nai thon', 'sakhu', 'si sunthon', 'thep krasatti'],
            'kathu': ['kathu', 'patong', 'kamala'],
            'mueang-phuket': ['rawai', 'chalong', 'nai harn', 'phuket town', 'wichit', 'ko kaeo', 'cape panwa', 'karon', 'kata', 'ratsada'],
        }
        
        for district_slug, keywords in district_keywords.items():
            for keyword in keywords:
                if keyword in address_lower:
                    try:
                        return District.objects.get(slug=district_slug)
                    except District.DoesNotExist:
                        continue
        
        # Если не нашли по ключевым словам, возвращаем район по умолчанию
        return self.get_default_district()
    
    def get_default_district(self):
        """Получить район по умолчанию"""
        try:
            return District.objects.get(slug='thalang')
        except District.DoesNotExist:
            # Если нет района по умолчанию, возвращаем первый доступный
            district = District.objects.first()
            if not district:
                # Если нет ни одного района, создаем их
                self.create_default_districts()
                return District.objects.get(slug='thalang')
            return district
    
    def generate_unique_slug(self, base_slug, legacy_id):
        """Генерировать уникальный slug для объекта"""
        from apps.properties.models import Property
        
        # Сначала проверяем базовый slug
        if not Property.objects.filter(slug=base_slug).exists():
            return base_slug
        
        # Если базовый slug занят, добавляем legacy_id
        slug_with_id = f"{base_slug}-{legacy_id}"
        if not Property.objects.filter(slug=slug_with_id).exists():
            return slug_with_id
        
        # Если и с legacy_id занят, добавляем счетчик
        counter = 1
        while True:
            unique_slug = f"{base_slug}-{legacy_id}-{counter}"
            if not Property.objects.filter(slug=unique_slug).exists():
                return unique_slug
            counter += 1

    def parse_datetime(self, datetime_str):
        """Конвертировать строку даты в timezone-aware datetime объект"""
        if not datetime_str:
            return timezone.now()
        
        # Попытка парсинга с помощью Django dateparse
        dt = parse_datetime(datetime_str)
        if dt:
            # Если дата уже содержит timezone info, возвращаем как есть
            if dt.tzinfo is not None:
                return dt
            # Если naive datetime, делаем timezone-aware
            return timezone.make_aware(dt, timezone.get_current_timezone())
        
        # Если не удалось парсить, пробуем стандартный формат
        try:
            dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            return timezone.make_aware(dt, timezone.get_current_timezone())
        except ValueError:
            # Если не удается парсить, возвращаем текущее время
            return timezone.now()

    def generate_unique_legacy_id(self, base_legacy_id, fields_data, title, item_id):
        """Генерировать уникальный legacy_id для случаев дублирования"""
        # Проверяем, есть ли дублирование по base_legacy_id
        duplicates_count = sum(1 for item in self.content_data 
                             if (item.get('note') or item['id']) == base_legacy_id)
        
        # Если дублирования нет, возвращаем базовый ID
        if duplicates_count <= 1:
            return base_legacy_id
        
        # Если есть дублирование, создаем уникальный суффикс на основе характеристик
        bedrooms = fields_data.get('93', '')
        area_total = fields_data.get('92', '')
        
        # Формируем суффикс на основе количества спален и площади
        suffix_parts = []
        
        if bedrooms:
            try:
                bedrooms_int = int(float(bedrooms))
                suffix_parts.append(f"{bedrooms_int}BR")
            except (ValueError, TypeError):
                pass
        
        if area_total:
            try:
                area_int = int(float(area_total))
                suffix_parts.append(f"{area_int}M")
            except (ValueError, TypeError):
                pass
        
        # Если нет характеристик для различения, используем item_id
        if not suffix_parts:
            suffix_parts.append(f"ID{item_id}")
        
        unique_legacy_id = f"{base_legacy_id}-{'-'.join(suffix_parts)}"
        
        print(f"    🔄 Создан уникальный legacy_id: {base_legacy_id} → {unique_legacy_id}")
        return unique_legacy_id

    def migrate_property(self, content_item):
        """Мигрировать один объект недвижимости"""
        from apps.properties.models import Property
        
        item_id = content_item['id']
        fields_data = self.fields_map.get(item_id, {})
        
        # Определяем базовый legacy_id и title для анализа типа недвижимости
        base_legacy_id = content_item.get('note') or item_id
        title = content_item.get('title', '')
        
        # Создаем уникальный legacy_id для случаев дублирования
        legacy_id = self.generate_unique_legacy_id(base_legacy_id, fields_data, title, item_id)
        
        # Проверяем, есть ли уже объект с таким уникальным legacy_id
        existing_property = Property.objects.filter(legacy_id=legacy_id).first()
        if existing_property:
            print(f"  ⚠ Объект {legacy_id} уже существует, пропускаем: {existing_property.title}")
            return existing_property
        
        # Проверяем, что это недвижимость
        catid = content_item.get('catid')
        property_type = self.get_property_type(catid, legacy_id, title)
        if not property_type:
            return None  # Пропускаем не-недвижимость
        
        # Определяем район
        address = fields_data.get('19', '')
        district = self.get_district_by_name(address)
        if not district:
            self.stats['errors'].append(f"Не удалось определить район для объекта {item_id}")
            return None
        
        # Определяем локацию
        location = self.get_location_by_address(address, district)
        if location:
            print(f"    📍 Локация определена: {location.name} ({location.district.name})")
        
        # Извлекаем координаты
        coordinates_str = fields_data.get('17', '')
        latitude, longitude = None, None
        if coordinates_str and ',' in coordinates_str:
            try:
                lat_str, lng_str = coordinates_str.split(',', 1)
                latitude = Decimal(lat_str.strip())
                longitude = Decimal(lng_str.strip())
            except (ValueError, InvalidOperation):
                self.stats['errors'].append(f"Ошибка парсинга координат для объекта {item_id}: {coordinates_str}")
        
        # Извлекаем цену в THB (исправлено!)
        price_thb = None
        price_str = fields_data.get('66', '')
        if price_str:
            try:
                price_thb = Decimal(price_str)
            except (ValueError, InvalidOperation):
                self.stats['errors'].append(f"Ошибка парсинга цены для объекта {item_id}: {price_str}")
        
        # Извлекаем площадь дома
        area_total = None
        area_str = fields_data.get('92', '')
        if area_str:
            try:
                area_total = Decimal(area_str)
            except (ValueError, InvalidOperation):
                pass
        
        # Извлекаем площадь участка
        area_land = None
        area_land_str = fields_data.get('95', '')
        if area_land_str:
            try:
                area_land = Decimal(area_land_str)
            except (ValueError, InvalidOperation):
                pass
        
        # Извлекаем спальни и ванные
        bedrooms = None
        bedrooms_str = fields_data.get('93', '')
        if bedrooms_str:
            try:
                bedrooms = int(float(bedrooms_str))
            except (ValueError, TypeError):
                pass
        
        bathrooms = None
        bathrooms_str = fields_data.get('94', '')
        if bathrooms_str:
            try:
                bathrooms = int(float(bathrooms_str))
            except (ValueError, TypeError):
                pass
        
        # Извлекаем типы кроватей
        double_beds = None
        double_beds_str = fields_data.get('60', '')
        if double_beds_str:
            try:
                double_beds = int(float(double_beds_str))
            except (ValueError, TypeError):
                pass
        
        single_beds = None
        single_beds_str = fields_data.get('61', '')
        if single_beds_str:
            try:
                single_beds = int(float(single_beds_str))
            except (ValueError, TypeError):
                pass
        
        sofa_beds = None
        sofa_beds_str = fields_data.get('62', '')
        if sofa_beds_str:
            try:
                sofa_beds = int(float(sofa_beds_str))
            except (ValueError, TypeError):
                pass
        
        # Создаем или обновляем объект недвижимости
        # legacy_id уже определен выше
        
        # Генерируем уникальный slug
        base_slug = content_item.get('alias') or slugify(content_item.get('title', f'property-{item_id}'))
        unique_slug = self.generate_unique_slug(base_slug, legacy_id)
        
        # Конвертируем даты в timezone-aware объекты
        created_at = self.parse_datetime(content_item.get('created'))
        updated_at = self.parse_datetime(content_item.get('modified'))
        
        defaults = {
            'title': content_item.get('title', f'Property {item_id}'),
            'slug': unique_slug,
            'property_type': property_type,
            'deal_type': 'sale',  # По умолчанию продажа
            'status': 'available',
            'description': content_item.get('introtext', '') + '\n\n' + content_item.get('fulltext', ''),
            'district': district,
            'location': location,  # Добавлена локация
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'bedrooms': bedrooms,
            'bathrooms': bathrooms,
            'area_total': area_total,
            'area_land': area_land,
            'price_sale_thb': price_thb,  # Исправлено на THB
            'is_featured': content_item.get('featured', '0') == '1',
            'is_active': content_item.get('state', '0') == '1',
            'created_at': created_at,
            'updated_at': updated_at,
        }
        
        # Добавляем новые поля если они доступны в модели
        try:
            from apps.properties.models import Property
            model_fields = [f.name for f in Property._meta.fields]
            
            if 'double_beds' in model_fields:
                defaults['double_beds'] = double_beds
            if 'single_beds' in model_fields:
                defaults['single_beds'] = single_beds
            if 'sofa_beds' in model_fields:
                defaults['sofa_beds'] = sofa_beds
        except Exception:
            pass  # Поля еще не добавлены в модель
        
        # Обработка агента
        agent_id = fields_data.get('26')
        if agent_id:
            # Найдем данные агента в content_data
            agent_content = next((item for item in self.content_data if item['id'] == agent_id), None)
            if agent_content:
                agent = self.get_or_create_agent(agent_content)
                if agent and 'agent' in [f.name for f in Property._meta.fields]:
                    defaults['agent'] = agent
        
        try:
            # Создаем новый объект (проверка существования уже выполнена в начале метода)
            property_obj = Property.objects.create(legacy_id=legacy_id, **defaults)
            
            self.stats['properties_created'] += 1
            print(f"  ✓ Создан объект: {property_obj.title}")
            
            # Обрабатываем изображения
            self.process_property_images(property_obj, fields_data)
            
            # Обрабатываем amenities (удобства) из field_id=6
            amenities_created = self.process_amenities(property_obj, fields_data.get('6', ''))
            self.stats['features_created'] += amenities_created
            
            return property_obj
            
        except Exception as e:
            self.stats['errors'].append(f"Ошибка создания объекта {item_id}: {e}")
            print(f"  ✗ Ошибка создания объекта {item_id}: {e}")
            return None
    
    def migrate_all_properties(self):
        """Мигрировать все объекты недвижимости"""
        print("Начинаем миграцию объектов недвижимости...")
        
        # Фильтруем только недвижимость
        property_items = [
            item for item in self.content_data 
            if item.get('catid') in self.property_type_mapping 
            and self.property_type_mapping[item.get('catid')] is not None
        ]
        
        print(f"Найдено {len(property_items)} объектов недвижимости для миграции")
        
        with transaction.atomic():
            for idx, item in enumerate(property_items, 1):
                print(f"[{idx}/{len(property_items)}] Мигрируем объект {item['id']}: {item.get('title', 'Без названия')[:50]}...")
                self.migrate_property(item)
                
                if idx % 50 == 0:
                    print(f"  Обработано {idx} объектов...")
    
    def print_statistics(self):
        """Вывести статистику миграции"""
        print("\n" + "="*60)
        print("СТАТИСТИКА МИГРАЦИИ")
        print("="*60)
        print(f"✓ Создано объектов недвижимости: {self.stats['properties_created']}")
        print(f"✓ Обновлено объектов недвижимости: {self.stats['properties_updated']}")
        print(f"✓ Создано агентов: {self.stats['agents_created']}")
        print(f"✓ Создано изображений: {self.stats['images_created']}")
        print(f"✓ Создано характеристик: {self.stats['features_created']}")
        
        if self.stats['errors']:
            print(f"\n⚠ Ошибки ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Показываем первые 10
                print(f"  • {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... и еще {len(self.stats['errors']) - 10} ошибок")
        else:
            print("\n✓ Миграция завершена без ошибок!")
    
    def run(self):
        """Запустить полную миграцию"""
        print("Запуск полной миграции из underson_bd_dump.json")
        print("="*60)
        
        # Загружаем дамп
        if not self.load_dump():
            return False
        
        # Извлекаем таблицы
        if not self.extract_tables():
            return False
        
        # Строим сопоставление полей
        self.build_fields_mapping()
        
        # Создаем районы перед миграцией объектов
        print("Подготавливаем районы Пхукета...")
        self.create_default_districts()
        
        # Создаем локации
        print("Подготавливаем локации Пхукета...")
        self.create_default_locations()
        
        # Мигрируем все объекты
        self.migrate_all_properties()
        
        # Выводим статистику
        self.print_statistics()
        
        return True


def main():
    """Точка входа скрипта"""
    dump_file = 'underson_bd_dump.json'
    
    if not os.path.exists(dump_file):
        print(f"✗ Файл {dump_file} не найден в текущей директории")
        print(f"Убедитесь, что файл дампа находится в: {os.getcwd()}")
        return
    
    migrator = UndersonDumpMigrator(dump_file)
    migrator.run()


if __name__ == '__main__':
    main()