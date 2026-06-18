import builtins
import os
import re
from io import BytesIO

from django.db import models
from django.db.models import Case, When, Value, IntegerField
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _, override, get_language
from django.urls import reverse
from django.core.files.base import ContentFile
from django.utils.html import strip_tags
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit
from PIL import Image
from tinymce.models import HTMLField

from apps.core.utils import truncate_meta
from apps.locations.models import District, Location


PROPERTY_TYPE_SEO_LABELS = {
    'condo': {'ru': 'Кондоминиум', 'en': 'Condo', 'th': 'คอนโดมิเนียม'},
    'villa': {'ru': 'Вилла', 'en': 'Villa', 'th': 'วิลล่า'},
    'townhouse': {'ru': 'Таунхаус', 'en': 'Townhouse', 'th': 'ทาวน์เฮาส์'},
    'land': {'ru': 'Участок', 'en': 'Land plot', 'th': 'ที่ดิน'},
    'investment': {'ru': 'Инвестиционная недвижимость', 'en': 'Investment property', 'th': 'อสังหาริมทรัพย์เพื่อการลงทุน'},
    'business': {'ru': 'Готовый бизнес', 'en': 'Business', 'th': 'ธุรกิจพร้อมดำเนินการ'},
}

PROPERTY_FALLBACK_LABELS = {
    'ru': {
        'title_template': '{property_type}{bedroom_suffix}{title_suffix} в {location}{deal_title_suffix} | Undersun Estate',
        'description_template': '{deal_type}: {property_type}{bedroom_suffix} в {location}. {facts}',
        'keywords_real_estate': 'недвижимость пхукет',
        'price': 'Цена {price}.',
        'price_on_request': 'Цена по запросу',
        'per_month': '/мес',
        'unit_sqm': 'м²',
        'discount_label': 'скидка',
        'area': 'Площадь {area} м².',
        'land_area': 'Участок {area} м².',
        'bathrooms': '{count} ванных.',
        'build_status': 'Статус: {status}.',
        'year_built': 'Год постройки: {year}.',
        'complex_name': 'Комплекс: {value}.',
        'beach_distance': 'До пляжа {value} мин.',
        'airport_distance': 'До аэропорта {value} мин.',
        'school_distance': 'До школы {value} мин.',
        'suitable_for': 'Подходит для: {value}.',
        'furnished': 'С мебелью.',
        'pool': 'С бассейном.',
        'parking': 'С парковкой.',
        'security': 'С охраной.',
        'gym': 'Со спортзалом.',
        'investment': 'Инвестиционный потенциал: {value}.',
        'section_heading': 'Почему стоит рассмотреть этот объект',
        'section_intro_template': '{property_type}{bedroom_suffix} в {location}.',
        'highlights_heading': 'Ключевые преимущества',
        'investment_heading': 'Инвестиционный потенциал',
        'suitable_for_heading': 'Подходит для',
        'faq_heading': 'Частые вопросы об объекте',
        'faq_price_question': 'Сколько стоит этот объект?',
        'faq_price_answer_sale': 'Стоимость этого объекта составляет {price}.',
        'faq_price_answer_rent': 'Стоимость аренды этого объекта составляет {price}.',
        'faq_price_answer_both': 'Объект доступен для продажи и аренды. Актуальная стоимость начинается от {price}.',
        'faq_price_on_request_answer': 'Стоимость объекта предоставляется по запросу. Мы подготовим актуальную цену и условия сделки после обращения.',
        'faq_location_question': 'Где находится объект?',
        'faq_location_answer': 'Объект расположен в {location_sentence}.',
        'faq_specs_question': 'Какие основные характеристики у объекта?',
        'faq_specs_answer': 'В объекте предусмотрены {specs}.',
        'faq_amenities_question': 'Какие удобства есть у объекта?',
        'faq_amenities_answer': 'В объекте предусмотрены {amenities}.',
        'faq_suitable_for_question': 'Для кого подойдет этот объект?',
        'faq_suitable_for_answer': 'Этот объект хорошо подойдет для {value}.',
        'faq_investment_question': 'Подходит ли объект для инвестиций?',
        'faq_investment_answer': '{value}',
        'faq_distances_question': 'Что находится рядом с объектом?',
        'faq_distances_answer': 'Рядом с объектом: {distances}.',
        'faq_freshness_question': 'Насколько актуальны цена и статус объекта?',
        'faq_freshness_answer': 'Цена и статус сверяются командой Undersun Estate; страница обновлена {updated_date}. Перед просмотром или резервированием мы подтвердим актуальные условия у владельца или застройщика.',
        'faq_viewing_question': 'Можно ли посмотреть объект перед решением?',
        'faq_viewing_answer': 'Да, просмотр можно согласовать через ответственного специалиста. Для части объектов возможен видео-показ или предварительная удаленная консультация по планировке, окружению и условиям сделки.',
        'faq_extra_costs_question': 'Какие расходы могут быть сверх цены?',
        'faq_extra_costs_answer_sale': 'Помимо цены объекта могут возникать регистрационные сборы, налоги, юридическая проверка, обслуживание комплекса и другие расходы по конкретной сделке. Мы заранее уточняем структуру платежей и рекомендуем проверять документы до внесения существенных сумм.',
        'faq_extra_costs_answer_rent': 'При аренде обычно нужно учитывать депозит, авансовую оплату, коммунальные платежи, интернет, уборку, обслуживание бассейна или сада и правила возврата депозита. Точные условия зависят от объекта и срока аренды.',
        'faq_extra_costs_answer_land': 'Для земельных участков особенно важны расходы на проверку титула, границ, доступа, инфраструктуры, разрешенного использования и регистрацию сделки. Финальные условия нужно подтверждать после проверки документов.',
        'faq_remote_question': 'Можно ли начать сделку удаленно?',
        'faq_remote_answer': 'Да, часть этапов можно начать удаленно: уточнить условия, получить дополнительные материалы, провести видео-показ и подготовить вопросы для проверки. Подписание и платежи зависят от формата сделки и документов, поэтому финальный порядок согласуется отдельно.',
        'bedroom_suffix': ' с {count} спальнями',
        'bedroom_keyword': '{count} спальни',
    },
    'en': {
        'title_template': '{property_type}{bedroom_suffix}{title_suffix} in {location}{deal_title_suffix} | Undersun Estate',
        'description_template': '{deal_type}: {property_type}{bedroom_suffix} in {location}. {facts}',
        'keywords_real_estate': 'phuket real estate',
        'price': 'Price {price}.',
        'price_on_request': 'Price on request',
        'per_month': '/month',
        'unit_sqm': 'm²',
        'discount_label': 'discount',
        'area': 'Total area {area} m².',
        'land_area': 'Land plot {area} m².',
        'bathrooms': '{count} bathrooms.',
        'build_status': 'Status: {status}.',
        'year_built': 'Built in {year}.',
        'complex_name': 'Project: {value}.',
        'beach_distance': '{value} min to the beach.',
        'airport_distance': '{value} min to the airport.',
        'school_distance': '{value} min to schools.',
        'suitable_for': 'Best suited for: {value}.',
        'furnished': 'Fully furnished.',
        'pool': 'Includes a pool.',
        'parking': 'Parking available.',
        'security': 'Security on site.',
        'gym': 'Gym access available.',
        'investment': 'Investment potential: {value}.',
        'section_heading': 'Why this property deserves attention',
        'section_intro_template': '{property_type}{bedroom_suffix} in {location}.',
        'highlights_heading': 'Key highlights',
        'investment_heading': 'Investment potential',
        'suitable_for_heading': 'Best suited for',
        'faq_heading': 'Frequently asked questions about property',
        'faq_price_question': 'What is the price of this property?',
        'faq_price_answer_sale': 'The asking price for this property is {price}.',
        'faq_price_answer_rent': 'The monthly rental price for this property is {price}.',
        'faq_price_answer_both': 'This property is available for sale and rent. Current pricing starts from {price}.',
        'faq_price_on_request_answer': 'The price is available on request. We can provide the current price and deal terms after inquiry.',
        'faq_location_question': 'Where is the property located?',
        'faq_location_answer': 'The property is located in {location_sentence}.',
        'faq_specs_question': 'What are the main specifications of the property?',
        'faq_specs_answer': 'The property includes {specs}.',
        'faq_amenities_question': 'What amenities are available?',
        'faq_amenities_answer': 'The property offers {amenities}.',
        'faq_suitable_for_question': 'Who is this property best suited for?',
        'faq_suitable_for_answer': 'This property is best suited for {value}.',
        'faq_investment_question': 'Is this property suitable for investment?',
        'faq_investment_answer': '{value}',
        'faq_distances_question': 'What is nearby?',
        'faq_distances_answer': 'Nearby highlights include {distances}.',
        'faq_freshness_question': 'How current are the price and status?',
        'faq_freshness_answer': 'The Undersun Estate team checks the price and status; this page was updated on {updated_date}. Before a viewing or reservation, we confirm the latest terms with the owner or developer.',
        'faq_viewing_question': 'Can I view the property before deciding?',
        'faq_viewing_answer': 'Yes. A viewing can be arranged through the responsible specialist. For some properties, a video viewing or remote pre-consultation on layout, surroundings, and deal terms is possible.',
        'faq_extra_costs_question': 'What costs may be added to the price?',
        'faq_extra_costs_answer_sale': 'Beyond the asking price, a transaction may include registration fees, taxes, legal checks, common area fees, and other deal-specific costs. We clarify the payment structure in advance and recommend document review before major payments.',
        'faq_extra_costs_answer_rent': 'For rentals, account for deposit, advance rent, utilities, internet, cleaning, pool or garden service, and deposit return terms. Exact terms depend on the property and rental period.',
        'faq_extra_costs_answer_land': 'For land, key costs and checks may include title review, boundaries, access, infrastructure, permitted use, and registration. Final terms should be confirmed after document review.',
        'faq_remote_question': 'Can I start the process remotely?',
        'faq_remote_answer': 'Yes. Several steps can start remotely: clarifying terms, receiving additional materials, arranging a video viewing, and preparing due-diligence questions. Signing and payments depend on the transaction format and documents.',
        'bedroom_suffix': ' with {count} bedrooms',
        'bedroom_keyword': '{count} bedroom',
    },
    'th': {
        'title_template': '{deal_type} {property_type}{bedroom_suffix}{title_suffix} ใน {location} | Undersun Estate',
        'description_template': '{deal_type} {property_type}{bedroom_suffix} ใน {location} {facts}',
        'keywords_real_estate': 'อสังหาริมทรัพย์ภูเก็ต',
        'price': 'ราคา {price}',
        'price_on_request': 'สอบถามราคา',
        'per_month': '/เดือน',
        'unit_sqm': 'ตร.ม.',
        'discount_label': 'ส่วนลด',
        'area': 'พื้นที่ใช้สอย {area} ตร.ม.',
        'land_area': 'ที่ดิน {area} ตร.ม.',
        'bathrooms': '{count} ห้องน้ำ',
        'build_status': 'สถานะ: {status}',
        'year_built': 'ปีที่สร้าง {year}',
        'complex_name': 'โครงการ: {value}',
        'beach_distance': 'ห่างชายหาด {value} นาที',
        'airport_distance': 'ห่างสนามบิน {value} นาที',
        'school_distance': 'ห่างโรงเรียน {value} นาที',
        'suitable_for': 'เหมาะสำหรับ: {value}',
        'furnished': 'พร้อมเฟอร์นิเจอร์',
        'pool': 'มีสระว่ายน้ำ',
        'parking': 'มีที่จอดรถ',
        'security': 'มีระบบรักษาความปลอดภัย',
        'gym': 'มีฟิตเนส',
        'investment': 'ศักยภาพการลงทุน: {value}',
        'section_heading': 'จุดเด่นของอสังหาริมทรัพย์นี้',
        'section_intro_template': '{property_type}{bedroom_suffix} ใน {location}',
        'highlights_heading': 'จุดเด่นสำคัญ',
        'investment_heading': 'ศักยภาพการลงทุน',
        'suitable_for_heading': 'เหมาะสำหรับ',
        'faq_heading': 'คำถามที่พบบ่อยเกี่ยวกับอสังหาริมทรัพย์นี้',
        'faq_price_question': 'อสังหาริมทรัพย์นี้ราคาเท่าไร?',
        'faq_price_answer_sale': 'ราคาขายของอสังหาริมทรัพย์นี้คือ {price}',
        'faq_price_answer_rent': 'ค่าเช่ารายเดือนของอสังหาริมทรัพย์นี้คือ {price}',
        'faq_price_answer_both': 'อสังหาริมทรัพย์นี้มีทั้งขายและให้เช่า โดยราคาเริ่มต้นที่ {price}',
        'faq_price_on_request_answer': 'สามารถสอบถามราคาและเงื่อนไขการซื้อขายล่าสุดได้โดยตรง',
        'faq_location_question': 'อสังหาริมทรัพย์นี้ตั้งอยู่ที่ไหน?',
        'faq_location_answer': 'อสังหาริมทรัพย์นี้ตั้งอยู่ใน {location_sentence}',
        'faq_specs_question': 'รายละเอียดหลักของอสังหาริมทรัพย์มีอะไรบ้าง?',
        'faq_specs_answer': 'อสังหาริมทรัพย์นี้มี {specs}',
        'faq_amenities_question': 'มีสิ่งอำนวยความสะดวกอะไรบ้าง?',
        'faq_amenities_answer': 'อสังหาริมทรัพย์นี้มี {amenities}',
        'faq_suitable_for_question': 'อสังหาริมทรัพย์นี้เหมาะกับใคร?',
        'faq_suitable_for_answer': 'อสังหาริมทรัพย์นี้เหมาะสำหรับ {value}',
        'faq_investment_question': 'อสังหาริมทรัพย์นี้เหมาะสำหรับการลงทุนหรือไม่?',
        'faq_investment_answer': '{value}',
        'faq_distances_question': 'มีสถานที่สำคัญอะไรอยู่ใกล้เคียง?',
        'faq_distances_answer': 'สถานที่สำคัญใกล้เคียง ได้แก่ {distances}',
        'faq_freshness_question': 'ราคาและสถานะอัปเดตล่าสุดหรือไม่?',
        'faq_freshness_answer': 'ทีม Undersun Estate ตรวจสอบราคาและสถานะ หน้านี้อัปเดตเมื่อ {updated_date} ก่อนนัดชมทรัพย์หรือจอง เราจะยืนยันเงื่อนไขล่าสุดกับเจ้าของหรือผู้พัฒนาโครงการอีกครั้ง',
        'faq_viewing_question': 'สามารถนัดชมทรัพย์ก่อนตัดสินใจได้หรือไม่?',
        'faq_viewing_answer': 'ได้ สามารถนัดชมผ่านผู้เชี่ยวชาญที่รับผิดชอบทรัพย์นี้ บางทรัพย์สามารถจัดวิดีโอทัวร์หรือให้คำปรึกษาเบื้องต้นเกี่ยวกับผัง ทำเล และเงื่อนไขดีลได้',
        'faq_extra_costs_question': 'มีค่าใช้จ่ายอื่นนอกเหนือจากราคาหรือไม่?',
        'faq_extra_costs_answer_sale': 'นอกจากราคาทรัพย์ อาจมีค่าธรรมเนียมจดทะเบียน ภาษี การตรวจเอกสาร ค่าส่วนกลาง และค่าใช้จ่ายเฉพาะดีล เราจะช่วยอธิบายโครงสร้างการชำระเงินล่วงหน้าและแนะนำให้ตรวจเอกสารก่อนชำระเงินก้อนใหญ่',
        'faq_extra_costs_answer_rent': 'สำหรับการเช่า ควรตรวจเงินมัดจำ ค่าเช่าล่วงหน้า ค่าน้ำไฟ อินเทอร์เน็ต ทำความสะอาด บริการสระหรือสวน และเงื่อนไขคืนมัดจำ เงื่อนไขจริงขึ้นอยู่กับทรัพย์และระยะเวลาเช่า',
        'faq_extra_costs_answer_land': 'สำหรับที่ดิน ควรตรวจเอกสารสิทธิ์ แนวเขต ทางเข้าออก โครงสร้างพื้นฐาน การใช้ประโยชน์ที่อนุญาต และค่าใช้จ่ายจดทะเบียน เงื่อนไขสุดท้ายควรยืนยันหลังตรวจเอกสาร',
        'faq_remote_question': 'สามารถเริ่มขั้นตอนจากระยะไกลได้หรือไม่?',
        'faq_remote_answer': 'ได้ หลายขั้นตอนเริ่มจากระยะไกลได้ เช่น ตรวจเงื่อนไข รับข้อมูลเพิ่มเติม วิดีโอทัวร์ และเตรียมคำถามสำหรับตรวจสอบเอกสาร ส่วนการลงนามและการชำระเงินขึ้นอยู่กับรูปแบบดีลและเอกสาร',
        'bedroom_suffix': ' {count} ห้องนอน',
        'bedroom_keyword': '{count} ห้องนอน',
    },
}

