import json
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus, urlencode

from django.conf import settings
from django.views.generic import ListView, DetailView, View
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, Http404, HttpResponseRedirect, HttpResponse, HttpResponsePermanentRedirect
# login_required decorator removed
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Count, Case, When, Value, IntegerField, F
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.translation import gettext, ngettext, override
from django.utils.html import strip_tags
from django.templatetags.static import static

from apps.currency.services import CurrencyService
from apps.core.utils import build_query_string, rate_limit, validate_form_security, truncate_meta
from apps.core.amp_utils import convert_html_to_amp
from apps.core.models import SEOContentBlock
from apps.core.seo_utils import build_property_meta
from .seo_landings import resolve_landing_signature, build_candidate_slugs
from .models import Property, PropertyType
from apps.locations.models import District, Location
from apps.users.models import PropertyInquiry
from .yml_feed import YandexYmlFeedGenerator


LEGACY_PROPERTY_SLUG_REDIRECTS = {
    # Укороченный slug из старого каталога → актуальный slug
    '1-bedroom-apart': '1-bedroom-apartment-in-a-deluxe-condominium-in-rawai',
}

PROPERTY_TYPE_NAV_LABELS = {
    'condo': {
        'ru': 'Квартиры',
        'en': 'Condos',
        'th': 'คอนโดมิเนียม',
    },
    'villa': {
        'ru': 'Виллы',
        'en': 'Villas',
        'th': 'วิลล่า',
    },
    'townhouse': {
        'ru': 'Дома',
        'en': 'Townhouses',
        'th': 'ทาวน์เฮาส์',
    },
    'land': {
        'ru': 'Земельные участки',
        'en': 'Land plots',
        'th': 'ที่ดิน',
    },
    'investment': {
        'ru': 'Инвестиционная недвижимость',
        'en': 'Investment properties',
        'th': 'อสังหาริมทรัพย์เพื่อการลงทุน',
    },
    'business': {
        'ru': 'Готовый бизнес',
        'en': 'Businesses',
        'th': 'ธุรกิจพร้อมดำเนินการ',
    },
}

CATALOG_SEO_TEXTS = {
    'ru': {
        'subject_fallback': 'Недвижимость',
        'heading_fallback': 'Каталог недвижимости на Пхукете',
        'deal_sale': 'на продажу',
        'deal_rent': 'в аренду',
        'geo_location': 'в %(location)s, Пхукет',
        'geo_district': 'в районе %(district)s, Пхукет',
        'geo_fallback': 'на Пхукете',
        'intro_heading': 'Что важно по этой подборке',
        'intro_template': 'В этой подборке собраны %(subject)s%(deal)s%(geo)s. Сейчас доступно %(count)s актуальных предложений.',
        'budget_sentence': 'По выбранным фильтрам бюджет %(budget)s.',
        'bedrooms_sentence': 'Фильтр по спальням: %(bedrooms)s.',
        'stage_sentence': 'В подборке показаны объекты со статусом "%(status)s".',
        'follow_up': 'Каталог обновляется по мере появления новых предложений, поэтому подборка подходит для первичного отбора и сравнения объектов.',
        'faq_heading': 'Частые вопросы о подборке',
        'faq_count_q': 'Сколько объектов представлено на этой странице?',
        'faq_count_a': 'Сейчас на странице %(count)s актуальных предложений.',
        'faq_geo_q': 'Какая локация представлена в подборке?',
        'faq_geo_a': 'Подборка посвящена объектам %(subject)s%(deal)s%(geo)s.',
        'faq_budget_q': 'Какой бюджет выбран в фильтрах?',
        'faq_budget_a': 'На странице применен бюджет %(budget)s.',
        'faq_bedrooms_q': 'Есть ли отбор по количеству спален?',
        'faq_bedrooms_a': 'Да, сейчас выбраны варианты %(bedrooms)s.',
        'faq_stage_q': 'Какая стадия строительства выбрана?',
        'faq_stage_a': 'Сейчас показаны объекты со статусом "%(status)s".',
        'popular_types_heading': 'Популярные типы недвижимости',
        'popular_districts_heading': 'Популярные районы',
        'page_title_template': '{base_title} — страница {page} | Undersun Estate',
        'page_description_template': 'Страница {page} каталога: {base_heading}. Смотрите дополнительные объекты в этой подборке.',
        'results_single': '%(count)s предложение',
        'results_plural': '%(count)s предложений',
        'bedroom_single': '%(count)s спальней',
        'bedroom_plural': '%(count)s спальнями',
        'bedroom_plus': '%(count)s+ спальнями',
    },
    'en': {
        'subject_fallback': 'Property',
        'heading_fallback': 'Phuket property catalogue',
        'deal_sale': 'for sale',
        'deal_rent': 'for rent',
        'geo_location': 'in %(location)s, Phuket',
        'geo_district': 'in %(district)s district, Phuket',
        'geo_fallback': 'in Phuket',
        'intro_heading': 'About this selection',
        'intro_template': 'This selection features %(subject)s%(deal)s%(geo)s. There are currently %(count)s active listings available.',
        'budget_sentence': 'The selected budget range is %(budget)s.',
        'bedrooms_sentence': 'Bedroom filter: %(bedrooms)s.',
        'stage_sentence': 'The page currently shows properties with status "%(status)s".',
        'follow_up': 'The catalogue is updated as new listings appear, so this page works well for shortlisting and comparing properties.',
        'faq_heading': 'Frequently asked questions about selection',
        'faq_count_q': 'How many listings are shown on this page?',
        'faq_count_a': 'There are currently %(count)s active listings on this page.',
        'faq_geo_q': 'Which area does this selection cover?',
        'faq_geo_a': 'This page focuses on %(subject)s%(deal)s%(geo)s.',
        'faq_budget_q': 'What budget is selected in the filters?',
        'faq_budget_a': 'The current filter uses a budget of %(budget)s.',
        'faq_bedrooms_q': 'Is there a bedroom filter applied?',
        'faq_bedrooms_a': 'Yes, the current selection includes %(bedrooms)s.',
        'faq_stage_q': 'Which construction stage is selected?',
        'faq_stage_a': 'The current selection shows properties with status "%(status)s".',
        'popular_types_heading': 'Popular property types',
        'popular_districts_heading': 'Popular districts',
        'page_title_template': '{base_title} — page {page} | Undersun Estate',
        'page_description_template': 'Page {page} of the catalogue: {base_heading}. Browse more listings in this collection.',
        'results_single': '%(count)s listing',
        'results_plural': '%(count)s listings',
        'bedroom_single': '%(count)s bedroom',
        'bedroom_plural': '%(count)s bedrooms',
        'bedroom_plus': '%(count)s+ bedrooms',
    },
    'th': {
        'subject_fallback': 'อสังหาริมทรัพย์',
        'heading_fallback': 'แค็ตตาล็อกอสังหาริมทรัพย์ในภูเก็ต',
        'deal_sale': 'สำหรับขาย',
        'deal_rent': 'สำหรับเช่า',
        'geo_location': 'ใน %(location)s, ภูเก็ต',
        'geo_district': 'ในเขต %(district)s, ภูเก็ต',
        'geo_fallback': 'ในภูเก็ต',
        'intro_heading': 'ภาพรวมของคัดสรรนี้',
        'intro_template': 'หน้านี้รวบรวม %(subject)s%(deal)s%(geo)s ขณะนี้มีข้อเสนอที่พร้อมอยู่ %(count)s รายการ.',
        'budget_sentence': 'ช่วงงบประมาณที่เลือกคือ %(budget)s.',
        'bedrooms_sentence': 'ตัวกรองห้องนอน: %(bedrooms)s.',
        'stage_sentence': 'หน้านี้แสดงเฉพาะอสังหาริมทรัพย์ที่มีสถานะ "%(status)s".',
        'follow_up': 'แค็ตตาล็อกจะอัปเดตเมื่อมีข้อเสนอใหม่ เหมาะสำหรับคัดเลือกและเปรียบเทียบอสังหาริมทรัพย์เบื้องต้น.',
        'faq_heading': 'คำถามที่พบบ่อยเกี่ยวกับคัดสรรนี้',
        'faq_count_q': 'หน้านี้มีอสังหาริมทรัพย์กี่รายการ?',
        'faq_count_a': 'ขณะนี้หน้านี้มีข้อเสนอที่พร้อมอยู่ %(count)s รายการ.',
        'faq_geo_q': 'คัดสรรนี้ครอบคลุมพื้นที่ใด?',
        'faq_geo_a': 'หน้านี้เน้น %(subject)s%(deal)s%(geo)s.',
        'faq_budget_q': 'ตัวกรองงบประมาณที่ใช้คืออะไร?',
        'faq_budget_a': 'ตัวกรองปัจจุบันใช้งบประมาณ %(budget)s.',
        'faq_bedrooms_q': 'มีการกรองตามจำนวนห้องนอนหรือไม่?',
        'faq_bedrooms_a': 'มี โดยคัดเลือกเป็น %(bedrooms)s.',
        'faq_stage_q': 'เลือกสถานะการก่อสร้างแบบใด?',
        'faq_stage_a': 'ขณะนี้แสดงอสังหาริมทรัพย์ที่มีสถานะ "%(status)s".',
        'popular_types_heading': 'ประเภทอสังหาริมทรัพย์ยอดนิยม',
        'popular_districts_heading': 'ย่านยอดนิยม',
        'page_title_template': '{base_title} — หน้า {page} | Undersun Estate',
        'page_description_template': 'หน้า {page} ของแค็ตตาล็อก {base_heading} ดูรายการเพิ่มเติมในคัดสรรนี้',
        'results_single': '%(count)s รายการ',
        'results_plural': '%(count)s รายการ',
        'bedroom_single': '%(count)s ห้องนอน',
        'bedroom_plural': '%(count)s ห้องนอน',
        'bedroom_plus': '%(count)s+ ห้องนอน',
    },
}


def _normalize_whitespace(value):
    if not isinstance(value, str):
        return value
    return ' '.join(value.split())


def _get_translated_attr(instance, field_name, language_code='ru', fallback=''):
    if instance is None:
        return fallback

    localized_field_name = field_name if language_code == 'ru' else f'{field_name}_{language_code}'
    localized_value = getattr(instance, localized_field_name, None)
    base_value = getattr(instance, field_name, None)
    value = localized_value or base_value or fallback
    return _normalize_whitespace(value)


def _get_property_catalog_type_url(property_obj):
    if property_obj.property_type:
        return reverse('properties:property_by_type', args=[property_obj.property_type.name])

    return reverse('properties:property_list')


def _get_property_type_nav_label(property_obj, language_code='ru'):
    if not property_obj.property_type:
        return gettext('Недвижимость')

    type_slug = property_obj.property_type.name
    mapped_label = PROPERTY_TYPE_NAV_LABELS.get(type_slug, {}).get(language_code)
    if mapped_label:
        return mapped_label

    return _get_translated_attr(
        property_obj.property_type,
        'name_display',
        language_code,
        gettext('Недвижимость'),
    )


def _build_property_location_context(property_obj, language_code='ru'):
    district_label = _get_translated_attr(property_obj.district, 'name', language_code, 'Phuket')
    location_label = _get_translated_attr(property_obj.location, 'name', language_code, '') if property_obj.location else ''
    full_location_label = district_label
    if location_label:
        full_location_label = f'{district_label}, {location_label}'

    return {
        'property_district_label': district_label,
        'property_location_label': location_label,
        'property_full_location_label': full_location_label,
    }


def _annotate_property_labels(property_obj, language_code='ru'):
    labels = _build_property_location_context(property_obj, language_code)
    property_obj.localized_district_label = labels['property_district_label']
    property_obj.localized_location_name = labels['property_location_label']
    property_obj.localized_location_label = labels['property_full_location_label']
    return property_obj


def _get_catalog_texts(language_code='ru'):
    return CATALOG_SEO_TEXTS.get((language_code or 'ru')[:2], CATALOG_SEO_TEXTS['ru'])


