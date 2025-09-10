// Featured Properties Carousel
(function () {

    function initFeaturedProperties() {
        
        // Check if data is available
        if (!window.homePageData || !window.homePageData.featuredProperties) {
            console.error('Featured properties data not found!');
            console.error('window.homePageData:', window.homePageData);
            return;
        }

        let currentPropertyType = 'villa';

        // Data from Django context (injected via json_script)
        const featuredProperties = window.homePageData.featuredProperties;

        // Switch property type
        window.switchPropertyType = function (type) {
            currentPropertyType = type;

            // Update tab buttons
            document.querySelectorAll('.property-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            const activeTab = document.getElementById('tab-' + type);
            if (activeTab) {
                activeTab.classList.add('active');
            }

            // Render properties for selected type
            renderProperties(featuredProperties[type] || []);

            // Update all prices to current header currency after rendering new properties
            setTimeout(() => {
                updateAllPricesToHeaderCurrency();
            }, 100);
        }

        // Carousel state
        let currentIndex = 0;
        let isTransitioning = false;
        let autoplayInterval;

        // Render properties with consultation forms
        function renderProperties(properties) {
            const container = document.getElementById('properties-carousel');

            if (!container) {
                console.error('properties-carousel container not found!');
                return;
            }

            // Reset carousel state
            currentIndex = 0;

            let items = [];

            properties.forEach((property, index) => {
                // Add consultation form every 4th position (after 3rd, 7th, 11th, etc.)
                if ((index + 1) % 4 === 0) {
                    items.push(createConsultationCard());
                }

                items.push(createPropertyCard(property));
            });

            // Create infinite carousel by duplicating items
            const allItems = [...items, ...items, ...items]; // Triple the items for smooth infinite scroll

            let html = '';
            allItems.forEach(item => {
                html += `<div class="carousel-item flex-shrink-0" style="width: 100%; max-width: 350px; height: 450px; min-width: 280px;">${item}</div>`;
            });

            container.innerHTML = html;

            // Start from the middle set to allow backward scrolling
            currentIndex = items.length;
            updateCarouselPosition(false);

            // Initialize carousel controls
            initializeCarouselControls();

            // Update all prices to current header currency
            updateAllPricesToHeaderCurrency();

            // Reinitialize property cards
            if (typeof window.initPropertyCards === 'function') {
                window.initPropertyCards();
            } else if (typeof initPropertyCards === 'function') {
                initPropertyCards();
            }

            // Force update price per sqm after everything else
            setTimeout(() => {
                const headerCurrency = getHeaderCurrency();
                const currentData = featuredProperties[currentPropertyType] || [];

                currentData.forEach(property => {
                    if (property.area > 0 && property.deal_type === 'sale') {
                        updatePricePerSqmFromData(property, headerCurrency.code);
                    }
                });
            }, 500);

            // Initialize currency dropdowns after everything is rendered
            setTimeout(() => {
                initializeCurrencyDropdowns();
            }, 600);
        }

        // Update carousel position
        function updateCarouselPosition(animate = true) {
            const container = document.getElementById('properties-carousel');
            if (!container) return;

            const carouselItems = container.querySelectorAll('.carousel-item');
            if (carouselItems.length === 0) return;

            // Calculate actual slide width based on first item
            const firstItem = carouselItems[0];
            const itemRect = firstItem.getBoundingClientRect();

            // Calculate slide width based on screen size
            const isMobile = window.innerWidth < 768;
            let slideWidth;

            if (isMobile) {
                // Mobile: use almost full viewport width minus padding
                slideWidth = Math.min(window.innerWidth - 48, 350); // 48px for padding
            } else {
                // Desktop: fixed width plus gap
                slideWidth = itemRect.width + 24; // 24px gap
            }

            const translateX = -(currentIndex * slideWidth);

            if (animate) {
                container.style.transition = 'transform 1s ease-in-out';
            } else {
                container.style.transition = 'none';
            }

            container.style.transform = `translateX(${translateX}px)`;
        }

        // Move to next slide
        function nextSlide() {
            if (isTransitioning) return;

            isTransitioning = true;
            currentIndex++;
            updateCarouselPosition();

            setTimeout(() => {
                checkInfiniteScroll();
                isTransitioning = false;
            }, 1000);
        }

        // Move to previous slide
        function prevSlide() {
            if (isTransitioning) return;

            isTransitioning = true;
            currentIndex--;
            updateCarouselPosition();

            setTimeout(() => {
                checkInfiniteScroll();
                isTransitioning = false;
            }, 1000);
        }

        // Check and handle infinite scroll
        function checkInfiniteScroll() {
            const container = document.getElementById('properties-carousel');
            if (!container) return;

            const items = container.querySelectorAll('.carousel-item');
            const totalItems = items.length;
            const itemsPerSet = totalItems / 3;

            // If we're at the end of the last set, jump to the beginning of the middle set
            if (currentIndex >= itemsPerSet * 2) {
                currentIndex = itemsPerSet;
                updateCarouselPosition(false);
            }
            // If we're at the beginning of the first set, jump to the end of the middle set
            else if (currentIndex < itemsPerSet) {
                currentIndex = itemsPerSet * 2 - 1;
                updateCarouselPosition(false);
            }
        }

        // Initialize carousel controls
        function initializeCarouselControls() {
            const prevBtn = document.getElementById('featured-prev');
            const nextBtn = document.getElementById('featured-next');

            if (prevBtn) {
                prevBtn.onclick = () => {
                    prevSlide();
                    resetAutoplay();
                };
            }

            if (nextBtn) {
                nextBtn.onclick = () => {
                    nextSlide();
                    resetAutoplay();
                };
            }

            startAutoplay();
        }

        // Autoplay functions
        function startAutoplay() {
            autoplayInterval = setInterval(() => {
                nextSlide();
            }, 8000); // Slower autoplay - every 8 seconds
        }

        function resetAutoplay() {
            clearInterval(autoplayInterval);
            startAutoplay();
        }

        // Update all prices to current header currency
        function updateAllPricesToHeaderCurrency() {
            // Get current currency from session/header
            const headerCurrency = getHeaderCurrency();

            // Find all price elements in the carousel
            const carouselContainer = document.getElementById('properties-carousel');
            if (!carouselContainer) return;

            carouselContainer.querySelectorAll('[class*="card-price-"]').forEach(priceElement => {
                const propertyId = priceElement.dataset.propertyId;
                const dealType = priceElement.dataset.dealType;

                if (propertyId) {
                    updatePropertyPrice(propertyId, headerCurrency.code, headerCurrency.symbol, dealType, priceElement);
                }
            });
        }

        // Make the function globally available
        window.updateAllPricesToHeaderCurrency = updateAllPricesToHeaderCurrency;

        // Get header currency from HTML or session
        function getHeaderCurrency() {
            // Try to get from currency switcher button in header
            const headerCurrencyElement = document.getElementById('currency-menu-button');
            if (headerCurrencyElement) {
                // Extract currency info from button text (format: "₽ RUB" or "$ USD")
                const buttonText = headerCurrencyElement.textContent?.trim() || '';
                
                // Remove any extra whitespace and split
                const cleanText = buttonText.replace(/\s+/g, ' ').trim();
                const parts = cleanText.split(' ');

                // Handle different formats: "₽ RUB", "$USD" or "$ USD"
                if (parts.length >= 2) {
                    const symbol = parts[0];
                    let code = parts[1];
                    
                    // Clean up code (remove any non-letter characters)
                    code = code.replace(/[^A-Z]/g, '');
                    
                    if (code.length === 3) {
                        return {code, symbol};
                    }
                } else if (parts.length === 1) {
                    // Handle format like "$USD" without space
                    const text = parts[0];
                    const match = text.match(/^([^A-Z]+)([A-Z]{3})$/);
                    if (match) {
                        return {code: match[2], symbol: match[1]};
                    }
                }
            }

            // Fallback: try to get from mobile currency button
            const mobileButton = document.querySelector('[onclick="toggleMobileSubmenu(\'currency-submenu\')"] span');
            if (mobileButton) {
                const buttonText = mobileButton.textContent || '';
                // Format: "Валюта (₽RUB)" or "Currency ($USD)"
                const match = buttonText.match(/\(([^\w])(\w+)\)/);
                if (match) {
                    return {code: match[2], symbol: match[1]};
                }
            }

            // Try to get from active currency option in the menu
            const activeCurrencyOption = document.querySelector('.currency-option.bg-gray-100, .currency-option[class*="font-semibold"]');
            if (activeCurrencyOption) {
                const code = activeCurrencyOption.dataset.currency;
                const symbol = activeCurrencyOption.dataset.symbol;
                if (code && symbol) {
                    return {code, symbol};
                }
            }

            // Default fallback to THB (base currency)
            return {code: 'THB', symbol: '฿'};
        }

        // Update single property price
        function updatePropertyPrice(propertyId, toCurrency, symbol, dealType, priceElement) {
            if (!priceElement) {
                priceElement = document.querySelector(`.card-price-${propertyId}`);
            }
            if (!priceElement) return;

            // Find property data
            const currentData = featuredProperties[currentPropertyType] || [];
            const propertyData = currentData.find(p => p.id == propertyId);

            if (!propertyData) return;

            // Get price per sqm element
            const pricePerSqmElement = document.querySelector(`.card-price-per-sqm-${propertyId}`);

            let basePrice = 0;
            let fromCurrency = 'THB';

            // Determine base price and currency (THB is base currency, but check all available)
            if (dealType === 'rent') {
                if (propertyData.price_rent_thb) {
                    basePrice = propertyData.price_rent_thb;
                    fromCurrency = 'THB';
                } else if (propertyData.price_rent_rub) {
                    basePrice = propertyData.price_rent_rub;
                    fromCurrency = 'RUB';
                } else if (propertyData.price_rent_usd) {
                    basePrice = propertyData.price_rent_usd;
                    fromCurrency = 'USD';
                }
            } else {
                if (propertyData.price_sale_thb) {
                    basePrice = propertyData.price_sale_thb;
                    fromCurrency = 'THB';
                } else if (propertyData.price_sale_rub) {
                    basePrice = propertyData.price_sale_rub;
                    fromCurrency = 'RUB';
                } else if (propertyData.price_sale_usd) {
                    basePrice = propertyData.price_sale_usd;
                    fromCurrency = 'USD';
                }
            }

            if (!basePrice) {
                priceElement.innerHTML = 'Цена по запросу';
                if (pricePerSqmElement) {
                    pricePerSqmElement.innerHTML = '';
                }
                return;
            }

            if (fromCurrency === toCurrency) {
                const displayPrice = dealType === 'rent' ?
                    `${symbol}${formatPrice(basePrice)}/мес` :
                    `${symbol}${formatPrice(basePrice)}`;
                priceElement.innerHTML = displayPrice;

                // Update price per sqm for sale properties
                updatePricePerSqmFromData(propertyData, toCurrency, pricePerSqmElement);
                return;
            }

            // Convert currency using real exchange rates
            const rateKey = `${fromCurrency}_${toCurrency}`;

            // Use global exchange rates if available, otherwise fetch them
            if (window.exchangeRates && window.exchangeRates[rateKey]) {
                const convertedPrice = basePrice * window.exchangeRates[rateKey];
                const displayPrice = dealType === 'rent' ?
                    `${symbol}${formatPrice(convertedPrice)}/мес` :
                    `${symbol}${formatPrice(convertedPrice)}`;
                priceElement.innerHTML = displayPrice;

                // Update price per sqm for sale properties
                updatePricePerSqmFromData(propertyData, toCurrency, pricePerSqmElement);
            } else {
                // Fetch exchange rates from server
                fetch('/currency/rates/')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            window.exchangeRates = data.rates;
                            const rate = data.rates[rateKey] || 1;
                            const convertedPrice = basePrice * rate;

                            const displayPrice = dealType === 'rent' ?
                                `${symbol}${formatPrice(convertedPrice)}/мес` :
                                `${symbol}${formatPrice(convertedPrice)}`;
                            priceElement.innerHTML = displayPrice;

                            // Update price per sqm for sale properties
                            updatePricePerSqmFromData(propertyData, toCurrency, pricePerSqmElement);
                        } else {
                            // Fallback to original price
                            const displayPrice = dealType === 'rent' ?
                                `${symbol}${formatPrice(basePrice)}/мес` :
                                `${symbol}${formatPrice(basePrice)}`;
                            priceElement.innerHTML = displayPrice;

                            // Update price per sqm for sale properties
                            updatePricePerSqmFromData(propertyData, toCurrency, pricePerSqmElement);
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching exchange rates:', error);
                        // Fallback to original price
                        const displayPrice = dealType === 'rent' ?
                            `${symbol}${formatPrice(basePrice)}/мес` :
                            `${symbol}${formatPrice(basePrice)}`;
                        priceElement.innerHTML = displayPrice;

                        // Update price per sqm for sale properties
                        updatePricePerSqmFromData(propertyData, toCurrency, pricePerSqmElement);
                    });
            }
        }

        // Update price per square meter using pre-calculated data from model
        function updatePricePerSqmFromData(propertyData, currency, pricePerSqmElement) {
            if (!propertyData.area || propertyData.area <= 0 || propertyData.deal_type !== 'sale') {
                return;
            }

            // Find ALL elements for this property (since carousel has multiple copies)
            const allPricePerSqmElements = document.querySelectorAll(`.card-price-per-sqm-${propertyData.id}`);

            // Use pre-calculated price from model based on currency
            let pricePerSqm = '';
            if (currency === 'RUB' && propertyData.price_per_sqm_rub) {
                pricePerSqm = propertyData.price_per_sqm_rub;
            } else if (currency === 'THB' && propertyData.price_per_sqm_thb) {
                pricePerSqm = propertyData.price_per_sqm_thb;
            } else if (currency === 'USD' && propertyData.price_per_sqm_usd) {
                pricePerSqm = propertyData.price_per_sqm_usd;
            }

            if (pricePerSqm) {
                // Update ALL copies of the element
                allPricePerSqmElements.forEach((element) => {
                    element.innerHTML = pricePerSqm;
                });
            }
        }

        // Format price helper
        function formatPrice(amount) {
            return Math.round(amount).toLocaleString('en-US').replace(/,/g, ' ');
        }

        // Get initial price for a property based on available data
        function getInitialPrice(property) {
            if (property.deal_type === 'rent') {
                return property.price_rent_thb || property.price_rent_usd || property.price_rent_rub || 0;
            } else {
                return property.price_sale_thb || property.price_sale_usd || property.price_sale_rub || 0;
            }
        }

        // Get initial currency for a property based on current header currency
        function getInitialCurrency(property) {
            // Get current currency from header first
            const headerCurrency = getHeaderCurrency();
            
            // Check if property has price in current currency
            const currentCode = headerCurrency.code;
            if (property.deal_type === 'rent') {
                if (currentCode === 'THB' && property.price_rent_thb) return {code: 'THB', symbol: '฿'};
                if (currentCode === 'USD' && property.price_rent_usd) return {code: 'USD', symbol: '$'};
                if (currentCode === 'RUB' && property.price_rent_rub) return {code: 'RUB', symbol: '₽'};
            } else {
                if (currentCode === 'THB' && property.price_sale_thb) return {code: 'THB', symbol: '฿'};
                if (currentCode === 'USD' && property.price_sale_usd) return {code: 'USD', symbol: '$'};
                if (currentCode === 'RUB' && property.price_sale_rub) return {code: 'RUB', symbol: '₽'};
            }
            
            // Fallback to header currency
            return headerCurrency;
        }

        // Initialize currency dropdowns for all property cards
        function initializeCurrencyDropdowns() {
            const carouselContainer = document.getElementById('properties-carousel');
            if (!carouselContainer) {
                return;
            }

            // Find all currency toggle buttons
            const toggleButtons = carouselContainer.querySelectorAll('.currency-toggle-btn');
            
            toggleButtons.forEach(toggleBtn => {
                const propertyId = toggleBtn.dataset.propertyId;
                const dropdown = document.getElementById(`currency-dropdown-${propertyId}`);
                
                if (!dropdown) {
                    return;
                }

                // Create specific handlers for each button to avoid closure issues
                const handleToggle = function(e) {
                    e.preventDefault();
                    e.stopPropagation();

                    // Close other dropdowns first
                    document.querySelectorAll('.currency-dropdown').forEach(d => {
                        if (d !== dropdown) {
                            d.classList.add('opacity-0', 'invisible');
                            d.classList.remove('opacity-100', 'visible');
                        }
                    });

                    // Toggle current dropdown
                    const isVisible = dropdown.classList.contains('opacity-100');
                    
                    if (isVisible) {
                        dropdown.classList.add('opacity-0', 'invisible');
                        dropdown.classList.remove('opacity-100', 'visible');
                    } else {
                        dropdown.classList.remove('opacity-0', 'invisible');
                        dropdown.classList.add('opacity-100', 'visible');
                        
                        // Also set inline styles as backup
                        dropdown.style.opacity = '1';
                        dropdown.style.visibility = 'visible';
                        dropdown.style.display = 'block';
                        
                        // Force repaint to ensure visibility
                        dropdown.offsetHeight;
                    }
                };

                // Remove old listeners and add new one
                toggleBtn.removeEventListener('click', toggleBtn.currencyToggleHandler);
                toggleBtn.currencyToggleHandler = handleToggle;
                toggleBtn.addEventListener('click', handleToggle);

                // Initialize currency options
                const currencyOptions = dropdown.querySelectorAll('.card-currency-option');
                currencyOptions.forEach(option => {
                    const handleCurrencySelect = function(e) {
                        e.preventDefault();
                        e.stopPropagation();

                        const currency = option.dataset.currency;
                        const symbol = option.dataset.symbol;
                        const dealType = option.dataset.dealType;

                        // Update currency button display
                        const currencySymbol = toggleBtn.querySelector(`.current-currency-${propertyId}`);
                        const currencyCode = toggleBtn.querySelector(`.current-currency-code-${propertyId}`);
                        if (currencySymbol) currencySymbol.textContent = symbol;
                        if (currencyCode) currencyCode.textContent = currency;

                        // Update price
                        convertAndUpdateCardPrice(propertyId, currency, symbol, dealType);

                        // Close dropdown
                        dropdown.classList.add('opacity-0', 'invisible');
                        dropdown.classList.remove('opacity-100', 'visible');
                    };

                    // Remove old listeners and add new one
                    option.removeEventListener('click', option.currencySelectHandler);
                    option.currencySelectHandler = handleCurrencySelect;
                    option.addEventListener('click', handleCurrencySelect);
                });
            });

            // Global click handler to close dropdowns when clicking outside
            const handleGlobalClick = function(e) {
                if (!e.target.closest('.currency-dropdown') && !e.target.closest('.currency-toggle-btn')) {
                    document.querySelectorAll('.currency-dropdown').forEach(dropdown => {
                        dropdown.classList.add('opacity-0', 'invisible');
                        dropdown.classList.remove('opacity-100', 'visible');
                    });
                }
            };

            // Remove old global listener and add new one
            document.removeEventListener('click', document.currencyGlobalClickHandler);
            document.currencyGlobalClickHandler = handleGlobalClick;
            document.addEventListener('click', handleGlobalClick);
        }

        // Convert and update price for a specific card
        function convertAndUpdateCardPrice(propertyId, toCurrency, symbol, dealType) {
            const priceElement = document.querySelector(`.card-price-${propertyId}`);
            if (!priceElement) return;

            // Find property data
            const currentData = featuredProperties[currentPropertyType] || [];
            const propertyData = currentData.find(p => p.id == propertyId);
            if (!propertyData) return;

            let basePrice = 0;
            let fromCurrency = 'USD';

            // Get base price and currency
            if (dealType === 'rent') {
                if (propertyData.price_rent_thb) {
                    basePrice = propertyData.price_rent_thb;
                    fromCurrency = 'THB';
                } else if (propertyData.price_rent_usd) {
                    basePrice = propertyData.price_rent_usd;
                    fromCurrency = 'USD';
                } else if (propertyData.price_rent_rub) {
                    basePrice = propertyData.price_rent_rub;
                    fromCurrency = 'RUB';
                }
            } else {
                if (propertyData.price_sale_thb) {
                    basePrice = propertyData.price_sale_thb;
                    fromCurrency = 'THB';
                } else if (propertyData.price_sale_usd) {
                    basePrice = propertyData.price_sale_usd;
                    fromCurrency = 'USD';
                } else if (propertyData.price_sale_rub) {
                    basePrice = propertyData.price_sale_rub;
                    fromCurrency = 'RUB';
                }
            }

            if (!basePrice) {
                priceElement.textContent = 'Цена по запросу';
                return;
            }

            if (fromCurrency === toCurrency) {
                priceElement.textContent = formatPrice(basePrice);
                updatePricePerSqmFromData(propertyData, toCurrency);
                return;
            }

            // Get exchange rate
            const rateKey = `${fromCurrency}_${toCurrency}`;

            if (window.exchangeRates && window.exchangeRates[rateKey]) {
                const rate = window.exchangeRates[rateKey];
                const convertedPrice = basePrice * rate;
                priceElement.textContent = formatPrice(convertedPrice);
                updatePricePerSqmFromData(propertyData, toCurrency);
            } else {
                fetch('/currency/rates/')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            window.exchangeRates = data.rates;
                            const rate = data.rates[rateKey] || 1;
                            const convertedPrice = basePrice * rate;
                            priceElement.textContent = formatPrice(convertedPrice);
                            updatePricePerSqmFromData(propertyData, toCurrency);
                        } else {
                            priceElement.textContent = formatPrice(basePrice);
                            updatePricePerSqmFromData(propertyData, toCurrency);
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching exchange rates:', error);
                        priceElement.textContent = formatPrice(basePrice);
                        updatePricePerSqmFromData(propertyData, toCurrency);
                    });
            }
        }

        // Create consultation form card
        function createConsultationCard() {
            const consultationId = Math.random().toString(36).substr(2, 9); // Unique ID for each card
            return `
            <div class="consultation-card bg-gradient-to-br from-primary to-tertiary rounded-lg p-4 text-white shadow-lg w-full h-full flex flex-col">
                <div class="text-center mb-4">
                    <div class="w-12 h-12 bg-accent rounded-full flex items-center justify-center mx-auto mb-3 consultation-icon-circle">
                        <i class="fas fa-user-tie text-gray-900 text-lg consultation-expert-icon"></i>
                    </div>
                    <h3 class="text-lg font-bold mb-2 leading-tight text-white">Получить консультацию эксперта <span class="text-accent">Undersun</span></h3>
                    <p class="text-white/90 mb-4 text-sm">Где вам удобнее общаться</p>
                </div>
                
                <!-- Tabs -->
                <div class="flex mb-3 bg-white/10 rounded-md p-1">
                    <button onclick="switchConsultationTab('${consultationId}', 'phone')" 
                            class="consultation-tab flex-1 py-2 px-2 rounded text-xs font-medium transition-all duration-200 active" 
                            data-tab="phone" data-consultation-id="${consultationId}">
                        <i class="fas fa-phone text-xs mr-1"></i>Звонок
                    </button>
                    <button onclick="switchConsultationTab('${consultationId}', 'whatsapp')" 
                            class="consultation-tab flex-1 py-2 px-2 rounded text-xs font-medium transition-all duration-200" 
                            data-tab="whatsapp" data-consultation-id="${consultationId}">
                        <i class="fab fa-whatsapp text-xs mr-1"></i>WhatsApp
                    </button>
                    <button onclick="switchConsultationTab('${consultationId}', 'telegram')" 
                            class="consultation-tab flex-1 py-2 px-2 rounded text-xs font-medium transition-all duration-200" 
                            data-tab="telegram" data-consultation-id="${consultationId}">
                        <i class="fab fa-telegram text-xs mr-1"></i>Telegram
                    </button>
                </div>
                
                <!-- Tab Content -->
                <div class="flex-1">
                    <!-- Phone Tab -->
                    <div class="consultation-content active" data-tab="phone" data-consultation-id="${consultationId}">
                        <form onsubmit="handlePhoneCallback(event, '${consultationId}')" class="space-y-3">
                            <div>
                                <input type="tel" 
                                       placeholder="+66 XXX XXX XXX" 
                                       class="consultation-form-input w-full px-3 py-2 rounded-md bg-white/20 backdrop-blur-sm border border-white/30 text-white placeholder-white/70 text-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                                       required>
                            </div>
                            <button type="submit" 
                                    class="w-full bg-accent hover:bg-yellow-400 text-gray-900 font-bold py-2 px-4 rounded-md transition-all duration-200 text-sm">
                                Заказать звонок
                            </button>
                        </form>
                    </div>
                    
                    <!-- WhatsApp Tab -->
                    <div class="consultation-content hidden" data-tab="whatsapp" data-consultation-id="${consultationId}">
                        <div class="text-center py-4">
                            <p class="text-white/90 mb-4 text-sm">Напишите нам в WhatsApp для быстрой консультации</p>
                            <a href="https://wa.me/66633033133?text=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5%21%20%D0%9C%D0%B5%D0%BD%D1%8F%20%D0%B8%D0%BD%D1%82%D0%B5%D1%80%D0%B5%D1%81%D1%83%D0%B5%D1%82%20%D0%BA%D0%BE%D0%BD%D1%81%D1%83%D0%BB%D1%8C%D1%82%D0%B0%D1%86%D0%B8%D1%8F%20%D0%BF%D0%BE%20%D0%BD%D0%B5%D0%B4%D0%B2%D0%B8%D0%B6%D0%B8%D0%BC%D0%BE%D1%81%D1%82%D0%B8" 
                               target="_blank" 
                               class="block w-full bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-md transition-all duration-200 text-sm">
                                <i class="fab fa-whatsapp mr-2"></i>Написать в WhatsApp
                            </a>
                        </div>
                    </div>
                    
                    <!-- Telegram Tab -->
                    <div class="consultation-content hidden" data-tab="telegram" data-consultation-id="${consultationId}">
                        <div class="text-center py-4">
                            <p class="text-white/90 mb-4 text-sm">Напишите нам в Telegram для получения консультации</p>
                            <a href="https://t.me/undersunestate" 
                               target="_blank" 
                               class="block w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-md transition-all duration-200 text-sm">
                                <i class="fab fa-telegram mr-2"></i>Написать в Telegram
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
        }

        // Create property card
        function createPropertyCard(property) {
            const imageUrl = property.main_image_url || '/static/images/no-image.svg';
            const priceDisplay = property.price_formatted || 'Цена по запросу';

            // Safely check favorites - use window.isFavorite if available
            let isFav = false;
            try {
                if (typeof window.isFavorite === 'function') {
                    isFav = window.isFavorite(property.id);
                } else if (typeof isFavorite === 'function') {
                    isFav = isFavorite(property.id);
                }
            } catch (e) {
            }

            const heartClass = isFav ? 'fas text-red-500' : 'far text-gray-600';

            return `
            <div class="property-card bg-white rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 overflow-hidden w-full h-full">
                <div class="relative h-48">
                    <img src="${imageUrl}" class="w-full h-full object-cover" alt="${property.title}" loading="lazy">

                    <!-- Special Offer Ribbon -->
                    ${property.special_offer ?
                    `<div class="special-offer-ribbon">
                            <div class="ribbon-content">
                                ${property.special_offer}
                            </div>
                        </div>` :
                    ''
                }
                    
                    <div class="absolute top-3 right-3">
                        <button class="bg-white/90 hover:bg-white w-10 h-10 rounded-full transition-all duration-200 group favorite-btn shadow-lg hover:shadow-xl transform hover:scale-110 flex items-center justify-center"
                                data-property-id="${property.id}">
                            <i class="${heartClass} group-hover:text-red-500 fa-heart transition-all duration-200"></i>
                        </button>
                    </div>
                </div>
                
                <div class="p-4 flex flex-col justify-between flex-1">
                    <div>
                        <h3 class="text-lg font-bold text-gray-900 mb-3 leading-tight line-clamp-2">
                            <a href="${property.url}" class="hover:text-primary transition-colors">
                                ${property.title.length > 60 ? property.title.substring(0, 60) + '...' : property.title}
                            </a>
                        </h3>
                        
                        <div class="flex items-center text-gray-600 mb-3">
                            <i class="fas fa-map-marker-alt mr-2 text-primary text-sm"></i>
                            <span class="text-sm font-medium">${property.district_name || 'Пхукет'}${property.location_name ? ', ' + property.location_name : ''}</span>
                        </div>
                        
                        <!-- Property Details -->
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center space-x-4">
                                ${property.bedrooms > 0 ? `
                                    <div class="flex items-center text-gray-600">
                                        <i class="fas fa-bed mr-2 text-primary text-base"></i>
                                        <span class="text-base font-medium">${property.bedrooms}</span>
                                    </div>
                                ` : ''}
                                ${property.bathrooms > 0 ? `
                                    <div class="flex items-center text-gray-600">
                                        <i class="fas fa-bath mr-2 text-primary text-base"></i>
                                        <span class="text-base font-medium">${property.bathrooms}</span>
                                    </div>
                                ` : ''}
                                ${property.area > 0 ? `
                                    <div class="flex items-center text-gray-600">
                                        <i class="fas fa-ruler-combined mr-2 text-primary text-base"></i>
                                        <span class="text-base font-medium">${property.area} м²</span>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                        
                        <!-- Price Section -->
                        <div class="mb-4">
                            <!-- Price and Currency in one line -->
                            <div class="flex items-center justify-center space-x-3 mb-2">
                                <!-- Price -->
                                <span class="text-2xl font-bold text-primary card-price-${property.id}" data-property-id="${property.id}" data-deal-type="${property.deal_type}">
                                    ${formatPrice(getInitialPrice(property))}
                                </span>
                                
                                <!-- Currency Dropdown -->
                                <div class="relative">
                                    <button class="currency-toggle-btn bg-gray-100 hover:bg-primary hover:text-white text-gray-500 transition-all duration-200 px-3 py-1.5 rounded-md text-sm border border-gray-200 hover:border-primary flex items-center"
                                            data-property-id="${property.id}"
                                            data-deal-type="${property.deal_type}"
                                            title="Изменить валюту">
                                        <span class="current-currency-${property.id} font-mono mr-1">${getInitialCurrency(property).symbol}</span>
                                        <span class="current-currency-code-${property.id} font-medium mr-1">${getInitialCurrency(property).code}</span>
                                        <i class="fas fa-chevron-down text-xs"></i>
                                    </button>

                                    <!-- Dropdown Menu -->
                                    <div class="currency-dropdown absolute top-full left-1/2 transform -translate-x-1/2 mt-1 w-32 bg-white rounded-lg shadow-xl border border-gray-200 opacity-0 invisible transform scale-95 transition-all duration-200"
                                         id="currency-dropdown-${property.id}"
                                         style="z-index: 99999 !important; position: absolute !important; box-shadow: 0 10px 25px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);">
                                        <div class="py-1">
                                            <button type="button"
                                                    class="card-currency-option w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-primary hover:text-white transition-all duration-150 flex items-center rounded-t-lg"
                                                    data-currency="USD" data-symbol="$"
                                                    data-property-id="${property.id}"
                                                    data-deal-type="${property.deal_type}">
                                                <span class="font-mono mr-2 w-4">$</span>
                                                <span class="font-medium">USD</span>
                                            </button>
                                            <button type="button"
                                                    class="card-currency-option w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-primary hover:text-white transition-all duration-150 flex items-center"
                                                    data-currency="THB" data-symbol="฿"
                                                    data-property-id="${property.id}"
                                                    data-deal-type="${property.deal_type}">
                                                <span class="font-mono mr-2 w-4">฿</span>
                                                <span class="font-medium">THB</span>
                                            </button>
                                            <button type="button"
                                                    class="card-currency-option w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-primary hover:text-white transition-all duration-150 flex items-center rounded-b-lg"
                                                    data-currency="RUB" data-symbol="₽"
                                                    data-property-id="${property.id}"
                                                    data-deal-type="${property.deal_type}">
                                                <span class="font-mono mr-2 w-4">₽</span>
                                                <span class="font-medium">RUB</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            ${property.area > 0 && property.deal_type === 'sale' ? `
                                <div class="text-center">
                                    <div class="text-sm text-gray-600 font-medium card-price-per-sqm-${property.id}">
                                        ${property.price_per_sqm_thb || property.price_per_sqm_rub || property.price_per_sqm_usd || ''}
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    
                    <a href="${property.url}" class="block w-full bg-accent hover:bg-yellow-500 text-gray-900 py-2 px-4 rounded-md font-semibold transition-all duration-300 text-center text-sm">
                        Узнать подробнее
                    </a>
                </div>
            </div>
        `;
        }

        // Initialize with villa properties
        renderProperties(featuredProperties.villa || []);

        // Handle window resize for mobile adaptation
        let resizeTimeout;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(function () {
                updateCarouselPosition(false); // Update position without animation
            }, 100);
        });
    }

    // Initialize when DOM is ready or immediately if already ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFeaturedProperties);
    } else {
        initFeaturedProperties();
    }
})();