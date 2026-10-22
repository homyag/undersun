"""A curated catalog for properties with an explicitly confirmed sea view."""

from django.db.models import Q
from django.urls import reverse
from django.views.generic import ListView

from .models import Property
from .public_inventory import public_sale_queryset


SEA_VIEW_COPY = {
    'ru': {
        'title': 'Недвижимость с видом на море на Пхукете | Undersun Estate',
        'description': 'Виллы и квартиры с подтверждённым видом на море на Пхукете. Сравните расположение, фотографии, характеристики и актуальные цены.',
        'heading': 'Недвижимость с видом на море на Пхукете',
        'eyebrow': 'Подборка Undersun Estate',
        'intro': 'В этой подборке — объекты, для которых вид на море указан в характеристиках карточки или подтверждён в доступных предложениях AREALISTING. Положение конкретного окна, этаж и открытость вида уточняйте перед просмотром.',
        'count': 'Объектов в подборке',
        'list_heading': 'Смотреть объекты',
        'check_heading': 'Что проверить перед выбором',
        'checks': [
            'С какого этажа и из каких комнат открывается вид.',
            'Нет ли запланированной застройки между объектом и берегом.',
            'Сколько времени занимает дорога к пляжу: вид на море не означает расположение у воды.',
        ],
        'empty': 'Сейчас нет опубликованных объектов с подтверждённым видом на море. Посмотрите весь каталог или попросите нас подобрать варианты.',
        'catalog_label': 'Весь каталог',
        'page_label': 'Страница',
        'previous': 'Назад',
        'next': 'Далее',
        'area': 'Пхукет, Таиланд',
        'details': 'Подробнее об объекте',
        'bedrooms_label': 'спал.',
        'price_on_request': 'Цена по запросу',
        'related_heading': 'Продолжить поиск',
        'villa_label': 'Виллы',
        'condo_label': 'Квартиры',
        'contact_label': 'Обсудить подбор',
    },
    'en': {
        'title': 'Sea-view properties in Phuket | Undersun Estate',
        'description': 'Explore Phuket villas and condos with a confirmed sea view. Compare locations, photos, property details and current asking prices.',
        'heading': 'Sea-view properties in Phuket',
        'eyebrow': 'Selected by Undersun Estate',
        'intro': 'These listings have a sea view recorded in the property features or in an available AREALISTING unit. Ask us to confirm the exact floor, room and outlook before arranging a viewing.',
        'count': 'Properties in this selection',
        'list_heading': 'Explore properties',
        'check_heading': 'What to check before choosing',
        'checks': [
            'Which floor and rooms actually face the sea.',
            'Whether planned construction could affect the outlook.',
            'Travel time to the beach: a sea view does not mean beachfront access.',
        ],
        'empty': 'There are currently no published properties with a confirmed sea view. Explore the full catalog or ask us to find suitable options.',
        'catalog_label': 'All properties',
        'page_label': 'Page',
        'previous': 'Previous',
        'next': 'Next',
        'area': 'Phuket, Thailand',
        'details': 'View property',
        'bedrooms_label': 'bedrooms',
        'price_on_request': 'Price on request',
        'related_heading': 'Continue exploring',
        'villa_label': 'Villas',
        'condo_label': 'Condos',
        'contact_label': 'Ask for a shortlist',
    },
    'th': {
        'title': 'อสังหาริมทรัพย์วิวทะเลในภูเก็ต | Undersun Estate',
        'description': 'เลือกชมวิลล่าและคอนโดในภูเก็ตที่มีข้อมูลยืนยันวิวทะเล เปรียบเทียบทำเล ภาพถ่าย รายละเอียด และราคาปัจจุบัน',
        'heading': 'อสังหาริมทรัพย์วิวทะเลในภูเก็ต',
        'eyebrow': 'คัดสรรโดย Undersun Estate',
        'intro': 'รายการนี้รวมทรัพย์ที่ระบุวิวทะเลในคุณลักษณะของทรัพย์หรือยูนิต AREALISTING ที่ยังว่าง กรุณาสอบถามชั้น ห้อง และทิศทางวิวที่แน่นอนก่อนนัดชม',
        'count': 'จำนวนทรัพย์ในรายการ',
        'list_heading': 'เลือกชมทรัพย์',
        'check_heading': 'สิ่งที่ควรตรวจสอบก่อนเลือก',
        'checks': [
            'ชั้นและห้องใดมองเห็นทะเลจริง',
            'โครงการก่อสร้างในอนาคตอาจบังวิวหรือไม่',
            'เวลาเดินทางไปชายหาด: วิวทะเลไม่ได้หมายความว่าติดชายหาด',
        ],
        'empty': 'ขณะนี้ยังไม่มีทรัพย์ที่เผยแพร่และยืนยันวิวทะเล ลองดูทรัพย์ทั้งหมดหรือให้เราช่วยคัดเลือก',
        'catalog_label': 'ทรัพย์ทั้งหมด',
        'page_label': 'หน้า',
        'previous': 'ก่อนหน้า',
        'next': 'ถัดไป',
        'area': 'ภูเก็ต ประเทศไทย',
        'details': 'ดูรายละเอียด',
        'bedrooms_label': 'ห้องนอน',
        'price_on_request': 'สอบถามราคา',
        'related_heading': 'ค้นหาต่อ',
        'villa_label': 'วิลล่า',
        'condo_label': 'คอนโด',
        'contact_label': 'ขอคำแนะนำ',
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
