/**
 * Property Detail Page JavaScript
 * Управление галереей, каруселью, формами и функциональностью страницы объекта
 */

let currentImageIndex = 0;
const preloadedGalleryImages = new Set();

const PROPERTY_I18N = window.propertyDetailTranslations || {};
const LABEL_PRICE_ON_REQUEST = PROPERTY_I18N.priceOnRequest || 'По запросу';
const LABEL_PER_MONTH = PROPERTY_I18N.perMonth || 'мес';
const LABEL_PER_SQM = PROPERTY_I18N.perSqm || 'м²';

function firePropertyGoal(goalName, params = {}) {
    if (typeof window.dispatchMetrikaGoal !== 'function' || !goalName) {
        return;
    }
    const payload = Object.assign({ propertyId: PROPERTY_ID }, params || {});
    window.dispatchMetrikaGoal(goalName, payload);
}

function getCarouselSlide(index) {
    return document.querySelector(`.property-slide[data-slide-index="${index}"]`);
}

function isDesktopDualMode() {
    return window.matchMedia('(min-width: 1024px)').matches;
}

function getHeroIndex(index = currentImageIndex) {
    const normalizedIndex = normalizeImageIndex(index);
    if (!isDesktopDualMode()) {
        return normalizedIndex;
    }

    return Math.floor(normalizedIndex / 2) * 2;
}

function getDesktopSecondaryIndex(primaryIndex = getHeroIndex()) {
    if (PROPERTY_IMAGES.length <= 1) {
        return null;
    }

    const secondaryIndex = primaryIndex + 1;
    return secondaryIndex < PROPERTY_IMAGES.length ? secondaryIndex : 0;
}

function getImageAspectRatio(imageIndex) {
    const dimensions = Array.isArray(PROPERTY_IMAGE_DIMENSIONS) ? PROPERTY_IMAGE_DIMENSIONS[imageIndex] : null;
    if (!dimensions || !dimensions.width || !dimensions.height) {
        return null;
    }

    return dimensions.width / dimensions.height;
}

function shouldContainDesktopImage(imageIndex) {
    const aspectRatio = getImageAspectRatio(imageIndex);
    if (!aspectRatio) {
        return false;
    }

    return aspectRatio >= 0.85 && aspectRatio <= 1.15;
}

function isPortraitDesktopImage(imageIndex) {
    const aspectRatio = getImageAspectRatio(imageIndex);
    if (!aspectRatio) {
        return false;
    }

    return aspectRatio < 0.85;
}

function updateDesktopFrameMode(frameElement, imageIndex) {
    if (!frameElement) {
        return;
    }
}

function applyDesktopImage(frameElement, imageElement, imageIndex) {
    if (!frameElement || !imageElement || imageIndex === null || imageIndex === undefined) {
        return;
    }

    const src = PROPERTY_IMAGES[imageIndex] || '';
    imageElement.src = src;
    imageElement.alt = PROPERTY_IMAGE_ALTS[imageIndex] || PROPERTY_TITLE;
    updateDesktopFrameMode(frameElement, imageIndex);
}

function syncDesktopDualFrame() {
    const primaryTrigger = document.getElementById('desktop-primary-trigger');
    const primaryImage = document.getElementById('desktop-primary-image');
    const secondaryTrigger = document.getElementById('desktop-secondary-trigger');
    const secondaryImage = document.getElementById('desktop-secondary-image');

    if (!primaryTrigger || !primaryImage || !secondaryTrigger || !secondaryImage) {
        return;
    }

    const heroIndex = getHeroIndex();
    const secondaryIndex = getDesktopSecondaryIndex(heroIndex);

    primaryTrigger.dataset.imageIndex = heroIndex;
    applyDesktopImage(primaryTrigger, primaryImage, heroIndex);
    primaryTrigger.classList.toggle('desktop-frame-primary--single', secondaryIndex === null);

    if (secondaryIndex === null) {
        secondaryTrigger.classList.add('hidden');
    } else {
        secondaryTrigger.classList.remove('hidden');
        secondaryTrigger.dataset.imageIndex = secondaryIndex;
        applyDesktopImage(secondaryTrigger, secondaryImage, secondaryIndex);
    }
}

function normalizeImageIndex(index) {
    if (!PROPERTY_IMAGES.length) {
        return 0;
    }

    return ((index % PROPERTY_IMAGES.length) + PROPERTY_IMAGES.length) % PROPERTY_IMAGES.length;
}

