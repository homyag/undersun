from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('bot/metrika-loaded/', views.metrika_loaded_ping, name='metrika_loaded'),
    path('about-us/team/<path:legacy_slug>/', views.legacy_team_member_redirect, name='legacy_team_member'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('map/', views.MapView.as_view(), name='map'),
    path('services/<slug:slug>/', views.ServiceDetailView.as_view(), name='service_detail'),
    path('privacy-policy/', views.legacy_privacy_policy_redirect, name='legacy_privacy_policy'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
    path('terms/', views.TermsView.as_view(), name='terms'),
]
