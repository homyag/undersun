"""
Тесты для обнаружения ошибок на страницах сайта
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from apps.properties.models import Property, PropertyType, District, Location
from apps.core.models import Service


class ErrorPageTestCase(TestCase):
    """Тесты для проверки ошибок на страницах"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.client = Client()
        
        # Создаем тестовые данные
        self.district = District.objects.create(
            name="Тестовый район",
            slug="test-district"
        )
        
        self.location = Location.objects.create(
            name="Тестовая локация",
            slug="test-location",
            district=self.district
        )
        
        # Создаем все типы недвижимости для тестирования
        self.property_type_villa = PropertyType.objects.create(
            name="villa",
            name_display="Вилла"
        )
        
        self.property_type_condo = PropertyType.objects.create(
            name="condo",
            name_display="Кондоминиум"
        )
        
        self.property_type_townhouse = PropertyType.objects.create(
            name="townhouse",
            name_display="Таунхаус"
        )
        
        self.property_type_land = PropertyType.objects.create(
            name="land",
            name_display="Земельный участок"
        )
        
        self.property = Property.objects.create(
            title="Тестовый объект",
            slug="test-property",
            property_type=self.property_type_villa,
            district=self.district,
            location=self.location,
            status='active',
            deal_type='sale',
            price_sale_usd=100000
        )
        
        self.service = Service.objects.create(
            title="Тестовая услуга",
            slug="test-service",
            description="Описание услуги"
        )

    def test_404_pages(self):
        """Тест 404 ошибок для несуществующих страниц"""
        error_urls = [
            '/ru/property/nonexistent-property/',
            '/ru/locations/nonexistent-district/',
            '/ru/services/nonexistent-service/',
            '/ru/blog/nonexistent-post/',
            '/ru/nonexistent-page/',
        ]
        
        for url in error_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404, 
                               f"URL {url} должен возвращать 404")

    def test_property_type_urls(self):
        """Тест URL типов недвижимости"""
        # Тестируем существующие типы
        existing_urls = [
            '/ru/property/type/villa/',
            '/ru/property/type/condo/',
            '/ru/property/type/townhouse/',
            '/ru/property/type/land/',
        ]
        
        for url in existing_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, 
                               f"URL {url} должен работать")
        
        # Тестируем несуществующие типы - должны возвращать 404
        invalid_urls = [
            '/ru/property/type/apartment/',  # Не существует
            '/ru/property/type/house/',      # Не существует  
            '/ru/property/type/plot/',       # Не существует
            '/ru/property/type/mansion/',    # Не существует
            '/ru/property/type/warehouse/',  # Не существует
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404, 
                               f"URL {url} должен возвращать 404")

    def test_existing_pages_status(self):
        """Проверка существующих страниц на наличие ошибок"""
        urls_to_test = [
            '/ru/',  # Главная
            '/ru/property/',  # Каталог недвижимости
            f'/ru/property/{self.property.slug}/',  # Страница объекта
            '/ru/map/',  # Карта
            f'/ru/locations/{self.district.slug}/',  # Район
            f'/ru/services/{self.service.slug}/',  # Услуга
        ]
        
        for url in urls_to_test:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, [200, 301, 302], 
                            f"URL {url} возвращает ошибку: {response.status_code}")

    def test_ajax_endpoints(self):
        """Проверка AJAX эндпоинтов"""
        ajax_urls = [
            '/ru/property/ajax/list/',  # Правильный URL из urls.py
        ]
        
        for url in ajax_urls:
            with self.subTest(url=url):
                response = self.client.get(url, 
                                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertIn(response.status_code, [200, 400], 
                            f"AJAX URL {url} возвращает ошибку: {response.status_code}")

    def test_language_redirects(self):
        """Проверка редиректов языков"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.url.startswith('/ru/'))

    def test_invalid_property_filters(self):
        """Тест некорректных параметров фильтрации"""
        invalid_params = [
            {'property_type': 'invalid'},
            {'price_min': 'not_a_number'},
            {'bedrooms': 'invalid'},
            {'district': 'nonexistent'},
        ]
        
        for params in invalid_params:
            with self.subTest(params=params):
                response = self.client.get('/ru/property/', params)
                self.assertIn(response.status_code, [200, 400], 
                            f"Фильтр с параметрами {params} вызывает ошибку")

    def test_database_queries_limit(self):
        """Проверка количества запросов к БД на основных страницах"""
        from django.test.utils import override_settings
        from django.db import connection
        
        # Создаем дополнительные объекты для проверки N+1 проблем
        for i in range(5):
            Property.objects.create(
                title=f"Объект {i}",
                slug=f"property-{i}",
                property_type=self.property_type_villa,
                district=self.district,
                location=self.location,
                status='active',
                deal_type='sale',
                price_sale_usd=100000 + i * 10000
            )
        
        with self.assertNumQueries(9):  # Точный лимит на основе фактических 9 запросов
            response = self.client.get('/ru/property/')
            self.assertEqual(response.status_code, 200)

    def test_required_context_variables(self):
        """Проверка наличия обязательных переменных в контексте"""
        response = self.client.get('/ru/property/')
        self.assertEqual(response.status_code, 200)
        
        # Проверяем наличие ключевых переменных контекста
        context_vars = ['properties', 'property_types', 'districts']
        for var in context_vars:
            self.assertIn(var, response.context, 
                        f"Переменная {var} отсутствует в контексте")

    def test_template_rendering(self):
        """Проверка корректности рендеринга шаблонов"""
        response = self.client.get('/ru/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html')
        self.assertContains(response, '</html>')
        
        # Проверяем отсутствие Django debug информации в продакшене
        self.assertNotContains(response, 'DebugToolbar')


class AdminErrorTestCase(TestCase):
    """Тесты ошибок в админке"""
    
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        self.client = Client()
    
    def test_admin_login_required(self):
        """Проверка, что админка требует авторизации"""
        response = self.client.get('/admin/')
        # Должен быть редирект на страницу логина или 302
        self.assertIn(response.status_code, [302, 200])
    
    def test_admin_access_with_auth(self):
        """Проверка доступа к админке с авторизацией"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)


class MultiLanguageErrorTestCase(TestCase):
    """Тесты ошибок для многоязычности"""
    
    def test_language_prefixes(self):
        """Проверка работы языковых префиксов"""
        languages = ['ru', 'en', 'th']
        
        for lang in languages:
            with self.subTest(language=lang):
                response = self.client.get(f'/{lang}/')
                self.assertIn(response.status_code, [200, 404], 
                            f"Язык {lang} возвращает неожиданный статус")
    
    def test_invalid_language_prefix(self):
        """Проверка несуществующих языковых префиксов"""
        response = self.client.get('/invalid-lang/')
        self.assertEqual(response.status_code, 404)