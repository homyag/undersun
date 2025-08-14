from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.core.files import File
from data_import.models import ImportFile, PropertyImportMapping
from data_import.services import ImportProcessor
import os


class Command(BaseCommand):
    help = 'Импорт данных недвижимости из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Путь к Excel файлу для импорта'
        )
        parser.add_argument(
            '--import-type',
            choices=['property_update', 'property_create', 'price_update'],
            default='property_update',
            help='Тип импорта (по умолчанию: property_update)'
        )
        parser.add_argument(
            '--mapping-id',
            type=int,
            help='ID маппинга полей (если не указан, используется маппинг по умолчанию)'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=1,
            help='ID пользователя, от имени которого выполняется импорт (по умолчанию: 1)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только проверка файла без фактического импорта'
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        import_type = options['import_type']
        mapping_id = options['mapping_id']
        user_id = options['user_id']
        dry_run = options['dry_run']

        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise CommandError(f'Файл {file_path} не найден')

        # Проверяем пользователя
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f'Пользователь с ID {user_id} не найден')

        # Получаем маппинг
        if mapping_id:
            try:
                mapping = PropertyImportMapping.objects.get(id=mapping_id)
            except PropertyImportMapping.DoesNotExist:
                raise CommandError(f'Маппинг с ID {mapping_id} не найден')
        else:
            mapping = PropertyImportMapping.get_default()
            if not mapping:
                raise CommandError('Не найден маппинг по умолчанию')

        self.stdout.write(f'Начинаем импорт файла: {file_path}')
        self.stdout.write(f'Тип импорта: {import_type}')
        self.stdout.write(f'Маппинг: {mapping.name}')
        self.stdout.write(f'Пользователь: {user.username}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('РЕЖИМ ПРОВЕРКИ - изменения не будут сохранены'))

        # Создаем запись ImportFile
        with open(file_path, 'rb') as f:
            file_name = os.path.basename(file_path)
            import_file = ImportFile.objects.create(
                name=file_name,
                import_type=import_type,
                uploaded_by=user,
                mapping=mapping
            )
            import_file.file.save(file_name, File(f), save=True)

        self.stdout.write(f'Создана запись импорта ID: {import_file.id}')

        if dry_run:
            # В режиме проверки только парсим файл
            from data_import.services import ExcelParser
            parser = ExcelParser(import_file.file.path, mapping)
            parse_result = parser.parse_file()
            
            if parse_result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Файл успешно распарсен. Найдено {parse_result["total_rows"]} строк данных'
                    )
                )
                
                # Показываем первые несколько записей
                if parse_result['data']:
                    self.stdout.write('\nПример данных:')
                    for i, row in enumerate(parse_result['data'][:3]):
                        self.stdout.write(f'Строка {i+1}: {dict(list(row.items())[:5])}...')
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'Ошибка парсинга: {"; ".join(parse_result["errors"])}'
                    )
                )
            
            # Удаляем тестовую запись
            import_file.delete()
            return

        # Обрабатываем импорт
        try:
            processor = ImportProcessor(import_file)
            result = processor.process_import()
            
            if result['success']:
                stats = result['statistics']
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Импорт завершен успешно!\n'
                        f'Всего строк: {stats["total_rows"]}\n'
                        f'Обработано: {stats["processed_rows"]}\n'
                        f'Успешно: {stats["successful_rows"]}\n'
                        f'Ошибок: {stats["failed_rows"]}\n'
                        f'Обновлено объектов: {stats["updated_count"]}\n'
                        f'Создано объектов: {stats["created_count"]}\n'
                        f'Процент успеха: {stats["success_rate"]}%'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Ошибка импорта: {result["message"]}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Критическая ошибка: {str(e)}')
            )
            raise CommandError(f'Импорт не удался: {str(e)}')