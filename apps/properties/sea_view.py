"""A curated catalog for properties with an explicitly confirmed sea view."""

from django.db.models import Q
from django.urls import reverse
from django.views.generic import ListView

from .models import Property
from .public_inventory import public_sale_queryset


SEA_VIEW_COPY = {
    'ru': {
        'title': 'Недвижимость с видом на море на Пхукете | Undersun Estate',
        'description': 'Виллы и квартиры с видом на море на Пхукете. Сравните расположение, планировки и цены, чтобы выбрать подходящий объект.',
        'heading': 'Недвижимость с видом на море на Пхукете',
        'eyebrow': 'Виллы и квартиры',
        'intro': 'Выберите виллу или квартиру с видом на море. Сравните расположение, планировки и цены, а мы уточним, откуда именно открывается вид, и организуем просмотр.',
        'count': 'В подборке',
        'list_heading': 'Доступные предложения',
        'check_heading': 'Перед просмотром уточним',
        'checks': [
            'Из каких комнат открывается вид: из гостиной, спальни или с террасы.',
            'Как этаж и окружающие здания влияют на обзор.',
            'Сколько времени занимает дорога до пляжа и повседневных мест.',
        ],
        'empty': 'Сейчас в подборке нет доступных объектов. Расскажите, что вы ищете, — поможем найти подходящий вариант.',
        'catalog_label': 'Весь каталог',
        'page_label': 'Страница',
        'previous': 'Назад',
        'next': 'Далее',
        'area': 'Пхукет, Таиланд',
        'details': 'Подробнее об объекте',
        'bedrooms_label': 'спал.',
        'price_on_request': 'Цена по запросу',
        'related_heading': 'Другие предложения',
        'villa_label': 'Виллы',
        'condo_label': 'Квартиры',
        'contact_label': 'Получить консультацию',
    },
    'en': {
        'title': 'Sea-view properties in Phuket | Undersun Estate',
        'description': 'Explore sea-view villas and condos in Phuket. Compare locations, layouts and prices to find the right property.',
        'heading': 'Sea-view properties in Phuket',
        'eyebrow': 'Villas and condos',
        'intro': 'Find a villa or condo with a sea view. Compare locations, layouts and prices, and we’ll help confirm the view from the specific property and arrange a viewing.',
        'count': 'In this selection',
        'list_heading': 'Available properties',
        'check_heading': 'We’ll confirm before your visit',
        'checks': [
            'Which rooms face the sea — the living room, bedroom or terrace.',
            'How the floor and nearby buildings affect the outlook.',
            'Travel time to the beach and the places you use every day.',
        ],
        'empty': 'There are no available properties in this selection right now. Tell us what you’re looking for and we’ll help find a suitable option.',
        'catalog_label': 'All properties',
        'page_label': 'Page',
        'previous': 'Previous',
        'next': 'Next',
        'area': 'Phuket, Thailand',
        'details': 'View property',
        'bedrooms_label': 'bedrooms',
        'price_on_request': 'Price on request',
        'related_heading': 'More properties',
        'villa_label': 'Villas',
        'condo_label': 'Condos',
        'contact_label': 'Help me choose',
    },
    'th': {
        'title': 'อสังหาริมทรัพย์วิวทะเลในภูเก็ต | Undersun Estate',
        'description': 'เลือกชมวิลล่าและคอนโดวิวทะเลในภูเก็ต เปรียบเทียบทำเล แบบห้อง และราคาเพื่อค้นหาทรัพย์ที่เหมาะกับคุณ',
        'heading': 'อสังหาริมทรัพย์วิวทะเลในภูเก็ต',
        'eyebrow': 'วิลล่าและคอนโด',
        'intro': 'เลือกวิลล่าหรือคอนโดที่มองเห็นทะเล เปรียบเทียบทำเล แบบห้อง และราคา เราจะช่วยยืนยันวิวของทรัพย์ที่คุณสนใจและนัดหมายเข้าชม',
        'count': 'ในรายการนี้',
        'list_heading': 'ทรัพย์ที่พร้อมเสนอ',
        'check_heading': 'เราจะช่วยตรวจสอบก่อนนัดชม',
        'checks': [
            'ห้องใดมองเห็นทะเล เช่น ห้องนั่งเล่น ห้องนอน หรือระเบียง',
            'ชั้นและอาคารรอบข้างมีผลต่อมุมมองอย่างไร',
            'ใช้เวลาเดินทางไปชายหาดและสถานที่ที่คุณไปเป็นประจำเท่าไร',
        ],
        'empty': 'ขณะนี้ยังไม่มีทรัพย์ที่พร้อมเสนอในรายการนี้ บอกความต้องการของคุณ แล้วเราจะช่วยค้นหาตัวเลือกที่เหมาะสม',
        'catalog_label': 'ทรัพย์ทั้งหมด',
        'page_label': 'หน้า',
        'previous': 'ก่อนหน้า',
        'next': 'ถัดไป',
        'area': 'ภูเก็ต ประเทศไทย',
        'details': 'ดูรายละเอียด',
        'bedrooms_label': 'ห้องนอน',
        'price_on_request': 'สอบถามราคา',
        'related_heading': 'ทรัพย์อื่น ๆ',
        'villa_label': 'วิลล่า',
        'condo_label': 'คอนโด',
        'contact_label': 'ให้เราช่วยเลือก',
    },
}


