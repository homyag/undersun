import json
from urllib.parse import urlencode

from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.urls import reverse
from statistics import median
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.translation import gettext_lazy as _
from .models import District, Location
from .phuket_area_content import (
    get_district_description,
    get_district_faq_items,
    get_location_description,
    get_location_faq_items,
)
from apps.properties.models import Property, PropertyType
from apps.properties.public_inventory import public_sale_queryset
from apps.currency.services import CurrencyService
from apps.core.models import Team
from apps.core.utils import truncate_meta


IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
PROPERTY_TYPE_PRIORITY = ['villa', 'condo', 'townhouse', 'land']

LOCATION_PAGE_COPY = {
    'ru': {
        'list_title': 'Районы и локации Пхукета для покупки недвижимости | Undersun Estate',
        'list_description': 'Гид по районам Пхукета: {district_count} районов и {property_count} активных объектов. Сравните локации, инфраструктуру, типы недвижимости и подберите объект с Undersun Estate.',
        'list_intro': 'Сравните районы, локации и активные предложения, чтобы выбрать место под жизнь, отдых или инвестиционный сценарий.',
        'decision_kicker': 'как выбирать',
        'decision_heading': 'Локация на Пхукете зависит от сценария покупки',
        'decision_text': 'Для постоянной жизни важны школы, медицина и ежедневная логистика. Для отдыха — близость к пляжам, окружение и управление объектом. Для земли — титул, подъезд, ограничения и инфраструктура участка.',
        'overview_kicker': 'ориентир по локации',
        'district_context_heading': 'Что важно знать о районе',
        'location_context_heading': 'Что важно знать о локации',
        'district_hero_summary': 'Активные объекты, локации района и готовые подборки каталога для сравнения предложений на Пхукете.',
        'location_hero_summary': 'Активные объекты в {name}, карта, соседние локации и готовые подборки из каталога.',
        'district_overview_fallback': '{name} стоит рассматривать через доступность, типы объектов, окружение и ежедневную логистику. Перед подбором мы сверяем актуальные предложения, состояние проектов и практические ограничения конкретной части района.',
        'location_overview_fallback': 'Локация {name} в районе {district} подходит для покупателей, которым важно сравнить окружение, доступ к инфраструктуре и актуальный выбор объектов. Перед просмотром мы уточняем статус, цену и условия сделки по каждому объекту.',
        'media_caption_district': 'Район',
        'media_caption_location': 'Локация',
        'district_title': 'Недвижимость в районе {district}, Пхукет | Undersun Estate',
        'district_description': 'Недвижимость в районе {district}, Пхукет: {property_count} активных объектов, локации, медианные цены, карта и подбор вилл, апартаментов и земли с Undersun Estate.',
        'location_title': 'Недвижимость в {location}, {district} | Undersun Estate',
        'location_description': 'Недвижимость в {location}, район {district}: {property_count} активных объектов, цены, карта, соседние локации и подбор объектов на Пхукете с Undersun Estate.',
        'all_properties': 'Все объекты',
        'sale': 'Купить недвижимость',
        'villa': 'Виллы',
        'condo': 'Апартаменты и кондо',
        'townhouse': 'Таунхаусы',
        'land': 'Земельные участки',
        'all_description': 'Полный каталог активных объектов в этой локации.',
        'sale_description': 'Объекты на продажу с актуальными ценами и статусом.',
        'villa_description': 'Отдельные дома и виллы для жизни, отдыха или инвестиций.',
        'condo_description': 'Квартиры и кондоминиумы в проектах рядом с инфраструктурой.',
        'townhouse_description': 'Таунхаусы и компактные дома для жизни на Пхукете.',
        'land_description': 'Участки, где особенно важны титул, доступ и ограничения.',
        'default_type_description': 'Подборка объектов этого типа в выбранной локации.',
        'advisor_heading': 'Комментарий специалиста',
        'advisor_kicker': 'Локальная экспертиза',
        'advisor_text': 'Перед подбором мы смотрим не только на цену, но и на повседневную логистику, качество окружения, ликвидность и ограничения конкретного объекта. Актуальные условия всегда подтверждаем у владельца или застройщика перед просмотром.',
        'market_kicker': 'профиль района',
        'catalog_kicker': 'подборки объектов',
        'catalog_heading_district': 'Что смотреть в этом районе',
        'catalog_heading_location': 'Что смотреть в этой локации',
        'catalog_text': 'Ниже — готовые подборки из каталога. В них попадают только разделы, где сейчас есть активные объекты.',
        'district_selection_heading': 'Как использовать район в подборе',
        'district_selection_text': 'В {district} важно сравнивать не только цену и тип объекта, но и конкретную часть района: дорогу до пляжей, школ и магазинов, плотность застройки, шум и будущую ликвидность. Поэтому мы сначала фиксируем сценарий покупки, а затем уже подбираем объекты внутри подходящих локаций.',
        'location_selection_heading': 'Как локация связана с районом',
        'location_selection_text': '{location} стоит оценивать в контексте района {district}: соседние части района могут заметно отличаться по трафику, туристическому спросу, окружению и скорости перепродажи. Это помогает сравнивать объект не только по планировке и цене, но и по реальному сценарию владения.',
        'related_kicker': 'рядом',
        'related_heading': 'Соседние локации с активными объектами',
        'faq_kicker': 'вопросы',
        'faq_heading': 'Частые вопросы по локации',
        'open_selection': 'Открыть подборку',
        'active_count_label': 'активных объектов',
        'faq_count_q': 'Сколько объектов доступно в {name}?',
        'faq_count_a': 'Сейчас в каталоге по этой локации показано {count} активных объектов. Количество меняется после обновления статусов, цен и доступности.',
        'faq_types_q': 'Какие типы недвижимости здесь чаще встречаются?',
        'faq_types_a': 'В подборке представлены актуальные типы объектов из каталога: {types}. Если нужного формата нет на странице, мы проверим закрытые предложения и новые поступления.',
        'faq_viewing_q': 'Можно ли организовать просмотр объектов в этой локации?',
        'faq_viewing_a': 'Да. Мы согласуем очный или онлайн-показ, подготовим короткий список объектов и заранее уточним условия сделки у владельца или застройщика.',
        'faq_caveat_q': 'На что обратить внимание при выборе района?',
        'faq_caveat_a': 'Важно проверить транспортную доступность, дорогу до пляжей и школ, состояние проекта, юридические документы, расходы на обслуживание и реалистичный сценарий владения или перепродажи.',
    },
    'en': {
        'list_title': 'Phuket Districts and Locations for Property Buyers | Undersun Estate',
        'list_description': 'Guide to Phuket districts: {district_count} areas and {property_count} active listings. Compare locations, infrastructure, property types and shortlist Phuket real estate with Undersun Estate.',
        'list_intro': 'Compare Phuket districts, locations and active listings to choose the right area for living, holidays or an investment scenario.',
        'decision_kicker': 'how to choose',
        'decision_heading': 'The right Phuket location depends on the buying scenario',
        'decision_text': 'For everyday living, schools, healthcare and daily logistics matter. For holiday use, beach access, surroundings and property management are key. For land, title, access, restrictions and infrastructure should be checked first.',
        'overview_kicker': 'location context',
        'district_context_heading': 'What to know about',
        'location_context_heading': 'What to know about',
        'district_hero_summary': 'Active listings, district locations and ready-made catalogue selections for comparing Phuket property options.',
        'location_hero_summary': 'Active listings in {name}, map context, nearby areas and ready-made catalogue selections.',
        'district_overview_fallback': '{name} should be evaluated through access, property types, surroundings and daily logistics. Before shortlisting, we check current listings, project condition and practical limitations in the specific part of the district.',
        'location_overview_fallback': '{name} in {district} is useful to compare by surroundings, infrastructure access and the current property selection. Before a viewing, we confirm status, price and deal terms for each property.',
        'media_caption_district': 'District',
        'media_caption_location': 'Location',
        'district_title': 'Property in {district}, Phuket | Undersun Estate',
        'district_description': 'Property in {district}, Phuket: {property_count} active listings, locations, median prices, map and curated villas, apartments and land plots with Undersun Estate.',
        'location_title': 'Property in {location}, {district} | Undersun Estate',
        'location_description': 'Property in {location}, {district}: {property_count} active listings, prices, map, nearby locations and Phuket property shortlisting by Undersun Estate.',
        'all_properties': 'All properties',
        'sale': 'Property for sale',
        'villa': 'Villas',
        'condo': 'Apartments and condos',
        'townhouse': 'Townhouses',
        'land': 'Land plots',
        'all_description': 'Full list of active properties in this location.',
        'sale_description': 'For-sale listings with current prices and status.',
        'villa_description': 'Detached homes and villas for living, holidays or investment.',
        'condo_description': 'Apartments and condominiums near daily infrastructure.',
        'townhouse_description': 'Townhouses and compact homes for Phuket living.',
        'land_description': 'Land plots where title, access and restrictions matter.',
        'default_type_description': 'A filtered selection of this property type in the area.',
        'advisor_heading': 'Specialist comment',
        'advisor_kicker': 'Local expertise',
        'advisor_text': 'Before shortlisting, we look beyond price: daily logistics, surroundings, liquidity and property-specific limitations. Current terms are confirmed with the owner or developer before a viewing.',
        'market_kicker': 'area profile',
        'catalog_kicker': 'property selections',
        'catalog_heading_district': 'What to explore in this district',
        'catalog_heading_location': 'What to explore in this location',
        'catalog_text': 'Below are ready-made catalogue selections. They only include sections that currently have active listings.',
        'district_selection_heading': 'How we use this district in the shortlist',
        'district_selection_text': 'In {district}, it is important to compare not only price and property type, but also the exact part of the district: access to beaches, schools and shops, density, noise and future liquidity. We first define the buying scenario, then shortlist properties in the locations that fit it.',
        'location_selection_heading': 'How this location fits into the district',
        'location_selection_text': '{location} should be assessed within {district}: nearby parts of the same district can differ in traffic, buyer demand, surroundings and resale speed. This helps compare a property not only by layout and price, but by the real ownership scenario.',
        'related_kicker': 'nearby',
        'related_heading': 'Nearby locations with active listings',
        'faq_kicker': 'questions',
        'faq_heading': 'Common questions about this location',
        'open_selection': 'Open selection',
        'active_count_label': 'active listings',
        'faq_count_q': 'How many properties are available in {name}?',
        'faq_count_a': 'The catalogue currently shows {count} active listings for this location. The number changes as statuses, prices and availability are updated.',
        'faq_types_q': 'Which property types are most common here?',
        'faq_types_a': 'The current selection includes these property types from the catalogue: {types}. If the format you need is not listed, we can check off-market and new options.',
        'faq_viewing_q': 'Can I arrange a viewing in this location?',
        'faq_viewing_a': 'Yes. We can arrange an in-person or remote viewing, prepare a shortlist and confirm the current deal terms with the owner or developer in advance.',
        'faq_caveat_q': 'What should I check when choosing an area?',
        'faq_caveat_a': 'Check transport access, distance to beaches and schools, project condition, legal documents, maintenance costs and a realistic ownership or resale scenario.',
    },
    'th': {
        'list_title': 'ย่านและทำเลในภูเก็ตสำหรับซื้ออสังหาริมทรัพย์ | Undersun Estate',
        'list_description': 'คู่มือย่านในภูเก็ต: {district_count} พื้นที่และ {property_count} รายการที่พร้อมอยู่ เปรียบเทียบทำเล โครงสร้างพื้นฐาน และประเภทอสังหาริมทรัพย์กับ Undersun Estate',
        'list_intro': 'เปรียบเทียบย่าน ทำเล และรายการที่พร้อมอยู่ เพื่อเลือกพื้นที่ที่เหมาะกับการอยู่อาศัย การพักผ่อน หรือการลงทุน',
        'decision_kicker': 'วิธีเลือกทำเล',
        'decision_heading': 'ทำเลที่เหมาะสมในภูเก็ตขึ้นอยู่กับเป้าหมายการซื้อ',
        'decision_text': 'สำหรับการอยู่อาศัย ควรดูโรงเรียน การแพทย์ และการเดินทางประจำวัน สำหรับการพักผ่อน ควรดูการเข้าถึงชายหาด สภาพแวดล้อม และการจัดการทรัพย์ สำหรับที่ดิน ควรตรวจเอกสารสิทธิ์ ทางเข้า ข้อจำกัด และโครงสร้างพื้นฐานก่อน',
        'overview_kicker': 'บริบทของทำเล',
        'district_context_heading': 'สิ่งที่ควรรู้เกี่ยวกับย่าน',
        'location_context_heading': 'สิ่งที่ควรรู้เกี่ยวกับทำเล',
        'district_hero_summary': 'รายการอสังหาริมทรัพย์ที่พร้อมอยู่ ทำเลในย่าน และรายการคัดเลือกจากแคตตาล็อกเพื่อเปรียบเทียบตัวเลือกในภูเก็ต',
        'location_hero_summary': 'รายการที่พร้อมอยู่ใน {name} แผนที่ ทำเลใกล้เคียง และรายการคัดเลือกจากแคตตาล็อก',
        'district_overview_fallback': 'ควรประเมินย่าน {name} จากการเดินทาง ประเภทอสังหาริมทรัพย์ สภาพแวดล้อม และการใช้ชีวิตประจำวัน ก่อนคัดเลือกทรัพย์ เราตรวจรายการที่พร้อมอยู่ สภาพโครงการ และข้อจำกัดของพื้นที่นั้น',
        'location_overview_fallback': 'ทำเล {name} ในย่าน {district} เหมาะสำหรับการเปรียบเทียบสภาพแวดล้อม การเข้าถึงโครงสร้างพื้นฐาน และตัวเลือกอสังหาริมทรัพย์ที่พร้อมอยู่ ก่อนนัดชม เราจะยืนยันสถานะ ราคา และเงื่อนไขของแต่ละทรัพย์',
        'media_caption_district': 'ย่าน',
        'media_caption_location': 'ทำเล',
        'district_title': 'อสังหาริมทรัพย์ใน {district}, ภูเก็ต | Undersun Estate',
        'district_description': 'อสังหาริมทรัพย์ใน {district}, ภูเก็ต: {property_count} รายการที่พร้อมอยู่ ทำเล ราคาเฉลี่ย แผนที่ และการคัดเลือกวิลล่า คอนโด และที่ดินกับ Undersun Estate',
        'location_title': 'อสังหาริมทรัพย์ใน {location}, {district} | Undersun Estate',
        'location_description': 'อสังหาริมทรัพย์ใน {location}, {district}: {property_count} รายการที่พร้อมอยู่ ราคา แผนที่ ทำเลใกล้เคียง และบริการคัดเลือกอสังหาริมทรัพย์ในภูเก็ต',
        'all_properties': 'อสังหาริมทรัพย์ทั้งหมด',
        'sale': 'อสังหาริมทรัพย์สำหรับขาย',
        'villa': 'วิลล่า',
        'condo': 'อพาร์ตเมนต์และคอนโด',
        'townhouse': 'ทาวน์เฮาส์',
        'land': 'ที่ดิน',
        'all_description': 'รายการอสังหาริมทรัพย์ที่พร้อมอยู่ทั้งหมดในทำเลนี้',
        'sale_description': 'รายการขายพร้อมราคาและสถานะล่าสุด',
        'villa_description': 'บ้านเดี่ยวและวิลล่าสำหรับอยู่อาศัย พักผ่อน หรือการลงทุน',
        'condo_description': 'อพาร์ตเมนต์และคอนโดใกล้โครงสร้างพื้นฐานประจำวัน',
        'townhouse_description': 'ทาวน์เฮาส์และบ้านขนาดกะทัดรัดสำหรับชีวิตในภูเก็ต',
        'land_description': 'ที่ดินที่ต้องตรวจเอกสารสิทธิ์ ทางเข้า และข้อจำกัด',
        'default_type_description': 'รายการประเภทอสังหาริมทรัพย์นี้ในพื้นที่ที่เลือก',
        'advisor_heading': 'ความคิดเห็นจากผู้เชี่ยวชาญ',
        'advisor_kicker': 'ความเชี่ยวชาญในพื้นที่',
        'advisor_text': 'ก่อนคัดเลือกทรัพย์ เราดูมากกว่าราคา เช่น การเดินทาง สภาพแวดล้อม สภาพคล่อง และข้อจำกัดของทรัพย์ เงื่อนไขล่าสุดจะยืนยันกับเจ้าของหรือผู้พัฒนาโครงการก่อนนัดชม',
        'market_kicker': 'โปรไฟล์พื้นที่',
        'catalog_kicker': 'รายการคัดเลือกอสังหาริมทรัพย์',
        'catalog_heading_district': 'ควรดูอะไรในย่านนี้',
        'catalog_heading_location': 'ควรดูอะไรในทำเลนี้',
        'catalog_text': 'ด้านล่างคือรายการคัดเลือกจากแคตตาล็อก โดยจะแสดงเฉพาะหมวดที่มีรายการพร้อมอยู่ในตอนนี้',
        'district_selection_heading': 'เราใช้ย่านนี้ในการคัดเลือกอย่างไร',
        'district_selection_text': 'ในย่าน {district} ไม่ควรดูเพียงราคาและประเภททรัพย์ แต่ควรดูพื้นที่ย่อยของย่านนั้นด้วย เช่น การเดินทางไปชายหาด โรงเรียน ร้านค้า ความหนาแน่น เสียงรบกวน และสภาพคล่องในอนาคต เราจึงเริ่มจากเป้าหมายการซื้อ แล้วจึงคัดเลือกทรัพย์ในทำเลที่เหมาะสม',
        'location_selection_heading': 'ทำเลนี้สัมพันธ์กับย่านอย่างไร',
        'location_selection_text': 'ควรประเมิน {location} ภายในบริบทของย่าน {district} เพราะพื้นที่ใกล้เคียงในย่านเดียวกันอาจต่างกันมากทั้งเรื่องการจราจร ความต้องการของผู้ซื้อ สภาพแวดล้อม และความเร็วในการขายต่อ วิธีนี้ช่วยเปรียบเทียบทรัพย์จากทั้งราคา แปลน และสถานการณ์การถือครองจริง',
        'related_kicker': 'ใกล้เคียง',
        'related_heading': 'ทำเลใกล้เคียงที่มีรายการพร้อมอยู่',
        'faq_kicker': 'คำถาม',
        'faq_heading': 'คำถามที่พบบ่อยเกี่ยวกับทำเลนี้',
        'open_selection': 'เปิดรายการ',
        'active_count_label': 'รายการที่พร้อมอยู่',
        'faq_count_q': 'มีอสังหาริมทรัพย์ใน {name} กี่รายการ?',
        'faq_count_a': 'ขณะนี้แคตตาล็อกแสดง {count} รายการที่พร้อมอยู่ในทำเลนี้ จำนวนอาจเปลี่ยนตามการอัปเดตราคา สถานะ และความพร้อม',
        'faq_types_q': 'ประเภทอสังหาริมทรัพย์ที่พบบ่อยในทำเลนี้คืออะไร?',
        'faq_types_a': 'รายการปัจจุบันมีประเภทอสังหาริมทรัพย์จากแคตตาล็อก: {types} หากไม่พบรูปแบบที่ต้องการ เราสามารถตรวจสอบตัวเลือกใหม่หรือข้อเสนอที่ไม่ได้เผยแพร่ได้',
        'faq_viewing_q': 'สามารถนัดชมทรัพย์ในทำเลนี้ได้หรือไม่?',
        'faq_viewing_a': 'ได้ เราสามารถจัดนัดชมจริงหรือวิดีโอทัวร์ เตรียมรายการคัดเลือก และยืนยันเงื่อนไขล่าสุดกับเจ้าของหรือผู้พัฒนาโครงการล่วงหน้า',
        'faq_caveat_q': 'ควรตรวจอะไรเมื่อเลือกทำเล?',
        'faq_caveat_a': 'ควรตรวจการเดินทาง ระยะทางถึงชายหาดและโรงเรียน สภาพโครงการ เอกสารทางกฎหมาย ค่าใช้จ่ายดูแลรักษา และสมมติฐานการถือครองหรือขายต่ออย่างสมจริง',
    },
}


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


