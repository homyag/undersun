from django.views.generic import TemplateView, DetailView
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
import json
from apps.properties.models import Property, PropertyType
from apps.locations.models import District
from apps.blog.models import BlogPost
from .models import PromotionalBanner, Service


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
        context['promotional_banner'] = PromotionalBanner.get_active_banner()
        
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