class DealTypeRedirectMixin:
    """Перенаправляет на корректный раздел каталога при смене типа сделки."""

    deal_type_redirects = None  # {deal_type_value: 'url_name'}

    def dispatch(self, request, *args, **kwargs):
        redirect_response = self._maybe_redirect_by_deal_type(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def _maybe_redirect_by_deal_type(self, request):
        if not self.deal_type_redirects:
            return None

        deal_type = request.GET.get('deal_type')
        target_view = self.deal_type_redirects.get(deal_type)
        if not target_view:
            return None

        query_params = request.GET.copy()
        if 'deal_type' in query_params:
            query_params.pop('deal_type')

        query_string = query_params.urlencode()
        target_url = reverse(target_view)
        if query_string:
            target_url = f"{target_url}?{query_string}"

        return HttpResponseRedirect(target_url)


class PropertyListView(ListView):
    model = Property
    template_name = 'properties/list.html'
    context_object_name = 'properties'
    paginate_by = 12
    PROPERTY_TYPE_PRIORITY = ['condo', 'villa', 'townhouse', 'land']
    BUILD_STATUS_ALLOWED_PROPERTY_TYPES = {'condo', 'villa', 'townhouse'}

    FILTER_PARAM_NAMES = {
        'deal_type': 'single',
        'property_type': 'multi',
        'district': 'single',
        'location': 'single',
        'min_price': 'single',
        'max_price': 'single',
        'bedrooms': 'multi',
        'amenities': 'multi',
        'q': 'single',
        'build_status': 'single',
    }

    PAGINATION_ALLOWED_PARAMS = (
        'deal_type',
        'property_type',
        'district',
        'location',
        'min_price',
        'max_price',
        'bedrooms',
        'amenities',
        'q',
        'sort',
        'map_view',
        'build_status',
    )

    NON_INDEX_FILTER_KEYS = ('min_price', 'max_price', 'bedrooms', 'amenities', 'q', 'build_status')

    def get_paginate_by(self, queryset):
        """Отключить пагинацию для карты"""
        if self.request.GET.get('map_view') == 'true':
            return None  # Отключить пагинацию для карты
        return self.paginate_by

    def has_active_filters(self):
        """Проверяет наличие пользовательских фильтров в GET параметрах."""
        request = self.request
        for param, param_type in self.FILTER_PARAM_NAMES.items():
            if param_type == 'multi':
                values = [value for value in request.GET.getlist(param) if value not in (None, '')]
                if values:
                    return True
            else:
                value = request.GET.get(param)
                if value not in (None, ''):
                    return True
        return False

    def get_queryset(self):
        queryset = Property.objects.filter(
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')
        
        # Применяем фильтры из GET параметров
        queryset = self.apply_filters(queryset)

        # Сортировка
        sort_param = self.request.GET.get('sort')
        sort_by = sort_param or '-created_at'
        allowed_sorts = [
            'price_asc', 'price_desc',
            'price_sale_usd', '-price_sale_usd',
            'price_sale_thb', '-price_sale_thb',
            'price_rent_monthly', '-price_rent_monthly',
            'area_total', '-area_total',
            'created_at', '-created_at'
        ]
        ordering = []

        if not sort_param and not self.has_active_filters():
            ordering.extend(['-featured_priority', '-is_featured'])

        if sort_by in allowed_sorts:
            if self._is_price_sort(sort_by):
                ordering.append(self.get_catalog_price_sort_expression(descending=self._is_descending_price_sort(sort_by)))
            else:
                ordering.append(sort_by)
        else:
            ordering.append('-created_at')

        queryset = queryset.order_by(*ordering)

        return queryset

    def get_effective_catalog_deal_type(self):
        request_deal_type = self.request.GET.get('deal_type')
        if request_deal_type in {'sale', 'rent'}:
            return request_deal_type

        return getattr(self, 'forced_deal_type', '') or ''

    def _is_price_sort(self, sort_value):
        return sort_value in {
            'price_asc',
            'price_desc',
            'price_sale_usd',
            '-price_sale_usd',
            'price_sale_thb',
            '-price_sale_thb',
            'price_rent_monthly',
            '-price_rent_monthly',
        }

    def _is_descending_price_sort(self, sort_value):
        return sort_value in {'price_desc', '-price_sale_usd', '-price_sale_thb', '-price_rent_monthly'}

    def get_catalog_price_sort_expression(self, descending=False):
        currency_code = CurrencyService.get_selected_currency_code(self.request)
        sale_expression = self._build_catalog_price_expression(currency_code, 'sale')
        rent_expression = self._build_catalog_price_expression(currency_code, 'rent')
        effective_deal_type = self.get_effective_catalog_deal_type()

        if effective_deal_type == 'sale':
            expression = sale_expression
        elif effective_deal_type == 'rent':
            expression = rent_expression
        else:
            expression = Case(
                When(deal_type='rent', then=rent_expression),
                default=Coalesce(sale_expression, rent_expression),
            )

        return expression.desc(nulls_last=True) if descending else expression.asc(nulls_last=True)

    def _build_catalog_price_expression(self, currency_code, deal_type):
        price_field_map = {
            'sale': {
                'USD': ['price_sale_usd', 'price_sale_thb', 'price_sale_rub'],
                'THB': ['price_sale_thb', 'price_sale_usd', 'price_sale_rub'],
                'RUB': ['price_sale_rub', 'price_sale_thb', 'price_sale_usd'],
            },
            'rent': {
                'USD': ['price_rent_monthly', 'price_rent_monthly_thb', 'price_rent_monthly_rub'],
                'THB': ['price_rent_monthly_thb', 'price_rent_monthly', 'price_rent_monthly_rub'],
                'RUB': ['price_rent_monthly_rub', 'price_rent_monthly_thb', 'price_rent_monthly'],
            },
        }

        normalized_currency = (currency_code or 'USD').upper()
        field_candidates = price_field_map.get(deal_type, {}).get(normalized_currency) or price_field_map[deal_type]['USD']
        ordered_fields = []
        for field_name in field_candidates:
            if field_name not in ordered_fields:
                ordered_fields.append(field_name)

        return Coalesce(*[F(field_name) for field_name in ordered_fields])

    def apply_filters(self, queryset):
        """Применяет фильтры на основе GET параметров"""
        # Тип сделки (deal_type)
        deal_type = self.request.GET.get('deal_type')
        if deal_type and deal_type in ['sale', 'rent']:
            queryset = queryset.filter(deal_type__in=[deal_type, 'both'])
        
        # Тип недвижимости (множественный выбор)
        property_types = self.request.GET.getlist('property_type')
        if property_types:
            queryset = queryset.filter(property_type__name__in=property_types)

        # Стадия готовности
        build_status = self.request.GET.get('build_status')
        valid_statuses = dict(Property.BUILD_STATUS_CHOICES)
        if build_status and build_status in valid_statuses:
            queryset = queryset.filter(build_status=build_status)

        # Район
        district = self.request.GET.get('district')
        if district:
            queryset = queryset.filter(district__slug=district)
        
        # Локация
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location__slug=location)
        
        currency_code = CurrencyService.get_selected_currency_code(self.request)
        sale_field, rent_field = CurrencyService.get_price_field_names(currency_code)

        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')

        if min_price:
            try:
                min_val = Decimal(min_price)
                price_filter = Q(**{f"{sale_field}__gte": min_val})
                if rent_field:
                    price_filter |= Q(**{f"{rent_field}__gte": min_val})
                queryset = queryset.filter(price_filter)
            except (InvalidOperation, ValueError):
                pass

        if max_price:
            try:
                max_val = Decimal(max_price)
                price_filter = Q(**{f"{sale_field}__lte": max_val})
                if rent_field:
                    price_filter |= Q(**{f"{rent_field}__lte": max_val})
                queryset = queryset.filter(price_filter)
            except (InvalidOperation, ValueError):
                pass
        
        # Количество спален
        bedrooms = self.request.GET.getlist('bedrooms')
        if bedrooms:
            bedroom_filters = Q()
            for bedroom in bedrooms:
                if bedroom == '4+':
                    bedroom_filters |= Q(bedrooms__gte=4)
                else:
                    try:
                        bedroom_filters |= Q(bedrooms=int(bedroom))
                    except ValueError:
                        pass
            if bedroom_filters:
                queryset = queryset.filter(bedroom_filters)
        
        # Удобства/особенности (динамические)
        amenities = self.request.GET.getlist('amenities')
        if amenities:
            for amenity_id in amenities:
                try:
                    amenity_id = int(amenity_id)
                    queryset = queryset.filter(features__feature__id=amenity_id)
                except ValueError:
                    pass
        
        # Поиск по тексту
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title_ru__icontains=query) |
                Q(title_en__icontains=query) |
                Q(description_ru__icontains=query) |
                Q(description_en__icontains=query) |
                Q(district__name_ru__icontains=query) |
                Q(district__name_en__icontains=query)
            )
        
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.build_filter_context())

        context['pagination_query_string'] = self.get_pagination_query_string()

        context['results_count_i18n'] = {
            'zero': gettext('Объекты не найдены'),
            'one': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 1),
            'few': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 2),
            'many': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 5),
        }

        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]

        with override(language_code):
            context['seo_heading'] = self.build_seo_heading(context)
        context['catalog_results_count'] = self._get_results_count(context) or 0
        context['generated_catalog_seo'] = self.build_generated_catalog_seo(context, language_code)
        context['catalog_seo_block'] = self.get_catalog_seo_block(context)
        context['catalog_faq'] = self.build_catalog_faq(context, language_code)
        context['catalog_breadcrumbs'] = self.build_catalog_breadcrumbs(context, language_code)
        context['property_type_filter_links'] = self.build_property_type_filter_links(context, language_code)
        context['active_filter_chips'] = self.build_active_filter_chips(context)
        context['active_filters_summary'] = self.build_active_filters_summary(context['active_filter_chips'], language_code)
        context['active_filters_reset_url'] = self.build_active_filters_reset_url(context)
        context['catalog_internal_links'] = self.build_catalog_internal_links(context, language_code)
        context['no_results_recovery'] = self.build_no_results_recovery(context, language_code)
        self.apply_catalog_indexation_strategy(context, language_code)

        self.update_page_meta(context, language_code)

        return context

    def update_page_meta(self, context, language_code=None):
        """Recalculate SEO meta based on the latest context values."""
        language_code = (language_code or getattr(self.request, 'LANGUAGE_CODE', 'ru'))[:2]
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()

        with override(language_code):
            meta = build_property_meta(
                heading=context.get('seo_heading'),
                results_count=self._get_results_count(context),
                property_type_name=self._get_catalog_subject_label(property_type_obj, language_code) if property_type_obj else '',
                district_name=_get_translated_attr(district_obj, 'name', language_code, '') if district_obj else '',
                location_name=_get_translated_attr(location_obj, 'name', language_code, '') if location_obj else '',
                min_price=self._parse_price_value(current_filters.get('min_price')),
                max_price=self._parse_price_value(current_filters.get('max_price')),
                currency_code=CurrencyService.get_selected_currency_code(self.request),
                bedrooms=current_filters.get('bedrooms') or [],
                build_status_label=self._resolve_build_status_label(current_filters.get('build_status')),
                language_code=language_code,
            )

        context['page_title'] = meta.title
        context['page_description'] = meta.description

        page_number = self._get_catalog_page_number()
        if context.get('catalog_is_indexable') and page_number and page_number > 1:
            meta = self._refine_paginated_catalog_meta(
                meta.title,
                meta.description,
                context.get('seo_heading') or meta.title,
                page_number,
                language_code,
            )
            context['page_title'] = meta['title']
            context['page_description'] = meta['description']
            self.request.seo_pagination_customized = True
        else:
            self.request.seo_pagination_customized = False

        self.request.seo_page_title = context['page_title']
        self.request.seo_page_description = context['page_description']

        return context

    def _refine_paginated_catalog_meta(self, base_title, base_description, base_heading, page_number, language_code='ru'):
        texts = _get_catalog_texts(language_code)
        site_name = getattr(settings, 'SITE_NAME', 'Undersun Estate')
        base_title_without_site = base_title or base_heading or texts['heading_fallback']

        site_suffix = f' | {site_name}'
        if base_title_without_site.endswith(site_suffix):
            base_title_without_site = base_title_without_site[:-len(site_suffix)]

        title = texts['page_title_template'].format(
            base_title=base_title_without_site.strip(),
            page=page_number,
        )
        description = truncate_meta(texts['page_description_template'].format(
            page=page_number,
            base_heading=(base_heading or texts['heading_fallback']).strip(),
        ))

        return {
            'title': title,
            'description': description,
        }

    def build_filter_context(self):
        from .models import PropertyFeature

        priority_case = Case(
            *[
                When(name=property_type, then=Value(index))
                for index, property_type in enumerate(self.PROPERTY_TYPE_PRIORITY)
            ],
            default=Value(len(self.PROPERTY_TYPE_PRIORITY)),
            output_field=IntegerField(),
        )

        property_types = (
            PropertyType.objects
            .annotate(_type_priority=priority_case)
            .order_by('_type_priority', 'name_display')
        )
        districts = District.objects.all()

        selected_district = self.request.GET.get('district')
        if selected_district:
            locations = Location.objects.filter(district__slug=selected_district)
        else:
            locations = Location.objects.all()

        amenities = PropertyFeature.objects.annotate(
            property_count=Count('propertyfeaturerelation')
        ).filter(property_count__gte=1).order_by('-property_count', 'name')

        current_filters = {
            'deal_type': self.request.GET.get('deal_type', ''),
            'property_type': self.request.GET.getlist('property_type'),
            'district': self.request.GET.get('district', ''),
            'location': self.request.GET.get('location', ''),
            'min_price': self.request.GET.get('min_price', ''),
            'max_price': self.request.GET.get('max_price', ''),
            'bedrooms': self.request.GET.getlist('bedrooms'),
            'amenities': self.request.GET.getlist('amenities'),
            'q': self.request.GET.get('q', ''),
            'sort': self.request.GET.get('sort', '-created_at'),
            'build_status': self.request.GET.get('build_status', ''),
        }

        filter_context = {
            'property_types': property_types,
            'districts': districts,
            'locations': locations,
            'amenities': amenities,
            'current_filters': current_filters,
            'build_status_choices': Property.BUILD_STATUS_CHOICES,
        }
        filter_context['show_build_status_filter'] = self.should_show_build_status_filter(filter_context)
        return filter_context

    def should_show_build_status_filter(self, context):
        """Показываем фильтр "Готово/стройка" всегда, кроме аренды и типов без стадии строительства."""
        current_filters = context.get('current_filters', {})
        deal_type = context.get('deal_type') or current_filters.get('deal_type')
        if deal_type == 'rent':
            return False

        selected_types = set(current_filters.get('property_type') or [])
        current_type = context.get('current_property_type')
        if current_type:
            selected_types.add(current_type)
        elif context.get('property_type'):
            selected_types.add(context['property_type'].name)

        if not selected_types:
            # Тип объекта не выбран — показываем фильтр по умолчанию
            return True

        return all(pt in self.BUILD_STATUS_ALLOWED_PROPERTY_TYPES for pt in selected_types)

    def get_pagination_query_string(self):
        allowed_keys = list(self.PAGINATION_ALLOWED_PARAMS)
        return build_query_string(self.request.GET, allowed_keys)

    def _get_primary_property_type(self, context):
        property_type = context.get('property_type')
        if property_type:
            return property_type

        selected_types = self.request.GET.getlist('property_type')
        if len(selected_types) == 1:
            return PropertyType.objects.filter(name=selected_types[0]).first()

        return None

    def build_seo_heading(self, context):
        """Builds an SEO-friendly H1 based on selected filters."""
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]
        texts = _get_catalog_texts(language_code)
        deal_type = context.get('deal_type') or self.request.GET.get('deal_type', '')
        property_type_obj = self._get_primary_property_type(context)
        current_filters = context.get('current_filters', {})
        location_obj, district_obj = self._get_location_and_district()

        subject = self._get_catalog_subject_label(property_type_obj, language_code) or texts['subject_fallback']
        deal_phrase = self._get_catalog_deal_phrase(deal_type, language_code)
        bedrooms_phrase = self._get_catalog_bedrooms_phrase(
            current_filters.get('bedrooms') or [],
            language_code,
            with_preposition=(language_code == 'ru'),
        )
        geo_phrase = self._get_catalog_geo_phrase(location_obj, district_obj, language_code)

        if language_code == 'en':
            segments = [subject]
            if bedrooms_phrase:
                segments.append(bedrooms_phrase)
            if deal_phrase:
                segments.append(deal_phrase)
            if geo_phrase:
                segments.append(geo_phrase)
            heading = ' '.join(seg for seg in segments if seg).strip()
        elif language_code == 'th':
            segments = [subject]
            if bedrooms_phrase:
                segments.append(bedrooms_phrase)
            if deal_phrase:
                segments.append(deal_phrase)
            if geo_phrase:
                segments.append(geo_phrase)
            heading = ' '.join(seg for seg in segments if seg).strip()
        else:
            segments = [subject]
            if bedrooms_phrase:
                segments.append(bedrooms_phrase)
            if deal_phrase:
                segments.append(deal_phrase)
            if geo_phrase:
                segments.append(geo_phrase)
            heading = ' '.join(seg for seg in segments if seg).strip()

        if not heading:
            heading = texts['heading_fallback']

        return heading

    def _get_location_and_district(self):
        location_slug = self.request.GET.get('location')
        district_slug = self.request.GET.get('district')
        location_obj = None
        district_obj = None

        if location_slug:
            location_qs = Location.objects.select_related('district').filter(slug=location_slug)
            if district_slug:
                location_qs = location_qs.filter(district__slug=district_slug)
            location_obj = location_qs.first()
            if location_obj:
                district_obj = location_obj.district

        if not district_obj and district_slug:
            district_obj = District.objects.filter(slug=district_slug).first()

        return location_obj, district_obj

    def get_catalog_seo_block(self, context):
        """Возвращает SEO-блок для каталога с учётом языка и контекста."""
        if not self.is_base_indexable_filter_page(context):
            return None

        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]
        candidate_slugs = self.get_seo_block_candidates(context)
        if not candidate_slugs:
            return None

        ordering = Case(
            *[
                When(slug=slug, then=Value(index))
                for index, slug in enumerate(candidate_slugs)
            ],
            default=Value(len(candidate_slugs)),
            output_field=IntegerField(),
        )

        blocks = (
            SEOContentBlock.objects
            .filter(is_active=True, slug__in=candidate_slugs)
            .annotate(_candidate_order=ordering)
            .order_by('_candidate_order')
        )

        for block in blocks:
            content = block.get_content(language_code)
            if content:
                return {
                    'title': block.title,
                    'content': content,
                    'slug': block.slug,
                }

        return None

    def _get_results_count(self, context):
        paginator = context.get('paginator')
        if paginator:
            return paginator.count
        properties = context.get(self.context_object_name)
        if properties is not None:
            try:
                return len(properties)
            except TypeError:
                return None
        return None

    def _parse_price_value(self, value):
        if not value:
            return None
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return None

    def _resolve_build_status_label(self, value):
        if not value:
            return ''
        choices = dict(Property.BUILD_STATUS_CHOICES)
        return choices.get(value, '')

    def _get_catalog_deal_label(self, deal_type, language_code='ru'):
        labels = {
            'sale': {'ru': 'Продажа', 'en': 'Sale', 'th': 'ขาย'},
            'rent': {'ru': 'Аренда', 'en': 'Rent', 'th': 'เช่า'},
        }
        return labels.get(deal_type, {}).get(language_code, '')

    def _build_catalog_url(self, base_url, params=None):
        if not params:
            return base_url
        normalized = {key: value for key, value in params.items() if value not in (None, '', [], ())}
        if not normalized:
            return base_url
        return f"{base_url}?{urlencode(normalized, doseq=True)}"

    def _build_catalog_url_from_pairs(self, base_url, params):
        normalized = [
            (key, value)
            for key, value in params
            if value not in (None, '', [], ())
        ]
        if not normalized:
            return base_url
        return f"{base_url}?{urlencode(normalized, doseq=True)}"

    def _get_catalog_base_url(self, context, *, include_route_type=True, include_route_deal=True):
        current_filters = context.get('current_filters', {})
        deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        property_type_obj = self._get_primary_property_type(context)

        if include_route_type and property_type_obj:
            return reverse('properties:property_by_type', args=[property_type_obj.name]), {'property_type'}

        if include_route_deal and deal_type in {'sale', 'rent'}:
            return reverse(f'properties:property_{deal_type}'), {'deal_type'}

        return reverse('properties:property_list'), set()

    def _build_querydict_url(self, base_url, querydict):
        if not querydict:
            return base_url
        query_string = build_query_string(querydict, list(querydict.keys()))
        return f'{base_url}?{query_string}' if query_string else base_url

    def _build_filter_removal_url(self, context, key, value=None):
        include_route_type = True
        include_route_deal = True

        if key == 'property_type':
            include_route_type = False
        elif key == 'deal_type':
            include_route_deal = False

        base_url, route_keys = self._get_catalog_base_url(
            context,
            include_route_type=include_route_type,
            include_route_deal=include_route_deal,
        )

        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        query_params.pop('current_property_type', None)

        if value is None:
            query_params.pop(key, None)
        else:
            remaining_values = [
                current_value for current_value in query_params.getlist(key)
                if str(current_value) != str(value)
            ]
            query_params.pop(key, None)
            if remaining_values:
                query_params.setlist(key, remaining_values)

        for route_key in route_keys:
            query_params.pop(route_key, None)

        return self._build_querydict_url(base_url, query_params)

    def build_active_filters_reset_url(self, context):
        base_url, _route_keys = self._get_catalog_base_url(context)
        return base_url

    def _build_catalog_preserved_query_params(self, exclude_keys=None):
        exclude = {'page', 'current_property_type'}
        if exclude_keys:
            exclude.update(exclude_keys)

        params = []
        for key in self.request.GET.keys():
            if key in exclude:
                continue
            for value in self.request.GET.getlist(key):
                if value in (None, ''):
                    continue
                params.append((key, value))
        return params

    def build_property_type_filter_links(self, context, language_code='ru'):
        if not context.get('current_property_type'):
            return []

        current_filters = context.get('current_filters', {})
        selected_deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        current_property_type = context.get('current_property_type')
        preserved_params = self._build_catalog_preserved_query_params({'property_type'})
        links = []

        all_base_url, all_base_params = self._get_catalog_link_base(
            context,
            deal_type=selected_deal_type,
            property_type_obj=None,
        )
        all_params = list(all_base_params.items()) + preserved_params
        links.append({
            'label': gettext('Все объекты'),
            'url': self._build_catalog_url_from_pairs(all_base_url, all_params),
            'is_active': False,
        })

        for property_type in context.get('property_types', []):
            base_url, base_params = self._get_catalog_link_base(
                context,
                deal_type=selected_deal_type,
                property_type_obj=property_type,
            )
            params = list(base_params.items()) + preserved_params
            links.append({
                'label': _get_translated_attr(
                    property_type,
                    'name_display',
                    language_code,
                    property_type.name_display,
                ),
                'url': self._build_catalog_url_from_pairs(base_url, params),
                'is_active': property_type.name == current_property_type,
            })

        return links

    def build_active_filters_summary(self, chips, language_code='ru'):
        if not chips:
            return ''

        labels = [chip.get('label', '').strip() for chip in chips if chip.get('label')]
        labels = [label for label in labels if label]
        if not labels:
            return ''

        max_items = 3
        summary = ' · '.join(labels[:max_items])
        remaining = len(labels) - max_items
        if remaining > 0:
            summary = f'{summary} · +{remaining}'
        return summary

    def build_active_filter_chips(self, context):
        current_filters = context.get('current_filters', {})
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]
        chips = []

        def get_bedroom_chip_label(value):
            raw_value = str(value)
            if raw_value in {'4', '4+'}:
                return {
                    'ru': '4+ спальни',
                    'en': '4+ bedrooms',
                    'th': '4+ ห้องนอน',
                }.get(language_code, '4+ bedrooms')

            try:
                count = int(raw_value)
            except (TypeError, ValueError):
                return raw_value

            if language_code == 'en':
                return f'{count} bedroom' if count == 1 else f'{count} bedrooms'
            if language_code == 'th':
                return f'{count} ห้องนอน'
            if count == 1:
                return '1 спальня'
            if count in {2, 3, 4}:
                return f'{count} спальни'
            return f'{count} спален'

        property_types_by_name = {
            property_type.name: _get_translated_attr(property_type, 'name_display', language_code, property_type.name)
            for property_type in context.get('property_types', [])
        }
        districts_by_slug = {
            district.slug: _get_translated_attr(district, 'name', language_code, district.slug)
            for district in context.get('districts', [])
        }
        locations_by_slug = {
            location.slug: _get_translated_attr(location, 'name', language_code, location.slug)
            for location in context.get('locations', [])
        }
        amenities_by_id = {
            str(amenity.id): _get_translated_attr(amenity, 'name', language_code, str(amenity.id))
            for amenity in context.get('amenities', [])
        }

        location_obj, district_obj = self._get_location_and_district()
        if district_obj:
            districts_by_slug.setdefault(district_obj.slug, _get_translated_attr(district_obj, 'name', language_code, district_obj.slug))
        if location_obj:
            locations_by_slug.setdefault(location_obj.slug, _get_translated_attr(location_obj, 'name', language_code, location_obj.slug))

        deal_type = context.get('deal_type') or current_filters.get('deal_type')
        deal_label = self._get_catalog_deal_label(deal_type, language_code) if deal_type else ''
        if deal_label:
            chips.append({
                'key': 'deal_type',
                'label': deal_label,
                'remove_url': self._build_filter_removal_url(context, 'deal_type'),
            })

        for property_type in current_filters.get('property_type') or []:
            label = property_types_by_name.get(property_type, property_type)
            chips.append({
                'key': 'property_type',
                'label': label,
                'remove_url': self._build_filter_removal_url(context, 'property_type', property_type),
            })

        district_slug = current_filters.get('district')
        if district_slug:
            chips.append({
                'key': 'district',
                'label': districts_by_slug.get(district_slug, district_slug),
                'remove_url': self._build_filter_removal_url(context, 'district'),
            })

        location_slug = current_filters.get('location')
        if location_slug:
            chips.append({
                'key': 'location',
                'label': locations_by_slug.get(location_slug, location_slug),
                'remove_url': self._build_filter_removal_url(context, 'location'),
            })

        min_price = current_filters.get('min_price')
        if min_price:
            chips.append({
                'key': 'min_price',
                'label': f"{gettext('Минимум')}: {min_price}",
                'remove_url': self._build_filter_removal_url(context, 'min_price'),
            })

        max_price = current_filters.get('max_price')
        if max_price:
            chips.append({
                'key': 'max_price',
                'label': f"{gettext('Максимум')}: {max_price}",
                'remove_url': self._build_filter_removal_url(context, 'max_price'),
            })

        for bedroom in current_filters.get('bedrooms') or []:
            chips.append({
                'key': 'bedrooms',
                'label': get_bedroom_chip_label(bedroom),
                'remove_url': self._build_filter_removal_url(context, 'bedrooms', bedroom),
            })

        build_status_label = self._resolve_build_status_label(current_filters.get('build_status'))
        if build_status_label:
            chips.append({
                'key': 'build_status',
                'label': build_status_label,
                'remove_url': self._build_filter_removal_url(context, 'build_status'),
            })

        for amenity_id in current_filters.get('amenities') or []:
            label = amenities_by_id.get(str(amenity_id), str(amenity_id))
            chips.append({
                'key': 'amenities',
                'label': label,
                'remove_url': self._build_filter_removal_url(context, 'amenities', amenity_id),
            })

        query = (current_filters.get('q') or '').strip()
        if query:
            chips.append({
                'key': 'q',
                'label': f"{gettext('Поиск')}: {query}",
                'remove_url': self._build_filter_removal_url(context, 'q'),
            })

        return chips

    def build_catalog_breadcrumbs(self, context, language_code='ru'):
        breadcrumbs = [{
            'label': gettext('Главная'),
            'url': reverse('core:home'),
        }]

        current_filters = context.get('current_filters', {})
        deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()

        breadcrumbs.append({
            'label': gettext('Недвижимость'),
            'url': reverse('properties:property_list'),
        })

        current_base_url = reverse('properties:property_list')

        if deal_type in {'sale', 'rent'}:
            current_base_url = reverse(f'properties:property_{deal_type}')
            breadcrumbs.append({
                'label': self._get_catalog_deal_label(deal_type, language_code),
                'url': current_base_url,
            })

        if property_type_obj:
            current_base_url = reverse('properties:property_by_type', args=[property_type_obj.name])
            query_params = {}
            if deal_type in {'sale', 'rent'}:
                query_params['deal_type'] = deal_type
            breadcrumbs.append({
                'label': self._get_catalog_subject_label(property_type_obj, language_code),
                'url': self._build_catalog_url(current_base_url, query_params),
            })

        if district_obj:
            district_params = {'district': district_obj.slug}
            if location_obj:
                district_params['location'] = ''
            breadcrumbs.append({
                'label': _get_translated_attr(district_obj, 'name', language_code, district_obj.name),
                'url': self._build_catalog_url(current_base_url, district_params),
            })

        if location_obj:
            breadcrumbs.append({
                'label': _get_translated_attr(location_obj, 'name', language_code, location_obj.name),
                'url': self._build_catalog_url(
                    current_base_url,
                    {'district': location_obj.district.slug, 'location': location_obj.slug},
                ),
            })

        breadcrumbs.append({
            'label': context.get('seo_heading') or _get_catalog_texts(language_code)['heading_fallback'],
            'url': '',
        })

        return breadcrumbs

    def is_indexable_filter_page(self, context):
        if not self.is_base_indexable_filter_page(context):
            return False

        page_number = self._get_catalog_page_number()
        if page_number is None:
            return False

        return True

    def is_base_indexable_filter_page(self, context):
        current_filters = context.get('current_filters', {})
        results_count = context.get('catalog_results_count') or 0
        if results_count <= 0:
            return False

        if self.request.GET.get('map_view') == 'true':
            return False

        if self.request.GET.get('sort') and self.request.GET.get('sort') != '-created_at':
            return False

        for key in self.NON_INDEX_FILTER_KEYS:
            value = current_filters.get(key)
            if isinstance(value, list):
                if any(item not in (None, '') for item in value):
                    return False
            elif value not in (None, ''):
                return False

        property_types = [value for value in current_filters.get('property_type', []) if value]
        if len(property_types) > 1:
            return False

        return self.get_catalog_landing_signature(context) is not None

    def _get_catalog_page_number(self):
        page_param = self.request.GET.get('page')
        if not page_param:
            return 1
        try:
            page_number = int(page_param)
        except (TypeError, ValueError):
            return None
        return page_number if page_number >= 1 else None

    def build_catalog_canonical_url(self, context, *, include_pagination=False):
        current_filters = context.get('current_filters', {})
        deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()

        if property_type_obj:
            base_url = reverse('properties:property_by_type', args=[property_type_obj.name])
            params = {}
            if deal_type in {'sale', 'rent'}:
                params['deal_type'] = deal_type
        elif deal_type in {'sale', 'rent'}:
            base_url = reverse(f'properties:property_{deal_type}')
            params = {}
        else:
            base_url = reverse('properties:property_list')
            params = {}

        if district_obj:
            params['district'] = district_obj.slug
        if location_obj:
            params['district'] = location_obj.district.slug
            params['location'] = location_obj.slug

        page_number = self._get_catalog_page_number()
        if include_pagination and page_number and page_number > 1:
            params['page'] = page_number

        return self.request.build_absolute_uri(self._build_catalog_url(base_url, params))

    def apply_catalog_indexation_strategy(self, context, language_code='ru'):
        base_indexable = self.is_base_indexable_filter_page(context)
        is_indexable = self.is_indexable_filter_page(context)
        canonical_url = self.build_catalog_canonical_url(
            context,
            include_pagination=base_indexable,
        )

        context['meta_robots'] = '' if is_indexable else 'noindex, follow'
        context['canonical_url'] = canonical_url
        context['catalog_is_indexable'] = is_indexable
        context['catalog_base_indexable'] = base_indexable

        self.request.canonical_url_override = canonical_url
        self.request.seo_meta_robots = context['meta_robots']

        return context

    def get_catalog_landing_signature(self, context):
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()
        deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''

        property_type_slug = property_type_obj.name if property_type_obj else ''
        district_slug = district_obj.slug if district_obj else ''
        location_slug = location_obj.slug if location_obj else ''

        return resolve_landing_signature(
            deal_type=deal_type,
            property_type=property_type_slug,
            district=district_slug,
            location=location_slug,
        )

    def _get_catalog_subject_label(self, property_type_obj, language_code='ru'):
        if not property_type_obj:
            return _get_catalog_texts(language_code)['subject_fallback']
        mapped_label = PROPERTY_TYPE_NAV_LABELS.get(property_type_obj.name, {}).get(language_code)
        if mapped_label:
            return mapped_label
        return _get_translated_attr(property_type_obj, 'name_display', language_code, property_type_obj.name_display)

    def _get_catalog_deal_phrase(self, deal_type, language_code='ru'):
        texts = _get_catalog_texts(language_code)
        if deal_type == 'sale':
            return texts['deal_sale']
        if deal_type == 'rent':
            return texts['deal_rent']
        return ''

    def _get_catalog_geo_phrase(self, location_obj, district_obj, language_code='ru'):
        texts = _get_catalog_texts(language_code)
        if location_obj:
            return texts['geo_location'] % {'location': _get_translated_attr(location_obj, 'name', language_code, location_obj.name)}
        if district_obj:
            return texts['geo_district'] % {'district': _get_translated_attr(district_obj, 'name', language_code, district_obj.name)}
        return texts['geo_fallback']

    def _format_catalog_budget_text(self, min_price, max_price, currency_code, language_code='ru'):
        texts = _get_catalog_texts(language_code)
        formatted_min = CurrencyService.format_price(min_price, currency_code) if min_price else None
        formatted_max = CurrencyService.format_price(max_price, currency_code) if max_price else None
        if formatted_min and formatted_max:
            return f'{formatted_min} - {formatted_max}'
        return formatted_min or formatted_max or ''

    def _get_catalog_bedrooms_phrase(self, bedrooms, language_code='ru', *, with_preposition=False):
        if not bedrooms or len(bedrooms) != 1:
            return ''

        value = bedrooms[0]
        texts = _get_catalog_texts(language_code)
        if value == '4+':
            base_value = texts['bedroom_plus'] % {'count': 4}
            if language_code == 'ru' and with_preposition:
                return f'с {base_value}'
            return base_value

        try:
            count = int(value)
        except (TypeError, ValueError):
            return ''

        if language_code == 'en':
            key = 'bedroom_single' if count == 1 else 'bedroom_plural'
            return texts[key] % {'count': count}
        if language_code == 'th':
            return texts['bedroom_single'] % {'count': count}
        key = 'bedroom_single' if count == 1 else 'bedroom_plural'
        base_value = texts[key] % {'count': count}
        if with_preposition:
            return f'с {base_value}'
        return base_value

    def build_generated_catalog_seo(self, context, language_code='ru'):
        texts = _get_catalog_texts(language_code)
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()
        results_count = context.get('catalog_results_count') or 0

        if not self.is_base_indexable_filter_page(context):
            return {
                'has_content': False,
                'heading': texts['intro_heading'],
                'intro': '',
                'highlights': [],
                'follow_up': '',
            }

        subject = self._get_catalog_subject_label(property_type_obj, language_code)
        deal_phrase = self._get_catalog_deal_phrase(current_filters.get('deal_type') or context.get('deal_type'), language_code)
        geo_phrase = self._get_catalog_geo_phrase(location_obj, district_obj, language_code)
        bedrooms_phrase = self._get_catalog_bedrooms_phrase(current_filters.get('bedrooms') or [], language_code)
        build_status_label = self._resolve_build_status_label(current_filters.get('build_status'))
        budget_text = self._format_catalog_budget_text(
            self._parse_price_value(current_filters.get('min_price')),
            self._parse_price_value(current_filters.get('max_price')),
            CurrencyService.get_selected_currency_code(self.request),
            language_code,
        )

        intro = texts['intro_template'] % {
            'subject': subject,
            'deal': f' {deal_phrase}' if deal_phrase else '',
            'geo': f' {geo_phrase}' if geo_phrase else '',
            'count': results_count,
        }

        highlights = []
        if budget_text:
            highlights.append(texts['budget_sentence'] % {'budget': budget_text})
        if bedrooms_phrase:
            highlights.append(texts['bedrooms_sentence'] % {'bedrooms': bedrooms_phrase})
        if build_status_label:
            highlights.append(texts['stage_sentence'] % {'status': build_status_label})

        return {
            'has_content': bool(results_count > 0 and (intro or highlights)),
            'heading': texts['intro_heading'],
            'intro': intro,
            'highlights': highlights,
            'follow_up': texts['follow_up'],
        }

    def build_catalog_faq(self, context, language_code='ru'):
        texts = _get_catalog_texts(language_code)
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()
        subject = self._get_catalog_subject_label(property_type_obj, language_code)
        deal_phrase = self._get_catalog_deal_phrase(current_filters.get('deal_type') or context.get('deal_type'), language_code)
        geo_phrase = self._get_catalog_geo_phrase(location_obj, district_obj, language_code)
        results_count = context.get('catalog_results_count') or 0
        budget_text = self._format_catalog_budget_text(
            self._parse_price_value(current_filters.get('min_price')),
            self._parse_price_value(current_filters.get('max_price')),
            CurrencyService.get_selected_currency_code(self.request),
            language_code,
        )
        bedrooms_phrase = self._get_catalog_bedrooms_phrase(current_filters.get('bedrooms') or [], language_code)
        build_status_label = self._resolve_build_status_label(current_filters.get('build_status'))

        if results_count <= 0 or not self.is_base_indexable_filter_page(context):
            return {
                'has_items': False,
                'heading': texts['faq_heading'],
                'entries': [],
            }

        entries = [{
            'question': texts['faq_count_q'],
            'answer': texts['faq_count_a'] % {'count': results_count},
        }]

        entries.append({
            'question': texts['faq_geo_q'],
            'answer': texts['faq_geo_a'] % {
                'subject': subject,
                'deal': f' {deal_phrase}' if deal_phrase else '',
                'geo': f' {geo_phrase}' if geo_phrase else '',
            },
        })

        if budget_text:
            entries.append({
                'question': texts['faq_budget_q'],
                'answer': texts['faq_budget_a'] % {'budget': budget_text},
            })

        if bedrooms_phrase:
            entries.append({
                'question': texts['faq_bedrooms_q'],
                'answer': texts['faq_bedrooms_a'] % {'bedrooms': bedrooms_phrase},
            })

        if build_status_label:
            entries.append({
                'question': texts['faq_stage_q'],
                'answer': texts['faq_stage_a'] % {'status': build_status_label},
            })

        return {
            'has_items': bool(entries),
            'heading': texts['faq_heading'],
            'entries': entries[:5],
        }

    def _get_catalog_link_base(self, context, deal_type=None, property_type_obj=None):
        resolved_deal_type = deal_type if deal_type is not None else (context.get('deal_type') or context.get('current_filters', {}).get('deal_type') or '')
        resolved_property_type = property_type_obj if property_type_obj is not None else self._get_primary_property_type(context)

        if resolved_property_type:
            base_url = reverse('properties:property_by_type', args=[resolved_property_type.name])
            params = {}
            if resolved_deal_type in {'sale', 'rent'}:
                params['deal_type'] = resolved_deal_type
            return base_url, params

        if resolved_deal_type in {'sale', 'rent'}:
            return reverse(f'properties:property_{resolved_deal_type}'), {}

        return reverse('properties:property_list'), {}

    def _build_catalog_suggestion_queryset(self, *, deal_type='', property_type_obj=None, district_obj=None, location_obj=None):
        queryset = Property.objects.filter(
            is_active=True,
            status='available',
        )

        if deal_type in {'sale', 'rent'}:
            queryset = queryset.filter(deal_type__in=[deal_type, 'both'])

        if property_type_obj:
            queryset = queryset.filter(property_type=property_type_obj)

        if district_obj:
            queryset = queryset.filter(district=district_obj)

        if location_obj:
            queryset = queryset.filter(location=location_obj)

        return queryset

    def _build_related_deal_link_label(self, property_type_obj, deal_type, language_code='ru'):
        if deal_type == 'all':
            return {
                'ru': gettext('Все объекты'),
                'en': 'All properties',
                'th': 'อสังหาริมทรัพย์ทั้งหมด',
            }.get(language_code, gettext('Все объекты'))

        subject = self._get_catalog_subject_label(property_type_obj, language_code) if property_type_obj else ''
        if not subject:
            return self._get_catalog_deal_label(deal_type, language_code)

        deal_phrase = self._get_catalog_deal_phrase(deal_type, language_code)
        if language_code == 'en':
            return f'{subject} {deal_phrase}'.strip()
        if language_code == 'th':
            return f'{subject} {deal_phrase}'.strip()
        return f'{subject} {deal_phrase}'.strip()

    def _build_no_results_district_links(self, context, language_code='ru'):
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        selected_deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        location_obj, district_obj = self._get_location_and_district()
        queryset = self._build_catalog_suggestion_queryset(
            deal_type=selected_deal_type,
            property_type_obj=property_type_obj,
        )

        rows = (
            queryset.values('district__slug')
            .annotate(property_count=Count('id'))
            .order_by('-property_count', 'district__slug')
        )

        district_map = District.objects.in_bulk(
            [row['district__slug'] for row in rows if row.get('district__slug')],
            field_name='slug',
        )
        links = []
        for row in rows:
            slug = row.get('district__slug')
            if not slug:
                continue
            if district_obj and slug == district_obj.slug:
                continue
            item = district_map.get(slug)
            if not item:
                continue

            base_url, params = self._get_catalog_link_base(
                context,
                deal_type=selected_deal_type,
                property_type_obj=property_type_obj,
            )
            params['district'] = slug
            links.append({
                'label': _get_translated_attr(item, 'name', language_code, item.name),
                'url': self._build_catalog_url(base_url, params),
                'count': row['property_count'],
            })

        return links[:4]

    def _build_no_results_type_links(self, context, language_code='ru'):
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        selected_deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        location_obj, district_obj = self._get_location_and_district()
        queryset = self._build_catalog_suggestion_queryset(
            deal_type=selected_deal_type,
            district_obj=district_obj,
            location_obj=location_obj,
        )

        rows = (
            queryset.values('property_type__name')
            .annotate(property_count=Count('id'))
            .order_by('-property_count', 'property_type__name')
        )

        property_type_map = PropertyType.objects.in_bulk(
            [row['property_type__name'] for row in rows if row.get('property_type__name')],
            field_name='name',
        )
        links = []
        for row in rows:
            slug = row.get('property_type__name')
            if not slug:
                continue
            if property_type_obj and slug == property_type_obj.name:
                continue
            item = property_type_map.get(slug)
            if not item:
                continue

            base_url, params = self._get_catalog_link_base(
                context,
                deal_type=selected_deal_type,
                property_type_obj=item,
            )
            if district_obj:
                params['district'] = district_obj.slug
            if location_obj:
                params['district'] = location_obj.district.slug
                params['location'] = location_obj.slug
            links.append({
                'label': self._get_catalog_subject_label(item, language_code),
                'url': self._build_catalog_url(base_url, params),
                'count': row['property_count'],
            })

        return links[:4]

    def _build_no_results_deal_links(self, context, language_code='ru'):
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()
        selected_deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        options = ['sale', 'rent', 'all']
        links = []

        for option in options:
            if option == selected_deal_type:
                continue

            option_deal_type = '' if option == 'all' else option
            queryset = self._build_catalog_suggestion_queryset(
                deal_type=option_deal_type,
                property_type_obj=property_type_obj,
                district_obj=district_obj,
                location_obj=location_obj,
            )
            count = queryset.count()
            if count <= 0:
                continue

            base_url, params = self._get_catalog_link_base(
                context,
                deal_type=option_deal_type,
                property_type_obj=property_type_obj,
            )
            if district_obj:
                params['district'] = district_obj.slug
            if location_obj:
                params['district'] = location_obj.district.slug
                params['location'] = location_obj.slug

            links.append({
                'label': self._build_related_deal_link_label(property_type_obj, option, language_code),
                'url': self._build_catalog_url(base_url, params),
                'count': count,
            })

        return links[:3]

    def build_catalog_internal_links(self, context, language_code='ru'):
        current_filters = context.get('current_filters', {})
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()
        selected_deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''

        type_links = []
        base_query = Q(property__is_active=True, property__status='available')
        property_types = (
            PropertyType.objects
            .annotate(property_count=Count('property', filter=base_query))
            .filter(property_count__gt=0)
            .order_by('-property_count', 'name_display')[:4]
        )

        for item in property_types:
            if property_type_obj and item.id == property_type_obj.id:
                continue
            base_url, params = self._get_catalog_link_base(context, deal_type=selected_deal_type, property_type_obj=item)
            if district_obj:
                params['district'] = district_obj.slug
            if location_obj:
                params['district'] = location_obj.district.slug
                params['location'] = location_obj.slug
            type_links.append({
                'label': self._get_catalog_subject_label(item, language_code),
                'url': self._build_catalog_url(base_url, params),
                'count': item.property_count,
            })

        district_links = []
        district_queryset = (
            District.objects
            .annotate(property_count=Count('property', filter=base_query))
            .filter(property_count__gt=0)
            .order_by('-property_count', 'name')[:6]
        )
        base_url, base_params = self._get_catalog_link_base(context, deal_type=selected_deal_type, property_type_obj=property_type_obj)
        for item in district_queryset:
            if district_obj and item.id == district_obj.id:
                continue
            params = dict(base_params)
            params['district'] = item.slug
            district_links.append({
                'label': _get_translated_attr(item, 'name', language_code, item.name),
                'url': self._build_catalog_url(base_url, params),
                'count': item.property_count,
            })

        return {
            'has_content': bool(type_links or district_links),
            'type_heading': _get_catalog_texts(language_code)['popular_types_heading'],
            'district_heading': _get_catalog_texts(language_code)['popular_districts_heading'],
            'type_links': type_links[:4],
            'district_links': district_links[:6],
        }

    def build_no_results_recovery(self, context, language_code='ru'):
        current_filters = context.get('current_filters', {})
        base_url, base_params = self._get_catalog_link_base(
            context,
            deal_type=context.get('deal_type') or current_filters.get('deal_type') or '',
            property_type_obj=self._get_primary_property_type(context),
        )

        def make_url(params):
            return self._build_catalog_url(base_url, params)

        actions = []
        if current_filters.get('min_price') or current_filters.get('max_price'):
            params = dict(base_params)
            if current_filters.get('district'):
                params['district'] = current_filters['district']
            if current_filters.get('location'):
                params['location'] = current_filters['location']
            actions.append({
                'label': gettext('Убрать ограничение по бюджету'),
                'url': make_url(params),
            })

        if current_filters.get('bedrooms'):
            params = dict(base_params)
            if current_filters.get('district'):
                params['district'] = current_filters['district']
            if current_filters.get('location'):
                params['location'] = current_filters['location']
            if current_filters.get('min_price'):
                params['min_price'] = current_filters['min_price']
            if current_filters.get('max_price'):
                params['max_price'] = current_filters['max_price']
            actions.append({
                'label': gettext('Убрать фильтр по спальням'),
                'url': make_url(params),
            })

        if current_filters.get('amenities'):
            params = dict(base_params)
            for key in ('district', 'location', 'min_price', 'max_price', 'build_status'):
                value = current_filters.get(key)
                if value:
                    params[key] = value
            actions.append({
                'label': gettext('Убрать фильтр по удобствам'),
                'url': make_url(params),
            })

        if current_filters.get('build_status'):
            params = dict(base_params)
            for key in ('district', 'location', 'min_price', 'max_price'):
                value = current_filters.get(key)
                if value:
                    params[key] = value
            actions.append({
                'label': gettext('Показать все стадии готовности'),
                'url': make_url(params),
            })

        if current_filters.get('location'):
            params = dict(base_params)
            if current_filters.get('district'):
                params['district'] = current_filters['district']
            actions.append({
                'label': gettext('Расширить поиск до всего района'),
                'url': make_url(params),
            })

        if current_filters.get('q'):
            params = dict(base_params)
            for key in ('district', 'location', 'min_price', 'max_price'):
                value = current_filters.get(key)
                if value:
                    params[key] = value
            actions.append({
                'label': gettext('Убрать поисковый запрос'),
                'url': make_url(params),
            })

        seen_urls = set()
        deduped_actions = []
        for action in actions:
            if action['url'] in seen_urls:
                continue
            seen_urls.add(action['url'])
            deduped_actions.append(action)

        reset_section_url = make_url(base_params)
        reset_all_url = reverse('properties:property_list')
        district_links = self._build_no_results_district_links(context, language_code)
        type_links = self._build_no_results_type_links(context, language_code)
        deal_links = self._build_no_results_deal_links(context, language_code)

        seen_related_urls = {reset_section_url, reset_all_url}

        def dedupe_links(links):
            cleaned = []
            for link in links:
                if link['url'] in seen_related_urls:
                    continue
                seen_related_urls.add(link['url'])
                cleaned.append(link)
            return cleaned

        district_links = dedupe_links(district_links)
        type_links = dedupe_links(type_links)
        deal_links = dedupe_links(deal_links)

        return {
            'has_content': bool(deduped_actions or district_links or type_links or deal_links),
            'reset_section_url': reset_section_url,
            'reset_all_url': reset_all_url,
            'actions': deduped_actions[:4],
            'district_heading': gettext('Соседние районы'),
            'type_heading': gettext('Похожие типы недвижимости'),
            'deal_heading': gettext('Похожие разделы продажи и аренды'),
            'district_links': district_links[:4],
            'type_links': type_links[:4],
            'deal_links': deal_links[:3],
        }

    def get_seo_block_candidates(self, context):
        """Список возможных slug для SEO-блоков по убыванию специфичности."""
        signature = self.get_catalog_landing_signature(context)
        if not signature:
            return ['properties_catalog']
        return build_candidate_slugs(signature)