PROPERTY_IMAGE_FRAME_TYPES = [
    ('facade', _('Фасад / экстерьер')),
    ('living_room', _('Гостиная')),
    ('bedroom', _('Спальня')),
    ('bathroom', _('Ванная')),
    ('kitchen', _('Кухня')),
    ('pool', _('Бассейн')),
    ('terrace', _('Терраса / балкон')),
    ('view', _('Вид')),
    ('garden', _('Сад / участок')),
    ('floorplan', _('Планировка')),
    ('neighborhood', _('Локация / окружение')),
    ('interior', _('Интерьер')),
    ('exterior', _('Экстерьер')),
    ('other', _('Другое')),
]

PROPERTY_IMAGE_GENERIC_ALT_PREFIXES = (
    'image', 'images', 'photo', 'photos', 'picture', 'pictures',
    'изображение', 'изображения', 'фото', 'фотография', 'картинка',
)

PROPERTY_IMAGE_FILENAME_HINTS = {
    'facade': ('facade', 'façade', 'fac', 'cam ext', 'exterior', 'ext', 'front', 'outside', 'building'),
    'living_room': ('living room', 'living', 'livingroom', 'lounge', 'salon', 'hall', 'sitting'),
    'bedroom': ('bedroom', 'master bedroom', 'small bedroom', 'sleep', 'room'),
    'bathroom': ('bathroom', 'bath', 'master bathroom', 'wc', 'toilet'),
    'kitchen': ('kitchen', 'cook', 'pantry'),
    'pool': ('pool', 'swim', 'jacuzzi'),
    'terrace': ('terrace', 'balcony', 'patio', 'deck', 'veranda'),
    'view': ('view', 'sea', 'ocean', 'sunset', 'sunrise', 'mountain', 'panorama'),
    'garden': ('garden', 'yard', 'lawn', 'green', 'outdoor'),
    'floorplan': ('floor plan', 'floorplan', 'plan', 'layout', 'masterplan', 'blueprint'),
    'neighborhood': ('location', 'area', 'map', 'neighborhood', 'street', 'district'),
    'interior': ('cam int', 'interior', 'inside', 'indoor', 'room', 'house'),
    'exterior': ('exterior', 'outside', 'outdoor'),
}

