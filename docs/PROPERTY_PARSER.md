# Парсер недвижимости Undersun Estate

## Описание

Парсер недвижимости (`parse_properties.py`) — это Django management команда для автоматического импорта объектов недвижимости с внешнего сайта undersunestate.com в локальную базу данных. Парсер извлекает полную информацию об объектах, включая характеристики, цены, изображения и метаданные.

## Расположение файла

```
apps/properties/management/commands/parse_properties.py
```

## Основные возможности

### 1. Типы недвижимости
- **Виллы** (villa)
- **Кондоминиумы** (condo)
- **Таунхаусы** (townhouse)
- **Земельные участки** (land)
- **Инвестиционная недвижимость** (investment)
- **Готовый бизнес** (business)

### 2. Типы сделок
- **Покупка** (buy/sale)
- **Аренда** (rent)
- **Все** (all) - покупка и аренда

### 3. Извлечение данных
- ✅ Заголовки и описания объектов
- ✅ Основные характеристики (спальни, ванные, площадь)
- ✅ Цены в различных валютах (THB, USD, RUB)
- ✅ Локации (районы и под-районы)
- ✅ Удобства (бассейн, парковка, охрана, спортзал)
- ✅ Галереи изображений с автоматическим сохранением
- ✅ SEO метаданные
- ✅ Оригинальные URL и ID для связи с источником

### 4. Интеллектуальная обработка изображений
- **Приоритетная система поиска:**
  1. Основные изображения из `/images/` директории
  2. Галереи и слайдеры (.gallery, .slider, .swiper)
  3. YooTheme и Joomla структуры (templates, cache)
  4. Lazy loading изображения
  5. Изображения высокого разрешения (800px+)

- **Умная фильтрация:**
  - Исключение логотипов, иконок, служебных изображений
  - Поддержка различных атрибутов (src, data-src, data-lazy)
  - Автоматическое создание thumbnails

### 5. Обработка цен и валют
- **Автоматическое определение валют:**
  - THB (฿) - основная валюта
  - USD ($)
  - RUB (₽)

- **Умное определение типа сделки:**
  - Анализ контекста (аренда/продажа)
  - Логика ценовых диапазонов
  - Автоматическое преобразование годовой аренды в месячную

## Использование

### Базовые команды

```bash
# Парсинг всей недвижимости (первые 5 страниц)
python manage.py parse_properties

# Парсинг конкретного типа недвижимости
python manage.py parse_properties --type villa
python manage.py parse_properties --type condo
python manage.py parse_properties --type townhouse

# Парсинг по типу сделки
python manage.py parse_properties --deal-type buy
python manage.py parse_properties --deal-type rent

# Комбинированный парсинг
python manage.py parse_properties --type villa --deal-type buy --max-pages 10

# Тестирование одного объекта
python manage.py parse_properties --test-single https://undersunestate.com/ru/real-estate/thalang/cherng-talay/450-apartment

# Подробный вывод процесса
python manage.py parse_properties --type condo --verbose
```

### Параметры команды

| Параметр | Описание | Варианты | По умолчанию |
|----------|----------|----------|--------------|
| `--type` | Тип недвижимости | `all`, `villa`, `condo`, `townhouse`, `land`, `investment`, `business` | `all` |
| `--deal-type` | Тип сделки | `all`, `buy`, `rent` | `all` |
| `--test-single` | URL одного объекта для тестирования | URL | - |
| `--max-pages` | Максимальное количество страниц | Число | `5` |
| `--verbose` | Подробный вывод процесса | Флаг | `False` |

## Алгоритм работы

### 1. Получение списка объектов
```python
# Загружает каталог недвижимости по указанным фильтрам
# Извлекает ссылки на все объекты с поддержкой пагинации
# Фильтрует валидные URL со структурой /ru/real-estate/{district}/{location}/{id}-{title}
```

