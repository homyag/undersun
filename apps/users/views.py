from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext as _
from django.utils import timezone
from django.shortcuts import get_object_or_404

from apps.properties.models import Property
from .models import (
    PropertyInquiry,
    QuickConsultationRequest,
    ContactFormSubmission,
    OfficeVisitRequest,
    FAQQuestion,
    NewsletterSubscription
)


def get_client_ip(request):
    """Получение IP адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_http_methods(["POST"])
def property_inquiry_view(request, property_id):
    """Обработка запросов по конкретному объекту (просмотр/консультация)"""
    try:
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

        return JsonResponse({
            'success': True,
            'message': _('Спасибо за подписку! Теперь вы будете получать наши новости.')
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': _('Произошла ошибка. Пожалуйста, попробуйте позже.')
        }, status=500)