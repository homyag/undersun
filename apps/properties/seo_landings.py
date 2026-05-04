from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


WHITELIST_PROPERTY_TYPES = {'villa', 'condo', 'townhouse', 'land'}
WHITELIST_DISTRICTS = {'thalang', 'mueang-phuket', 'kathu-district'}
WHITELIST_LOCATIONS = {
    'cherng-talay',
    'rawai',
    'chalong',
    'karon',
    'patong',
    'wichit',
    'kamala',
    'bangtao',
}

ALLOWED_DEAL_TYPES = {'sale', 'rent'}

PROPERTY_TYPE_LANDING_LABELS = {
    'condo': {'ru': 'Квартиры', 'en': 'Condos', 'th': 'คอนโดมิเนียม'},
    'villa': {'ru': 'Виллы', 'en': 'Villas', 'th': 'วิลล่า'},
    'townhouse': {'ru': 'Таунхаусы', 'en': 'Townhouses', 'th': 'ทาวน์เฮาส์'},
    'land': {'ru': 'Земельные участки', 'en': 'Land plots', 'th': 'ที่ดิน'},
}

DEAL_LABELS = {
    'sale': {'ru': 'Продажа', 'en': 'Sale', 'th': 'ขาย'},
    'rent': {'ru': 'Аренда', 'en': 'Rent', 'th': 'เช่า'},
}

DEAL_HEADING_PHRASES = {
    'sale': {'ru': 'на продажу', 'en': 'for sale', 'th': 'สำหรับขาย'},
    'rent': {'ru': 'в аренду', 'en': 'for rent', 'th': 'สำหรับเช่า'},
}


@dataclass(frozen=True)
class LandingSignature:
    pattern: str
    deal_type: str = ''
    property_type: str = ''
    district: str = ''
    location: str = ''


def get_property_type_label(property_type_slug: str, language_code: str = 'ru') -> str:
    return PROPERTY_TYPE_LANDING_LABELS.get(property_type_slug, {}).get(language_code, property_type_slug)


def get_deal_label(deal_type: str, language_code: str = 'ru') -> str:
    return DEAL_LABELS.get(deal_type, {}).get(language_code, deal_type)


def get_deal_heading_phrase(deal_type: str, language_code: str = 'ru') -> str:
    return DEAL_HEADING_PHRASES.get(deal_type, {}).get(language_code, '')


def resolve_landing_signature(
    *,
    deal_type: str = '',
    property_type: str = '',
    district: str = '',
    location: str = '',
) -> Optional[LandingSignature]:
    deal_type = (deal_type or '').strip()
    property_type = (property_type or '').strip()
    district = (district or '').strip()
    location = (location or '').strip()

    if deal_type and deal_type not in ALLOWED_DEAL_TYPES:
        return None
    if property_type and property_type not in WHITELIST_PROPERTY_TYPES:
        return None
    if district and district not in WHITELIST_DISTRICTS:
        return None
    if location and location not in WHITELIST_LOCATIONS:
        return None

    if location and not district:
        return None

    if not any((deal_type, property_type, district, location)):
        return LandingSignature(pattern='catalog_root')

    if location:
        if property_type and deal_type:
            return LandingSignature('type_deal_location', deal_type, property_type, district, location)
        if property_type:
            return LandingSignature('type_location', '', property_type, district, location)
        if deal_type:
            return LandingSignature('deal_location', deal_type, '', district, location)
        return LandingSignature('location_only', '', '', district, location)

    if district:
        if property_type and deal_type:
            return LandingSignature('type_deal_district', deal_type, property_type, district, '')
        if property_type:
            return LandingSignature('type_district', '', property_type, district, '')
        if deal_type:
            return LandingSignature('deal_district', deal_type, '', district, '')
        return LandingSignature('district_only', '', '', district, '')

    if property_type and deal_type:
        return LandingSignature('type_deal', deal_type, property_type, '', '')
    if property_type:
        return LandingSignature('type_only', '', property_type, '', '')
    if deal_type:
        return LandingSignature('deal_only', deal_type, '', '', '')

    return None


