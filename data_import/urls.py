from django.urls import path
from . import views

app_name = 'data_import'

urlpatterns = [
    # Основные страницы
    path('', views.import_dashboard, name='dashboard'),
    path('upload/', views.upload_file, name='upload_file'),
    path('imports/', views.import_list, name='import_list'),
    path('imports/<int:pk>/', views.import_detail, name='import_detail'),
    path('imports/<int:pk>/preview/', views.preview_import, name='preview_import'),
    path('imports/<int:pk>/process/', views.process_import, name='process_import'),
    
    # API endpoints
    path('api/imports/<int:pk>/status/', views.import_status, name='import_status'),
    
    # Маппинги
    path('mappings/', views.mapping_list, name='mapping_list'),
    path('mappings/create/', views.mapping_create, name='mapping_create'),
    path('mappings/<int:pk>/edit/', views.mapping_edit, name='mapping_edit'),
    path('mappings/<int:pk>/delete/', views.mapping_delete, name='mapping_delete'),
    
    # Утилиты
    path('download-template/', views.download_template, name='download_template'),
]