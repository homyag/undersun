# Undersun Estate - Real Estate Platform

## 1. Project Overview

**Undersun Estate** is a comprehensive multi-language real estate platform focused on the Phuket, Thailand market. The application serves as a professional real estate agency website offering property listings for sale and rent, with advanced search capabilities, interactive maps, and multi-currency support.

### Target Audience
- **Primary**: Russian-speaking investors and buyers looking for properties in Thailand
- **Secondary**: English-speaking international clients  
- **Tertiary**: Thai local market

### Core Business Model
- Real estate agency specializing in Phuket properties
- Property listings for sale and rental
- Investment-focused offerings
- Client consultation and property management services

## 2. Technical Architecture

### Framework & Version
- **Django 5.0.6** - Main web framework
- **Python 3.x** with modern async capabilities
- **PostgreSQL** - Primary database (psycopg2-binary 2.9.9)
- **Multi-app Django architecture** with separation of concerns

### App Structure
```
apps/
├── core/           # Site-wide functionality, SEO, services
├── properties/     # Property listings and management
├── locations/      # Geographic organization (districts/locations)
├── users/          # User management and inquiries
├── currency/       # Multi-currency support
├── blog/           # Content marketing and SEO blog
└── data_import/    # Legacy data migration tools
```

### Configuration
- **Multi-environment setup**: base, development, production settings
- **Environment variables** via django-environ
- **Organized static files** with Tailwind CSS
- **Multi-language support** with i18n patterns

## 3. Features & Functionality

### 3.1 Property Management System

#### Property Types Supported
- **Villas** - Luxury standalone homes
- **Condominiums** - Apartment complexes
- **Townhouses** - Multi-story attached homes
- **Land Plots** - Raw land for development
- **Investment Properties** - Income-generating assets
- **Ready Business** - Operational commercial properties

#### Property Information Architecture
- **Basic Details**: Title, description, property type, deal type (sale/rent/both)
- **Location Data**: District, specific location, address, GPS coordinates
- **Physical Specs**: Bedrooms, bathrooms, total/living/land area, floors
- **Pricing**: Multi-currency support (USD, THB, RUB) for both sale and rent
- **Features**: Pool, parking, security, gym, furnished status
- **Media**: Multiple images with thumbnail generation, floor plans
- **SEO**: Custom meta tags per property with template system
- **Legacy Support**: Migration fields from old Joomla system

#### Advanced Property Features
- **Special Offers**: Promotional pricing and urgency flags
- **Investment Analysis**: ROI potential and suitability descriptions  
- **Agent Assignment**: Dedicated agent per property
- **Feature Tags**: Amenities through many-to-many relationships
- **Distance Metrics**: Travel time to beaches, airport, schools
- **Bed Configuration**: Detailed bed type breakdown (double, single, sofa beds)

### 3.2 Search & Discovery

#### Search Capabilities
- **Text Search**: Full-text search across titles and descriptions
- **Advanced Filters**:
  - Property type (multiple selection)
  - Deal type (sale/rent)
  - Price range (respects selected currency)
  - Bedrooms (including 4+ option)
  - Districts and locations
  - Property features and amenities
- **Sorting Options**: Price, area, date added
- **AJAX Loading**: Dynamic results without page reload

#### Geographic Organization
- **Two-level hierarchy**: Districts → Locations
- **District Pages**: Dedicated landing pages for each area
- **Location Pages**: Specific neighborhood information
- **Interactive Maps**: Leaflet.js integration with property markers
- **Coordinate Storage**: High-precision GPS data (18,15 decimal places)

#### Interactive Map System
- **Map View Toggle**: Switch between grid and map views in property catalog
- **Real-time Filtering**: Map updates automatically when filters are applied
- **All Properties Display**: Shows all filtered properties, not limited to pagination
- **Property Markers**: Each property displayed as a map marker with popup information
- **Marker Clustering**: Smart positioning to handle overlapping coordinates
- **AJAX Loading**: Efficient loading of all properties for map view via backend API
- **Popup Details**: Property title, type, location, price, and direct link
- **Currency Integration**: Prices in popups respect user's selected currency
- **Responsive Design**: Full functionality on desktop and mobile devices
- **View Persistence**: Remembers user's preferred view (map/grid) between sessions