def build_candidate_slugs(signature: LandingSignature) -> List[str]:
    slugs: List[str] = []

    if signature.pattern == 'catalog_root':
        slugs.append('properties_catalog')
    elif signature.pattern == 'deal_only':
        slugs.extend([
            f'properties_{signature.deal_type}',
            'properties_catalog',
        ])
    elif signature.pattern == 'type_only':
        slugs.extend([
            f'properties_type_{signature.property_type}',
            'properties_catalog',
        ])
    elif signature.pattern == 'type_deal':
        slugs.extend([
            f'properties_type_{signature.property_type}_{signature.deal_type}',
            f'properties_type_{signature.property_type}',
            f'properties_{signature.deal_type}',
            'properties_catalog',
        ])
    elif signature.pattern == 'district_only':
        slugs.extend([
            f'properties_district_{signature.district}',
            'properties_catalog',
        ])
    elif signature.pattern == 'location_only':
        slugs.extend([
            f'properties_location_{signature.location}',
            f'properties_district_{signature.district}',
            'properties_catalog',
        ])
    elif signature.pattern == 'deal_district':
        slugs.extend([
            f'properties_{signature.deal_type}_district_{signature.district}',
            f'properties_district_{signature.district}',
            f'properties_{signature.deal_type}',
            'properties_catalog',
        ])
    elif signature.pattern == 'deal_location':
        slugs.extend([
            f'properties_{signature.deal_type}_location_{signature.location}',
            f'properties_location_{signature.location}',
            f'properties_{signature.deal_type}_district_{signature.district}',
            f'properties_district_{signature.district}',
            f'properties_{signature.deal_type}',
            'properties_catalog',
        ])
    elif signature.pattern == 'type_district':
        slugs.extend([
            f'properties_type_{signature.property_type}_district_{signature.district}',
            f'properties_type_{signature.property_type}',
            f'properties_district_{signature.district}',
            'properties_catalog',
        ])
    elif signature.pattern == 'type_location':
        slugs.extend([
            f'properties_type_{signature.property_type}_location_{signature.location}',
            f'properties_type_{signature.property_type}_district_{signature.district}',
            f'properties_location_{signature.location}',
            f'properties_type_{signature.property_type}',
            f'properties_district_{signature.district}',
            'properties_catalog',
        ])
    elif signature.pattern == 'type_deal_district':
        slugs.extend([
            f'properties_type_{signature.property_type}_{signature.deal_type}_district_{signature.district}',
            f'properties_type_{signature.property_type}_{signature.deal_type}',
            f'properties_type_{signature.property_type}_district_{signature.district}',
            f'properties_{signature.deal_type}_district_{signature.district}',
            f'properties_type_{signature.property_type}',
            f'properties_{signature.deal_type}',
            f'properties_district_{signature.district}',
            'properties_catalog',
        ])
    elif signature.pattern == 'type_deal_location':
        slugs.extend([
            f'properties_type_{signature.property_type}_{signature.deal_type}_location_{signature.location}',
            f'properties_type_{signature.property_type}_{signature.deal_type}_district_{signature.district}',
            f'properties_type_{signature.property_type}_location_{signature.location}',
            f'properties_{signature.deal_type}_location_{signature.location}',
            f'properties_type_{signature.property_type}_{signature.deal_type}',
            f'properties_type_{signature.property_type}_district_{signature.district}',
            f'properties_{signature.deal_type}_district_{signature.district}',
            f'properties_location_{signature.location}',
            f'properties_type_{signature.property_type}',
            f'properties_{signature.deal_type}',
            f'properties_district_{signature.district}',
            'properties_catalog',
        ])

    seen = set()
    unique = []
    for slug in slugs:
        if slug in seen:
            continue
        seen.add(slug)
        unique.append(slug)
    return unique


def build_primary_slug(signature: LandingSignature) -> str:
    return build_candidate_slugs(signature)[0]


def build_landing_heading(
    *,
    language_code: str,
    property_type_label: str = '',
    deal_label: str = '',
    district_label: str = '',
    location_label: str = '',
) -> str:
    language_code = (language_code or 'ru')[:2]
    deal_phrase = get_deal_heading_phrase(deal_label.lower() if deal_label else '', language_code)

    # When a localized label was passed instead of a slug, recover phrase from display value.
    if not deal_phrase and deal_label:
        reverse_map = {value.get(language_code): key for key, value in DEAL_LABELS.items()}
        deal_slug = reverse_map.get(deal_label)
        if deal_slug:
            deal_phrase = get_deal_heading_phrase(deal_slug, language_code)

    if language_code == 'en':
        subject = property_type_label or 'Property'
        if location_label:
            geo = f'in {location_label}, Phuket'
        elif district_label:
            geo = f'in {district_label} district, Phuket'
        else:
            geo = 'in Phuket'
        if deal_phrase:
            return f'{subject} {deal_phrase} {geo}'
        return f'{subject} {geo}'

    if language_code == 'th':
        subject = property_type_label or 'อสังหาริมทรัพย์'
        if location_label:
            geo = f'ใน {location_label}, ภูเก็ต'
        elif district_label:
            geo = f'ในเขต {district_label}, ภูเก็ต'
        else:
            geo = 'ในภูเก็ต'
        if deal_phrase:
            return f'{subject} {deal_phrase} {geo}'
        return f'{subject} {geo}'

    subject = property_type_label or 'Недвижимость'
    if location_label:
        geo = f'в {location_label}, Пхукет'
    elif district_label:
        geo = f'в районе {district_label}, Пхукет'
    else:
        geo = 'на Пхукете'
    if deal_phrase:
        return f'{subject} {deal_phrase} {geo}'
    return f'{subject} {geo}'


