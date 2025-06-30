from django.urls import path
from . import views

urlpatterns = [
    path('', views.LocationListView.as_view(), name='location_list'),
    path('<slug:district_slug>/', views.DistrictDetailView.as_view(), name='district_detail'),
    path('<slug:district_slug>/<slug:location_slug>/', views.LocationDetailView.as_view(), name='location_detail'),
]