def _language_code(request):
    return (getattr(request, 'LANGUAGE_CODE', '') or 'ru').split('-')[0]


def _copy_for(language_code):
    return LOCATION_PAGE_COPY.get(language_code, LOCATION_PAGE_COPY['ru'])


def _is_placeholder_location_text(value):
    if not value:
        return True

    text = ' '.join(str(value).strip().split())
    if not text:
        return True

    text_lower = text.lower()
    placeholder_prefixes = (
        'район ',
        'локация ',
        'district ',
        'location ',
    )
    return len(text.split()) <= 4 and text_lower.startswith(placeholder_prefixes)


def _localized_text(obj, field_name, language_code):
    localized_value = getattr(obj, f'{field_name}_{language_code}', None)
    if localized_value and not _is_placeholder_location_text(localized_value):
        return localized_value
    if language_code == 'ru':
        fallback_value = getattr(obj, f'{field_name}_ru', None) or getattr(obj, field_name, '')
        if not _is_placeholder_location_text(fallback_value):
            return fallback_value
    return ''


def _median_sale_price_for_currency(queryset, currency_code):
    values_thb = list(
        queryset
        .filter(deal_type__in=['sale', 'both'])
        .filter(price_sale_thb__isnull=False)
        .values_list('price_sale_thb', flat=True)
    )
    if not values_thb:
        return None, None

    median_thb = median(values_thb)
    target_code = (currency_code or 'THB').upper()
    target_currency = CurrencyService.get_currency_by_code(target_code)

    if target_code == 'THB' and target_currency:
        return median_thb, target_currency

    if target_currency:
        converted_price = CurrencyService.convert_price(median_thb, 'THB', target_code)
        if converted_price is not None:
            return converted_price, target_currency

    return median_thb, CurrencyService.get_currency_by_code('THB')


