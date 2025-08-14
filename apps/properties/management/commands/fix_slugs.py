from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.properties.models import Property


class Command(BaseCommand):
    help = 'Fix slugs for all properties to ensure they are URL-safe'
    
    def handle(self, *args, **options):
        self.stdout.write('Fixing property slugs...')
        
        properties = Property.objects.all()
        fixed_count = 0
        
        for prop in properties:
            old_slug = prop.slug
            
            # Создаем новый slug из названия
            base_slug = slugify(prop.title)
            
            # Добавляем ID для уникальности
            new_slug = f"{base_slug}-{prop.id}"
            
            # Проверяем, нужно ли обновление
            if old_slug != new_slug:
                # Проверяем уникальность
                counter = 1
                unique_slug = new_slug
                while Property.objects.filter(slug=unique_slug).exclude(id=prop.id).exists():
                    unique_slug = f"{new_slug}-{counter}"
                    counter += 1
                
                prop.slug = unique_slug
                prop.save(update_fields=['slug'])
                
                self.stdout.write(f'  Fixed: {old_slug} -> {unique_slug}')
                fixed_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully fixed {fixed_count} property slugs!')
        )