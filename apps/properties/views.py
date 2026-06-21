import json
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote_plus, urlencode

from django.conf import settings
from django.views.generic import ListView, DetailView, View
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, Http404, HttpResponseRedirect, HttpResponse, HttpResponsePermanentRedirect
# login_required decorator removed
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Count, Case, When, Value, IntegerField, F, Avg
from django.db.models.functions import Coalesce
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.urls import reverse
from django.utils.translation import gettext, ngettext, override
from django.utils.html import strip_tags
from django.templatetags.static import static

from apps.currency.services import CurrencyService
from apps.core.utils import build_query_string, rate_limit, validate_form_security, truncate_meta
from apps.core.amp_utils import convert_html_to_amp
from apps.core.models import SEOContentBlock, Team
from apps.core.seo_utils import build_property_meta
from apps.core.business_profile import BUSINESS_PROFILE
from .seo_landings import resolve_landing_signature, build_candidate_slugs
from .models import Property, PropertyType
from apps.locations.models import District, Location
from apps.users.models import PropertyInquiry
from .yml_feed import YandexYmlFeedGenerator


LEGACY_PROPERTY_SLUG_REDIRECTS = {
    # Укороченный slug из старого каталога → актуальный slug
    '1-bedroom-apart': '1-bedroom-apartment-in-a-deluxe-condominium-in-rawai',
}

MISSING_PROPERTY_SLUG_FALLBACKS = {
    '2-bedroom-apartment-300-meters-from-surin-beach-phuket-at-the-petit-tycoon': {
        'view_name': 'properties:property_sale',
        'params': {
            'property_type': 'condo',
            'district': 'thalang',
        },
    },
}

CATALOG_LINK_UNSET = object()

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