### 3.3 Multi-Language System

#### Language Support
- **Russian (Primary)**: Default language, complete content
- **English**: Full translation support
- **Thai**: Local market support

#### Translation Infrastructure
- **django-modeltranslation**: Field-level translations
- **Rosetta Interface**: Admin translation management
- **API Integration**: Yandex Translate API
- **Automated Translation**: Bulk translation actions in admin
- **SEO-Aware**: Translated URLs and meta tags

#### Translation Services
- **Yandex Translate API** integration через REST-запросы
- **Настройка доступа** через переменные окружения (`YANDEX_TRANSLATE_API_KEY`, `YANDEX_TRANSLATE_FOLDER_ID`)
- **Bulk operations** with admin actions
- **Force retranslation** capabilities

### 3.4 Currency Management

#### Multi-Currency Support
- **Primary Currencies**: USD, THB (Thai Baht), RUB (Russian Ruble)
- **Exchange Rate Management**: API-driven rate updates
- **Conversion System**: Real-time price calculation
- **User Preferences**: Language-based default currencies
- **Session Storage**: Maintains user's selected currency

#### Currency Features  
- **Live Conversion**: Dynamic price updates without page reload
- **Exchange Rate History**: Stored historical rates
- **Admin Management**: Manual rate override capability
- **API Sources**: exchangerate-api.com integration
- **Fallback Pricing**: Stored prices in multiple currencies

### 3.5 User Experience Features

#### Favorites System
- **Session-Based**: Works without user registration
- **Persistent Storage**: Maintains favorites across sessions
- **Quick Toggle**: Heart icon on property cards
- **Dedicated Page**: View all saved favorites
- **Count Display**: Dynamic counter in navigation

#### Responsive Design
- **Mobile-First**: Tailwind CSS framework
- **Touch-Friendly**: Mobile navigation and interactions
- **Performance Optimized**: Image thumbnails and lazy loading
- **Cross-Browser**: Modern browser compatibility

#### Interactive Elements
- **Property Gallery**: Image sliders with zoom
- **Map Integration**: Property location visualization  
- **AJAX Forms**: Contact forms without page reload
- **Social Sharing**: Open Graph meta tags
- **WhatsApp Integration**: Direct messaging button

## 4. Database Structure

### 4.1 Core Models

#### Property Model
```python
class Property(models.Model):
    # Basic Information
    title = CharField(max_length=200)
    slug = SlugField(unique=True)
    property_type = ForeignKey(PropertyType)
    deal_type = CharField(choices=['sale', 'rent', 'both'])
    status = CharField(choices=['available', 'reserved', 'sold', 'rented'])
    
    # Location
    district = ForeignKey(District)
    location = ForeignKey(Location, nullable=True)
    address = CharField
    latitude/longitude = DecimalField(high precision)
    
    # Specifications  
    bedrooms/bathrooms = PositiveIntegerField
    area_total/area_living/area_land = DecimalField
    floor/floors_total = PositiveIntegerField
    
    # Multi-currency pricing
    price_sale_usd/thb/rub = DecimalField
    price_rent_monthly_usd/thb/rub = DecimalField
    
    # Features
    furnished/pool/parking/security/gym = BooleanField
    developer = ForeignKey(Developer)
    agent = ForeignKey(Agent)
    
    # Legacy & Investment
    legacy_id = CharField  # Joomla migration
    is_for_investment = BooleanField
    special_offer = CharField
    
    # SEO (multi-language)
    custom_title_ru/en/th = CharField
    custom_description_ru/en/th = TextField
    custom_keywords_ru/en/th = TextField
```

#### Location Hierarchy
```python
class District(models.Model):  # Top level (e.g., Patong, Kata)
    name = CharField
    slug = SlugField
    description = TextField

class Location(models.Model):  # Sub-areas within districts
    name = CharField
    slug = SlugField
    district = ForeignKey(District)
    description = TextField
```