class PropertySaleView(DealTypeRedirectMixin, PropertyListView):
    template_name = 'properties/list.html'
    forced_deal_type = 'sale'
    deal_type_redirects = {
        'rent': 'properties:property_rent',
        '': 'properties:property_list',
    }

    def get_queryset(self):
        queryset = super().get_queryset().filter(deal_type__in=['sale', 'both'])

        sort_by = self.request.GET.get('sort')
        if sort_by in (None, '', '-created_at'):
            priority_case = Case(
                *[
                    When(property_type__name=property_type, then=Value(index))
                    for index, property_type in enumerate(self.PROPERTY_TYPE_PRIORITY)
                ],
                default=Value(len(self.PROPERTY_TYPE_PRIORITY)),
                output_field=IntegerField(),
            )
            ordering = []
            if not self.has_active_filters():
                ordering.extend(['-featured_priority', '-is_featured'])
            ordering.extend(['_type_priority', '-created_at'])

            queryset = queryset.annotate(_type_priority=priority_case).order_by(*ordering)

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deal_type'] = 'sale'
        if not self.request.GET.get('deal_type'):
            context['current_filters']['deal_type'] = 'sale'
        context['seo_heading'] = self.build_seo_heading(context)
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]
        context['generated_catalog_seo'] = self.build_generated_catalog_seo(context, language_code)
        context['catalog_seo_block'] = self.get_catalog_seo_block(context)
        context['catalog_faq'] = self.build_catalog_faq(context, language_code)
        context['catalog_breadcrumbs'] = self.build_catalog_breadcrumbs(context, language_code)
        context['property_type_filter_links'] = self.build_property_type_filter_links(context, language_code)
        context['active_filter_chips'] = self.build_active_filter_chips(context)
        context['active_filters_summary'] = self.build_active_filters_summary(context['active_filter_chips'], language_code)
        context['active_filters_reset_url'] = self.build_active_filters_reset_url(context)
        context['catalog_internal_links'] = self.build_catalog_internal_links(context, language_code)
        context['no_results_recovery'] = self.build_no_results_recovery(context, language_code)
        self.apply_catalog_indexation_strategy(context, language_code)
        self.update_page_meta(context)
        return context