### 2. Обработка каждого объекта
```python
# Для каждого URL объекта:
# 1. Загружает HTML страницы объекта
# 2. Извлекает заголовок и описание
# 3. Парсит характеристики (спальни, ванные, площадь)
# 4. Определяет цену и тип сделки
# 5. Извлекает тип недвижимости и локацию
# 6. Находит все изображения по приоритетному алгоритму
# 7. Проверяет на дубликаты по legacy_id и title
```

### 3. Сохранение в базу данных
```python
# Создает или обновляет записи Property
# Создает PropertyType, District, Location при необходимости
# Скачивает и сохраняет изображения как PropertyImage
# Автоматически устанавливает главное изображение
```

## Структура данных

### Модель Property (основные поля)
- `title` - заголовок объекта
- `slug` - URL-friendly версия заголовка
- `description` - полное HTML описание
- `short_description` - краткое описание (до 300 символов)
- `property_type` - тип недвижимости (ForeignKey)
- `deal_type` - тип сделки ('sale', 'rent', 'both')
- `district` / `location` - географическое расположение
- `bedrooms` / `bathrooms` - количество комнат
- `area_total` - общая площадь в м²
- `price_sale_thb` / `price_rent_monthly_thb` - цены в тайских батах
- `pool` / `parking` / `security` / `gym` - булевы удобства
- `legacy_id` - ID объекта с исходного сайта
- `original_url` - ссылка на исходную страницу

### Модель PropertyImage
- `property` - связь с объектом недвижимости
- `image` - файл изображения
- `is_main` - главное изображение объекта
- `order` - порядок отображения
- `image_type` - тип изображения ('main', 'floorplan', etc.)

### Автоматически создаваемые связанные объекты
- **PropertyType** - типы недвижимости
- **District** - районы (Thalang, Kathu, Muang Phuket)
- **Location** - под-районы (Cherng Talay, Bang Tao, etc.)

## Обработка дубликатов

Парсер автоматически определяет дубликаты по:
1. `legacy_id` - ID объекта с исходного сайта
2. `title` - точное совпадение заголовка

При обнаружении дубликата:
- Обновляет описание и характеристики, если они пустые
- Добавляет новые изображения
- Не создает повторные записи

## Журналирование

### В режиме --verbose показывает:
- Процесс загрузки каждой страницы каталога
- Извлеченные данные для каждого объекта
- Найденные изображения и их количество
- Статус сохранения (новый объект/обновление/дубликат)
- Процесс скачивания изображений

### Итоговая статистика:
- Количество успешно обработанных объектов
- Количество найденных дубликатов
- Количество ошибок
- Общее количество обработанных URL

## Пример вывода

```
Начинаем парсинг недвижимости: тип=villa, сделка=buy
Загружаем страницу 1: https://undersunestate.com/ru/real-estate/villa
Найдено 12 новых объектов на странице 1
Загружаем страницу 2: https://undersunestate.com/ru/real-estate/villa?page=2
Найдено 15 новых объектов на странице 2
Всего найдено 27 объектов на 2 страницах

Парсинг 1/27: https://undersunestate.com/ru/real-estate/kathu/patong/852-luxury-villa
Извлеченные данные:
  legacy_id: 852
  title: Роскошная вилла в Патонге с видом на море
  bedrooms: 4
  bathrooms: 3
  area_total: 280
  price_sale_thb: 15500000
  deal_type: sale
  property_type: villa
  district_slug: kathu
  location_slug: patong
  description: 890 символов
  images: 8 изображений
Создан новый район: Kathu
Создана новая локация: Patong
Создан новый объект: Роскошная вилла в Патонге с видом на море
Сохранено изображение: villa-exterior-1.jpg
Сохранено изображение: villa-pool.jpg
...

=== РЕЗУЛЬТАТЫ ПАРСИНГА ===
Успешно обработано: 25
Найдено дубликатов: 2
Ошибок: 0
Всего обработано: 27
```

## Требования

