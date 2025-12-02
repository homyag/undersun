// Hero Section Responsive Height Adjustment
function adjustHeroHeight() {
    const heroSection = document.querySelector('.hero-section');
    if (!heroSection) return;

    if (window.innerWidth >= 1440) {
        // Large desktop (1440px+): Full viewport height, account for header stack
        heroSection.style.minHeight = '100vh';
        heroSection.style.paddingTop = '120px';
    } else if (window.innerWidth >= 1024) {
        // Desktop: leave room for contact bar + navigation
        heroSection.style.minHeight = '100vh';
        heroSection.style.paddingTop = '120px';
    } else if (window.innerWidth >= 768) {
        // Tablet: navigation height only
        heroSection.style.minHeight = '100vh';
        heroSection.style.paddingTop = '64px';
    } else {
        // Mobile: maintain clearance from sticky navigation without large gap
        heroSection.style.minHeight = '100vh';
        heroSection.style.paddingTop = '32px';
    }
}

function initializeHeroSection() {
    adjustHeroHeight();
    window.addEventListener('resize', adjustHeroHeight);

    const slides = document.querySelectorAll('.hero-slide');
    if (!slides.length) {
        return;
    }

    const lazySlides = Array.from(slides).filter(slide => slide.dataset.lazyBg);
    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
    let currentSlide = 0;
    let slideInterval = null;

    function ensureSlideBackground(slide) {
        if (!slide || slide.dataset.bgLoaded === 'true') {
            return;
        }

        const lazySrc = slide.dataset.lazyBg;
        if (!lazySrc) {
            return;
        }

        const img = new Image();
        img.decoding = 'async';
        img.loading = 'eager';
        img.addEventListener('load', () => {
            slide.style.backgroundImage = `url('${lazySrc}')`;
            slide.dataset.bgLoaded = 'true';
        });
        img.src = lazySrc;
    }

    function hydrateLazyHeroSlides() {
        lazySlides.forEach(slide => ensureSlideBackground(slide));
    }

    function scheduleHeroBackgroundHydration() {
        if (!lazySlides.length) {
            return;
        }

        const loadBackgrounds = () => {
            if (document.readyState === 'complete') {
                hydrateLazyHeroSlides();
            } else {
                window.addEventListener('load', () => hydrateLazyHeroSlides(), { once: true });
            }
        };

        if ('requestIdleCallback' in window) {
            requestIdleCallback(hydrateLazyHeroSlides, { timeout: 2000 });
        } else {
            setTimeout(loadBackgrounds, 200);
        }
    }

    function nextSlide() {
        if (!slides.length || slides.length === 1) {
            return;
        }

        slides[currentSlide].style.opacity = '0';
        currentSlide = (currentSlide + 1) % slides.length;
        ensureSlideBackground(slides[currentSlide]);
        slides[currentSlide].style.opacity = '1';
    }

    function startSlider() {
        if (slides.length <= 1 || (prefersReducedMotion && prefersReducedMotion.matches)) {
            return;
        }

        if (!slideInterval) {
            slideInterval = setInterval(nextSlide, 10000);
        }
    }

    function stopSlider() {
        if (slideInterval) {
            clearInterval(slideInterval);
            slideInterval = null;
        }
    }

    const motionChangeHandler = (event) => {
        if (event.matches) {
            stopSlider();
            slides.forEach((slide, index) => {
                slide.style.opacity = index === 0 ? '1' : '0';
            });
        } else {
            startSlider();
        }
    };

    if (prefersReducedMotion && typeof prefersReducedMotion.addEventListener === 'function') {
        prefersReducedMotion.addEventListener('change', motionChangeHandler);
    } else if (prefersReducedMotion && typeof prefersReducedMotion.addListener === 'function') {
        prefersReducedMotion.addListener(motionChangeHandler);
    }

    ensureSlideBackground(slides[currentSlide]);
    scheduleHeroBackgroundHydration();
    startSlider();
}

// Hero Section Background Slideshow
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeHeroSection);
} else {
    initializeHeroSection();
}
