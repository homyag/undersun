from decimal import Decimal, InvalidOperation
import json

from django.views.generic import TemplateView, DetailView, View
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from django.utils.html import strip_tags
from django.http import HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils import translation
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext, ngettext, get_language, get_language_from_path
from django.conf import settings
from django.contrib.staticfiles import finders

from apps.currency.services import CurrencyService
from apps.core.legacy_redirects import (
    append_legacy_real_estate_query,
    build_legacy_real_estate_target,
)
from apps.core.utils import build_query_string, truncate_meta
from apps.properties.models import Property, PropertyType, PROPERTY_FALLBACK_LABELS
from apps.properties.views import PropertyListView
from apps.locations.models import District, Location
from apps.blog.models import BlogPost
from .models import PromotionalBanner, Service, Team
from .service_landing_content import build_service_landing_content, get_service_page_copy
from .google_reviews import get_homepage_google_reviews
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def metrika_loaded_ping(request):
    """Простой endpoint для фиксации факта загрузки Метрики (используется sendBeacon)."""
    return JsonResponse({'status': 'ok'})


def llms_txt(request):
    """Serve the AI-agent source map without DB-backed context processors."""
    content = render_to_string('llms.txt')
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


def serialize_properties_for_js(properties):
    """Сериализация объектов недвижимости для JavaScript"""
    result = []
    language_code = (get_language() or 'ru')[:2]

    def get_price_deal_type(prop):
        if prop.deal_type == 'rent':
            return 'rent'
        if prop.deal_type == 'both' and not prop.price_sale_thb and prop.price_rent_monthly_thb:
            return 'rent'
        return 'sale'

    def format_home_price(prop, currency_code, deal_type):
        labels = PROPERTY_FALLBACK_LABELS.get(language_code, PROPERTY_FALLBACK_LABELS['ru'])
        price = prop.get_price_in_currency(currency_code, deal_type)
        if not price:
            return labels['price_on_request']

        symbols = {'USD': '$', 'THB': '฿', 'RUB': '₽'}
        price_display = f"{symbols.get(currency_code, currency_code)}{float(price):,.0f}"
        if deal_type == 'rent':
            price_display += labels['per_month']
        return price_display

    def get_price_amount(prop, currency_code, deal_type):
        price = prop.get_price_in_currency(currency_code, deal_type)
        return float(price) if price else 0

    for prop in properties:
        main_image_url = ''
        main_image_thumbnail_url = ''
        if prop.main_image:
            main_image_url = prop.main_image.medium_url
            main_image_thumbnail_url = prop.main_image.thumbnail_url

        price_deal_type = get_price_deal_type(prop)
        price_formatted = format_home_price(prop, 'USD', price_deal_type)
        
        result.append({
            'id': prop.id,
            'slug': prop.slug,
            'title': prop._get_translated_property_field('title', language_code, fallback=prop.title),
            'url': prop.get_absolute_url(),
            'main_image_url': main_image_url,
            'main_image_thumbnail_url': main_image_thumbnail_url,
            'price_formatted': price_formatted,
            'district_name': prop._get_translated_district_name(language_code),
            'location_name': prop._get_translated_location_name(language_code),
            'property_type': prop._get_translated_type_name(language_code),
            'property_type_name': prop._get_translated_type_name(language_code),
            'property_type_key': prop.property_type.name if prop.property_type else '',
            'deal_type': prop.deal_type,
            'bedrooms': prop.bedrooms or 0,
            'bathrooms': prop.bathrooms or 0,
            'area': float(prop.area_total) if prop.area_total else 0,
            # Цены в разных валютах для переключения
            'price_sale_usd': get_price_amount(prop, 'USD', 'sale'),
            'price_sale_thb': get_price_amount(prop, 'THB', 'sale'),
            'price_sale_rub': get_price_amount(prop, 'RUB', 'sale'),
            'price_rent_usd': get_price_amount(prop, 'USD', 'rent'),
            'price_rent_thb': get_price_amount(prop, 'THB', 'rent'),
            'price_rent_rub': get_price_amount(prop, 'RUB', 'rent'),
            # Цены за квадратный метр
            'price_per_sqm_thb': prop.get_formatted_price_per_sqm('THB', prop.deal_type),
            'price_per_sqm_usd': prop.get_formatted_price_per_sqm('USD', prop.deal_type), 
            'price_per_sqm_rub': prop.get_formatted_price_per_sqm('RUB', prop.deal_type),
            # Специальное предложение
            'special_offer': prop._get_translated_property_field('special_offer', language_code),
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
                if price_value is None or not price_currency:
                    continue
                structured_offers.append({
                    'name': prop.title,
                    'url': self.request.build_absolute_uri(prop.get_absolute_url()),
                    'description': strip_tags(prop.short_description or prop.description or ''),
                    'image': prop.get_main_image_absolute_url(self.request),
                    'price': price_value,
                    'price_currency': price_currency,
                    'deal_type': prop.get_deal_type_display(),
                    'property_type': prop.property_type.name_display if prop.property_type else '',
                    'property_type_slug': prop.property_type.name if prop.property_type else '',
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
        context['google_reviews'] = get_homepage_google_reviews(current_language)

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

        property_list_view = PropertyListView()
        property_list_view.request = self.request
        filtered_qs = property_list_view.apply_filters(properties_qs)

        properties = list(filtered_qs)
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

        filter_context = property_list_view.build_filter_context()
        context.update(filter_context)
        context['show_build_status_filter'] = property_list_view.should_show_build_status_filter(context)

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
        lang = (getattr(self.request, 'LANGUAGE_CODE', None) or get_language() or settings.LANGUAGE_CODE)[:2]
        self.request.LANGUAGE_CODE = lang
        context['privacy_language'] = lang
        return context


class TermsView(TemplateView):
    template_name = 'core/terms.html'


class SitemapBaseView(View):
    languages = ['ru', 'en', 'th']
    max_property_images = 3

    @staticmethod
    def _get_base_url(request):
        return request.build_absolute_uri('/')[:-1]

    @staticmethod
    def _to_absolute_url(base_url, url):
        if not url:
            return ''
        if url.startswith(('http://', 'https://')):
            return url
        if url.startswith('//'):
            return f'https:{url}'
        if url.startswith('/'):
            return f'{base_url}{url}'
        return f'{base_url}/{url.lstrip("/")}'

    def _build_alternates(self, base_url, resolve_func):
        alternates = []
        for lang in self.languages:
            with translation.override(lang):
                path = resolve_func()
                alternates.append({
                    'lang': lang,
                    'url': f'{base_url}{path}'
                })
        return alternates

    @staticmethod
    def _expand_entries(alternates, lastmod):
        expanded = []
        x_default = next((alt['url'] for alt in alternates if alt['lang'] == 'en'), alternates[0]['url'])
        for alt in alternates:
            expanded.append({
                'loc': alt['url'],
                'lastmod': lastmod,
                'alternates': alternates + [{'lang': 'x-default', 'url': x_default}],
            })
        return expanded

    @staticmethod
    def _render_urlset(entries):
        xml_content = render_to_string('core/sitemaps/sitemap.xml', {'entries': entries})
        return HttpResponse(xml_content, content_type='application/xml')

    def _build_property_images(self, base_url, property_obj):
        images = sorted(
            property_obj.images.all(),
            key=lambda image: (not image.is_main, image.order, image.id)
        )
        image_entries = []
        seen = set()

        for image in images:
            if image.image_type == 'floorplan':
                continue

            image_url = self._to_absolute_url(base_url, image.original_url)
            if not image_url or image_url in seen:
                continue

            image_entries.append({'loc': image_url})
            seen.add(image_url)

            if len(image_entries) >= self.max_property_images:
                break

        return image_entries


class SitemapView(SitemapBaseView):
    """Sitemap index entry point submitted in robots.txt and Search Console."""

    sitemap_paths = [
        'sitemap-static.xml',
        'sitemap-properties.xml',
        'sitemap-images.xml',
    ]

    def get(self, request, *args, **kwargs):
        base_url = self._get_base_url(request)
        sitemaps = [{'loc': f'{base_url}/{path}'} for path in self.sitemap_paths]
        xml_content = render_to_string('core/sitemaps/sitemap_index.xml', {'sitemaps': sitemaps})
        return HttpResponse(xml_content, content_type='application/xml')


class StaticSitemapView(SitemapBaseView):
    """Static, service, blog, catalog hub, district and location URLs."""

    static_names = ['core:home', 'core:about', 'core:contact', 'core:map', 'core:privacy', 'core:terms']
    section_routes = [
        ('blog:list', None),
        ('properties:property_list', None),
        ('properties:property_sale', None),
        ('properties:property_rent', None),
        ('location_list', None),
    ]
    property_type_slugs = ['condo', 'villa', 'townhouse', 'land']

    def get(self, request, *args, **kwargs):
        base_url = self._get_base_url(request)
        entries = []

        # Static pages
        for name in self.static_names:
            alternates = self._build_alternates(base_url, lambda n=name: reverse(n))
            entries.extend(self._expand_entries(alternates, None))

        # Section landing pages without пагинации/фильтров
        for route_name, route_kwargs in self.section_routes:
            alternates = self._build_alternates(
                base_url,
                lambda n=route_name, kw=route_kwargs: reverse(n, kwargs=kw) if kw else reverse(n)
            )
            entries.extend(self._expand_entries(alternates, None))

        for slug in self.property_type_slugs:
            alternates = self._build_alternates(
                base_url,
                lambda type_slug=slug: reverse('properties:property_by_type', kwargs={'type_name': type_slug})
            )
            entries.extend(self._expand_entries(alternates, None))

        # District and location detail pages
        for district in District.objects.order_by('slug'):
            alternates = self._build_alternates(base_url, district.get_absolute_url)
            entries.extend(self._expand_entries(alternates, None))

        for location in Location.objects.select_related('district').order_by('district__slug', 'slug'):
            alternates = self._build_alternates(base_url, location.get_absolute_url)
            entries.extend(self._expand_entries(alternates, None))

        # Services
        for service in Service.objects.filter(is_active=True):
            alternates = self._build_alternates(base_url, service.get_absolute_url)
            lastmod = service.updated_at.isoformat() if service.updated_at else None
            entries.extend(self._expand_entries(alternates, lastmod))

        # Blog
        for post in BlogPost.get_published():
            alternates = self._build_alternates(base_url, post.get_absolute_url)
            lastmod = post.updated_at.isoformat() if post.updated_at else None
            entries.extend(self._expand_entries(alternates, lastmod))

        return self._render_urlset(entries)


class PropertySitemapView(SitemapBaseView):
    """Canonical active property detail URLs in every supported language."""

    def get(self, request, *args, **kwargs):
        base_url = self._get_base_url(request)
        entries = []

        for prop in Property.objects.filter(is_active=True, status='available').order_by('id'):
            alternates = self._build_alternates(base_url, prop.get_absolute_url)
            lastmod = prop.updated_at.isoformat() if prop.updated_at else None
            entries.extend(self._expand_entries(alternates, lastmod))

        return self._render_urlset(entries)


class ImageSitemapView(SitemapBaseView):
    """Property image sitemap with up to three crawlable images per localized property URL."""

    def get(self, request, *args, **kwargs):
        base_url = self._get_base_url(request)
        entries = []

        properties = (
            Property.objects
            .filter(is_active=True, status='available')
            .select_related('district', 'location', 'property_type')
            .prefetch_related('images')
            .order_by('id')
        )

        for prop in properties:
            images = self._build_property_images(base_url, prop)
            if not images:
                continue

            alternates = self._build_alternates(base_url, prop.get_absolute_url)
            x_default = next((alt['url'] for alt in alternates if alt['lang'] == 'en'), alternates[0]['url'])
            lastmod = prop.updated_at.isoformat() if prop.updated_at else None
            alternates_with_default = alternates + [{'lang': 'x-default', 'url': x_default}]

            for alt in alternates:
                entries.append({
                    'loc': alt['url'],
                    'lastmod': lastmod,
                    'alternates': alternates_with_default,
                    'images': images,
                })

        return self._render_urlset(entries)


def custom_404(request, exception):
    response = TemplateResponse(request, 'core/404.html', status=404)
    response.render()
    return response


def legacy_real_estate_redirect(request, *args, **kwargs):
    """Постоянный редирект со старых URL /real-estate/... на актуальные страницы каталога."""
    default_language = (
        get_language_from_path(request.path)
        or get_language()
        or settings.LANGUAGE_CODE
    )
    target_url = (
        build_legacy_real_estate_target(request.path, default_language=default_language)
        or reverse('properties:property_list')
    )
    target_url = append_legacy_real_estate_query(
        target_url,
        request.META.get('QUERY_STRING'),
    )

    return HttpResponsePermanentRedirect(target_url)


def legacy_team_member_redirect(request, *args, **kwargs):
    """Командные страницы из старого сайта перенаправляем на текущий раздел «О компании»"""
    target_url = reverse('core:about')
    return HttpResponsePermanentRedirect(target_url)


def legacy_privacy_policy_redirect(request, *args, **kwargs):
    """Все варианты /privacy-policy/ ведем на актуальную страницу /privacy/."""
    target_url = reverse('core:privacy')
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
        service = self.get_object()
        language_code = (getattr(self.request, 'LANGUAGE_CODE', translation.get_language() or 'ru') or 'ru')[:2]
        service_landing = build_service_landing_content(service.slug, language_code)
        page_copy = get_service_page_copy(service.slug, language_code)
        localized_meta_title = getattr(service, f'meta_title_{language_code}', '') if language_code != 'ru' else service.meta_title
        localized_meta_description = getattr(service, f'meta_description_{language_code}', '') if language_code != 'ru' else service.meta_description

        # Добавляем все услуги для меню
        context['all_services'] = Service.get_menu_services()
        context['localized_menu_services'] = [
            {
                'slug': menu_service.slug,
                'url': menu_service.get_absolute_url(),
                'icon_class': menu_service.icon_class,
                'title': get_service_page_copy(menu_service.slug, language_code).get('title') or menu_service.title,
            }
            for menu_service in context['all_services']
        ]
        
        # SEO данные
        context['page_title'] = self._build_service_page_title(
            service=service,
            page_copy=page_copy,
            language_code=language_code,
            localized_meta_title=localized_meta_title,
        )
        context['page_description'] = truncate_meta(localized_meta_description or page_copy.get('description') or service.description)
        context['page_keywords'] = service.meta_keywords
        context['service_landing'] = service_landing
        context['service_display_title'] = page_copy.get('title') or service_landing.get('badge') or service.title
        context['service_display_description'] = page_copy.get('description') or service.description
        context['service_static_image'] = self._get_static_image_for_service(service.slug)
        context['service_schema_url'] = self.request.build_absolute_uri(self.request.path)
        context['service_home_schema_url'] = self.request.build_absolute_uri(reverse('core:home'))
        context['service_provider_schema_id'] = f"{self.request.build_absolute_uri('/')}#real-estate-agent"
        context['responsible_specialist'] = self._get_responsible_specialist_context(language_code)
        context['service_context_links'] = self._get_service_context_links(service.slug, language_code)
        service_image_url = self._get_service_image_url(service, context['service_static_image'])
        if service_image_url:
            context['og_image_url'] = service_image_url
            context['service_schema_image_url'] = service_image_url
        
        # Добавляем рекомендуемые объекты в зависимости от типа услуги
        context['featured_properties'] = self._get_featured_properties_for_service(service)
        
        return context

    def _build_service_page_title(self, service, page_copy, language_code, localized_meta_title):
        if localized_meta_title:
            return localized_meta_title

        title = page_copy.get('title') or service.title
        normalized_title = title.lower()
        if 'undersun' in normalized_title:
            return title

        location_markers = {
            'ru': 'пхукет',
            'en': 'phuket',
            'th': 'ภูเก็ต',
        }
        has_location = location_markers.get(language_code, 'phuket') in normalized_title

        if language_code == 'ru':
            localized_title = title if has_location else f'{title} на Пхукете'
            return f'{localized_title} - Undersun Estate'

        if language_code == 'th':
            localized_title = title if has_location else f'{title}ในภูเก็ต'
            return f'{localized_title} | Undersun Estate'

        localized_title = title if has_location else f'{title} in Phuket'
        return f'{localized_title} | Undersun Estate'

    def _get_static_image_for_service(self, slug):
        static_path = f'images/services/{slug}.webp'
        return static_path if finders.find(static_path) else ''

    def _get_service_image_url(self, service, static_image_path):
        if service.image:
            return self.request.build_absolute_uri(service.image.url)

        if static_image_path:
            return self.request.build_absolute_uri(static(static_image_path))

        return ''

    def _get_responsible_specialist_context(self, language_code):
        specialist = Team.objects.filter(
            Q(first_name_ru__iexact='Богдан') | Q(first_name_en__iexact='Bogdan') | Q(first_name__iexact='Bogdan'),
            is_active=True,
        ).order_by('display_order', 'id').first()

        if not specialist:
            return None

        def localized_value(field_name):
            candidates = [
                getattr(specialist, f'{field_name}_{language_code}', ''),
                getattr(specialist, f'{field_name}_en', ''),
                getattr(specialist, f'{field_name}_ru', ''),
                getattr(specialist, field_name, ''),
            ]
            return next((value for value in candidates if value), '')

        first_name = localized_value('first_name')
        last_name = localized_value('last_name')
        position = localized_value('position')
        photo_url = ''
        photo_width = 256
        photo_height = 256

        if specialist.photo:
            photo_url = self.request.build_absolute_uri(specialist.photo.url)
            try:
                photo_width = specialist.photo.width or photo_width
                photo_height = specialist.photo.height or photo_height
            except Exception:
                pass

        schema_id = f"{self.request.build_absolute_uri('/')}#bogdan-dyachuk"
        profile_url = self.request.build_absolute_uri(reverse('core:about'))
        schema = {
            '@context': 'https://schema.org',
            '@type': 'Person',
            '@id': schema_id,
            'name': f'{first_name} {last_name}'.strip(),
            'jobTitle': position,
            'url': profile_url,
            'worksFor': {
                '@type': 'Organization',
                '@id': f"{self.request.build_absolute_uri('/')}#real-estate-agent",
                'name': 'Undersun Estate',
            },
        }

        if photo_url:
            schema['image'] = photo_url
        if specialist.email:
            schema['email'] = specialist.email
        if specialist.phone:
            schema['telephone'] = specialist.phone

        return {
            'name': f'{first_name} {last_name}'.strip(),
            'position': position,
            'photo_url': photo_url,
            'photo_width': photo_width,
            'photo_height': photo_height,
            'phone': specialist.phone,
            'phone_display': specialist.phone_display,
            'email': specialist.email,
            'whatsapp_url': specialist.whatsapp_url,
            'telegram_url': specialist.telegram_url,
            'profile_url': profile_url,
            'schema_json': json.dumps(schema, ensure_ascii=False),
        }

    def _get_service_context_links(self, service_slug, language_code):
        labels = {
            'ru': {
                'property_sale': 'Все объекты на продажу',
                'property_rent': 'Каталог аренды',
                'property_land': 'Все земельные участки',
                'contact': 'Оставить запрос',
                'buying_service': 'Как мы сопровождаем покупку',
                'land_service': 'Проверка земли и сделки с участками',
                'commercial_service': 'Коммерческая недвижимость',
                'legal_service': 'Юридическое сопровождение',
                'villa_type': 'Виллы на Пхукете',
                'condo_type': 'Квартиры на Пхукете',
                'townhouse_type': 'Таунхаусы и дома',
            },
            'en': {
                'property_sale': 'All properties for sale',
                'property_rent': 'Rental catalogue',
                'property_land': 'All land plots',
                'contact': 'Send a request',
                'buying_service': 'How we support purchase',
                'land_service': 'Land checks and land deals',
                'commercial_service': 'Commercial real estate',
                'legal_service': 'Legal support',
                'villa_type': 'Villas in Phuket',
                'condo_type': 'Condos in Phuket',
                'townhouse_type': 'Townhouses and houses',
            },
            'th': {
                'property_sale': 'อสังหาริมทรัพย์สำหรับขายทั้งหมด',
                'property_rent': 'แค็ตตาล็อกเช่า',
                'property_land': 'ที่ดินทั้งหมด',
                'contact': 'ส่งคำขอ',
                'buying_service': 'การดูแลการซื้อ',
                'land_service': 'ตรวจสอบที่ดินและดีลที่ดิน',
                'commercial_service': 'อสังหาริมทรัพย์เชิงพาณิชย์',
                'legal_service': 'บริการด้านกฎหมาย',
                'villa_type': 'วิลล่าในภูเก็ต',
                'condo_type': 'คอนโดในภูเก็ต',
                'townhouse_type': 'ทาวน์เฮาส์และบ้าน',
            },
        }.get(language_code, {})

        configs = {
            'buying-property': {
                'title': {
                    'ru': 'Подборки для покупки',
                    'en': 'Selections for buyers',
                    'th': 'คัดสรรสำหรับผู้ซื้อ',
                },
                'description': {
                    'ru': 'Начните с актуальных объектов на продажу и смежных подборок по типам недвижимости.',
                    'en': 'Start with active sale listings and related property-type collections.',
                    'th': 'เริ่มจากรายการขายที่พร้อมอยู่และคัดสรรตามประเภทอสังหาริมทรัพย์.',
                },
                'primary_url': reverse('properties:property_sale'),
                'primary_label': labels['property_sale'],
                'queryset': Property.objects.filter(deal_type__in=['sale', 'both']).exclude(property_type__name='land'),
                'secondary': [
                    ('villa', labels['villa_type']),
                    ('condo', labels['condo_type']),
                    ('townhouse', labels['townhouse_type']),
                ],
            },
            'land-sale': {
                'title': {
                    'ru': 'Земельные участки в каталоге',
                    'en': 'Land plots in the catalogue',
                    'th': 'ที่ดินในแค็ตตาล็อก',
                },
                'description': {
                    'ru': 'Посмотрите реальные участки, по которым особенно важны титул, доступ, назначение земли и инфраструктура.',
                    'en': 'Browse real plots where title, access, permitted use, and infrastructure checks are especially important.',
                    'th': 'ดูที่ดินจริงที่ควรตรวจสอบเอกสารสิทธิ์ ทางเข้าออก การใช้ประโยชน์ และโครงสร้างพื้นฐาน.',
                },
                'primary_url': reverse('properties:property_by_type', kwargs={'type_name': 'land'}),
                'primary_label': labels['property_land'],
                'queryset': Property.objects.filter(property_type__name='land'),
                'secondary': [
                    ('service:legal-services', labels['legal_service']),
                    ('property_sale', labels['property_sale']),
                ],
            },
            'renting-property': {
                'title': {
                    'ru': 'Аренда и быстрый запрос',
                    'en': 'Rentals and quick request',
                    'th': 'เช่าและส่งคำขออย่างรวดเร็ว',
                },
                'description': {
                    'ru': 'Если активных объектов аренды в каталоге мало, оставьте запрос: команда подберёт варианты под срок, район и состав семьи.',
                    'en': 'If active rental listings are limited, send a request and the team will source options by term, area, and household needs.',
                    'th': 'หากรายการเช่าในแค็ตตาล็อกมีจำกัด ส่งคำขอเพื่อให้ทีมคัดตัวเลือกตามระยะเวลา พื้นที่ และความต้องการของผู้อยู่อาศัย.',
                },
                'primary_url': reverse('properties:property_rent'),
                'primary_label': labels['property_rent'],
                'queryset': Property.objects.filter(deal_type__in=['rent', 'both']),
                'secondary': [
                    ('contact', labels['contact']),
                    ('property_sale', labels['property_sale']),
                ],
            },
            'selling-property': {
                'title': {
                    'ru': 'Как покупатели видят рынок',
                    'en': 'How buyers browse the market',
                    'th': 'ผู้ซื้อดูตลาดอย่างไร',
                },
                'description': {
                    'ru': 'Эти страницы помогают понять, как объект будет конкурировать в каталоге и какие форматы сейчас сравнивают покупатели.',
                    'en': 'These pages help show how a listing competes in the catalogue and which formats buyers compare.',
                    'th': 'หน้าเหล่านี้ช่วยให้เห็นว่าทรัพย์จะแข่งขันในแค็ตตาล็อกอย่างไรและผู้ซื้อเปรียบเทียบรูปแบบใด.',
                },
                'primary_url': reverse('properties:property_sale'),
                'primary_label': labels['property_sale'],
                'queryset': Property.objects.filter(deal_type__in=['sale', 'both']),
                'secondary': [
                    ('service:buying-property', labels['buying_service']),
                    ('villa', labels['villa_type']),
                    ('condo', labels['condo_type']),
                ],
            },
            'commercial-real-estate': {
                'title': {
                    'ru': 'Связанные направления сделки',
                    'en': 'Related deal directions',
                    'th': 'หัวข้อที่เกี่ยวข้องกับดีล',
                },
                'description': {
                    'ru': 'Для коммерческих объектов чаще всего нужны проверка условий сделки, сравнение с рынком продажи и юридическое сопровождение.',
                    'en': 'Commercial deals usually require transaction review, market comparison, and legal support.',
                    'th': 'ดีลเชิงพาณิชย์มักต้องตรวจเงื่อนไข เปรียบเทียบตลาด และมีการดูแลด้านกฎหมาย.',
                },
                'primary_url': reverse('properties:property_sale'),
                'primary_label': labels['property_sale'],
                'queryset': Property.objects.none(),
                'secondary': [
                    ('service:legal-services', labels['legal_service']),
                    ('service:land-sale', labels['land_service']),
                    ('contact', labels['contact']),
                ],
            },
            'legal-services': {
                'title': {
                    'ru': 'Где проверка особенно важна',
                    'en': 'Where checks matter most',
                    'th': 'กรณีที่การตรวจสอบสำคัญมาก',
                },
                'description': {
                    'ru': 'Юридическая проверка особенно нужна при покупке, сделках с землёй и коммерческих объектах.',
                    'en': 'Legal review is especially relevant for purchases, land deals, and commercial property.',
                    'th': 'การตรวจด้านกฎหมายสำคัญมากสำหรับการซื้อ ดีลที่ดิน และอสังหาริมทรัพย์เชิงพาณิชย์.',
                },
                'primary_url': reverse('core:service_detail', kwargs={'slug': 'buying-property'}),
                'primary_label': labels['buying_service'],
                'queryset': Property.objects.filter(property_type__name='land'),
                'secondary': [
                    ('service:land-sale', labels['land_service']),
                    ('service:commercial-real-estate', labels['commercial_service']),
                    ('property_sale', labels['property_sale']),
                ],
            },
        }

        config = configs.get(service_slug)
        if not config:
            return {}

        queryset = config['queryset'].filter(is_active=True, status='available').select_related(
            'district',
            'location',
            'property_type',
        ).order_by('-is_featured', '-featured_priority', '-updated_at')

        property_links = [self._build_context_property_link(prop, language_code) for prop in queryset[:4]]
        secondary_links = [
            link
            for link in (self._build_context_secondary_link(target, label) for target, label in config['secondary'])
            if link
        ]

        return {
            'title': config['title'].get(language_code) or config['title']['en'],
            'description': config['description'].get(language_code) or config['description']['en'],
            'primary_url': config['primary_url'],
            'primary_label': config['primary_label'],
            'property_links': property_links,
            'secondary_links': secondary_links,
        }

    def _build_context_property_link(self, prop, language_code):
        meta_parts = []
        if prop.property_type:
            meta_parts.append(prop.property_type.name_display)
        if prop.district:
            meta_parts.append(str(prop.district))
        elif prop.location:
            meta_parts.append(str(prop.location))

        fallback_meta = {
            'ru': 'Объект в каталоге',
            'en': 'Catalogue listing',
            'th': 'รายการในแค็ตตาล็อก',
        }

        return {
            'url': prop.get_absolute_url(),
            'title': prop.get_display_title(),
            'meta': ' · '.join(meta_parts) or fallback_meta.get(language_code, fallback_meta['en']),
        }

    def _build_context_secondary_link(self, target, label):
        if target.startswith('service:'):
            return {
                'url': reverse('core:service_detail', kwargs={'slug': target.split(':', 1)[1]}),
                'label': label,
            }

        if target == 'property_sale':
            return {'url': reverse('properties:property_sale'), 'label': label}

        if target == 'property_rent':
            return {'url': reverse('properties:property_rent'), 'label': label}

        if target == 'contact':
            return {'url': reverse('core:contact'), 'label': label}

        if PropertyType.objects.filter(name=target).exists():
            return {'url': reverse('properties:property_by_type', kwargs={'type_name': target}), 'label': label}

        return None
    
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