class PropertyRentView(DealTypeRedirectMixin, PropertyListView):
    template_name = 'properties/list.html'
    forced_deal_type = 'rent'
    deal_type_redirects = {
        'sale': 'properties:property_sale',
        '': 'properties:property_list',
    }

    def get_queryset(self):
        return super().get_queryset().filter(deal_type__in=['rent', 'both'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deal_type'] = 'rent'
        if not self.request.GET.get('deal_type'):
            context['current_filters']['deal_type'] = 'rent'
        context['seo_heading'] = self.build_seo_heading(context)
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]
        context['generated_catalog_seo'] = self.build_generated_catalog_seo(context, language_code)
        context['catalog_seo_block'] = self.get_catalog_seo_block(context)
        context['catalog_faq'] = self.build_catalog_faq(context, language_code)
        context['catalog_breadcrumbs'] = self.build_catalog_breadcrumbs(context, language_code)
        context['property_type_filter_links'] = self.build_property_type_filter_links(context, language_code)
        context['active_filter_chips'] = self.build_active_filter_chips(context)
        context['active_filters_summary'] = self.build_active_filters_summary(context['active_filter_chips'], language_code)
        context['active_filters_reset_url'] = self.build_active_filters_reset_url(context)
        context['catalog_internal_links'] = self.build_catalog_internal_links(context, language_code)
        context['no_results_recovery'] = self.build_no_results_recovery(context, language_code)
        self.apply_catalog_indexation_strategy(context, language_code)
        self.update_page_meta(context)
        return context


class PropertyByTypeView(PropertyListView):
    template_name = 'properties/list.html'

    def dispatch(self, request, *args, **kwargs):
        redirect_response = self._maybe_redirect_by_property_type(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def _maybe_redirect_by_property_type(self, request):
        selected_types = request.GET.getlist('property_type')
        if not selected_types:
            return None

        valid_types = set(
            PropertyType.objects.filter(name__in=selected_types).values_list('name', flat=True)
        )
        if not valid_types:
            return None

        ordered_selected = [type_name for type_name in selected_types if type_name in valid_types]
        if not ordered_selected:
            return None

        resolver_kwargs = request.resolver_match.kwargs if request.resolver_match else {}
        current_type = resolver_kwargs.get('type_name', self.kwargs.get('type_name'))

        if len(ordered_selected) == 1 and ordered_selected[0] == current_type:
            return None

        if current_type in valid_types:
            alternative_types = [type_name for type_name in ordered_selected if type_name != current_type]
            if not alternative_types:
                return None
            target_type = alternative_types[-1]
        else:
            target_type = ordered_selected[-1]

        query_params = request.GET.copy()
        for key in ('property_type', 'current_property_type'):
            if key in query_params:
                query_params.pop(key)

        target_url = reverse('properties:property_by_type', args=[target_type])
        query_string = query_params.urlencode()
        if query_string:
            target_url = f"{target_url}?{query_string}"

        return HttpResponseRedirect(target_url)

    def get_queryset(self):
        type_name = self.kwargs['type_name']
        
        # Проверяем существование типа недвижимости
        try:
            self.property_type = PropertyType.objects.get(name=type_name)
        except PropertyType.DoesNotExist:
            raise Http404(f"Property type '{type_name}' not found")
        
        return super().get_queryset().filter(property_type=self.property_type)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['property_type'] = self.property_type
        context['current_property_type'] = self.property_type.name
        context['current_filters']['property_type'] = [self.property_type.name]
        context['seo_heading'] = self.build_seo_heading(context)
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]
        context['generated_catalog_seo'] = self.build_generated_catalog_seo(context, language_code)
        context['catalog_seo_block'] = self.get_catalog_seo_block(context)
        context['catalog_faq'] = self.build_catalog_faq(context, language_code)
        context['catalog_breadcrumbs'] = self.build_catalog_breadcrumbs(context, language_code)
        context['property_type_filter_links'] = self.build_property_type_filter_links(context, language_code)
        context['active_filter_chips'] = self.build_active_filter_chips(context)
        context['active_filters_summary'] = self.build_active_filters_summary(context['active_filter_chips'], language_code)
        context['active_filters_reset_url'] = self.build_active_filters_reset_url(context)
        context['catalog_internal_links'] = self.build_catalog_internal_links(context, language_code)
        context['no_results_recovery'] = self.build_no_results_recovery(context, language_code)
        self.apply_catalog_indexation_strategy(context, language_code)
        self.update_page_meta(context)
        return context


class PropertyDetailView(DetailView):
    model = Property
    template_name = 'properties/detail.html'
    context_object_name = 'property'

    def get_queryset(self):
        # Возвращаем ВСЕ объекты, не фильтруем по is_active здесь
        return Property.objects.select_related(
            'district', 'location', 'property_type', 'developer'
        ).prefetch_related('images', 'features__feature')

    def get_object(self):
        try:
            obj = super().get_object()
        except Http404:
            # Если объект не найден вообще, возвращаем 404
            raise Http404("Недвижимость не найдена")
        
        # Увеличиваем счетчик просмотров только для активных объектов
        if obj.is_active:
            obj.views_count += 1
            obj.save(update_fields=['views_count'])
        
        return obj
    
    def handle_inactive_property(self, property_obj):
        """
        Обрабатывает неактивную недвижимость и определяет куда редиректить
        Приоритет редиректов:
        1. Тип недвижимости + район + тип сделки
        2. Тип недвижимости + тип сделки  
        3. Тип недвижимости
        4. Главная страница недвижимости
        """
        redirect_url = None
        
        # 1. Пытаемся редиректить на тип недвижимости + тип сделки
        if property_obj.property_type and property_obj.deal_type:
            # Формируем URL вида /properties/sale/ или /properties/rent/
            if property_obj.deal_type in ['sale', 'both']:
                redirect_url = reverse('properties:property_sale')
            elif property_obj.deal_type == 'rent':
                redirect_url = reverse('properties:property_rent')
            
            # Добавляем фильтры в query params
            if redirect_url:
                params = []
                # Добавляем тип недвижимости
                params.append(f'property_type={property_obj.property_type.name}')
                # Добавляем район если есть
                if property_obj.district:
                    params.append(f'district={property_obj.district.slug}')
                
                if params:
                    redirect_url = f"{redirect_url}?{'&'.join(params)}"
        
        # 2. Fallback: редиректим на общий список недвижимости
        if not redirect_url:
            redirect_url = reverse('properties:property_list')
            if property_obj.property_type:
                redirect_url = f"{redirect_url}?property_type={property_obj.property_type.name}"
        
        # 3. Финальный fallback: главная страница недвижимости
        if not redirect_url:
            redirect_url = reverse('properties:property_list')
        
        # Выполняем 301 редирект
        from django.http import HttpResponsePermanentRedirect
        return HttpResponsePermanentRedirect(redirect_url)
    
    def get(self, request, *args, **kwargs):
        """Переопределяем get метод для обработки редиректов"""
        slug = kwargs.get('slug')
        try:
            self.object = self.get_object()
        except Http404:
            legacy_redirect = self._maybe_redirect_legacy_slug(slug)
            if legacy_redirect:
                return legacy_redirect
            raise
        
        # Если объект найден, но неактивен - делаем редирект
        if not self.object.is_active:
            return self.handle_inactive_property(self.object)
        
        # Иначе продолжаем как обычно
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')

        # Похожие объекты с приоритетом по локации
        similar_properties = self.get_similar_properties()
        for similar_property in similar_properties:
            _annotate_property_labels(similar_property, language_code)
        context['similar_properties'] = similar_properties

        # Favorite functionality removed
        context['is_favorite'] = False

        main_image_url = self.object.get_main_image_absolute_url(self.request)
        if main_image_url:
            context['og_image_url'] = main_image_url

        amp_url = self.request.build_absolute_uri(
            reverse('properties:property_detail_amp', kwargs={'slug': self.object.slug})
        )
        context['amp_url'] = amp_url
        context['property_title_display'] = _normalize_whitespace(self.object.title)
        context['property_image_alt_base'] = self.object.get_seo_image_alt_base(language_code)
        context['property_seo_section'] = self.object.get_detail_seo_section(language_code)
        context['property_faq'] = self.object.get_detail_faq_items(language_code)
        context['property_type_nav_label'] = _get_property_type_nav_label(self.object, language_code)
        context['property_catalog_type_url'] = _get_property_catalog_type_url(self.object)
        context.update(_build_property_location_context(self.object, language_code))

        return context

    def _maybe_redirect_legacy_slug(self, slug):
        """Проверяем, нужно ли перенаправить запрос со старого slug на актуальный."""
        if not slug:
            return None

        target_slug = LEGACY_PROPERTY_SLUG_REDIRECTS.get(slug)
        if not target_slug:
            return None

        target_url = reverse('properties:property_detail', kwargs={'slug': target_slug})
        return HttpResponsePermanentRedirect(target_url)
    
    def get_similar_properties(self):
        """
        Получает похожие объекты с приоритетом по локации и типу недвижимости
        Приоритет:
        1. Тот же тип + та же конкретная локация (location)
        2. Тот же тип + тот же район (district) 
        3. Тот же тип + любая локация
        """
        base_filter = {
            'property_type': self.object.property_type,
            'is_active': True,
            'status': 'available'
        }
        
        similar_properties = []
        
        # 1. Приоритет: та же конкретная локация (если есть)
        if self.object.location:
            same_location = Property.objects.filter(
                location=self.object.location,
                **base_filter
            ).exclude(id=self.object.id).select_related(
                'district', 'location', 'property_type'
            ).prefetch_related('images')[:2]
            
            similar_properties.extend(same_location)
        
        # 2. Тот же район (но другая локация или без локации)
        if len(similar_properties) < 4:
            same_district = Property.objects.filter(
                district=self.object.district,
                **base_filter
            ).exclude(id=self.object.id)
            
            # Исключаем уже добавленные объекты
            if similar_properties:
                same_district = same_district.exclude(
                    id__in=[prop.id for prop in similar_properties]
                )
            
            same_district = same_district.select_related(
                'district', 'location', 'property_type'
            ).prefetch_related('images')[:(4 - len(similar_properties))]
            
            similar_properties.extend(same_district)
        
        # 3. Тот же тип недвижимости (любая локация)
        if len(similar_properties) < 4:
            same_type = Property.objects.filter(
                **base_filter
            ).exclude(id=self.object.id)
            
            # Исключаем уже добавленные объекты
            if similar_properties:
                same_type = same_type.exclude(
                    id__in=[prop.id for prop in similar_properties]
                )
            
            same_type = same_type.select_related(
                'district', 'location', 'property_type'
            ).prefetch_related('images')[:(4 - len(similar_properties))]
            
            similar_properties.extend(same_type)
        
        return similar_properties[:4]


@require_POST
def toggle_favorite(request):
    # Функция избранного отключена - используется LocalStorage
    return JsonResponse({'success': False, 'message': 'Функция избранного отключена'})

def favorites_view(request):
    """Страница избранного"""
    return render(request, 'properties/favorites.html')
def _build_property_stats(property_obj):
    stats = []
    if property_obj.bedrooms:
        stats.append({'label': gettext('Спальни'), 'value': property_obj.bedrooms})
    if property_obj.bathrooms:
        stats.append({'label': gettext('Ванные'), 'value': property_obj.bathrooms})
    if property_obj.area_total:
        stats.append({'label': gettext('Площадь'), 'value': f"{property_obj.area_total} m²"})
    if property_obj.area_land:
        stats.append({'label': gettext('Участок'), 'value': f"{property_obj.area_land} m²"})
    if property_obj.floors_total:
        stats.append({'label': gettext('Этажей'), 'value': property_obj.floors_total})
    return stats


def _build_final_price(property_obj):
    if property_obj.deal_type == 'rent' and property_obj.price_rent_monthly_thb:
        return property_obj.price_rent_monthly_thb
    return property_obj.price_sale_thb or property_obj.price_rent_monthly_thb or 0


def property_detail_amp(request, slug):
    queryset = Property.objects.select_related(
        'district', 'location', 'property_type', 'developer'
    ).prefetch_related('images', 'features__feature')

    property_obj = get_object_or_404(queryset, slug=slug)

    detail_view = PropertyDetailView()
    detail_view.request = request

    if not property_obj.is_active:
        return detail_view.handle_inactive_property(property_obj)

    detail_view.object = property_obj
    similar_properties = detail_view.get_similar_properties()
    language_code = getattr(request, 'LANGUAGE_CODE', 'ru')
    for similar_property in similar_properties:
        _annotate_property_labels(similar_property, language_code)

    canonical_url = request.build_absolute_uri(property_obj.get_absolute_url())
    property_title_display = _normalize_whitespace(property_obj.title)
    seo_data = property_obj.get_seo_data(language_code)
    meta_title = seo_data.get('title') or f"{property_title_display} – Undersun Estate"
    raw_description = seo_data.get('description') or property_obj.short_description or strip_tags(property_obj.description)
    meta_description = truncate_meta(raw_description)

    gallery_images = []
    for index, image in enumerate(property_obj.images.all(), start=1):
        image_url = image.medium_url or image.thumbnail_url or image.original_url
        if not image_url:
            continue
        gallery_images.append({
            'url': image_url,
            'alt': property_obj.get_seo_image_alt(image=image, language_code=language_code, position=index),
        })

    if not gallery_images:
        gallery_images.append({
            'url': static('images/no-image.svg'),
            'alt': property_obj.get_seo_image_alt(language_code=language_code),
        })

    amenities = [relation.feature.name for relation in property_obj.features.all() if relation.feature]
    stats = _build_property_stats(property_obj)
    location_context = _build_property_location_context(property_obj, language_code)
    location_label = location_context['property_full_location_label']

    whatsapp_message = gettext('Здравствуйте! Меня интересует объект {title} ({url})').format(
        title=property_title_display,
        url=canonical_url,
    )
    whatsapp_url = f"https://wa.me/66633033133?text={quote_plus(whatsapp_message)}"
    contact_phone = '+66633033133'

    final_price = _build_final_price(property_obj)

    metrika_counter_id = getattr(settings, 'METRIKA_COUNTER_ID', 90630603)
    property_type_value = property_obj.property_type.name if property_obj.property_type else ''
    district_slug = property_obj.district.slug if property_obj.district else ''
    ya_params = {
        'property_id': property_obj.id,
        'slug': property_obj.slug,
        'deal_type': property_obj.deal_type,
        'property_type': property_type_value,
        'district': district_slug,
        'language': getattr(request, 'LANGUAGE_CODE', 'ru'),
        'is_amp': True,
    }

    context = {
        'property': property_obj,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'canonical_url': canonical_url,
        'gallery_images': gallery_images,
        'location_label': location_label,
        'property_title_display': property_title_display,
        'property_image_alt_base': property_obj.get_seo_image_alt_base(language_code),
        'property_seo_section': property_obj.get_detail_seo_section(language_code),
        'property_faq': property_obj.get_detail_faq_items(language_code),
        'stats': stats,
        'amenities': amenities,
        'price_display': property_obj.price_display,
        'contact_phone': contact_phone,
        'whatsapp_url': whatsapp_url,
        'similar_properties': similar_properties,
        'amp_description': convert_html_to_amp(property_obj.description),
        'final_price': final_price,
        'status_label': property_obj.get_status_display(),
        'deal_type_label': property_obj.get_deal_type_display(),
        'developer_name': property_obj.developer.name if property_obj.developer else '',
        'metrika_counter_id': metrika_counter_id,
        'amp_metrika_params': json.dumps(ya_params, ensure_ascii=False),
    }
    context.update(location_context)

    return render(request, 'properties/property_detail_amp.html', context)


@require_http_methods(["GET", "POST"])
def get_favorite_properties(request):
    """AJAX endpoint для получения данных избранных объектов"""
    if request.method == 'POST':
        property_ids = request.POST.getlist('property_ids[]') or request.POST.getlist('property_ids')
    else:
        property_ids = request.GET.getlist('property_ids[]') or request.GET.getlist('property_ids')

    # Поддержка передачи ID одной строкой через запятую
    if len(property_ids) == 1 and ',' in property_ids[0]:
        property_ids = [item.strip() for item in property_ids[0].split(',') if item.strip()]

    if not property_ids:
        return JsonResponse({'success': False, 'message': 'Не переданы ID объектов'})
    
    try:
        # Преобразуем в integers
        ids = [int(id) for id in property_ids if id.isdigit()]
        
        # Получаем объекты
        properties = Property.objects.filter(id__in=ids).select_related(
            'district', 'property_type'
        ).prefetch_related('images')
        
        # Получаем выбранную валюту из сессии
        selected_currency_code = request.session.get('currency')
        if not selected_currency_code:
            # Определяем валюту по языку
            language = getattr(request, 'LANGUAGE_CODE', 'ru')
            default_currency = CurrencyService.get_currency_for_language(language)
            selected_currency_code = default_currency.code if default_currency else 'USD'

        user_currency = CurrencyService.get_currency_by_code(selected_currency_code)
        if not user_currency:
            user_currency = CurrencyService.get_currency_by_code('USD')

        # Формируем данные для ответа
        properties_data = []
        for prop in properties:
            main_image_url = ''
            if prop.main_image:
                main_image_url = prop.main_image.thumbnail_url

            # Формируем цену для отображения с учетом выбранной валюты
            price_display = 'Цена по запросу'

            # Определяем исходную цену и валюту
            source_price = None
            source_currency = None

            if prop.deal_type == 'rent':
                # Проверяем цены аренды в разных валютах
                if prop.price_rent_monthly:
                    source_price = float(prop.price_rent_monthly)
                    source_currency = 'USD'
                elif prop.price_rent_monthly_thb:
                    source_price = float(prop.price_rent_monthly_thb)
                    source_currency = 'THB'
                elif prop.price_rent_monthly_rub:
                    source_price = float(prop.price_rent_monthly_rub)
                    source_currency = 'RUB'
            elif prop.deal_type in ['sale', 'both']:
                # Проверяем цены продажи в разных валютах
                if prop.price_sale_usd:
                    source_price = float(prop.price_sale_usd)
                    source_currency = 'USD'
                elif prop.price_sale_thb:
                    source_price = float(prop.price_sale_thb)
                    source_currency = 'THB'
                elif prop.price_sale_rub:
                    source_price = float(prop.price_sale_rub)
                    source_currency = 'RUB'

            # Конвертируем цену в выбранную валюту пользователя
            converted_price = None
            price_per_sqm = None

            if source_price and source_currency:
                converted_price = CurrencyService.convert_price(
                    source_price, source_currency, user_currency.code
                )
                if converted_price:
                    if prop.deal_type == 'rent':
                        price_display = f'{user_currency.symbol}{converted_price:,.0f}/мес'
                    else:
                        price_display = f'{user_currency.symbol}{converted_price:,.0f}'

                    # Вычисляем цену за квадратный метр (только для продажи)
                    if prop.deal_type in ['sale', 'both'] and prop.area_total and prop.area_total > 0:
                        price_per_sqm = converted_price / float(prop.area_total)

            properties_data.append({
                'id': prop.id,
                'title': prop.title,
                'slug': prop.slug,
                'district_name': prop.district.name if prop.district else '',
                'property_type_name': prop.property_type.name_display if prop.property_type else '',
                'deal_type': prop.deal_type,
                'price_display': price_display,
                'price_per_sqm': price_per_sqm,
                'currency_symbol': user_currency.symbol,
                'main_image_url': main_image_url,
                # Дополнительные данные для таблицы сравнения
                'bedrooms': prop.bedrooms,
                'bathrooms': prop.bathrooms,
                'area_total': float(prop.area_total) if prop.area_total else None,
                'area_land': float(prop.area_land) if prop.area_land else None,
                'pool': prop.pool,
                'parking': prop.parking,
                'furnished': prop.furnished,
                'security': prop.security,
                'gym': prop.gym,
            })
        
        return JsonResponse({
            'success': True,
            'properties': properties_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Ошибка при получении объектов: {str(e)}'
        })


@require_POST
@rate_limit('property-inquiry', limit=5, timeout=60)
def property_inquiry(request, property_id):
    """AJAX отправка запроса по недвижимости"""
    security_error = validate_form_security(request)
    if security_error:
        return security_error
    name = request.POST.get('name')
    phone = request.POST.get('phone', '')
    email = request.POST.get('email', '')
    message = request.POST.get('message', '')
    inquiry_type = request.POST.get('inquiry_type', 'general')

    # Дополнительные поля для разных типов запросов
    preferred_date = request.POST.get('preferred_date', None)
    consultation_topic = request.POST.get('consultation_topic', '')
    preferred_contact = request.POST.get('preferred_contact', '')

    # Проверяем обязательные поля (имя и телефон)
    if not all([name, phone]):
        return JsonResponse({
            'success': False,
            'message': 'Заполните все обязательные поля'
        })

    property_obj = get_object_or_404(Property, id=property_id)

    # Создаем запрос с учетом всех полей
    inquiry_data = {
        'property': property_obj,
        'name': name,
        'phone': phone,
        'email': email,
        'message': message,
        'inquiry_type': inquiry_type,
    }

    # Добавляем опциональные поля если они заполнены
    if preferred_date:
        inquiry_data['preferred_date'] = preferred_date
    if consultation_topic:
        inquiry_data['consultation_topic'] = consultation_topic
    if preferred_contact:
        inquiry_data['preferred_contact'] = preferred_contact

    inquiry = PropertyInquiry.objects.create(**inquiry_data)

    # TODO: Отправка email уведомления
    # TODO: Интеграция с AmoCRM

    return JsonResponse({
        'success': True,
        'message': 'Ваш запрос отправлен! Мы свяжемся с вами в ближайшее время.'
    })


def property_list_ajax(request):
    """AJAX endpoint для фильтрации списка недвижимости"""
    # Создаем временный объект view для использования метода apply_filters
    view = PropertyListView()
    view.request = request
    
    # Получаем базовый queryset
    queryset = Property.objects.filter(
        is_active=True,
        status='available'
    ).select_related('district', 'property_type').prefetch_related('images')
    
    # Применяем фильтры
    queryset = view.apply_filters(queryset)
    
    # Сортировка
    sort_by = request.GET.get('sort', '-created_at')
    allowed_sorts = [
        'price_asc', 'price_desc',
        'price_sale_usd', '-price_sale_usd',
        'price_sale_thb', '-price_sale_thb',
        'price_rent_monthly', '-price_rent_monthly',
        'area_total', '-area_total',
        'created_at', '-created_at'
    ]
    if sort_by in allowed_sorts:
        if view._is_price_sort(sort_by):
            queryset = queryset.order_by(view.get_catalog_price_sort_expression(descending=view._is_descending_price_sort(sort_by)))
        else:
            queryset = queryset.order_by(sort_by)
    else:
        queryset = queryset.order_by('-created_at')
    
    # Пагинация
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, 12)
    try:
        properties = paginator.page(page)
    except:
        properties = paginator.page(1)
    
    # Подготавливаем данные для JSON ответа
    properties_data = []
    for property_obj in properties:
        # Получаем главное изображение
        main_image = property_obj.images.filter(is_main=True).first()
        if not main_image:
            main_image = property_obj.images.first()
        
        # Определяем цену для отображения в зависимости от типа сделки
        if property_obj.deal_type == 'rent' and property_obj.price_rent_monthly:
            price_usd = property_obj.price_rent_monthly
            price_thb = property_obj.price_rent_monthly * 36 if property_obj.price_rent_monthly else 0  # примерный курс
        else:
            price_usd = property_obj.price_sale_usd or 0
            price_thb = property_obj.price_sale_thb or 0
            
        properties_data.append({
            'id': property_obj.id,
            'title': property_obj.title,
            'price_usd': price_usd,
            'price_thb': price_thb,
            'bedrooms': property_obj.bedrooms,
            'bathrooms': property_obj.bathrooms,
            'area': property_obj.area_total,
            'district_name': property_obj.district.name if property_obj.district else '',
            'property_type_name': property_obj.property_type.name_display if property_obj.property_type else '',
            'slug': property_obj.slug,
            'main_image_url': main_image.original_url if main_image else '',
            'main_image_thumbnail_url': main_image.thumbnail_url if main_image else '',
            'deal_type': property_obj.deal_type,
            'is_featured': property_obj.is_featured,
        })
    
    return JsonResponse({
        'success': True,
        'properties': properties_data,
        'pagination': {
            'current_page': properties.number,
            'total_pages': paginator.num_pages,
            'has_previous': properties.has_previous(),
            'has_next': properties.has_next(),
            'previous_page': properties.previous_page_number() if properties.has_previous() else None,
            'next_page': properties.next_page_number() if properties.has_next() else None,
            'total_count': paginator.count,
        }
    })


