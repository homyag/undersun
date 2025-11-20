from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.contrib.staticfiles.storage import staticfiles_storage
from .models import District, Location
from apps.properties.models import Property


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
        properties = Property.objects.filter(
            district=self.object,
            is_active=True,
            status='available'
        ).select_related('property_type').prefetch_related('images')

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(properties, 12)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['properties'] = page_obj

        # Локации в районе
        context['locations'] = self.object.locations.all()
        context['district_static_image'] = _get_static_location_image(self.object.slug)

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
        properties = Property.objects.filter(
            location=self.object,
            is_active=True,
            status='available'
        ).select_related('property_type').prefetch_related('images')

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(properties, 12)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context['properties'] = page_obj
        context['district'] = self.object.district
        context['location_static_image'] = (
            _get_static_location_image(self.object.slug)
            or _get_static_location_image(self.object.district.slug)
        )
        context['district_static_image'] = _get_static_location_image(self.object.district.slug)

        return context
