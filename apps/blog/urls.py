from django.urls import path, include
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_list, name='list'),
    path('tinymce-upload/', views.tinymce_upload, name='tinymce_upload'),
    path('articles/<path:legacy_slug>/', views.legacy_blog_article_redirect, name='legacy_article_redirect'),
    path('articles/<path:legacy_slug>', views.legacy_blog_article_redirect),
    path('checklist-buyer-real-estate-thailand/', views.buying_guide_redirect, name='buying_guide_en_legacy_redirect'),
    path('<slug:slug>/', views.blog_detail, name='detail'),
    path('<slug:slug>/amp/', views.blog_detail_amp, name='detail_amp'),
    path('category/<slug:slug>/', views.blog_category, name='category'),
    path('tag/<slug:slug>/', views.blog_tag, name='tag'),
    path('tinymce/', include('tinymce.urls')),
]