#### Currency System
```python
class Currency(models.Model):
    code = CharField(max_length=3)  # USD, THB, RUB
    symbol = CharField              # $, ฿, ₽
    is_base/is_active = BooleanField
    decimal_places = PositiveSmallIntegerField

class ExchangeRate(models.Model):
    base_currency = ForeignKey(Currency)
    target_currency = ForeignKey(Currency)
    rate = DecimalField(max_digits=12, decimal_places=6)
    date = DateField
    source = CharField
```

### 4.2 Content Management

#### SEO System
```python
class SEOPage(models.Model):  # Static page SEO
    page_name = CharField(unique=True)
    title_ru/en/th = CharField
    description_ru/en/th = TextField
    keywords_ru/en/th = TextField

class SEOTemplate(models.Model):  # Dynamic SEO generation
    template_type = CharField  # property_detail, property_list_type, etc.
    property_type = CharField  # Filter by property type
    deal_type = CharField      # Filter by deal type
    title_template_ru/en/th = CharField
    description_template_ru/en/th = TextField
    keywords_template_ru/en/th = TextField
```

#### Blog System
```python
class BlogCategory(models.Model):
    name = CharField
    slug = SlugField
    color = CharField  # HEX color
    meta_title/description/keywords = CharField/TextField

class BlogPost(models.Model):
    title = CharField
    slug = SlugField
    content = HTMLField  # TinyMCE
    category = ForeignKey(BlogCategory)
    author = ForeignKey(User)
    status = CharField(['draft', 'published', 'archived'])
    
    # Event-specific fields
    event_date = DateTimeField
    event_location/price = CharField
    
    # SEO fields
    meta_title/description/keywords = CharField/TextField
```

### 4.3 Migration History

The system includes comprehensive migration support:
- **Legacy Joomla import**: 15+ migrations handling data structure evolution
- **Translation field additions**: Incremental multi-language support
- **Currency system evolution**: From single to multi-currency
- **SEO template system**: Dynamic meta tag generation
- **Investment features**: Specialized fields for investment properties

## 5. Frontend Technology

### 5.1 Template System

#### Framework
- **Django Templates** with template inheritance
- **Base Template**: Comprehensive layout with navigation, footer
- **Block System**: Content, CSS, JavaScript extension points
- **i18n Integration**: Template-level translation support

#### Styling Framework
- **Tailwind CSS 4.1.11** via CDN
- **Custom Color Palette**:
  - Primary: #474B57 (Dark gray)
  - Secondary: #f8f9fa (Light gray)
  - Accent: #F1B400 (Golden yellow)
  - Tertiary: #616677 (Medium gray)
- **Custom Fonts**: Gilroy font family
- **Font Awesome 6.4.0**: Icon library

#### Key Templates
```
templates/
├── base.html                 # Main layout with navigation
├── core/
│   ├── home.html            # Homepage with featured properties
│   ├── about.html           # Company information
│   ├── contact.html         # Contact form
│   ├── map.html            # Interactive property map
│   └── search.html         # Search results page
├── properties/
│   ├── list.html           # Property listing page
│   ├── detail.html         # Property detail view
│   ├── card.html           # Reusable property card
│   └── favorites.html      # Favorites page
├── blog/
│   ├── blog_list.html      # Blog listing
│   ├── blog_detail.html    # Article detail
│   └── blog_category.html  # Category filtering
└── locations/
    ├── list.html           # District overview
    ├── district_detail.html
    └── location_detail.html
```

### 5.2 Interactive Features

#### JavaScript Libraries
- **jQuery 3.7.0**: DOM manipulation and AJAX
- **Leaflet 1.9.4**: Interactive maps with markers
- **Tailwind CSS**: Responsive styling
- **Native JavaScript**: Modern ES6+ features

