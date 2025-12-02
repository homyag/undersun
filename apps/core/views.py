from decimal import Decimal, InvalidOperation
import json
from urllib.parse import parse_qsl, urlencode

from django.views.generic import TemplateView, DetailView, View
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from django.utils.html import strip_tags
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils import translation
from django.urls import reverse
from django.utils.translation import gettext, ngettext, get_language, get_language_from_path
from django.conf import settings

from apps.currency.services import CurrencyService
from apps.core.utils import build_query_string
from apps.properties.models import Property, PropertyType
from apps.locations.models import District
from apps.blog.models import BlogPost
from .models import PromotionalBanner, Service, Team
import logging

logger = logging.getLogger(__name__)


def serialize_properties_for_js(properties):
    """Сериализация объектов недвижимости для JavaScript"""
    result = []
    for prop in properties:
        main_image_url = ''
        if prop.main_image:
            main_image_url = prop.main_image.medium_url
        
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
        ).select_related('district', 'property_type').prefetch_related('images').order_by('-featured_priority', '-updated_at')
        
        featured_villa = list(base_featured.filter(property_type__name='villa')[:9])
        featured_condo = list(base_featured.filter(property_type__name='condo')[:9])
        featured_townhouse = list(base_featured.filter(property_type__name='townhouse')[:9])

        structured_offers = []

        def choose_price(prop):
            candidates = [
                ('price_sale_thb', 'THB'),
                ('price_sale_usd', 'USD'),
                ('price_sale_rub', 'RUB'),
                ('price_rent_monthly_thb', 'THB'),
                ('price_rent_monthly', 'USD'),
                ('price_rent_monthly_rub', 'RUB'),
            ]
            for field, currency in candidates:
                value = getattr(prop, field, None)
                if value:
                    return float(value), currency
            return None, None

        def append_structured(items):
            for prop in items[:3]:
                price_value, price_currency = choose_price(prop)
                structured_offers.append({
                    'name': prop.title,
                    'url': self.request.build_absolute_uri(prop.get_absolute_url()),
                    'description': strip_tags(prop.short_description or prop.description or ''),
                    'image': prop.get_main_image_absolute_url(self.request),
                    'price': price_value,
                    'price_currency': price_currency,
                    'deal_type': prop.get_deal_type_display(),
                    'property_type': prop.property_type.name_display if prop.property_type else '',
                    'address': prop.address or (str(prop.district) if prop.district else ''),
                })

        append_structured(featured_villa)
        append_structured(featured_condo)
        append_structured(featured_townhouse)
        context['featured_properties_structured'] = structured_offers
        context['featured_properties_initial'] = {
            'villa': featured_villa[:4],
            'condo': featured_condo[:4],
            'townhouse': featured_townhouse[:4],
        }

        # Сериализация для JavaScript
        context['featured_properties_villa'] = mark_safe(serialize_properties_for_js(featured_villa))
        context['featured_properties_condo'] = mark_safe(serialize_properties_for_js(featured_condo))
        context['featured_properties_townhouse'] = mark_safe(serialize_properties_for_js(featured_townhouse))


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
        context['property_types'] = PropertyType.ordered_for_navigation()
        
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

        context['home_services_structured'] = [
            {
                'name': gettext("Покупка недвижимости онлайн и офлайн"),
                'description': gettext("Тщательный отбор объектов под ваши цели, полная проверка и сопровождение до получения ключей."),
                'url': self.request.build_absolute_uri(reverse('core:service_detail', kwargs={'slug': 'buying-property'}))
            },
            {
                'name': gettext("Продажа недвижимости"),
                'description': gettext("Используем эффективные каналы, чтобы найти покупателя и закрыть сделку на лучших условиях."),
                'url': self.request.build_absolute_uri(reverse('core:service_detail', kwargs={'slug': 'selling-property'}))
            },
            {
                'name': gettext("Консультации по покупке недвижимости"),
                'description': gettext("Разъясним ключевые юридические нюансы и организуем процесс оформления сделки в Таиланде."),
                'url': self.request.build_absolute_uri(reverse('core:service_detail', kwargs={'slug': 'legal-services'}))
            },
            {
                'name': gettext("Продажа земли"),
                'description': gettext("В нашем портфеле — земля в перспективных районах Пхукета."),
                'url': self.request.build_absolute_uri(reverse('core:service_detail', kwargs={'slug': 'land-sale'}))
            }
        ]

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

        sort_param = self.request.GET.get('sort')
        sort_by = sort_param or '-created_at'
        allowed_sorts = [
            'price_sale_usd', '-price_sale_usd',
            'price_sale_thb', '-price_sale_thb',
            'price_rent_monthly', '-price_rent_monthly',
            'area_total', '-area_total',
            'created_at', '-created_at'
        ]

        ordering = []
        if not sort_param:
            ordering.append('-is_featured')

        if sort_by in allowed_sorts:
            ordering.append(sort_by)
        else:
            ordering.append('-created_at')

        properties = properties.order_by(*ordering)

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
        context['property_types'] = PropertyType.ordered_for_navigation()
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
            'sort': sort_param or '-created_at',
        }

        allowed_keys = ['q', 'type', 'district', 'location', 'deal_type', 'min_price', 'max_price', 'bedrooms', 'sort']
        context['pagination_query_string'] = build_query_string(self.request.GET, allowed_keys)

        context['results_count_i18n'] = {
            'zero': gettext('Объекты не найдены'),
            'one': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 1),
            'few': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 2),
            'many': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 5),
        }

        if 'q' in self.request.GET:
            context['meta_robots'] = 'noindex, follow'

        return context