PROTOMAPS_BASEMAP_URL = getattr(
    settings,
    'PROTOMAPS_BASEMAP_URL',
    '',
)
PHUKET_DISTRICT_BOUNDARIES_PATH = Path(settings.BASE_DIR) / 'data' / 'geoBoundaries-THA-ADM2.geojson'
PHUKET_DISTRICT_BOUNDARY_SLUG_ALIASES = {
    'kathu-district': 'kathu',
    'phuket': 'mueang-phuket',
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

CATALOG_LANDING_OVERRIDES = {
    ('en', 'type_only', 'condo', '', '', ''): {
        'heading': 'Condos in Phuket for buying and investment',
        'page_title': 'Condos for Sale in Phuket | Ownership and Project Checks | Undersun Estate',
        'page_description': (
            'Compare %(count)s condo listings by area, budget, project status, ownership structure and fees. '
            'Undersun Estate helps shortlist Phuket units.'
        ),
        'answer_first': (
            'Foreign buyers may be able to own condominium units in Thailand as foreign freehold when the project '
            'has available foreign quota. Before reserving a Phuket condo, confirm quota, title status, payment '
            'schedule, common area fees, sinking fund, rental rules and transfer costs.'
        ),
        'seo_heading': 'Buying a condo in Phuket',
        'intro': (
            'Compare condos and apartments for sale in Phuket with current listings from Undersun Estate. '
            'Use this page to shortlist units by budget, area, project status and practical ownership terms '
            'before arranging a viewing.'
        ),
        'highlights': [
            'Start with the use case: own stay, holiday use, rental management or long-term capital preservation.',
            (
                'Check foreign freehold quota, leasehold/freehold structure, common area fees, sinking fund, '
                'rental rules and handover terms before reserving.'
            ),
            (
                'Compare beach areas such as Bang Tao, Kamala and Karon with everyday locations such as '
                'Chalong, Rawai, Kathu and Phuket Town.'
            ),
            (
                'For off-plan condos, review developer track record, construction stage, payment schedule '
                'and what is included in the furniture package.'
            ),
        ],
        'follow_up': (
            'Our team can prepare a shortlist, confirm current availability with the developer or owner, '
            'and explain the tradeoffs between similar condo projects before you visit.'
        ),
        'faq_heading': 'Questions to ask before buying a condo in Phuket',
        'faq_entries': [
            {
                'question': 'Can foreigners buy a condo in Phuket?',
                'answer': (
                    'Foreign buyers can usually consider condominium units where foreign freehold quota is '
                    'available, or leasehold structures where that is the project format. The exact structure '
                    'must be checked for the specific unit before reservation.'
                ),
            },
            {
                'question': 'What should I check before buying a Phuket condo?',
                'answer': (
                    'Check the project status, title and ownership structure, foreign quota, payment schedule, '
                    'common area fees, sinking fund, furniture package, rental rules and handover terms.'
                ),
            },
            {
                'question': 'Which Phuket areas are popular for condos?',
                'answer': (
                    'Beach-focused buyers often compare Bang Tao, Kamala, Karon, Kata and Mai Khao. For daily '
                    'living and a lower-key environment, Chalong, Rawai, Kathu and Phuket Town can also be relevant.'
                ),
            },
            {
                'question': 'Is a Phuket condo suitable for investment?',
                'answer': (
                    'It can be, but only after checking the entry price, rental rules, management model, fees, '
                    'seasonality and resale liquidity. We avoid treating projected yield as a guarantee.'
                ),
            },
            {
                'question': 'How many condo listings are available on this page?',
                'answer': 'There are currently %(count)s active condo listings in this selection.',
            },
        ],
    },
    ('en', 'type_only', 'villa', '', '', ''): {
        'heading': 'Private villas and family homes in Phuket',
        'page_title': 'Villas for Sale in Phuket | Pool Villas and Family Homes | Undersun Estate',
        'page_description': (
            'Compare %(count)s villa listings by area, bedrooms, land, pool, project status and ownership terms. '
            'Undersun Estate helps shortlist Phuket homes.'
        ),
        'answer_first': (
            'Villas in Phuket can suit private living, family use and rental-focused ownership, but each villa '
            'requires project-specific checks. Before reserving, confirm land title, ownership structure, lease '
            'terms, access road, utilities, estate fees, construction status and legal review requirements.'
        ),
        'seo_heading': 'Buying a villa in Phuket',
        'intro': (
            'Use this villa selection to compare private pool villas, family homes and resort-style residences '
            'across Phuket. The right shortlist depends on more than the photo gallery: road access, land title, '
            'maintenance, rental rules and the specific micro-location all need to be checked.'
        ),
        'highlights': [
            'Separate lifestyle villas for own stay from rental-focused villas managed by a project or operator.',
            (
                'Review land title, ownership structure, access road, utilities, estate fees, pool and garden '
                'maintenance before committing to a reservation.'
            ),
            (
                'Compare Bang Tao, Layan and Laguna with Kamala, Rawai, Chalong, Kathu and Thalang depending '
                'on privacy, beach access, schools and daily logistics.'
            ),
            (
                'For off-plan villas, check developer delivery history, construction stage, payment schedule, '
                'included furniture and warranty terms.'
            ),
        ],
        'follow_up': (
            'Undersun Estate can compare similar villas side by side, confirm current availability and prepare '
            'questions for the owner or developer before a viewing.'
        ),
        'faq_heading': 'Questions to ask before buying a villa in Phuket',
        'faq_entries': [
            {
                'question': 'What should I check before buying a villa in Phuket?',
                'answer': (
                    'Check the land title, ownership structure, road access, utilities, estate fees, pool and '
                    'garden maintenance, project rules, construction status and all payment milestones.'
                ),
            },
            {
                'question': 'Which Phuket areas are popular for villas?',
                'answer': (
                    'Buyers often compare Bang Tao, Layan, Laguna and Kamala for resort-style villas, while '
                    'Rawai, Chalong, Kathu and Thalang can work for daily living, family logistics or larger plots.'
                ),
            },
            {
                'question': 'Is a villa better than a condo in Phuket?',
                'answer': (
                    'A villa gives more privacy, land and outdoor space, but it also brings more checks around '
                    'land structure, maintenance, access and management. The better format depends on the goal.'
                ),
            },
            {
                'question': 'Can a Phuket villa be used for rental income?',
                'answer': (
                    'Some villas can be rented, but the result depends on location, management, seasonality, '
                    'pricing, operating costs and legal/project rules. Projected yield should not be treated as guaranteed.'
                ),
            },
            {
                'question': 'How many villa listings are available on this page?',
                'answer': 'There are currently %(count)s active villa listings in this selection.',
            },
        ],
    },
    ('en', 'type_only', 'townhouse', '', '', ''): {
        'heading': 'Townhouses and family homes in Phuket',
        'page_title': 'Townhouses for Sale in Phuket | Family Homes | Undersun Estate',
        'page_description': (
            'Compare %(count)s listings by area, bedrooms, living space, project rules and budget. '
            'Undersun Estate helps shortlist practical Phuket homes.'
        ),
        'seo_heading': 'Buying a townhouse in Phuket',
        'intro': (
            'This townhouse selection helps compare practical Phuket homes for family living, relocation and '
            'long-term ownership. A townhouse can be a more manageable alternative to a private villa while '
            'still offering more space and privacy than a condo.'
        ),
        'highlights': [
            'Check whether the townhouse suits daily living: parking, road access, storage, bedrooms and outdoor space matter.',
            (
                'Review ownership structure, project rules, common fees, maintenance responsibilities, utilities '
                'and what is included before reserving.'
            ),
            (
                'Compare family-friendly areas such as Chalong, Rawai, Kathu, Phuket Town and parts of Thalang '
                'by schools, supermarkets, hospitals and commute time.'
            ),
            (
                'For resale or rental scenarios, look at project condition, competing homes nearby, management '
                'quality and realistic long-term demand.'
            ),
        ],
        'follow_up': (
            'Undersun Estate can compare townhouses with villas and condos, check current availability and '
            'prepare practical questions before a viewing.'
        ),
        'faq_heading': 'Questions to ask before buying a townhouse in Phuket',
        'faq_entries': [
            {
                'question': 'Is a townhouse a good alternative to a villa in Phuket?',
                'answer': (
                    'It can be. A townhouse usually gives more space than a condo and can be easier to maintain '
                    'than a private villa, but road access, project rules, fees and privacy need to be checked.'
                ),
            },
            {
                'question': 'What should I check before buying a Phuket townhouse?',
                'answer': (
                    'Check ownership structure, project rules, common fees, parking, road access, utilities, '
                    'building condition, maintenance responsibilities and rental restrictions.'
                ),
            },
            {
                'question': 'Which areas are practical for townhouses in Phuket?',
                'answer': (
                    'Townhouse buyers often compare everyday areas such as Chalong, Rawai, Kathu, Phuket Town '
                    'and parts of Thalang where schools, supermarkets and main roads are more important than beachfront access.'
                ),
            },
            {
                'question': 'Is a townhouse better than a condo?',
                'answer': (
                    'A townhouse can offer more living space, parking and privacy. A condo can be simpler to '
                    'manage and may have stronger resort facilities. The better format depends on the goal.'
                ),
            },
            {
                'question': 'How many townhouse listings are available on this page?',
                'answer': 'There are currently %(count)s active townhouse listings in this selection.',
            },
        ],
    },
    ('en', 'type_only', 'land', '', '', ''): {
        'heading': 'Land plots and development sites in Phuket',
        'page_title': 'Land for Sale in Phuket | Title and Site Checks | Undersun Estate',
        'page_description': (
            'Compare %(count)s plots by area, access, title, utilities, zoning constraints and development fit. '
            'Undersun Estate helps review site basics.'
        ),
        'seo_heading': 'Checking land before purchase in Phuket',
        'intro': (
            'This land selection is for buyers who are considering construction, development or long-term '
            'landholding in Phuket. A plot should be assessed through documents and site conditions, not only '
            'through its size and price.'
        ),
        'highlights': [
            'Check title type, boundaries, access road, utilities, slope, drainage and practical buildability before reserving.',
            (
                'Review planning limitations, surrounding development, road width, electricity, water, soil and '
                'the actual route from main roads.'
            ),
            (
                'For villa construction or development, compare the land with realistic design, permit, budget '
                'and exit scenarios.'
            ),
            (
                'For foreign buyers, the legal structure needs separate review before any payment is made.'
            ),
        ],
        'follow_up': (
            'Undersun Estate can prepare a shortlist of plots, request core documents and flag practical checks '
            'before a site visit.'
        ),
        'faq_heading': 'Questions to ask before buying land in Phuket',
        'faq_entries': [
            {
                'question': 'What should I check before buying land in Phuket?',
                'answer': (
                    'Check title, boundaries, access, utilities, slope, drainage, planning limitations, nearby '
                    'development and the legal structure for the buyer.'
                ),
            },
            {
                'question': 'Is every land plot suitable for villa construction?',
                'answer': (
                    'No. Buildability depends on title, access, utilities, slope, planning rules, budget, permits '
                    'and the actual site conditions.'
                ),
            },
            {
                'question': 'Can foreigners buy land in Thailand directly?',
                'answer': (
                    'Foreign land ownership is restricted, so the structure needs a separate legal review. Do not '
                    'rely on informal nominee or trust-based arrangements.'
                ),
            },
            {
                'question': 'How many land listings are available on this page?',
                'answer': 'There are currently %(count)s active land listings in this selection.',
            },
        ],
    },
    ('ru', 'type_only', 'villa', '', '', ''): {
        'heading': 'Подбор виллы на Пхукете',
        'page_title': 'Купить виллу на Пхукете | Подбор и проверка объекта | Undersun Estate',
        'page_description': (
            'Сравните варианты по району, бюджету, спальням, участку, бассейну, стадии проекта '
            'и условиям владения. Undersun Estate помогает собрать шорт-лист.'
        ),
        'answer_first': (
            'Виллы на Пхукете подходят для личного проживания, семейного использования и сценариев с арендой, '
            'но каждая вилла требует проверки конкретного проекта. Перед резервированием нужно подтвердить титул '
            'земли, структуру владения, условия leasehold, подъездную дорогу, коммуникации, платежи в комплексе, '
            'статус строительства и необходимость юридической проверки.'
        ),
        'seo_heading': 'Как выбирать виллу на Пхукете',
        'intro': (
            'В этом разделе собраны виллы на Пхукете для жизни, отдыха и инвестиционных сценариев. При выборе '
            'важно смотреть не только планировку и бассейн, но и титул земли, подъезд, управление, расходы на '
            'обслуживание, правила аренды и конкретную микролокацию.'
        ),
        'highlights': [
            'Разделяйте виллы для личного проживания, семейной жизни, отдыха и аренды: критерии выбора будут разными.',
            (
                'Проверьте титул земли, структуру владения, подъездную дорогу, коммуникации, платежи в комплексе, '
                'обслуживание бассейна и сада до внесения существенных платежей.'
            ),
            (
                'Сравнивайте Bang Tao, Layan, Laguna и Kamala с Rawai, Chalong, Kathu и Thalang по приватности, '
                'пляжам, школам, пробкам и повседневной логистике.'
            ),
            (
                'Для строящихся вилл отдельно оценивайте репутацию застройщика, стадию строительства, график '
                'платежей, комплектацию мебелью и гарантийные условия.'
            ),
        ],
        'follow_up': (
            'Мы можем сравнить похожие виллы, уточнить актуальную доступность и заранее подготовить вопросы '
            'к собственнику или застройщику перед просмотром.'
        ),
        'faq_heading': 'Что проверить перед покупкой виллы на Пхукете',
        'faq_entries': [
            {
                'question': 'Что важно проверить перед покупкой виллы на Пхукете?',
                'answer': (
                    'Титул земли, структуру владения, подъезд, коммуникации, платежи за обслуживание, состояние '
                    'объекта, правила комплекса, график платежей и условия передачи.'
                ),
            },
            {
                'question': 'Какие районы Пхукета чаще смотрят для покупки виллы?',
                'answer': (
                    'Для курортного формата часто сравнивают Bang Tao, Layan, Laguna и Kamala. Для жизни и '
                    'семейной логистики также смотрят Rawai, Chalong, Kathu и Thalang.'
                ),
            },
            {
                'question': 'Вилла на Пхукете подходит для инвестиций?',
                'answer': (
                    'Потенциально да, но нужно считать конкретный объект: цену входа, расходы, управление, '
                    'сезонность, правила аренды и ликвидность. Доходность нельзя считать гарантированной.'
                ),
            },
            {
                'question': 'Чем вилла отличается от квартиры в кондоминиуме при покупке?',
                'answer': (
                    'Вилла обычно даёт больше приватности, земли и пространства, но требует более тщательной '
                    'проверки земли, содержания, управления и юридической структуры.'
                ),
            },
            {
                'question': 'Сколько вилл сейчас есть в этой подборке?',
                'answer': 'Сейчас в подборке %(count)s актуальных предложений вилл.',
            },
        ],
    },
    ('ru', 'type_only', 'townhouse', '', '', ''): {
        'heading': 'Дома для жизни на Пхукете',
        'page_title': 'Купить дом на Пхукете | Дома для семьи | Undersun Estate',
        'page_description': (
            'Сравните варианты по району, спальням, площади, комплексу, бюджету '
            'и условиям владения. Undersun Estate помогает выбрать практичный вариант.'
        ),
        'seo_heading': 'Как выбирать дом на Пхукете',
        'intro': (
            'В этой подборке собраны дома на Пхукете для семейной жизни, переезда и долгосрочного владения. '
            'Такой формат часто практичнее квартиры и проще в обслуживании, чем отдельная вилла, но перед покупкой '
            'важно проверить правила комплекса, подъезд, парковку, расходы и состояние объекта.'
        ),
        'highlights': [
            'Оценивайте дом под ежедневную жизнь: парковка, подъезд, хранение, спальни и небольшое внешнее пространство важны не меньше площади.',
            (
                'Проверьте структуру владения, правила комплекса, платежи за обслуживание, коммунальные условия, '
                'ответственность за ремонт и то, что входит в цену.'
            ),
            (
                'Для семьи чаще сравнивают Chalong, Rawai, Kathu, Phuket Town и части Thalang по школам, '
                'магазинам, медицине, пробкам и ежедневной логистике.'
            ),
            (
                'Если дом рассматривается для аренды или перепродажи, отдельно оцените состояние комплекса, '
                'конкурирующие предложения рядом, управление и реальный спрос.'
            ),
        ],
        'follow_up': (
            'Undersun Estate поможет сравнить дома с виллами и квартирами, уточнить актуальную доступность '
            'и подготовить вопросы перед просмотром.'
        ),
        'faq_heading': 'Что проверить перед покупкой дома на Пхукете',
        'faq_entries': [
            {
                'question': 'Дом на Пхукете — это альтернатива вилле?',
                'answer': (
                    'Да, если нужен более практичный формат для жизни: больше пространства, чем в квартире, '
                    'но обычно меньше расходов и забот, чем у отдельной виллы. Нужно проверять комплекс, правила и платежи.'
                ),
            },
            {
                'question': 'Что важно проверить перед покупкой дома?',
                'answer': (
                    'Структуру владения, документы, правила комплекса, платежи за обслуживание, парковку, подъезд, '
                    'коммуникации, состояние здания, ответственность за ремонт и ограничения по аренде.'
                ),
            },
            {
                'question': 'Какие районы Пхукета удобны для покупки дома?',
                'answer': (
                    'Для постоянной жизни часто смотрят Chalong, Rawai, Kathu, Phuket Town и части Thalang, '
                    'где важны школы, магазины, медицина, дороги и повседневная инфраструктура.'
                ),
            },
            {
                'question': 'Дом лучше квартиры?',
                'answer': (
                    'Дом даёт больше пространства, приватности и парковку. Квартира может быть проще в управлении '
                    'и понятнее по владению для иностранцев. Выбор зависит от цели покупки.'
                ),
            },
            {
                'question': 'Сколько домов сейчас есть в этой подборке?',
                'answer': 'Сейчас в подборке %(count)s актуальных предложений домов.',
            },
        ],
    },
    ('ru', 'type_only', 'land', '', '', ''): {
        'heading': 'Участки для покупки на Пхукете',
        'page_title': 'Земля на Пхукете | Проверка участка и титула | Undersun Estate',
        'page_description': (
            'Сравните участки по району, площади, доступу, титулу, коммуникациям и ограничениям застройки. '
            'Undersun Estate помогает проверить исходные условия.'
        ),
        'seo_heading': 'Что проверить перед покупкой земли на Пхукете',
        'intro': (
            'Эта подборка подходит покупателям, которые рассматривают строительство, девелопмент или долгосрочное '
            'владение участком на Пхукете. Землю нельзя оценивать только по площади и цене: важны документы, '
            'доступ, коммуникации и реальные условия строительства.'
        ),
        'highlights': [
            'Проверьте титул, границы, подъезд, коммуникации, уклон, дренаж и практическую пригодность участка под строительство.',
            (
                'Оцените ограничения застройки, окружение, ширину дороги, электричество, воду, грунт и фактический '
                'маршрут от основных дорог.'
            ),
            (
                'Если участок нужен под виллу или проект, сравнивайте его с реальным бюджетом, разрешениями, '
                'архитектурной концепцией и сценарием выхода.'
            ),
            'Для иностранного покупателя юридическую структуру сделки нужно проверять отдельно до внесения платежей.',
        ],
        'follow_up': (
            'Undersun Estate поможет собрать короткий список участков, запросить базовые документы и заранее '
            'отметить вопросы для выезда на место.'
        ),
        'faq_heading': 'Вопросы перед покупкой земли на Пхукете',
        'faq_entries': [
            {
                'question': 'Что важно проверить перед покупкой земли на Пхукете?',
                'answer': (
                    'Титул, границы, подъезд, коммуникации, уклон, дренаж, ограничения застройки, окружение '
                    'и юридическую структуру сделки.'
                ),
            },
            {
                'question': 'Любой участок подходит для строительства виллы?',
                'answer': (
                    'Нет. Пригодность зависит от титула, подъезда, коммуникаций, уклона, правил застройки, '
                    'бюджета, разрешений и фактического состояния участка.'
                ),
            },
            {
                'question': 'Может ли иностранец купить землю в Таиланде напрямую?',
                'answer': (
                    'Прямое владение землей для иностранцев ограничено, поэтому структуру сделки нужно разбирать '
                    'с юристом. Серые схемы через номиналов лучше исключать.'
                ),
            },
            {
                'question': 'Сколько участков сейчас есть в этой подборке?',
                'answer': 'Сейчас в подборке %(count)s актуальных предложений земли.',
            },
        ],
    },
    ('en', 'deal_only', '', 'rent', '', ''): {
        'heading': 'Renting property in Phuket',
        'page_title': 'Phuket Rentals | Villas, Condos and Homes | Undersun Estate',
        'page_description': (
            'Explore rental listings by area, property type, bedrooms, budget and lease terms. '
            'Undersun Estate helps shortlist Phuket villas, condos and homes.'
        ),
        'seo_heading': 'Renting property in Phuket',
        'intro': (
            'This rental selection helps compare Phuket villas, condos, townhouses and homes by location, '
            'budget and practical living conditions. Before choosing a property, it is important to confirm '
            'lease length, deposit, utilities, maintenance responsibilities and what is included in the rent.'
        ),
        'highlights': [
            'Clarify the rental scenario first: holiday stay, seasonal rental, long-term living or relocation.',
            (
                'Check deposit, advance rent, utility rates, internet, cleaning, pool and garden service, pet rules '
                'and early termination terms.'
            ),
            (
                'Compare beach areas with daily-life locations: proximity to schools, supermarkets, gyms, hospitals '
                'and main roads can matter more than distance to the beach.'
            ),
            'For remote selection, request current photos, video viewing and a written list of included items.',
        ],
        'follow_up': (
            'Undersun Estate can clarify current availability, negotiate viewing times and confirm the lease terms '
            'before you travel to the property.'
        ),
        'faq_heading': 'Questions to ask before renting property in Phuket',
        'faq_entries': [
            {
                'question': 'What should I check before renting in Phuket?',
                'answer': (
                    'Check lease length, deposit, advance rent, utilities, internet, maintenance responsibilities, '
                    'cleaning, pool or garden service, pet rules and deposit return terms.'
                ),
            },
            {
                'question': 'Are Phuket rentals usually short-term or long-term?',
                'answer': (
                    'Both exist. Some properties are better for holiday or seasonal stays, while others work for '
                    'long-term living. The allowed rental period must be confirmed for each property.'
                ),
            },
            {
                'question': 'Which areas are convenient for renting in Phuket?',
                'answer': (
                    'It depends on the lifestyle: Bang Tao, Kamala, Karon and Kata are beach-oriented; Rawai, '
                    'Chalong, Kathu and Phuket Town can be more practical for everyday routines.'
                ),
            },
            {
                'question': 'Can I arrange a rental remotely?',
                'answer': (
                    'Initial shortlisting and video viewing can be arranged remotely, but the exact condition, '
                    'included items and contract terms should be confirmed before payment.'
                ),
            },
            {
                'question': 'How many rentals are available on this page?',
                'answer': 'There are currently %(count)s active rental listings in this selection.',
            },
        ],
    },
    ('ru', 'type_only', 'condo', '', '', ''): {
        'heading': 'Квартиры в кондоминиумах на Пхукете',
        'page_title': 'Купить квартиру на Пхукете | Подбор и проверка объекта | Undersun Estate',
        'page_description': (
            'Сравните варианты по району, бюджету, стадии проекта, форме владения '
            'и расходам. Undersun Estate помогает выбрать подходящие варианты.'
        ),
        'answer_first': (
            'Иностранные покупатели могут владеть квартирой в тайском кондоминиуме в формате foreign freehold, '
            'если в проекте доступна иностранная квота. Перед резервированием квартиры на Пхукете нужно подтвердить '
            'квоту, титул, график платежей, common area fees, sinking fund, правила аренды и расходы при регистрации сделки.'
        ),
        'seo_heading': 'Как выбирать квартиру в кондоминиуме на Пхукете',
        'intro': (
            'В этой подборке собраны квартиры в кондоминиумах на Пхукете для жизни, отдыха и инвестиционных задач. '
            'Перед выбором важно сравнить не только цену и вид из окна, но и район, статус проекта, форму '
            'владения, квоту foreign freehold, расходы на содержание и правила аренды.'
        ),
        'highlights': [
            'Сначала определите сценарий: собственное проживание, отдых, сдача в аренду или сохранение капитала.',
            (
                'Проверьте freehold/leasehold, доступность иностранной квоты, common fee, sinking fund, правила '
                'аренды, комплектацию мебелью и условия передачи.'
            ),
            (
                'Сравнивайте пляжные районы Bang Tao, Kamala, Karon, Kata и Mai Khao с более повседневными '
                'локациями Chalong, Rawai, Kathu и Phuket Town.'
            ),
            (
                'Для строящихся кондоминиумов отдельно проверяйте репутацию застройщика, стадию строительства, график '
                'платежей и состав мебельного пакета.'
            ),
        ],
        'follow_up': (
            'Команда Undersun Estate может подготовить шорт-лист, уточнить актуальную доступность и сравнить '
            'похожие проекты перед просмотром или резервированием.'
        ),
        'faq_heading': 'Что проверить перед покупкой квартиры на Пхукете',
        'faq_entries': [
            {
                'question': 'Может ли иностранец купить квартиру на Пхукете?',
                'answer': (
                    'Да, если в конкретном кондоминиуме доступна иностранная квота freehold, либо если проект '
                    'продаётся в leasehold. Точную структуру нужно проверять по конкретному юниту.'
                ),
            },
            {
                'question': 'Что важно проверить перед покупкой квартиры?',
                'answer': (
                    'Статус проекта, форму владения, иностранную квоту, график платежей, common fee, sinking fund, '
                    'мебельный пакет, правила аренды и условия передачи.'
                ),
            },
            {
                'question': 'Какие районы Пхукета популярны для покупки квартир?',
                'answer': (
                    'Для пляжного формата часто смотрят Bang Tao, Kamala, Karon, Kata и Mai Khao. Для жизни и '
                    'повседневной логистики могут подойти Chalong, Rawai, Kathu и Phuket Town.'
                ),
            },
            {
                'question': 'Квартира на Пхукете подходит для инвестиций?',
                'answer': (
                    'Может подходить, если цена входа, управление, расходы, сезонность и правила аренды сходятся '
                    'в понятную модель. Прогноз доходности не стоит воспринимать как гарантию.'
                ),
            },
            {
                'question': 'Сколько квартир сейчас есть в этой подборке?',
                'answer': 'Сейчас в подборке %(count)s актуальных предложений квартир.',
            },
        ],
    },
    ('ru', 'deal_only', '', 'sale', '', ''): {
        'heading': 'Покупка недвижимости на Пхукете',
        'page_title': 'Купить недвижимость на Пхукете | Undersun Estate',
        'page_description': (
            'Сравните виллы, квартиры, дома и участки по районам, бюджету, цели покупки '
            'и условиям сделки.'
        ),
        'answer_first': (
            'В этом каталоге собрана недвижимость на Пхукете для покупки: кондоминиумы, виллы, таунхаусы, земля '
            'и отдельные инвестиционные объекты. Используйте его как отправную точку: доступность, структуру '
            'владения, налоги, сборы и пункты due diligence нужно подтверждать по каждому объекту до резервирования или покупки.'
        ),
        'seo_heading': 'Покупка недвижимости на Пхукете',
        'intro': (
            'Этот раздел помогает сравнить недвижимость на Пхукете для покупки: виллы, квартиры, дома, '
            'земельные участки и инвестиционные объекты. Выбор зависит от цели: жизнь, отдых, аренда, перепродажа '
            'или сохранение капитала.'
        ),
        'highlights': [
            'Сначала определите цель покупки и горизонт владения, а уже затем сравнивайте тип объекта и район.',
            (
                'Для квартир в кондоминиумах проверяйте foreign freehold quota, common fee и правила аренды; для вилл - землю, '
                'подъезд, коммуникации, управление и обслуживание.'
            ),
            (
                'Сравнивайте районы не только по расстоянию до пляжа, но и по школам, магазинам, пробкам, '
                'медицине, шуму и ликвидности.'
            ),
            (
                'Перед резервированием важно уточнить актуальную цену, статус объекта, структуру платежей, '
                'налоги/сборы и документы.'
            ),
        ],
        'follow_up': (
            'Undersun Estate помогает собрать первичный шорт-лист, сравнить похожие варианты и подготовить '
            'вопросы для проверки объекта и условий сделки.'
        ),
        'faq_heading': 'Частые вопросы о покупке недвижимости на Пхукете',
        'faq_entries': [
            {
                'question': 'С чего начать покупку недвижимости на Пхукете?',
                'answer': (
                    'Начните с цели покупки, бюджета, срока владения и формата объекта. После этого можно '
                    'сравнивать районы, юридическую структуру, расходы и ликвидность.'
                ),
            },
            {
                'question': 'Что важнее: район или тип объекта?',
                'answer': (
                    'Оба фактора важны. Район определяет образ жизни, спрос и логистику, а тип объекта влияет '
                    'на юридическую структуру, расходы, управление и сценарий аренды.'
                ),
            },
            {
                'question': 'Какие расходы могут быть помимо цены объекта?',
                'answer': (
                    'В зависимости от сделки могут быть регистрационные сборы, налоги, юридическая проверка, '
                    'common fee, sinking fund, обслуживание, мебельный пакет и расходы на управление.'
                ),
            },
            {
                'question': 'Можно ли выбрать объект удаленно?',
                'answer': (
                    'Первичный подбор и видео-просмотр можно провести удаленно. Перед оплатой важно подтвердить '
                    'актуальные условия, документы, комплектацию и состояние объекта.'
                ),
            },
            {
                'question': 'Сколько объектов на продажу сейчас есть в каталоге?',
                'answer': 'Сейчас в подборке %(count)s актуальных объектов на продажу.',
            },
        ],
    },
    ('th', 'type_only', 'condo', '', '', ''): {
        'heading': 'คอนโดในภูเก็ต',
        'page_title': 'คอนโดภูเก็ตสำหรับขาย | ตรวจโครงการและค่าใช้จ่าย | Undersun Estate',
        'page_description': (
            'เปรียบเทียบตัวเลือกตามทำเล งบประมาณ สถานะโครงการ รูปแบบการถือครอง '
            'และค่าใช้จ่าย เพื่อคัดเลือกตัวเลือกที่เหมาะสม.'
        ),
        'answer_first': (
            'ผู้ซื้อชาวต่างชาติอาจถือกรรมสิทธิ์ยูนิตคอนโดมิเนียมในไทยแบบ foreign freehold ได้ '
            'เมื่อโครงการยังมีโควตาต่างชาติ ก่อนจองคอนโดในภูเก็ตควรยืนยันโควตา สถานะเอกสารสิทธิ์ '
            'ตารางชำระเงิน ค่าส่วนกลาง เงินกองทุน กฎการปล่อยเช่า และค่าใช้จ่ายโอนกรรมสิทธิ์.'
        ),
        'seo_heading': 'การเลือกซื้อคอนโดในภูเก็ต',
        'intro': (
            'หน้านี้รวบรวมคอนโดและอพาร์ตเมนต์ในภูเก็ตสำหรับอยู่อาศัย พักผ่อน และวางแผนลงทุน '
            'ก่อนเลือกยูนิตควรเปรียบเทียบทำเล สถานะโครงการ รูปแบบการถือครอง โควตาต่างชาติ '
            'ค่าใช้จ่ายส่วนกลาง และเงื่อนไขการปล่อยเช่า.'
        ),
        'highlights': [
            'เริ่มจากเป้าหมายการซื้อ: อยู่อาศัยเอง พักผ่อน ปล่อยเช่า หรือถือครองระยะยาว.',
            (
                'ตรวจสอบ freehold/leasehold โควตาต่างชาติ ค่าส่วนกลาง เงินกองทุนส่วนกลาง '
                'กฎการปล่อยเช่า เฟอร์นิเจอร์ และเงื่อนไขส่งมอบ.'
            ),
            (
                'เปรียบเทียบทำเลชายหาด เช่น Bang Tao, Kamala, Karon, Kata และ Mai Khao '
                'กับทำเลใช้ชีวิตประจำวัน เช่น Chalong, Rawai, Kathu และ Phuket Town.'
            ),
            (
                'สำหรับคอนโดที่ยังสร้างไม่เสร็จ ควรตรวจสอบประวัติผู้พัฒนาโครงการ สถานะก่อสร้าง '
                'ตารางชำระเงิน และรายการที่รวมในแพ็กเกจเฟอร์นิเจอร์.'
            ),
        ],
        'follow_up': (
            'ทีม Undersun Estate ช่วยจัดทำ shortlist ตรวจสอบห้องว่างล่าสุด และเปรียบเทียบโครงการที่ใกล้เคียงกัน '
            'ก่อนนัดชมจริงหรือจอง.'
        ),
        'faq_heading': 'คำถามก่อนซื้อคอนโดในภูเก็ต',
        'faq_entries': [
            {
                'question': 'ชาวต่างชาติซื้อคอนโดในภูเก็ตได้หรือไม่?',
                'answer': (
                    'โดยทั่วไปสามารถพิจารณายูนิตในคอนโดมิเนียมที่มีโควตา foreign freehold หรือรูปแบบ leasehold '
                    'ตามโครงสร้างของโครงการ แต่ต้องตรวจสอบยูนิตนั้นโดยเฉพาะก่อนจอง.'
                ),
            },
            {
                'question': 'ควรตรวจสอบอะไรบ้างก่อนซื้อคอนโด?',
                'answer': (
                    'ควรตรวจสอบสถานะโครงการ รูปแบบการถือครอง โควตาต่างชาติ ตารางชำระเงิน ค่าส่วนกลาง '
                    'เงินกองทุน เฟอร์นิเจอร์ กฎการปล่อยเช่า และเงื่อนไขส่งมอบ.'
                ),
            },
            {
                'question': 'ทำเลไหนในภูเก็ตนิยมซื้อคอนโด?',
                'answer': (
                    'ผู้ซื้อที่เน้นชายหาดมักเปรียบเทียบ Bang Tao, Kamala, Karon, Kata และ Mai Khao ส่วน Chalong, '
                    'Rawai, Kathu และ Phuket Town เหมาะกับการใช้ชีวิตประจำวันมากกว่า.'
                ),
            },
            {
                'question': 'คอนโดในภูเก็ตเหมาะสำหรับลงทุนหรือไม่?',
                'answer': (
                    'อาจเหมาะได้หากราคาเริ่มต้น การบริหาร ค่าใช้จ่าย ฤดูกาล และกฎการปล่อยเช่าสอดคล้องกัน '
                    'ไม่ควรมองผลตอบแทนที่คาดการณ์ไว้เป็นการรับประกัน.'
                ),
            },
            {
                'question': 'หน้านี้มีคอนโดกี่รายการ?',
                'answer': 'ขณะนี้มีคอนโด %(count)s รายการในคัดสรรนี้.',
            },
        ],
    },
    ('th', 'type_only', 'villa', '', '', ''): {
        'heading': 'วิลล่าในภูเก็ต',
        'page_title': 'วิลล่าภูเก็ตสำหรับขาย | ทำเล ที่ดิน และสระว่ายน้ำ | Undersun Estate',
        'page_description': (
            'เปรียบเทียบตัวเลือกตามทำเล ห้องนอน ที่ดิน สระว่ายน้ำ สถานะโครงการ '
            'และเงื่อนไขการถือครอง.'
        ),
        'answer_first': (
            'วิลล่าในภูเก็ตอาจเหมาะกับการอยู่อาศัยส่วนตัว ครอบครัว หรือการถือครองเพื่อปล่อยเช่า '
            'แต่ต้องตรวจสอบเป็นรายโครงการ ก่อนจองควรยืนยันเอกสารสิทธิ์ที่ดิน โครงสร้างการถือครอง '
            'เงื่อนไข leasehold ถนนเข้าออก สาธารณูปโภค ค่าส่วนกลาง สถานะก่อสร้าง และความจำเป็นในการตรวจทางกฎหมาย.'
        ),
        'seo_heading': 'การเลือกซื้อวิลล่าในภูเก็ต',
        'intro': (
            'คัดสรรนี้ช่วยเปรียบเทียบวิลล่าสระว่ายน้ำ บ้านครอบครัว และเรสซิเดนซ์ในภูเก็ต '
            'การเลือกวิลล่าไม่ควรดูแค่ภาพและผังบ้าน แต่ต้องตรวจสอบถนนเข้าออก เอกสารสิทธิ์ที่ดิน '
            'การดูแลรักษา กฎการปล่อยเช่า และทำเลย่อยของโครงการ.'
        ),
        'highlights': [
            'แยกเป้าหมายให้ชัดเจนระหว่างอยู่อาศัยเอง บ้านพักครอบครัว บ้านพักตากอากาศ และวิลล่าสำหรับปล่อยเช่า.',
            (
                'ตรวจสอบเอกสารสิทธิ์ที่ดิน โครงสร้างการถือครอง ถนนเข้าออก สาธารณูปโภค ค่าส่วนกลาง '
                'และค่าใช้จ่ายดูแลสระกับสวนก่อนจอง.'
            ),
            (
                'เปรียบเทียบ Bang Tao, Layan, Laguna และ Kamala กับ Rawai, Chalong, Kathu และ Thalang '
                'ตามความเป็นส่วนตัว โรงเรียน ชายหาด และการเดินทางประจำวัน.'
            ),
            (
                'สำหรับวิลล่าที่ยังสร้างไม่เสร็จ ควรตรวจสอบผลงานผู้พัฒนาโครงการ สถานะก่อสร้าง ตารางชำระเงิน '
                'รายการเฟอร์นิเจอร์ และเงื่อนไขรับประกัน.'
            ),
        ],
        'follow_up': (
            'Undersun Estate ช่วยเปรียบเทียบวิลล่าที่คล้ายกัน ตรวจสอบสถานะว่างล่าสุด '
            'และเตรียมคำถามสำหรับเจ้าของหรือผู้พัฒนาโครงการก่อนนัดชม.'
        ),
        'faq_heading': 'คำถามก่อนซื้อวิลล่าในภูเก็ต',
        'faq_entries': [
            {
                'question': 'ควรตรวจสอบอะไรบ้างก่อนซื้อวิลล่าในภูเก็ต?',
                'answer': (
                    'ควรตรวจสอบเอกสารสิทธิ์ที่ดิน โครงสร้างการถือครอง ถนนเข้าออก สาธารณูปโภค ค่าส่วนกลาง '
                    'การดูแลสระและสวน กฎโครงการ สถานะก่อสร้าง และตารางชำระเงิน.'
                ),
            },
            {
                'question': 'ทำเลไหนนิยมสำหรับวิลล่าในภูเก็ต?',
                'answer': (
                    'ผู้ซื้อมักเปรียบเทียบ Bang Tao, Layan, Laguna และ Kamala สำหรับวิลล่าสไตล์รีสอร์ต ส่วน Rawai, '
                    'Chalong, Kathu และ Thalang อาจเหมาะกับชีวิตประจำวัน ครอบครัว หรือที่ดินขนาดใหญ่.'
                ),
            },
            {
                'question': 'วิลล่าดีกว่าคอนโดหรือไม่?',
                'answer': (
                    'วิลล่าให้ความเป็นส่วนตัว ที่ดิน และพื้นที่ภายนอกมากกว่า แต่ต้องตรวจสอบเรื่องที่ดิน '
                    'การดูแลรักษา ทางเข้าออก และการบริหารมากขึ้น รูปแบบที่เหมาะขึ้นอยู่กับเป้าหมาย.'
                ),
            },
            {
                'question': 'วิลล่าในภูเก็ตปล่อยเช่าได้หรือไม่?',
                'answer': (
                    'บางวิลล่าสามารถปล่อยเช่าได้ แต่ผลลัพธ์ขึ้นอยู่กับทำเล การบริหาร ฤดูกาล ราคา ค่าใช้จ่าย '
                    'และกฎของโครงการ ไม่ควรมองผลตอบแทนที่คาดการณ์ไว้เป็นการรับประกัน.'
                ),
            },
            {
                'question': 'หน้านี้มีวิลล่ากี่รายการ?',
                'answer': 'ขณะนี้มีวิลล่า %(count)s รายการในคัดสรรนี้.',
            },
        ],
    },
    ('th', 'type_only', 'townhouse', '', '', ''): {
        'heading': 'ทาวน์เฮาส์สำหรับครอบครัวในภูเก็ต',
        'page_title': 'ทาวน์เฮาส์ภูเก็ตสำหรับขาย | บ้านสำหรับครอบครัว | Undersun Estate',
        'page_description': (
            'เปรียบเทียบตัวเลือกตามทำเล จำนวนห้องนอน พื้นที่ใช้สอย กฎโครงการ '
            'และงบประมาณ.'
        ),
        'seo_heading': 'การเลือกซื้อทาวน์เฮาส์ในภูเก็ต',
        'intro': (
            'คัดสรรนี้ช่วยเปรียบเทียบทาวน์เฮาส์ในภูเก็ตสำหรับครอบครัว การย้ายมาอยู่อาศัย '
            'และการถือครองระยะยาว ทาวน์เฮาส์มักให้พื้นที่มากกว่าคอนโด และดูแลง่ายกว่าวิลล่าส่วนตัว.'
        ),
        'highlights': [
            'ตรวจสอบความเหมาะสมกับชีวิตประจำวัน: ที่จอดรถ ทางเข้าออก พื้นที่เก็บของ จำนวนห้องนอน และพื้นที่ภายนอก.',
            (
                'ตรวจสอบโครงสร้างการถือครอง กฎโครงการ ค่าส่วนกลาง ความรับผิดชอบในการดูแลรักษา '
                'สาธารณูปโภค และสิ่งที่รวมอยู่ในราคา.'
            ),
            (
                'เปรียบเทียบ Chalong, Rawai, Kathu, Phuket Town และบางส่วนของ Thalang ตามโรงเรียน '
                'ซูเปอร์มาร์เก็ต โรงพยาบาล และเวลาเดินทาง.'
            ),
            (
                'หากซื้อเพื่อปล่อยเช่าหรือขายต่อ ควรดูสภาพโครงการ ทรัพย์คู่แข่งใกล้เคียง คุณภาพการบริหาร '
                'และความต้องการระยะยาว.'
            ),
        ],
        'follow_up': (
            'Undersun Estate ช่วยเปรียบเทียบทาวน์เฮาส์กับวิลล่าและคอนโด ตรวจสอบสถานะว่างล่าสุด '
            'และเตรียมคำถามก่อนนัดชม.'
        ),
        'faq_heading': 'คำถามก่อนซื้อทาวน์เฮาส์ในภูเก็ต',
        'faq_entries': [
            {
                'question': 'ทาวน์เฮาส์เป็นทางเลือกแทนวิลล่าได้หรือไม่?',
                'answer': (
                    'ได้ในหลายกรณี ทาวน์เฮาส์มักมีพื้นที่มากกว่าคอนโดและดูแลง่ายกว่าวิลล่าส่วนตัว '
                    'แต่ต้องตรวจสอบทางเข้า กฎโครงการ ค่าส่วนกลาง และความเป็นส่วนตัว.'
                ),
            },
            {
                'question': 'ควรตรวจสอบอะไรบ้างก่อนซื้อทาวน์เฮาส์?',
                'answer': (
                    'ควรตรวจสอบโครงสร้างการถือครอง กฎโครงการ ค่าส่วนกลาง ที่จอดรถ ทางเข้าออก '
                    'สาธารณูปโภค สภาพอาคาร การดูแลรักษา และข้อจำกัดการปล่อยเช่า.'
                ),
            },
            {
                'question': 'ทำเลไหนเหมาะกับทาวน์เฮาส์ในภูเก็ต?',
                'answer': (
                    'ผู้ซื้อทาวน์เฮาส์มักเปรียบเทียบ Chalong, Rawai, Kathu, Phuket Town และบางส่วนของ Thalang '
                    'ซึ่งสะดวกต่อโรงเรียน ซูเปอร์มาร์เก็ต และถนนหลัก.'
                ),
            },
            {
                'question': 'ทาวน์เฮาส์ดีกว่าคอนโดหรือไม่?',
                'answer': (
                    'ทาวน์เฮาส์ให้พื้นที่ใช้สอย ที่จอดรถ และความเป็นส่วนตัวมากกว่า ส่วนคอนโดอาจดูแลง่ายกว่า '
                    'และมีสิ่งอำนวยความสะดวกแบบรีสอร์ตมากกว่า.'
                ),
            },
            {
                'question': 'หน้านี้มีทาวน์เฮาส์กี่รายการ?',
                'answer': 'ขณะนี้มีทาวน์เฮาส์ %(count)s รายการในคัดสรรนี้.',
            },
        ],
    },
    ('th', 'type_only', 'land', '', '', ''): {
        'heading': 'ที่ดินและแปลงพัฒนาในภูเก็ต',
        'page_title': 'ที่ดินภูเก็ตสำหรับขาย | ตรวจเอกสารสิทธิ์และสภาพแปลง | Undersun Estate',
        'page_description': (
            'เปรียบเทียบตัวเลือกตามทำเล ขนาด ทางเข้า เอกสารสิทธิ์ สาธารณูปโภค ข้อจำกัดการก่อสร้าง '
            'และความเหมาะสมของโครงการ.'
        ),
        'seo_heading': 'การตรวจสอบที่ดินก่อนซื้อในภูเก็ต',
        'intro': (
            'คัดสรรนี้เหมาะสำหรับผู้ซื้อที่พิจารณาก่อสร้าง พัฒนาโครงการ หรือถือครองที่ดินระยะยาวในภูเก็ต '
            'การเลือกแปลงควรดูทั้งเอกสาร ทางเข้า สาธารณูปโภค และสภาพพื้นที่จริง ไม่ใช่เพียงขนาดและราคา.'
        ),
        'highlights': [
            'ตรวจสอบเอกสารสิทธิ์ แนวเขต ทางเข้า สาธารณูปโภค ความลาดชัน การระบายน้ำ และความเหมาะสมในการก่อสร้าง.',
            (
                'พิจารณาข้อจำกัดการก่อสร้าง สภาพแวดล้อม ความกว้างถนน ไฟฟ้า น้ำ สภาพดิน '
                'และเส้นทางจริงจากถนนหลัก.'
            ),
            (
                'หากซื้อเพื่อสร้างวิลล่าหรือพัฒนาโครงการ ควรเทียบกับแบบ งบประมาณ ใบอนุญาต '
                'และแผนการขายต่อหรือถือครอง.'
            ),
            'สำหรับผู้ซื้อต่างชาติ โครงสร้างทางกฎหมายต้องได้รับการตรวจสอบแยกต่างหากก่อนชำระเงิน.',
        ],
        'follow_up': (
            'Undersun Estate ช่วยคัดเลือกแปลง ขอเอกสารหลัก และเตรียมรายการตรวจสอบก่อนลงพื้นที่จริง.'
        ),
        'faq_heading': 'คำถามก่อนซื้อที่ดินในภูเก็ต',
        'faq_entries': [
            {
                'question': 'ควรตรวจสอบอะไรบ้างก่อนซื้อที่ดินในภูเก็ต?',
                'answer': (
                    'ควรตรวจสอบเอกสารสิทธิ์ แนวเขต ทางเข้า สาธารณูปโภค ความลาดชัน การระบายน้ำ '
                    'ข้อจำกัดการก่อสร้าง พื้นที่รอบข้าง และโครงสร้างทางกฎหมายของผู้ซื้อ.'
                ),
            },
            {
                'question': 'ที่ดินทุกแปลงเหมาะกับการสร้างวิลล่าหรือไม่?',
                'answer': (
                    'ไม่เสมอไป ความเหมาะสมขึ้นอยู่กับเอกสารสิทธิ์ ทางเข้า สาธารณูปโภค ความลาดชัน '
                    'กฎการก่อสร้าง งบประมาณ ใบอนุญาต และสภาพพื้นที่จริง.'
                ),
            },
            {
                'question': 'ชาวต่างชาติซื้อที่ดินในไทยโดยตรงได้หรือไม่?',
                'answer': (
                    'การถือครองที่ดินโดยชาวต่างชาติมีข้อจำกัด จึงต้องตรวจโครงสร้างทางกฎหมายก่อน '
                    'และไม่ควรใช้โครงสร้างที่ไม่ชัดเจนหรือพึ่งพานอมินี.'
                ),
            },
            {
                'question': 'หน้านี้มีที่ดินกี่รายการ?',
                'answer': 'ขณะนี้มีรายการที่ดิน %(count)s รายการในคัดสรรนี้.',
            },
        ],
    },
    ('ru', 'deal_only', '', 'rent', '', ''): {
        'heading': 'Подбор аренды на Пхукете',
        'page_title': 'Аренда на Пхукете | Виллы, квартиры и дома | Undersun Estate',
        'page_description': (
            'Сравните варианты по району, типу объекта, спальням, бюджету и условиям договора. '
            'Виллы, квартиры и дома для жизни или отдыха.'
        ),
        'seo_heading': 'Как выбирать аренду на Пхукете',
        'intro': (
            'Этот раздел помогает сравнить виллы, квартиры и дома в аренду на Пхукете по району, '
            'бюджету и бытовым условиям. Перед выбором важно уточнить срок аренды, депозит, коммунальные платежи, '
            'ответственность за обслуживание и что входит в стоимость.'
        ),
        'highlights': [
            'Сначала определите сценарий: короткий отпуск, сезонная аренда, долгосрочная жизнь или релокация.',
            (
                'Проверьте депозит, предоплату, тарифы на воду и электричество, интернет, уборку, обслуживание '
                'бассейна и сада, правила с животными и условия досрочного выезда.'
            ),
            (
                'Сравнивайте пляжные районы с повседневными локациями: школы, магазины, спортзалы, медицина '
                'и основные дороги могут быть важнее расстояния до моря.'
            ),
            'Для удалённого подбора запрашивайте актуальные фото, видео-просмотр и письменный список того, что включено.',
        ],
        'follow_up': (
            'Undersun Estate помогает уточнить актуальную доступность, согласовать время просмотра и проверить '
            'условия аренды до поездки на объект.'
        ),
        'faq_heading': 'Что проверить перед арендой недвижимости на Пхукете',
        'faq_entries': [
            {
                'question': 'Что важно проверить перед арендой на Пхукете?',
                'answer': (
                    'Срок аренды, депозит, предоплату, коммунальные платежи, интернет, обслуживание, уборку, '
                    'правила с животными, условия возврата депозита и досрочного выезда.'
                ),
            },
            {
                'question': 'На Пхукете чаще ищут краткосрочную или долгосрочную аренду?',
                'answer': (
                    'Есть оба сценария. Одни объекты лучше подходят для отпуска или сезона, другие - для '
                    'долгосрочной жизни. Разрешённый срок аренды нужно подтверждать по конкретному объекту.'
                ),
            },
            {
                'question': 'Какие районы удобны для аренды на Пхукете?',
                'answer': (
                    'Для пляжного формата часто смотрят Bang Tao, Kamala, Karon и Kata. Для повседневной жизни '
                    'могут быть удобны Rawai, Chalong, Kathu и Phuket Town.'
                ),
            },
            {
                'question': 'Можно ли подобрать аренду удалённо?',
                'answer': (
                    'Первичный подбор и видео-просмотр можно организовать удалённо, но состояние объекта, '
                    'комплектацию и договорные условия нужно подтвердить до оплаты.'
                ),
            },
            {
                'question': 'Сколько объектов в аренду сейчас есть в подборке?',
                'answer': 'Сейчас в подборке %(count)s актуальных объектов в аренду.',
            },
        ],
    },
    ('th', 'deal_only', '', 'rent', '', ''): {
        'heading': 'การเช่าอสังหาริมทรัพย์ในภูเก็ต',
        'page_title': 'เช่าอสังหาริมทรัพย์ภูเก็ต | วิลล่า คอนโด และบ้าน | Undersun Estate',
        'page_description': (
            'ค้นหาตัวเลือกตามทำเล ประเภท จำนวนห้องนอน งบประมาณ '
            'และเงื่อนไขสัญญาเช่า.'
        ),
        'seo_heading': 'การเลือกเช่าอสังหาริมทรัพย์ในภูเก็ต',
        'intro': (
            'คัดสรรนี้ช่วยเปรียบเทียบวิลล่า คอนโด ทาวน์เฮาส์ และบ้านให้เช่าในภูเก็ตตามทำเล งบประมาณ '
            'และเงื่อนไขการอยู่อาศัย ก่อนเลือกทรัพย์ควรยืนยันระยะเวลาเช่า เงินมัดจำ ค่าสาธารณูปโภค '
            'ความรับผิดชอบในการดูแลรักษา และสิ่งที่รวมอยู่ในค่าเช่า.'
        ),
        'highlights': [
            'กำหนดรูปแบบการเช่าก่อน: พักผ่อนระยะสั้น เช่าตามฤดูกาล อยู่อาศัยระยะยาว หรือย้ายถิ่นฐาน.',
            (
                'ตรวจสอบเงินมัดจำ ค่าเช่าล่วงหน้า ค่าน้ำไฟ อินเทอร์เน็ต ทำความสะอาด บริการสระและสวน '
                'กฎเกี่ยวกับสัตว์เลี้ยง และเงื่อนไขยกเลิกก่อนกำหนด.'
            ),
            (
                'เปรียบเทียบทำเลชายหาดกับทำเลใช้ชีวิตประจำวัน เพราะโรงเรียน ซูเปอร์มาร์เก็ต ฟิตเนส '
                'โรงพยาบาล และถนนหลักอาจสำคัญกว่าระยะทางถึงทะเล.'
            ),
            'หากเลือกจากระยะไกล ควรขอรูปปัจจุบัน วิดีโอชมทรัพย์ และรายการสิ่งที่รวมอยู่ในสัญญาเป็นลายลักษณ์อักษร.',
        ],
        'follow_up': (
            'Undersun Estate ช่วยตรวจสอบสถานะว่างล่าสุด นัดหมายเข้าชม และยืนยันเงื่อนไขสัญญาเช่าก่อนเดินทางไปดูทรัพย์.'
        ),
        'faq_heading': 'คำถามก่อนเช่าอสังหาริมทรัพย์ในภูเก็ต',
        'faq_entries': [
            {
                'question': 'ควรตรวจสอบอะไรบ้างก่อนเช่าในภูเก็ต?',
                'answer': (
                    'ควรตรวจสอบระยะเวลาเช่า เงินมัดจำ ค่าเช่าล่วงหน้า ค่าน้ำไฟ อินเทอร์เน็ต การดูแลรักษา '
                    'ทำความสะอาด บริการสระหรือสวน กฎสัตว์เลี้ยง และเงื่อนไขคืนเงินมัดจำ.'
                ),
            },
            {
                'question': 'การเช่าในภูเก็ตเป็นระยะสั้นหรือระยะยาว?',
                'answer': (
                    'มีทั้งสองแบบ บางทรัพย์เหมาะกับวันหยุดหรือฤดูกาลท่องเที่ยว บางทรัพย์เหมาะกับการอยู่ระยะยาว '
                    'ต้องยืนยันระยะเวลาที่อนุญาตสำหรับทรัพย์แต่ละรายการ.'
                ),
            },
            {
                'question': 'ทำเลไหนเหมาะกับการเช่าในภูเก็ต?',
                'answer': (
                    'ขึ้นอยู่กับไลฟ์สไตล์ Bang Tao, Kamala, Karon และ Kata เน้นชายหาด ส่วน Rawai, Chalong, Kathu '
                    'และ Phuket Town อาจสะดวกกว่าสำหรับชีวิตประจำวัน.'
                ),
            },
            {
                'question': 'สามารถเลือกเช่าจากระยะไกลได้หรือไม่?',
                'answer': (
                    'สามารถเริ่มคัดเลือกและชมวิดีโอจากระยะไกลได้ แต่ควรยืนยันสภาพทรัพย์ สิ่งที่รวมอยู่ '
                    'และเงื่อนไขสัญญาก่อนชำระเงิน.'
                ),
            },
            {
                'question': 'หน้านี้มีทรัพย์ให้เช่ากี่รายการ?',
                'answer': 'ขณะนี้มีรายการให้เช่า %(count)s รายการในคัดสรรนี้.',
            },
        ],
    },
    ('en', 'deal_only', '', 'sale', '', ''): {
        'heading': 'Buying property in Phuket',
        'page_title': 'Property for Sale in Phuket | Villas, Condos and Land | Undersun Estate',
        'page_description': (
            'Compare Phuket listings across villas, condos, townhouses and land. Shortlist by area, budget, '
            'purchase goal and deal terms.'
        ),
        'answer_first': (
            'This catalog lists Phuket properties for sale, including condos, villas, townhouses, land and selected '
            'investment properties. Use it as a starting point: availability, ownership structure, taxes, fees and '
            'due-diligence items must be confirmed for each property before reservation or purchase.'
        ),
        'seo_heading': 'Buying property in Phuket',
        'intro': (
            'This section helps compare Phuket property for sale, including villas, condos, townhouses, land plots '
            'and selected investment properties. The right option depends on the goal: living, holiday use, rental, '
            'resale potential or long-term capital preservation.'
        ),
        'highlights': [
            'Start with the purchase goal and holding period before comparing property type and area.',
            (
                'For condos, check foreign freehold quota, common area fees and rental rules; for villas, check land, '
                'road access, utilities, management and maintenance.'
            ),
            (
                'Compare districts by more than beach distance: schools, shops, traffic, medical access, noise and '
                'resale liquidity can change the decision.'
            ),
            (
                'Before reservation, confirm current price, availability, payment structure, taxes, fees and documents.'
            ),
        ],
        'follow_up': (
            'Undersun Estate helps prepare a shortlist, compare similar options and organize the questions needed '
            'for property and deal checks.'
        ),
        'faq_heading': 'Questions about buying property in Phuket',
        'faq_entries': [
            {
                'question': 'Where should I start when buying property in Phuket?',
                'answer': (
                    'Start with the purchase goal, budget, holding period and preferred property format. Then compare '
                    'areas, ownership structure, running costs and liquidity.'
                ),
            },
            {
                'question': 'Is area or property type more important?',
                'answer': (
                    'Both matter. Area affects lifestyle, demand and daily logistics, while property type affects '
                    'ownership structure, running costs, management and rental scenario.'
                ),
            },
            {
                'question': 'What costs can be added to the property price?',
                'answer': (
                    'Depending on the deal, costs may include registration fees, taxes, legal checks, common area fees, '
                    'sinking fund, maintenance, furniture package and management costs.'
                ),
            },
            {
                'question': 'Can I shortlist Phuket property remotely?',
                'answer': (
                    'Initial shortlisting and video viewing can be done remotely. Before payment, current terms, '
                    'documents, included items and property condition should be confirmed.'
                ),
            },
            {
                'question': 'How many sale listings are available in the catalogue?',
                'answer': 'There are currently %(count)s active sale listings in this selection.',
            },
        ],
    },
    ('th', 'deal_only', '', 'sale', '', ''): {
        'heading': 'การซื้ออสังหาริมทรัพย์ในภูเก็ต',
        'page_title': 'อสังหาริมทรัพย์ภูเก็ตสำหรับขาย | วิลล่า คอนโด และที่ดิน | Undersun Estate',
        'page_description': (
            'เปรียบเทียบตัวเลือกทั้งวิลล่า คอนโด ทาวน์เฮาส์ และที่ดิน '
            'ตามทำเล งบประมาณ เป้าหมายการซื้อ และเงื่อนไขดีล.'
        ),
        'answer_first': (
            'แค็ตตาล็อกนี้รวบรวมอสังหาริมทรัพย์ภูเก็ตสำหรับขาย รวมถึงคอนโด วิลล่า ทาวน์เฮาส์ ที่ดิน '
            'และทรัพย์เพื่อการลงทุนบางรายการ ใช้เป็นจุดเริ่มต้นในการเปรียบเทียบ โดยต้องยืนยันสถานะว่าง '
            'โครงสร้างการถือครอง ภาษี ค่าธรรมเนียม และรายการตรวจสอบ due diligence ของแต่ละทรัพย์ก่อนจองหรือซื้อ.'
        ),
        'seo_heading': 'การซื้ออสังหาริมทรัพย์ในภูเก็ต',
        'intro': (
            'หน้านี้ช่วยเปรียบเทียบอสังหาริมทรัพย์ในภูเก็ตสำหรับซื้อ ทั้งวิลล่า คอนโด ทาวน์เฮาส์ '
            'ที่ดิน และทรัพย์เพื่อการลงทุนบางรายการ ตัวเลือกที่เหมาะขึ้นอยู่กับเป้าหมาย เช่น อยู่อาศัย '
            'พักผ่อน ปล่อยเช่า ขายต่อ หรือถือครองระยะยาว.'
        ),
        'highlights': [
            'เริ่มจากเป้าหมายการซื้อและระยะเวลาถือครอง ก่อนเปรียบเทียบประเภททรัพย์และทำเล.',
            (
                'สำหรับคอนโดควรตรวจสอบโควตาต่างชาติ ค่าส่วนกลาง และกฎการปล่อยเช่า; สำหรับวิลล่าควรตรวจสอบที่ดิน '
                'ทางเข้า สาธารณูปโภค การบริหาร และการดูแลรักษา.'
            ),
            (
                'เปรียบเทียบพื้นที่ไม่ใช่แค่ระยะทางถึงชายหาด แต่รวมถึงโรงเรียน ร้านค้า การจราจร การแพทย์ '
                'เสียงรบกวน และสภาพคล่องในการขายต่อ.'
            ),
            (
                'ก่อนจองควรยืนยันราคาปัจจุบัน สถานะทรัพย์ โครงสร้างการชำระเงิน ภาษี ค่าธรรมเนียม และเอกสาร.'
            ),
        ],
        'follow_up': (
            'Undersun Estate ช่วยจัดทำ shortlist เปรียบเทียบตัวเลือกใกล้เคียง และเตรียมคำถามสำหรับตรวจสอบทรัพย์และเงื่อนไขดีล.'
        ),
        'faq_heading': 'คำถามเกี่ยวกับการซื้ออสังหาริมทรัพย์ในภูเก็ต',
        'faq_entries': [
            {
                'question': 'ควรเริ่มจากอะไรเมื่อซื้ออสังหาริมทรัพย์ในภูเก็ต?',
                'answer': (
                    'เริ่มจากเป้าหมายการซื้อ งบประมาณ ระยะเวลาถือครอง และประเภททรัพย์ที่ต้องการ '
                    'จากนั้นจึงเปรียบเทียบทำเล โครงสร้างการถือครอง ค่าใช้จ่าย และสภาพคล่อง.'
                ),
            },
            {
                'question': 'ทำเลหรือประเภททรัพย์สำคัญกว่ากัน?',
                'answer': (
                    'สำคัญทั้งสองด้าน ทำเลมีผลต่อไลฟ์สไตล์ ความต้องการ และการเดินทางประจำวัน '
                    'ส่วนประเภททรัพย์มีผลต่อโครงสร้างการถือครอง ค่าใช้จ่าย การบริหาร และรูปแบบการปล่อยเช่า.'
                ),
            },
            {
                'question': 'มีค่าใช้จ่ายอะไรนอกเหนือจากราคาทรัพย์?',
                'answer': (
                    'ขึ้นอยู่กับดีล อาจมีค่าธรรมเนียมจดทะเบียน ภาษี ค่าตรวจเอกสาร ค่าส่วนกลาง เงินกองทุน '
                    'ค่าบำรุงรักษา แพ็กเกจเฟอร์นิเจอร์ และค่าใช้จ่ายการบริหาร.'
                ),
            },
            {
                'question': 'สามารถคัดเลือกทรัพย์จากระยะไกลได้หรือไม่?',
                'answer': (
                    'สามารถเริ่มคัดเลือกและชมวิดีโอจากระยะไกลได้ แต่ก่อนชำระเงินควรยืนยันเงื่อนไขล่าสุด '
                    'เอกสาร รายการที่รวมอยู่ และสภาพทรัพย์.'
                ),
            },
            {
                'question': 'หน้านี้มีทรัพย์สำหรับขายกี่รายการ?',
                'answer': 'ขณะนี้มีรายการขาย %(count)s รายการในคัดสรรนี้.',
            },
        ],
    },
}

PROPERTY_DETAIL_CONTEXT_TEXTS = {
    'ru': {
        'freshness_updated_label': 'Цена и статус обновлены',
        'freshness_status_label': 'Статус',
        'freshness_note': 'Перед просмотром или резервированием подтвердим актуальные условия у владельца или застройщика.',
        'trust_eyebrow': 'Ответственный специалист',
        'trust_note': 'Отвечает за актуальность цены, статуса и организацию просмотра этого объекта.',
        'trust_languages_label': 'Языки',
        'trust_profile_label': 'О специалисте',
        'context_heading': 'Полезные ссылки по этому объекту',
        'context_description': 'Сравните похожие предложения, изучите локацию и связанные услуги Undersun Estate.',
        'catalog_link_label': '{property_type} в {location}',
        'catalog_link_description': 'Похожие объекты этого типа в выбранной локации.',
        'location_link_label': 'Недвижимость в {location}',
        'location_link_description': 'Обзор локации и актуальные объекты рядом.',
        'buying_service_label': 'Сопровождение покупки',
        'buying_service_description': 'Проверка объекта, документов и условий сделки.',
        'renting_service_label': 'Сопровождение аренды',
        'renting_service_description': 'Подбор, согласование условий и организация заселения.',
        'land_service_label': 'Сделки с землей',
        'land_service_description': 'Проверка участка, титула, доступа и ограничений.',
        'legal_service_label': 'Юридическая проверка',
        'legal_service_description': 'Документы, структура сделки и риски до оплаты.',
        'same_complex_eyebrow': 'В этом комплексе',
        'same_complex_heading': 'Другие объекты в {complex}',
        'same_complex_description': 'В этом комплексе есть несколько доступных вариантов. Сравните их по спальням, площади и бюджету, чтобы быстрее понять, какой объект подходит под вашу задачу.',
        'same_complex_stats_label': 'Краткое сравнение объектов в комплексе',
        'same_complex_count_one': 'объект в проекте',
        'same_complex_count_few': 'объекта в проекте',
        'same_complex_count_many': 'объектов в проекте',
        'same_complex_bedroom_one': 'спальня',
        'same_complex_bedroom_few': 'спальни',
        'same_complex_bedroom_many': 'спален',
        'same_complex_area_label': 'площадь',
        'same_complex_price_label': 'бюджет',
        'same_complex_from_price': 'от {price}',
    },
    'en': {
        'freshness_updated_label': 'Price and status updated',
        'freshness_status_label': 'Status',
        'freshness_note': 'Before a viewing or reservation, we confirm the latest terms with the owner or developer.',
        'trust_eyebrow': 'Responsible specialist',
        'trust_note': 'Responsible for confirming price, status, and arranging the viewing for this property.',
        'trust_languages_label': 'Languages',
        'trust_profile_label': 'About specialist',
        'context_heading': 'Useful links for this property',
        'context_description': 'Compare similar listings, explore the area, and review related Undersun Estate services.',
        'catalog_link_label': '{property_type} in {location}',
        'catalog_link_description': 'Similar properties of this type in the selected area.',
        'location_link_label': 'Property in {location}',
        'location_link_description': 'Area overview and active listings nearby.',
        'buying_service_label': 'Purchase support',
        'buying_service_description': 'Property checks, documents, and transaction terms.',
        'renting_service_label': 'Rental support',
        'renting_service_description': 'Shortlisting, terms negotiation, and move-in coordination.',
        'land_service_label': 'Land transactions',
        'land_service_description': 'Land title, access, boundaries, and restrictions checks.',
        'legal_service_label': 'Legal review',
        'legal_service_description': 'Documents, transaction structure, and risk review before payment.',
        'same_complex_eyebrow': 'Same project',
        'same_complex_heading': 'Other listings in {complex}',
        'same_complex_description': 'This project has several active options. Compare bedrooms, area and budget before choosing the unit that fits your brief.',
        'same_complex_stats_label': 'Quick comparison for this project',
        'same_complex_count_one': 'listing in project',
        'same_complex_count_few': 'listings in project',
        'same_complex_count_many': 'listings in project',
        'same_complex_bedroom_one': 'bedroom',
        'same_complex_bedroom_few': 'bedrooms',
        'same_complex_bedroom_many': 'bedrooms',
        'same_complex_area_label': 'area',
        'same_complex_price_label': 'budget',
        'same_complex_from_price': 'from {price}',
    },
    'th': {
        'freshness_updated_label': 'ราคาและสถานะอัปเดตแล้ว',
        'freshness_status_label': 'สถานะ',
        'freshness_note': 'ก่อนนัดชมทรัพย์หรือจอง เราจะยืนยันเงื่อนไขล่าสุดกับเจ้าของหรือผู้พัฒนาโครงการอีกครั้ง',
        'trust_eyebrow': 'ผู้เชี่ยวชาญที่รับผิดชอบ',
        'trust_note': 'รับผิดชอบการยืนยันราคา สถานะ และการนัดชมทรัพย์นี้',
        'trust_languages_label': 'ภาษา',
        'trust_profile_label': 'เกี่ยวกับผู้เชี่ยวชาญ',
        'context_heading': 'ลิงก์ที่เป็นประโยชน์สำหรับทรัพย์นี้',
        'context_description': 'เปรียบเทียบรายการใกล้เคียง ดูข้อมูลทำเล และบริการที่เกี่ยวข้องของ Undersun Estate',
        'catalog_link_label': '{property_type} ใน {location}',
        'catalog_link_description': 'ทรัพย์ประเภทเดียวกันในทำเลที่เลือก',
        'location_link_label': 'อสังหาริมทรัพย์ใน {location}',
        'location_link_description': 'ข้อมูลทำเลและรายการที่พร้อมอยู่ใกล้เคียง',
        'buying_service_label': 'บริการช่วยซื้อ',
        'buying_service_description': 'ตรวจทรัพย์ เอกสาร และเงื่อนไขการซื้อขาย',
        'renting_service_label': 'บริการช่วยเช่า',
        'renting_service_description': 'คัดเลือกทรัพย์ เจรจาเงื่อนไข และประสานการย้ายเข้า',
        'land_service_label': 'ธุรกรรมที่ดิน',
        'land_service_description': 'ตรวจเอกสารสิทธิ์ ทางเข้าออก แนวเขต และข้อจำกัด',
        'legal_service_label': 'ตรวจเอกสารทางกฎหมาย',
        'legal_service_description': 'เอกสาร โครงสร้างดีล และความเสี่ยงก่อนชำระเงิน',
        'same_complex_eyebrow': 'โครงการเดียวกัน',
        'same_complex_heading': 'รายการอื่นใน {complex}',
        'same_complex_description': 'โครงการนี้มีตัวเลือกที่ยังพร้อมอยู่หลายรายการ เปรียบเทียบจำนวนห้องนอน พื้นที่ และงบประมาณก่อนเลือกยูนิตที่เหมาะกับเป้าหมายของคุณ',
        'same_complex_stats_label': 'สรุปเปรียบเทียบโครงการนี้',
        'same_complex_count_one': 'รายการในโครงการ',
        'same_complex_count_few': 'รายการในโครงการ',
        'same_complex_count_many': 'รายการในโครงการ',
        'same_complex_bedroom_one': 'ห้องนอน',
        'same_complex_bedroom_few': 'ห้องนอน',
        'same_complex_bedroom_many': 'ห้องนอน',
        'same_complex_area_label': 'พื้นที่',
        'same_complex_price_label': 'งบประมาณ',
        'same_complex_from_price': 'เริ่มที่ {price}',
    },
}


CATALOG_INTERNAL_TYPE_LABELS = {
    'en': {
        '': {
            'condo': 'Phuket condos for sale',
            'villa': 'Phuket villas for sale',
            'townhouse': 'Phuket townhouses for sale',
            'land': 'Land for sale in Phuket',
        },
        'sale': {
            'condo': 'Phuket condos for sale',
            'villa': 'Phuket villas for sale',
            'townhouse': 'Phuket townhouses for sale',
            'land': 'Land for sale in Phuket',
        },
        'rent': {
            'condo': 'Phuket condos for rent',
            'villa': 'Phuket villas for rent',
            'townhouse': 'Phuket townhouses for rent',
        },
    },
    'ru': {
        '': {
            'condo': 'Квартиры на Пхукете на продажу',
            'villa': 'Виллы на Пхукете на продажу',
            'townhouse': 'Дома на Пхукете на продажу',
            'land': 'Земля на Пхукете на продажу',
        },
        'sale': {
            'condo': 'Квартиры на Пхукете на продажу',
            'villa': 'Виллы на Пхукете на продажу',
            'townhouse': 'Дома на Пхукете на продажу',
            'land': 'Земля на Пхукете на продажу',
        },
        'rent': {
            'condo': 'Квартиры на Пхукете в аренду',
            'villa': 'Виллы на Пхукете в аренду',
            'townhouse': 'Дома на Пхукете в аренду',
        },
    },
    'th': {
        '': {
            'condo': 'คอนโดภูเก็ตสำหรับขาย',
            'villa': 'วิลล่าภูเก็ตสำหรับขาย',
            'townhouse': 'ทาวน์เฮาส์ภูเก็ตสำหรับขาย',
            'land': 'ที่ดินภูเก็ตสำหรับขาย',
        },
        'sale': {
            'condo': 'คอนโดภูเก็ตสำหรับขาย',
            'villa': 'วิลล่าภูเก็ตสำหรับขาย',
            'townhouse': 'ทาวน์เฮาส์ภูเก็ตสำหรับขาย',
            'land': 'ที่ดินภูเก็ตสำหรับขาย',
        },
        'rent': {
            'condo': 'คอนโดภูเก็ตสำหรับเช่า',
            'villa': 'วิลล่าภูเก็ตสำหรับเช่า',
            'townhouse': 'ทาวน์เฮาส์ภูเก็ตสำหรับเช่า',
        },
    },
}


def _normalize_whitespace(value):
    if not isinstance(value, str):
        return value
    return ' '.join(value.split())


@lru_cache(maxsize=1)
def _load_phuket_district_boundaries():
    if not PHUKET_DISTRICT_BOUNDARIES_PATH.exists():
        return {}

    with PHUKET_DISTRICT_BOUNDARIES_PATH.open(encoding='utf-8') as geojson_file:
        payload = json.load(geojson_file)

    boundaries = {}
    for feature in payload.get('features', []):
        properties = feature.get('properties') or {}
        slug = properties.get('slug')
        if not slug:
            continue
        boundaries[slug] = feature

    return boundaries


def _get_translated_attr(instance, field_name, language_code='ru', fallback=''):
    if instance is None:
        return fallback

    localized_field_name = field_name if language_code == 'ru' else f'{field_name}_{language_code}'
    localized_value = getattr(instance, localized_field_name, None)
    base_value = getattr(instance, field_name, None)
    value = localized_value or base_value or fallback
    return _normalize_whitespace(value)


def _get_explicit_translated_attr(instance, field_name, language_code='ru'):
    if instance is None:
        return ''

    localized_field_name = field_name if language_code == 'ru' else f'{field_name}_{language_code}'
    return _normalize_whitespace(getattr(instance, localized_field_name, None) or '')


def _strip_property_title_suffix(value):
    value = _normalize_whitespace(value or '')
    for separator in (' | ', ' — ', ' – '):
        if separator in value:
            return _normalize_whitespace(value.split(separator, 1)[0])
    return value


def _build_property_display_title(property_obj, language_code='ru'):
    localized_getter = getattr(property_obj, 'get_localized_display_title', None)
    if callable(localized_getter):
        return localized_getter(language_code)

    language_code = (language_code or 'ru')[:2]
    explicit_title = _get_explicit_translated_attr(property_obj, 'title', language_code)
    if explicit_title:
        return explicit_title

    if language_code != 'ru':
        generated_title = property_obj.generate_auto_seo(language_code).get('title', '')
        generated_heading = _strip_property_title_suffix(generated_title)
        if generated_heading:
            return generated_heading

    return _normalize_whitespace(property_obj.title)


def _build_property_schema_description(property_obj, language_code='ru'):
    language_code = (language_code or 'ru')[:2]
    for field_name in ('short_description', 'description'):
        explicit_value = _get_explicit_translated_attr(property_obj, field_name, language_code)
        plain_value = _normalize_whitespace(strip_tags(explicit_value or ''))
        if plain_value:
            return truncate_meta(plain_value)

    if language_code != 'ru':
        generated_description = property_obj.generate_auto_seo(language_code).get('description', '')
        if generated_description:
            return truncate_meta(generated_description)

    fallback = _normalize_whitespace(strip_tags(property_obj.short_description or property_obj.description or ''))
    return truncate_meta(fallback)


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


PROJECT_NAME_SUFFIX_PATTERN = re.compile(r'\s(?:в|in|at|ใน)\s+', re.IGNORECASE)
PROJECT_NAME_LEADING_CONTEXT_PATTERNS = (
    re.compile(
        r'^(?:в\s+)?'
        r'(?:(?:новом|новый|нового|новая|новой|новое|новые|новых|'
        r'премиум|премиальном|премиальный|премиального)\s+)*'
        r'(?:жил(?:ом|ой|ого)?\s+)?'
        r'(?:комплекс(?:е|а|ом)?|проект(?:е|а|ом)?|кондоминиум(?:е|а|ом)?|резиденци(?:и|я)|жк)\s+',
        re.IGNORECASE,
    ),
    re.compile(
        r'^(?:премиум-класса|премиум|премиальном|премиальный|премиального)\s+',
        re.IGNORECASE,
    ),
    re.compile(
        r'^(?:the\s+)?(?:new\s+)?(?:project|complex|development|residence|condominium|condo)\s+',
        re.IGNORECASE,
    ),
    re.compile(r'^(?:โครงการ|คอมเพล็กซ์|คอนโดมิเนียม)\s*', re.IGNORECASE),
)
PROJECT_NAME_GENERIC_PATTERNS = (
    re.compile(r'^(?:a\s+)?bargain price$', re.IGNORECASE),
    re.compile(r'^(?:the\s+)?area$', re.IGNORECASE),
    re.compile(r'^phuket$', re.IGNORECASE),
    re.compile(r'\b(?:район(?:е|а|ом)?|district|area)\b', re.IGNORECASE),
)


def _clean_project_name_candidate(value):
    value = _normalize_whitespace(strip_tags(value or '').strip(' .,;:|/\\-–—'))
    if not value:
        return ''

    previous = None
    while value and value != previous:
        previous = value
        for pattern in PROJECT_NAME_LEADING_CONTEXT_PATTERNS:
            value = _normalize_whitespace(pattern.sub('', value).strip(' .,;:|/\\-–—'))

    return value


def _normalize_project_key(value):
    value = _clean_project_name_candidate(value)
    if not value:
        return ''
    value = re.sub(r'[^\w\u0E00-\u0E7F]+', ' ', value, flags=re.UNICODE)
    return _normalize_whitespace(value).lower()


def _normalize_legacy_project_key(value):
    value = _normalize_whitespace(strip_tags(value or ''))
    return value.lower()


def _is_plausible_project_name(value):
    value = _clean_project_name_candidate(value)
    if not value:
        return False
    if len(value) < 4 or len(value.split()) > 8:
        return False
    if any(pattern.search(value) for pattern in PROJECT_NAME_GENERIC_PATTERNS):
        return False

    contains_thai = bool(re.search(r'[\u0E00-\u0E7F]', value))
    contains_uppercase = any(char.isupper() for char in value)
    contains_digit = any(char.isdigit() for char in value)
    return contains_thai or contains_uppercase or contains_digit


def _extract_project_name_from_title(value):
    value = _normalize_whitespace(strip_tags(value or ''))
    if not value:
        return ''

    matches = list(PROJECT_NAME_SUFFIX_PATTERN.finditer(value))
    for match in reversed(matches):
        candidate = _clean_project_name_candidate(value[match.end():])
        if _is_plausible_project_name(candidate):
            return candidate
    return ''


def _get_property_project_name(property_obj, language_code='ru'):
    if property_obj is None:
        return ''

    language_code = (language_code or 'ru')[:2]
    field_candidates = []
    for base_field in ('complex_name', 'title'):
        localized_field = base_field if language_code == 'ru' else f'{base_field}_{language_code}'
        field_candidates.append(localized_field)
        field_candidates.append(base_field)
        field_candidates.extend([f'{base_field}_ru', f'{base_field}_en', f'{base_field}_th'])

    seen_fields = set()
    for field_name in field_candidates:
        if field_name in seen_fields:
            continue
        seen_fields.add(field_name)
        value = _normalize_whitespace(getattr(property_obj, field_name, '') or '')
        if not value:
            continue
        if field_name.startswith('complex_name'):
            return _clean_project_name_candidate(value) or value
        extracted = _extract_project_name_from_title(value)
        if extracted:
            return extracted

    return ''


def _get_property_project_keys(property_obj, language_code='ru'):
    if property_obj is None:
        return []

    keys = []

    legacy_key = _normalize_legacy_project_key(getattr(property_obj, 'legacy_id', ''))
    if legacy_key:
        keys.append(('legacy_id', legacy_key))

    project_name = _get_property_project_name(property_obj, language_code)
    project_key = _normalize_project_key(project_name)
    if project_key:
        keys.append(('project_name', project_key))

    return keys


def _property_matches_project_keys(property_obj, project_keys, language_code='ru'):
    if not project_keys:
        return False

    candidate_keys = set(_get_property_project_keys(property_obj, language_code))
    return any(project_key in candidate_keys for project_key in project_keys)


def _filter_out_project_matches(properties, project_keys, language_code='ru'):
    if not project_keys:
        return list(properties)
    return [
        property_obj for property_obj in properties
        if not _property_matches_project_keys(property_obj, project_keys, language_code)
    ]


def _get_catalog_deal_breadcrumb_label(deal_type, language_code='ru'):
    labels = {
        'sale': {'ru': 'Продажа', 'en': 'Sale', 'th': 'ขาย'},
        'rent': {'ru': 'Аренда', 'en': 'Rent', 'th': 'เช่า'},
    }
    return labels.get(deal_type, {}).get(language_code, '')


def _build_catalog_breadcrumb_url(base_url, params=None):
    if not params:
        return base_url
    normalized = {key: value for key, value in params.items() if value not in (None, '', [], ())}
    if not normalized:
        return base_url
    return f"{base_url}?{urlencode(normalized, doseq=True)}"


def _build_catalog_breadcrumbs_common(
    *,
    language_code='ru',
    deal_type='',
    property_type_obj=None,
    district_obj=None,
    location_obj=None,
    current_label='',
    current_url='',
):
    breadcrumbs = [{
        'label': gettext('Главная'),
        'url': reverse('core:home'),
    }, {
        'label': gettext('Недвижимость'),
        'url': reverse('properties:property_list'),
    }]

    current_base_url = reverse('properties:property_list')

    if deal_type in {'sale', 'rent'}:
        current_base_url = reverse(f'properties:property_{deal_type}')
        breadcrumbs.append({
            'label': _get_catalog_deal_breadcrumb_label(deal_type, language_code),
            'url': current_base_url,
        })

    if district_obj:
        breadcrumbs.append({
            'label': _get_translated_attr(district_obj, 'name', language_code, district_obj.name),
            'url': _build_catalog_breadcrumb_url(current_base_url, {'district': district_obj.slug}),
        })

    if location_obj:
        breadcrumbs.append({
            'label': _get_translated_attr(location_obj, 'name', language_code, location_obj.name),
            'url': _build_catalog_breadcrumb_url(
                current_base_url,
                {'district': location_obj.district.slug, 'location': location_obj.slug},
            ),
        })

    if property_type_obj:
        type_base_url = reverse('properties:property_by_type', args=[property_type_obj.name])
        type_params = {}
        if deal_type in {'sale', 'rent'}:
            type_params['deal_type'] = deal_type
        if district_obj:
            type_params['district'] = district_obj.slug
        if location_obj:
            type_params['location'] = location_obj.slug
        breadcrumbs.append({
            'label': PROPERTY_TYPE_NAV_LABELS.get(property_type_obj.name, {}).get(language_code)
                     or _get_translated_attr(property_type_obj, 'name_display', language_code, property_type_obj.name_display),
            'url': _build_catalog_breadcrumb_url(type_base_url, type_params),
        })

    current_label = _normalize_whitespace(current_label or '')
    if current_label and current_label != breadcrumbs[-1]['label']:
        breadcrumbs.append({
            'label': current_label,
            'url': current_url or '',
        })

    return breadcrumbs


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


def _format_plain_decimal(value):
    if value is None:
        return ''

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ''

    if decimal_value == decimal_value.to_integral_value():
        return f'{int(decimal_value):,}'.replace(',', ' ')

    formatted = f'{decimal_value:,.1f}'.replace(',', ' ')
    return formatted.rstrip('0').rstrip('.')


def _format_same_complex_area_range(properties, language_code='ru'):
    areas = [
        Decimal(str(property_obj.area_total))
        for property_obj in properties
        if property_obj.area_total
    ]
    if not areas:
        return ''

    min_area = min(areas)
    max_area = max(areas)
    unit = 'ตร.ม.' if language_code == 'th' else ('м²' if language_code == 'ru' else 'm²')

    if min_area == max_area:
        return f'{_format_plain_decimal(min_area)} {unit}'

    return f'{_format_plain_decimal(min_area)}-{_format_plain_decimal(max_area)} {unit}'


def _format_same_complex_price(property_obj, currency_code='THB'):
    price = None
    deal_type = property_obj.deal_type if property_obj.deal_type in {'sale', 'rent'} else 'sale'

    if deal_type == 'sale':
        price = property_obj.get_price_in_currency(currency_code, 'sale')
        if not price and property_obj.deal_type == 'both':
            price = property_obj.get_price_in_currency(currency_code, 'rent')
    else:
        price = property_obj.get_price_in_currency(currency_code, 'rent')

    return price


def _get_same_complex_plural_label(count, language_code, one_key, few_key, many_key):
    texts = _get_property_detail_context_texts(language_code)

    if language_code == 'ru':
        if count % 10 == 1 and count % 100 != 11:
            key = one_key
        elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            key = few_key
        else:
            key = many_key
    elif language_code == 'en':
        key = one_key if count == 1 else many_key
    else:
        key = many_key

    return texts[key]


def _build_same_complex_stats(property_obj, same_complex_properties, language_code='ru', currency_code='THB'):
    all_project_properties = [property_obj, *same_complex_properties]
    texts = _get_property_detail_context_texts(language_code)
    count = len(all_project_properties)
    stats = [{
        'icon': 'fas fa-layer-group',
        'value': count,
        'label': _get_same_complex_plural_label(
            count,
            language_code,
            'same_complex_count_one',
            'same_complex_count_few',
            'same_complex_count_many',
        ),
    }]

    bedroom_values = sorted({
        int(project_property.bedrooms)
        for project_property in all_project_properties
        if project_property.bedrooms
    })
    if bedroom_values:
        min_bedrooms = min(bedroom_values)
        max_bedrooms = max(bedroom_values)
        bedroom_label_count = min_bedrooms if min_bedrooms == max_bedrooms else max_bedrooms
        bedroom_value = str(min_bedrooms) if min_bedrooms == max_bedrooms else f'{min_bedrooms}-{max_bedrooms}'
        stats.append({
            'icon': 'fas fa-bed',
            'value': bedroom_value,
            'label': _get_same_complex_plural_label(
                bedroom_label_count,
                language_code,
                'same_complex_bedroom_one',
                'same_complex_bedroom_few',
                'same_complex_bedroom_many',
            ),
        })

    area_range = _format_same_complex_area_range(all_project_properties, language_code)
    if area_range:
        stats.append({
            'icon': 'fas fa-ruler-combined',
            'value': area_range,
            'label': texts['same_complex_area_label'],
        })

    prices = [
        Decimal(str(price))
        for price in (
            _format_same_complex_price(project_property, currency_code)
            for project_property in all_project_properties
        )
        if price
    ]
    if prices:
        formatted_price = CurrencyService.format_price(min(prices), currency_code).replace(',', ' ')
        stats.append({
            'icon': 'fas fa-tag',
            'value': texts['same_complex_from_price'].format(price=formatted_price),
            'label': texts['same_complex_price_label'],
        })

    return stats


def _get_property_detail_context_texts(language_code='ru'):
    language_code = (language_code or 'ru')[:2]
    return PROPERTY_DETAIL_CONTEXT_TEXTS.get(language_code, PROPERTY_DETAIL_CONTEXT_TEXTS['ru'])


def _get_localized_team_value(specialist, field_name, language_code='ru'):
    candidates = [
        getattr(specialist, f'{field_name}_{language_code}', ''),
        getattr(specialist, f'{field_name}_en', ''),
        getattr(specialist, f'{field_name}_ru', ''),
        getattr(specialist, field_name, ''),
    ]
    return _normalize_whitespace(next((value for value in candidates if value), ''))


def _get_default_property_specialist():
    return Team.objects.filter(
        Q(first_name_ru__iexact='Богдан') | Q(first_name_en__iexact='Bogdan') | Q(first_name__iexact='Bogdan'),
        is_active=True,
    ).order_by('display_order', 'id').first()


def _build_property_responsible_specialist_context(property_obj, request, language_code='ru'):
    language_code = (language_code or 'ru')[:2]
    texts = _get_property_detail_context_texts(language_code)
    specialist = property_obj.contact_person if property_obj.contact_person and property_obj.contact_person.is_active else None
    if not specialist:
        specialist = _get_default_property_specialist()

    if not specialist:
        return None

    first_name = _get_localized_team_value(specialist, 'first_name', language_code)
    last_name = _get_localized_team_value(specialist, 'last_name', language_code)
    position = _get_localized_team_value(specialist, 'position', language_code)
    name = _normalize_whitespace(f'{first_name} {last_name}'.strip()) or specialist.full_name
    languages = specialist.get_languages_list()
    photo_url = ''
    photo_width = 256
    photo_height = 256
    schema_photo_url = ''

    if specialist.photo:
        try:
            schema_photo_url = request.build_absolute_uri(specialist.photo.url)
        except Exception:
            schema_photo_url = ''
        avatar_url = getattr(specialist, 'photo_avatar_url', '') or ''
        photo_url = request.build_absolute_uri(avatar_url) if avatar_url else schema_photo_url
        if avatar_url:
            photo_width = 160
            photo_height = 160
        try:
            if not avatar_url:
                photo_width = specialist.photo.width or photo_width
                photo_height = specialist.photo.height or photo_height
        except Exception:
            pass

    site_root_url = request.build_absolute_uri('/')
    profile_url = request.build_absolute_uri(reverse('core:about'))
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        '@id': f'{site_root_url}#team-member-{specialist.id}',
        'name': name,
        'url': profile_url,
        'worksFor': {
            '@type': 'Organization',
            '@id': f'{site_root_url}#real-estate-agent',
            'name': 'Undersun Estate',
        },
    }

    if position:
        schema['jobTitle'] = position
    if schema_photo_url or photo_url:
        schema['image'] = schema_photo_url or photo_url
    if specialist.email:
        schema['email'] = specialist.email
    if specialist.phone:
        schema['telephone'] = specialist.phone
    if languages:
        schema['knowsLanguage'] = languages

    return {
        'name': name,
        'position': position,
        'initial': (first_name or name or 'U')[:1].upper(),
        'photo_url': photo_url,
        'photo_width': photo_width,
        'photo_height': photo_height,
        'phone': specialist.phone,
        'phone_display': specialist.phone_display,
        'email': specialist.email,
        'whatsapp_url': specialist.whatsapp_url,
        'telegram_url': specialist.telegram_url,
        'profile_url': profile_url,
        'languages': languages,
        'labels': {
            'eyebrow': texts['trust_eyebrow'],
            'note': texts['trust_note'],
            'languages': texts['trust_languages_label'],
            'profile': texts['trust_profile_label'],
        },
        'schema_json': json.dumps(schema, ensure_ascii=False),
    }