def _catalog_url(url_name, params=None, args=None):
    base_url = reverse(url_name, args=args or [])
    clean_params = {}
    for key, value in (params or {}).items():
        if value in (None, '', [], ()):
            continue
        clean_params[key] = value
    if not clean_params:
        return base_url
    return f'{base_url}?{urlencode(clean_params, doseq=True)}'


def _geo_params(district=None, location=None):
    params = {}
    if district:
        params['district'] = district.slug
    if location:
        params['location'] = location.slug
    return params


def _property_type_queryset(type_names):
    priority_case = Case(
        *[
            When(name=property_type, then=Value(index))
            for index, property_type in enumerate(PROPERTY_TYPE_PRIORITY)
        ],
        default=Value(len(PROPERTY_TYPE_PRIORITY)),
        output_field=IntegerField(),
    )
    return (
        PropertyType.objects
        .filter(name__in=type_names)
        .annotate(_type_priority=priority_case)
        .order_by('_type_priority', 'name_display')
    )


def _build_catalog_links(base_queryset, language_code, district=None, location=None):
    copy = _copy_for(language_code)
    params = _geo_params(district, location)
    links = []
    total_count = base_queryset.count()

    if total_count:
        links.append({
            'label': copy['all_properties'],
            'description': copy['all_description'],
            'url': _catalog_url('properties:property_list', params),
            'count': total_count,
            'icon': 'fas fa-border-all',
        })

    sale_count = base_queryset.filter(deal_type__in=['sale', 'both']).count()
    if sale_count:
        links.append({
            'label': copy['sale'],
            'description': copy['sale_description'],
            'url': _catalog_url('properties:property_sale', params),
            'count': sale_count,
            'icon': 'fas fa-key',
        })

    type_counts = {
        item['property_type__name']: item['count']
        for item in (
            base_queryset
            .filter(property_type__isnull=False)
            .values('property_type__name')
            .annotate(count=Count('id'))
        )
    }
    for property_type in _property_type_queryset(type_counts.keys()):
        property_type_count = type_counts.get(property_type.name, 0)
        if not property_type_count:
            continue
        links.append({
            'label': copy.get(property_type.name) or property_type.name_display,
            'description': copy.get(f'{property_type.name}_description') or copy['default_type_description'],
            'url': _catalog_url(
                'properties:property_by_type',
                params,
                args=[property_type.name],
            ),
            'count': property_type_count,
            'icon': {
                'villa': 'fas fa-house-chimney-window',
                'condo': 'fas fa-building',
                'townhouse': 'fas fa-house-user',
                'land': 'fas fa-drafting-compass',
            }.get(property_type.name, 'fas fa-home'),
            'property_type': property_type.name,
        })

    return links


