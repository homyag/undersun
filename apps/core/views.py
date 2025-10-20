from decimal import Decimal, InvalidOperation
import json

from django.views.generic import TemplateView, DetailView, View
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils import translation

from apps.currency.services import CurrencyService
from apps.properties.models import Property, PropertyType
from apps.locations.models import District
from apps.blog.models import BlogPost
from .models import PromotionalBanner, Service, Team


def serialize_properties_for_js(properties):
    """Сериализация объектов недвижимости для JavaScript"""
    result = []
    for prop in properties:
        main_image_url = ''
        if prop.main_image:
            main_image_url = prop.main_image.medium.url if hasattr(prop.main_image, 'medium') else prop.main_image.url
        
        # Форматирование цены с правильным преобразованием Decimal
        price_formatted = 'Цена по запросу'
        if prop.deal_type == 'rent' and prop.price_rent_monthly:
            price_formatted = f'${float(prop.price_rent_monthly):,.0f}/мес'
        elif prop.deal_type == 'both':
            # Для объектов "продажа/аренда" показываем цену продажи
            if prop.price_sale_usd:
                price_formatted = f'${float(prop.price_sale_usd):,.0f}'
        elif prop.price_sale_usd:
            price_formatted = f'${float(prop.price_sale_usd):,.0f}'
        
        result.append({
            'id': prop.id,
            'title': prop.title,
            'url': prop.get_absolute_url(),
            'main_image_url': main_image_url,
            'price_formatted': price_formatted,
            'district_name': prop.district.name if prop.district else 'Пхукет',
            'location_name': prop.location.name if prop.location else '',
            'property_type': prop.property_type.name_display if prop.property_type else '',
            'property_type_name': prop.property_type.name_display if prop.property_type else '',
            'deal_type': prop.deal_type,
            'bedrooms': prop.bedrooms or 0,
            'bathrooms': prop.bathrooms or 0,
            'area': float(prop.area_total) if prop.area_total else 0,
            # Цены в разных валютах для переключения
            'price_sale_usd': float(prop.price_sale_usd) if prop.price_sale_usd else 0,
            'price_sale_thb': float(prop.price_sale_thb) if prop.price_sale_thb else 0,
            'price_sale_rub': float(prop.price_sale_rub) if prop.price_sale_rub else 0,
            'price_rent_usd': float(prop.price_rent_monthly) if prop.price_rent_monthly else 0,
            'price_rent_thb': float(prop.price_rent_monthly_thb) if prop.price_rent_monthly_thb else 0,
            'price_rent_rub': float(prop.price_rent_monthly_rub) if prop.price_rent_monthly_rub else 0,
            # Цены за квадратный метр
            'price_per_sqm_thb': prop.get_formatted_price_per_sqm('THB', prop.deal_type),
            'price_per_sqm_usd': prop.get_formatted_price_per_sqm('USD', prop.deal_type), 
            'price_per_sqm_rub': prop.get_formatted_price_per_sqm('RUB', prop.deal_type),
            # Специальное предложение
            'special_offer': prop.special_offer or '',
        })
    return json.dumps(result)


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Рекомендуемая недвижимость по типам недвижимости
        base_featured = Property.objects.filter(
            is_featured=True,
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')
        
        context['featured_properties_villa'] = base_featured.filter(
            property_type__name='villa'
        )[:9]  # 9 объектов для размещения 2 форм консультации
        
        context['featured_properties_condo'] = base_featured.filter(
            property_type__name='condo'
        )[:9]
        
        context['featured_properties_townhouse'] = base_featured.filter(
            property_type__name='townhouse'
        )[:9]
        
        # Сериализация для JavaScript
        context['featured_properties_villa'] = mark_safe(serialize_properties_for_js(context['featured_properties_villa']))
        context['featured_properties_condo'] = mark_safe(serialize_properties_for_js(context['featured_properties_condo']))
        context['featured_properties_townhouse'] = mark_safe(serialize_properties_for_js(context['featured_properties_townhouse']))


        # Статистика по типам
        context['property_stats'] = PropertyType.objects.annotate(
            count=Count('property', filter=Q(property__is_active=True, property__status='available'))
        ).filter(count__gt=0)

        # Районы с количеством объектов
        context['districts'] = District.objects.annotate(
            properties_count=Count('property', filter=Q(property__is_active=True, property__status='available'))
        ).filter(properties_count__gt=0)

        # Активный рекламный баннер
        current_language = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2] if hasattr(self.request, 'LANGUAGE_CODE') else 'ru'
        context['promotional_banner'] = PromotionalBanner.get_active_banner(current_language)
        
        # Типы недвижимости для поиска
        context['property_types'] = PropertyType.objects.all()
        
        # Общее количество активных объектов
        context['total_properties_count'] = Property.objects.filter(
            is_active=True,
            status='available'
        ).count()
        
        # Новые поступления (до 4 объектов)
        context['recent_properties'] = Property.objects.filter(
            is_active=True,
            status='available'
        ).select_related('district', 'location', 'property_type').prefetch_related('images').order_by('-created_at')[:4]
        
        # Последние новости (3 новости для главной страницы)
        context['latest_news'] = BlogPost.get_published().select_related('category', 'author').order_by('-published_at')[:3]
        
        # Команда для главной страницы
        context['homepage_team'] = Team.get_homepage_team()
        context['all_team'] = Team.get_all_active()
        context['hidden_team'] = Team.objects.filter(is_active=True, show_on_homepage=False).order_by('display_order', 'last_name')

        return context


