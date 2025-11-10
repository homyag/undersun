from decimal import Decimal, InvalidOperation

from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, Http404, HttpResponseRedirect
# login_required decorator removed
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.translation import gettext, ngettext

from apps.currency.services import CurrencyService
from apps.core.utils import build_query_string
from .models import Property, PropertyType
from apps.locations.models import District
from apps.users.models import PropertyInquiry


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
    )

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
            'price_sale_usd', '-price_sale_usd', 
            'price_sale_thb', '-price_sale_thb',
            'price_rent_monthly', '-price_rent_monthly',
            'area_total', '-area_total',
            'created_at', '-created_at'
        ]
        ordering = []

        if not sort_param and not self.has_active_filters():
            ordering.append('-is_featured')

        if sort_by in allowed_sorts:
            ordering.append(sort_by)
        else:
            ordering.append('-created_at')

        queryset = queryset.order_by(*ordering)

        return queryset

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
        from apps.locations.models import Location
        from .models import PropertyFeature
        
        context = super().get_context_data(**kwargs)
        priority_case = Case(
            *[
                When(name=property_type, then=Value(index))
                for index, property_type in enumerate(self.PROPERTY_TYPE_PRIORITY)
            ],
            default=Value(len(self.PROPERTY_TYPE_PRIORITY)),
            output_field=IntegerField(),
        )

        context['property_types'] = (
            PropertyType.objects
            .annotate(_type_priority=priority_case)
            .order_by('_type_priority', 'name_display')
        )
        context['districts'] = District.objects.all()
        
        # Добавляем локации для выбранного района
        selected_district = self.request.GET.get('district')
        if selected_district:
            context['locations'] = Location.objects.filter(district__slug=selected_district)
        else:
            context['locations'] = Location.objects.all()
        
        # Добавляем популярные amenities (с количеством > 0 объектов)
        context['amenities'] = PropertyFeature.objects.annotate(
            property_count=Count('propertyfeaturerelation')
        ).filter(property_count__gte=1).order_by('-property_count')[:12]
        
        # Передаем текущие фильтры в контекст для сохранения состояния формы
        context['current_filters'] = {
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
        }

        context['pagination_query_string'] = self.get_pagination_query_string()

        context['results_count_i18n'] = {
            'zero': gettext('Объекты не найдены'),
            'one': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 1),
            'few': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 2),
            'many': ngettext('Найден %(count)s объект', 'Найдено %(count)s объектов', 5),
        }

        return context

    def get_pagination_query_string(self):
        allowed_keys = list(self.PAGINATION_ALLOWED_PARAMS)
        return build_query_string(self.request.GET, allowed_keys)


class PropertySaleView(DealTypeRedirectMixin, PropertyListView):
    template_name = 'properties/list.html'
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
                ordering.append('-is_featured')
            ordering.extend(['_type_priority', '-created_at'])

            queryset = queryset.annotate(_type_priority=priority_case).order_by(*ordering)

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deal_type'] = 'sale'
        if not self.request.GET.get('deal_type'):
            context['current_filters']['deal_type'] = 'sale'
        return context


class PropertyRentView(DealTypeRedirectMixin, PropertyListView):
    template_name = 'properties/list.html'
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
        return context


class PropertyByTypeView(PropertyListView):
    template_name = 'properties/list.html'

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
        try:
            self.object = self.get_object()
        except Http404:
            raise
        
        # Если объект найден, но неактивен - делаем редирект
        if not self.object.is_active:
            return self.handle_inactive_property(self.object)
        
        # Иначе продолжаем как обычно
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Похожие объекты с приоритетом по локации
        similar_properties = self.get_similar_properties()
        context['similar_properties'] = similar_properties

        # Favorite functionality removed
        context['is_favorite'] = False

        main_image_url = self.object.get_main_image_absolute_url(self.request)
        if main_image_url:
            context['og_image_url'] = main_image_url

        return context
    
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
def property_inquiry(request, property_id):
    """AJAX отправка запроса по недвижимости"""
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
        'price_sale_usd', '-price_sale_usd', 
        'price_sale_thb', '-price_sale_thb',
        'price_rent_monthly', '-price_rent_monthly',
        'area_total', '-area_total',
        'created_at', '-created_at'
    ]
    if sort_by in allowed_sorts:
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
    
    district_slug = request.GET.get('district')
    
    if district_slug:
        locations = Location.objects.filter(district__slug=district_slug).values('slug', 'name')
    else:
        locations = Location.objects.all().values('slug', 'name')
    
    return JsonResponse({
        'success': True,
        'locations': list(locations)
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
        ).select_related('district', 'location', 'property_type').prefetch_related('images')
        
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
            
            properties_data.append({
                'id': prop.id,
                'title': prop.title,
                'slug': prop.slug,
                'lat': float(prop.latitude),
                'lng': float(prop.longitude),
                'property_type': prop.property_type.name if prop.property_type else '',
                'deal_type': prop.deal_type,
                'price': price_display,
                'location': prop.location.name if prop.location else (prop.district.name if prop.district else ''),
                'url': property_url,
                'image_url': image_url
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
    
    # Тип недвижимости
    property_type = filters.get('type')
    if property_type:
        queryset = queryset.filter(property_type__name=property_type)
    
    # Район  
    district = filters.get('district')
    if district:
        queryset = queryset.filter(district__slug=district)
    
    # Локация
    location = filters.get('location')  
    if location:
        queryset = queryset.filter(location__id=location)
    
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
    bedrooms = filters.get('bedrooms')
    if bedrooms:
        try:
            if bedrooms == '4+':
                queryset = queryset.filter(bedrooms__gte=4)
            else:
                queryset = queryset.filter(bedrooms=int(bedrooms))
        except ValueError:
            pass
    
    # Тип сделки
    deal_type = filters.get('deal_type')
    if deal_type and deal_type in ['sale', 'rent']:
        queryset = queryset.filter(deal_type__in=[deal_type, 'both'])
    
    # Удобства/особенности
    amenities = filters.getlist('amenities') if hasattr(filters, 'getlist') else [filters.get('amenities')] if filters.get('amenities') else []
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