#### Dynamic Functionality
- **AJAX Property Loading**: Infinite scroll and filtering
- **Currency Conversion**: Real-time price updates
- **Favorites Management**: Session-based storage
- **Mobile Navigation**: Responsive menu system
- **Image Galleries**: Property photo sliders
- **Form Validation**: Client-side validation
- **Map Interactions**: Property location display

#### Performance Optimization
- **ImageKit Integration**: Automatic thumbnail generation
- **Lazy Loading**: Progressive image loading
- **Caching Strategy**: Template and query optimization
- **CDN Resources**: External library loading
- **Minified Assets**: Production-ready CSS/JS

### 5.3 SEO & Meta Tags

#### Comprehensive SEO Implementation
- **Multi-language URLs**: `/ru/`, `/en/`, `/th/` prefixes
- **Canonical URLs**: Proper canonicalization
- **Hreflang Tags**: Language targeting
- **Open Graph**: Social media optimization
- **Structured Data**: Property schema markup
- **Meta Tag Management**: Template-driven SEO

#### Dynamic SEO Generation
- **SEO Templates**: Configurable meta tag patterns
- **Property Variables**: `{title}`, `{type}`, `{location}`, `{price}`, `{area}`
- **Language-Aware**: Translated templates per language
- **Fallback System**: Auto-generation when custom fields empty
- **Priority System**: Custom → Template → Auto-generated

## 6. API Endpoints & AJAX

### 6.1 Property APIs

#### Core Property Endpoints
```python
# Property listing with AJAX pagination
/property/ajax/list/
    - GET parameters: filters, sorting, pagination
    - Returns: JSON property data
    - Features: Currency conversion, image URLs

# Location hierarchy
/property/ajax/locations/
    - GET parameter: district_id
    - Returns: Available locations in district
    - Used by: Filter dropdowns

# Favorites management
/property/ajax/favorite/
    - POST: Toggle property in favorites
    - Returns: Updated favorites count
    - Session-based storage

# Property inquiries
/property/ajax/inquiry/<property_id>/
    - POST: Submit inquiry form
    - Creates: PropertyInquiry record
    - Integration: AmoCRM support ready
```

#### Search & Filter APIs
- **Dynamic Filtering**: Real-time results without page reload
- **Sorting Options**: Price, area, date with URL state
- **Pagination**: AJAX-powered infinite scroll
- **Currency-Aware**: Prices converted to user's selected currency

#### Interactive Map API
```python
# Map view without pagination
/property/sale/?map_view=true
    - GET parameter: map_view=true
    - Disables pagination via get_paginate_by()
    - Returns: All filtered properties for map display
    - Usage: AJAX loading for map markers
    - Performance: Loads complete dataset for geographic visualization

# Backend implementation
def get_paginate_by(self, queryset):
    if self.request.GET.get('map_view') == 'true':
        return None  # Disable pagination for map
    return self.paginate_by
```

#### Map Features & Implementation
- **Leaflet.js Integration**: OpenStreetMap tiles with custom markers
- **Coordinate Handling**: High-precision GPS data with jitter for overlapping markers  
- **AJAX Property Loading**: Fetches all filtered properties bypassing pagination
- **Currency-Aware Popups**: Displays prices in user's selected currency
- **Fallback Strategy**: Falls back to current page properties if AJAX fails
- **Performance Optimization**: Only loads when map view is activated
- **View Persistence**: localStorage integration for user preference storage

### 6.2 Currency API

#### Exchange Rate Management
```python
/currency/change/
    - POST: Change user's currency preference
    - Updates: Session currency selection
    - Returns: Success confirmation
    - Triggers: Price updates across interface
```

### 6.3 Content APIs

#### Blog System
- **Category Filtering**: Dynamic post loading by category
- **Tag-based Filtering**: Content discovery
- **Reading Time Calculation**: Automatic time estimates
- **View Counting**: Popular content tracking

#### TinyMCE Integration
```python
/blog/tinymce-upload/
    - POST: Image upload for blog editor
    - Returns: Image URL for content insertion
    - Security: Validation and file type checking
```

## 7. Localization Implementation

### 7.1 Translation Architecture