function preloadImageAtIndex(index) {
    if (!PROPERTY_IMAGES.length) {
        return;
    }

    const normalizedIndex = normalizeImageIndex(index);
    const imageUrl = PROPERTY_IMAGES[normalizedIndex];
    if (!imageUrl || preloadedGalleryImages.has(imageUrl)) {
        return;
    }

    const image = new Image();
    image.src = imageUrl;
    preloadedGalleryImages.add(imageUrl);
}

function preloadAdjacentImages(index) {
    if (PROPERTY_IMAGES.length <= 1) {
        return;
    }

    preloadImageAtIndex(index);
    preloadImageAtIndex(index + 1);
    preloadImageAtIndex(index - 1);
}

function setSlideVisibility(slide, isActive) {
    if (!slide) {
        return;
    }

    slide.style.opacity = isActive ? '1' : '0';
    slide.classList.toggle('pointer-events-none', !isActive);
    slide.classList.toggle('pointer-events-auto', isActive);
    slide.setAttribute('aria-hidden', isActive ? 'false' : 'true');
}

// Carousel functionality (works for both mobile and desktop)
function nextSlide() {
    if (PROPERTY_IMAGES.length <= 1) return;
    if (isDesktopDualMode()) {
        const nextIndex = getHeroIndex() + 2;
        showCarouselSlide(nextIndex >= PROPERTY_IMAGES.length ? 0 : nextIndex);
    } else {
        showCarouselSlide((currentImageIndex + 1) % PROPERTY_IMAGES.length);
    }
    updateCarouselUI();
}

function previousSlide() {
    if (PROPERTY_IMAGES.length <= 1) return;
    if (isDesktopDualMode()) {
        const heroIndex = getHeroIndex();
        let targetIndex = heroIndex - 2;
        if (targetIndex < 0) {
            targetIndex = PROPERTY_IMAGES.length % 2 === 0 ? PROPERTY_IMAGES.length - 2 : PROPERTY_IMAGES.length - 1;
        }
        showCarouselSlide(targetIndex);
    } else {
        let targetIndex = currentImageIndex - 1;
        if (targetIndex < 0) {
            targetIndex = PROPERTY_IMAGES.length - 1;
        }
        showCarouselSlide(targetIndex);
    }
    updateCarouselUI();
}

function showCarouselSlide(targetIndex) {
    if (!PROPERTY_IMAGES.length) {
        return;
    }

    const normalizedIndex = normalizeImageIndex(targetIndex);
    if (isDesktopDualMode()) {
        currentImageIndex = normalizedIndex;
        syncDesktopDualFrame();
        preloadImageAtIndex(getHeroIndex(normalizedIndex));
        const secondaryIndex = getDesktopSecondaryIndex(getHeroIndex(normalizedIndex));
        if (secondaryIndex !== null) {
            preloadImageAtIndex(secondaryIndex);
        }
        preloadAdjacentImages(getHeroIndex(normalizedIndex));
        return;
    }

    const currentSlide = getCarouselSlide(currentImageIndex);
    const targetSlide = getCarouselSlide(normalizedIndex);

    if (currentSlide) {
        setSlideVisibility(currentSlide, false);
    }
    if (targetSlide) {
        setSlideVisibility(targetSlide, true);
        currentImageIndex = normalizedIndex;
    }

    preloadAdjacentImages(normalizedIndex);
}

function goToSlideByImage(imageIndex) {
    showCarouselSlide(imageIndex);
    updateCarouselUI();
}

function goToHeroPair(imageIndex) {
    showCarouselSlide(imageIndex);
    updateCarouselUI();
}

function syncHeroCarouselToCurrentImage() {
    showCarouselSlide(currentImageIndex);
    updateCarouselUI();
}

function updateCarouselUI() {
    const counter = document.getElementById('current-photo');
    const heroIndex = getHeroIndex();
    const secondaryHeroIndex = isDesktopDualMode() ? getDesktopSecondaryIndex(heroIndex) : null;
    if (counter) {
        counter.textContent = secondaryHeroIndex !== null ? `${heroIndex + 1}-${secondaryHeroIndex + 1}` : `${heroIndex + 1}`;
    }

    const indicators = document.querySelectorAll('.property-slide-indicator');
    indicators.forEach((indicator, index) => {
        if (index === currentImageIndex) {
            indicator.classList.remove('bg-white', 'bg-opacity-60');
            indicator.classList.add('bg-accent', 'shadow-lg');
        } else {
            indicator.classList.remove('bg-accent', 'shadow-lg');
            indicator.classList.add('bg-white', 'bg-opacity-60');
        }
    });

    const pairIndicators = document.querySelectorAll('.property-slide-pair-indicator');
    pairIndicators.forEach((indicator) => {
        const indicatorIndex = parseInt(indicator.dataset.slideIndex || '-1', 10);
        const isActive = indicatorIndex === heroIndex;
        indicator.classList.toggle('w-7', isActive);
        indicator.classList.toggle('bg-accent', isActive);
        indicator.classList.toggle('shadow-lg', isActive);
        indicator.classList.toggle('bg-white/35', !isActive);
        indicator.classList.toggle('w-2.5', !isActive);
    });

    const thumbs = document.querySelectorAll('img[data-thumb]');
    thumbs.forEach((thumb, index) => {
        const isActive = isDesktopDualMode()
            ? index === heroIndex || index === secondaryHeroIndex
            : index === currentImageIndex;

        if (isActive) {
            thumb.classList.remove('border-transparent', 'hover:border-accent/50');
            thumb.classList.add('border-accent', 'shadow-lg');
        } else {
            thumb.classList.remove('border-accent', 'shadow-lg');
            thumb.classList.add('border-transparent', 'hover:border-accent/50');
        }
    });
}