def _build_related_location_links(district, current_location=None, limit=6):
    queryset = (
        district.locations
        .annotate(
            active_property_count=Count(
                'property',
                filter=Q(
                    property__is_active=True,
                    property__status='available',
                    property__deal_type='sale',
                ),
            )
        )
        .filter(active_property_count__gt=0)
        .order_by('-active_property_count', 'name')
    )
    if current_location:
        queryset = queryset.exclude(pk=current_location.pk)
    return list(queryset[:limit])


def _get_location_advisor():
    advisor = (
        Team.objects
        .filter(is_active=True)
        .filter(
            Q(first_name_ru__iexact='Богдан')
            | Q(first_name_en__iexact='Bogdan')
            | Q(first_name__iexact='Bogdan')
        )
        .order_by('display_order', 'last_name')
        .first()
    )
    if advisor:
        return advisor
    return Team.objects.filter(is_active=True).order_by('display_order', 'last_name').first()


DISTRICT_MARKET_INFO = {
    'ru': {
        'krabi': {
            'profile': 'Спокойная альтернатива Пхукету',
            'focus': 'Долгосрочная жизнь, пляжные зоны и городская инфраструктура',
            'note': 'Краби стоит сравнивать с Пхукетом по цели покупки: жизнь у моря, релокация, сезонный отдых или спокойный lifestyle. Перед сделкой важны транспорт, медицина, ликвидность и реальный выбор объектов.',
        },
        'thalang': {
            'profile': 'Курортный и семейный спрос',
            'focus': 'Виллы, кондо, участки и новые проекты',
            'note': 'Thalang часто выбирают за близость к аэропорту, Bang Tao, Laguna и северным пляжам. Здесь особенно важно сравнивать инфраструктуру проекта, доступ к пляжу и реальные расходы на содержание.',
        },
        'mueang-phuket': {
            'profile': 'Городская инфраструктура и долгосрочный спрос',
            'focus': 'Кондо, дома, таунхаусы и объекты для жизни',
            'note': 'Mueang Phuket удобен для постоянной жизни: школы, медицина, торговые центры и городская логистика рядом. Для инвестиций важно оценивать не только цену, но и ликвидность конкретной локации.',
        },
        'kathu-district': {
            'profile': 'Баланс города и туристических зон',
            'focus': 'Кондо, виллы и объекты рядом с Patong/Kamala',
            'note': 'Kathu District сочетает доступ к пляжам, городской инфраструктуре и туристическому спросу. Перед покупкой стоит отдельно проверять шум, подъездные дороги и сезонность спроса.',
        },
        'phuket': {
            'profile': 'Широкий островной поиск',
            'focus': 'Сравнение районов и форматов объектов',
            'note': 'Подбор по всему Пхукету лучше начинать со сценария: жизнь, отдых, перепродажа, земля или релокация. После этого район и тип объекта становятся намного понятнее.',
        },
        'default': {
            'profile': 'Локальный спрос и практичная логистика',
            'focus': 'Жилая и инвестиционная недвижимость',
            'note': 'Мы оцениваем район через реальные маршруты, окружение, качество проектов, доступность сервиса и актуальную структуру предложений в каталоге.',
        },
    },
    'en': {
        'krabi': {
            'profile': 'A calmer alternative to Phuket',
            'focus': 'Long-term living, beach areas and town infrastructure',
            'note': 'Krabi should be compared with Phuket by buying scenario: seaside living, relocation, seasonal use or a quieter lifestyle. Transport, healthcare, liquidity and real inventory depth should be checked before buying.',
        },
        'thalang': {
            'profile': 'Resort and family demand',
            'focus': 'Villas, condos, land and new projects',
            'note': 'Thalang is often chosen for access to the airport, Bang Tao, Laguna and the northern beaches. Project infrastructure, beach access and maintenance costs should be checked carefully.',
        },
        'mueang-phuket': {
            'profile': 'Urban infrastructure and long-term demand',
            'focus': 'Condos, houses, townhouses and living-focused homes',
            'note': 'Mueang Phuket suits everyday living with schools, healthcare, shopping and city logistics nearby. For investment, liquidity of the exact location matters as much as the asking price.',
        },
        'kathu-district': {
            'profile': 'City access and tourist-area balance',
            'focus': 'Condos, villas and homes near Patong/Kamala',
            'note': 'Kathu District combines access to beaches, city infrastructure and tourist demand. Noise, access roads and seasonality should be reviewed before buying.',
        },
        'phuket': {
            'profile': 'Island-wide property search',
            'focus': 'Comparing areas and property formats',
            'note': 'An island-wide search should start from the scenario: living, holidays, resale, land or relocation. After that, the area and property type become much clearer.',
        },
        'default': {
            'profile': 'Local demand and practical logistics',
            'focus': 'Residential and investment property',
            'note': 'We evaluate each area through real routes, surroundings, project quality, service access and the current structure of active listings.',
        },
    },
    'th': {
        'krabi': {
            'profile': 'ทางเลือกที่สงบกว่าภูเก็ต',
            'focus': 'การอยู่อาศัยระยะยาว พื้นที่ชายหาด และโครงสร้างเมือง',
            'note': 'ควรเปรียบเทียบ Krabi กับภูเก็ตตามเป้าหมายการซื้อ เช่น อยู่อาศัยริมทะเล ย้ายถิ่นฐาน พักผ่อนตามฤดูกาล หรือไลฟ์สไตล์ที่สงบกว่า ก่อนซื้อควรตรวจการเดินทาง การแพทย์ สภาพคล่อง และตัวเลือกทรัพย์จริง',
        },
        'thalang': {
            'profile': 'ความต้องการแบบรีสอร์ตและครอบครัว',
            'focus': 'วิลล่า คอนโด ที่ดิน และโครงการใหม่',
            'note': 'Thalang มักถูกเลือกเพราะใกล้สนามบิน Bang Tao, Laguna และชายหาดทางเหนือ ควรตรวจโครงสร้างพื้นฐานของโครงการ การเข้าถึงชายหาด และค่าใช้จ่ายดูแลรักษาอย่างละเอียด',
        },
        'mueang-phuket': {
            'profile': 'โครงสร้างเมืองและความต้องการระยะยาว',
            'focus': 'คอนโด บ้าน ทาวน์เฮาส์ และที่อยู่อาศัย',
            'note': 'Mueang Phuket เหมาะกับการอยู่อาศัยประจำ มีโรงเรียน โรงพยาบาล ศูนย์การค้า และการเดินทางในเมืองใกล้เคียง สำหรับการลงทุน สภาพคล่องของทำเลสำคัญพอๆ กับราคา',
        },
        'kathu-district': {
            'profile': 'สมดุลระหว่างเมืองและโซนท่องเที่ยว',
            'focus': 'คอนโด วิลล่า และบ้านใกล้ Patong/Kamala',
            'note': 'Kathu District เชื่อมต่อชายหาด โครงสร้างเมือง และความต้องการท่องเที่ยว ก่อนซื้อควรตรวจเรื่องเสียง ถนนทางเข้า และฤดูกาลของความต้องการจากผู้ซื้อ',
        },
        'phuket': {
            'profile': 'ค้นหาอสังหาริมทรัพย์ทั่วเกาะ',
            'focus': 'เปรียบเทียบพื้นที่และรูปแบบทรัพย์',
            'note': 'การค้นหาทั่วภูเก็ตควรเริ่มจากเป้าหมาย: อยู่อาศัย พักผ่อน ขายต่อ ที่ดิน หรือย้ายถิ่นฐาน จากนั้นทำเลและประเภททรัพย์จะชัดเจนขึ้น',
        },
        'default': {
            'profile': 'ความต้องการในพื้นที่และการเดินทางจริง',
            'focus': 'ที่อยู่อาศัยและอสังหาริมทรัพย์เพื่อการลงทุน',
            'note': 'เราประเมินพื้นที่จากเส้นทางจริง สภาพแวดล้อม คุณภาพโครงการ การเข้าถึงบริการ และรายการที่พร้อมอยู่ในแคตตาล็อก',
        },
    },
}


