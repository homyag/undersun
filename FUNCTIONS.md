# Undersun Estate - Function Documentation

This document provides a comprehensive reference for all functions across the Undersun Estate Django project, including Python functions and JavaScript functions used in the real estate platform.

## Table of Contents

- [Python Functions](#python-functions)
  - [Core App](#core-app)
  - [Properties App](#properties-app)
  - [Currency App](#currency-app)
  - [Locations App](#locations-app)
  - [Blog App](#blog-app)
  - [Users App](#users-app)
  - [Management Commands](#management-commands)
- [JavaScript Functions](#javascript-functions)
  - [Main JavaScript Functions](#main-javascript-functions)
  - [Admin JavaScript Functions](#admin-javascript-functions)
  - [Template JavaScript Functions](#template-javascript-functions)
- [Context Processors](#context-processors)
- [Translation Utilities](#translation-utilities)

---

## Python Functions

### Core App

#### Models (`apps/core/models.py`)

**SEOPage Model**
- `get_title(language_code='ru')` - Get page title for specified language with fallback to Russian
  - **Parameters**: `language_code` (str) - Language code (ru, en, th)
  - **Returns**: str - Page title
  - **Usage**: SEO meta tag generation

- `get_description(language_code='ru')` - Get page description for specified language
  - **Parameters**: `language_code` (str) - Language code
  - **Returns**: str - Page description
  - **Usage**: SEO meta description generation

- `get_keywords(language_code='ru')` - Get page keywords for specified language
  - **Parameters**: `language_code` (str) - Language code
  - **Returns**: str - Comma-separated keywords
  - **Usage**: SEO meta keywords generation

**PromotionalBanner Model**
- `get_translation(language_code='ru')` - Get banner translation for specified language
  - **Parameters**: `language_code` (str) - Language code
  - **Returns**: PromotionalBannerTranslation or None
  - **Usage**: Multilingual banner content display

- `get_active_banner()` - Class method to get currently active banner
  - **Parameters**: None
  - **Returns**: PromotionalBanner or None
  - **Usage**: Homepage banner display
  - **Side effects**: Filters by date validity and priority

- `get_language_aware_url(language_code=None)` - Get localized button URL
  - **Parameters**: `language_code` (str, optional) - Target language
  - **Returns**: str or None - Localized URL
  - **Usage**: Banner button linking with language support
  - **Dependencies**: Django URL reversing, current language detection

- `is_valid()` - Check if banner is currently valid
  - **Parameters**: None
  - **Returns**: bool - Banner validity status
  - **Usage**: Banner display validation

**SEOTemplate Model**
- `get_template(field_type, language_code='ru')` - Get template for field and language
  - **Parameters**: `field_type` (str), `language_code` (str)
  - **Returns**: str - Template text
  - **Usage**: SEO content generation

- `render_template(template_text, property_obj, language_code='ru')` - Render template with property data
  - **Parameters**: `template_text` (str), `property_obj` (Property), `language_code` (str)
  - **Returns**: str - Rendered content
  - **Usage**: Dynamic SEO generation
  - **Dependencies**: Property model attributes, regex processing

- `generate_seo_for_property(property_obj, language_code='ru')` - Generate complete SEO data
  - **Parameters**: `property_obj` (Property), `language_code` (str)
  - **Returns**: dict - SEO data (title, description, keywords)
  - **Usage**: Automated SEO creation for properties

**Service Model**
- `get_absolute_url()` - Get service page URL
  - **Parameters**: None
  - **Returns**: str - Service detail URL
  - **Usage**: Service page navigation

- `get_meta_title()` - Get SEO title or fallback to main title
  - **Parameters**: None
  - **Returns**: str - Page title for SEO
  - **Usage**: Meta tag generation

- `get_meta_description()` - Get SEO description or fallback
  - **Parameters**: None
  - **Returns**: str - Meta description
  - **Usage**: Meta tag generation

- `get_menu_services()` - Class method to get services for menu display
  - **Parameters**: None
  - **Returns**: QuerySet - Active menu services
  - **Usage**: Navigation menu population

#### Views (`apps/core/views.py`)

**Utility Functions**
- `serialize_properties_for_js(properties)` - Convert property queryset to JavaScript-ready JSON
  - **Parameters**: `properties` (QuerySet) - Property objects
  - **Returns**: str - JSON string
  - **Usage**: Frontend property data transfer
  - **Side effects**: Price formatting, currency conversion

**HomeView Class**
- `get_context_data(**kwargs)` - Prepare homepage context data
  - **Parameters**: `**kwargs` - View keyword arguments
  - **Returns**: dict - Template context
  - **Usage**: Homepage rendering
  - **Dependencies**: Property filtering, serialization, statistics calculation

**SearchView Class**
- `get_context_data(**kwargs)` - Prepare search results context
  - **Parameters**: `**kwargs` - View keyword arguments
  - **Returns**: dict - Search results and filters
  - **Usage**: Search functionality
  - **Dependencies**: Property filtering, pagination, currency services

- `apply_filters(queryset)` - Apply search filters to property queryset (method of PropertyListView)
  - **Parameters**: `queryset` (QuerySet) - Base property queryset
  - **Returns**: QuerySet - Filtered properties
  - **Usage**: Property search and filtering
  - **Side effects**: Complex query building with multiple filter types

#### Services (`apps/core/services.py`)

**TranslationService Class**
- `translate_text(text, target_language, preserve_html=False)` - Translate text using configured API
  - **Parameters**: `text` (str), `target_language` (str), `preserve_html` (bool)
  - **Returns**: str or None - Translated text
  - **Usage**: Automated content translation
  - **Dependencies**: Google Translate API or DeepL API, HTML processing

- `translate_model_fields(instance, fields)` - Translate multiple model fields
  - **Parameters**: `instance` (Model), `fields` (list) - Field names to translate
  - **Returns**: dict - Translation results by field and language
  - **Usage**: Bulk model translation
  - **Side effects**: API calls, rate limiting

- `apply_translations_to_model(instance, translations)` - Apply translations to model instance
  - **Parameters**: `instance` (Model), `translations` (dict)
  - **Returns**: None
  - **Usage**: Save translated content to model
  - **Side effects**: Model field updates

- `is_configured()` - Check if translation service is properly configured
  - **Parameters**: None
  - **Returns**: bool - Configuration status
  - **Usage**: Feature availability check

#### Context Processors (`apps/core/context_processors.py`)

- `site_context(request)` - Global site context for all templates
  - **Parameters**: `request` (HttpRequest)
  - **Returns**: dict - Global template variables
  - **Usage**: Template rendering across all pages
  - **Dependencies**: Property types, districts, services, language detection

- `seo_context(request)` - SEO context based on current URL
  - **Parameters**: `request` (HttpRequest)
  - **Returns**: dict - SEO meta tags data
  - **Usage**: Dynamic SEO generation
  - **Dependencies**: URL pattern matching, SEO templates, Property model

### Properties App

#### Models (`apps/properties/models.py`)

**Property Model**
- `get_absolute_url()` - Get property detail page URL
  - **Parameters**: None
  - **Returns**: str - Property detail URL
  - **Usage**: Property page navigation

- `main_image` (property) - Get main property image
  - **Parameters**: None
  - **Returns**: PropertyImage or None
  - **Usage**: Property display in listings and details

- `price_display` (property) - Get formatted price for display
  - **Parameters**: None
  - **Returns**: str - Formatted price with currency
  - **Usage**: Property price display
  - **Side effects**: Currency formatting, discount calculation

- `get_price_per_sqm_in_currency(currency_code, deal_type='sale')` - Calculate price per square meter
  - **Parameters**: `currency_code` (str), `deal_type` (str)
  - **Returns**: float or None - Price per sqm
  - **Usage**: Property value comparison
  - **Dependencies**: Currency conversion, area validation

- `get_formatted_price_per_sqm(currency_code='THB', deal_type='sale')` - Get formatted price per sqm
  - **Parameters**: `currency_code` (str), `deal_type` (str) 
  - **Returns**: str or None - Formatted price per sqm with currency
  - **Usage**: Property listings display

- `get_price_in_currency(currency_code, deal_type='sale')` - Convert price to specified currency
  - **Parameters**: `currency_code` (str), `deal_type` (str)
  - **Returns**: Decimal or None - Price in target currency
  - **Usage**: Multi-currency price display
  - **Dependencies**: Exchange rate conversion, stored price fields

- `get_formatted_price(currency_code='THB', deal_type='sale')` - Get fully formatted price
  - **Parameters**: `currency_code` (str), `deal_type` (str)
  - **Returns**: str - Formatted price with currency symbol
  - **Usage**: Frontend price display

- `has_custom_seo(language_code='ru')` - Check if property has custom SEO
  - **Parameters**: `language_code` (str)
  - **Returns**: bool - Custom SEO availability
  - **Usage**: SEO generation decision

- `get_custom_seo(language_code='ru')` - Get custom SEO data
  - **Parameters**: `language_code` (str)
  - **Returns**: dict - Custom SEO fields
  - **Usage**: SEO meta tag generation

- `get_seo_template()` - Find appropriate SEO template for property
  - **Parameters**: None
  - **Returns**: SEOTemplate or None
  - **Usage**: Automated SEO generation
  - **Dependencies**: Property type and deal type matching

#### Views (`apps/properties/views.py`)

**PropertyListView Class**
- `get_queryset()` - Get filtered property queryset
  - **Parameters**: None
  - **Returns**: QuerySet - Filtered properties
  - **Usage**: Property listing pages
  - **Dependencies**: Filter application, sorting, database optimization

- `apply_filters(queryset)` - Apply search and filter parameters
  - **Parameters**: `queryset` (QuerySet)
  - **Returns**: QuerySet - Filtered properties
  - **Usage**: Property search functionality
  - **Side effects**: Complex query building, price filtering, text search

- `get_context_data(**kwargs)` - Prepare property listing context
  - **Parameters**: `**kwargs`
  - **Returns**: dict - Template context with filters and results
  - **Usage**: Property listing template rendering

#### Services (`apps/properties/services.py`)

- `translate_property(property_obj, target_languages=None, force_retranslate=False)` - Translate property content
  - **Parameters**: `property_obj` (Property), `target_languages` (list), `force_retranslate` (bool)
  - **Returns**: None
  - **Usage**: Multilingual content management
  - **Side effects**: API calls, model updates, field translation
  - **Dependencies**: Translation service configuration

- `translate_property_type(property_type_obj, target_languages=None, force_retranslate=False)` - Translate property type
  - **Parameters**: `property_type_obj` (PropertyType), `target_languages` (list), `force_retranslate` (bool)
  - **Returns**: None
  - **Usage**: Property type localization
  - **Side effects**: Model updates, translation API usage

### Currency App

#### Models (`apps/currency/models.py`)

**Currency Model**
- `save(*args, **kwargs)` - Override to ensure single base currency
  - **Parameters**: Standard save parameters
  - **Returns**: None
  - **Usage**: Currency management
  - **Side effects**: Ensures only one base currency exists

**ExchangeRate Model**
- `get_latest_rate(base_currency, target_currency)` - Class method to get latest exchange rate
  - **Parameters**: `base_currency` (Currency), `target_currency` (Currency)
  - **Returns**: Decimal or None - Latest exchange rate
  - **Usage**: Currency conversion calculations
  - **Dependencies**: Database queries, reverse rate calculation

- `convert_amount(amount, from_currency, to_currency)` - Class method to convert amounts
  - **Parameters**: `amount` (Decimal), `from_currency` (Currency), `to_currency` (Currency)
  - **Returns**: Decimal or None - Converted amount
  - **Usage**: Price conversion across currencies
  - **Dependencies**: Exchange rate lookup, mathematical conversion

#### Services (`apps/currency/services.py`)

**CurrencyService Class**
- `get_currency_for_language(language_code)` - Static method to get default currency for language
  - **Parameters**: `language_code` (str)
  - **Returns**: Currency or None
  - **Usage**: Language-specific currency display
  - **Dependencies**: CurrencyPreference model, fallback logic

- `get_active_currencies()` - Static method to get all active currencies
  - **Parameters**: None
  - **Returns**: QuerySet - Active currencies
  - **Usage**: Currency selector population

- `get_currency_by_code(code)` - Static method to get currency by code
  - **Parameters**: `code` (str) - Currency code (USD, EUR, etc.)
  - **Returns**: Currency or None
  - **Usage**: Currency lookup and validation

- `convert_price(amount, from_currency_code, to_currency_code)` - Convert price between currencies
  - **Parameters**: `amount` (Decimal), `from_currency_code` (str), `to_currency_code` (str)
  - **Returns**: Decimal or None - Converted price
  - **Usage**: Real-time price conversion
  - **Dependencies**: Exchange rate service, currency validation

- `format_price(amount, currency_code)` - Format price with currency symbol
  - **Parameters**: `amount` (Decimal), `currency_code` (str)
  - **Returns**: str - Formatted price string
  - **Usage**: Price display formatting

- `get_latest_rates_summary()` - Get summary of all current exchange rates
  - **Parameters**: None
  - **Returns**: dict - Rate summary by currency code
  - **Usage**: Admin dashboard, rate overview

### Locations App

#### Models (`apps/locations/models.py`)

**District Model**
- `get_absolute_url()` - Get district detail page URL
  - **Parameters**: None
  - **Returns**: str - District detail URL
  - **Usage**: District page navigation

**Location Model**
- `get_absolute_url()` - Get location detail page URL
  - **Parameters**: None
  - **Returns**: str - Location detail URL
  - **Usage**: Location page navigation
  - **Dependencies**: District slug for URL building

### Blog App

#### Models (`apps/blog/models.py`)

**BlogCategory Model**
- `get_absolute_url()` - Get category page URL
  - **Parameters**: None
  - **Returns**: str - Category page URL
  - **Usage**: Blog category navigation

### Management Commands

#### Currency Commands

**setup_currencies Command** (`apps/currency/management/commands/setup_currencies.py`)
- `handle(*args, **options)` - Set up initial currencies and language preferences
  - **Parameters**: Command line arguments and options
  - **Returns**: None
  - **Usage**: Initial project setup
  - **Side effects**: Creates/updates Currency and CurrencyPreference records

**update_exchange_rates Command** (`apps/currency/management/commands/update_exchange_rates.py`)
- `handle(*args, **options)` - Update exchange rates from external API
  - **Parameters**: Command arguments including base currency and API URL
  - **Returns**: None
  - **Usage**: Scheduled exchange rate updates
  - **Side effects**: API calls, database updates, property price updates
  - **Dependencies**: External API (exchangerate-api.com), internet connection

- `add_arguments(parser)` - Define command arguments
  - **Parameters**: `parser` (ArgumentParser)
  - **Returns**: None
  - **Usage**: Command line argument parsing

- `update_property_prices()` - Update property prices based on new exchange rates
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Automatic price synchronization
  - **Side effects**: Bulk property model updates

---

## JavaScript Functions

### Main JavaScript Functions (`static/js/main.js`)

#### Core Functions

- `getCookie(name)` - Get CSRF token from cookies
  - **Parameters**: `name` (string) - Cookie name
  - **Returns**: string - Cookie value
  - **Usage**: CSRF token retrieval for AJAX requests
  - **Dependencies**: Browser cookie API

#### Carousel Functions

- `nextSlide()` - Advance hero carousel to next slide
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Automatic hero image rotation
  - **Side effects**: DOM class manipulation, slide transitions

#### Favorites Management

- `getFavorites()` - Get favorites list from localStorage
  - **Parameters**: None
  - **Returns**: Array - Property IDs in favorites
  - **Usage**: Local favorites management

- `saveFavorites(favorites)` - Save favorites to localStorage
  - **Parameters**: `favorites` (Array) - Property IDs
  - **Returns**: None
  - **Usage**: Persist favorites across sessions
  - **Side effects**: localStorage updates

- `isFavorite(propertyId)` - Check if property is in favorites
  - **Parameters**: `propertyId` (number) - Property ID
  - **Returns**: boolean - Favorite status
  - **Usage**: UI state management

- `toggleFavorite(propertyId, icon)` - Add/remove property from favorites
  - **Parameters**: `propertyId` (number), `icon` (jQuery object, optional)
  - **Returns**: boolean - New favorite status
  - **Usage**: Favorite button interactions
  - **Side effects**: localStorage updates, UI updates, notifications

- `updateFavoritesCounter()` - Update favorites count display
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Navigation badge updates
  - **Side effects**: DOM text updates, visibility changes

- `initializeFavorites()` - Initialize favorite button states on page load
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Page initialization
  - **Side effects**: Icon state updates based on localStorage

#### Property Filtering and AJAX

- `updatePropertyFilters()` - Update property listings via AJAX
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Dynamic property filtering without page reload
  - **Side effects**: AJAX requests, DOM updates, URL history updates
  - **Dependencies**: Server-side filtering API

- `updatePropertiesGrid(properties)` - Update property grid with new data
  - **Parameters**: `properties` (Array) - Property data objects
  - **Returns**: None
  - **Usage**: Dynamic content updates
  - **Side effects**: DOM replacement, event handler reinitialization

- `createPropertyCard(property)` - Generate HTML for property card
  - **Parameters**: `property` (Object) - Property data
  - **Returns**: string - HTML markup for property card
  - **Usage**: Dynamic property card creation
  - **Dependencies**: Property data structure, favorites system

- `updatePagination(pagination)` - Update pagination controls
  - **Parameters**: `pagination` (Object) - Pagination data
  - **Returns**: None
  - **Usage**: AJAX pagination updates
  - **Side effects**: DOM updates, event handler attachment

- `updateResultsCount(count)` - Update search results counter
  - **Parameters**: `count` (number) - Number of results
  - **Returns**: None
  - **Usage**: Search feedback display
  - **Side effects**: DOM text updates

#### Gallery and Image Functions

- `openImageGallery(images, startIndex)` - Open property image gallery modal
  - **Parameters**: `images` (Array), `startIndex` (number, default 0)
  - **Returns**: None
  - **Usage**: Property image viewing
  - **Side effects**: Modal creation, keyboard event binding, DOM manipulation

#### Map Functions

- `initPropertyMap()` - Initialize property map with Leaflet
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Property map display
  - **Dependencies**: Leaflet library, property coordinates
  - **Side effects**: Map rendering, marker clustering

- `filterMapMarkers()` - Filter map markers by property type
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Map filtering functionality
  - **Side effects**: Marker visibility updates

#### Search Functions

- `searchProperties(query)` - Perform property search with autocomplete
  - **Parameters**: `query` (string) - Search query
  - **Returns**: None
  - **Usage**: Search suggestions display
  - **Side effects**: AJAX requests, dropdown updates
  - **Dependencies**: Search API endpoint

#### Utility Functions

- `showNotification(message, type)` - Display toast notification
  - **Parameters**: `message` (string), `type` (string, default 'info')
  - **Returns**: None
  - **Usage**: User feedback display
  - **Side effects**: DOM insertion, automatic removal after timeout

- `formatPrice(price)` - Format price for display
  - **Parameters**: `price` (number) - Raw price value
  - **Returns**: string - Formatted price with currency symbol
  - **Usage**: Price display formatting

- `formatArea(area)` - Format area for display
  - **Parameters**: `area` (number) - Area in square meters
  - **Returns**: string - Formatted area with units
  - **Usage**: Property area display

- `validateForm(form)` - Validate form fields
  - **Parameters**: `form` (jQuery object) - Form element
  - **Returns**: boolean - Validation result
  - **Usage**: Client-side form validation
  - **Side effects**: CSS class updates, validation state changes

### Admin JavaScript Functions (`static/admin/js/seo_admin.js`)

#### SEO Administration

- `addCharacterCounter(element, maxLength, warningLength)` - Add character counter to SEO fields
  - **Parameters**: `element` (DOM element), `maxLength` (number), `warningLength` (number)
  - **Returns**: None
  - **Usage**: SEO field length monitoring
  - **Side effects**: DOM insertion, event listener attachment, real-time counter updates

### Template JavaScript Functions (`templates/base.html`)

#### Navigation Functions

- `toggleMobileSubmenu(submenuId)` - Toggle mobile menu submenu visibility
  - **Parameters**: `submenuId` (string) - ID of submenu to toggle
  - **Returns**: None
  - **Usage**: Mobile navigation interaction
  - **Side effects**: CSS class toggles, arrow rotation

- `toggleMobileSearch()` - Toggle mobile search form visibility
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Mobile search interface
  - **Side effects**: CSS class toggles

#### Currency Switching

- Mobile currency selector event handlers - Handle currency switching in mobile menu
  - **Parameters**: Event objects
  - **Returns**: None
  - **Usage**: Currency preference updates
  - **Side effects**: AJAX requests, page reload or price updates, session updates
  - **Dependencies**: Currency change API endpoint

#### Scroll Behavior

- Scroll event handler - Manage navigation bar behavior on scroll
  - **Parameters**: Scroll event
  - **Returns**: None
  - **Usage**: Dynamic navigation positioning
  - **Side effects**: CSS transform updates, responsive behavior

---

## Context Processors

### Site Context (`apps/core/context_processors.py`)

- `site_context(request)` - Provides global template variables
  - **Available in all templates**: property_types, districts, current_language, menu_services
  - **Usage**: Navigation menus, filters, global site data

- `seo_context(request)` - Provides SEO meta tags for pages
  - **Available in all templates**: page_title, page_description, page_keywords
  - **Usage**: Dynamic SEO meta tag generation based on URL patterns

---

## Translation Utilities

### Translation Service (`apps/core/services.py`)

The TranslationService class provides automated content translation capabilities using Google Translate or DeepL APIs.

**Key Methods:**
- Content translation with HTML preservation
- Bulk model field translation
- API rate limiting and error handling
- Fallback service selection

**Usage Examples:**
- Property description translation
- SEO content localization  
- Admin interface content translation

---

## Function Index

### By Functionality

**SEO and Meta Tags:**
- `get_title()`, `get_description()`, `get_keywords()` - SEO page content
- `get_meta_title()`, `get_meta_description()` - Service page SEO
- `seo_context()` - Dynamic SEO generation
- `render_template()`, `generate_seo_for_property()` - Automated SEO

**Currency and Pricing:**
- `get_price_in_currency()`, `convert_price()` - Currency conversion
- `format_price()`, `get_formatted_price()` - Price formatting
- `get_latest_rate()`, `convert_amount()` - Exchange rates
- `update_exchange_rates()` - Rate synchronization

**Property Management:**
- `apply_filters()`, `get_queryset()` - Property filtering
- `serialize_properties_for_js()` - Frontend data transfer
- `get_price_per_sqm_in_currency()` - Property metrics
- `translate_property()` - Content localization

**User Interface:**
- `toggleFavorite()`, `updateFavoritesCounter()` - Favorites system
- `showNotification()` - User feedback
- `updatePropertyFilters()` - Dynamic filtering
- `initPropertyMap()` - Map functionality

**Administrative:**
- `setup_currencies()`, `update_exchange_rates()` - System setup
- `addCharacterCounter()` - Admin UI enhancements
- `translate_text()` - Content translation

This documentation serves as a comprehensive reference for all functions in the Undersun Estate platform, providing developers with detailed information about each function's purpose, parameters, and usage context.