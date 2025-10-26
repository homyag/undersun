import logging
from typing import Iterable, Optional, Sequence, Tuple

from django.conf import settings
from django.core.mail import mail_admins
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

DetailItem = Tuple[str, object]


def build_admin_change_url(instance) -> Optional[str]:
    """Получить URL записи в админке."""
    if not instance or not getattr(instance, 'pk', None):
        return None

    try:
        return reverse(
            f"admin:{instance._meta.app_label}_{instance._meta.model_name}_change",
            args=[instance.pk],
        )
    except NoReverseMatch:
        logger.debug(
            "Не удалось построить admin URL для %s", instance.__class__.__name__
        )
        return None


def _format_details(details: Sequence[DetailItem]) -> str:
    lines = []
    for label, value in details:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _maybe_absolute(url: Optional[str], request) -> Optional[str]:
    if not url or url.startswith('http'):
        return url
    if request is None:
        return url
    try:
        return request.build_absolute_uri(url)
    except Exception:  # pragma: no cover - уходим в relative URL при ошибке
        logger.debug("Не удалось построить абсолютный URL для %s", url)
        return url


def notify_admins_about_submission(
    *,
    form_name: str,
    details: Sequence[DetailItem],
    request=None,
    subject_context: Optional[str] = None,
    admin_url: Optional[str] = None,
    extra_lines: Optional[Iterable[str]] = None,
) -> None:
    """Отправить уведомление администраторам о новой заявке."""
    if not getattr(settings, 'ADMINS', None):
        logger.debug(
            "Пропущено уведомление для '%s' — ADMINS не настроены", form_name
        )
        return

    subject = _("Новая заявка: %(form)s") % {"form": form_name}
    if subject_context:
        subject = f"{subject} — {subject_context}"

    admin_link = _maybe_absolute(admin_url, request)

    message_lines = []
    if extra_lines:
        filtered = [line.strip() for line in extra_lines if str(line).strip()]
        message_lines.extend(filtered)

    details_block = _format_details(details)
    if details_block:
        if message_lines:
            message_lines.append("")
        message_lines.append(_("Данные заявки:"))
        message_lines.append(details_block)

    if admin_link:
        message_lines.append("")
        message_lines.append(
            _("Запись в админке: %(url)s") % {"url": admin_link}
        )

    message = "\n".join(message_lines) if message_lines else subject

    try:
        logger.warning(
            "Отправляем уведомление '%s' для %s",
            subject,
            settings.ADMINS,
        )
        mail_admins(subject, message, fail_silently=False)
        logger.warning(
            "Уведомление '%s' успешно отправлено",
            subject,
        )
    except Exception:
        logger.exception(
            "Не удалось отправить уведомление администраторам по форме '%s'",
            form_name,
        )
