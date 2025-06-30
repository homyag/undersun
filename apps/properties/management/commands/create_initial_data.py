from django.core.management.base import BaseCommand
from apps.locations.models import District, Location
from apps.properties.models import PropertyType, PropertyFeature


class Command(BaseCommand):
    help = 'Создает начальные данные для сайта'

    def handle(self, *args, **options):
        # Создаем районы Пхукета
        districts_data = [
            {
                'name_ru': 'Муанг Пхукет', 'name_en': 'Mueang Phuket', 'name_th': 'เมืองภูเก็ต',
                'slug': 'mueang-phuket',
                'description_ru': 'Центральный район Пхукета с административным центром',
                'description_en': 'Central district of Phuket with administrative center',
            },
            {
                'name_ru': 'Катху', 'name_en': 'Kathu', 'name_th': 'กะทู้',
                'slug': 'kathu',
                'description_ru': 'Район с популярными пляжами Патонг и Камала',
                'description_en': 'District with popular Patong and Kamala beaches',
            },
            {
                'name_ru': 'Таланг', 'name_en': 'Thalang', 'name_th': 'ถลาง',
                'slug': 'thalang',
                'description_ru': 'Северный район с аэропортом и элитными пляжами',
                'description_en': 'Northern district with airport and luxury beaches',
            },
        ]

        for district_data in districts_data:
            district, created = District.objects.get_or_create(
                slug=district_data['slug'],
                defaults={
                    'name_ru': district_data['name_ru'],
                    'name_en': district_data['name_en'],
                    'name_th': district_data['name_th'],
                    'description_ru': district_data['description_ru'],
                    'description_en': district_data['description_en'],
                }
            )
            if created:
                self.stdout.write(f'Создан район: {district.name}')

        # Создаем популярные локации
        locations_data = [
            # Муанг Пхукет
            {'name_ru': 'Пхукет Таун', 'name_en': 'Phuket Town', 'district_slug': 'mueang-phuket',
             'slug': 'phuket-town'},
            {'name_ru': 'Чалонг', 'name_en': 'Chalong', 'district_slug': 'mueang-phuket', 'slug': 'chalong'},
            {'name_ru': 'Раваи', 'name_en': 'Rawai', 'district_slug': 'mueang-phuket', 'slug': 'rawai'},
            {'name_ru': 'Най Харн', 'name_en': 'Nai Harn', 'district_slug': 'mueang-phuket', 'slug': 'nai-harn'},

            # Катху
            {'name_ru': 'Патонг', 'name_en': 'Patong', 'district_slug': 'kathu', 'slug': 'patong'},
            {'name_ru': 'Камала', 'name_en': 'Kamala', 'district_slug': 'kathu', 'slug': 'kamala'},
            {'name_ru': 'Карон', 'name_en': 'Karon', 'district_slug': 'kathu', 'slug': 'karon'},
            {'name_ru': 'Ката', 'name_en': 'Kata', 'district_slug': 'kathu', 'slug': 'kata'},

            # Таланг
            {'name_ru': 'Банг Тао', 'name_en': 'Bang Tao', 'district_slug': 'thalang', 'slug': 'bang-tao'},
            {'name_ru': 'Лаян', 'name_en': 'Layan', 'district_slug': 'thalang', 'slug': 'layan'},
            {'name_ru': 'Най Тон', 'name_en': 'Nai Ton', 'district_slug': 'thalang', 'slug': 'nai-ton'},
            {'name_ru': 'Май Као', 'name_en': 'Mai Khao', 'district_slug': 'thalang', 'slug': 'mai-khao'},
        ]

        for location_data in locations_data:
            district = District.objects.get(slug=location_data['district_slug'])
            location, created = Location.objects.get_or_create(
                slug=location_data['slug'],
                district=district,
                defaults={
                    'name_ru': location_data['name_ru'],
                    'name_en': location_data['name_en'],
                }
            )
            if created:
                self.stdout.write(f'Создана локация: {location.name}')

        # Создаем типы недвижимости
        property_types = [
            {'name': 'villa', 'name_display_ru': 'Виллы', 'name_display_en': 'Villas', 'icon': 'fas fa-home'},
            {'name': 'apartment', 'name_display_ru': 'Апартаменты', 'name_display_en': 'Apartments',
             'icon': 'fas fa-building'},
            {'name': 'condo', 'name_display_ru': 'Кондоминиумы', 'name_display_en': 'Condominiums',
             'icon': 'fas fa-city'},
            {'name': 'townhouse', 'name_display_ru': 'Таунхаусы', 'name_display_en': 'Townhouses',
             'icon': 'fas fa-home'},
            {'name': 'commercial', 'name_display_ru': 'Коммерческая', 'name_display_en': 'Commercial',
             'icon': 'fas fa-store'},
            {'name': 'land', 'name_display_ru': 'Земля', 'name_display_en': 'Land', 'icon': 'fas fa-map'},
        ]

        for pt_data in property_types:
            pt, created = PropertyType.objects.get_or_create(
                name=pt_data['name'],
                defaults={
                    'name_display_ru': pt_data['name_display_ru'],
                    'name_display_en': pt_data['name_display_en'],
                    'icon': pt_data['icon'],
                }
            )
            if created:
                self.stdout.write(f'Создан тип недвижимости: {pt.name_display}')

        # Создаем характеристики
        features = [
            {'name_ru': 'Кондиционер', 'name_en': 'Air Conditioning', 'icon': 'fas fa-snowflake'},
            {'name_ru': 'Интернет WiFi', 'name_en': 'WiFi Internet', 'icon': 'fas fa-wifi'},
            {'name_ru': 'Прачечная', 'name_en': 'Laundry', 'icon': 'fas fa-tshirt'},
            {'name_ru': 'Кухня', 'name_en': 'Kitchen', 'icon': 'fas fa-utensils'},
            {'name_ru': 'Балкон/Терраса', 'name_en': 'Balcony/Terrace', 'icon': 'fas fa-tree'},
            {'name_ru': 'Сад', 'name_en': 'Garden', 'icon': 'fas fa-leaf'},
            {'name_ru': 'Мотоциклы в аренду', 'name_en': 'Motorcycle Rental', 'icon': 'fas fa-motorcycle'},
            {'name_ru': 'Трансфер', 'name_en': 'Transfer', 'icon': 'fas fa-car'},
            {'name_ru': 'Ресепшен 24/7', 'name_en': '24/7 Reception', 'icon': 'fas fa-concierge-bell'},
            {'name_ru': 'Фитнес-центр', 'name_en': 'Fitness Center', 'icon': 'fas fa-dumbbell'},
            {'name_ru': 'Спа', 'name_en': 'Spa', 'icon': 'fas fa-spa'},
            {'name_ru': 'Рядом с пляжем', 'name_en': 'Near Beach', 'icon': 'fas fa-umbrella-beach'},
        ]

        for feature_data in features:
            feature, created = PropertyFeature.objects.get_or_create(
                name_ru=feature_data['name_ru'],
                defaults={
                    'name_en': feature_data['name_en'],
                    'icon': feature_data['icon'],
                }
            )
            if created:
                self.stdout.write(f'Создана характеристика: {feature.name}')

        self.stdout.write(
            self.style.SUCCESS('Успешно создали начальные данные!')
        )