PROPERTY_IMAGE_AUTO_ALT_TEMPLATES = {
    'ru': {
        'facade': 'Фасад {subject}{location_suffix}',
        'living_room': 'Гостиная {subject}{location_suffix}',
        'bedroom': 'Спальня {subject}{location_suffix}',
        'bathroom': 'Ванная {subject}{location_suffix}',
        'kitchen': 'Кухня {subject}{location_suffix}',
        'pool': 'Бассейн {subject}{location_suffix}',
        'terrace': 'Терраса {subject}{location_suffix}',
        'view': 'Вид с {subject}{location_suffix}',
        'garden': 'Сад {subject}{location_suffix}',
        'floorplan': 'Планировка {subject}{location_suffix}',
        'neighborhood': 'Локация {subject}{location_suffix}',
        'interior': 'Интерьер {subject}{location_suffix}',
        'exterior': 'Экстерьер {subject}{location_suffix}',
        'other': '{subject}{location_suffix}',
    },
    'en': {
        'facade': 'Exterior of {subject}{location_suffix}',
        'living_room': 'Living room of {subject}{location_suffix}',
        'bedroom': 'Bedroom of {subject}{location_suffix}',
        'bathroom': 'Bathroom of {subject}{location_suffix}',
        'kitchen': 'Kitchen of {subject}{location_suffix}',
        'pool': 'Pool area of {subject}{location_suffix}',
        'terrace': 'Terrace of {subject}{location_suffix}',
        'view': 'View from {subject}{location_suffix}',
        'garden': 'Garden of {subject}{location_suffix}',
        'floorplan': 'Floor plan of {subject}{location_suffix}',
        'neighborhood': 'Area around {subject}{location_suffix}',
        'interior': 'Interior of {subject}{location_suffix}',
        'exterior': 'Exterior of {subject}{location_suffix}',
        'other': '{subject}{location_suffix}',
    },
    'th': {
        'facade': 'ภายนอกของ{subject}{location_suffix}',
        'living_room': 'ห้องนั่งเล่นของ{subject}{location_suffix}',
        'bedroom': 'ห้องนอนของ{subject}{location_suffix}',
        'bathroom': 'ห้องน้ำของ{subject}{location_suffix}',
        'kitchen': 'ห้องครัวของ{subject}{location_suffix}',
        'pool': 'สระว่ายน้ำของ{subject}{location_suffix}',
        'terrace': 'ระเบียงของ{subject}{location_suffix}',
        'view': 'วิวจาก{subject}{location_suffix}',
        'garden': 'สวนของ{subject}{location_suffix}',
        'floorplan': 'ผังของ{subject}{location_suffix}',
        'neighborhood': 'บริเวณรอบ{subject}{location_suffix}',
        'interior': 'ภายในของ{subject}{location_suffix}',
        'exterior': 'ภายนอกของ{subject}{location_suffix}',
        'other': '{subject}{location_suffix}',
    },
}


class PropertyType(models.Model):
    """Типы недвижимости"""
    PROPERTY_TYPES = [
        ('villa', _('Вилла')),
        ('condo', _('Кондоминиум')),
        ('townhouse', _('Таунхаус')),
        ('land', _('Земельный участок')),
        ('investment', _('Инвестиции')),
        ('business', _('Готовый бизнес')),
    ]

    name = models.CharField(_('Тип'), max_length=20, choices=PROPERTY_TYPES, unique=True)
    name_display = models.CharField(_('Отображаемое название'), max_length=100)
    name_plural = models.CharField(_('Название во множественном числе'), max_length=100, blank=True)
    icon = models.CharField(_('Иконка'), max_length=50, blank=True)

    NAVIGATION_ORDER = ['condo', 'villa', 'townhouse', 'land']

    class Meta:
        verbose_name = _('Тип недвижимости')
        verbose_name_plural = _('Типы недвижимости')

    def __str__(self):
        return self.name_display

    @classmethod
    def ordered_for_navigation(cls):
        """Return property types ordered for navigation menus."""
        order_case = Case(
            *[
                When(name=property_type, then=Value(index))
                for index, property_type in enumerate(cls.NAVIGATION_ORDER)
            ],
            default=Value(len(cls.NAVIGATION_ORDER)),
            output_field=IntegerField(),
        )
        return cls.objects.annotate(_nav_order=order_case).order_by('_nav_order', 'name_display')


class Developer(models.Model):
    """Застройщики"""
    name = models.CharField(_('Название'), max_length=100)
    slug = models.SlugField(_('URL'), unique=True)
    description = models.TextField(_('Описание'), blank=True)
    logo = models.ImageField(_('Логотип'), upload_to='developers/', blank=True)
    website = models.URLField(_('Сайт'), blank=True)

    class Meta:
        verbose_name = _('Застройщик')
        verbose_name_plural = _('Застройщики')

    def __str__(self):
        return self.name


