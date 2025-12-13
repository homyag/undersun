from django.urls import path, include
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_list, name='list'),
    path('tinymce-upload/', views.tinymce_upload, name='tinymce_upload'),
    path('<slug:slug>/', views.blog_detail, name='detail'),
    path('<slug:slug>/amp/', views.blog_detail_amp, name='detail_amp'),
    path('category/<slug:slug>/', views.blog_category, name='category'),
    path('tag/<slug:slug>/', views.blog_tag, name='tag'),
    path('tinymce/', include('tinymce.urls')),
]
