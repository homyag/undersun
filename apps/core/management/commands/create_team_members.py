from django.core.management.base import BaseCommand
from apps.core.models import Team


class Command(BaseCommand):
    help = 'Create initial team members from the original template data'

    def handle(self, *args, **options):
        # Проверяем, есть ли уже сотрудники
        if Team.objects.exists():
            self.stdout.write(
                self.style.WARNING('Team members already exist. Use --force to recreate.')
            )
            return

        team_data = [
            # Основная команда для главной страницы
            {
                'first_name': 'Bogdan',
                'last_name': 'Dyachuk', 
                'position': 'Sales Director',
                'role': 'sales_director',
                'phone': '+66827268615',
                'email': 'bd@undersunestate.com',
                'whatsapp': '+66827268615',
                'show_on_homepage': True,
                'display_order': 1,
                'bio': 'Директор по продажам с многолетним опытом работы на рынке недвижимости Пхукета',
                'languages': 'Русский, Английский, Украинский',
                'specialization': 'Продажа элитной недвижимости, инвестиционные проекты'
            },
            {
                'first_name': 'Kirill',
                'last_name': 'Dedyugin',
                'position': 'Senior Manager for International Client Relations', 
                'role': 'senior_manager',
                'phone': '+66625392970',
                'whatsapp': '+66625392970',
                'show_on_homepage': True,
                'display_order': 2,
                'bio': 'Старший менеджер по работе с международными клиентами',
                'languages': 'Русский, Английский',
                'specialization': 'Международные сделки, консультации по инвестициям'
            },
            {
                'first_name': 'Vitalii',
                'last_name': 'Savchuk',
                'position': 'Manager for International Client Relations',
                'role': 'manager', 
                'phone': '+66836087179',
                'whatsapp': '+66836087179',
                'show_on_homepage': True,
                'display_order': 3,
                'bio': 'Менеджер по работе с международными клиентами',
                'languages': 'Русский, Английский',
                'specialization': 'Подбор недвижимости, сопровождение сделок'
            },
            
            # Дополнительная команда
            {
                'first_name': 'Ilya',
                'last_name': 'Ordovskii-Tanaevskii',
                'position': 'Chief Art Officer (CAO)',
                'role': 'chief_art_officer',
                'phone': '+66994402232', 
                'email': 'iot@undersunestate.com',
                'whatsapp': '+66994402232',
                'show_on_homepage': False,
                'display_order': 4,
                'bio': 'Главный по креативу и маркетинговым материалам',
                'languages': 'Русский, Английский',
                'specialization': 'Креативные решения, брендинг, дизайн'
            },
            {
                'first_name': 'Tatiana',
                'last_name': 'Korostyleva',
                'position': 'Chief Marketing Officer (CMO)',
                'role': 'chief_marketing_officer',
                'phone': '+79177188313',
                'email': 'tatyanak@undersunestate.com',
                'whatsapp': '+79177188313',
                'show_on_homepage': False,
                'display_order': 5,
                'bio': 'Директор по маркетингу, отвечает за продвижение и рекламу',
                'languages': 'Русский, Английский',
                'specialization': 'Цифровой маркетинг, SEO, контент-стратегия'
            },
            {
                'first_name': 'Aleksei',
                'last_name': 'Kljujev', 
                'position': 'Chief Financial Officer (CFO)',
                'role': 'chief_financial_officer',
                'phone': '+66945955257',
                'email': 'alex@undersunestate.com',
                'whatsapp': '+66945955257',
                'show_on_homepage': False,
                'display_order': 6,
                'bio': 'Финансовый директор, контролирует финансовые операции',
                'languages': 'Русский, Английский',
                'specialization': 'Финансовое планирование, налоговое консультирование'
            },
            {
                'first_name': 'Withanyu',
                'last_name': 'Satchaphan',
                'position': 'Office Manager',
                'role': 'office_manager',
                'show_on_homepage': False,
                'display_order': 7,
                'bio': 'Офис-менеджер, координирует работу офиса',
                'languages': 'Тайский, Английский',
                'specialization': 'Административная поддержка, координация'
            }
        ]

        created_count = 0
        for member_data in team_data:
            team_member = Team.objects.create(**member_data)
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f'Created team member: {team_member.full_name}')
            )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} team members!')
        )
        self.stdout.write(
            self.style.SUCCESS(f'{sum(1 for m in team_data if m["show_on_homepage"])} members will be shown on homepage')
        )