from django.core.management.base import BaseCommand
from django.db import transaction
from apps.currency.models import Currency, ExchangeRate
from apps.properties.models import Property
from decimal import Decimal
from datetime import date


class Command(BaseCommand):
    help = 'Мигрирует цены недвижимости с USD на THB как базовую валюту'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать что будет сделано, без изменений в БД'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('ТЕСТОВЫЙ РЕЖИМ: изменения не будут сохранены в БД')
            )
        
        self.stdout.write('Начинаем миграцию цен с USD на THB как базовую валюту...')
        
        try:
            # Получаем валюты
            usd_currency = Currency.objects.get(code='USD')
            thb_currency = Currency.objects.get(code='THB')
            
            # Получаем текущий курс USD/THB
            try:
                usd_to_thb_rate = ExchangeRate.objects.filter(
                    base_currency=usd_currency,
                    target_currency=thb_currency,
                    date=date.today()
                ).first()
                
                if not usd_to_thb_rate:
                    # Ищем последний доступный курс
                    usd_to_thb_rate = ExchangeRate.objects.filter(
                        base_currency=usd_currency,
                        target_currency=thb_currency
                    ).order_by('-date').first()
                
                if not usd_to_thb_rate:
                    raise ExchangeRate.DoesNotExist("Курс USD/THB не найден")
                    
                conversion_rate = usd_to_thb_rate.rate
                self.stdout.write(f'Используем курс USD/THB: {conversion_rate}')
                
            except ExchangeRate.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        'Курс обмена USD/THB не найден. '
                        'Сначала запустите команду update_exchange_rates'
                    )
                )
                return
        
        except Currency.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(f'Валюта не найдена: {e}')
            )
            return

        # Получаем все объекты недвижимости с ценами в USD
        properties_with_usd = Property.objects.filter(
            price_sale_usd__isnull=False
        )
        
        total_properties = properties_with_usd.count()
        self.stdout.write(f'Найдено {total_properties} объектов с ценами в USD')
        
        if total_properties == 0:
            self.stdout.write(
                self.style.WARNING('Нет объектов для миграции')
            )
            return

        migrated_count = 0
        
        with transaction.atomic():
            for prop in properties_with_usd:
                updated = False
                
                # Конвертируем цену продажи
                if prop.price_sale_usd and not prop.price_sale_thb:
                    new_thb_price = prop.price_sale_usd * conversion_rate
                    if not dry_run:
                        prop.price_sale_thb = new_thb_price
                        updated = True
                    
                    self.stdout.write(
                        f'  Объект {prop.id}: {prop.price_sale_usd} USD -> '
                        f'{new_thb_price:.0f} THB'
                    )
                
                # Конвертируем цену аренды
                if prop.price_rent_monthly and not prop.price_rent_monthly_thb:
                    new_thb_rent = prop.price_rent_monthly * conversion_rate
                    if not dry_run:
                        prop.price_rent_monthly_thb = new_thb_rent
                        updated = True
                    
                    self.stdout.write(
                        f'  Аренда {prop.id}: {prop.price_rent_monthly} USD -> '
                        f'{new_thb_rent:.0f} THB/месяц'
                    )
                
                if updated and not dry_run:
                    prop.save()
                    migrated_count += 1
                elif not dry_run:
                    migrated_count += 1

            if dry_run:
                # Откатываем транзакцию в тестовом режиме
                transaction.set_rollback(True)
                
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'ТЕСТОВЫЙ РЕЖИМ завершен. Было бы обработано {total_properties} объектов'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Миграция завершена: обработано {migrated_count} объектов'
                )
            )
            
            # Теперь обновляем настройки валют
            self.stdout.write('Обновляем настройки базовой валюты...')
            
            # Устанавливаем THB как базовую валюту
            Currency.objects.filter(code='USD').update(is_base=False)
            Currency.objects.filter(code='THB').update(is_base=True)
            
            self.stdout.write(
                self.style.SUCCESS(
                    'THB установлен как базовая валюта'
                )
            )