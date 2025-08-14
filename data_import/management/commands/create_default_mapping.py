from django.core.management.base import BaseCommand
from data_import.models import PropertyImportMapping


class Command(BaseCommand):
    help = 'Создает базовый маппинг полей по умолчанию'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Перезаписать существующий маппинг по умолчанию'
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # Проверяем, есть ли уже маппинг по умолчанию
        existing_default = PropertyImportMapping.objects.filter(is_default=True).first()
        
        if existing_default and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Маппинг по умолчанию уже существует: "{existing_default.name}". '
                    'Используйте --force для перезаписи.'
                )
            )
            return
        
        # Базовый маппинг полей (колонки A-Z соответствуют основным полям)
        default_mapping = {
            'A': 'legacy_id',              # ID объекта
            'B': 'title',                  # Название
            'C': 'price_sale_usd',         # Цена продажи USD
            'D': 'price_sale_thb',         # Цена продажи THB
            'E': 'price_sale_rub',         # Цена продажи RUB
            'F': 'price_rent_monthly',     # Аренда USD
            'G': 'price_rent_monthly_thb', # Аренда THB
            'H': 'price_rent_monthly_rub', # Аренда RUB
            'I': 'area_total',             # Общая площадь
            'J': 'area_living',            # Жилая площадь
            'K': 'area_land',              # Площадь участка
            'L': 'bedrooms',               # Спальни
            'M': 'bathrooms',              # Ванные
            'N': 'floor',                  # Этаж
            'O': 'floors_total',           # Всего этажей
            'P': 'status',                 # Статус
            'Q': 'deal_type',              # Тип сделки
            'R': 'latitude',               # Широта
            'S': 'longitude',              # Долгота
            'T': 'furnished',              # С мебелью
            'U': 'pool',                   # Бассейн
            'V': 'parking',                # Парковка
            'W': 'security',               # Охрана
            'X': 'gym',                    # Спортзал
            'Y': 'year_built',             # Год постройки
        }
        
        mapping_obj, created = PropertyImportMapping.objects.update_or_create(
            name='Базовый маппинг',
            defaults={
                'description': 'Стандартный маппинг полей для импорта недвижимости',
                'is_default': True,
                'field_mapping': default_mapping,
                'header_row': 1,
                'data_start_row': 2,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Создан новый маппинг по умолчанию')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Обновлен существующий маппинг по умолчанию')
            )
        
        self.stdout.write(f'Маппинг ID: {mapping_obj.id}')
        self.stdout.write(f'Замаппленных полей: {len(default_mapping)}')
        
        # Показываем маппинг
        self.stdout.write('\nМаппинг полей:')
        for excel_col, model_field in default_mapping.items():
            self.stdout.write(f'  {excel_col} -> {model_field}')
        
        self.stdout.write(
            '\nТеперь вы можете использовать команду импорта:\n'
            f'python manage.py import_excel /path/to/file.xlsx --mapping-id {mapping_obj.id}'
        )