class MapView(TemplateView):
    template_name = 'core/map.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        properties_qs = Property.objects.filter(
            is_active=True,
            status='available',
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('district', 'property_type', 'agent', 'contact_person').prefetch_related('images')

        properties = list(properties_qs)
        language_code = (translation.get_language() or 'ru')[:2]
        supported_languages = {'ru', 'en', 'th'}
        if language_code not in supported_languages:
            language_code = 'ru'

        for prop in properties:
            prop.localized_title = self._get_localized_value(prop, 'title', language_code)
            if prop.property_type:
                prop.localized_property_type = self._get_localized_value(
                    prop.property_type,
                    'name_display',
                    language_code
                ) or prop.property_type.name_display
            if prop.district:
                prop.district.localized_name = self._get_localized_value(prop.district, 'name', language_code)
            if prop.location:
                prop.localized_location_name = self._get_localized_value(prop.location, 'name', language_code)

        context['properties'] = properties
        context['property_types'] = PropertyType.ordered_for_navigation()
        context['districts'] = District.objects.prefetch_related('locations')

        context['total_properties'] = len(properties)
        context['sale_properties'] = sum(1 for prop in properties if prop.deal_type in ['sale', 'both'])
        context['rent_properties'] = sum(1 for prop in properties if prop.deal_type in ['rent', 'both'])
        context['districts_count'] = District.objects.filter(
            property__is_active=True,
            property__status='available'
        ).distinct().count()

        # Featured properties data reused on map page
        featured_base = Property.objects.filter(
            is_featured=True,
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')

        context['featured_properties_villa'] = mark_safe(serialize_properties_for_js(
            featured_base.filter(property_type__name='villa')[:9]
        ))
        context['featured_properties_condo'] = mark_safe(serialize_properties_for_js(
            featured_base.filter(property_type__name='condo')[:9]
        ))
        context['featured_properties_townhouse'] = mark_safe(serialize_properties_for_js(
            featured_base.filter(property_type__name='townhouse')[:9]
        ))

        district_coords = {}
        for prop in properties:
            if not prop.latitude or not prop.longitude:
                continue
            if prop.district_id and prop.district_id not in district_coords:
                district_coords[prop.district_id] = (prop.latitude, prop.longitude)

        focus_districts = []
        for district in context['districts']:
            lat, lng = district_coords.get(district.id, (None, None))
            if lat is None or lng is None:
                continue
            focus_districts.append({
                'name': district.name,
                'lat': lat,
                'lng': lng,
            })
            if len(focus_districts) >= 6:
                break

        context['district_focus_list'] = focus_districts

        selected_currency_code = CurrencyService.get_selected_currency_code(self.request)
        selected_currency = CurrencyService.get_currency_by_code(selected_currency_code)
        active_currencies = CurrencyService.get_active_currencies()

        context['selected_currency_code'] = selected_currency_code
        context['selected_currency'] = selected_currency
        context['map_currency_settings'] = [
            {
                'code': currency.code,
                'symbol': currency.symbol,
                'decimal_places': currency.decimal_places,
            }
            for currency in active_currencies
        ]

        return context

    @staticmethod
    def _get_localized_value(obj, field_name, language_code):
        if not obj:
            return ''
        localized_field = f"{field_name}_{language_code}"
        value = getattr(obj, localized_field, None)
        if value:
            return value
        return getattr(obj, field_name, '')


class PrivacyView(TemplateView):
    template_name = 'core/privacy.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate = get_language_from_path(self.request.path)
        default_lang = getattr(self.request, 'LANGUAGE_CODE', None) or get_language() or settings.LANGUAGE_CODE
        lang = (candidate or default_lang)[:2]
        self.request.LANGUAGE_CODE = lang
        context['privacy_language'] = lang
        return context


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


def legacy_real_estate_redirect(request, *args, **kwargs):
    """Постоянный редирект со старых URL /real-estate/... на новый каталог /property/."""
    target_url = reverse('properties:property_list')

    raw_query = request.META.get('QUERY_STRING', '').strip()
    allowed_params = {}

    if raw_query:
        # Сохраняем только безопасные параметры, чтобы не протягивать legacy-хвосты в индекс
        for key, value in parse_qsl(raw_query, keep_blank_values=True):
            if key == 'page' and value:
                allowed_params[key] = value

    if allowed_params:
        target_url = f"{target_url}?{urlencode(allowed_params)}"

    return HttpResponsePermanentRedirect(target_url)


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
        ).select_related('district', 'property_type').prefetch_related('images').order_by('-featured_priority', '-updated_at')
        
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
