import re
from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.services import translation_service


PLACEHOLDER_PATTERN = re.compile(r"%\([\w_]+\)s|%s|\{[\w_]+\}")


class Command(BaseCommand):
    help = "Автоматически заполняет отсутствующие переводы в .po файлах через Yandex Translate"

    def add_arguments(self, parser):
        parser.add_argument(
            "--languages",
            nargs="+",
            help="Список языков (по умолчанию используются целевые языки TranslationService)",
        )
        parser.add_argument(
            "--po-file",
            dest="po_file",
            help="Явно указанный путь к .po файлу (если нужно обработать отдельный файл)",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Перезаписать уже заполненные переводы",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать сколько записей будет переведено, без изменения файлов",
        )

    def handle(self, *args, **options):
        if not translation_service.is_configured():
            raise RuntimeError("Translation service is not configured. Set YANDEX_TRANSLATE_* env vars.")

        languages = options["languages"] or translation_service.translation_settings["target_languages"]
        po_file_override = options.get("po_file")
        overwrite = options["overwrite"]
        dry_run = options["dry_run"]

        total_translated = 0
        for lang in languages:
            po_path = self._resolve_po_path(lang, po_file_override)
            if not po_path.exists():
                self.stdout.write(self.style.WARNING(f"Файл {po_path} не найден, пропускаем"))
                continue

            po = polib.pofile(str(po_path))

            translated_count = self._process_po(po, lang, overwrite=overwrite, dry_run=dry_run)
            total_translated += translated_count

            if translated_count and not dry_run:
                po.save()
                self.stdout.write(self.style.SUCCESS(f"Сохранены изменения в {po_path}"))
            self.stdout.write(
                f"{po_path}: добавлено переводов — {translated_count}{' (dry-run)' if dry_run else ''}"
            )

        if total_translated and not dry_run:
            self.stdout.write(self.style.NOTICE("Не забудьте выполнить `python manage.py compilemessages`"))
        elif total_translated == 0:
            self.stdout.write("Новых переводов не найдено")

    def _resolve_po_path(self, language_code, override):
        if override:
            return Path(override)
        return Path(settings.BASE_DIR) / "locale" / language_code / "LC_MESSAGES" / "django.po"

    def _process_po(self, po, language_code, overwrite=False, dry_run=False):
        translated_entries = 0
        for entry in po:
            if entry.obsolete:
                continue

            if entry.msgid_plural:
                changed = self._translate_plural_entry(entry, language_code, overwrite, dry_run)
            else:
                changed = self._translate_entry(entry, language_code, overwrite, dry_run)

            if changed:
                translated_entries += 1

        return translated_entries

    def _translate_entry(self, entry, language_code, overwrite=False, dry_run=False):
        if not overwrite and entry.msgstr.strip():
            return False

        source_text = entry.msgid.strip()
        if not source_text:
            return False

        if PLACEHOLDER_PATTERN.search(source_text):
            return False

        if dry_run:
            return True

        preserve_html = "<" in source_text and ">" in source_text
        translated = translation_service.translate_text(
            source_text,
            language_code,
            preserve_html=preserve_html,
        )

        if not translated:
            return False

        if not dry_run:
            entry.msgstr = translated
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
        return True

    def _translate_plural_entry(self, entry, language_code, overwrite=False, dry_run=False):
        changed = False
        plural_items = entry.msgstr_plural or {}
        if not plural_items:
            # Инициализируем базовыми ключами (обычно "0" и "1")
            plural_items = {key: "" for key in self._infer_plural_keys(language_code)}

        for key in sorted(plural_items.keys(), key=int):
            current_translation = plural_items.get(key, "").strip()
            if current_translation and not overwrite:
                continue

            source_text = entry.msgid if key == "0" else entry.msgid_plural
            if not source_text:
                continue

            if PLACEHOLDER_PATTERN.search(source_text):
                continue

            if dry_run:
                changed = True
                continue

            preserve_html = "<" in source_text and ">" in source_text
            translated = translation_service.translate_text(
                source_text,
                language_code,
                preserve_html=preserve_html,
            )

            if not translated:
                continue

            if not dry_run:
                entry.msgstr_plural[key] = translated
                if "fuzzy" in entry.flags:
                    entry.flags.remove("fuzzy")
            changed = True

        return changed

    @staticmethod
    def _infer_plural_keys(language_code):
        # Простая эвристика: en — 0,1; th — 0; по умолчанию 0,1
        if language_code == "th":
            return ["0"]
        return ["0", "1"]