def build_landing_block_payload(
    *,
    language_code: str,
    heading: str,
    signature: LandingSignature,
    property_type_label: str = '',
    district_label: str = '',
    location_label: str = '',
) -> dict:
    paragraphs = _build_landing_paragraphs(
        language_code=language_code,
        signature=signature,
        property_type_label=property_type_label,
        district_label=district_label,
        location_label=location_label,
    )

    return {
        'title': heading,
        'content': ''.join(f'<p>{paragraph}</p>' for paragraph in ([heading] + paragraphs)),
    }


def _build_landing_paragraphs(
    *,
    language_code: str,
    signature: LandingSignature,
    property_type_label: str = '',
    district_label: str = '',
    location_label: str = '',
) -> List[str]:
    if language_code == 'en':
        return _build_en_paragraphs(signature, property_type_label, district_label, location_label)
    if language_code == 'th':
        return _build_th_paragraphs(signature, property_type_label, district_label, location_label)
    return _build_ru_paragraphs(signature, property_type_label, district_label, location_label)


def _build_ru_paragraphs(signature: LandingSignature, property_type_label: str, district_label: str, location_label: str) -> List[str]:
    subject = property_type_label or 'недвижимость'
    lower_subject = subject[:1].lower() + subject[1:] if subject else 'недвижимость'

    type_focus = {
        'villa': f'В подборке собраны {lower_subject} для собственного проживания, отдыха и долгосрочных инвестиций на Пхукете.',
        'condo': f'В подборке представлены {lower_subject.lower()} для жизни, отдыха и инвестиционных целей, в том числе в востребованных курортных локациях.',
        'townhouse': f'В подборке собраны {lower_subject.lower()}, которые подходят для семейного проживания и покупки в районах с развитой городской инфраструктурой.',
        'land': f'В подборке представлены {lower_subject.lower()} для строительства, девелопмента и долгосрочного владения на Пхукете.',
        '': 'В каталоге Undersun Estate собраны актуальные предложения по продаже и аренде недвижимости на Пхукете: виллы, квартиры, таунхаусы и земельные участки.',
    }

    deal_focus = {
        'sale': 'Этот раздел помогает оценить объекты для покупки, сравнить бюджеты и выбрать вариант для собственного проживания или инвестиционной стратегии.',
        'rent': 'Этот раздел помогает подобрать объекты для аренды, сравнить форматы размещения и выбрать удобную локацию для жизни или отдыха на Пхукете.',
        '': 'Используйте каталог для быстрого перехода к нужному сегменту, сравнения локаций и подбора подходящих вариантов под ваши задачи.',
    }

    if location_label:
        geo_focus = f'Если вас интересует именно {location_label}, эта подборка помогает быстрее сравнить предложения в выбранной локации и посмотреть соседние варианты внутри каталога.'
    elif district_label:
        geo_focus = f'Если приоритетен район {district_label}, в этом разделе удобно ориентироваться по актуальным предложениям именно в выбранной части острова.'
    else:
        geo_focus = 'Используйте фильтры, чтобы уточнить район, тип недвижимости и бюджет и быстрее выйти на предложения, которые подходят под ваши цели.'

    return [
        type_focus.get(signature.property_type, type_focus['']),
        deal_focus.get(signature.deal_type, deal_focus['']),
        geo_focus,
    ]