def get_locations_for_district(request):
    """AJAX endpoint для получения локаций по району"""
    from apps.locations.models import Location

    language_code = getattr(request, 'LANGUAGE_CODE', 'ru')[:2]
    district_slug = request.GET.get('district')

    if district_slug:
        locations = Location.objects.filter(district__slug=district_slug).order_by('name')
    else:
        locations = Location.objects.all().order_by('name')

    return JsonResponse({
        'success': True,
        'locations': [
            {
                'slug': location.slug,
                'name': _get_translated_attr(location, 'name', language_code, location.name),
            }
            for location in locations
        ]
    })


def map_properties_json(request):
    """Optimized AJAX endpoint для получения всех отфильтрованных объектов для карты"""
    try:
        # Создаем временный объект view для использования фильтров
        view = PropertyListView()
        view.request = request
        
        # Получаем базовый queryset с минимальными данными для карты
        queryset = Property.objects.filter(
            is_active=True,
            status='available'
        ).select_related('district', 'location', 'property_type', 'agent').prefetch_related('images')
        
        # Применяем все фильтры
        queryset = view.apply_filters(queryset)
        
        # Ограничиваем количество для производительности (максимум 1000 объектов)
        queryset = queryset[:1000]
        
        # Подготавливаем минимальные данные для маркеров карты
        properties_data = []
        for prop in queryset:
            # Пропускаем объекты без координат
            if not prop.latitude or not prop.longitude:
                continue
                
            # Получаем главное изображение
            main_image = prop.images.filter(is_main=True).first()
            if not main_image:
                main_image = prop.images.first()
            
            image_url = main_image.thumbnail_url if main_image else ''
                
            # Определяем цену для отображения
            price_display = ''
            if prop.deal_type == 'rent' and prop.price_rent_monthly:
                price_display = f"${prop.price_rent_monthly:,.0f}/мес"
            elif prop.deal_type in ['sale', 'both'] and prop.price_sale_usd:
                price_display = f"${prop.price_sale_usd:,.0f}"
            else:
                price_display = "Цена по запросу"
            
            # Generate language-aware URL
            from django.utils.translation import get_language
            
            current_language = get_language() or 'ru'
            # Всегда используем языковой префикс, так как prefix_default_language=True
            property_url = f'/{current_language}/property/{prop.slug}/'
            
            agent_phone = ''
            if prop.agent and prop.agent.phone:
                agent_phone = prop.agent.phone
            properties_data.append({
                'id': prop.id,
                'title': prop.title,
                'slug': prop.slug,
                'lat': float(prop.latitude),
                'lng': float(prop.longitude),
                'property_type': prop.property_type.name if prop.property_type else '',
                'property_type_label': prop.property_type.name_display if prop.property_type else '',
                'deal_type': prop.deal_type,
                'price': price_display,
                'location': prop.location.name if prop.location else (prop.district.name if prop.district else ''),
                'url': property_url,
                'image_url': image_url,
                'bedrooms': prop.bedrooms or 0,
                'bathrooms': prop.bathrooms or 0,
                'area': float(prop.area_total) if prop.area_total else 0,
                'agent_phone': agent_phone or '+66633033133'
            })
        
        return JsonResponse({
            'success': True,
            'properties': properties_data,
            'total_count': len(properties_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def ajax_search_count(request):
    """AJAX endpoint для подсчета количества объектов по фильтрам"""
    try:
        # Получаем базовый queryset
        queryset = Property.objects.filter(
            is_active=True,
            status='available'
        )
        
        # Применяем фильтры (используем POST или GET данные)
        filters = request.POST if request.method == 'POST' else request.GET
        currency_code = CurrencyService.get_selected_currency_code(request)
        queryset = apply_search_filters(queryset, filters, currency_code)
        
        # Возвращаем количество
        count = queryset.count()
        
        return JsonResponse({
            'success': True,
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def apply_search_filters(queryset, filters, currency_code='USD'):
    """Применяет поисковые фильтры к queryset (работает с POST и GET данными)"""

    def get_values(key):
        if hasattr(filters, 'getlist'):
            values = [value for value in filters.getlist(key) if value not in (None, '')]
            if values:
                return values
        value = filters.get(key)
        return [value] if value not in (None, '') else []

    # Тип недвижимости
    property_types = get_values('property_type')
    legacy_property_type = filters.get('type')
    current_property_type = filters.get('current_property_type')
    if legacy_property_type and legacy_property_type not in property_types:
        property_types.append(legacy_property_type)
    if not property_types and current_property_type:
        property_types.append(current_property_type)
    if property_types:
        queryset = queryset.filter(property_type__name__in=property_types)

    # Стадия готовности
    build_status = filters.get('build_status')
    valid_statuses = dict(Property.BUILD_STATUS_CHOICES)
    if build_status and build_status in valid_statuses:
        queryset = queryset.filter(build_status=build_status)

    # Район  
    district = filters.get('district')
    if district:
        queryset = queryset.filter(district__slug=district)
    
    # Локация
    location = filters.get('location')
    if location:
        if str(location).isdigit():
            queryset = queryset.filter(location__id=location)
        else:
            queryset = queryset.filter(location__slug=location)
    
    # Ценовые фильтры (в USD по умолчанию)
    min_price = filters.get('min_price')
    max_price = filters.get('max_price')
    
    sale_field, rent_field = CurrencyService.get_price_field_names(currency_code)

    if min_price:
        try:
            min_val = Decimal(min_price)
            price_filter = Q(**{f"{sale_field}__gte": min_val})
            if rent_field:
                price_filter |= Q(**{f"{rent_field}__gte": min_val})
            queryset = queryset.filter(price_filter)
        except (InvalidOperation, ValueError):
            pass
            
    if max_price:
        try:
            max_val = Decimal(max_price)
            price_filter = Q(**{f"{sale_field}__lte": max_val})
            if rent_field:
                price_filter |= Q(**{f"{rent_field}__lte": max_val})
            queryset = queryset.filter(price_filter)
        except (InvalidOperation, ValueError):
            pass
    
    # Количество спален
    bedrooms = get_values('bedrooms')
    if bedrooms:
        bedroom_filters = Q()
        for bedroom in bedrooms:
            try:
                if str(bedroom) in ('4', '4+'):
                    bedroom_filters |= Q(bedrooms__gte=4)
                else:
                    bedroom_filters |= Q(bedrooms=int(bedroom))
            except ValueError:
                continue
        if bedroom_filters:
            queryset = queryset.filter(bedroom_filters)
    
    # Тип сделки
    deal_type = filters.get('deal_type')
    if deal_type and deal_type in ['sale', 'rent']:
        queryset = queryset.filter(deal_type__in=[deal_type, 'both'])
    
    # Удобства/особенности
    amenities = get_values('amenities')
    if amenities:
        for amenity_id in amenities:
            try:
                amenity_id = int(amenity_id)
                queryset = queryset.filter(features__feature__id=amenity_id)
            except (ValueError, TypeError):
                pass
    
    # Текстовый поиск
    query = filters.get('q')
    if query:
        queryset = queryset.filter(
            Q(title_ru__icontains=query) |
            Q(title_en__icontains=query) |
            Q(description_ru__icontains=query) |
            Q(description_en__icontains=query) |
            Q(district__name_ru__icontains=query) |
            Q(district__name_en__icontains=query)
        )
    
    return queryset.distinct()


@require_POST
@csrf_exempt
def bulk_upload_images(request):
    """AJAX endpoint для массовой загрузки изображений для объекта недвижимости"""
    from .models import PropertyImage
    from django.db import models
    
    try:
        property_id = request.POST.get('property_id')
        if not property_id:
            return JsonResponse({
                'success': False,
                'message': 'Property ID не указан'
            })
        
        # Проверяем существование объекта недвижимости
        try:
            property_obj = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Объект недвижимости не найден'
            })
        
        # Получаем загруженные файлы
        uploaded_files = request.FILES.getlist('images')
        if not uploaded_files:
            return JsonResponse({
                'success': False,
                'message': 'Файлы для загрузки не найдены'
            })
        
        # Проверяем, что это изображения
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
        valid_files = []
        errors = []
        
        for file in uploaded_files:
            if file.content_type not in allowed_types:
                errors.append(f'Файл {file.name} не является изображением')
                continue
            
            # Проверяем размер файла (максимум 10MB)
            if file.size > 10 * 1024 * 1024:
                errors.append(f'Файл {file.name} слишком большой (максимум 10MB)')
                continue
                
            valid_files.append(file)
        
        if not valid_files:
            return JsonResponse({
                'success': False,
                'message': 'Нет допустимых файлов для загрузки',
                'errors': errors
            })
        
        # Определяем следующий порядковый номер
        last_order = PropertyImage.objects.filter(
            property=property_obj
        ).aggregate(max_order=models.Max('order'))['max_order'] or 0
        
        # Создаем объекты PropertyImage
        created_images = []
        for i, file in enumerate(valid_files):
            try:
                # Определяем, является ли первое изображение главным
                is_main = (i == 0) and not PropertyImage.objects.filter(
                    property=property_obj, 
                    is_main=True
                ).exists()
                
                property_image = PropertyImage.objects.create(
                    property=property_obj,
                    image=file,
                    title=file.name.split('.')[0],  # Используем имя файла без расширения как название
                    is_main=is_main,
                    order=last_order + i + 1,
                    image_type='main'
                )
                
                created_images.append({
                    'id': property_image.id,
                    'title': property_image.title,
                    'image_url': property_image.original_url,
                    'thumbnail_url': property_image.thumbnail_url,
                    'is_main': property_image.is_main,
                    'order': property_image.order
                })
                
            except Exception as e:
                errors.append(f'Ошибка при загрузке файла {file.name}: {str(e)}')
        
        return JsonResponse({
            'success': True,
            'message': f'Успешно загружено {len(created_images)} изображений',
            'images': created_images,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Произошла ошибка: {str(e)}'
        })


@require_POST
@csrf_exempt
def update_image_order(request):
    """AJAX endpoint для обновления порядка изображений"""
    import json
    from .models import PropertyImage
    
    try:
        # Получаем JSON данные
        data = json.loads(request.body)
        images_data = data.get('images', [])
        
        if not images_data:
            return JsonResponse({
                'success': False,
                'message': 'Нет данных для обновления'
            })
        
        # Обновляем порядок изображений
        updated_count = 0
        for image_data in images_data:
            image_id = image_data.get('id')
            new_order = image_data.get('order')
            
            if image_id and new_order is not None:
                try:
                    property_image = PropertyImage.objects.get(id=image_id)
                    property_image.order = new_order
                    property_image.save(update_fields=['order'])
                    updated_count += 1
                except PropertyImage.DoesNotExist:
                    continue
        
        return JsonResponse({
            'success': True,
            'message': f'Обновлен порядок {updated_count} изображений',
            'updated_count': updated_count
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат JSON данных'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Произошла ошибка: {str(e)}'
        })


class YandexYmlFeedView(View):
    """Serve Yandex-compatible YML feed with the current inventory."""

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        base_url = request.build_absolute_uri('/')
        language_code = request.GET.get('lang') or getattr(request, 'LANGUAGE_CODE', 'ru')
        generator = YandexYmlFeedGenerator(base_url=base_url, language_code=language_code)
        feed_bytes = generator.generate()
        response = HttpResponse(feed_bytes, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = 'inline; filename="yandex_realty.xml"'
        response['X-Generated-At'] = generator.generated_at.isoformat()
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
