// Hero Section Responsive Height Adjustment
function adjustHeroHeight() {
    const heroSection = document.querySelector('.hero-section');
    if (!heroSection) return;

    if (window.innerWidth >= 1440) {
        // Large desktop (1440px+): Full viewport height
        heroSection.style.minHeight = '100vh';
        heroSection.style.paddingTop = '0px';
    } else if (window.innerWidth >= 1024) {
        // Desktop: account for contact bar + navigation
        heroSection.style.minHeight = 'calc(100vh - 120px)';
        heroSection.style.paddingTop = '120px';
    } else {
        // Mobile: only navigation
        heroSection.style.minHeight = 'calc(100vh - 64px)';
        heroSection.style.paddingTop = '64px';
    }
}

// Hero Section Background Slideshow
document.addEventListener('DOMContentLoaded', function () {
    // Adjust height on load
    adjustHeroHeight();

    // Adjust height on resize
    window.addEventListener('resize', adjustHeroHeight);

    const slides = document.querySelectorAll('.hero-slide');
    let currentSlide = 0;

    function nextSlide() {
        // Hide current slide
        slides[currentSlide].style.opacity = '0';

        // Move to next slide
        currentSlide = (currentSlide + 1) % slides.length;

        // Show next slide
        slides[currentSlide].style.opacity = '1';
    }

    // Auto change slides every 10 seconds
    setInterval(nextSlide, 10000);

    // Preload images for smoother transitions
    slides.forEach(function (slide) {
        const bgImage = slide.style.backgroundImage;
        if (bgImage) {
            const imageUrl = bgImage.match(/url\(['"]?(.*?)['"]?\)/)[1];
            const img = new Image();
            img.src = imageUrl;
        }
    });
});