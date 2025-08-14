from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.blog'
    verbose_name = 'Блог'
    
    def ready(self):
        # Импортируем файл переводов
        import apps.blog.translation