def _get_district_market_info(district, language_code):
    language_items = DISTRICT_MARKET_INFO.get(language_code, DISTRICT_MARKET_INFO['ru'])
    return language_items.get(district.slug) or language_items['default']


def _build_faq_items(name, count, catalog_links, language_code):
    copy = _copy_for(language_code)
    type_labels = [
        link['label']
        for link in catalog_links
        if link.get('property_type')
    ][:4]
    if not type_labels:
        type_labels = [copy['all_properties']]
    types_text = ', '.join(type_labels)
    return [
        {
            'question': copy['faq_count_q'].format(name=name),
            'answer': copy['faq_count_a'].format(count=count),
        },
        {
            'question': copy['faq_types_q'],
            'answer': copy['faq_types_a'].format(types=types_text),
        },
        {
            'question': copy['faq_viewing_q'],
            'answer': copy['faq_viewing_a'],
        },
        {
            'question': copy['faq_caveat_q'],
            'answer': copy['faq_caveat_a'],
        },
    ]


def _merge_location_faq_items(slug, generic_items, language_code):
    source_items = get_location_faq_items(slug, language_code)
    if not source_items:
        return generic_items
    return source_items + generic_items[:2]


def _merge_district_faq_items(slug, generic_items, language_code):
    source_items = get_district_faq_items(slug, language_code)
    if not source_items:
        return generic_items
    return source_items + generic_items[:2]


