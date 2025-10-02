import time
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Полный парсинг всех объектов недвижимости со всех разделов сайта с последующей сверкой'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-pages',
            type=int,
            default=10,
            help='Максимальное количество страниц для парсинга (по умолчанию: 10)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод отладочной информации'
        )
        parser.add_argument(
            '--no-pause',
            action='store_true',
            help='Не делать паузы между категориями (не рекомендуется)'
        )

    def handle(self, *args, **options):
        max_pages = options['max_pages']
        verbose = options['verbose']
        no_pause = options['no_pause']

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('ПОЛНЫЙ ПАРСИНГ НЕДВИЖИМОСТИ UNDERSUNESTATE.COM'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        # Определяем все категории для парсинга
        categories = [
            {'name': 'Все объекты на продажу', 'type': 'all', 'deal_type': 'buy'},
            {'name': 'Все объекты в аренду', 'type': 'all', 'deal_type': 'rent'},
            {'name': 'Виллы', 'type': 'villa', 'deal_type': 'all'},
            {'name': 'Кондоминиумы', 'type': 'condo', 'deal_type': 'all'},
            {'name': 'Таунхаусы', 'type': 'townhouse', 'deal_type': 'all'},
            {'name': 'Земельные участки', 'type': 'land', 'deal_type': 'all'},
        ]

        # Статистика парсинга
        total_stats = {
            'categories_parsed': 0,
            'categories_failed': 0,
            'total_time': 0
        }

        start_time = time.time()

        # Парсим каждую категорию
        for i, category in enumerate(categories, 1):
            category_start = time.time()

            self.stdout.write(self.style.WARNING(f'\n[{i}/{len(categories)}] Парсинг категории: {category["name"]}'))
            self.stdout.write('-' * 70)

            try:
                # Вызываем основной парсер с нужными параметрами
                call_command(
                    'parse_properties',
                    type=category['type'],
                    deal_type=category['deal_type'],
                    max_pages=max_pages,
                    verbose=verbose
                )

                category_time = time.time() - category_start
                total_stats['categories_parsed'] += 1

                self.stdout.write(self.style.SUCCESS(
                    f'✓ Категория "{category["name"]}" завершена за {category_time:.1f} сек'
                ))

            except Exception as e:
                total_stats['categories_failed'] += 1
                self.stdout.write(self.style.ERROR(
                    f'✗ Ошибка при парсинге категории "{category["name"]}": {e}'
                ))

            # Пауза между категориями (защита от блокировки)
            if not no_pause and i < len(categories):
                pause_time = 5
                self.stdout.write(f'\nПауза {pause_time} секунд перед следующей категорией...')
                time.sleep(pause_time)

        # Подсчитываем общее время
        total_stats['total_time'] = time.time() - start_time

        # Выводим итоговую статистику
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('ИТОГОВАЯ СТАТИСТИКА ПАРСИНГА'))
        self.stdout.write(self.style.SUCCESS('='*70))

        self.stdout.write(f'Категорий успешно обработано: {total_stats["categories_parsed"]}/{len(categories)}')
        self.stdout.write(f'Категорий с ошибками: {total_stats["categories_failed"]}')
        self.stdout.write(f'Общее время выполнения: {total_stats["total_time"]:.1f} сек ({total_stats["total_time"]/60:.1f} мин)')

        # Получаем статистику по объектам в БД
        from apps.properties.models import Property

        self.stdout.write('\n' + '='*70)
        self.stdout.write('СТАТИСТИКА ПО ОБЪЕКТАМ В БАЗЕ ДАННЫХ')
        self.stdout.write('='*70)

        total_properties = Property.objects.count()
        sale_properties = Property.objects.filter(deal_type='sale').count()
        rent_properties = Property.objects.filter(deal_type='rent').count()
        both_properties = Property.objects.filter(deal_type='both').count()
        available_properties = Property.objects.filter(status='available').count()

        self.stdout.write(f'Всего объектов в базе: {total_properties}')
        self.stdout.write(f'  - На продажу: {sale_properties}')
        self.stdout.write(f'  - В аренду: {rent_properties}')
        self.stdout.write(f'  - Продажа/Аренда: {both_properties}')
        self.stdout.write(f'  - Доступных: {available_properties}')

        # Статистика по типам недвижимости
        from apps.properties.models import PropertyType

        self.stdout.write('\nСтатистика по типам недвижимости:')
        for prop_type in PropertyType.objects.all():
            count = Property.objects.filter(property_type=prop_type).count()
            self.stdout.write(f'  - {prop_type.name_display}: {count}')

        # Проверка на дубликаты
        self.stdout.write('\n' + '='*70)
        self.stdout.write('ПРОВЕРКА НА ДУБЛИКАТЫ')
        self.stdout.write('='*70)

        # Дубликаты по legacy_id
        from django.db.models import Count

        duplicates_by_legacy = Property.objects.values('legacy_id').annotate(
            count=Count('id')
        ).filter(count__gt=1, legacy_id__isnull=False)

        if duplicates_by_legacy:
            self.stdout.write(self.style.WARNING(
                f'Найдено {len(duplicates_by_legacy)} дубликатов по legacy_id:'
            ))
            for dup in duplicates_by_legacy[:10]:  # Показываем первые 10
                properties = Property.objects.filter(legacy_id=dup['legacy_id'])
                self.stdout.write(f'  - legacy_id {dup["legacy_id"]}: {dup["count"]} объектов')
                for prop in properties:
                    self.stdout.write(f'    - ID {prop.id}: {prop.title[:50]}...')
        else:
            self.stdout.write(self.style.SUCCESS('✓ Дубликатов по legacy_id не найдено'))

        # Дубликаты по заголовку
        duplicates_by_title = Property.objects.values('title').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        if duplicates_by_title:
            self.stdout.write(self.style.WARNING(
                f'\nНайдено {len(duplicates_by_title)} дубликатов по заголовку:'
            ))
            for dup in duplicates_by_title[:5]:  # Показываем первые 5
                self.stdout.write(f'  - "{dup["title"][:50]}...": {dup["count"]} объектов')
        else:
            self.stdout.write(self.style.SUCCESS('✓ Дубликатов по заголовку не найдено'))

        # Объекты без цены
        properties_without_price = Property.objects.filter(
            price_sale_thb__isnull=True,
            price_rent_monthly_thb__isnull=True
        ).count()

        if properties_without_price > 0:
            self.stdout.write(self.style.WARNING(
                f'\n⚠ Объектов без цены: {properties_without_price}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Все объекты имеют цену'))

        # Объекты без изображений
        properties_without_images = Property.objects.filter(images__isnull=True).distinct().count()

        if properties_without_images > 0:
            self.stdout.write(self.style.WARNING(
                f'⚠ Объектов без изображений: {properties_without_images}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Все объекты имеют изображения'))

        # Объекты без координат
        properties_without_coords = Property.objects.filter(
            latitude__isnull=True
        ).count() + Property.objects.filter(
            longitude__isnull=True
        ).count()

        if properties_without_coords > 0:
            self.stdout.write(self.style.WARNING(
                f'⚠ Объектов без координат: {properties_without_coords}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Все объекты имеют координаты'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('ПАРСИНГ ЗАВЕРШЕН'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))