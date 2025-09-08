from django.urls import path
from . import views

# Admin AJAX endpoints (не требуют i18n префиксов)
urlpatterns = [
    path('update-image-order/', views.update_image_order, name='admin_update_image_order'),
    path('bulk-upload-images/', views.bulk_upload_images, name='admin_bulk_upload_images'),
]