### Python пакеты:
- `requests` - HTTP запросы
- `beautifulsoup4` - парсинг HTML
- `Pillow` - обработка изображений
- `django` - веб-фреймворк

### Django приложения:
- `apps.properties` - модели недвижимости
- `apps.locations` - географические модели
- `django.contrib.auth` - пользователи

## Обработка ошибок

- **HTTP ошибки**: Пропуск недоступных страниц
- **Изображения**: Продолжение работы при ошибках скачивания
- **Парсинг данных**: Fallback к базовым значениям
- **Сеть**: Таймауты и повторные попытки
- **Дубликаты**: Умное обновление существующих записей

## Настройка

### User-Agent
```python
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
```

### Задержки между запросами
```python
time.sleep(1)  # 1 секунда между объектами
time.sleep(0.5)  # 0.5 секунды между страницами
```

### Таймауты
```python
timeout=30  # 30 секунд для скачивания изображений
```

## Расширение функциональности

### Добавление новых типов недвижимости
```python
# В методе get_or_create_property_type()
type_mapping = {
    'villa': ('villa', 'Вилла'),
    'condo': ('condo', 'Кондоминиум'),
    'new_type': ('new_type', 'Новый тип'),  # Добавить здесь
}
```

### Добавление новых селекторов изображений
```python
# В методе extract_property_images()
image_selectors = [
    'img[src*="/images/"]',
    '.new-gallery img',  # Добавить новый селектор
]
```

### Добавление новых характеристик
```python
# В методе extract_property_characteristics()
# Добавить извлечение новых полей, например:
balcony_patterns = [r'(\d+)\s*балкон', r'(\d+)\s*balcon']
for pattern in balcony_patterns:
    match = re.search(pattern, text)
    if match:
        data['balconies'] = int(match.group(1))
        break
```

## Мониторинг и поддержка

### Логи ошибок
Все ошибки выводятся в консоль с использованием Django logging:
```python
self.stdout.write(self.style.ERROR(f"Ошибка: {e}"))
self.stdout.write(self.style.WARNING(f"Предупреждение: {message}"))
self.stdout.write(self.style.SUCCESS(f"Успех: {message}"))
```

### Проверка результатов
```bash
# Проверить созданные объекты
python manage.py shell -c "from apps.properties.models import Property; print(f'Объектов: {Property.objects.count()}')"

# Проверить типы недвижимости
python manage.py shell -c "from apps.properties.models import PropertyType; [print(f'{pt.name_display}: {pt.property_set.count()}') for pt in PropertyType.objects.all()]"

# Проверить районы
python manage.py shell -c "from apps.locations.models import District; [print(f'{d.name}: {d.property_set.count()}') for d in District.objects.all()]"

# Проверить изображения
python manage.py shell -c "from apps.properties.models import Property; [print(f'{p.title}: {p.images.count()} изображений') for p in Property.objects.all()[:5]]"
```

### Производительность
```bash
# Статистика по времени выполнения
time python manage.py parse_properties --type villa --max-pages 3

# Проверка размера базы данных
python manage.py dbshell -c "SELECT COUNT(*) as objects FROM properties_property;"
python manage.py dbshell -c "SELECT COUNT(*) as images FROM properties_propertyimage;"
```

---

## История изменений

### v1.0 (Текущая версия)
- ✅ Полнофункциональный парсинг объектов недвижимости
- ✅ Интеллектуальное извлечение характеристик и цен
- ✅ Система обработки изображений с приоритизацией
- ✅ Автоматическое определение районов и локаций
- ✅ Поддержка множественных типов недвижимости и сделок
- ✅ Система предотвращения дубликатов
- ✅ Подробное журналирование и статистика

### Планы на будущее
- [ ] Интеграция с внешними API для проверки цен
- [ ] Автоматический перевод описаний на разные языки
- [ ] Система уведомлений о новых объектах
- [ ] Интеграция с картографическими сервисами для координат