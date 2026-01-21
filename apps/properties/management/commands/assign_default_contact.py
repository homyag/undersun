from django.core.management.base import BaseCommand
from apps.properties.models import Property
from apps.core.models import Team


class Command(BaseCommand):
    help = 'Назначает контактное лицо по умолчанию объектам недвижимости'

    def add_arguments(self, parser):
        parser.add_argument(
            '--contact-id',
            type=int,
            default=2,
            help='ID сотрудника для назначения (по умолчанию: 2 - Kirill Dedyugin)'
        )
        parser.add_argument(
            '--override-existing',
            action='store_true',
            help='Назначить выбранного менеджера всем объектам, даже если он уже указан'
        )

    def handle(self, *args, **options):
        contact_id = options['contact_id']
        override_existing = options['override_existing']

        try:
            contact_person = Team.objects.get(id=contact_id)
        except Team.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Сотрудник с ID {contact_id} не найден'))
            return

        # Находим подходящие объекты
        if override_existing:
            properties_qs = Property.objects.all()
        else:
            properties_qs = Property.objects.filter(contact_person__isnull=True)

        count = properties_qs.count()

        if count == 0:
            message = 'Все объекты уже имеют контактное лицо' if not override_existing else \
                'Объекты для обновления не найдены'
            self.stdout.write(self.style.SUCCESS(message))
            return

        # Назначаем контактное лицо
        updated = properties_qs.update(contact_person=contact_person)

        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно назначен менеджер "{contact_person.first_name} {contact_person.last_name}" '
                f'для {updated} объект(ов)'
            )
        )
