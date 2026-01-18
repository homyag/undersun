from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg
from statistics import median
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.translation import gettext_lazy as _
from .models import District, Location
from apps.properties.models import Property, PropertyType
from apps.currency.services import CurrencyService


IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def _get_static_location_image(slug):
    if not slug:
        return None

    base = slug.strip()
    if not base:
        return None

    variants = {
        base,
        base.lower(),
        base.upper(),
        base.capitalize(),
        base.replace('-', ''),
        base.replace('-', '_'),
        base.replace('-', ' '),
        base.replace('-', ' ').title(),
        base.replace('-', ' ').title().replace(' ', ''),
        base.replace('-', ' ').title().replace(' ', '_'),
    }

    for variant in list(variants):
        if not variant:
            continue
        for ext in IMAGE_EXTENSIONS:
            path = f'images/locations/{variant}{ext}'
            try:
                if staticfiles_storage.exists(path):
                    return staticfiles_storage.url(path)
            except Exception:
                continue

    return None


class LocationListView(ListView):
    model = District
    template_name = 'locations/list.html'
    context_object_name = 'districts'

    def get_queryset(self):
        return District.objects.annotate(
            properties_count=Count('property', filter=Q(property__is_active=True, property__status='available'))
        ).filter(properties_count__gt=0)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for district in context['districts']:
            district.static_image = _get_static_location_image(district.slug)
        return context


class DistrictDetailView(DetailView):
    model = District
    template_name = 'locations/district_detail.html'
    context_object_name = 'district'
    slug_url_kwarg = 'district_slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Недвижимость в районе
        base_queryset = Property.objects.filter(
            district=self.object,
            is_active=True,
            status='available'
        ).select_related('property_type').prefetch_related('images')

        currency_code = CurrencyService.get_selected_currency_code(self.request)
        sale_field, _ = CurrencyService.get_price_field_names(currency_code)

        sale_values = list(
            base_queryset
            .filter(**{f"{sale_field}__isnull": False})
            .values_list(sale_field, flat=True)
        )
        median_price = median(sale_values) if sale_values else None

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(base_queryset, 12)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['properties'] = page_obj
        context['district_property_count'] = paginator.count
        context['selected_currency'] = CurrencyService.get_currency_by_code(currency_code)
        context['district_avg_price'] = median_price

        # Локации в районе
        locations = self.object.locations.all()
        context['locations'] = locations

        property_type_ids = (
            base_queryset
            .filter(property_type__isnull=False)
            .values_list('property_type_id', flat=True)
            .distinct()
        )
        property_types = list(
            PropertyType.objects.filter(id__in=property_type_ids)
            .order_by('name_display')
        )
        context['district_property_types'] = property_types
        location_stats = []
        for location in locations:
            location_queryset = base_queryset.filter(location=location)
            location_count = location_queryset.count()
            if location_count == 0:
                median_value = None
            else:
                location_values = list(
                    location_queryset
                    .filter(**{f"{sale_field}__isnull": False})
                    .values_list(sale_field, flat=True)
                )
                median_value = median(location_values) if location_values else None

            type_stats = []
            for property_type in property_types:
                type_queryset = location_queryset.filter(property_type=property_type)
                type_count = type_queryset.count()
                if type_count:
                    type_values = list(
                        type_queryset
                        .filter(**{f"{sale_field}__isnull": False})
                        .values_list(sale_field, flat=True)
                    )
                    type_median = median(type_values) if type_values else None
                else:
                    type_median = None

                type_stats.append({
                    'property_type': property_type,
                    'count': type_count,
                    'median_price': type_median,
                })

            location_stats.append({
                'location': location,
                'property_count': location_count,
                'median_price': median_value,
                'types': type_stats,
            })

        context['location_stats'] = location_stats
        context['district_static_image'] = _get_static_location_image(self.object.slug)
        context['district_roi'] = DISTRICT_ROI_INFO.get(self.object.slug)
        context['district_travel_time'] = DISTRICT_TRAVEL_TIMES.get(self.object.slug)

        return context


class LocationDetailView(DetailView):
    model = Location
    template_name = 'locations/location_detail.html'
    context_object_name = 'location'
    slug_url_kwarg = 'location_slug'

    def get_object(self):
        district = get_object_or_404(District, slug=self.kwargs['district_slug'])
        return get_object_or_404(Location, slug=self.kwargs['location_slug'], district=district)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Недвижимость в локации
        base_queryset = Property.objects.filter(
            location=self.object,
            is_active=True,
            status='available'
        ).select_related('property_type').prefetch_related('images')

        currency_code = CurrencyService.get_selected_currency_code(self.request)
        sale_field, _ = CurrencyService.get_price_field_names(currency_code)
        sale_values = list(
            base_queryset
            .filter(**{f"{sale_field}__isnull": False})
            .values_list(sale_field, flat=True)
        )
        median_price = median(sale_values) if sale_values else None

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(base_queryset, 12)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['properties'] = page_obj
        context['district_property_count'] = paginator.count
        context['location_property_count'] = paginator.count
        context['district'] = self.object.district
        context['selected_currency'] = CurrencyService.get_currency_by_code(currency_code)
        context['district_avg_price'] = median_price
        context['location_avg_price'] = median_price
        context['location_static_image'] = (
            _get_static_location_image(self.object.slug)
            or _get_static_location_image(self.object.district.slug)
        )
        context['district_static_image'] = _get_static_location_image(self.object.district.slug)
        context['district_roi'] = DISTRICT_ROI_INFO.get(self.object.district.slug)
        context['district_travel_time'] = DISTRICT_TRAVEL_TIMES.get(self.object.district.slug)

        return context
DISTRICT_ROI_INFO = {
    'mueang-phuket-district': {
        'title': 'Mueang Phuket',
        'roi': _('4–6%/год'),
        'note': _('Ставка на стабильный спрос (город + долгосрок), ниже сезонность.')
    },
    'kathu-district': {
        'title': 'Kathu District',
        'roi': _('7–8%/год'),
        'note': _('Смешанный спрос + туристические зоны, доходность выше, но сезонность заметнее.')
    },
    'thalang-district': {
        'title': 'Thalang',
        'roi': _('6–9%+/год'),
        'note': _('Курортные локации, премиальный спрос, иногда встречаются «гарантированные» программы.')
    },
}

DISTRICT_TRAVEL_TIMES = {
    'mueang-phuket-district': {
        'car': '35–40',
        'bus': '60–70',
        'note': _('Такси или трансфер — около 35 минут; автобус дольше из-за остановок.')
    },
    'kathu-district': {
        'car': '30–45',
        'bus': '50–60',
        'note': _('Среднее ~40 минут на автомобиле, автобусом чуть дольше.')
    },
    'thalang-district': {
        'car': '10–15',
        'bus': '15',
        'note': _('Аэропорт находится в пределах района — самый быстрый доступ.')
    },
}
