"""Сервис для проверки Google reCAPTCHA v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class RecaptchaResult:
    success: bool
    message: str = ''
    score: float = 0.0
    action: str = ''


def verify_recaptcha(token: Optional[str], action: str = '') -> RecaptchaResult:
    """Проверяет токен reCAPTCHA через API Google."""
    site_secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
    verify_url = getattr(settings, 'RECAPTCHA_VERIFY_URL', '')
    min_score = getattr(settings, 'RECAPTCHA_MIN_SCORE', 0.5)

    if not site_secret or not verify_url:
        logger.warning('reCAPTCHA is not configured; skipping verification')
        return RecaptchaResult(success=True, message='Recaptcha disabled')

    if not token:
        return RecaptchaResult(success=False, message='Отсутствует подтверждение reCAPTCHA')

    try:
        response = requests.post(
            verify_url,
            data={
                'secret': site_secret,
                'response': token,
            },
            timeout=5,
        )
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except requests.RequestException as exc:
        logger.error('reCAPTCHA verify failed: %s', exc, exc_info=exc)
        return RecaptchaResult(success=False, message='Ошибка проверки reCAPTCHA')

    success = bool(data.get('success'))
    score = float(data.get('score') or 0.0)
    response_action = data.get('action') or ''

    if not success:
        return RecaptchaResult(success=False, message='Проверка reCAPTCHA не пройдена')

    if score < min_score:
        logger.warning('reCAPTCHA score too low: %.2f < %.2f', score, min_score)
        return RecaptchaResult(success=False, message='Вы похожи на бота. Попробуйте ещё раз.')

    if action and response_action and action != response_action:
        logger.warning('reCAPTCHA action mismatch: expected %s, got %s', action, response_action)
        return RecaptchaResult(success=False, message='Проверка reCAPTCHA не пройдена')

    return RecaptchaResult(success=True, score=score, action=response_action)
