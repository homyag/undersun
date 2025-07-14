import requests
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.currency.models import Currency, ExchangeRate


class Command(BaseCommand):
    help = 'Обновляет курсы валют с помощью ExchangeRate-API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-currency',
            type=str,
            default='THB',
            help='Базовая валюта для получения курсов (по умолчанию THB)'
        )
        parser.add_argument(
            '--api-url',
            type=str,
            default='https://api.exchangerate-api.com/v4/latest/',
            help='URL API для получения курсов валют'
        )

    def handle(self, *args, **options):
        base_currency_code = options['base_currency']
        api_url = options['api_url']
        
        try:
            # Получаем базовую валюту
            base_currency = Currency.objects.get(code=base_currency_code, is_active=True)
        except Currency.DoesNotExist:
            raise CommandError(f'Базовая валюта {base_currency_code} не найдена или неактивна')

        # Получаем все активные валюты кроме базовой
        target_currencies = Currency.objects.filter(is_active=True).exclude(code=base_currency_code)
        
        if not target_currencies.exists():
            self.stdout.write(
                self.style.WARNING('Нет активных целевых валют для обновления курсов')
            )
            return

        # Делаем запрос к API
        self.stdout.write(f'Получение курсов валют для {base_currency_code}...')
        
        try:
            response = requests.get(f'{api_url}{base_currency_code}', timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise CommandError(f'Ошибка при запросе к API: {e}')
        except ValueError as e:
            raise CommandError(f'Ошибка при парсинге JSON ответа: {e}')

        if 'rates' not in data:
            raise CommandError('API не вернул данные о курсах валют')

        rates = data['rates']
        today = date.today()
        updated_count = 0
        created_count = 0

        # Обновляем курсы для каждой целевой валюты
        for target_currency in target_currencies:
            target_code = target_currency.code
            
            if target_code not in rates:
                self.stdout.write(
                    self.style.WARNING(f'Курс для {target_code} не найден в API ответе')
                )
                continue

            rate_value = Decimal(str(rates[target_code]))
            
            # Создаем или обновляем курс
            exchange_rate, created = ExchangeRate.objects.update_or_create(
                base_currency=base_currency,
                target_currency=target_currency,
                date=today,
                defaults={
                    'rate': rate_value,
                    'source': 'exchangerate-api.com'
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f'  + Создан курс {base_currency_code}/{target_code}: {rate_value}')
            else:
                updated_count += 1
                self.stdout.write(f'  ~ Обновлен курс {base_currency_code}/{target_code}: {rate_value}')

        # Также обновляем цены в недвижимости
        self.update_property_prices()

        # Выводим итоги
        self.stdout.write(
            self.style.SUCCESS(
                f'Обновление завершено: создано {created_count}, обновлено {updated_count} курсов'
            )
        )

    def update_property_prices(self):
        """Обновляет цены в объектах недвижимости на основе новых курсов"""
        from apps.properties.models import Property
        
        self.stdout.write('Обновление цен в объектах недвижимости...')
        
        try:
            usd_currency = Currency.objects.get(code='USD')
            thb_currency = Currency.objects.get(code='THB') 
            rub_currency = Currency.objects.get(code='RUB')
        except Currency.DoesNotExist as e:
            self.stdout.write(
                self.style.WARNING(f'Не все необходимые валюты найдены: {e}')
            )
            return

        # Теперь базовая валюта THB, поэтому ищем объекты с ценами в THB
        properties = Property.objects.filter(price_sale_thb__isnull=False)
        updated_properties = 0

        for prop in properties:
            updated = False
            
            # Обновляем цены продажи (THB -> USD, RUB)
            if prop.price_sale_thb:
                # Обновляем цену в USD
                usd_price = ExchangeRate.convert_amount(prop.price_sale_thb, thb_currency, usd_currency)
                if usd_price:
                    prop.price_sale_usd = usd_price
                    updated = True
                
                # Обновляем цену в RUB
                rub_price = ExchangeRate.convert_amount(prop.price_sale_thb, thb_currency, rub_currency)
                if rub_price:
                    prop.price_sale_rub = rub_price
                    updated = True

            # Обновляем цены аренды (THB -> USD, RUB)
            if prop.price_rent_monthly_thb:
                # Обновляем цену аренды в USD
                usd_rent = ExchangeRate.convert_amount(prop.price_rent_monthly_thb, thb_currency, usd_currency)
                if usd_rent:
                    prop.price_rent_monthly = usd_rent
                    updated = True
                
                # Обновляем цену аренды в RUB
                rub_rent = ExchangeRate.convert_amount(prop.price_rent_monthly_thb, thb_currency, rub_currency)
                if rub_rent:
                    prop.price_rent_monthly_rub = rub_rent
                    updated = True

            if updated:
                prop.save()
                updated_properties += 1

        self.stdout.write(f'  Обновлено цен в {updated_properties} объектах недвижимости')