from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Формы обратной связи
    path('quick-consultation/', views.quick_consultation_view, name='quick_consultation'),
    path('contact/', views.contact_form_view, name='contact_form'),
    path('office-visit/', views.office_visit_request_view, name='office_visit'),
    path('faq-question/', views.faq_question_view, name='faq_question'),
    path('newsletter/subscribe/', views.newsletter_subscribe_view, name='newsletter_subscribe'),

    # Запросы по объектам недвижимости
    path('property/<int:property_id>/inquiry/', views.property_inquiry_view, name='property_inquiry'),
]