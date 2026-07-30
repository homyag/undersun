# Undersun Estate

Мультиязычный сайт агентства недвижимости на Пхукете. Публичная часть работает на русском, английском и тайском языках; ключевые сценарии — каталог объектов, карточки недвижимости, лид-формы, локации и блог.

## Стек

- Python 3, Django 5, PostgreSQL
- Django templates, Tailwind CSS и vanilla JavaScript
- `django-modeltranslation` для RU/EN/TH
- TinyMCE для редакционного контента
- ImageKit для вариантов изображений

## Быстрый старт

Требуются Python 3, PostgreSQL и Node.js/npm.

```bash
git clone <repository-url>
cd undersunestate_django

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Заполните .env локальными значениями; не коммитьте этот файл.

python manage.py migrate
python manage.py runserver
```

Сайт будет доступен по адресу <http://127.0.0.1:8000/>. Админка — `/admin/`.

## Настройки окружения

Настройки выбираются через `DJANGO_ENVIRONMENT`:

- `development` — режим разработки;
- `production` — production-настройки, PostgreSQL и security headers.

Минимально важные переменные для production:

```dotenv
DJANGO_ENVIRONMENT=production
SECRET_KEY=...
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=undersunestate.com,www.undersunestate.com
CSRF_TRUSTED_ORIGINS=https://undersunestate.com,https://www.undersunestate.com
```

Дополнительные интеграции — SMTP, reCAPTCHA, перевод и Google Business Profile — настраиваются через `.env`; ориентируйтесь на `.env.example` и `config/settings/base.py`.

## Frontend и CSS

Основной layout использует `theme/static/css/dist/styles.css`. Его собирает pipeline в `theme/static_src`:

```bash
cd theme/static_src
npm install
npm run dev       # watch-режим
npm run build     # production-сборка
```

Корневой `package.json` собирает `static/css/tailwind.min.css`; этот файл не подключён базовым шаблоном по умолчанию. Не используйте этот pipeline для обычных изменений базового интерфейса.

## Полезные команды

```bash
# Проверки
python manage.py check
python manage.py test

# База данных
python manage.py makemigrations
python manage.py migrate

# Валюты и данные
python manage.py setup_currencies
python manage.py update_exchange_rates

# Контент и SEO
python manage.py generate_property_seo_landings
python manage.py parse_properties --type villa --deal-type buy --max-pages 5
python manage.py parse_blog --category news --languages ru,en,th

# Операционные проверки
python manage.py analyze_bad_requests
python manage.py ban_bad_requests
```

## Структура проекта

```text
apps/
  core/            # главная, статические страницы, SEO, сервисы, anti-bot
  properties/      # каталог, карточки, карта, YML feed
  locations/       # районы и локации
  currency/        # курсы и выбранная валюта
  users/           # лид-формы и уведомления
  blog/            # статьи, FAQ, AMP и переводы
config/            # URL и settings
templates/         # серверные Django-шаблоны
static/js/         # клиентские JS-модули
theme/static_src/  # основной Tailwind source и build
```

## Важные правила разработки

- Публичные маршруты всегда имеют языковой префикс: `/ru/`, `/en/`, `/th/`.
- Перед изменением frontend-кода проверьте владельца логики: шаблон, `static/js` или оба слоя.
- Новые формы должны использовать существующую защиту: CSRF, reCAPTCHA при настройке, honeypot и проверку времени заполнения.
- Новые CTA следует снабжать метрикой через `data-ym-goal` или `dispatchMetrikaGoal`.
- Не редактируйте и не удаляйте миграции, уже применённые на окружениях. При расхождении истории сначала сверяйте Git и `django_migrations`.
- Не храните ключи, пароли, дампы и локальные данные в Git.

## Документация

- [Onboarding и правила проекта](AGENTS.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Карта функций](docs/FUNCTIONS_RU.md)
- [Документационный хаб](docs/README.md)

При расхождении документации и кода источником истины является код.
