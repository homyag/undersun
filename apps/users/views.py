import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _
from django.utils import timezone
from django.shortcuts import get_object_or_404

from apps.properties.models import Property
from apps.core.recaptcha import verify_recaptcha
from apps.core.utils import validate_form_security
from .models import (
    PropertyInquiry,
    QuickConsultationRequest,
    ContactFormSubmission,
    OfficeVisitRequest,
    FAQQuestion,
    NewsletterSubscription
)
from .notifications import build_admin_change_url, notify_admins_about_submission


logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Получение IP адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def _check_recaptcha(request):
    """Проверяем токен reCAPTCHA и возвращаем JsonResponse при ошибке."""
    token = request.POST.get('g-recaptcha-response')
    action = request.POST.get('recaptcha_action')
    result = verify_recaptcha(token, action=action)
    if not result.success:
        return JsonResponse({'success': False, 'message': result.message}, status=400)
    return None


@require_http_methods(["POST"])
def property_inquiry_view(request, property_id):
    """Обработка запросов по конкретному объекту (просмотр/консультация)"""
    try:
        recaptcha_error = _check_recaptcha(request)
        if recaptcha_error:
            return recaptcha_error

        security_error = validate_form_security(request)
        if security_error:
            return security_error

        property_obj = get_object_or_404(Property, id=property_id)

        # Получаем данные из формы
        inquiry_type = request.POST.get('inquiry_type', 'general')
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()

        # Валидация обязательных полей
        if not name or not phone:
            return JsonResponse({
                'success': False,
                'message': _('Пожалуйста, заполните имя и телефон')
            }, status=400)

        # Создаем запрос
        inquiry = PropertyInquiry.objects.create(
            property=property_obj,
            inquiry_type=inquiry_type,
            name=name,
            phone=phone,
            email=email,
            message=message,
        )

        # Дополнительные поля для записи на просмотр
        if inquiry_type == 'viewing':
            preferred_date = request.POST.get('preferred_date')
            if preferred_date:
                inquiry.preferred_date = preferred_date
                inquiry.save()

        # Дополнительные поля для консультации
        if inquiry_type == 'consultation':
            consultation_topic = request.POST.get('consultation_topic')
            preferred_contact = request.POST.get('preferred_contact')
            if consultation_topic:
                inquiry.consultation_topic = consultation_topic
            if preferred_contact:
                inquiry.preferred_contact = preferred_contact
            inquiry.save()

        # TODO: Интеграция с AmoCRM
        # send_to_amocrm(inquiry)

        details = [
            (_('Объект'), property_obj.title),
            (_('Тип запроса'), inquiry.get_inquiry_type_display()),
            (_('Имя'), inquiry.name),
            (_('Телефон'), inquiry.phone),
        ]

        if inquiry.email:
            details.append((_('Email'), inquiry.email))

        if inquiry.preferred_date:
            preferred_date = inquiry.preferred_date
            if hasattr(preferred_date, 'strftime'):
                try:
                    preferred_date = timezone.localtime(preferred_date)
                except Exception:
                    pass
                else:
                    preferred_date = preferred_date.strftime('%d.%m.%Y %H:%M')
            details.append((_('Желаемая дата'), preferred_date))

        if inquiry.consultation_topic:
            topic_display = dict(PropertyInquiry.CONSULTATION_TOPICS).get(
                inquiry.consultation_topic,
                inquiry.consultation_topic,
            )
            details.append((_('Тема консультации'), topic_display))

        if inquiry.preferred_contact:
            contact_display = dict(PropertyInquiry.CONTACT_PREFERENCES).get(
                inquiry.preferred_contact,
                inquiry.preferred_contact,
            )
            details.append((_('Предпочтительный способ связи'), contact_display))

        if inquiry.message:
            details.append((_('Сообщение'), inquiry.message))

        details.append(
            (_('Создано'), timezone.localtime(inquiry.created_at).strftime('%d.%m.%Y %H:%M'))
        )

        property_url = request.build_absolute_uri(property_obj.get_absolute_url())

        notify_admins_about_submission(
            form_name=_('Запрос по объекту'),
            subject_context=property_obj.title,
            details=details,
            admin_url=build_admin_change_url(inquiry),
            request=request,
            extra_lines=[
                _('Ссылка на объект: %(url)s') % {'url': property_url},
            ],
        )

        return JsonResponse({
            'success': True,
            'message': _('Спасибо! Ваша заявка принята. Наш менеджер свяжется с вами в ближайшее время.')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': _('Произошла ошибка. Пожалуйста, попробуйте позже.')
        }, status=500)



