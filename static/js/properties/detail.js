/**
 * Property Detail Page JavaScript
 * Управление галереей, каруселью, формами и функциональностью страницы объекта
 */

let currentImageIndex = 0;
let currentSlidePairIndex = 0;
let totalSlidePairs = Math.ceil(PROPERTY_IMAGES.length / 2);

// Check if we're on mobile or desktop
function isMobile() {
    return window.innerWidth < 768; // md breakpoint
}

// Carousel functionality (works for both mobile and desktop)
function nextSlide() {
    if (isMobile()) {
        // Mobile: single image navigation
        if (PROPERTY_IMAGES.length <= 1) return;

        const currentSlide = document.querySelector('.property-slide-single[data-slide-single="' + currentImageIndex + '"]');
        currentImageIndex = (currentImageIndex + 1) % PROPERTY_IMAGES.length;
        const nextSlide = document.querySelector('.property-slide-single[data-slide-single="' + currentImageIndex + '"]');

        if (currentSlide && nextSlide) {
            currentSlide.style.opacity = '0';
            nextSlide.style.opacity = '1';
        }
    } else {
        // Desktop: dual image navigation
        if (totalSlidePairs <= 1) return;

        const currentSlidePair = document.querySelector('.property-slide-pair[data-slide-pair="' + currentSlidePairIndex + '"]');
        currentSlidePairIndex = (currentSlidePairIndex + 2) % PROPERTY_IMAGES.length;
        if (currentSlidePairIndex >= PROPERTY_IMAGES.length) currentSlidePairIndex = 0;

        const nextSlidePair = document.querySelector('.property-slide-pair[data-slide-pair="' + currentSlidePairIndex + '"]');

        if (currentSlidePair && nextSlidePair) {
            currentSlidePair.style.opacity = '0';
            nextSlidePair.style.opacity = '1';
        }
    }

    updateCarouselUI();
}

function previousSlide() {
    if (isMobile()) {
        // Mobile: single image navigation
        if (PROPERTY_IMAGES.length <= 1) return;

        const currentSlide = document.querySelector('.property-slide-single[data-slide-single="' + currentImageIndex + '"]');
        currentImageIndex = (currentImageIndex - 1 + PROPERTY_IMAGES.length) % PROPERTY_IMAGES.length;
        const prevSlide = document.querySelector('.property-slide-single[data-slide-single="' + currentImageIndex + '"]');

        if (currentSlide && prevSlide) {
            currentSlide.style.opacity = '0';
            prevSlide.style.opacity = '1';
        }
    } else {
        // Desktop: dual image navigation
        if (totalSlidePairs <= 1) return;

        const currentSlidePair = document.querySelector('.property-slide-pair[data-slide-pair="' + currentSlidePairIndex + '"]');
        currentSlidePairIndex = (currentSlidePairIndex - 2 + PROPERTY_IMAGES.length);
        while (currentSlidePairIndex >= PROPERTY_IMAGES.length) currentSlidePairIndex -= 2;
        if (currentSlidePairIndex < 0) currentSlidePairIndex = PROPERTY_IMAGES.length - (PROPERTY_IMAGES.length % 2 === 0 ? 2 : 1);

        const prevSlidePair = document.querySelector('.property-slide-pair[data-slide-pair="' + currentSlidePairIndex + '"]');

        if (currentSlidePair && prevSlidePair) {
            currentSlidePair.style.opacity = '0';
            prevSlidePair.style.opacity = '1';
        }
    }

    updateCarouselUI();
}

function goToSlidePair(pairIndex) {
    if (totalSlidePairs <= 1 || pairIndex === currentSlidePairIndex) return;

    const currentSlidePair = document.querySelector('.property-slide-pair[data-slide-pair="' + currentSlidePairIndex + '"]');
    const targetSlidePair = document.querySelector('.property-slide-pair[data-slide-pair="' + pairIndex + '"]');

    if (currentSlidePair && targetSlidePair) {
        currentSlidePair.style.opacity = '0';
        targetSlidePair.style.opacity = '1';
    }

    currentSlidePairIndex = pairIndex;
    updateCarouselUI();
}

