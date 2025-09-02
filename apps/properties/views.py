from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, Http404
# login_required decorator removed
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.urls import reverse
from .models import Property, PropertyType
from apps.locations.models import District
from apps.users.models import PropertyInquiry


class PropertyListView(ListView):
    model = Property
    template_name = 'properties/list.html'
    context_object_name = 'properties'
    paginate_by = 12

    def get_queryset(self):
        queryset = Property.objects.filter(
            is_active=True,
            status='available'
        ).select_related('district', 'property_type').prefetch_related('images')
        
        # Применяем фильтры из GET параметров
        queryset = self.apply_filters(queryset)
        
        # Сортировка
        sort_by = self.request.GET.get('sort', '-created_at')
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
        
        # Цена в USD (учитываем и продажу и аренду)
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            try:
                min_val = int(min_price)
                queryset = queryset.filter(
                    Q(price_sale_usd__gte=min_val) | Q(price_rent_monthly__gte=min_val)
                )
            except ValueError:
                pass
        if max_price:
            try:
                max_val = int(max_price)
                queryset = queryset.filter(
                    Q(price_sale_usd__lte=max_val) | Q(price_rent_monthly__lte=max_val)
                )
            except ValueError:
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
        context['property_types'] = PropertyType.objects.all()
        context['districts'] = District.objects.all()
        
        # Добавляем локации для выбранного района
        selected_district = self.request.GET.get('district')
        if selected_district:
            context['locations'] = Location.objects.filter(district__slug=selected_district)
        else:
            context['locations'] = Location.objects.all()
        
        # Добавляем популярные amenities (с количеством > 10 объектов)
        context['amenities'] = PropertyFeature.objects.annotate(
            property_count=Count('propertyfeaturerelation')
        ).filter(property_count__gte=10).order_by('-property_count')[:12]
        
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
        
        return context


class PropertySaleView(PropertyListView):
    template_name = 'properties/list.html'

    def get_queryset(self):
        return super().get_queryset().filter(deal_type__in=['sale', 'both'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deal_type'] = 'sale'
        return context


class PropertyRentView(PropertyListView):
    template_name = 'properties/list.html'

    def get_queryset(self):
        return super().get_queryset().filter(deal_type__in=['rent', 'both'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deal_type'] = 'rent'
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
                redirect_url = reverse('property_sale')
            elif property_obj.deal_type == 'rent':
                redirect_url = reverse('property_rent')
            
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
            redirect_url = reverse('property_list')
            if property_obj.property_type:
                redirect_url = f"{redirect_url}?property_type={property_obj.property_type.name}"
        
        # 3. Финальный fallback: главная страница недвижимости
        if not redirect_url:
            redirect_url = reverse('property_list')
        
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

@require_POST
def get_favorite_properties(request):
    """AJAX endpoint для получения данных избранных объектов"""
    property_ids = request.POST.getlist('property_ids[]')
    
    if not property_ids:
        return JsonResponse({'success': False, 'message': 'Не переданы ID объектов'})
    
    try:
        # Преобразуем в integers
        ids = [int(id) for id in property_ids if id.isdigit()]
        
        # Получаем объекты
        properties = Property.objects.filter(id__in=ids).select_related(
            'district', 'property_type'
        ).prefetch_related('images')
        
        # Формируем данные для ответа
        properties_data = []
        for prop in properties:
            main_image_url = ''
            if prop.main_image:
                main_image_url = prop.main_image.thumbnail.url
            
            # Формируем цену для отображения
            price_display = 'Цена по запросу'
            if prop.deal_type == 'rent' and prop.price_rent_monthly:
                price_display = f'${prop.price_rent_monthly:,.0f}/мес'
            elif prop.deal_type in ['sale', 'both'] and prop.price_sale_usd:
                price_display = f'${prop.price_sale_usd:,.0f}'
            
            properties_data.append({
                'id': prop.id,
                'title': prop.title,
                'slug': prop.slug,
                'district_name': prop.district.name if prop.district else '',
                'property_type_name': prop.property_type.name if prop.property_type else '',
                'deal_type': prop.deal_type,
                'price_display': price_display,
                'main_image_url': main_image_url,
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
    email = request.POST.get('email')
    phone = request.POST.get('phone', '')
    message = request.POST.get('message')

    if not all([name, email, message]):
        return JsonResponse({
            'success': False,
            'message': 'Заполните все обязательные поля'
        })

    property_obj = get_object_or_404(Property, id=property_id)

    inquiry = PropertyInquiry.objects.create(
        property=property_obj,
        name=name,
        email=email,
        phone=phone,
        message=message
    )

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
            'main_image_url': main_image.image.url if main_image else '',
            'main_image_thumbnail_url': main_image.thumbnail.url if main_image and hasattr(main_image, 'thumbnail') else '',
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
        queryset = apply_search_filters(queryset, filters)
        
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


def apply_search_filters(queryset, filters):
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
        queryset = queryset.filter(location__slug=location)
    
    # Ценовые фильтры (в USD по умолчанию)
    min_price = filters.get('min_price')
    max_price = filters.get('max_price')
    
    if min_price:
        try:
            min_val = int(min_price)
            queryset = queryset.filter(
                Q(price_sale_usd__gte=min_val) | Q(price_rent_monthly__gte=min_val)
            )
        except ValueError:
            pass
            
    if max_price:
        try:
            max_val = int(max_price)
            queryset = queryset.filter(
                Q(price_sale_usd__lte=max_val) | Q(price_rent_monthly__lte=max_val)
            )
        except ValueError:
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