#### Django i18n Framework
- **Language Codes**: `ru` (primary), `en`, `th`
- **URL Patterns**: `i18n_patterns()` with language prefixes
- **Middleware**: `LocaleMiddleware` for language detection
- **Template Tags**: `{% load i18n %}` and `{% trans %}` usage

#### Model Translation System
```python
# django-modeltranslation configuration
TRANSLATION_SETTINGS = {
    'source_language': 'ru',
    'target_languages': ['en', 'th'],
    'chunk_size': 5000
}

# Translated model fields automatically generate:
# title → title_ru, title_en, title_th
# description → description_ru, description_en, description_th
```

### 7.2 Translation Services Integration

#### API Services
- **Yandex Translate API** (cloud REST endpoint)
- **Credentials**: `YANDEX_TRANSLATE_API_KEY`, `YANDEX_TRANSLATE_FOLDER_ID`, опционально `YANDEX_TRANSLATE_ENDPOINT`
- **Fallback Strategy**: Yandex → Manual review

#### Admin Integration
- **Bulk Translation Actions**: Translate selected properties
- **Force Retranslation**: Override existing translations
- **Progress Tracking**: Success/failure reporting
- **Field-Level Control**: Translate only empty fields or force all

#### Translation Workflow
```python
# Automatic translation service
def translate_property(property_obj, force_retranslate=False):
    # Check for existing translations
    # Use configured API service
    # Update translated fields
    # Handle API errors gracefully
```

### 7.3 Content Management

#### Rosetta Interface
- **Admin Panel**: `/rosetta/` translation interface  
- **PO File Management**: Edit translation files directly
- **Progress Tracking**: Translation completion status
- **Multi-user Support**: Translator role management

#### Static Content Translation
- **Template Messages**: `{% trans "Text" %}` usage
- **JavaScript Translations**: Server-rendered translated strings
- **Email Templates**: Multi-language notification support

## 8. Special Features

### 8.1 Investment-Focused Features

#### Investment Property Classification
- **Investment Flag**: `is_for_investment` boolean field
- **Investment Potential**: Dedicated text field for ROI analysis
- **Suitability Analysis**: Usage recommendations
- **Architectural Details**: Style and material specifications
- **Historical Pricing**: Original vs. current pricing for deals

#### Financial Analysis Tools
- **Multi-Currency Pricing**: Complete price storage in USD/THB/RUB
- **Price Per Square Meter**: Automatic calculation across currencies
- **Discount Tracking**: Special offers and urgency flags
- **ROI Information**: Investment potential descriptions

### 8.2 Property Search Intelligence

#### Advanced Filtering System
- **Smart Price Ranges**: Adapts to selected currency
- **Bedroom Logic**: Includes "4+" option for luxury properties
- **Deal Type Intelligence**: Handles sale/rent/both properties
- **Location Hierarchy**: District → Location drilling
- **Feature Combinations**: Multiple amenity selections

#### Search Performance
- **Database Optimization**: Selective related queries
- **Index Strategy**: Optimized for common filter combinations
- **Caching Layer**: Property list caching
- **AJAX Loading**: Smooth user experience

### 8.3 Legacy System Migration

#### Joomla Migration Support
- **Legacy ID Mapping**: `legacy_id` field for reference
- **Agent Migration**: Complete agent profile import
- **Image Migration**: Bulk media file handling
- **URL Preservation**: SEO-friendly redirects
- **Data Validation**: Comprehensive cleanup scripts

#### Migration Tools
```python
# Migration scripts and utilities
migrate_underson_full_dump.py
analyze_locations.py
create_full_amenities.py
final_location_report.py
```

### 8.4 Promotional System

#### Dynamic Banner Management
```python
class PromotionalBanner(models.Model):
    image = ImageField  # 1248x125 recommended
    valid_until = DateField
    button_url = CharField  # Django URL patterns support
    priority = IntegerField
    
    # Multi-language translations
    title/description/discount_text/button_text per language
```

