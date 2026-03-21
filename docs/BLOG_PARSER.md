# Парсер блога Undersun Estate

## Описание

Парсер блога (`parse_blog.py`) — это Django management команда для автоматического импорта статей блога с внешнего сайта undersunestate.com в локальную базу данных. Парсер извлекает полный контент статей, включая изображения, видео и метаданные.

## Расположение файла

```
apps/blog/management/commands/parse_blog.py
```

## Основные функции

### 1. Парсинг категорий блога
- **Новости** (news)
- **Статьи** (articles) 
- **Кейсы** (cases)
- **Обзоры** (reviews)
- **Места и активности** (places)
- **Мероприятия** (events)

### 2. Извлечение контента
- ✅ Заголовки статей
- ✅ Основной текст с HTML-форматированием
- ✅ Даты публикации (поддержка русского формата)
- ✅ Краткие описания (excerpt)
- ✅ Главные изображения (featured images)
- ✅ Видео YouTube (автоматическое встраивание iframe)
- ✅ SEO метаданные
- ✅ Оригинальные URL и ID для связи с источником

### 3. Обработка изображений
- **Приоритетная система поиска:**
  1. Meta теги (`og:image`, `twitter:image`)
  2. Специальные контейнеры (`.el-image`, `.featured-image`)
  3. YooTheme кэш (`/templates/yootheme/cache/`) - профессиональные обложки
  4. Директории блога (`/images/For_blog/`)
  5. Первые изображения в статье

- **Умная фильтрация:**
  - Исключение логотипов, иконок, флагов
  - Приоритет крупным изображениям (400x300+)
  - Фильтрация служебных элементов интерфейса

### 4. Обработка видео
- Автоматическое извлечение YouTube ссылок из текста
- Преобразование в iframe для встраивания
- Поддержка различных форматов YouTube URL:
  - `https://youtube.com/watch?v=...`
  - `https://youtu.be/...`
  - `https://youtube.com/embed/...`

## Использование

### Базовые команды

```bash
# Парсинг всех новостей сразу на трёх языках (ru,en,th по умолчанию)
python manage.py parse_blog --category news

# Ограничение списка языков
python manage.py parse_blog --category news --languages ru,en

# Парсинг с подробным выводом
python manage.py parse_blog --category news --verbose

# Парсинг других категорий
python manage.py parse_blog --category articles
python manage.py parse_blog --category reviews
python manage.py parse_blog --category cases

# Тестирование одной статьи и явный выбор языка источника
python manage.py parse_blog --test-single https://undersunestate.com/en/blog/news/1094-article-title --language en
```

### Параметры команды

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--category` | Категория блога для парсинга | `news` |
| `--languages` | Список языков через запятую для пакетного парсинга (ru, en, th) | `ru,en,th` |
| `--language` | Язык одиночной статьи при `--test-single` (если не указан — берётся первый из `--languages`) | – |
| `--test-single` | URL одной статьи для тестирования | – |
| `--verbose` | Подробный вывод процесса | `False` |

## Алгоритм работы

### 1. Получение списка статей
```python
# Загружает страницу категории (например, /ru/blog/news)
# Извлекает ссылки на все статьи в категории
# Фильтрует валидные URL со структурой /ru/blog/{category}/{id}-{title}
```

### 2. Обработка каждой статьи
```python
# Для каждого URL статьи:
# 1. Загружает HTML страницы
# 2. Извлекает заголовок из <h1> или .uk-article-title
# 3. Парсит дату публикации (русский формат: "22 мая 2025")
# 4. Извлекает основной контент из article/main контейнеров
# 5. Находит главное изображение по приоритетному алгоритму
# 6. Извлекает YouTube видео и преобразует в iframe
# 7. Проверяет на дубликаты по original_id и title
```

### 3. Сохранение в базу данных
```python
# Создает или обновляет записи BlogPost
# Скачивает и сохраняет featured изображения
# Создает категории BlogCategory при необходимости
# Связывает с автором по умолчанию (username: 'parser')
```

## Структура данных

### Модель BlogPost
- `title` - заголовок статьи (хранится вместе с переводами `title_en`, `title_th`)
- `slug` - URL-friendly версия заголовка
- `content` / `content_en` / `content_th` - полный HTML контент для каждого языка
- `excerpt` / `excerpt_en` / `excerpt_th` - краткое описание (до 500 символов)
- `featured_image`, `featured_image_en`, `featured_image_th` - локализованные главные изображения
- `published_at` - дата публикации
- `original_url`, `original_url_en`, `original_url_th` - ссылки на исходные версии
- `original_id` - ID статьи на исходном сайте
- `category` - связь с BlogCategory
- `author` - автор (по умолчанию 'parser')
- `status` - статус публикации ('published')

### Модель BlogCategory  
- `name` - название категории
- `slug` - URL slug
- `description` - описание
- `color` - цвет для интерфейса

## Обработка дубликатов

Парсер автоматически определяет дубликаты по:
1. `original_id` - ID статьи с исходного сайта
2. `title` - точное совпадение заголовка

При обнаружении дубликата:
- Обновляет контент, если он изменился
- Сохраняет актуальную информацию
- Не создает повторные записи

## Журналирование

### В режиме --verbose показывает:
- Процесс загрузки каждой статьи
- Извлеченные данные (заголовок, дата, размер контента)
- Найденные изображения и видео
- Статус сохранения (новая статья/обновление/дубликат)

### Итоговая статистика:
- Количество успешно обработанных статей
- Количество найденных дубликатов  
- Количество ошибок
- Общее количество обработанных URL

## Пример вывода

```
Начинаем парсинг категории: news
Загружаем категорию: https://undersunestate.com/ru/blog/news
Найдено 3 статей для парсинга