function goToSlidePairByImage(imageIndex) {
    // Calculate which pair this image belongs to
    const pairIndex = Math.floor(imageIndex / 2) * 2;
    goToSlidePair(pairIndex);
}

function updateCarouselUI() {
    // Update photo counter - show range of photos visible
    const counter = document.getElementById('current-photo');
    if (counter) {
        const firstPhoto = currentSlidePairIndex + 1;
        let secondPhoto;

        // Handle the case where we're showing the last image paired with first image
        if (currentSlidePairIndex + 1 >= PROPERTY_IMAGES.length) {
            // Show last image + first image
            secondPhoto = 1;
            counter.textContent = `${PROPERTY_IMAGES.length}, 1`;
        } else {
            secondPhoto = Math.min(currentSlidePairIndex + 2, PROPERTY_IMAGES.length);
            if (firstPhoto === secondPhoto) {
                counter.textContent = firstPhoto;
            } else {
                counter.textContent = `${firstPhoto}-${secondPhoto}`;
            }
        }
    }

    // Update pair indicators
    const indicators = document.querySelectorAll('.property-pair-indicator');
    indicators.forEach((indicator, index) => {
        const pairIndex = index * 2;
        if (pairIndex === currentSlidePairIndex) {
            indicator.classList.remove('bg-white', 'bg-opacity-60');
            indicator.classList.add('bg-accent', 'shadow-lg');
        } else {
            indicator.classList.remove('bg-accent', 'shadow-lg');
            indicator.classList.add('bg-white', 'bg-opacity-60');
        }
    });

    // Update thumbnails
    const thumbs = document.querySelectorAll('img[data-thumb]');
    thumbs.forEach((thumb, index) => {
        const isFirstInPair = index === currentSlidePairIndex;
        let isSecondInPair;

        // Handle zipped display for odd number of images
        if (currentSlidePairIndex + 1 >= PROPERTY_IMAGES.length && PROPERTY_IMAGES.length % 2 === 1) {
            // We're showing last image + first image
            isSecondInPair = index === 0; // First image as second in pair
        } else {
            isSecondInPair = index === currentSlidePairIndex + 1 && index < PROPERTY_IMAGES.length;
        }

        if (isFirstInPair || isSecondInPair) {
            thumb.classList.remove('border-transparent', 'hover:border-accent/50');
            thumb.classList.add('border-accent', 'shadow-lg');
        } else {
            thumb.classList.remove('border-accent', 'shadow-lg');
            thumb.classList.add('border-transparent', 'hover:border-accent/50');
        }
    });
}