#### Smart URL Handling
- **Django URL Patterns**: Support for named URLs
- **Static URLs**: Direct path support  
- **External Links**: Full URL support
- **Language-Aware**: Automatic language prefix addition

## 9. Admin Interface Features

### 9.1 Enhanced Admin Functionality

#### Property Management
- **List View Customization**: Key fields display
- **Bulk Actions**: Publish/unpublish, feature/unfeature
- **Translation Actions**: Automatic translation workflows
- **Inline Editing**: Images and features management
- **Advanced Filtering**: Property type, district, status filters

#### SEO Management
- **Template System**: Create reusable SEO templates
- **Variable Substitution**: Dynamic content generation
- **Multi-language Support**: Templates per language
- **Priority Management**: Template selection logic

#### Content Administration
- **TinyMCE Integration**: Rich text editing for blog
- **Image Upload**: Direct file management
- **Translation Interface**: Rosetta integration
- **Bulk Operations**: Efficient content management

#### Image Management & Sorting
- **Drag & Drop Upload**: Bulk image upload with preview
- **SortableJS Integration**: Drag & drop reordering of property images
- **Real-time AJAX Saving**: Automatic order updates without page reload
- **Visual Feedback**: Drag states, loading indicators, success notifications
- **Image Previews**: Thumbnail previews with main image indicators
- **Custom Admin URLs**: Dedicated admin AJAX endpoints (`/admin-ajax/`) outside i18n patterns

##### SortableJS Implementation Details
```javascript
// Core functionality in static/admin/js/sortable_images.js
const sortable = new Sortable(imageContainer, {
    handle: '.drag-handle',           // Drag by handle only
    filter: 'tr:not(.has_original)',  // Exclude empty rows
    ghostClass: 'sortable-ghost',     // Visual drag feedback
    animation: 300,                   // Smooth transitions
    onEnd: updateImageOrder          // Save on drop
});
```

##### Admin AJAX Endpoints
```python
# apps/properties/admin_urls.py (outside i18n patterns)
urlpatterns = [
    path('update-image-order/', views.update_image_order, name='admin_update_image_order'),
    path('bulk-upload-images/', views.bulk_upload_images, name='admin_bulk_upload_images'),
]
```

#### Browser Compatibility Fixes
- **Permissions Policy Fix**: Resolves Django admin violations with unload events
- **Modern Browser Support**: Handles deprecated event listeners in RelatedObjectLookups
- **Console Error Suppression**: Eliminates browser policy warnings
- **Automatic Application**: Applied to all admin pages via custom template

##### Permissions Policy Implementation
```python
# apps/core/middleware.py - Custom middleware for admin pages
class PermissionsPolicyMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path.startswith('/admin/'):
            response['Permissions-Policy'] = 'unload=*'
        return response
```

##### JavaScript Compatibility Fix
```javascript
// static/admin/js/fixes/permissions-policy-fix.js
// Replaces deprecated unload events with beforeunload
window.addEventListener = function(type, listener, options) {
    if (type === 'unload') {
        type = 'beforeunload';  // Modern browser compatible
    }
    return originalAddEventListener.call(this, type, listener, options);
};
```

##### Template Integration
```html
<!-- templates/admin/base.html -->
<script src="{% static 'admin/js/fixes/permissions-policy-fix.js' %}"></script>
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"></script>
<script src="{% static 'admin/js/sortable_images.js' %}"></script>
```

### 9.2 Data Import System

#### Legacy Data Handling
```python
# data_import app provides:
- Joomla database import utilities
- Property data validation
- Image migration tools
- Location mapping automation
- Agent profile creation
```

#### Migration Monitoring
- **Progress Tracking**: Import status monitoring
- **Error Handling**: Graceful failure management
- **Data Validation**: Comprehensive checks
- **Rollback Support**: Safe migration practices

## 10. Security & Performance

### 10.1 Security Measures

#### Django Security Features
- **CSRF Protection**: Form security
- **XSS Prevention**: Template auto-escaping
- **SQL Injection Protection**: ORM usage
- **Password Validation**: Strong password requirements
- **Session Security**: Secure session management

