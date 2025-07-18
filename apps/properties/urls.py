from django.urls import path
from . import views

urlpatterns = [
    path('', views.PropertyListView.as_view(), name='property_list'),
    path('sale/', views.PropertySaleView.as_view(), name='property_sale'),
    path('rent/', views.PropertyRentView.as_view(), name='property_rent'),
    path('ajax/list/', views.property_list_ajax, name='property_list_ajax'),
    path('ajax/locations/', views.get_locations_for_district, name='get_locations_for_district'),
    path('ajax/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('ajax/inquiry/<int:property_id>/', views.property_inquiry, name='property_inquiry'),
    path('<slug:slug>/', views.PropertyDetailView.as_view(), name='property_detail'),
    path('type/<str:type_name>/', views.PropertyByTypeView.as_view(), name='property_by_type'),
]