def _place_schema_json(request, *, name, url, contained_in=None, image_url=None):
    absolute_url = request.build_absolute_uri(url)
    site_root_url = request.build_absolute_uri('/').rstrip('/') + '/'
    language_code = _language_code(request)
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Place',
        '@id': f'{absolute_url}#place',
        'name': name,
        'url': absolute_url,
        'inLanguage': language_code,
        'containedInPlace': {
            '@type': 'Place',
            'name': 'Phuket',
        },
        'isPartOf': {
            '@type': 'WebSite',
            '@id': f'{site_root_url}#website',
            'name': 'Undersun Estate',
            'url': site_root_url,
        },
    }
    if contained_in:
        schema['containedInPlace'] = {
            '@type': 'Place',
            'name': contained_in,
        }
    if image_url:
        schema['image'] = request.build_absolute_uri(image_url)
    return json.dumps(schema, ensure_ascii=False)


def _set_page_seo(request, title, description):
    labels = {
        'ru': 'Страница {page}',
        'en': 'Page {page}',
        'th': 'หน้า {page}',
    }
    language_code = _language_code(request)
    suffix = ''
    try:
        page_number = int(request.GET.get('page') or 1)
    except (TypeError, ValueError):
        page_number = 1
    if page_number > 1:
        suffix = f" | {labels.get(language_code, labels['en']).format(page=page_number)}"

    request.seo_page_title = f'{title}{suffix}'
    request.seo_page_description = truncate_meta(f'{description}{suffix}')
    request.seo_pagination_customized = True