class Property(models.Model):
    """Основная модель недвижимости"""
    STATUS_CHOICES = [
        ('available', _('Доступно')),
        ('reserved', _('Забронировано')),
        ('sold', _('Продано')),
        ('rented', _('Сдано')),
    ]

    DEAL_TYPES = [
        ('sale', _('Продажа')),
        ('rent', _('Аренда')),
        ('both', _('Продажа/Аренда')),
    ]

    BUILD_STATUS_CHOICES = [
        ('completed', _('Готовый объект')),
        ('under_construction', _('Строящийся объект')),
    ]

    # Основная информация
    title = models.CharField(_('Название'), max_length=200)
    slug = models.SlugField(_('URL'), unique=True, max_length=150)
    property_type = models.ForeignKey(PropertyType, on_delete=models.CASCADE, verbose_name=_('Тип'))
    deal_type = models.CharField(_('Тип сделки'), max_length=10, choices=DEAL_TYPES, default='sale')
    status = models.CharField(_('Статус'), max_length=10, choices=STATUS_CHOICES, default='available')
    build_status = models.CharField(
        _('Стадия готовности'),
        max_length=20,
        choices=BUILD_STATUS_CHOICES,
        default='under_construction',
        help_text=_('Выберите "Готовый объект" или "Строящийся объект"'),
    )

    # Описание
    description = HTMLField(_('Описание'))
    short_description = models.CharField(_('Краткое описание'), max_length=300, blank=True)
    special_offer = models.CharField(_('Специальное предложение'), max_length=50, blank=True)

    # Локация
    district = models.ForeignKey(District, on_delete=models.CASCADE, verbose_name=_('Район'))
    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name=_('Локация'), blank=True, null=True)
    address = models.CharField(_('Адрес'), max_length=200, blank=True)

    # Координаты для карты (увеличена точность для сохранения данных из дампа)
    latitude = models.DecimalField(_('Широта'), max_digits=18, decimal_places=15, blank=True, null=True)
    longitude = models.DecimalField(_('Долгота'), max_digits=19, decimal_places=15, blank=True, null=True)

    # Характеристики
    bedrooms = models.PositiveIntegerField(_('Спальни'), blank=True, null=True)
    bathrooms = models.PositiveIntegerField(_('Ванные'), blank=True, null=True)
    area_total = models.DecimalField(_('Общая площадь, м²'), max_digits=8, decimal_places=2, blank=True, null=True)
    area_living = models.DecimalField(_('Жилая площадь, м²'), max_digits=8, decimal_places=2, blank=True, null=True)
    area_land = models.DecimalField(_('Площадь участка, м²'), max_digits=10, decimal_places=2, blank=True, null=True)
    floor = models.PositiveIntegerField(_('Этаж'), blank=True, null=True)
    floors_total = models.PositiveIntegerField(_('Всего этажей'), blank=True, null=True)

    # Цены
    price_sale_usd = models.DecimalField(_('Цена продажи, USD'), max_digits=12, decimal_places=2, blank=True, null=True)
    price_sale_thb = models.DecimalField(_('Цена продажи, THB'), max_digits=15, decimal_places=2, blank=True, null=True)
    price_sale_rub = models.DecimalField(_('Цена продажи, RUB'), max_digits=15, decimal_places=2, blank=True, null=True)
    price_rent_monthly = models.DecimalField(_('Аренда в месяц, USD'), max_digits=10, decimal_places=2, blank=True,
                                             null=True)
    price_rent_monthly_thb = models.DecimalField(_('Аренда в месяц, THB'), max_digits=12, decimal_places=2, blank=True, null=True)
    price_rent_monthly_rub = models.DecimalField(_('Аренда в месяц, RUB'), max_digits=12, decimal_places=2, blank=True, null=True)

    # Дополнительная информация
    developer = models.ForeignKey(Developer, on_delete=models.SET_NULL, blank=True, null=True,
                                  verbose_name=_('Застройщик'))
    year_built = models.PositiveIntegerField(_('Год постройки'), blank=True, null=True)
    furnished = models.BooleanField(_('С мебелью'), default=False)
    pool = models.BooleanField(_('Бассейн'), default=False)
    parking = models.BooleanField(_('Парковка'), default=False)
    security = models.BooleanField(_('Охрана'), default=False)
    gym = models.BooleanField(_('Спортзал'), default=False)
    is_for_investment = models.BooleanField(_('Для инвестиций'), default=False, 
                                           help_text=_('Объект рекомендован для инвестиций'))
    
    # Удобства (amenities) теперь через PropertyFeature и PropertyFeatureRelation

    # Поля для совместимости со старой БД
    legacy_id = models.CharField(_('ID объекта'), max_length=20, blank=True, null=True,
                                help_text=_('Идентификатор из старой Joomla системы (например: VS82)'))
    complex_name = models.CharField(_('Название комплекса'), max_length=100, blank=True,
                                   help_text=_('Название жилого комплекса или проекта'))
    pool_area = models.DecimalField(_('Площадь бассейна, м²'), max_digits=6, decimal_places=2, blank=True, null=True)
    
    # Финансовая информация
    original_price_thb = models.DecimalField(_('Первоначальная цена, THB'), max_digits=15, decimal_places=2, 
                                           blank=True, null=True,
                                           help_text=_('Цена до скидки'))
    is_urgent_sale = models.BooleanField(_('Срочная продажа'), default=False)
    urgency_note = models.CharField(_('Примечание о срочности'), max_length=200, blank=True,
                                   help_text=_('Дополнительная информация о срочной продаже'))
    
    # Архитектурные особенности
    architectural_style = models.CharField(_('Архитектурный стиль'), max_length=100, blank=True)
    material_type = models.CharField(_('Материалы'), max_length=200, blank=True,
                                    help_text=_('Основные строительные материалы'))
    
    # Инвестиционная информация
    investment_potential = models.TextField(_('Инвестиционный потенциал'), blank=True,
                                          help_text=_('Описание инвестиционной привлекательности'))
    suitable_for = models.CharField(_('Подходит для'), max_length=200, blank=True,
                                   help_text=_('Назначение использования (отпуск, постоянное проживание и т.д.)'))
    
    # Расстояния до ключевых объектов (в минутах)
    distance_to_beach = models.PositiveIntegerField(_('До пляжа, мин'), blank=True, null=True)
    distance_to_airport = models.PositiveIntegerField(_('До аэропорта, мин'), blank=True, null=True)
    distance_to_school = models.PositiveIntegerField(_('До школы, мин'), blank=True, null=True)

    # Типы кроватей (из дампа Joomla field_id=60-62)
    double_beds = models.PositiveIntegerField(_('Двуспальные кровати'), blank=True, null=True,
                                            help_text=_('Количество двуспальных кроватей'))
    single_beds = models.PositiveIntegerField(_('Односпальные кровати'), blank=True, null=True,
                                            help_text=_('Количество односпальных кроватей'))
    sofa_beds = models.PositiveIntegerField(_('Диван-кровати'), blank=True, null=True,
                                          help_text=_('Количество диван-кроватей'))
    
    # Контактное лицо (связь с командой)
    contact_person = models.ForeignKey('core.Team', on_delete=models.SET_NULL, null=True, blank=True,
                                      default=1, verbose_name=_('Контактное лицо'),
                                      help_text=_('Сотрудник компании, ответственный за данный объект (по умолчанию: Bogdan)'))
    
    # Связь с агентом (из дампа Joomla field_id=26) - оставляем для совместимости
    agent = models.ForeignKey('Agent', on_delete=models.SET_NULL, null=True, blank=True,
                             verbose_name=_('Агент (legacy)'),
                             help_text=_('Ответственный агент (устаревшее поле)'))
    
    # Дополнительные изображения
    floorplan = models.ImageField(_('План этажа'), upload_to='properties/floorplans/', blank=True,
                                 help_text=_('План планировки этажей'))
    intro_image = models.ImageField(_('Интро изображение'), upload_to='properties/intro/', blank=True,
                                   help_text=_('Дополнительное изображение для анонса'))

    # Мета-информация
    views_count = models.PositiveIntegerField(_('Просмотры'), default=0)
    is_featured = models.BooleanField(_('Рекомендуемое'), default=False)
    featured_priority = models.PositiveIntegerField(
        _('Приоритет в рекомендуемых'),
        default=0,
        help_text=_('Чем выше значение, тем раньше объект отображается в блоках рекомендаций')
    )
    is_active = models.BooleanField(_('Активно'), default=True)

    # SEO поля (опциональные - для переопределения автогенерации)
    custom_title_ru = models.CharField(_('Заголовок (RU)'), max_length=200, blank=True,
                                     help_text=_('Оставьте пустым для автоматической генерации'))
    custom_description_ru = models.TextField(_('Описание (RU)'), max_length=300, blank=True,
                                           help_text=_('Оставьте пустым для автоматической генерации'))
    custom_keywords_ru = models.TextField(_('Ключевые слова (RU)'), blank=True,
                                        help_text=_('Оставьте пустым для автоматической генерации'))
    
    custom_title_en = models.CharField(_('Заголовок (EN)'), max_length=200, blank=True,
                                     help_text=_('Оставьте пустым для автоматической генерации'))
    custom_description_en = models.TextField(_('Описание (EN)'), max_length=300, blank=True,
                                           help_text=_('Оставьте пустым для автоматической генерации'))
    custom_keywords_en = models.TextField(_('Ключевые слова (EN)'), blank=True,
                                        help_text=_('Оставьте пустым для автоматической генерации'))
    
    custom_title_th = models.CharField(_('Заголовок (TH)'), max_length=200, blank=True,
                                     help_text=_('Оставьте пустым для автоматической генерации'))
    custom_description_th = models.TextField(_('Описание (TH)'), max_length=300, blank=True,
                                           help_text=_('Оставьте пустым для автоматической генерации'))
    custom_keywords_th = models.TextField(_('Ключевые слова (TH)'), blank=True,
                                        help_text=_('Оставьте пустым для автоматической генерации'))

    # Временные метки
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)

    class Meta:
        verbose_name = _('Недвижимость')
        verbose_name_plural = _('Недвижимость')
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('properties:property_detail', kwargs={'slug': self.slug})

    @property
    def main_image(self):
        """Получить главное изображение"""
        return self.images.filter(is_main=True).first()

    def get_main_image_url(self):
        """Вернуть URL главного изображения или первого доступного."""
        candidate_images = [self.main_image, self.images.first()]
        for image in candidate_images:
            if not image:
                continue
            if image.original_url:
                return image.original_url
        return ''

    def get_main_image_absolute_url(self, request):
        """Вернуть абсолютный URL главного изображения для OG метатегов."""
        relative_url = self.get_main_image_url()
        if not relative_url:
            return ''
        try:
            return request.build_absolute_uri(relative_url)
        except Exception:
            return relative_url

    @property
    def price_display(self):
        """Отформатированная цена для отображения"""
        language_code = (get_language() or 'ru')[:2]
        labels = PROPERTY_FALLBACK_LABELS.get(language_code, PROPERTY_FALLBACK_LABELS['ru'])
        if self.deal_type == 'sale' and self.price_sale_thb:
            price_str = f"฿{self.price_sale_thb:,.0f}"
            if self.is_urgent_sale and self.original_price_thb and self.price_sale_thb:
                # Показываем скидку если это срочная продажа
                discount_percent = ((self.original_price_thb - self.price_sale_thb) / self.original_price_thb) * 100
                if discount_percent > 0:
                    price_str += f" ({labels['discount_label']} {discount_percent:.0f}%)"
            return price_str
        elif self.deal_type == 'rent' and self.price_rent_monthly_thb:
            return f"฿{self.price_rent_monthly_thb:,.0f}{labels['per_month']}"
        return labels['price_on_request']
    
    def get_price_per_sqm_in_currency(self, currency_code, deal_type='sale'):
        """Получить цену за квадратный метр в указанной валюте"""
        from decimal import Decimal
        
        if not self.area_total or self.area_total <= 0 or deal_type != 'sale':
            return None
            
        price = self.get_price_in_currency(currency_code, deal_type)
        if not price:
            return None
            
        # Приводим к Decimal для корректного деления
        price_decimal = Decimal(str(price))
        area_decimal = Decimal(str(self.area_total))
        
        return float(price_decimal / area_decimal)
    
    def get_formatted_price_per_sqm(self, currency_code='THB', deal_type='sale'):
        """Получить отформатированную цену за квадратный метр"""
        price_per_sqm = self.get_price_per_sqm_in_currency(currency_code, deal_type)
        if not price_per_sqm:
            return None
            
        symbols = {'USD': '$', 'THB': '฿', 'RUB': '₽'}
        symbol = symbols.get(currency_code, currency_code)
        
        # Форматируем с пробелами
        formatted_price = f"{int(price_per_sqm):,}".replace(',', ' ')
        language_code = (get_language() or 'ru')[:2]
        labels = PROPERTY_FALLBACK_LABELS.get(language_code, PROPERTY_FALLBACK_LABELS['ru'])
        return f"{symbol}{formatted_price}/{labels['unit_sqm']}"

    def get_price_in_currency(self, currency_code, deal_type='sale'):
        """Получить цену в указанной валюте"""
        from apps.currency.models import Currency, ExchangeRate
        from decimal import Decimal
        
        # Получаем базовую цену (теперь храним в THB)
        if deal_type == 'sale':
            base_price = self.price_sale_thb
        else:
            base_price = self.price_rent_monthly_thb
            
        if not base_price:
            return None
            
        # Если нужная валюта THB, возвращаем как есть
        if currency_code == 'THB':
            return base_price
            
        # Если есть уже сохраненная цена в нужной валюте, возвращаем ее
        if currency_code == 'USD':
            if deal_type == 'sale' and self.price_sale_usd:
                return self.price_sale_usd
            elif deal_type == 'rent' and self.price_rent_monthly:
                return self.price_rent_monthly
        elif currency_code == 'RUB':
            if deal_type == 'sale' and self.price_sale_rub:
                return self.price_sale_rub
            elif deal_type == 'rent' and self.price_rent_monthly_rub:
                return self.price_rent_monthly_rub
        
        # Конвертируем через курс валют
        try:
            thb_currency = Currency.objects.get(code='THB')
            target_currency = Currency.objects.get(code=currency_code)
            converted_amount = ExchangeRate.convert_amount(base_price, thb_currency, target_currency)
            return converted_amount
        except Currency.DoesNotExist:
            return None
    
    def get_formatted_price(self, currency_code='THB', deal_type='sale'):
        """Получить отформатированную цену в указанной валюте"""
        from apps.currency.models import Currency
        
        price = self.get_price_in_currency(currency_code, deal_type)
        if not price:
            language_code = (get_language() or 'ru')[:2]
            labels = PROPERTY_FALLBACK_LABELS.get(language_code, PROPERTY_FALLBACK_LABELS['ru'])
            return labels['price_on_request']
            
        try:
            currency = Currency.objects.get(code=currency_code)
            symbol = currency.symbol
            decimal_places = currency.decimal_places
            
            if decimal_places == 0:
                price_str = f"{symbol}{price:,.0f}"
            else:
                price_str = f"{symbol}{price:,.{decimal_places}f}"
                
            if deal_type == 'rent':
                language_code = (get_language() or 'ru')[:2]
                labels = PROPERTY_FALLBACK_LABELS.get(language_code, PROPERTY_FALLBACK_LABELS['ru'])
                price_str += labels['per_month']
                
            return price_str
        except Currency.DoesNotExist:
            return f"{price:,.0f} {currency_code}"
    
    @property
    def total_area(self):
        """Alias для совместимости с SEOTemplate"""
        return self.area_total
    
    def has_custom_seo(self, language_code='ru'):
        """Проверить, есть ли кастомные SEO поля для языка"""
        title_field = f'custom_title_{language_code}'
        return bool(getattr(self, title_field, ''))
    
    def get_custom_seo(self, language_code='ru'):
        """Получить кастомные SEO данные"""
        return {
            'title': getattr(self, f'custom_title_{language_code}', ''),
            'description': getattr(self, f'custom_description_{language_code}', ''),
            'keywords': getattr(self, f'custom_keywords_{language_code}', ''),
        }
    
    def get_seo_template(self):
        """Найти подходящий SEO шаблон для этого объекта"""
        from apps.core.models import SEOTemplate
        
        # Ищем точное совпадение по типу недвижимости и типу сделки
        template = SEOTemplate.objects.filter(
            template_type='property_detail',
            property_type=self.property_type.name,
            deal_type=self.deal_type,
            is_active=True
        ).order_by('priority').first()
        
        # Если не найден, ищем по типу недвижимости без учета типа сделки
        if not template:
            template = SEOTemplate.objects.filter(
                template_type='property_detail',
                property_type=self.property_type.name,
                deal_type='',
                is_active=True
            ).order_by('priority').first()
        
        # Если не найден, ищем общий шаблон
        if not template:
            template = SEOTemplate.objects.filter(
                template_type='property_detail',
                property_type='',
                is_active=True
            ).order_by('priority').first()
        
        return template

    @staticmethod
    def _normalize_whitespace(value):
        if not isinstance(value, str):
            return value
        return ' '.join(value.split())

    def _get_seo_texts(self, language_code='ru'):
        return PROPERTY_FALLBACK_LABELS.get(language_code, PROPERTY_FALLBACK_LABELS['ru'])

    def _get_translated_property_field(self, field_name, language_code='ru', fallback=''):
        translated_field = field_name if language_code == 'ru' else f'{field_name}_{language_code}'
        value = getattr(self, translated_field, None)
        if value in (None, ''):
            value = getattr(self, field_name, None)
        if value in (None, ''):
            value = fallback
        return self._normalize_whitespace(value)

    def _get_translated_location_name(self, language_code='ru'):
        if not self.location:
            return ''

        field_name = 'name' if language_code == 'ru' else f'name_{language_code}'
        value = getattr(self.location, field_name, None) or self.location.name
        return self._normalize_whitespace(value)

    def _get_primary_location_label(self, language_code='ru'):
        location_name = self._get_translated_location_name(language_code)
        district_name = self._get_translated_district_name(language_code)
        return location_name or district_name

    def _get_seo_property_type_name(self, language_code='ru'):
        if not self.property_type:
            defaults = {'ru': 'Недвижимость', 'en': 'Property', 'th': 'อสังหาริมทรัพย์'}
            return defaults.get(language_code, defaults['ru'])

        mapped_label = PROPERTY_TYPE_SEO_LABELS.get(self.property_type.name, {}).get(language_code)
        if mapped_label:
            return mapped_label

        return self._normalize_whitespace(self._get_translated_type_name(language_code))

    def _get_bedroom_suffix(self, language_code='ru'):
        if not self.bedrooms:
            return ''

        count = self.bedrooms
        if language_code == 'en':
            noun = 'bedroom' if count == 1 else 'bedrooms'
            return f' with {count} {noun}'
        if language_code == 'th':
            return f' {count} ห้องนอน'
        if count == 1:
            return f' с {count} спальней'
        return f' с {count} спальнями'

    @staticmethod
    def _format_compact_thb(value):
        if value in (None, ''):
            return ''

        amount = float(value)
        if amount >= 1_000_000:
            compact = f'{amount / 1_000_000:.1f}'.rstrip('0').rstrip('.')
            return f'฿{compact}M'

        return f'฿{amount:,.0f}'

    def _get_title_suffix(self, language_code='ru'):
        parts = []
        property_type_name = self.property_type.name if self.property_type else ''
        area_value = self.area_land if property_type_name == 'land' and self.area_land else self.area_total or self.area_land

        if area_value:
            area_units = {
                'ru': 'м²',
                'en': 'm²',
                'th': 'ตร.ม.',
            }
            area_unit = area_units.get(language_code, area_units['ru'])
            parts.append(f'{self._format_number(area_value)} {area_unit}')

        if self.deal_type == 'rent':
            price_value = self.price_rent_monthly_thb
        else:
            price_value = self.price_sale_thb or self.price_rent_monthly_thb

        price_label = self._format_compact_thb(price_value)
        if price_label:
            parts.append(price_label)

        if not parts and self.legacy_id:
            parts.append(f'ID {self.legacy_id}')

        if not parts:
            return ''

        if language_code == 'th':
            return f" {' '.join(parts[:3])}"

        return f", {', '.join(parts[:3])}"

    def _get_deal_title_suffix(self, language_code='ru'):
        if self.deal_type == 'sale':
            return ''

        deal_type_name = self._get_translated_deal_type(language_code)
        if not deal_type_name or language_code == 'th':
            return ''

        return f' | {deal_type_name}'

    def _get_keyword_bedroom_label(self, language_code='ru'):
        if not self.bedrooms:
            return ''
        count = self.bedrooms
        if language_code == 'en':
            noun = 'bedroom' if count == 1 else 'bedrooms'
            return f'{count} {noun}'
        if language_code == 'th':
            return f'{count} ห้องนอน'
        if count == 1:
            return f'{count} спальня'
        return f'{count} спальни'

    @staticmethod
    def _format_number(value):
        if value in (None, ''):
            return ''
        numeric_value = float(value)
        if numeric_value.is_integer():
            return str(int(numeric_value))
        return f'{numeric_value:.1f}'.rstrip('0').rstrip('.')

    def _get_localized_price_display(self, language_code='ru'):
        texts = self._get_seo_texts(language_code)

        if self.deal_type == 'sale' and self.price_sale_thb:
            return f"฿{self.price_sale_thb:,.0f}".replace(',', ',')

        if self.deal_type == 'rent' and self.price_rent_monthly_thb:
            base_value = f"฿{self.price_rent_monthly_thb:,.0f}".replace(',', ',')
            return f"{base_value}{texts['per_month']}"

        if self.deal_type == 'both':
            if self.price_sale_thb:
                return f"฿{self.price_sale_thb:,.0f}".replace(',', ',')
            if self.price_rent_monthly_thb:
                base_value = f"฿{self.price_rent_monthly_thb:,.0f}".replace(',', ',')
                return f"{base_value}{texts['per_month']}"

        return texts['price_on_request']

    def _get_translated_build_status(self, language_code='ru'):
        with override(language_code):
            return self._normalize_whitespace(self.get_build_status_display())

    def _get_translated_bool_labels(self, language_code='ru'):
        texts = self._get_seo_texts(language_code)
        highlights = []
        if self.furnished:
            highlights.append(texts['furnished'])
        if self.pool:
            highlights.append(texts['pool'])
        if self.parking:
            highlights.append(texts['parking'])
        if self.security:
            highlights.append(texts['security'])
        if self.gym:
            highlights.append(texts['gym'])
        return highlights

    def _get_translated_amenity_names(self, language_code='ru'):
        labels = {
            'ru': {
                'furnished': 'мебель',
                'pool': 'бассейн',
                'parking': 'парковка',
                'security': 'охрана',
                'gym': 'спортзал',
            },
            'en': {
                'furnished': 'furniture',
                'pool': 'a pool',
                'parking': 'parking',
                'security': 'security',
                'gym': 'a gym',
            },
            'th': {
                'furnished': 'เฟอร์นิเจอร์',
                'pool': 'สระว่ายน้ำ',
                'parking': 'ที่จอดรถ',
                'security': 'ระบบรักษาความปลอดภัย',
                'gym': 'ฟิตเนส',
            },
        }
        translated = labels.get(language_code, labels['ru'])
        amenities = []
        if self.furnished:
            amenities.append(translated['furnished'])
        if self.pool:
            amenities.append(translated['pool'])
        if self.parking:
            amenities.append(translated['parking'])
        if self.security:
            amenities.append(translated['security'])
        if self.gym:
            amenities.append(translated['gym'])
        return amenities

    def _join_localized_list(self, values, language_code='ru'):
        items = [self._normalize_whitespace(value).rstrip('.').strip() for value in values if value]
        if not items:
            return ''
        if len(items) == 1:
            return items[0]

        conjunctions = {
            'ru': 'и',
            'en': 'and',
            'th': 'และ',
        }
        conjunction = conjunctions.get(language_code, conjunctions['ru'])
        if language_code == 'th':
            return ' '.join([', '.join(items[:-1]), conjunction, items[-1]])
        return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"

    def _get_room_phrase(self, room_type, count, language_code='ru'):
        if not count:
            return ''

        if room_type == 'bedrooms':
            if language_code == 'en':
                noun = 'bedroom' if count == 1 else 'bedrooms'
                return f'{count} {noun}'
            if language_code == 'th':
                return f'{count} ห้องนอน'
            if count == 1:
                return '1 спальню'
            if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
                return f'{count} спальни'
            return f'{count} спален'

        if language_code == 'en':
            noun = 'bathroom' if count == 1 else 'bathrooms'
            return f'{count} {noun}'
        if language_code == 'th':
            return f'{count} ห้องน้ำ'
        if count == 1:
            return '1 ванную комнату'
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            return f'{count} ванные комнаты'
        return f'{count} ванных комнат'

    def _get_location_sentence(self, language_code='ru'):
        district_name = self._get_translated_district_name(language_code)
        location_name = self._get_translated_location_name(language_code)

        if language_code == 'ru':
            if location_name and location_name != district_name:
                return f'{location_name}, {district_name} на Пхукете'
            return f'{district_name} на Пхукете'
        if language_code == 'en':
            if location_name and location_name != district_name:
                return f'{location_name}, {district_name}, Phuket'
            return f'{district_name}, Phuket'
        if location_name and location_name != district_name:
            return f'{location_name}, {district_name}, ภูเก็ต'
        return f'{district_name}, ภูเก็ต'

    def _get_specs_faq_answer(self, language_code='ru'):
        spec_parts = []
        if self.bedrooms:
            spec_parts.append(self._get_room_phrase('bedrooms', self.bedrooms, language_code))
        if self.bathrooms:
            spec_parts.append(self._get_room_phrase('bathrooms', self.bathrooms, language_code))
        if self.area_total:
            area_value = self._format_number(self.area_total)
            if language_code == 'ru':
                spec_parts.append(f'общую площадь {area_value} м²')
            elif language_code == 'en':
                spec_parts.append(f'a total area of {area_value} m²')
            else:
                spec_parts.append(f'พื้นที่ใช้สอย {area_value} ตร.ม.')
        if self.build_status:
            build_status = self._get_translated_build_status(language_code)
            if language_code == 'ru':
                spec_parts.append(f'статус {build_status.lower()}')
            elif language_code == 'en':
                spec_parts.append(f'status {build_status.lower()}')
            else:
                spec_parts.append(f'สถานะ {build_status}')
        if self.year_built:
            if language_code == 'ru':
                spec_parts.append(f'год постройки {self.year_built}')
            elif language_code == 'en':
                spec_parts.append(f'year built {self.year_built}')
            else:
                spec_parts.append(f'ปีที่สร้าง {self.year_built}')

        if not spec_parts:
            return ''

        texts = self._get_seo_texts(language_code)
        return texts['faq_specs_answer'].format(
            specs=self._join_localized_list(spec_parts, language_code)
        )

    def _get_distances_faq_answer(self, language_code='ru'):
        distance_parts = []
        texts = self._get_seo_texts(language_code)
        if self.distance_to_beach:
            distance_parts.append(texts['beach_distance'].format(value=self.distance_to_beach).rstrip('.'))
        if self.distance_to_airport:
            distance_parts.append(texts['airport_distance'].format(value=self.distance_to_airport).rstrip('.'))
        if self.distance_to_school:
            distance_parts.append(texts['school_distance'].format(value=self.distance_to_school).rstrip('.'))

        if not distance_parts:
            return ''

        return texts['faq_distances_answer'].format(
            distances=self._join_localized_list(distance_parts, language_code)
        )

    @staticmethod
    def _to_plain_text(value):
        if not value:
            return ''
        return ' '.join(strip_tags(str(value)).split())

    def _build_seo_fact_sentences(self, language_code='ru'):
        texts = self._get_seo_texts(language_code)
        facts = []
        price_display = self._get_localized_price_display(language_code)

        if self.area_total:
            facts.append(texts['area'].format(area=self._format_number(self.area_total)))
        if self.area_land:
            facts.append(texts['land_area'].format(area=self._format_number(self.area_land)))
        if self.bathrooms:
            facts.append(texts['bathrooms'].format(count=self.bathrooms))
        if self.build_status:
            facts.append(texts['build_status'].format(status=self._get_translated_build_status(language_code)))
        if self.year_built:
            facts.append(texts['year_built'].format(year=self.year_built))
        if self.complex_name:
            facts.append(texts['complex_name'].format(
                value=self._get_translated_property_field('complex_name', language_code)
            ))
        if self.distance_to_beach:
            facts.append(texts['beach_distance'].format(value=self.distance_to_beach))
        if self.distance_to_airport:
            facts.append(texts['airport_distance'].format(value=self.distance_to_airport))
        if self.distance_to_school:
            facts.append(texts['school_distance'].format(value=self.distance_to_school))
        facts.extend(self._get_translated_bool_labels(language_code))

        if price_display != texts['price_on_request']:
            facts.append(texts['price'].format(price=price_display))

        suitable_for = self._get_translated_property_field('suitable_for', language_code)
        if suitable_for:
            facts.append(texts['suitable_for'].format(value=suitable_for))

        investment_potential = self._get_translated_property_field('investment_potential', language_code)
        short_description = self._get_translated_property_field('short_description', language_code)
        if investment_potential:
            facts.append(texts['investment'].format(value=investment_potential))
        elif short_description:
            facts.append(short_description)

        return [self._normalize_whitespace(fact) for fact in facts if fact]

    def generate_auto_seo(self, language_code='ru'):
        """Автоматическая генерация SEO данных как fallback"""
        texts = self._get_seo_texts(language_code)
        type_name = self._get_seo_property_type_name(language_code)
        location_name = self._get_primary_location_label(language_code)
        district_name = self._get_translated_district_name(language_code)
        deal_type_name = self._get_translated_deal_type(language_code)
        bedroom_suffix = self._get_bedroom_suffix(language_code)

        title = texts['title_template'].format(
            property_type=type_name,
            bedroom_suffix=bedroom_suffix,
            title_suffix=self._get_title_suffix(language_code),
            location=location_name,
            deal_type=deal_type_name,
            deal_title_suffix=self._get_deal_title_suffix(language_code),
        )

        facts = ' '.join(self._build_seo_fact_sentences(language_code))
        description = texts['description_template'].format(
            deal_type=deal_type_name,
            property_type=type_name.lower() if language_code != 'th' else type_name,
            bedroom_suffix=bedroom_suffix,
            location=location_name,
            facts=facts,
        ).strip()

        keywords = [
            type_name,
            self._get_translated_type_name(language_code),
            location_name,
            district_name,
            texts['keywords_real_estate'],
            deal_type_name,
            self._get_keyword_bedroom_label(language_code),
        ]

        return {
            'title': title,
            'description': description,
            'keywords': ', '.join(self._normalize_whitespace(value) for value in keywords if value),
        }
    
    def _get_translated_type_name(self, language_code='ru'):
        """Получить переведённое название типа недвижимости"""
        if not self.property_type:
            defaults = {
                'ru': 'недвижимость',
                'en': 'real estate',
                'th': 'อสังหาริมทรัพย์'
            }
            return defaults.get(language_code, defaults['ru'])
        
        # Используем переведённое поле из modeltranslation
        field_name = f'name_display_{language_code}' if language_code != 'ru' else 'name_display'
        translated_name = getattr(self.property_type, field_name, None)
        
        # Fallback на русский язык
        if not translated_name:
            translated_name = self.property_type.name_display
            
        return translated_name or 'недвижимость'
    
    def _get_translated_district_name(self, language_code='ru'):
        """Получить переведённое название района"""
        if not self.district:
            defaults = {
                'ru': 'Пхукет',
                'en': 'Phuket',
                'th': 'ภูเก็ต'
            }
            return defaults.get(language_code, defaults['ru'])
        
        # Используем переведённое поле из modeltranslation
        field_name = f'name_{language_code}' if language_code != 'ru' else 'name'
        translated_name = getattr(self.district, field_name, None)
        
        # Fallback на русский язык
        if not translated_name:
            translated_name = self.district.name
            
        return translated_name or 'Пхукет'
    
    def _get_translated_deal_type(self, language_code='ru'):
        """Получить переведённое название типа сделки"""
        deal_type_translations = {
            'sale': {
                'ru': 'Продажа',
                'en': 'Sale',
                'th': 'ขาย'
            },
            'rent': {
                'ru': 'Аренда',
                'en': 'Rent',
                'th': 'เช่า'
            },
            'both': {
                'ru': 'Продажа/Аренда',
                'en': 'Sale/Rent',
                'th': 'ขาย/เช่า'
            }
        }
        
        deal_translations = deal_type_translations.get(self.deal_type, {})
        return deal_translations.get(language_code, deal_translations.get('ru', self.deal_type))

    def _get_active_language_code(self):
        language_code = (get_language() or 'ru').split('-')[0]
        return language_code if language_code in {'ru', 'en', 'th'} else 'ru'

    @staticmethod
    def _strip_display_title_suffix(value):
        value = Property._normalize_whitespace(value or '')
        for separator in (' | ', ' — ', ' – '):
            if separator in value:
                return Property._normalize_whitespace(value.split(separator, 1)[0])
        return value

    def get_localized_display_title(self, language_code='ru'):
        language_code = (language_code or 'ru')[:2]
        translated_field = 'title' if language_code == 'ru' else f'title_{language_code}'
        explicit_title = self._normalize_whitespace(getattr(self, translated_field, '') or '')
        if explicit_title:
            return explicit_title

        if language_code != 'ru':
            generated_title = self.generate_auto_seo(language_code).get('title', '')
            generated_heading = self._strip_display_title_suffix(generated_title)
            if generated_heading:
                return generated_heading

        return self._normalize_whitespace(self.title)

    def get_detail_seo_section(self, language_code='ru'):
        texts = self._get_seo_texts(language_code)
        property_type_name = self._get_seo_property_type_name(language_code)
        location_name = self._get_primary_location_label(language_code)
        bedroom_suffix = self._get_bedroom_suffix(language_code)
        suitable_for = self._get_translated_property_field('suitable_for', language_code)
        investment_potential = self._get_translated_property_field('investment_potential', language_code)
        short_description = self._get_translated_property_field('short_description', language_code)
        highlights = self._build_seo_fact_sentences(language_code)

        intro = texts['section_intro_template'].format(
            property_type=property_type_name,
            bedroom_suffix=bedroom_suffix,
            location=location_name,
        )

        return {
            'has_content': any([intro, highlights, suitable_for, investment_potential, short_description]),
            'heading': texts['section_heading'],
            'intro': intro,
            'highlights_heading': texts['highlights_heading'],
            'highlights': highlights[:8],
            'suitable_for_heading': texts['suitable_for_heading'],
            'suitable_for': suitable_for,
            'investment_heading': texts['investment_heading'],
            'investment_potential': investment_potential,
            'supporting_text': short_description if short_description and short_description != investment_potential else '',
        }

    def get_detail_faq_items(self, language_code='ru'):
        texts = self._get_seo_texts(language_code)
        faq_items = []

        price_display = self._get_localized_price_display(language_code)
        if price_display == texts['price_on_request']:
            price_answer = texts['faq_price_on_request_answer']
        elif self.deal_type == 'rent':
            price_answer = texts['faq_price_answer_rent'].format(price=price_display)
        elif self.deal_type == 'both':
            price_answer = texts['faq_price_answer_both'].format(price=price_display)
        else:
            price_answer = texts['faq_price_answer_sale'].format(price=price_display)
        faq_items.append({
            'question': texts['faq_price_question'],
            'answer': self._to_plain_text(price_answer),
        })

        updated_date = self.updated_at.strftime('%d.%m.%Y') if self.updated_at else ''
        faq_items.append({
            'question': texts['faq_freshness_question'],
            'answer': self._to_plain_text(texts['faq_freshness_answer'].format(updated_date=updated_date)),
        })

        location_answer = texts['faq_location_answer'].format(
            location_sentence=self._get_location_sentence(language_code)
        )
        faq_items.append({
            'question': texts['faq_location_question'],
            'answer': self._to_plain_text(location_answer),
        })

        specs_answer = self._get_specs_faq_answer(language_code)
        if specs_answer:
            faq_items.append({
                'question': texts['faq_specs_question'],
                'answer': self._to_plain_text(specs_answer),
            })

        faq_items.append({
            'question': texts['faq_viewing_question'],
            'answer': self._to_plain_text(texts['faq_viewing_answer']),
        })

        extra_costs_key = 'faq_extra_costs_answer_land' if self.property_type and self.property_type.name == 'land' else (
            'faq_extra_costs_answer_rent' if self.deal_type == 'rent' else 'faq_extra_costs_answer_sale'
        )
        faq_items.append({
            'question': texts['faq_extra_costs_question'],
            'answer': self._to_plain_text(texts[extra_costs_key]),
        })

        faq_items.append({
            'question': texts['faq_remote_question'],
            'answer': self._to_plain_text(texts['faq_remote_answer']),
        })

        amenities = self._get_translated_amenity_names(language_code)
        if amenities:
            faq_items.append({
                'question': texts['faq_amenities_question'],
                'answer': self._to_plain_text(
                    texts['faq_amenities_answer'].format(
                        amenities=self._join_localized_list(amenities, language_code)
                    )
                ),
            })

        suitable_for = self._get_translated_property_field('suitable_for', language_code)
        if suitable_for:
            faq_items.append({
                'question': texts['faq_suitable_for_question'],
                'answer': self._to_plain_text(texts['faq_suitable_for_answer'].format(value=suitable_for)),
            })

        investment_potential = self._get_translated_property_field('investment_potential', language_code)
        if investment_potential:
            faq_items.append({
                'question': texts['faq_investment_question'],
                'answer': self._to_plain_text(texts['faq_investment_answer'].format(value=investment_potential)),
            })

        distances_answer = self._get_distances_faq_answer(language_code)
        if distances_answer:
            faq_items.append({
                'question': texts['faq_distances_question'],
                'answer': self._to_plain_text(distances_answer),
            })

        return {
            'has_items': bool(faq_items),
            'heading': texts['faq_heading'],
            'entries': faq_items[:8],
        }

    def get_display_title(self):
        return self.get_localized_display_title(self._get_active_language_code())

    def get_display_location_label(self):
        language_code = self._get_active_language_code()
        district_label = self._get_translated_district_name(language_code)
        location_label = self._get_translated_location_name(language_code)
        if location_label and location_label != district_label:
            return f'{district_label}, {location_label}'
        return district_label

    def get_display_district_label(self):
        return self._get_translated_district_name(self._get_active_language_code())

    def get_card_image_alt(self):
        language_code = self._get_active_language_code()
        return self.get_seo_image_alt(
            image=self.main_image,
            language_code=language_code,
            position=1,
        )

    def get_seo_image_alt_base(self, language_code='ru'):
        property_type_name = self._get_seo_property_type_name(language_code)
        location_name = self._get_primary_location_label(language_code)
        bedroom_suffix = self._get_bedroom_suffix(language_code)

        templates = {
            'ru': '{property_type}{bedroom_suffix} в {location}',
            'en': '{property_type}{bedroom_suffix} in {location}',
            'th': '{property_type}{bedroom_suffix} ใน {location}',
        }

        template = templates.get(language_code, templates['ru'])
        return self._normalize_whitespace(template.format(
            property_type=property_type_name,
            bedroom_suffix=bedroom_suffix,
            location=location_name,
        ))

    def get_seo_image_alt(self, image=None, language_code='ru', position=None):
        base_alt = self.get_seo_image_alt_base(language_code)

        if image:
            localized_getter = getattr(image, 'get_localized_alt_text', None)
            if callable(localized_getter):
                candidate = localized_getter(language_code)
            else:
                candidate = getattr(image, 'alt_text', '') or getattr(image, 'title', '')
            candidate = self._normalize_whitespace(candidate)
            generic_prefixes = (
                'image', 'images', 'photo', 'photos', 'picture',
                'изображение', 'изображения', 'фото', 'картинка',
            )
            normalized_candidate = candidate.strip().lower()
            is_generic = any(
                normalized_candidate == prefix or normalized_candidate.startswith(f'{prefix} ')
                for prefix in generic_prefixes
            )
            if candidate and not is_generic:
                return candidate

        if position is None:
            return base_alt

        suffixes = {
            'ru': f'фото {position}',
            'en': f'photo {position}',
            'th': f'ภาพที่ {position}',
        }
        return f"{base_alt} {suffixes.get(language_code, suffixes['ru'])}"
    
    def get_seo_data(self, language_code='ru'):
        """Получить финальные SEO данные с учетом приоритетов"""
        # 1. Проверяем кастомные SEO поля
        if self.has_custom_seo(language_code):
            return self._with_truncated_description(self.get_custom_seo(language_code))
        
        # 2. Ищем подходящий шаблон
        template = self.get_seo_template()
        if template:
            return self._with_truncated_description(
                template.generate_seo_for_property(self, language_code)
            )
        
        # 3. Fallback - автогенерация
        return self._with_truncated_description(self.generate_auto_seo(language_code))

    def _with_truncated_description(self, seo_data):
        """Убеждаемся, что meta description не превышает лимит."""
        seo_data = seo_data or {}
        for field_name in ('title', 'description', 'keywords'):
            value = seo_data.get(field_name)
            if isinstance(value, str):
                seo_data[field_name] = ' '.join(value.split())
        description = seo_data.get('description')
        if description:
            seo_data['description'] = truncate_meta(description)
        return seo_data


