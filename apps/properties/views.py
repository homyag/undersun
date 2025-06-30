from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import Property, PropertyType
from apps.locations.models import District
from apps.users.models import PropertyFavorite, PropertyInquiry


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
        
        # Удобства/особенности
        if self.request.GET.get('pool'):
            queryset = queryset.filter(features__feature__name_en__icontains='pool')
        if self.request.GET.get('parking'):
            queryset = queryset.filter(features__feature__name_en__icontains='parking')
        if self.request.GET.get('sea_view'):
            queryset = queryset.filter(features__feature__name_en__icontains='sea view')
        
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
        context = super().get_context_data(**kwargs)
        context['property_types'] = PropertyType.objects.all()
        context['districts'] = District.objects.all()
        
        # Передаем текущие фильтры в контекст для сохранения состояния формы
        context['current_filters'] = {
            'deal_type': self.request.GET.get('deal_type', ''),
            'property_type': self.request.GET.getlist('property_type'),
            'district': self.request.GET.get('district', ''),
            'min_price': self.request.GET.get('min_price', ''),
            'max_price': self.request.GET.get('max_price', ''),
            'bedrooms': self.request.GET.getlist('bedrooms'),
            'pool': self.request.GET.get('pool', ''),
            'parking': self.request.GET.get('parking', ''),
            'sea_view': self.request.GET.get('sea_view', ''),
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
        self.property_type = get_object_or_404(PropertyType, name=self.kwargs['type_name'])
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
        return Property.objects.filter(
            is_active=True
        ).select_related('district', 'location', 'property_type', 'developer').prefetch_related(
            'images', 'features__feature'
        )

    def get_object(self):
        obj = super().get_object()
        # Увеличиваем счетчик просмотров
        obj.views_count += 1
        obj.save(update_fields=['views_count'])
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Похожие объекты
        similar_properties = Property.objects.filter(
            property_type=self.object.property_type,
            district=self.object.district,
            is_active=True,
            status='available'
        ).exclude(id=self.object.id).select_related('district', 'property_type').prefetch_related('images')[:4]

        context['similar_properties'] = similar_properties

        # Проверяем, добавлен ли объект в избранное
        if self.request.user.is_authenticated:
            context['is_favorite'] = PropertyFavorite.objects.filter(
                user=self.request.user,
                property=self.object
            ).exists()

        return context


@require_POST
@login_required
def toggle_favorite(request):
    """AJAX добавление/удаление из избранного"""
    property_id = request.POST.get('property_id')
    property_obj = get_object_or_404(Property, id=property_id)

    favorite, created = PropertyFavorite.objects.get_or_create(
        user=request.user,
        property=property_obj
    )

    if not created:
        favorite.delete()
        is_favorite = False
    else:
        is_favorite = True

    return JsonResponse({
        'success': True,
        'is_favorite': is_favorite,
        'message': 'Добавлено в избранное' if is_favorite else 'Удалено из избранного'
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