#### File Upload Security
- **Image Validation**: Type and size checking
- **Upload Restrictions**: 10MB limit
- **Secure Storage**: Media file isolation
- **Thumbnail Generation**: Automatic processing

### 10.2 Performance Optimization

#### Database Optimization
- **Query Optimization**: `select_related()` and `prefetch_related()`
- **Index Strategy**: Strategic database indexing
- **Connection Pooling**: PostgreSQL optimization
- **Query Analysis**: Performance monitoring

#### Caching Strategy
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
# Production: Redis caching recommended
```

#### Frontend Performance
- **Image Optimization**: ImageKit thumbnails
- **CDN Resources**: External library loading
- **Minification**: Production asset optimization
- **Lazy Loading**: Progressive content loading

### 10.3 Monitoring & Logging

#### Logging Configuration
```python
LOGGING = {
    'handlers': {
        'file': {'filename': 'django.log'},
        'console': {'class': 'logging.StreamHandler'}
    },
    'loggers': {
        'django': {'level': 'INFO'},
        'apps': {'level': 'INFO'}
    }
}
```

## 11. File Structure & Organization

### 11.1 Project Organization
```
undersunestate_django/
├── config/                 # Django settings
│   ├── settings/
│   │   ├── base.py        # Common settings
│   │   ├── development.py # Dev environment
│   │   └── production.py  # Production config
│   ├── urls.py           # Main URL configuration
│   └── wsgi.py/asgi.py   # Server configuration
│
├── apps/                 # Application modules
│   ├── core/            # Site-wide functionality
│   ├── properties/      # Property management
│   ├── locations/       # Geographic data
│   ├── users/          # User management
│   ├── currency/       # Multi-currency system
│   ├── blog/           # Content management
│   └── data_import/    # Migration utilities
│
├── templates/          # HTML templates
│   ├── base.html      # Main layout
│   ├── core/          # Site pages
│   ├── properties/    # Property templates
│   └── blog/          # Blog templates
│
├── static/            # Static assets
│   ├── css/           # Stylesheets
│   ├── js/            # JavaScript files
│   │   └── fixes/     # Browser compatibility fixes
│   └── images/        # Site images
│
├── media/             # User uploads
│   ├── properties/    # Property images
│   └── promotional_banners/
│
├── locale/            # Translation files
│   ├── en/LC_MESSAGES/
│   └── th/LC_MESSAGES/
│
└── logs/              # Application logs
```

### 11.2 Key Configuration Files

#### Environment Management
```python
# .env file structure (not in repository)
SECRET_KEY=django-secret-key
DEBUG=True
DATABASE_URL=postgres://user:pass@localhost/db
GOOGLE_TRANSLATE_API_KEY=api-key
DEEPL_API_KEY=api-key
TRANSLATION_SERVICE=google
```

#### Frontend Build Process
```json
// package.json
{
  "scripts": {
    "build-css": "tailwindcss -i ./static/css/tailwind.css -o ./static/css/tailwind.min.css --watch",
    "build-css-prod": "tailwindcss -i ./static/css/tailwind.css -o ./static/css/tailwind.min.css --minify"
  }
}
```

## 12. Configuration & Deployment

### 12.1 Environment Configuration

#### Development Setup
- **Database**: PostgreSQL with development settings
- **Debug Mode**: Enabled with detailed error pages
- **Static Files**: Development server handling
- **Translation APIs**: Optional for development

#### Production Requirements
- **Database**: Production PostgreSQL with connection pooling
- **Static Files**: CDN or static file server
- **Media Files**: Secure media storage
- **Caching**: Redis for production caching
- **Logging**: File-based logging system
- **SSL**: HTTPS enforcement

### 12.2 Dependencies & Requirements

#### Core Dependencies
```
Django==5.0.6                    # Web framework
Pillow==10.3.0                   # Image processing
django-environ==0.11.2           # Environment management
psycopg2-binary==2.9.9           # PostgreSQL adapter
django-modeltranslation==0.18.11 # Translation system
```

#### Translation & Localization
```
django-rosetta==0.10.0           # Translation interface
requests==2.31.0                 # HTTP client (Yandex Translate API)
```

#### Frontend & Media
```
django-imagekit==5.0.0           # Image processing
django-leaflet==0.30.1           # Map integration
django-crispy-forms==2.1         # Form rendering
crispy-tailwind==1.0.3           # Tailwind integration
django-tinymce==4.0.0            # Rich text editor
```

#### JavaScript Libraries (CDN)
```
SortableJS 1.15.2                # Drag & drop functionality
jQuery 3.7.0                     # DOM manipulation
Leaflet 1.9.4                    # Interactive maps
Font Awesome 6.4.0              # Icon library
```

#### Data Management
```
openpyxl==3.1.2                  # Excel file handling
pandas==2.2.2                    # Data analysis
django-filter==24.2              # Advanced filtering
```

### 12.3 Server Configuration

#### WSGI/ASGI Support
- **Gunicorn**: Production WSGI server
- **Async Support**: Django 5.0 async capabilities
- **Process Management**: Supervisor or systemd
- **Load Balancing**: Nginx reverse proxy

#### Database Configuration
- **PostgreSQL 12+**: Recommended database version
- **Connection Pooling**: Production optimization
- **Backup Strategy**: Regular database backups
- **Migration Management**: Safe deployment practices

### 12.4 VPS Production Deployment

#### Static Files & CDN Setup
For production deployment on VPS, ensure all JavaScript libraries are properly served:

```bash
# Create static files directory structure
mkdir -p /var/www/undersunestate/static/js/vendor/
mkdir -p /var/www/undersunestate/static/css/vendor/

