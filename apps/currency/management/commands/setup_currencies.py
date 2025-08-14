from django.core.management.base import BaseCommand
from apps.currency.models import Currency, CurrencyPreference


class Command(BaseCommand):
    help = 'Настраивает основные валюты и языковые предпочтения'

    def handle(self, *args, **options):
        self.stdout.write('Настройка валют...')
        
        # Создаем основные валюты
        currencies_data = [
            {
                'code': 'USD',
                'name': 'US Dollar',
                'name_ru': 'Доллар США',
                'name_en': 'US Dollar',
                'name_th': 'ดอลลาร์สหรัฐ',
                'symbol': '$',
                'is_base': False,
                'decimal_places': 2
            },
            {
                'code': 'THB',
                'name': 'Thai Baht',
                'name_ru': 'Тайский бат',
                'name_en': 'Thai Baht', 
                'name_th': 'บาทไทย',
                'symbol': '฿',
                'is_base': True,
                'decimal_places': 0  # Обычно баты считают без копеек
            },
            {
                'code': 'RUB',
                'name': 'Russian Ruble',
                'name_ru': 'Российский рубль',
                'name_en': 'Russian Ruble',
                'name_th': 'รูเบิลรัสเซีย',
                'symbol': '₽',
                'is_base': False,
                'decimal_places': 0  # Обычно рубли считают без копеек
            },
        ]

        created_count = 0
        updated_count = 0

        for currency_data in currencies_data:
            currency, created = Currency.objects.update_or_create(
                code=currency_data['code'],
                defaults=currency_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'  + Создана валюта: {currency}')
            else:
                updated_count += 1
                self.stdout.write(f'  ~ Обновлена валюта: {currency}')

        # Настраиваем языковые предпочтения
        self.stdout.write('\nНастройка языковых предпочтений...')
        
        try:
            usd = Currency.objects.get(code='USD')
            thb = Currency.objects.get(code='THB')
            rub = Currency.objects.get(code='RUB')
            
            preferences = [
                {'language': 'en', 'default_currency': thb},
                {'language': 'th', 'default_currency': thb},
                {'language': 'ru', 'default_currency': rub},
            ]
            
            for pref_data in preferences:
                pref, created = CurrencyPreference.objects.update_or_create(
                    language=pref_data['language'],
                    defaults={'default_currency': pref_data['default_currency']}
                )
                
                if created:
                    self.stdout.write(f'  + Создано предпочтение: {pref}')
                else:
                    self.stdout.write(f'  ~ Обновлено предпочтение: {pref}')
                    
        except Currency.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при настройке предпочтений: {e}')
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Настройка завершена: валют создано {created_count}, обновлено {updated_count}'
            )
        )