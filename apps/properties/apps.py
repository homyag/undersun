from django.apps import AppConfig

class PropertiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.properties'
    verbose_name = 'Недвижимость'
    
    def ready(self):
        import apps.properties.translation