# Download SortableJS library
wget https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js -O /var/www/undersunestate/static/js/vendor/sortable.min.js

# Download other dependencies
wget https://code.jquery.com/jquery-3.7.0.min.js -O /var/www/undersunestate/static/js/vendor/jquery.min.js
wget https://unpkg.com/leaflet@1.9.4/dist/leaflet.js -O /var/www/undersunestate/static/js/vendor/leaflet.min.js
wget https://unpkg.com/leaflet@1.9.4/dist/leaflet.css -O /var/www/undersunestate/static/css/vendor/leaflet.min.css

# Set proper permissions
chown -R www-data:www-data /var/www/undersunestate/static/
chmod -R 644 /var/www/undersunestate/static/
```

#### Admin Static Files Configuration
Update your Django admin base template to load SortableJS:

```html
<!-- In admin/change_form.html or base template -->
{% load static %}
<script src="{% static 'js/vendor/sortable.min.js' %}"></script>
<script src="{% static 'admin/js/sortable_images.js' %}"></script>
<link rel="stylesheet" href="{% static 'admin/css/sortable_images.css' %}">
```

#### Nginx Configuration
```nginx
# Serve static files efficiently
location /static/ {
    alias /var/www/undersunestate/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
    gzip on;
    gzip_types text/css application/javascript;
}

# Handle admin AJAX endpoints
location /admin-ajax/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

#### Production Settings
```python
# production.py settings
STATIC_ROOT = '/var/www/undersunestate/static/'
MEDIA_ROOT = '/var/www/undersunestate/media/'

# CDN fallback URLs
SORTABLE_JS_URL = 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js'
JQUERY_URL = 'https://code.jquery.com/jquery-3.7.0.min.js'

# Security for admin AJAX
CSRF_TRUSTED_ORIGINS = ['https://your-domain.com']
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']
```

#### Deployment Checklist
- [ ] Download and verify all JavaScript libraries
- [ ] Configure nginx for static file serving
- [ ] Set up proper file permissions
- [ ] Configure CSRF trusted origins
- [ ] Test admin drag & drop functionality
- [ ] Verify AJAX endpoints are accessible
- [ ] Set up SSL certificates
- [ ] Configure media file permissions

This comprehensive real estate platform demonstrates modern Django development practices with international market focus, robust multi-language support, and investment-oriented features specifically tailored for the Southeast Asian property market.
- to memorize