function openGallery(index) {
    currentImageIndex = index;
    updateGalleryImage();
    document.getElementById('gallery-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeGallery() {
    document.getElementById('gallery-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

function updateGalleryImage() {
    if (PROPERTY_IMAGES.length > 0) {
        const galleryImage = document.getElementById('gallery-image');
        const loading = document.getElementById('gallery-loading');

        // Show loading
        loading.classList.remove('hidden');

        // Update image
        galleryImage.onload = function () {
            loading.classList.add('hidden');
        };

        galleryImage.src = PROPERTY_IMAGES[currentImageIndex];
        document.getElementById('gallery-counter').textContent = `${currentImageIndex + 1} / ${PROPERTY_IMAGES.length}`;

        // Update thumbnail highlights
        const thumbs = document.querySelectorAll('.gallery-thumb');
        thumbs.forEach((thumb, index) => {
            if (index === currentImageIndex) {
                thumb.classList.add('border-accent', 'border-4');
                thumb.classList.remove('border-transparent', 'border-2');
            } else {
                thumb.classList.remove('border-accent', 'border-4');
                thumb.classList.add('border-transparent', 'border-2');
            }
        });
    }
}

// Download image function
function downloadImage() {
    if (PROPERTY_IMAGES.length > 0) {
        const link = document.createElement('a');
        link.href = PROPERTY_IMAGES[currentImageIndex];
        link.download = `${PROPERTY_SLUG}-${currentImageIndex + 1}.jpg`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

// Share property function (for carousel button)
function shareProperty() {
    if (navigator.share) {
        navigator.share({
            title: PROPERTY_TITLE,
            text: TRANSLATIONS.shareText,
            url: window.location.href
        }).catch(console.error);
    } else {
        // Fallback: copy URL to clipboard
        navigator.clipboard.writeText(window.location.href).then(() => {
            showNotification(TRANSLATIONS.linkCopied, 'success');
        }).catch(() => {
            showNotification(TRANSLATIONS.copyError, 'error');
        });
    }
}

function setDetailFavoriteState(propertyId, isFavorite) {
    if (typeof window.updateFavoriteButtons === 'function') {
        window.updateFavoriteButtons(propertyId, isFavorite);
    } else {
        // Fallback for pages without global helpers
        document.querySelectorAll(`.favorite-btn[data-property-id="${propertyId}"] i`).forEach(iconEl => {
            iconEl.classList.toggle('fas', isFavorite);
            iconEl.classList.toggle('far', !isFavorite);
            iconEl.classList.toggle('text-red-500', isFavorite);
            iconEl.classList.toggle('text-gray-600', !isFavorite);
        });
    }

    const carouselIcon = document.querySelector('.carousel-favorite-btn i');
    if (carouselIcon) {
        carouselIcon.classList.toggle('fas', isFavorite);
        carouselIcon.classList.toggle('far', !isFavorite);
        carouselIcon.classList.toggle('text-red-500', isFavorite);
    }
}

// Toggle favorite function (for carousel button)
function toggleFavoriteDetail(propertyId) {
    let isFavoriteNow = null;

    if (typeof window.toggleFavorite === 'function') {
        isFavoriteNow = window.toggleFavorite(propertyId);
    }

    if (typeof isFavoriteNow !== 'boolean') {
        // Fallback if global handler недоступен
        let favorites = [];
        if (typeof window.getFavorites === 'function') {
            favorites = window.getFavorites();
        } else {
            favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
            favorites = favorites.map(id => parseInt(id, 10)).filter(id => Number.isInteger(id));
        }

        const id = parseInt(propertyId, 10);
        const wasFavorite = favorites.includes(id);

        if (wasFavorite) {
            favorites = favorites.filter(item => item !== id);
            showNotification(TRANSLATIONS.removedFromFavorites, 'info');
        } else {
            favorites.push(id);
            showNotification(TRANSLATIONS.addedToFavorites, 'success');
        }

        localStorage.setItem('favorites', JSON.stringify(favorites));
        if (typeof window.updateFavoritesCounter === 'function') {
            window.updateFavoritesCounter();
        }

        isFavoriteNow = !wasFavorite;
    }

    setDetailFavoriteState(parseInt(propertyId, 10), Boolean(isFavoriteNow));
}

// Share image function
function shareImage() {
    if (navigator.share && PROPERTY_IMAGES.length > 0) {
        navigator.share({
            title: PROPERTY_TITLE,
            text: TRANSLATIONS.shareText,
            url: window.location.href
        }).catch(console.error);
    } else {
        // Fallback: copy URL to clipboard
        navigator.clipboard.writeText(window.location.href).then(() => {
            showNotification(TRANSLATIONS.linkCopied, 'success');
        });
    }
}

function nextImage() {
    currentImageIndex = (currentImageIndex + 1) % PROPERTY_IMAGES.length;
    updateGalleryImage();
}

function previousImage() {
    currentImageIndex = (currentImageIndex - 1 + PROPERTY_IMAGES.length) % PROPERTY_IMAGES.length;
    updateGalleryImage();
}

// Auto-carousel functionality
let autoCarouselInterval;

function startAutoCarousel() {
    if (PROPERTY_IMAGES.length > 1) {
        autoCarouselInterval = setInterval(() => {
            nextSlide();
        }, 5000); // Change slide every 5 seconds
    }
}

function stopAutoCarousel() {
    if (autoCarouselInterval) {
        clearInterval(autoCarouselInterval);
        autoCarouselInterval = null;
    }
}

// Go back to catalog with preserved filters
function goBackToCatalog() {
    // Get saved catalog state from localStorage or sessionStorage
    const savedCatalogState = sessionStorage.getItem('catalogState') || localStorage.getItem('catalogState');

    if (savedCatalogState) {
        // If we have saved catalog state, restore it
        const catalogData = JSON.parse(savedCatalogState);
        const catalogUrl = catalogData.url || '/property/sale/';

        // Navigate to the catalog with preserved filters
        window.location.href = catalogUrl;
    } else {
        // Fallback to default catalog page
        const dealType = PROPERTY_DEAL_TYPE;
        if (dealType === 'sale') {
            window.location.href = '/property/sale/';
        } else if (dealType === 'rent') {
            window.location.href = '/property/rent/';
        } else {
            // For 'both' type, go to sale catalog as default
            window.location.href = '/property/sale/';
        }
    }
}

// Save current page referrer when coming from catalog
function saveCatalogReferrer() {
    const referrer = document.referrer;
    if (referrer && (referrer.includes('/property/sale/') || referrer.includes('/property/rent/'))) {
        const catalogState = {
            url: referrer,
            timestamp: Date.now()
        };
        sessionStorage.setItem('catalogState', JSON.stringify(catalogState));
    }
}

// Description toggle functionality
function toggleDescription() {
    const content = document.getElementById('description-content');
    const gradient = document.getElementById('description-gradient');
    const toggleText = document.getElementById('toggle-text');
    const toggleIcon = document.getElementById('toggle-icon');

    if (content.classList.contains('max-h-24')) {
        // Expand
        content.classList.remove('max-h-24');
        content.classList.add('max-h-full');
        gradient.style.opacity = '0';
        toggleText.textContent = TRANSLATIONS.collapse;
        toggleIcon.classList.remove('fa-chevron-down');
        toggleIcon.classList.add('fa-chevron-up');
    } else {
        // Collapse
        content.classList.remove('max-h-full');
        content.classList.add('max-h-24');
        gradient.style.opacity = '1';
        toggleText.textContent = TRANSLATIONS.showFull;
        toggleIcon.classList.remove('fa-chevron-up');
        toggleIcon.classList.add('fa-chevron-down');
    }
}

// Price functionality - property data with currency conversion
function updatePrices() {
    // Get current currency from localStorage
    const currentCurrency = localStorage.getItem('selectedCurrency') || 'THB';

    let salePrice = null;
    let rentPrice = null;
    let currencySymbol = '';

    switch(currentCurrency) {
        case 'USD':
            salePrice = PROPERTY_DATA.price_sale_usd;
            rentPrice = PROPERTY_DATA.price_rent_monthly_usd;
            currencySymbol = '$';
            break;
        case 'THB':
            salePrice = PROPERTY_DATA.price_sale_thb;
            rentPrice = PROPERTY_DATA.price_rent_monthly_thb;
            currencySymbol = '฿';
            break;
        case 'RUB':
            salePrice = PROPERTY_DATA.price_sale_rub;
            rentPrice = PROPERTY_DATA.price_rent_monthly_rub;
            currencySymbol = '₽';
            break;
    }

    // Update main price
    const mainPriceEl = document.getElementById('main-price');
    if (mainPriceEl) {
        let priceText = '';

        if (PROPERTY_DATA.deal_type === 'sale' && salePrice) {
            priceText = `${currencySymbol}${Math.round(salePrice).toLocaleString()}`;
        } else if (PROPERTY_DATA.deal_type === 'rent' && rentPrice) {
            priceText = `${currencySymbol}${Math.round(rentPrice).toLocaleString()}/мес`;
        } else if (PROPERTY_DATA.deal_type === 'both') {
            if (salePrice) {
                priceText = `${currencySymbol}${Math.round(salePrice).toLocaleString()}`;
            } else if (rentPrice) {
                priceText = `${currencySymbol}${Math.round(rentPrice).toLocaleString()}/мес`;
            }
        }

        if (priceText) {
            mainPriceEl.textContent = priceText;
        } else {
            mainPriceEl.textContent = 'По запросу';
        }
    }

    // Update price per square meter
    const pricePerSqmEl = document.getElementById('price-per-sqm');

    if (pricePerSqmEl && PROPERTY_DATA.area_total && salePrice) {
        if (PROPERTY_DATA.deal_type !== 'rent') {
            const pricePerSqm = Math.round(salePrice / PROPERTY_DATA.area_total);
            const pricePerSqmText = `${pricePerSqm.toLocaleString()} ${currencySymbol}/м²`;
            pricePerSqmEl.textContent = pricePerSqmText;
        } else {
            pricePerSqmEl.textContent = '';
        }
    } else if (pricePerSqmEl) {
        pricePerSqmEl.textContent = '';
    }
}

// Modal functions
function openDetailsModal() {
    document.getElementById('consultation-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeDetailsModal() {
    document.getElementById('consultation-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';

    // Очищаем форму и скрываем сообщения
    const form = document.getElementById('consultationRequestForm');
    const message = document.getElementById('consultation-message');
    if (form) form.reset();
    if (message) message.classList.add('hidden');
}

function openViewingModal() {
    document.getElementById('viewing-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeViewingModal() {
    document.getElementById('viewing-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';

    // Очищаем форму и скрываем сообщения
    const form = document.getElementById('viewingRequestForm');
    const message = document.getElementById('viewing-message');
    if (form) form.reset();
    if (message) message.classList.add('hidden');
}

function openConsultationModal() {
    document.getElementById('consultation-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeConsultationModal() {
    document.getElementById('consultation-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';

    // Очищаем форму и скрываем сообщения
    const form = document.getElementById('consultationRequestForm');
    const message = document.getElementById('consultation-message');
    if (form) form.reset();
    if (message) message.classList.add('hidden');
}

// Form submission handler
function handleFormSubmit(formId, endpoint, successCallback) {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        const formData = new FormData(this);
        const submitBtn = this.querySelector('button[type="submit"]');
        const messageDiv = this.parentElement.querySelector('[id$="-message"]');
        const originalText = submitBtn.textContent;

        // Отключаем кнопку во время отправки
        submitBtn.disabled = true;
        submitBtn.textContent = TRANSLATIONS.sending;

        fetch(endpoint, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value,
            },
        })
            .then(response => response.json())
            .then(data => {
                if (messageDiv) {
                    messageDiv.classList.remove('hidden');

                    if (data.success) {
                        messageDiv.className = 'p-3 rounded-md text-sm bg-green-100 text-green-800';
                        messageDiv.textContent = data.message;
                        form.reset();

                        // Вызываем callback если есть
                        if (successCallback) {
                            setTimeout(successCallback, 2000);
                        }
                    } else {
                        messageDiv.className = 'p-3 rounded-md text-sm bg-red-100 text-red-800';
                        messageDiv.textContent = data.message;
                    }

                    // Скрываем сообщение через 5 секунд
                    setTimeout(() => {
                        messageDiv.classList.add('hidden');
                    }, 5000);
                }

                // Восстанавливаем кнопку
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            })
            .catch(error => {
                console.error('Error:', error);
                if (messageDiv) {
                    messageDiv.classList.remove('hidden');
                    messageDiv.className = 'p-3 rounded-md text-sm bg-red-100 text-red-800';
                    messageDiv.textContent = TRANSLATIONS.formError;
                }

                // Восстанавливаем кнопку
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            });
    });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function () {
    // Save catalog referrer if coming from catalog
    saveCatalogReferrer();

    // Initialize carousel auto-play
    startAutoCarousel();

    // Initialize prices
    updatePrices();

    // Listen for currency changes
    window.addEventListener('currencyChanged', updatePrices);

    // Stop carousel on hover, restart on mouse leave
    const carouselContainer = document.querySelector('.property-carousel');
    if (carouselContainer) {
        carouselContainer.addEventListener('mouseenter', stopAutoCarousel);
        carouselContainer.addEventListener('mouseleave', startAutoCarousel);
    }

    // Initialize favorite buttons state
    const propertyId = PROPERTY_ID;
    let favorites = [];
    if (typeof window.getFavorites === 'function') {
        favorites = window.getFavorites();
    } else {
        favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
        favorites = favorites.map(id => parseInt(id, 10)).filter(id => Number.isInteger(id));
    }

    const isFavorite = (typeof window.isFavorite === 'function')
        ? window.isFavorite(propertyId)
        : favorites.includes(propertyId);

    setDetailFavoriteState(propertyId, isFavorite);

    if (typeof window.updateFavoritesCounter === 'function') {
        window.updateFavoritesCounter();
    }

    const favoriteBtn = document.querySelector('.favorite-btn');
    if (favoriteBtn) {
        favoriteBtn.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            toggleFavoriteDetail(propertyId);
        });
    }

    // Initialize all forms
    if (INQUIRY_ENDPOINT) {
        handleFormSubmit('inquiry-form', INQUIRY_ENDPOINT);
        handleFormSubmit('viewingRequestForm', INQUIRY_ENDPOINT, closeViewingModal);
        handleFormSubmit('consultationRequestForm', INQUIRY_ENDPOINT, closeConsultationModal);
    }

    // Newsletter form (если нужно)
    const newsletterForm = document.getElementById('newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const messageDiv = document.getElementById('newsletter-message');
            const submitBtn = this.querySelector('button[type="submit"]');

            submitBtn.disabled = true;
            submitBtn.textContent = TRANSLATIONS.subscribing;

            setTimeout(() => {
                if (messageDiv) {
                    messageDiv.classList.remove('hidden');
                    messageDiv.className = 'mt-4 p-3 rounded-md text-sm bg-green-100 text-green-800';
                    messageDiv.textContent = TRANSLATIONS.subscribeSuccess;
                }

                newsletterForm.reset();
                submitBtn.disabled = false;
                submitBtn.textContent = TRANSLATIONS.subscribe;

                setTimeout(() => {
                    if (messageDiv) messageDiv.classList.add('hidden');
                }, 5000);
            }, 1000);
        });
    }

    // Keyboard navigation for gallery
    document.addEventListener('keydown', function (e) {
        if (!document.getElementById('gallery-modal').classList.contains('hidden')) {
            if (e.key === 'ArrowRight') nextImage();
            if (e.key === 'ArrowLeft') previousImage();
            if (e.key === 'Escape') closeGallery();
        }
    });

    // Close modal on outside click
    document.addEventListener('click', function (e) {
        const viewingModal = document.getElementById('viewing-modal');
        const consultationModal = document.getElementById('consultation-modal');

        if (e.target === consultationModal) {
            closeDetailsModal();
        }
        if (e.target === viewingModal) {
            closeViewingModal();
        }
    });

    // Close modal on escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const viewingModal = document.getElementById('viewing-modal');
            const consultationModal = document.getElementById('consultation-modal');

            if (!consultationModal.classList.contains('hidden')) {
                closeDetailsModal();
            } else if (!viewingModal.classList.contains('hidden')) {
                closeViewingModal();
            }
        }
    });
});