def _build_property_freshness_context(property_obj, language_code='ru'):
    language_code = (language_code or 'ru')[:2]
    texts = _get_property_detail_context_texts(language_code)
    return {
        'updated_label': texts['freshness_updated_label'],
        'status_label': texts['freshness_status_label'],
        'status': property_obj.get_status_display(),
        'note': texts['freshness_note'],
    }


def _build_property_context_links(property_obj, language_code='ru'):
    language_code = (language_code or 'ru')[:2]
    texts = _get_property_detail_context_texts(language_code)
    location_context = _build_property_location_context(property_obj, language_code)
    location_label = location_context.get('property_full_location_label') or 'Phuket'
    property_type_label = _get_property_type_nav_label(property_obj, language_code)
    property_type_slug = property_obj.property_type.name if property_obj.property_type else ''
    deal_type = property_obj.deal_type
    links = []
    seen_urls = set()

    def add_link(url, label, description, icon):
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        links.append({
            'url': url,
            'label': label,
            'description': description,
            'icon': icon,
        })

    catalog_base_url = (
        reverse('properties:property_by_type', args=[property_type_slug])
        if property_type_slug
        else reverse('properties:property_list')
    )
    catalog_params = {}
    if deal_type in {'sale', 'rent'}:
        catalog_params['deal_type'] = deal_type
    if property_obj.district:
        catalog_params['district'] = property_obj.district.slug
    if property_obj.location:
        catalog_params['location'] = property_obj.location.slug

    add_link(
        _build_catalog_breadcrumb_url(catalog_base_url, catalog_params),
        texts['catalog_link_label'].format(property_type=property_type_label, location=location_label),
        texts['catalog_link_description'],
        'fas fa-building',
    )

    if property_obj.location:
        add_link(
            property_obj.location.get_absolute_url(),
            texts['location_link_label'].format(location=location_label),
            texts['location_link_description'],
            'fas fa-map-marker-alt',
        )
    elif property_obj.district:
        add_link(
            property_obj.district.get_absolute_url(),
            texts['location_link_label'].format(location=location_label),
            texts['location_link_description'],
            'fas fa-map-marker-alt',
        )

    def add_service_link(slug, label_key, description_key, icon):
        add_link(
            reverse('core:service_detail', kwargs={'slug': slug}),
            texts[label_key],
            texts[description_key],
            icon,
        )

    if property_type_slug == 'land':
        add_service_link('land-sale', 'land_service_label', 'land_service_description', 'fas fa-drafting-compass')
        add_service_link('legal-services', 'legal_service_label', 'legal_service_description', 'fas fa-file-signature')
    else:
        if deal_type in {'sale', 'both'}:
            add_service_link('buying-property', 'buying_service_label', 'buying_service_description', 'fas fa-handshake')
            add_service_link('legal-services', 'legal_service_label', 'legal_service_description', 'fas fa-file-signature')
        if deal_type in {'rent', 'both'}:
            add_service_link('renting-property', 'renting_service_label', 'renting_service_description', 'fas fa-key')

    return {
        'heading': texts['context_heading'],
        'description': texts['context_description'],
        'links': links[:5],
    }


