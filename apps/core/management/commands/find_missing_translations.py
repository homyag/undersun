import csv

from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q


class Command(BaseCommand):
    help = (
        "Finds modeltranslation fields where the source language is filled "
        "but the target language is empty."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="ru",
            help="Source language code (default: ru)",
        )
        parser.add_argument(
            "--lang",
            default="en",
            help="Target language code to audit (default: en)",
        )
        parser.add_argument(
            "--model",
            default=None,
            help="Limit audit to one model: app_label.ModelName",
        )
        parser.add_argument(
            "--ids",
            action="store_true",
            help="Print first 50 object IDs for each field with missing translations",
        )
        parser.add_argument(
            "--csv",
            default=None,
            metavar="PATH",
            help="Write full result to CSV: model, pk, field, source_preview",
        )

    def handle(self, *args, **options):
        try:
            from modeltranslation.translator import translator
        except ImportError as exc:
            raise CommandError("django-modeltranslation is not installed") from exc

        source = options["source"]
        target = options["lang"]
        only_model = (options["model"] or "").lower()

        csv_file = None
        csv_writer = None
        if options["csv"]:
            csv_file = open(options["csv"], "w", newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["model", "pk", "field", "source_preview"])

        try:
            summary_rows = []
            grand_total = 0

            for model in translator.get_registered_models(abstract=False):
                model_label = f"{model._meta.app_label}.{model.__name__}"
                if only_model and model_label.lower() != only_model:
                    continue

                translation_options = translator.get_options_for_model(model)
                field_names = self._get_translated_field_names(translation_options)

                for base_field in field_names:
                    source_field = f"{base_field}_{source}"
                    target_field = f"{base_field}_{target}"
                    if not self._has_fields(model, source_field, target_field):
                        continue

                    queryset = (
                        model._default_manager
                        .exclude(
                            Q(**{f"{source_field}__isnull": True})
                            | Q(**{source_field: ""})
                        )
                        .filter(
                            Q(**{f"{target_field}__isnull": True})
                            | Q(**{target_field: ""})
                        )
                    )
                    count = queryset.count()
                    if not count:
                        continue

                    summary_rows.append((model_label, base_field, count))
                    grand_total += count

                    if options["ids"]:
                        ids = list(queryset.values_list("pk", flat=True)[:50])
                        suffix = " ..." if count > 50 else ""
                        self.stdout.write(
                            f"    {model_label}.{base_field}: ids={ids}{suffix}"
                        )

                    if csv_writer:
                        for pk, source_value in queryset.values_list("pk", source_field):
                            preview = str(source_value or "")[:120].replace("\n", " ")
                            csv_writer.writerow([model_label, pk, base_field, preview])
        finally:
            if csv_file:
                csv_file.close()

        if not summary_rows:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No missing translations found for {source} -> {target}."
                )
            )
            return

        self.stdout.write("")
        self.stdout.write(f"Missing translations {source} -> {target}:")
        self.stdout.write("-" * 72)
        width = max(len(f"{model}.{field}") for model, field, _ in summary_rows) + 2
        for model_label, field, count in sorted(summary_rows, key=lambda row: -row[2]):
            self.stdout.write(f"  {(model_label + '.' + field).ljust(width)} {count}")
        self.stdout.write("-" * 72)
        self.stdout.write(
            self.style.WARNING(
                f"Total gaps: {grand_total}. Each gap can fall back to "
                f"'{source}' text on '{target}' pages."
            )
        )
        if options["csv"]:
            self.stdout.write(f"CSV saved: {options['csv']}")

    @staticmethod
    def _get_translated_field_names(translation_options):
        if hasattr(translation_options, "get_field_names"):
            return sorted(translation_options.get_field_names())
        return sorted(translation_options.fields.keys())

    @staticmethod
    def _has_fields(model, *field_names):
        for field_name in field_names:
            try:
                model._meta.get_field(field_name)
            except FieldDoesNotExist:
                return False
        return True