def _annotate_property_schema_titles(properties, language_code='ru'):
    object_list = getattr(properties, 'object_list', properties)
    for property_obj in object_list:
        title_getter = getattr(property_obj, 'get_localized_display_title', None)
        if callable(title_getter):
            property_obj.localized_title = title_getter(language_code)
        else:
            property_obj.localized_title = property_obj.title
    return properties


class LocationListView(ListView):
    model = District
    template_name = 'locations/list.html'
    context_object_name = 'districts'

    def get_queryset(self):
        return District.objects.annotate(
            properties_count=Count('property', filter=Q(
                property__is_active=True,
                property__status='available',
                property__deal_type='sale',
            ))
        ).filter(properties_count__gt=0)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = _language_code(self.request)
        copy = _copy_for(language_code)
        total_property_count = sum(district.properties_count for district in context['districts'])
        _set_page_seo(
            self.request,
            copy['list_title'],
            copy['list_description'].format(
                district_count=len(context['districts']),
                property_count=total_property_count,
            ),
        )

        for district in context['districts']:
            district.static_image = _get_static_location_image(district.slug)
            district.market_info = _get_district_market_info(district, language_code)
            district.localized_description = (
                get_district_description(district.slug, language_code)
                or _localized_text(district, 'description', language_code)
                or copy['district_overview_fallback'].format(name=district.name)
            )

        context['location_page_copy'] = copy
        context['total_property_count'] = total_property_count
        context['location_advisor'] = _get_location_advisor()
        return context