def _annotate_property_labels(property_obj, language_code='ru'):
    labels = _build_property_location_context(property_obj, language_code)
    property_obj.localized_title = _build_property_display_title(property_obj, language_code)
    property_obj.localized_district_label = labels['property_district_label']
    property_obj.localized_location_name = labels['property_location_label']
    property_obj.localized_location_label = labels['property_full_location_label']
    return property_obj


def _get_catalog_texts(language_code='ru'):
    return CATALOG_SEO_TEXTS.get((language_code or 'ru')[:2], CATALOG_SEO_TEXTS['ru'])


def _get_catalog_internal_type_label(property_type_obj, deal_type='', language_code='ru'):
    language_code = (language_code or 'ru')[:2]
    type_slug = getattr(property_type_obj, 'name', '') or ''
    deal_key = deal_type if deal_type in {'sale', 'rent'} else ''
    label_map = CATALOG_INTERNAL_TYPE_LABELS.get(language_code, CATALOG_INTERNAL_TYPE_LABELS['en'])
    return (
        label_map.get(deal_key, {}).get(type_slug)
        or label_map.get('', {}).get(type_slug)
        or _get_translated_attr(
            property_type_obj,
            'name_display',
            language_code,
            getattr(property_type_obj, 'name_display', type_slug),
        )
    )


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
    SINGLE_VALUE_QUERY_PARAMS = {
        'deal_type',
        'district',
        'location',
        'min_price',
        'max_price',
        'q',
        'sort',
        'map_view',
        'build_status',
        'page',
    }
    MULTI_VALUE_QUERY_PARAMS = {'property_type', 'bedrooms', 'amenities'}
    CATALOG_QUERY_PARAM_ORDER = (
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
        'page',
    )

    def dispatch(self, request, *args, **kwargs):
        redirect_response = self._maybe_redirect_legacy_start_param(request)
        if redirect_response:
            return redirect_response

        redirect_response = self._maybe_redirect_normalized_catalog_query(request)
        if redirect_response:
            return redirect_response

        redirect_response = self._maybe_redirect_single_property_type_filter(request)
        if redirect_response:
            return redirect_response

        return super().dispatch(request, *args, **kwargs)

    def _maybe_redirect_legacy_start_param(self, request):
        start_value = request.GET.get('start')
        if start_value in (None, ''):
            return None

        query_params = request.GET.copy()
        query_params.pop('start', None)

        try:
            offset = int(start_value)
        except (TypeError, ValueError):
            offset = 0

        if offset > 0:
            page_size = self.get_paginate_by(None) or self.paginate_by or 12
            query_params['page'] = str((offset // page_size) + 1)

        query_string = query_params.urlencode()
        target_url = request.path
        if query_string:
            target_url = f'{target_url}?{query_string}'

        return HttpResponsePermanentRedirect(target_url)

    def _maybe_redirect_normalized_catalog_query(self, request):
        if not request.GET:
            return None

        normalized = {}
        changed = False

        for key in request.GET:
            values = [value for value in request.GET.getlist(key) if value not in (None, '')]
            if not values:
                changed = True
                continue

            if key in self.SINGLE_VALUE_QUERY_PARAMS:
                if len(values) > 1:
                    changed = True
                normalized[key] = [values[-1]]
            elif key in self.MULTI_VALUE_QUERY_PARAMS:
                deduped_values = []
                seen_values = set()
                for value in values:
                    if value in seen_values:
                        changed = True
                        continue
                    seen_values.add(value)
                    deduped_values.append(value)
                normalized[key] = deduped_values
            else:
                normalized[key] = values

        forced_deal_type = getattr(self, 'forced_deal_type', '')
        deal_type_values = normalized.get('deal_type') or []
        if forced_deal_type and deal_type_values == [forced_deal_type]:
            normalized.pop('deal_type', None)
            changed = True

        if normalized.get('sort') == ['-created_at']:
            normalized.pop('sort', None)
            changed = True

        page_values = normalized.get('page') or []
        if page_values:
            try:
                page_number = int(page_values[-1])
            except (TypeError, ValueError):
                normalized.pop('page', None)
                changed = True
            else:
                if page_number <= 1:
                    normalized.pop('page', None)
                    changed = True

        location_values = normalized.get('location') or []
        if location_values:
            location_queryset = Location.objects.select_related('district').filter(slug=location_values[-1])
            district_values = normalized.get('district') or []
            location_obj = None
            if district_values:
                location_obj = location_queryset.filter(district__slug=district_values[-1]).first()
            else:
                location_matches = list(location_queryset[:2])
                if len(location_matches) == 1:
                    location_obj = location_matches[0]

            if location_obj and location_obj.district_id:
                district_slug = location_obj.district.slug
                if normalized.get('district') != [district_slug]:
                    normalized['district'] = [district_slug]
                    changed = True

        if not changed:
            return None

        ordered_items = []
        handled_keys = set()
        for key in self.CATALOG_QUERY_PARAM_ORDER:
            values = normalized.get(key)
            if not values:
                continue
            handled_keys.add(key)
            for value in values:
                ordered_items.append((key, value))

        for key in request.GET:
            if key in handled_keys or key in self.CATALOG_QUERY_PARAM_ORDER:
                continue
            for value in normalized.get(key, []):
                ordered_items.append((key, value))

        query_string = urlencode(ordered_items)
        target_url = request.path
        if query_string:
            target_url = f'{target_url}?{query_string}'

        return HttpResponsePermanentRedirect(target_url)

    def _maybe_redirect_single_property_type_filter(self, request):
        if self.kwargs.get('type_name'):
            return None

        selected_types = [type_name for type_name in request.GET.getlist('property_type') if type_name]
        if len(selected_types) != 1:
            return None

        property_type_name = selected_types[0]
        if not PropertyType.objects.filter(name=property_type_name).exists():
            return None

        query_params = request.GET.copy()
        query_params.pop('property_type', None)

        deal_type = getattr(self, 'forced_deal_type', '') or request.GET.get('deal_type', '')
        if deal_type == 'rent':
            query_params['deal_type'] = deal_type

        target_url = reverse('properties:property_by_type', args=[property_type_name])
        query_string = query_params.urlencode()
        if query_string:
            target_url = f'{target_url}?{query_string}'

        return HttpResponsePermanentRedirect(target_url)

    def get_paginate_by(self, queryset):
        """Отключить пагинацию для карты"""
        if self.request.GET.get('map_view') == 'true':
            return None  # Отключить пагинацию для карты
        return self.paginate_by

    def paginate_queryset(self, queryset, page_size):
        """Return the nearest valid catalog page instead of a crawl-facing 404."""
        paginator = self.get_paginator(
            queryset,
            page_size,
            allow_empty_first_page=self.get_allow_empty(),
        )
        page_kwarg = self.page_kwarg
        raw_page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        fallback_used = False

        try:
            page_number = int(raw_page)
        except (TypeError, ValueError):
            if raw_page == 'last':
                page_number = paginator.num_pages
            else:
                page_number = 1
                fallback_used = True

        requested_page_number = page_number
        if page_number < 1:
            page_number = 1
            fallback_used = True

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(max(paginator.num_pages, 1))
            fallback_used = True
        except PageNotAnInteger:
            page_obj = paginator.page(1)
            fallback_used = True

        if fallback_used:
            self.request.catalog_pagination_fallback = True
            self.request.catalog_requested_page_number = requested_page_number
            self.request.catalog_effective_page_number = page_obj.number

        return paginator, page_obj, page_obj.object_list, page_obj.has_other_pages()

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
        
        # Поиск по тексту, внутреннему ID и legacy-коду объекта
        query = (self.request.GET.get('q') or '').strip()
        if query:
            legacy_query = query.lstrip('#№').strip()
            compact_legacy_query = ''.join(char for char in legacy_query if char.isalnum())
            legacy_tokens = {query, legacy_query, compact_legacy_query}
            if compact_legacy_query.lower().startswith('id') and len(compact_legacy_query) > 2:
                legacy_tokens.add(compact_legacy_query[2:])

            search_filter = (
                Q(title_ru__icontains=query) |
                Q(title_en__icontains=query) |
                Q(title_th__icontains=query) |
                Q(description_ru__icontains=query) |
                Q(description_en__icontains=query) |
                Q(description_th__icontains=query) |
                Q(short_description_ru__icontains=query) |
                Q(short_description_en__icontains=query) |
                Q(short_description_th__icontains=query) |
                Q(complex_name__icontains=query) |
                Q(address__icontains=query) |
                Q(district__name_ru__icontains=query) |
                Q(district__name_en__icontains=query) |
                Q(district__name_th__icontains=query) |
                Q(location__name_ru__icontains=query) |
                Q(location__name_en__icontains=query) |
                Q(location__name_th__icontains=query)
            )

            for legacy_token in legacy_tokens:
                if legacy_token:
                    search_filter |= Q(legacy_id__icontains=legacy_token)

            for legacy_token in legacy_tokens:
                if legacy_token and legacy_token.isdigit():
                    search_filter |= Q(pk=int(legacy_token))

            queryset = queryset.filter(search_filter)
        
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
        context['catalog_results_heading'] = self.build_catalog_results_heading(context)
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
        context['catalog_answer_first'] = ''
        landing_override = self.get_catalog_landing_override(context, language_code)
        if landing_override:
            context['page_title'] = self._format_catalog_override_text(
                landing_override.get('page_title', context['page_title']),
                context,
            )
            context['page_description'] = truncate_meta(self._format_catalog_override_text(
                landing_override.get('page_description', context['page_description']),
                context,
            ))
            context['catalog_answer_first'] = self._format_catalog_override_text(
                landing_override.get('answer_first', ''),
                context,
            )

        page_number = self._get_catalog_page_number()
        if context.get('catalog_is_indexable') and page_number and page_number > 1:
            meta = self._refine_paginated_catalog_meta(
                context['page_title'],
                context['page_description'],
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

    def get_catalog_landing_override(self, context, language_code='ru'):
        signature = self.get_catalog_landing_signature(context)
        if not signature:
            return None

        current_filters = context.get('current_filters', {})
        if self.request.GET.get('map_view') == 'true':
            return None
        if self.request.GET.get('sort') and self.request.GET.get('sort') != '-created_at':
            return None

        for key in self.NON_INDEX_FILTER_KEYS:
            value = current_filters.get(key)
            if isinstance(value, list):
                if any(item not in (None, '') for item in value):
                    return None
            elif value not in (None, ''):
                return None

        property_types = [value for value in current_filters.get('property_type', []) if value]
        if len(property_types) > 1:
            return None

        page_number = self._get_catalog_page_number()
        if page_number is None:
            return None

        key = (
            (language_code or 'ru')[:2],
            signature.pattern,
            signature.property_type,
            signature.deal_type,
            signature.district,
            signature.location,
        )
        return CATALOG_LANDING_OVERRIDES.get(key)

    def _format_catalog_override_text(self, text, context):
        if not isinstance(text, str):
            return text
        values = {
            'count': context.get('catalog_results_count') or self._get_results_count(context) or 0,
        }
        try:
            return text % values
        except (KeyError, TypeError, ValueError):
            return text

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
        override = self.get_catalog_landing_override(context, language_code)
        if override and override.get('heading'):
            return self._format_catalog_override_text(override['heading'], context)

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

    def build_catalog_results_heading(self, context):
        language_code = getattr(self.request, 'LANGUAGE_CODE', 'ru')[:2]
        results_count = context.get('catalog_results_count') or 0
        property_type_obj = self._get_primary_property_type(context)
        current_filters = context.get('current_filters', {})
        deal_type = context.get('deal_type') or current_filters.get('deal_type', '')
        location_obj, district_obj = self._get_location_and_district()

        subject = self._get_catalog_subject_label(property_type_obj, language_code)
        deal_phrase = self._get_catalog_deal_phrase(deal_type, language_code)
        geo_phrase = self._get_catalog_geo_phrase(location_obj, district_obj, language_code)

        if language_code == 'en':
            context_parts = [subject, deal_phrase, geo_phrase]
            context_label = ' '.join(part for part in context_parts if part).strip() or 'properties in the catalogue'
            return f'{results_count} {context_label}' if results_count else 'No properties found'

        if language_code == 'th':
            context_parts = [subject, deal_phrase, geo_phrase]
            context_label = ' '.join(part for part in context_parts if part).strip() or 'รายการในแคตตาล็อก'
            return f'{context_label} {results_count} รายการ' if results_count else 'ไม่พบรายการ'

        context_parts = [subject, deal_phrase, geo_phrase]
        context_label = ' '.join(part for part in context_parts if part).strip() or 'объектов в каталоге'
        if not results_count:
            return 'Объекты не найдены'

        count_label = ngettext('%(count)s объект', '%(count)s объектов', results_count) % {'count': results_count}
        return f'{count_label} {context_label}'.strip()

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
        if self.get_catalog_landing_override(context, language_code):
            return None

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
        current_filters = context.get('current_filters', {})
        deal_type = context.get('deal_type') or current_filters.get('deal_type') or ''
        property_type_obj = self._get_primary_property_type(context)
        location_obj, district_obj = self._get_location_and_district()
        return _build_catalog_breadcrumbs_common(
            language_code=language_code,
            deal_type=deal_type,
            property_type_obj=property_type_obj,
            district_obj=district_obj,
            location_obj=location_obj,
            current_label=context.get('seo_heading') or _get_catalog_texts(language_code)['heading_fallback'],
        )

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
        effective_page_number = getattr(self.request, 'catalog_effective_page_number', None)
        if effective_page_number:
            return effective_page_number

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
        pagination_fallback = bool(getattr(self.request, 'catalog_pagination_fallback', False))
        if pagination_fallback:
            is_indexable = False

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

        override = self.get_catalog_landing_override(context, language_code)
        if override:
            return {
                'has_content': results_count > 0,
                'heading': self._format_catalog_override_text(
                    override.get('seo_heading') or override.get('heading') or texts['intro_heading'],
                    context,
                ),
                'intro': self._format_catalog_override_text(override.get('intro', ''), context),
                'highlights': [
                    self._format_catalog_override_text(item, context)
                    for item in override.get('highlights', [])
                    if item
                ],
                'follow_up': self._format_catalog_override_text(override.get('follow_up', ''), context),
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

        override = self.get_catalog_landing_override(context, language_code)
        if override and override.get('faq_entries'):
            entries = []
            for item in override.get('faq_entries', []):
                question = self._format_catalog_override_text(item.get('question', ''), context)
                answer = self._format_catalog_override_text(item.get('answer', ''), context)
                if question and answer:
                    entries.append({
                        'question': question,
                        'answer': answer,
                    })

            return {
                'has_items': bool(entries),
                'heading': self._format_catalog_override_text(
                    override.get('faq_heading') or texts['faq_heading'],
                    context,
                ),
                'entries': entries[:5],
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

    def _get_catalog_link_base(self, context, deal_type=None, property_type_obj=CATALOG_LINK_UNSET):
        resolved_deal_type = deal_type if deal_type is not None else (context.get('deal_type') or context.get('current_filters', {}).get('deal_type') or '')
        resolved_property_type = self._get_primary_property_type(context) if property_type_obj is CATALOG_LINK_UNSET else property_type_obj

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
            link_deal_type = selected_deal_type
            if selected_deal_type == 'sale' and item.name in {'condo', 'villa', 'townhouse', 'land'}:
                # Primary commercial landings for sale intent are the clean type pages.
                # Keeping ?deal_type=sale here creates extra type+deal URLs competing with them.
                link_deal_type = ''
            base_url, params = self._get_catalog_link_base(context, deal_type=link_deal_type, property_type_obj=item)
            if district_obj:
                params['district'] = district_obj.slug
            if location_obj:
                params['district'] = location_obj.district.slug
                params['location'] = location_obj.slug
            type_links.append({
                'label': _get_catalog_internal_type_label(item, selected_deal_type, language_code),
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
        redirect_response = self._maybe_redirect_redundant_sale_deal_type(request)
        if redirect_response:
            return redirect_response

        redirect_response = self._maybe_redirect_by_property_type(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def _maybe_redirect_redundant_sale_deal_type(self, request):
        if request.GET.get('deal_type') != 'sale':
            return None

        query_params = request.GET.copy()
        query_params.pop('deal_type', None)

        target_url = request.path
        query_string = query_params.urlencode()
        if query_string:
            target_url = f"{target_url}?{query_string}"

        return HttpResponsePermanentRedirect(target_url)

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
            'district', 'location', 'property_type', 'developer', 'contact_person'
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
        context['property_title_display'] = _build_property_display_title(self.object, language_code)
        context['property_schema_description'] = _build_property_schema_description(self.object, language_code)
        context['property_image_alt_base'] = self.object.get_seo_image_alt_base(language_code)
        context['property_seo_section'] = self.object.get_detail_seo_section(language_code)
        context['property_faq'] = self.object.get_detail_faq_items(language_code)
        context['property_type_nav_label'] = _get_property_type_nav_label(self.object, language_code)
        context['property_catalog_type_url'] = _get_property_catalog_type_url(self.object)
        context['property_freshness'] = _build_property_freshness_context(self.object, language_code)
        context['property_responsible_specialist'] = _build_property_responsible_specialist_context(
            self.object,
            self.request,
            language_code,
        )
        context['property_context_links'] = _build_property_context_links(self.object, language_code)
        same_complex_properties = self.get_same_complex_properties(language_code)
        for same_complex_property in same_complex_properties:
            _annotate_property_labels(same_complex_property, language_code)
        same_complex_name = _get_property_project_name(self.object, language_code)
        detail_context_texts = _get_property_detail_context_texts(language_code)
        selected_currency_code = CurrencyService.get_selected_currency_code(self.request)
        context['same_complex_properties'] = same_complex_properties
        context['same_complex_context'] = {
            'has_items': bool(same_complex_properties),
            'eyebrow': detail_context_texts['same_complex_eyebrow'],
            'heading': detail_context_texts['same_complex_heading'].format(complex=same_complex_name),
            'description': detail_context_texts['same_complex_description'],
            'stats_label': detail_context_texts['same_complex_stats_label'],
        }
        context['same_complex_stats'] = _build_same_complex_stats(
            self.object,
            same_complex_properties,
            language_code,
            selected_currency_code,
        ) if same_complex_properties else []
        context.update(_build_property_image_sets(self.object, language_code))
        context.update(_build_property_location_context(self.object, language_code))
        context['detail_breadcrumbs'] = _build_catalog_breadcrumbs_common(
            language_code=language_code,
            deal_type=self.object.deal_type,
            property_type_obj=self.object.property_type,
            district_obj=self.object.district,
            location_obj=self.object.location,
            current_label=context['property_title_display'],
            current_url=self.object.get_absolute_url(),
        )

        return context

    def _maybe_redirect_legacy_slug(self, slug):
        """Проверяем, нужно ли перенаправить запрос со старого slug на актуальный."""
        if not slug:
            return None

        target_slug = LEGACY_PROPERTY_SLUG_REDIRECTS.get(slug)
        if target_slug:
            target_url = reverse('properties:property_detail', kwargs={'slug': target_slug})
            return HttpResponsePermanentRedirect(target_url)

        fallback = MISSING_PROPERTY_SLUG_FALLBACKS.get(slug)
        if fallback:
            target_url = reverse(fallback['view_name'])
            params = fallback.get('params') or {}
            if params:
                target_url = f"{target_url}?{urlencode(params)}"
            return HttpResponsePermanentRedirect(target_url)

        return None

    def get_same_complex_properties(self, language_code='ru'):
        project_keys = _get_property_project_keys(self.object, language_code)
        if not project_keys:
            return []

        queryset = Property.objects.filter(
            is_active=True,
            status='available',
        ).exclude(id=self.object.id)

        if self.object.district_id:
            queryset = queryset.filter(district=self.object.district)

        candidates = queryset.select_related(
            'district', 'location', 'property_type'
        ).prefetch_related('images').order_by(
            'bedrooms', 'price_sale_thb', '-updated_at'
        )
        matches = [
            property_obj for property_obj in candidates
            if _property_matches_project_keys(property_obj, project_keys, language_code)
        ]
        return matches[:4]
    
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
        same_project_keys = _get_property_project_keys(self.object)
        
        similar_properties = []
        
        # 1. Приоритет: та же конкретная локация (если есть)
        if self.object.location:
            same_location = Property.objects.filter(
                location=self.object.location,
                **base_filter
            ).exclude(id=self.object.id)
            same_location = same_location.select_related(
                'district', 'location', 'property_type'
            ).prefetch_related('images')[:8]
            
            similar_properties.extend(
                _filter_out_project_matches(same_location, same_project_keys)[:2]
            )
        
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
            ).prefetch_related('images')[:8]
            
            similar_properties.extend(
                _filter_out_project_matches(same_district, same_project_keys)[:(4 - len(similar_properties))]
            )
        
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
            ).prefetch_related('images')[:8]
            
            similar_properties.extend(
                _filter_out_project_matches(same_type, same_project_keys)[:(4 - len(similar_properties))]
            )
        
        return similar_properties[:4]


@require_POST
def toggle_favorite(request):
    # Функция избранного отключена - используется LocalStorage
    return JsonResponse({'success': False, 'message': 'Функция избранного отключена'})

def favorites_view(request):
    """Страница избранного"""
    request.seo_meta_robots = 'noindex, follow'
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


def _file_field_exists(file_field):
    try:
        storage = getattr(file_field, 'storage', None)
        name = getattr(file_field, 'name', '')
        return bool(storage and name and storage.exists(name))
    except Exception:
        return False


def _get_file_dimensions(file_field):
    try:
        return {
            'width': file_field.width or None,
            'height': file_field.height or None,
        }
    except Exception:
        return {'width': None, 'height': None}


def _build_floorplan_alt(property_obj, language_code='ru'):
    base_alt = property_obj.get_seo_image_alt_base(language_code)
    templates = {
        'ru': 'Планировка: {base}',
        'en': 'Floor plan: {base}',
        'th': 'ผัง: {base}',
    }
    template = templates.get((language_code or 'ru')[:2], templates['ru'])
    return template.format(base=base_alt)


def _is_floorplan_image(image):
    if getattr(image, 'image_type', '') == 'floorplan':
        return True
    if getattr(image, 'frame_type', '') == 'floorplan':
        if getattr(image, 'alt_generated_by', '') == 'heuristic':
            try:
                inferred_frame_type, _ = image.infer_frame_type()
                return inferred_frame_type == 'floorplan'
            except Exception:
                return False
        return True

    frame_getter = getattr(image, 'get_effective_frame_type', None)
    if callable(frame_getter):
        try:
            return frame_getter() == 'floorplan'
        except Exception:
            return False
    return False


def _build_property_image_sets(property_obj, language_code='ru'):
    gallery_images = []
    floorplan_images = []
    property_schema_image_urls = []
    seen_floorplan_urls = set()

    if _file_field_exists(getattr(property_obj, 'floorplan', None)):
        floorplan_url = property_obj.floorplan.url
        floorplan_images.append({
            'url': floorplan_url,
            'full_url': floorplan_url,
            'alt': _build_floorplan_alt(property_obj, language_code),
            'width': _get_file_dimensions(property_obj.floorplan)['width'],
            'height': _get_file_dimensions(property_obj.floorplan)['height'],
        })
        seen_floorplan_urls.add(floorplan_url)

    for image in property_obj.images.all():
        image_url = image.medium_url or image.thumbnail_url or image.original_url
        if not image_url:
            continue

        is_floorplan = _is_floorplan_image(image)
        target_images = floorplan_images if is_floorplan else gallery_images
        position = len(target_images) + 1
        alt_text = property_obj.get_seo_image_alt(
            image=image,
            language_code=language_code,
            position=position,
        )

        image_item = {
            'url': image_url,
            'thumbnail_url': image.thumbnail_url or image_url,
            'full_url': image.original_url or image_url,
            'alt': alt_text,
            **_get_file_dimensions(image.image),
        }

        if is_floorplan:
            if image_item['full_url'] in seen_floorplan_urls:
                continue
            seen_floorplan_urls.add(image_item['full_url'])
            floorplan_images.append(image_item)
        else:
            gallery_images.append(image_item)
            property_schema_image_urls.append(image_url)

    if not gallery_images:
        if floorplan_images:
            gallery_images.append(floorplan_images[0])
        else:
            gallery_images.append({
                'url': static('images/no-image.svg'),
                'full_url': static('images/no-image.svg'),
                'alt': property_obj.get_seo_image_alt(language_code=language_code),
                'width': None,
                'height': None,
            })

    return {
        'gallery_images': gallery_images,
        'floorplan_images': floorplan_images,
        'property_schema_image_urls': property_schema_image_urls,
    }


def property_detail_amp(request, slug):
    queryset = Property.objects.select_related(
        'district', 'location', 'property_type', 'developer', 'contact_person'
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
    request.canonical_url_override = canonical_url
    property_title_display = _build_property_display_title(property_obj, language_code)
    property_schema_description = _build_property_schema_description(property_obj, language_code)
    property_responsible_specialist = _build_property_responsible_specialist_context(
        property_obj,
        request,
        language_code,
    )
    seo_data = property_obj.get_seo_data(language_code)
    meta_title = seo_data.get('title') or f"{property_title_display} – Undersun Estate"
    raw_description = seo_data.get('description') or property_obj.short_description or strip_tags(property_obj.description)
    meta_description = truncate_meta(raw_description)

    image_context = _build_property_image_sets(property_obj, language_code)

    amenities = [relation.feature.name for relation in property_obj.features.all() if relation.feature]
    stats = _build_property_stats(property_obj)
    location_context = _build_property_location_context(property_obj, language_code)
    location_label = location_context['property_full_location_label']

    whatsapp_message = gettext('Здравствуйте! Меня интересует объект {title} ({url})').format(
        title=property_title_display,
        url=canonical_url,
    )
    whatsapp_url = f"https://wa.me/{BUSINESS_PROFILE['phone_e164'].lstrip('+')}?text={quote_plus(whatsapp_message)}"
    contact_phone = BUSINESS_PROFILE['phone_e164']
    if property_responsible_specialist:
        contact_phone = property_responsible_specialist.get('phone') or contact_phone
        whatsapp_url = property_responsible_specialist.get('whatsapp_url') or whatsapp_url

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
        'gallery_images': image_context['gallery_images'],
        'floorplan_images': image_context['floorplan_images'],
        'location_label': location_label,
        'property_title_display': property_title_display,
        'property_schema_description': property_schema_description,
        'property_image_alt_base': property_obj.get_seo_image_alt_base(language_code),
        'property_seo_section': property_obj.get_detail_seo_section(language_code),
        'property_faq': property_obj.get_detail_faq_items(language_code),
        'property_freshness': _build_property_freshness_context(property_obj, language_code),
        'property_responsible_specialist': property_responsible_specialist,
        'property_context_links': _build_property_context_links(property_obj, language_code),
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
    def _get_bounds_param(name):
        raw_value = request.GET.get(name)
        if raw_value in (None, ''):
            return None

        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    def _get_requested_bounds():
        north = _get_bounds_param('bounds_north')
        south = _get_bounds_param('bounds_south')
        east = _get_bounds_param('bounds_east')
        west = _get_bounds_param('bounds_west')

        if None in (north, south, east, west):
            return None

        if north < south:
            north, south = south, north
        if not (-90 <= south <= 90 and -90 <= north <= 90):
            return None
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            return None

        return {
            'north': north,
            'south': south,
            'east': east,
            'west': west,
        }

    try:
        language_code = getattr(request, 'LANGUAGE_CODE', 'ru')[:2]
        # Создаем временный объект view для использования фильтров
        view = PropertyListView()
        view.request = request
        requested_bounds = _get_requested_bounds()
        
        # Получаем базовый queryset с минимальными данными для карты
        queryset = Property.objects.filter(
            is_active=True,
            status='available'
        ).select_related('district', 'location', 'property_type', 'agent').prefetch_related('images')
        
        # Применяем все фильтры
        queryset = view.apply_filters(queryset)

        if requested_bounds:
            queryset = queryset.filter(
                latitude__gte=requested_bounds['south'],
                latitude__lte=requested_bounds['north'],
            )

            if requested_bounds['west'] <= requested_bounds['east']:
                queryset = queryset.filter(
                    longitude__gte=requested_bounds['west'],
                    longitude__lte=requested_bounds['east'],
                )
            else:
                queryset = queryset.filter(
                    Q(longitude__gte=requested_bounds['west']) |
                    Q(longitude__lte=requested_bounds['east'])
                )
        
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
                'title': _get_translated_attr(prop, 'title', language_code, prop.title),
                'slug': prop.slug,
                'lat': float(prop.latitude),
                'lng': float(prop.longitude),
                'property_type': prop.property_type.name if prop.property_type else '',
                'property_type_label': (
                    _get_translated_attr(prop.property_type, 'name_display', language_code, prop.property_type.name_display)
                    if prop.property_type else ''
                ),
                'deal_type': prop.deal_type,
                'price': price_display,
                'location': (
                    _get_translated_attr(prop.location, 'name', language_code, prop.location.name)
                    if prop.location else (
                        _get_translated_attr(prop.district, 'name', language_code, prop.district.name)
                        if prop.district else ''
                    )
                ),
                'url': property_url,
                'image_url': image_url,
                'bedrooms': prop.bedrooms or 0,
                'bathrooms': prop.bathrooms or 0,
                'area': float(prop.area_total) if prop.area_total else 0,
                'agent_phone': agent_phone or BUSINESS_PROFILE['phone_e164']
            })
        
        return JsonResponse({
            'success': True,
            'properties': properties_data,
            'total_count': len(properties_data),
            'bounds_applied': bool(requested_bounds),
            'bounds': requested_bounds,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def map_districts_json(request):
    """District overlay payload for the catalog map."""

    def _build_centroid(points):
        lng = sum(point[0] for point in points) / len(points)
        lat = sum(point[1] for point in points) / len(points)
        return [lng, lat]

    def _build_padded_bounds_polygon(points):
        lng_values = [point[0] for point in points]
        lat_values = [point[1] for point in points]
        min_lng = min(lng_values)
        max_lng = max(lng_values)
        min_lat = min(lat_values)
        max_lat = max(lat_values)

        lng_span = max_lng - min_lng
        lat_span = max_lat - min_lat
        lng_padding = max(0.008, lng_span * 0.22)
        lat_padding = max(0.006, lat_span * 0.22)

        return [
            [min_lng - lng_padding, min_lat - lat_padding],
            [max_lng + lng_padding, min_lat - lat_padding],
            [max_lng + lng_padding, max_lat + lat_padding],
            [min_lng - lng_padding, max_lat + lat_padding],
            [min_lng - lng_padding, min_lat - lat_padding],
        ]

    def _cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def _build_convex_hull_polygon(points):
        unique_points = sorted({(float(lng), float(lat)) for lng, lat in points})
        if len(unique_points) < 3:
            return _build_padded_bounds_polygon(unique_points)

        lower = []
        for point in unique_points:
            while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
                lower.pop()
            lower.append(point)

        upper = []
        for point in reversed(unique_points):
            while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
                upper.pop()
            upper.append(point)

        hull = lower[:-1] + upper[:-1]
        if len(hull) < 3:
            return _build_padded_bounds_polygon(unique_points)

        polygon = [[float(lng), float(lat)] for lng, lat in hull]
        polygon.append(polygon[0])
        return polygon

    def _iter_geometry_points(geometry):
        geometry_type = (geometry or {}).get('type')
        coordinates = (geometry or {}).get('coordinates') or []

        if geometry_type == 'Polygon':
            for ring in coordinates:
                for lng, lat in ring:
                    yield float(lng), float(lat)
            return

        if geometry_type == 'MultiPolygon':
            for polygon in coordinates:
                for ring in polygon:
                    for lng, lat in ring:
                        yield float(lng), float(lat)

    def _build_geometry_center(geometry):
        points = list(_iter_geometry_points(geometry))
        if not points:
            return None

        lng_values = [point[0] for point in points]
        lat_values = [point[1] for point in points]
        return [
            (min(lng_values) + max(lng_values)) / 2,
            (min(lat_values) + max(lat_values)) / 2,
        ]

    try:
        district_boundaries = _load_phuket_district_boundaries()
        property_points = (
            Property.objects
            .filter(
                is_active=True,
                status='available',
                district__isnull=False,
                latitude__isnull=False,
                longitude__isnull=False,
            )
            .select_related('district')
            .values(
                'district_id',
                'district__slug',
                'district__name',
                'district__name_en',
                'latitude',
                'longitude',
            )
            .order_by('district__name')
        )

        grouped = {}
        for row in property_points:
            source_slug = row['district__slug']
            boundary_slug = PHUKET_DISTRICT_BOUNDARY_SLUG_ALIASES.get(source_slug, source_slug)
            grouped.setdefault(boundary_slug, {
                'boundary_slug': boundary_slug,
                'source_slugs': set(),
                'source_names': {},
                'points': [],
            })
            grouped[boundary_slug]['source_slugs'].add(source_slug)
            grouped[boundary_slug]['source_names'][source_slug] = row.get('district__name_en') or row['district__name']
            grouped[boundary_slug]['points'].append([
                float(row['longitude']),
                float(row['latitude']),
            ])

        districts_payload = []
        district_features = []

        for district in grouped.values():
            points = district['points']
            if not points:
                continue

            properties_count = len(points)
            boundary_feature = district_boundaries.get(district['boundary_slug'])
            source_slugs = district['source_slugs']
            preferred_slug = (
                district['boundary_slug']
                if district['boundary_slug'] in source_slugs
                else sorted(source_slugs)[0]
            )
            district_name = (
                district['source_names'].get(preferred_slug)
                or (boundary_feature or {}).get('properties', {}).get('name')
                or district['boundary_slug'].replace('-', ' ').title()
            )

            if boundary_feature:
                geometry = boundary_feature.get('geometry') or {}
                center = _build_geometry_center(geometry) or _build_centroid(points)
            else:
                center = _build_centroid(points)
                geometry = {
                    'type': 'Polygon',
                    'coordinates': [_build_convex_hull_polygon(points)],
                }

            district_payload = {
                'slug': preferred_slug,
                'name': district_name,
                'lat': center[1],
                'lng': center[0],
                'properties_count': properties_count,
                'polygon': geometry.get('coordinates', []),
            }
            districts_payload.append(district_payload)
            district_feature = {
                'type': 'Feature',
                'geometry': geometry,
                'properties': {
                    'slug': preferred_slug,
                    'name': district_name,
                    'properties_count': properties_count,
                    'center_lat': center[1],
                    'center_lng': center[0],
                },
            }
            district_features.append(district_feature)

        districts_payload.sort(key=lambda item: item['name'])

        return JsonResponse({
            'success': True,
            'districts': districts_payload,
            'geojson': {
                'type': 'FeatureCollection',
                'features': district_features,
            },
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'districts': [],
            'geojson': {
                'type': 'FeatureCollection',
                'features': [],
            },
        })


@require_http_methods(["GET", "HEAD"])
def map_protomaps_basemap_proxy(request):
    """Same-origin proxy for PMTiles basemap to avoid browser CORS failures."""
    if not PROTOMAPS_BASEMAP_URL:
        response = HttpResponse(status=204)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    try:
        upstream_headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
        }
        range_header = request.headers.get('Range')
        if range_header:
            upstream_headers['Range'] = range_header

        upstream_request = Request(
            PROTOMAPS_BASEMAP_URL,
            headers=upstream_headers,
            method='GET',
        )

        with urlopen(upstream_request, timeout=20) as upstream_response:
            status_code = getattr(upstream_response, 'status', 200)
            content_type = upstream_response.headers.get('Content-Type', 'application/octet-stream')
            response = HttpResponse(
                b'' if request.method == 'HEAD' else upstream_response.read(),
                status=status_code,
                content_type=content_type,
            )

            passthrough_headers = (
                'Accept-Ranges',
                'Content-Range',
                'Content-Length',
                'ETag',
                'Last-Modified',
                'Cache-Control',
            )
            for header_name in passthrough_headers:
                header_value = upstream_response.headers.get(header_name)
                if header_value:
                    response[header_name] = header_value

            response['Access-Control-Allow-Origin'] = '*'
            return response

    except HTTPError as error:
        response = HttpResponse(
            b'' if request.method == 'HEAD' else error.read(),
            status=error.code,
            content_type=error.headers.get('Content-Type', 'text/plain'),
        )
        for header_name in ('Accept-Ranges', 'Content-Range', 'Content-Length', 'ETag', 'Last-Modified', 'Cache-Control'):
            header_value = error.headers.get(header_name)
            if header_value:
                response[header_name] = header_value
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['Access-Control-Allow-Origin'] = '*'
        return response
    except URLError as error:
        response = JsonResponse({
            'success': False,
            'error': str(error),
        }, status=502)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response


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
