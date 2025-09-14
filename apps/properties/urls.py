from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.PropertyListView.as_view(), name='property_list'),
    path('sale/', views.PropertySaleView.as_view(), name='property_sale'),
    path('rent/', views.PropertyRentView.as_view(), name='property_rent'),
    path('favorites/', views.favorites_view, name='property_favorites'),
    path('ajax/list/', views.property_list_ajax, name='property_list_ajax'),
    path('ajax/map/', views.map_properties_json, name='map_properties_json'),
    path('ajax/locations/', views.get_locations_for_district, name='get_locations_for_district'),
    path('ajax/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('ajax/favorites/', views.get_favorite_properties, name='get_favorite_properties'),
    path('ajax/inquiry/<int:property_id>/', views.property_inquiry, name='property_inquiry'),
    path('ajax/search-count/', views.ajax_search_count, name='ajax_search_count'),
    path('ajax/bulk-upload-images/', views.bulk_upload_images, name='bulk_upload_images'),
    path('ajax/update-image-order/', views.update_image_order, name='update_image_order'),
    path('<slug:slug>/', views.PropertyDetailView.as_view(), name='property_detail'),
    path('type/<str:type_name>/', views.PropertyByTypeView.as_view(), name='property_by_type'),
]