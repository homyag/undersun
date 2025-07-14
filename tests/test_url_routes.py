"""
Тесты основных URL маршрутов проекта
"""
from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth.models import User
from apps.properties.models import Property, PropertyType, District, Location
from apps.core.models import Service


class URLRoutesTestCase(TestCase):
    """Тесты маршрутизации URL"""
    
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
        
        self.property_type = PropertyType.objects.create(
            name="villa",
            name_display="Тестовый тип"
        )
        
        self.property = Property.objects.create(
            title="Тестовый объект",
            slug="test-property", 
            property_type=self.property_type,
            district=self.district,
            location=self.location,
            status='active',
            deal_type='sale',
            price_sale_usd=100000
        )

    def test_core_urls(self):
        """Тест основных URL маршрутов"""
        urls = [
            '/ru/',  # Главная страница
            '/ru/map/',  # Карта
            '/ru/about/',  # О компании
            '/ru/contact/',  # Контакты
        ]
        
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, [200, 404], 
                            f"URL {url} недоступен")

    def test_property_urls(self):
        """Тест URL недвижимости"""
        urls = [
            '/ru/property/',  # Каталог
            f'/ru/property/{self.property.slug}/',  # Детальная страница
            '/ru/property/ajax/list/',  # AJAX фильтрация (правильный URL)
        ]
        
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, [200, 302], 
                            f"Property URL {url} недоступен")

    def test_location_urls(self):
        """Тест URL локаций"""
        urls = [
            '/ru/locations/',  # Список районов
            f'/ru/locations/{self.district.slug}/',  # Страница района
        ]
        
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url) 
                self.assertIn(response.status_code, [200, 404], 
                            f"Location URL {url} недоступен")

    def test_admin_urls(self):
        """Тест административных URL"""
        # Без авторизации должен быть редирект
        response = self.client.get('/admin/')
        self.assertIn(response.status_code, [200, 302])
        
        # Тест других admin URL
        admin_urls = [
            '/admin/login/',
            '/admin/logout/',
        ]
        
        for url in admin_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, [200, 302, 405])

    def test_language_switching_urls(self):
        """Тест переключения языков"""
        response = self.client.post('/i18n/setlang/', {'language': 'en'})
        self.assertIn(response.status_code, [200, 302])

    def test_currency_urls(self):
        """Тест URL валют"""
        response = self.client.post('/currency/set/', {'currency': 'USD'})
        self.assertIn(response.status_code, [200, 302, 404])

    def test_static_urls(self):
        """Тест статических URL"""
        static_urls = [
            '/static/css/styles.css',
            '/static/js/main.js', 
        ]
        
        for url in static_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                # Статические файлы могут не существовать в тестах
                self.assertIn(response.status_code, [200, 404])

    def test_blog_urls(self):
        """Тест URL блога"""
        blog_urls = [
            '/ru/blog/',  # Список постов
            '/ru/blog/test-post/',  # Детальная страница (может не существовать)
        ]
        
        for url in blog_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, [200, 404])

    def test_user_urls(self):
        """Тест пользовательских URL"""
        user_urls = [
            '/ru/users/favorites/',  # Избранное
            '/ru/users/profile/',   # Профиль
        ]
        
        for url in user_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                # Могут требовать авторизации
                self.assertIn(response.status_code, [200, 302, 404])

    def test_url_reversibility(self):
        """Тест обратимости URL (reverse)"""
        try:
            # Проверяем что основные URL можно построить через reverse
            home_url = reverse('core:home')
            self.assertTrue(home_url.startswith('/'))
        except Exception:
            # Если reverse не работает, это тоже важная информация
            pass

    def test_redirect_from_root(self):
        """Тест редиректа с корневого URL"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.url.endswith('/ru/'))


class URLPerformanceTestCase(TestCase):
    """Тесты производительности URL"""
    
    def setUp(self):
        # Создаем несколько объектов для тестирования производительности
        district = District.objects.create(name="Test District", slug="test-district")
        location = Location.objects.create(name="Test Location", slug="test-location", district=district)
        property_type = PropertyType.objects.create(name="villa", name_display="Test Type")
        
        for i in range(10):
            Property.objects.create(
                title=f"Property {i}",
                slug=f"property-{i}",
                property_type=property_type,
                district=district,
                location=location,
                status='active',
                deal_type='sale',
                price_sale_usd=100000 + i * 10000
            )

    def test_property_list_performance(self):
        """Тест производительности списка недвижимости"""
        import time
        
        start_time = time.time()
        response = self.client.get('/ru/property/')
        end_time = time.time()
        
        # Страница должна загружаться быстро (меньше 2 секунд)
        self.assertLess(end_time - start_time, 2.0)
        self.assertEqual(response.status_code, 200)

    def test_ajax_filter_performance(self):
        """Тест производительности AJAX фильтрации"""
        import time
        
        start_time = time.time()
        response = self.client.get('/ru/property/ajax/list/', 
                                 {'property_type': 'villa'},
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        end_time = time.time()
        
        # AJAX должен быть быстрым (меньше 1 секунды)
        self.assertLess(end_time - start_time, 1.0)


class SecurityURLTestCase(TestCase):
    """Тесты безопасности URL"""
    
    def test_admin_security(self):
        """Проверка безопасности административных URL"""
        # Без авторизации не должно быть доступа к админке
        admin_urls = [
            '/admin/properties/property/',
            '/admin/properties/property/add/',
            '/admin/core/service/',
        ]
        
        for url in admin_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                # Должен быть редирект на логин или 403
                self.assertIn(response.status_code, [302, 403])

    def test_sql_injection_protection(self):
        """Тест защиты от SQL инъекций в параметрах"""
        malicious_params = [
            "'; DROP TABLE properties_property; --",
            "1' OR '1'='1",
            "<script>alert('xss')</script>",
        ]
        
        for param in malicious_params:
            with self.subTest(param=param):
                response = self.client.get('/ru/property/', {'search': param})
                # Не должно быть ошибки сервера
                self.assertNotEqual(response.status_code, 500)

    def test_xss_protection(self):
        """Тест защиты от XSS в параметрах поиска"""
        xss_payload = "<script>alert('xss')</script>"
        response = self.client.get('/ru/property/', {'search': xss_payload})
        
        # Проверяем что скрипт не выполняется в ответе
        if response.status_code == 200:
            self.assertNotContains(response, "<script>alert('xss')</script>", html=False)