class AboutView(TemplateView):
    template_name = 'core/about.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Добавляем услуги для меню
        context['menu_services'] = Service.get_menu_services()
        
        return context


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
        location = self.request.GET.get('location', '')
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
        
        if location:
            properties = properties.filter(location__id=location)

        if deal_type:
            properties = properties.filter(deal_type=deal_type)

        # Получаем текущую валюту (аналогично context_processor)
        selected_currency_code = CurrencyService.get_selected_currency_code(self.request)
        current_currency = CurrencyService.get_currency_by_code(selected_currency_code)
        sale_field, rent_field = CurrencyService.get_price_field_names(selected_currency_code)

        if min_price:
            try:
                min_val = Decimal(min_price)
                price_filter = Q(**{f"{sale_field}__gte": min_val})
                if rent_field:
                    price_filter |= Q(**{f"{rent_field}__gte": min_val})
                properties = properties.filter(price_filter)
            except (InvalidOperation, ValueError):
                pass

        if max_price:
            try:
                max_val = Decimal(max_price)
                price_filter = Q(**{f"{sale_field}__lte": max_val})
                if rent_field:
                    price_filter |= Q(**{f"{rent_field}__lte": max_val})
                properties = properties.filter(price_filter)
            except (InvalidOperation, ValueError):
                pass

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
        context['selected_currency'] = current_currency
        context['selected_currency_code'] = selected_currency_code
        context['search_params'] = {
            'q': query,
            'type': property_type,
            'district': district,
            'location': location,
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

        properties = Property.objects.filter(
            is_active=True,
            status='available',
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('district', 'property_type', 'agent', 'contact_person').prefetch_related('images')

        context['properties'] = properties
        context['property_types'] = PropertyType.objects.all()
        context['districts'] = District.objects.prefetch_related('locations')

        context['total_properties'] = properties.count()
        context['sale_properties'] = properties.filter(deal_type__in=['sale', 'both']).count()
        context['rent_properties'] = properties.filter(deal_type__in=['rent', 'both']).count()
        context['districts_count'] = District.objects.filter(
            property__is_active=True,
            property__status='available'
        ).distinct().count()

        return context


class PrivacyView(TemplateView):
    template_name = 'core/privacy.html'


class TermsView(TemplateView):
    template_name = 'core/terms.html'


class SitemapView(View):
    languages = ['ru', 'en', 'th']
    static_names = ['core:home', 'core:about', 'core:contact', 'core:map', 'core:privacy', 'core:terms']

    def get(self, request, *args, **kwargs):
        from django.urls import reverse

        base_url = request.build_absolute_uri('/')[:-1]
        entries = []

        def build_alternates(resolve_func):
            alternates = []
            for lang in self.languages:
                with translation.override(lang):
                    path = resolve_func()
                    alternates.append({
                        'lang': lang,
                        'url': f'{base_url}{path}'
                    })
            return alternates

        # Static pages
        for name in self.static_names:
            alternates = build_alternates(lambda n=name: reverse(n))
            entries.extend(self._expand_entries(alternates, None))

        # Services
        for service in Service.objects.filter(is_active=True):
            alternates = build_alternates(service.get_absolute_url)
            lastmod = service.updated_at.isoformat() if service.updated_at else None
            entries.extend(self._expand_entries(alternates, lastmod))

        # Properties
        for prop in Property.objects.filter(is_active=True, status='available'):
            alternates = build_alternates(prop.get_absolute_url)
            lastmod = prop.updated_at.isoformat() if prop.updated_at else None
            entries.extend(self._expand_entries(alternates, lastmod))

        # Blog
        for post in BlogPost.get_published():
            alternates = build_alternates(post.get_absolute_url)
            lastmod = post.updated_at.isoformat() if post.updated_at else None
            entries.extend(self._expand_entries(alternates, lastmod))

        xml_content = render_to_string('core/sitemaps/sitemap.xml', {'entries': entries})
        return HttpResponse(xml_content, content_type='application/xml')

    @staticmethod
    def _expand_entries(alternates, lastmod):
        expanded = []
        for alt in alternates:
            expanded.append({
                'loc': alt['url'],
                'lastmod': lastmod,
                'alternates': [a for a in alternates if a['url'] != alt['url']]
            })
        return expanded


def custom_404(request, exception):
    response = TemplateResponse(request, 'core/404.html', status=404)
    response.render()
    return response


class ServiceDetailView(DetailView):
    """Детальная страница услуги"""
    model = Service
    template_name = 'core/service_detail.html'
    context_object_name = 'service'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        """Получить только активные услуги"""
        return Service.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Добавляем все услуги для меню
        context['all_services'] = Service.get_menu_services()
        
        # SEO данные
        service = self.get_object()
        context['page_title'] = service.get_meta_title()
        context['page_description'] = service.get_meta_description()
        context['page_keywords'] = service.meta_keywords
        
        # Добавляем рекомендуемые объекты в зависимости от типа услуги
        context['featured_properties'] = self._get_featured_properties_for_service(service)
        
        return context
    
    def _get_featured_properties_for_service(self, service):
        """Получить рекомендуемые объекты для конкретного типа услуги"""
        from apps.properties.models import Property, PropertyType
        
        # Базовый queryset для рекомендуемых объектов
        base_queryset = Property.objects.filter(
            is_featured=True,
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')
        
        # Фильтруем по типу услуги
        if service.slug == 'buying-property':
            # Покупка недвижимости: объекты для покупки
            return base_queryset.filter(deal_type__in=['sale', 'both'])
        elif service.slug == 'selling-property':
            # Продажа недвижимости: не показывать блок
            return Property.objects.none()
        elif service.slug == 'renting-property':
            # Аренда недвижимости: объекты для аренды
            return base_queryset.filter(deal_type__in=['rent', 'both'])
        elif service.slug == 'commercial-real-estate':
            # Коммерческая недвижимость: готовый бизнес
            return base_queryset.filter(property_type__name='business')
        elif service.slug == 'legal-services':
            # Юридические услуги: не показывать блок
            return Property.objects.none()
        elif service.slug == 'land-sale':
            # Продажа земли: земельные участки
            return base_queryset.filter(property_type__name='land')
        else:
            # Для остальных услуг показываем все рекомендуемые объекты
            return base_queryset