class Agent(models.Model):
    """Агенты по недвижимости"""
    name = models.CharField(_('Имя'), max_length=100)
    email = models.EmailField(_('Email'), blank=True)
    phone = models.CharField(_('Телефон'), max_length=20, blank=True)
    whatsapp = models.CharField(_('WhatsApp'), max_length=20, blank=True)
    telegram = models.CharField(_('Telegram'), max_length=50, blank=True)
    bio = models.TextField(_('Биография'), blank=True)
    photo = models.ImageField(_('Фото'), upload_to='agents/', blank=True)
    is_active = models.BooleanField(_('Активен'), default=True)
    
    # Из старой системы Joomla (field_id=26)
    legacy_id = models.CharField(_('ID из Joomla'), max_length=20, blank=True, unique=True,
                                help_text=_('Идентификатор из старой Joomla системы'))
    
    # Временные метки
    created_at = models.DateTimeField(_('Создано'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлено'), auto_now=True)
    
    class Meta:
        verbose_name = _('Агент')
        verbose_name_plural = _('Агенты')
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PropertyImage(models.Model):
    """Изображения недвижимости"""
    IMAGE_TYPES = [
        ('main', _('Основная галерея')),
        ('intro', _('Интро изображение')),
        ('floorplan', _('План этажа')),
        ('teaser', _('Тизер')),
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('Изображение'), upload_to='properties/')
    title = models.CharField(_('Название'), max_length=100, blank=True)
    is_main = models.BooleanField(_('Главное изображение'), default=False)
    order = models.PositiveIntegerField(_('Порядок'), default=0)
    
    # Дополнительные поля для разных типов изображений (из дампа Joomla)
    image_type = models.CharField(_('Тип изображения'), max_length=20, choices=IMAGE_TYPES, 
                                 default='main', help_text=_('Тип изображения для категоризации'))
    frame_type = models.CharField(
        _('Тип кадра'),
        max_length=20,
        choices=PROPERTY_IMAGE_FRAME_TYPES,
        default='other',
        help_text=_('Автоматически определяемый тип кадра для генерации alt-текста'),
    )
    alt_text = models.CharField(_('Alt текст'), max_length=200, blank=True,
                               help_text=_('Альтернативный текст для SEO и доступности'))
    alt_text_ru = models.CharField(_('Alt текст (RU)'), max_length=200, blank=True, default='')
    alt_text_en = models.CharField(_('Alt текст (EN)'), max_length=200, blank=True, default='')
    alt_text_th = models.CharField(_('Alt текст (TH)'), max_length=200, blank=True, default='')
    alt_generated_by = models.CharField(
        _('Источник alt'),
        max_length=20,
        blank=True,
        default='',
        help_text=_('heuristic, vision или manual'),
    )
    alt_confidence = models.DecimalField(
        _('Уверенность'),
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_('Уверенность классификации от 0 до 1'),
    )
    alt_generated_at = models.DateTimeField(_('Сгенерировано'), blank=True, null=True)

    # Автоматическое создание thumbnails
    thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(300, 200)],
        format='WEBP',
        options={'quality': 75, 'method': 6}
    )

    medium = ImageSpecField(
        source='image',
        processors=[ResizeToFit(800, 600)],
        format='WEBP',
        options={'quality': 78, 'method': 6}
    )

    class Meta:
        verbose_name = _('Изображение')
        verbose_name_plural = _('Изображения')
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.property.title} - {self.title or 'Image'}"

    @staticmethod
    def _normalize_alt_source(value):
        if not isinstance(value, str):
            return ''
        return ' '.join(value.split()).strip()

    @classmethod
    def _looks_generic_alt(cls, value):
        normalized = cls._normalize_alt_source(value).lower()
        if not normalized:
            return True
        return any(
            normalized == prefix or normalized.startswith(f'{prefix} ')
            for prefix in PROPERTY_IMAGE_GENERIC_ALT_PREFIXES
        )

    @classmethod
    def _normalize_frame_source(cls, value):
        if not isinstance(value, str):
            return ''
        normalized = value.replace('\\', '/').split('/')[-1]
        normalized = normalized.rsplit('.', 1)[0]
        normalized = normalized.replace('-', ' ').replace('_', ' ')
        normalized = re.sub(r'[^0-9a-zA-Z\u0400-\u04FF\u0E00-\u0E7F]+', ' ', normalized)
        return ' '.join(normalized.lower().split())

    def _collect_frame_source_text(self):
        parts = [
            self.title,
            self.image.name if self.image else '',
            self.image_type,
        ]
        if not self.alt_generated_by:
            parts.extend([
                self.alt_text,
                self.alt_text_ru,
                self.alt_text_en,
                self.alt_text_th,
            ])
        normalized_parts = [
            self._normalize_frame_source(part)
            for part in parts
            if part
        ]
        return ' '.join(part for part in normalized_parts if part)

    def infer_frame_type(self):
        source_text = self._collect_frame_source_text()
        if not source_text:
            return 'other', 0.0

        if self.image_type == 'floorplan':
            return 'floorplan', 0.99

        best_frame_type = 'other'
        best_score = 0

        for frame_type, hints in PROPERTY_IMAGE_FILENAME_HINTS.items():
            score = sum(1 for hint in hints if hint in source_text)
            if score > best_score:
                best_frame_type = frame_type
                best_score = score

        if best_score == 0:
            return 'other', 0.0

        confidence = min(0.95, 0.55 + (best_score * 0.12))
        return best_frame_type, round(confidence, 2)

    def get_effective_frame_type(self):
        if self.frame_type and self.frame_type != 'other':
            return self.frame_type
        inferred_frame_type, _ = self.infer_frame_type()
        return inferred_frame_type

    def _get_subject_phrase(self, language_code='ru'):
        try:
            property_obj = self.property
        except Exception:
            property_obj = None
        if not property_obj:
            defaults = {'ru': 'объекта', 'en': 'property', 'th': 'อสังหาริมทรัพย์'}
            return defaults.get(language_code, defaults['ru'])

        type_slug = property_obj.property_type.name if property_obj.property_type else ''
        subject_map = {
            'ru': {
                'villa': 'виллы',
                'condo': 'кондоминиума',
                'townhouse': 'таунхауса',
                'land': 'участка',
                'investment': 'инвестиционного объекта',
                'business': 'готового бизнеса',
            },
            'en': {
                'villa': 'villa',
                'condo': 'condo',
                'townhouse': 'townhouse',
                'land': 'land plot',
                'investment': 'investment property',
                'business': 'business property',
            },
            'th': {
                'villa': 'วิลล่า',
                'condo': 'คอนโดมิเนียม',
                'townhouse': 'ทาวน์เฮาส์',
                'land': 'ที่ดิน',
                'investment': 'อสังหาริมทรัพย์เพื่อการลงทุน',
                'business': 'ธุรกิจ',
            },
        }
        return subject_map.get(language_code, subject_map['ru']).get(type_slug, {
            'ru': 'объекта',
            'en': 'property',
            'th': 'อสังหาริมทรัพย์',
        }.get(language_code, 'объекта'))

    def get_auto_alt_text(self, language_code='ru', frame_type=None):
        language_code = (language_code or 'ru')[:2]
        frame_type = (frame_type or self.get_effective_frame_type() or 'other')[:20]
        templates = PROPERTY_IMAGE_AUTO_ALT_TEMPLATES.get(language_code, PROPERTY_IMAGE_AUTO_ALT_TEMPLATES['ru'])
        template = templates.get(frame_type, templates['other'])

        subject = self._get_subject_phrase(language_code)
        location_suffix = ''
        try:
            property_obj = self.property
        except Exception:
            property_obj = None
        if property_obj:
            location_label = property_obj._get_primary_location_label(language_code)
            if location_label:
                if language_code == 'en':
                    location_suffix = f' in {location_label}'
                elif language_code == 'th':
                    location_suffix = f' ใน{location_label}'
                else:
                    location_suffix = f' в {location_label}'

        alt_text = template.format(subject=subject, location_suffix=location_suffix)
        return self._normalize_alt_source(alt_text)

    def get_localized_alt_text(self, language_code='ru'):
        language_code = (language_code or 'ru')[:2]
        candidates = []
        if language_code == 'ru':
            candidates.extend([
                getattr(self, 'alt_text_ru', ''),
                self.alt_text,
            ])
        else:
            candidates.append(getattr(self, f'alt_text_{language_code}', ''))
            if self.alt_text and not self._contains_cyrillic(self.alt_text):
                candidates.append(self.alt_text)

        for candidate in candidates:
            candidate = self._normalize_alt_source(candidate)
            if candidate and not self._looks_generic_alt(candidate):
                return candidate

        return self.get_auto_alt_text(language_code)

    @staticmethod
    def _contains_cyrillic(value):
        if not isinstance(value, str):
            return False
        return bool(re.search(r'[\u0400-\u04FF]', value))

    def mark_alt_generated(self, generated_by='heuristic', confidence=None):
        self.alt_generated_by = generated_by or ''
        self.alt_confidence = confidence
        try:
            from django.utils import timezone
            self.alt_generated_at = timezone.now()
        except Exception:
            self.alt_generated_at = None

    def populate_localized_alt_texts(self, generated_by='heuristic', confidence=None, overwrite=False):
        for language_code in ('ru', 'en', 'th'):
            field_name = 'alt_text' if language_code == 'ru' else f'alt_text_{language_code}'
            current_value = self._normalize_alt_source(getattr(self, field_name, ''))
            if current_value and not overwrite and not self._looks_generic_alt(current_value):
                continue
            setattr(self, field_name, self.get_auto_alt_text(language_code))
        self.mark_alt_generated(generated_by=generated_by, confidence=confidence)

    def save(self, *args, **kwargs):
        # Автоматически делать первое изображение главным
        if self.is_main:
            PropertyImage.objects.filter(property=self.property).exclude(id=self.id).update(is_main=False)
        elif not PropertyImage.objects.filter(property=self.property, is_main=True).exists():
            self.is_main = True

        if not self.frame_type or self.frame_type == 'other':
            inferred_frame_type, confidence = self.infer_frame_type()
            self.frame_type = inferred_frame_type
            if inferred_frame_type != 'other' and not self.alt_generated_by:
                self.mark_alt_generated(generated_by='heuristic', confidence=confidence)

        self._convert_image_to_webp()
        super().save(*args, **kwargs)

    @staticmethod
    def _safe_url(file_field):
        """Вернуть URL файла, если он существует."""
        try:
            return file_field.url
        except Exception:
            return ''

    @builtins.property
    def original_url(self):
        """Базовый URL оригинального изображения."""
        return self._safe_url(self.image)

    @builtins.property
    def medium_url(self):
        """URL изображения среднего размера с fallback на оригинал."""
        if not self.original_url:
            return ''

        try:
            medium_file = self.medium
            generate = getattr(medium_file, 'generate', None)
            if callable(generate):
                generate()
            storage = getattr(medium_file, 'storage', None)
            name = getattr(medium_file, 'name', None)
            if storage and name and storage.exists(name):
                return storage.url(name)
        except Exception:
            pass

        return self.original_url

    def _convert_image_to_webp(self):
        """Преобразовать исходный файл изображения в WebP при сохранении."""
        image_field = getattr(self, 'image', None)
        if not image_field:
            return

        filename = image_field.name or ''
        if filename.lower().endswith('.webp'):
            return

        try:
            image_field.open()
            pil_image = Image.open(image_field)
            pil_image.load()
        except Exception:
            return

        buffer = None
        try:
            if pil_image.mode not in ('RGB', 'RGBA'):
                # Сохраняем прозрачность, если она была, иначе конвертируем в RGB
                target_mode = 'RGBA' if pil_image.mode in ('LA', 'P') else 'RGB'
                pil_image = pil_image.convert(target_mode)

            buffer = BytesIO()
            pil_image.save(buffer, format='WEBP', quality=85, method=6)
            buffer.seek(0)

            base_name, _ = os.path.splitext(filename)
            webp_name = f"{base_name}.webp"
            self.image.save(webp_name, ContentFile(buffer.read()), save=False)
        finally:
            if buffer is not None:
                buffer.close()
            pil_image.close()
            close_file = getattr(image_field, 'close', None)
            if callable(close_file):
                close_file()

    @builtins.property
    def thumbnail_url(self):
        """URL превью с fallback на оригинал."""
        if not self.original_url:
            return ''

        try:
            thumb_file = self.thumbnail
            generate = getattr(thumb_file, 'generate', None)
            if callable(generate):
                generate()
            storage = getattr(thumb_file, 'storage', None)
            name = getattr(thumb_file, 'name', None)
            if storage and name and storage.exists(name):
                return storage.url(name)
        except Exception:
            pass

        return self.original_url


class PropertyFeature(models.Model):
    """Дополнительные характеристики"""
    name = models.CharField(_('Название'), max_length=100)
    icon = models.CharField(_('Иконка'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Характеристика')
        verbose_name_plural = _('Характеристики')

    def __str__(self):
        return self.name


class PropertyFeatureRelation(models.Model):
    """Связь недвижимости с характеристиками"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='features')
    feature = models.ForeignKey(PropertyFeature, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['property', 'feature']