def _build_en_paragraphs(signature: LandingSignature, property_type_label: str, district_label: str, location_label: str) -> List[str]:
    subject = property_type_label or 'property'

    type_focus = {
        'villa': f'This selection focuses on {subject.lower()} suited to private living, holiday use and long-term investment in Phuket.',
        'condo': f'This selection highlights {subject.lower()} for residence, resort-style stays and investment opportunities in sought-after areas.',
        'townhouse': f'This section brings together {subject.lower()} suitable for family living and practical ownership in urban parts of Phuket.',
        'land': f'This section focuses on {subject.lower()} for development, construction projects and long-term landholding in Phuket.',
        '': 'The Undersun Estate catalogue brings together current Phuket property listings for sale and rent, including villas, condos, townhouses and land plots.',
    }

    deal_focus = {
        'sale': 'Use this section to compare options for purchase, review budgets and shortlist properties for personal use or investment goals.',
        'rent': 'Use this section to compare rental formats, review locations and shortlist properties for living or extended stays in Phuket.',
        '': 'This section helps visitors move directly into the selected segment, compare locations and continue browsing relevant properties inside the catalogue.',
    }

    if location_label:
        geo_focus = f'If {location_label} is the priority, this page makes it easier to compare listings in that location and continue exploring nearby options.'
    elif district_label:
        geo_focus = f'If your focus is {district_label} district, this selection helps narrow the catalogue to the most relevant properties in that part of the island.'
    else:
        geo_focus = 'Use the catalogue filters to narrow down budget, property type and area and find options that match your goals faster.'

    return [
        type_focus.get(signature.property_type, type_focus['']),
        deal_focus.get(signature.deal_type, deal_focus['']),
        geo_focus,
    ]


def _build_th_paragraphs(signature: LandingSignature, property_type_label: str, district_label: str, location_label: str) -> List[str]:
    subject = property_type_label or 'อสังหาริมทรัพย์'

    type_focus = {
        'villa': f'คัดสรรนี้เน้น {subject} ที่เหมาะสำหรับการอยู่อาศัยส่วนตัว การพักผ่อน และการถือครองระยะยาวในภูเก็ต',
        'condo': f'คัดสรรนี้รวบรวม {subject} ที่เหมาะสำหรับอยู่อาศัย พักผ่อน และการลงทุนในทำเลยอดนิยมของภูเก็ต',
        'townhouse': f'ส่วนนี้รวบรวม {subject} ที่เหมาะสำหรับครอบครัวและการถือครองในย่านเมืองที่มีสิ่งอำนวยความสะดวกครบครัน',
        'land': f'ส่วนนี้รวบรวม {subject} สำหรับการพัฒนา ก่อสร้าง และการถือครองระยะยาวในภูเก็ต',
        '': 'แค็ตตาล็อกของ Undersun Estate รวบรวมข้อเสนออสังหาริมทรัพย์ในภูเก็ตที่พร้อมขายและให้เช่า ทั้งวิลล่า คอนโดมิเนียม ทาวน์เฮาส์ และที่ดิน',
    }

    deal_focus = {
        'sale': 'หน้านี้ช่วยให้เปรียบเทียบตัวเลือกสำหรับการซื้อ ตรวจสอบช่วงงบประมาณ และคัดเลือกอสังหาริมทรัพย์สำหรับอยู่อาศัยหรือการลงทุนได้ง่ายขึ้น',
        'rent': 'หน้านี้ช่วยให้เปรียบเทียบตัวเลือกสำหรับการเช่า ตรวจสอบทำเล และคัดเลือกอสังหาริมทรัพย์สำหรับอยู่อาศัยหรือพักระยะยาวได้สะดวกขึ้น',
        '': 'ส่วนนี้ช่วยให้ผู้ใช้เข้าถึงอสังหาริมทรัพย์ในกลุ่มที่ต้องการได้เร็วขึ้น เปรียบเทียบทำเล และค้นหาต่อภายในแค็ตตาล็อกได้สะดวก',
    }

    if location_label:
        geo_focus = f'หากคุณสนใจ {location_label} เป็นพิเศษ หน้านี้ช่วยให้เปรียบเทียบข้อเสนอในทำเลนั้นและดูตัวเลือกใกล้เคียงได้ง่ายขึ้น'
    elif district_label:
        geo_focus = f'หากคุณต้องการค้นหาในเขต {district_label} เป็นหลัก หน้านี้ช่วยคัดกรองข้อเสนอที่เกี่ยวข้องในพื้นที่นั้นได้รวดเร็วขึ้น'
    else:
        geo_focus = 'ใช้ตัวกรองของแค็ตตาล็อกเพื่อระบุงบประมาณ ประเภทอสังหาริมทรัพย์ และย่านที่สนใจ เพื่อค้นหาตัวเลือกที่เหมาะกับความต้องการได้เร็วขึ้น'

    return [
        type_focus.get(signature.property_type, type_focus['']),
        deal_focus.get(signature.deal_type, deal_focus['']),
        geo_focus,
    ]