@require_http_methods(["POST"])
def quick_consultation_view(request):
    """Быстрый запрос консультации (форма с телефоном)"""
    try:
        recaptcha_error = _check_recaptcha(request)
        if recaptcha_error:
            return recaptcha_error

        security_error = validate_form_security(request)
        if security_error:
            return security_error

        phone = request.POST.get('phone', '').strip()

        if not phone:
            return JsonResponse({
                'success': False,
                'message': _('Пожалуйста, укажите номер телефона')
            }, status=400)

        # Создаем запрос
        consultation = QuickConsultationRequest.objects.create(
            phone=phone,
            source_page=request.META.get('HTTP_REFERER', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            ip_address=get_client_ip(request)
        )

        # TODO: Интеграция с AmoCRM
        # send_to_amocrm(consultation)

        details = [
            (_('Телефон'), consultation.phone),
            (_('Страница отправки'), consultation.source_page),
            (_('IP адрес'), consultation.ip_address),
            (_('User Agent'), consultation.user_agent),
            (
                _('Создано'),
                timezone.localtime(consultation.created_at).strftime('%d.%m.%Y %H:%M'),
            ),
        ]

        notify_admins_about_submission(
            form_name=_('Быстрая консультация'),
            subject_context=consultation.phone,
            details=details,
            admin_url=build_admin_change_url(consultation),
            request=request,
        )

        return JsonResponse({
            'success': True,
            'message': _('Спасибо! Мы свяжемся с вами в течение 30 минут и подберем 3 лучших объекта.')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': _('Произошла ошибка. Пожалуйста, попробуйте позже.')
        }, status=500)


@require_http_methods(["POST"])
def contact_form_view(request):
    """Обработка общей контактной формы"""
    try:
        recaptcha_error = _check_recaptcha(request)
        if recaptcha_error:
            return recaptcha_error

        security_error = validate_form_security(request)
        if security_error:
            return security_error

        logger.warning("contact_form_view POST: %s", dict(request.POST))
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        subject = request.POST.get('subject', 'other')
        message = request.POST.get('message', '').strip()

        # Валидация
        if not name or not email or not message:
            return JsonResponse({
                'success': False,
                'message': _('Пожалуйста, заполните все обязательные поля')
            }, status=400)

        # Создаем запись
        submission = ContactFormSubmission.objects.create(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message
        )

        # TODO: Интеграция с AmoCRM
        # send_to_amocrm(submission)

        details = [
            (_('Имя'), submission.name),
            (_('Email'), submission.email),
        ]

        if submission.phone:
            details.append((_('Телефон'), submission.phone))

        details.append((_('Тема'), submission.get_subject_display()))

        if submission.message:
            details.append((_('Сообщение'), submission.message))

        details.append(
            (_('Создано'), timezone.localtime(submission.created_at).strftime('%d.%m.%Y %H:%M'))
        )

        notify_admins_about_submission(
            form_name=_('Контактная форма'),
            subject_context=submission.get_subject_display(),
            details=details,
            admin_url=build_admin_change_url(submission),
            request=request,
            extra_lines=[
                _('Источник запроса: %(url)s')
                % {'url': request.META.get('HTTP_REFERER', '')},
            ],
        )

        return JsonResponse({
            'success': True,
            'message': _('Спасибо за обращение! Мы ответим вам в ближайшее время.')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': _('Произошла ошибка. Пожалуйста, попробуйте позже.')
        }, status=500)


@require_http_methods(["POST"])
def office_visit_request_view(request):
    """Запись на встречу в офисе"""
    try:
        recaptcha_error = _check_recaptcha(request)
        if recaptcha_error:
            return recaptcha_error

        security_error = validate_form_security(request)
        if security_error:
            return security_error

        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        preferred_date = request.POST.get('preferred_date', '').strip()
        message = request.POST.get('message', '').strip()

        # Валидация
        if not name or not phone or not preferred_date:
            return JsonResponse({
                'success': False,
                'message': _('Пожалуйста, заполните имя, телефон и дату')
            }, status=400)

        # Создаем запись
        visit_request = OfficeVisitRequest.objects.create(
            name=name,
            phone=phone,
            preferred_date=preferred_date,
            message=message
        )

        # TODO: Интеграция с AmoCRM
        # send_to_amocrm(visit_request)

        visit_date = visit_request.preferred_date
        if hasattr(visit_date, 'strftime'):
            visit_date_display = visit_date.strftime('%d.%m.%Y')
        else:
            visit_date_display = visit_date

        details = [
            (_('Имя'), visit_request.name),
            (_('Телефон'), visit_request.phone),
            (_('Желаемая дата'), visit_date_display),
        ]

        if visit_request.message:
            details.append((_('Дополнительная информация'), visit_request.message))

        details.append(
            (_('Создано'), timezone.localtime(visit_request.created_at).strftime('%d.%m.%Y %H:%M'))
        )

        notify_admins_about_submission(
            form_name=_('Запись на встречу в офисе'),
            subject_context=visit_request.name,
            details=details,
            admin_url=build_admin_change_url(visit_request),
            request=request,
        )

        return JsonResponse({
            'success': True,
            'message': _('Спасибо! Ваша запись принята. Мы перезвоним для подтверждения встречи.')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': _('Произошла ошибка. Пожалуйста, попробуйте позже.')
        }, status=500)


@require_http_methods(["POST"])
def faq_question_view(request):
    """Вопрос из секции FAQ"""
    try:
        recaptcha_error = _check_recaptcha(request)
        if recaptcha_error:
            return recaptcha_error

        security_error = validate_form_security(request)
        if security_error:
            return security_error

        phone = request.POST.get('phone', '').strip()
        question = request.POST.get('question', '').strip()

        # Валидация
        if not phone or not question:
            return JsonResponse({
                'success': False,
                'message': _('Пожалуйста, укажите телефон и вопрос')
            }, status=400)

        # Создаем запись
        faq = FAQQuestion.objects.create(
            phone=phone,
            question=question
        )

        # TODO: Интеграция с AmoCRM
        # send_to_amocrm(faq)

        details = [
            (_('Телефон'), faq.phone),
            (_('Вопрос'), faq.question),
            (
                _('Создано'),
                timezone.localtime(faq.created_at).strftime('%d.%m.%Y %H:%M'),
            ),
        ]

        notify_admins_about_submission(
            form_name=_('Вопрос из FAQ'),
            subject_context=faq.phone,
            details=details,
            admin_url=build_admin_change_url(faq),
            request=request,
        )

        return JsonResponse({
            'success': True,
            'message': _('Спасибо за вопрос! Наш эксперт свяжется с вами в ближайшее время.')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': _('Произошла ошибка. Пожалуйста, попробуйте позже.')
        }, status=500)


@require_http_methods(["POST"])
def newsletter_subscribe_view(request):
    """Подписка на новости"""
    try:
        recaptcha_error = _check_recaptcha(request)
        if recaptcha_error:
            return recaptcha_error

        security_error = validate_form_security(request)
        if security_error:
            return security_error

        email = request.POST.get('email', '').strip()

        # Валидация
        if not email:
            return JsonResponse({
                'success': False,
                'message': _('Пожалуйста, укажите email')
            }, status=400)

        # Проверяем существует ли подписка
        subscription, created = NewsletterSubscription.objects.get_or_create(
            email=email,
            defaults={
                'source_page': request.META.get('HTTP_REFERER', ''),
                'is_active': True
            }
        )

        if not created:
            # Подписка уже существует
            if subscription.is_active:
                return JsonResponse({
                    'success': False,
                    'message': _('Вы уже подписаны на нашу рассылку')
                }, status=400)
            else:
                # Активируем старую подписку
                subscription.is_active = True
                subscription.unsubscribed_at = None
                subscription.save()

                reactivate_details = [
                    (_('Email'), subscription.email),
                    (_('Статус'), _('Активна')),
                    (_('Дата первоначальной подписки'),
                     timezone.localtime(subscription.subscribed_at).strftime('%d.%m.%Y %H:%M')),
                ]

                reactivate_details.append(
                    (
                        _('Дата повторной активации'),
                        timezone.localtime(timezone.now()).strftime('%d.%m.%Y %H:%M'),
                    )
                )

                notify_admins_about_submission(
                    form_name=_('Подписка на новости'),
                    subject_context=_('реактивация'),
                    details=reactivate_details,
                    admin_url=build_admin_change_url(subscription),
                    request=request,
                    extra_lines=[
                        _('Источник запроса: %(url)s') % {
                            'url': request.META.get('HTTP_REFERER', ''),
                        }
                    ],
                )
        else:
            subscribe_details = [
                (_('Email'), subscription.email),
                (_('Статус'), _('Активна')),
            ]

            if subscription.source_page:
                subscribe_details.append(
                    (_('Страница подписки'), subscription.source_page)
                )

            subscribe_details.append(
                (
                    _('Создано'),
                    timezone.localtime(subscription.subscribed_at).strftime('%d.%m.%Y %H:%M'),
                )
            )

            notify_admins_about_submission(
                form_name=_('Подписка на новости'),
                subject_context=subscription.email,
                details=subscribe_details,
                admin_url=build_admin_change_url(subscription),
                request=request,
                extra_lines=[
                    _('Источник запроса: %(url)s') % {
                        'url': request.META.get('HTTP_REFERER', ''),
                    }
                ],
            )

        return JsonResponse({
            'success': True,
            'message': _('Спасибо за подписку! Теперь вы будете получать наши новости.')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': _('Произошла ошибка. Пожалуйста, попробуйте позже.')
        }, status=500)