function openGallery(index) {
    const normalizedIndex = normalizeImageIndex(typeof index === 'number' ? index : currentImageIndex);
    currentImageIndex = normalizedIndex;
    syncHeroCarouselToCurrentImage();
    firePropertyGoal('property_gallery_open', { index: normalizedIndex });
    updateGalleryImage();
    document.getElementById('gallery-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeGallery() {
    document.getElementById('gallery-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
    syncHeroCarouselToCurrentImage();
}

function setupContactSidebarScroll() {
    const wrapper = document.getElementById('contact-sidebar-wrapper');
    const sidebar = document.getElementById('property-contact-form');
    const scrollBoundary = document.getElementById('same-complex-properties') || document.getElementById('similar-properties');
    if (!wrapper || !sidebar || !scrollBoundary) {
        return;
    }

    let lastY = 0;

    const getStickyTopOffset = () => {
        const mainNav = document.getElementById('main-nav');
        const gap = 24;

        if (!mainNav) {
            return gap;
        }

        const navRect = mainNav.getBoundingClientRect();
        if (!navRect.height) {
            return gap;
        }

        return Math.max(gap, Math.ceil(navRect.bottom + gap));
    };

    const onScroll = () => {
        if (window.innerWidth < 1024) {
            sidebar.style.transform = '';
            return;
        }

        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const wrapperTop = wrapper.getBoundingClientRect().top + scrollTop;
        const boundaryTop = scrollBoundary.getBoundingClientRect().top + scrollTop;
        const sidebarHeight = sidebar.offsetHeight;
        const topOffset = getStickyTopOffset();
        const sectionGap = 24;
        const maxOffset = Math.max(0, boundaryTop - sidebarHeight - sectionGap - wrapperTop);
        const currentOffset = Math.max(0, Math.min(scrollTop - wrapperTop + topOffset, maxOffset));

        if (Math.abs(currentOffset - lastY) > 1) {
            sidebar.style.transform = `translateY(${currentOffset}px)`;
            lastY = currentOffset;
        }
    };

    ['scroll', 'resize', 'orientationchange'].forEach(eventName => {
        window.addEventListener(eventName, onScroll, { passive: true });
    });

    onScroll();
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
        galleryImage.alt = PROPERTY_IMAGE_ALTS[currentImageIndex] || PROPERTY_TITLE;
        preloadAdjacentImages(currentImageIndex);
        const galleryCounter = document.getElementById('gallery-counter');
        if (galleryCounter) {
            galleryCounter.textContent = `${currentImageIndex + 1} / ${PROPERTY_IMAGES.length}`;
        }

        // Update thumbnail highlights
        const thumbs = document.querySelectorAll('.gallery-thumb');
        thumbs.forEach((thumb, index) => {
            if (index === currentImageIndex) {
                thumb.classList.add('border-accent', 'scale-105', 'shadow-lg');
                thumb.classList.remove('border-transparent');
                thumb.scrollIntoView({
                    behavior: 'smooth',
                    block: 'nearest',
                    inline: 'center',
                });
            } else {
                thumb.classList.remove('border-accent', 'scale-105', 'shadow-lg');
                thumb.classList.add('border-transparent');
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
        firePropertyGoal('property_gallery_download', { index: currentImageIndex });
    }
}

// Share property function (for carousel button)
function shareProperty() {
    firePropertyGoal('property_share_click');
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

    const numericId = parseInt(propertyId, 10);
    const favoriteState = Boolean(isFavoriteNow);
    setDetailFavoriteState(numericId, favoriteState);
    firePropertyGoal('property_favorite_toggle', {
        status: favoriteState ? 'add' : 'remove'
    });
}

// Share image function
function shareImage() {
    firePropertyGoal('property_gallery_share', { index: currentImageIndex });
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
    currentImageIndex = normalizeImageIndex(currentImageIndex + 1);
    syncHeroCarouselToCurrentImage();
    updateGalleryImage();
}

function previousImage() {
    currentImageIndex = normalizeImageIndex(currentImageIndex - 1);
    syncHeroCarouselToCurrentImage();
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

    if (!content) {
        return;
    }

    const collapsedClassCandidates = ['max-h-52', 'max-h-48', 'max-h-40', 'max-h-32', 'max-h-24'];
    if (!content.dataset.collapsedClass) {
        const foundClass = collapsedClassCandidates.find(className => content.classList.contains(className));
        if (foundClass) {
            content.dataset.collapsedClass = foundClass;
        }
    }

    const collapsedClass = content.dataset.collapsedClass || collapsedClassCandidates[0];
    const expandedClass = 'max-h-full';

    if (content.classList.contains(collapsedClass)) {
        // Expand
        collapsedClassCandidates.forEach(className => content.classList.remove(className));
        content.classList.add(expandedClass);
        if (gradient) gradient.style.opacity = '0';
        if (toggleText) toggleText.textContent = TRANSLATIONS.collapse;
        if (toggleIcon) {
            toggleIcon.classList.remove('fa-chevron-down');
            toggleIcon.classList.add('fa-chevron-up');
        }
    } else {
        // Collapse
        content.classList.remove(expandedClass);
        collapsedClassCandidates.forEach(className => content.classList.remove(className));
        content.classList.add(collapsedClass);
        if (gradient) gradient.style.opacity = '1';
        if (toggleText) toggleText.textContent = TRANSLATIONS.showFull;
        if (toggleIcon) {
            toggleIcon.classList.remove('fa-chevron-up');
            toggleIcon.classList.add('fa-chevron-down');
        }
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
            priceText = `${currencySymbol}${Math.round(rentPrice).toLocaleString()}/${LABEL_PER_MONTH}`;
        } else if (PROPERTY_DATA.deal_type === 'both') {
            if (salePrice) {
                priceText = `${currencySymbol}${Math.round(salePrice).toLocaleString()}`;
            } else if (rentPrice) {
                priceText = `${currencySymbol}${Math.round(rentPrice).toLocaleString()}/${LABEL_PER_MONTH}`;
            }
        }

        if (priceText) {
            mainPriceEl.textContent = priceText;
        } else {
            mainPriceEl.textContent = LABEL_PRICE_ON_REQUEST;
        }
    }

    // Update price per square meter
    const pricePerSqmEl = document.getElementById('price-per-sqm');

    if (pricePerSqmEl && PROPERTY_DATA.area_total && salePrice) {
        if (PROPERTY_DATA.deal_type !== 'rent') {
            const pricePerSqm = Math.round(salePrice / PROPERTY_DATA.area_total);
            const pricePerSqmText = `${pricePerSqm.toLocaleString()} ${currencySymbol}/${LABEL_PER_SQM}`;
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
    firePropertyGoal('property_details_modal_open');
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
    firePropertyGoal('property_viewing_modal_open');
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
    firePropertyGoal('property_consultation_modal_open');
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
    syncDesktopDualFrame();
    preloadAdjacentImages(currentImageIndex);
    updateCarouselUI();

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

    const desktopPrimaryTrigger = document.getElementById('desktop-primary-trigger');
    const desktopSecondaryTrigger = document.getElementById('desktop-secondary-trigger');
    [desktopPrimaryTrigger, desktopSecondaryTrigger].forEach(trigger => {
        if (!trigger) {
            return;
        }
        trigger.addEventListener('click', function () {
            const targetIndex = parseInt(this.dataset.imageIndex || `${currentImageIndex}`, 10);
            openGallery(Number.isNaN(targetIndex) ? currentImageIndex : targetIndex);
        });
    });

    ['resize', 'orientationchange'].forEach(eventName => {
        window.addEventListener(eventName, syncHeroCarouselToCurrentImage, { passive: true });
    });

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

    setupContactSidebarScroll();

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


if (typeof document !== 'undefined') {
    document.addEventListener('click', function (event) {
        const modal = document.getElementById('gallery-modal');
        if (!modal || modal.classList.contains('hidden')) {
            return;
        }
        const isBackdrop = event.target.hasAttribute('data-gallery-backdrop');
        const insideContent = event.target.closest('[data-gallery-content]');
        if (isBackdrop && !insideContent) {
            closeGallery();
        }
    });
}