class DistrictDetailView(DetailView):
    model = District
    template_name = 'locations/district_detail.html'
    context_object_name = 'district'
    slug_url_kwarg = 'district_slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language_code = _language_code(self.request)
        copy = _copy_for(language_code)

        # Недвижимость в районе
        base_queryset = public_sale_queryset(Property.objects.filter(
            district=self.object,
            is_active=True,
            status='available',
        )).select_related('property_type').prefetch_related('images')

        currency_code = CurrencyService.get_selected_currency_code(self.request)
        median_price, median_currency = _median_sale_price_for_currency(
            base_queryset,
            currency_code,
        )

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(base_queryset, 12)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        _annotate_property_schema_titles(page_obj, language_code)

        context['properties'] = page_obj
        context['district_property_count'] = paginator.count
        context['selected_currency'] = CurrencyService.get_currency_by_code(currency_code)
        context['district_avg_price'] = median_price
        context['district_avg_price_currency'] = median_currency
        context['district_description_text'] = (
            get_district_description(self.object.slug, language_code)
            or _localized_text(self.object, 'description', language_code)
            or copy['district_overview_fallback'].format(name=self.object.name)
        )
        _set_page_seo(
            self.request,
            copy['district_title'].format(district=self.object.name),
            copy['district_description'].format(
                district=self.object.name,
                property_count=paginator.count,
            ),
        )

        # Локации в районе
        locations = (
            self.object.locations
            .annotate(
                active_property_count=Count(
                    'property',
                    filter=Q(
                        property__is_active=True,
                        property__status='available',
                        property__deal_type='sale',
                    ),
                )
            )
            .filter(active_property_count__gt=0)
            .order_by('-active_property_count', 'name')
        )
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
            median_value, location_median_currency = _median_sale_price_for_currency(
                location_queryset,
                currency_code,
            )

            type_stats = []
            for property_type in property_types:
                type_queryset = location_queryset.filter(property_type=property_type)
                type_count = type_queryset.count()
                type_median, type_median_currency = _median_sale_price_for_currency(
                    type_queryset,
                    currency_code,
                )

                type_stats.append({
                    'property_type': property_type,
                    'count': type_count,
                    'median_price': type_median,
                    'median_currency': type_median_currency,
                })

            location_stats.append({
                'location': location,
                'property_count': location_count,
                'median_price': median_value,
                'median_currency': location_median_currency,
                'types': type_stats,
            })

        context['location_stats'] = location_stats
        context['district_static_image'] = _get_static_location_image(self.object.slug)
        context['district_market'] = _get_district_market_info(self.object, language_code)
        context['district_travel_time'] = DISTRICT_TRAVEL_TIMES.get(self.object.slug)
        context['district_hero_summary_text'] = copy['district_hero_summary']
        context['catalog_links'] = _build_catalog_links(
            base_queryset,
            language_code,
            district=self.object,
        )
        context['district_selection_heading'] = copy['district_selection_heading']
        context['district_selection_text'] = copy['district_selection_text'].format(
            district=self.object.name,
        )
        context['related_location_links'] = _build_related_location_links(self.object, limit=8)
        context['location_page_copy'] = copy
        context['location_advisor'] = _get_location_advisor()
        context['location_faq_items'] = _merge_district_faq_items(
            self.object.slug,
            _build_faq_items(
                self.object.name,
                paginator.count,
                context['catalog_links'],
                language_code,
            ),
            language_code,
        )
        context['district_place_schema_json'] = _place_schema_json(
            self.request,
            name=self.object.name,
            url=self.object.get_absolute_url(),
            image_url=(self.object.image.url if self.object.image else context['district_static_image']),
        )
        if self.object.image:
            context['og_image_url'] = self.request.build_absolute_uri(self.object.image.url)
        elif context['district_static_image']:
            context['og_image_url'] = self.request.build_absolute_uri(context['district_static_image'])

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
        language_code = _language_code(self.request)
        copy = _copy_for(language_code)

        # Недвижимость в локации
        base_queryset = public_sale_queryset(Property.objects.filter(
            location=self.object,
            is_active=True,
            status='available',
        )).select_related('property_type').prefetch_related('images')

        currency_code = CurrencyService.get_selected_currency_code(self.request)
        median_price, median_currency = _median_sale_price_for_currency(
            base_queryset,
            currency_code,
        )

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(base_queryset, 12)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        _annotate_property_schema_titles(page_obj, language_code)

        context['properties'] = page_obj
        context['district_property_count'] = paginator.count
        context['location_property_count'] = paginator.count
        context['district'] = self.object.district
        context['selected_currency'] = CurrencyService.get_currency_by_code(currency_code)
        context['district_avg_price'] = median_price
        context['location_avg_price'] = median_price
        context['location_avg_price_currency'] = median_currency
        context['location_description_text'] = (
            get_location_description(self.object.slug, language_code)
            or _localized_text(self.object, 'description', language_code)
            or copy['location_overview_fallback'].format(
                name=self.object.name,
                district=self.object.district.name,
            )
        )
        context['location_static_image'] = (
            _get_static_location_image(self.object.slug)
            or _get_static_location_image(self.object.district.slug)
        )
        context['district_static_image'] = _get_static_location_image(self.object.district.slug)
        context['district_market'] = _get_district_market_info(self.object.district, language_code)
        context['district_travel_time'] = DISTRICT_TRAVEL_TIMES.get(self.object.district.slug)
        context['location_hero_summary_text'] = copy['location_hero_summary'].format(
            name=self.object.name,
        )
        context['catalog_links'] = _build_catalog_links(
            base_queryset,
            language_code,
            district=self.object.district,
            location=self.object,
        )
        context['location_selection_heading'] = copy['location_selection_heading']
        context['location_selection_text'] = copy['location_selection_text'].format(
            location=self.object.name,
            district=self.object.district.name,
        )
        context['related_location_links'] = _build_related_location_links(
            self.object.district,
            current_location=self.object,
            limit=6,
        )
        context['location_page_copy'] = copy
        context['location_advisor'] = _get_location_advisor()
        context['location_faq_items'] = _merge_location_faq_items(
            self.object.slug,
            _build_faq_items(
                self.object.name,
                paginator.count,
                context['catalog_links'],
                language_code,
            ),
            language_code,
        )
        context['location_place_schema_json'] = _place_schema_json(
            self.request,
            name=self.object.name,
            url=self.object.get_absolute_url(),
            contained_in=self.object.district.name,
            image_url=(
                self.object.image.url
                if self.object.image
                else context['location_static_image']
            ),
        )
        if self.object.image:
            context['og_image_url'] = self.request.build_absolute_uri(self.object.image.url)
        elif context['location_static_image']:
            context['og_image_url'] = self.request.build_absolute_uri(context['location_static_image'])
        _set_page_seo(
            self.request,
            copy['location_title'].format(
                location=self.object.name,
                district=self.object.district.name,
            ),
            copy['location_description'].format(
                location=self.object.name,
                district=self.object.district.name,
                property_count=paginator.count,
            ),
        )

        return context
DISTRICT_TRAVEL_TIMES = {
    'mueang-phuket': {
        'car': '35–40',
        'bus': '60–70',
        'note': _('Такси или трансфер — около 35 минут; автобус дольше из-за остановок.')
    },
    'kathu-district': {
        'car': '30–45',
        'bus': '50–60',
        'note': _('Среднее ~40 минут на автомобиле, автобусом чуть дольше.')
    },
    'thalang': {
        'car': '10–15',
        'bus': '15',
        'note': _('Аэропорт находится в пределах района — самый быстрый доступ.')
    },
    'phuket': {
        'car': '15–60',
        'bus': '30–90',
        'note': _('Время зависит от выбранной части острова и дорожной ситуации.')
    },
}
