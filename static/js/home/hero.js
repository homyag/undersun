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

    const staticBackground = document.querySelector('.hero-static-bg');
    let currentSlide = -1;
    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
    let slideInterval = null;

    function ensureSlideBackground(slide, { highPriority = false, onLoad } = {}) {
        if (!slide) {
            return;
        }

        const lazySrc = slide.dataset.lazyBg || slide.dataset.imageSrc || slide.dataset.placeholder || null;
        if (!lazySrc) {
            if (typeof onLoad === 'function') {
                onLoad();
            }
            return;
        }

        const markLoaded = () => {
            if (!slide.style.backgroundImage) {
                slide.style.backgroundImage = `url('${lazySrc}')`;
            }
            slide.dataset.bgLoaded = 'true';
            if (typeof onLoad === 'function') {
                onLoad();
            }
        };

        if (slide.dataset.bgLoaded === 'true') {
            markLoaded();
            return;
        }

        if (!slide.style.backgroundImage) {
            slide.style.backgroundImage = `url('${lazySrc}')`;
        }

        const img = new Image();
        img.decoding = 'async';
        img.loading = 'eager';
        if (img.fetchPriority !== undefined) {
            try {
                img.fetchPriority = highPriority ? 'high' : 'low';
            } catch (e) {
                // ignore unsupported assignment
            }
        }
        img.addEventListener('load', markLoaded, { once: true });
        img.addEventListener('error', markLoaded, { once: true });
        img.src = lazySrc;
    }

    function setSlideVisibility() {
        slides.forEach((slide, index) => {
            slide.style.opacity = currentSlide >= 0 && index === currentSlide ? '1' : '0';
        });
    }

    function hideStaticBackground() {
        if (!staticBackground) {
            return;
        }
        staticBackground.classList.add('hero-static-bg--hidden');
    }

    function nextSlide() {
        if (!slides.length || slides.length === 1) {
            return;
        }

        const previousSlide = currentSlide >= 0 ? slides[currentSlide] : null;
        if (previousSlide) {
            previousSlide.style.opacity = '0';
        }

        currentSlide = (currentSlide + 1) % slides.length;
        const targetSlide = slides[currentSlide];
        ensureSlideBackground(targetSlide, {
            onLoad: () => {
                hideStaticBackground();
                targetSlide.style.opacity = '1';
            }
        });
    }

    function startSlider() {
        if (slides.length <= 1 || (prefersReducedMotion && prefersReducedMotion.matches)) {
            return;
        }

        if (!slideInterval) {
            slideInterval = setInterval(nextSlide, 12000);
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
            currentSlide = -1;
            slides.forEach(slide => {
                slide.style.opacity = '0';
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

    ensureSlideBackground(staticBackground, { highPriority: true });
    setSlideVisibility();
    startSlider();
}

// Hero Section Background Slideshow
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeHeroSection);
} else {
    initializeHeroSection();
}