def sea_view_property_queryset():
    """Use structured claims only; text matches could describe a blocked view."""
    sea_view_feature = (
        Q(features__feature__name_ru__iexact='Вид на море')
        | Q(features__feature__name_en__iexact='Sea view')
        | Q(features__feature__name_en__iexact='Ocean view')
        | Q(features__feature__name_th__iexact='วิวทะเล')
    )
    # Source-owned features may lag behind a unit update until card refresh.
    # In that case the current unit flag is authoritative for the landing.
    usable_feature = sea_view_feature & (
        Q(arealisting_group__isnull=True)
        | ~Q(arealisting_group__source_owned_fields__contains=['features'])
        | Q(arealisting_group__locked_fields__contains=['features'])
    )
    available_sea_view_unit = Q(
        arealisting_group__is_active=True,
        arealisting_group__project__is_deleted=False,
        arealisting_group__units__is_deleted=False,
        arealisting_group__units__availability_status='AVAILABLE',
        arealisting_group__units__sea_view=True,
    )
    return (
        public_sale_queryset(Property.objects.filter(is_active=True, status='available'))
        .exclude(property_type__name='land')
        .filter(usable_feature | available_sea_view_unit)
        .select_related('district', 'location', 'property_type')
        .prefetch_related('images')
        .distinct()
    )


class SeaViewListView(ListView):
    template_name = 'properties/sea_view.html'
    context_object_name = 'properties'
    paginate_by = 12

    def get_queryset(self):
        return sea_view_property_queryset().order_by('-featured_priority', '-created_at', '-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'en')[:2]
        copy = SEA_VIEW_COPY.get(language_code, SEA_VIEW_COPY['en'])
        canonical_url = self.request.build_absolute_uri(reverse('properties:property_sea_view'))
        context.update({
            'copy': copy,
            'page_title': copy['title'],
            'page_description': copy['description'],
            'canonical_url': canonical_url,
            'catalog_url': reverse('properties:property_sale'),
            'villa_url': reverse('properties:property_by_type', args=['villa']),
            'condo_url': reverse('properties:property_by_type', args=['condo']),
            'contact_url': reverse('core:contact'),
            'results_count': context['paginator'].count,
        })
        if not context['paginator'].count or context['page_obj'].number > 1 or set(self.request.GET) - {'page'}:
            context['meta_robots'] = 'noindex, follow'
        self.request.canonical_url_override = canonical_url
        self.request.seo_page_title = copy['title']
        self.request.seo_page_description = copy['description']
        return context
