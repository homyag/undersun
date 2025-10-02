from django.core.management.base import BaseCommand
from apps.properties.models import Property
from apps.core.models import Team


class Command(BaseCommand):
    help = 'Назначает контактное лицо по умолчанию всем объектам без менеджера'

    def add_arguments(self, parser):
        parser.add_argument(
            '--contact-id',
            type=int,
            default=1,
            help='ID сотрудника для назначения (по умолчанию: 1 - Bogdan)'
        )

    def handle(self, *args, **options):
        contact_id = options['contact_id']

        try:
            contact_person = Team.objects.get(id=contact_id)
        except Team.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Сотрудник с ID {contact_id} не найден'))
            return

        # Находим все объекты без контактного лица
        properties_without_contact = Property.objects.filter(contact_person__isnull=True)
        count = properties_without_contact.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Все объекты уже имеют контактное лицо'))
            return

        # Назначаем контактное лицо
        updated = properties_without_contact.update(contact_person=contact_person)

        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно назначен менеджер "{contact_person.first_name} {contact_person.last_name}" '
                f'для {updated} объект(ов)'
            )
        )