Парсинг 1/3: https://undersunestate.com/ru/blog/news/1094-podcast-title
Извлеченные данные:
  original_id: 1094
  title: Первый подкаст о Phuket Property Association...
  published_at: 2025-05-22 00:00:00+07:00
  content: 1680 символов
  featured_image_url: https://undersunestate.com/templates/yootheme/cache/...
Создана новая статья: Первый подкаст о Phuket Property Association...
Сохранено изображение: podcast-cover.jpeg

=== РЕЗУЛЬТАТЫ ПАРСИНГА ===
Успешно обработано: 3
Найдено дубликатов: 0
Ошибок: 0
Всего обработано: 3
```

## Требования

### Python пакеты:
- `requests` - HTTP запросы
- `beautifulsoup4` - парсинг HTML
- `Pillow` - обработка изображений
- `django` - веб-фреймворк

### Django приложения:
- `apps.blog` - модели блога
- `django.contrib.auth` - пользователи

## Обработка ошибок

- **HTTP ошибки**: Пропуск недоступных страниц
- **Изображения**: Продолжение работы при ошибках скачивания
- **Парсинг контента**: Fallback к базовому извлечению текста
- **Сеть**: Таймауты и повторные попытки

## Настройка

### User-Agent
```python
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
```

### Задержки между запросами
```python
time.sleep(1)  # 1 секунда между запросами
```

### Таймауты
```python
timeout=30  # 30 секунд для скачивания изображений
```

## Расширение функциональности

### Добавление новых категорий
```python
# В методе get_or_create_blog_category()
category_names = {
    'news': 'Новости',
    'articles': 'Статьи',
    'new_category': 'Новая категория',  # Добавить здесь
}
```

### Добавление новых селекторов изображений
```python
# В методе extract_featured_image()
image_selectors = [
    # Добавить новые селекторы в порядке приоритета
    '.new-image-selector img',
]
```

### Добавление новых видео сервисов
```python
# В методе extract_video_links()
video_patterns = [
    r'https?://vimeo\.com/[\w-]+',  # Добавить Vimeo
    r'https?://rutube\.ru/video/[\w-]+',  # Добавить RuTube
]
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
# Проверить созданные статьи
python manage.py shell -c "from apps.blog.models import BlogPost; print(BlogPost.objects.count())"

# Проверить категории
python manage.py shell -c "from apps.blog.models import BlogCategory; [print(f'{c.name}: {c.posts.count()}') for c in BlogCategory.objects.all()]"

# Проверить изображения
python manage.py shell -c "from apps.blog.models import BlogPost; [print(f'{p.title}: {bool(p.featured_image)}') for p in BlogPost.objects.all()]"
```

---

## История изменений

### v1.1 (Текущая версия)
- ✅ Улучшен алгоритм поиска главных изображений
- ✅ Добавлена приоритизация YooTheme кэша
- ✅ Улучшена фильтрация служебных изображений
- ✅ Добавлена поддержка проверки размеров изображений
- ✅ Исправлены проблемы с временными зонами

### v1.0 (Первоначальная версия)
- ✅ Базовый парсинг статей блога
- ✅ Извлечение текста, заголовков, дат
- ✅ Простой поиск изображений
- ✅ Интеграция с YouTube видео
- ✅ Система предотвращения дубликатов
