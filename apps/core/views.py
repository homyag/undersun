from django.views.generic import TemplateView
from django.db.models import Q, Count
from apps.properties.models import Property, PropertyType
from apps.locations.models import District
from .models import PromotionalBanner


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Рекомендуемая недвижимость
        context['featured_properties'] = Property.objects.filter(
            is_featured=True,
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')[:6]

        # Новая недвижимость
        context['latest_properties'] = Property.objects.filter(
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')[:8]

        # Статистика по типам
        context['property_stats'] = PropertyType.objects.annotate(
            count=Count('property', filter=Q(property__is_active=True, property__status='available'))
        ).filter(count__gt=0)

        # Районы с количеством объектов
        context['districts'] = District.objects.annotate(
            properties_count=Count('property', filter=Q(property__is_active=True, property__status='available'))
        ).filter(properties_count__gt=0)

        # Активный рекламный баннер
        context['promotional_banner'] = PromotionalBanner.get_active_banner()
        
        # Типы недвижимости для поиска
        context['property_types'] = PropertyType.objects.all()

        return context


class AboutView(TemplateView):
    template_name = 'core/about.html'


class ContactView(TemplateView):
    template_name = 'core/contact.html'


class SearchView(TemplateView):
    template_name = 'core/search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Параметры поиска
        query = self.request.GET.get('q', '')
        property_type = self.request.GET.get('type', '')
        district = self.request.GET.get('district', '')
        deal_type = self.request.GET.get('deal_type', '')
        min_price = self.request.GET.get('min_price', '')
        max_price = self.request.GET.get('max_price', '')
        bedrooms = self.request.GET.get('bedrooms', '')

        # Базовый запрос
        properties = Property.objects.filter(
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')

        # Фильтрация
        if query:
            properties = properties.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(address__icontains=query)
            )

        if property_type:
            properties = properties.filter(property_type__name=property_type)

        if district:
            properties = properties.filter(district__slug=district)

        if deal_type:
            properties = properties.filter(deal_type=deal_type)

        # Получаем текущую валюту (аналогично context_processor)
        from apps.currency.services import CurrencyService
        selected_currency_code = self.request.session.get('currency')
        if not selected_currency_code:
            language = getattr(self.request, 'LANGUAGE_CODE', 'en')
            default_currency = CurrencyService.get_currency_for_language(language)
            selected_currency_code = default_currency.code if default_currency else 'USD'
        current_currency = CurrencyService.get_currency_by_code(selected_currency_code)
        
        if min_price:
            if current_currency and current_currency.code == 'RUB':
                properties = properties.filter(price_sale_rub__gte=min_price)
            elif current_currency and current_currency.code == 'THB':
                properties = properties.filter(price_sale_thb__gte=min_price)
            else:
                properties = properties.filter(price_sale_usd__gte=min_price)

        if max_price:
            if current_currency and current_currency.code == 'RUB':
                properties = properties.filter(price_sale_rub__lte=max_price)
            elif current_currency and current_currency.code == 'THB':
                properties = properties.filter(price_sale_thb__lte=max_price)
            else:
                properties = properties.filter(price_sale_usd__lte=max_price)

        if bedrooms:
            properties = properties.filter(bedrooms=bedrooms)

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(properties, 12)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['properties'] = page_obj
        context['results'] = page_obj  # Добавляем для совместимости с шаблоном
        context['page_obj'] = page_obj
        context['is_paginated'] = page_obj.has_other_pages()
        context['property_types'] = PropertyType.objects.all()
        context['districts'] = District.objects.all()
        context['query'] = query
        context['search_params'] = {
            'q': query,
            'type': property_type,
            'district': district,
            'deal_type': deal_type,
            'min_price': min_price,
            'max_price': max_price,
            'bedrooms': bedrooms,
        }

        return context


class MapView(TemplateView):
    template_name = 'core/map.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Недвижимость с координатами для карты
        properties = Property.objects.filter(
            is_active=True,
            status='available',
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('district', 'property_type').prefetch_related('images')

        context['properties'] = properties
        
        # Статистика для карты
        context['total_properties'] = properties.count()
        context['sale_properties'] = properties.filter(deal_type__in=['sale', 'both']).count()
        context['rent_properties'] = properties.filter(deal_type__in=['rent', 'both']).count()
        context['districts_count'] = District.objects.annotate(
            properties_count=Count('property', filter=Q(
                property__is_active=True, 
                property__status='available',
                property__latitude__isnull=False,
                property__longitude__isnull=False
            ))
        ).filter(properties_count__gt=0).count()

        return context