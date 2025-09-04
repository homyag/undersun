// Reviews Carousel - Contact Form & Reviews Section
document.addEventListener('DOMContentLoaded', function() {
    // Reviews data
    const reviews = [
        {
            name: 'Александр К.',
            rating: 5.0,
            text: 'Отличная работа команды! Помогли подобрать квартиру в Патонге, провели через все этапы сделки. Особенно благодарен Богдану за профессионализм и внимание к деталям.',
            shortText: 'Отличная работа команды! Помогли подобрать квартиру в Патонге...',
            date: '2 недели назад'
        },
        {
            name: 'Marina S.',
            rating: 5.0,
            text: 'Купили виллу в Черн Талае через Undersun Estate. Кирилл провёл отличную презентацию проектов, всё объяснил понятно. Процесс прошёл гладко, без неприятных сюрпризов.',
            shortText: 'Купили виллу в Черн Талае через Undersun Estate. Кирилл провёл отличную презентацию...',
            date: '1 месяц назад'
        },
        {
            name: 'Dmitry R.',
            rating: 4.0,
            text: 'Хороший сервис, адекватные цены. Виталий помог с выбором кондо для инвестиций. Единственное - процесс занял чуть больше времени чем ожидалось, но результат хороший.',
            shortText: 'Хороший сервис, адекватные цены. Виталий помог с выбором кондо...',
            date: '3 недели назад'
        },
        {
            name: 'Elena P.',
            rating: 5.0,
            text: 'Очень довольны покупкой! Команда профессиональная, всегда были на связи. Помогли с оформлением всех документов. Рекомендую для покупки недвижимости в Таиланде.',
            shortText: 'Очень довольны покупкой! Команда профессиональная, всегда были на связи...',
            date: '1 неделя назад'
        },
        {
            name: 'Michael B.',
            rating: 5.0,
            text: 'Great experience working with Undersun Estate team. Professional approach, good selection of properties. Bogdan was very helpful throughout the process. Highly recommended!',
            shortText: 'Great experience working with Undersun Estate team. Professional approach...',
            date: '5 дней назад'
        },
        {
            name: 'Ольга М.',
            rating: 5.0,
            text: 'Купили квартиру в новом проекте в Камале. Все прошло отлично! Особенно приятно было работать с русскоговорящими специалистами. Спасибо команде за поддержку!',
            shortText: 'Купили квартиру в новом проекте в Камале. Все прошло отлично!...',
            date: '2 месяца назад'
        }
    ];

    let currentIndex = 0;
    let autoplayInterval;

    // DOM elements
    const mainReviewName = document.getElementById('main-review-name');
    const mainReviewStars = document.getElementById('main-review-stars');
    const mainReviewRating = document.getElementById('main-review-rating');
    const mainReviewText = document.getElementById('main-review-text');
    const mainReviewDate = document.getElementById('main-review-date');
    
    const secondaryReviewName = document.getElementById('secondary-review-name');
    const secondaryReviewStars = document.getElementById('secondary-review-stars');
    const secondaryReviewRating = document.getElementById('secondary-review-rating');
    const secondaryReviewText = document.getElementById('secondary-review-text');
    const secondaryReviewDate = document.getElementById('secondary-review-date');

    // Generate stars HTML
    function generateStars(rating) {
        let starsHtml = '';
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 !== 0;
        
        for (let i = 0; i < fullStars; i++) {
            starsHtml += '<i class="fas fa-star"></i>';
        }
        
        if (hasHalfStar) {
            starsHtml += '<i class="fas fa-star-half-alt"></i>';
        }
        
        const emptyStars = 5 - Math.ceil(rating);
        for (let i = 0; i < emptyStars; i++) {
            starsHtml += '<i class="far fa-star"></i>';
        }
        
        return starsHtml;
    }

    // Update review content
    function updateReviews() {
        const mainReview = reviews[currentIndex];
        const secondaryReview = reviews[(currentIndex + 1) % reviews.length];

        // Update main review
        mainReviewName.textContent = mainReview.name;
        mainReviewStars.innerHTML = generateStars(mainReview.rating);
        mainReviewRating.textContent = mainReview.rating.toFixed(1);
        mainReviewText.textContent = mainReview.text;
        mainReviewDate.textContent = '• ' + mainReview.date;

        // Update secondary review
        secondaryReviewName.textContent = secondaryReview.name;
        secondaryReviewStars.innerHTML = generateStars(secondaryReview.rating);
        secondaryReviewRating.textContent = secondaryReview.rating.toFixed(1);
        secondaryReviewText.textContent = secondaryReview.shortText;
        secondaryReviewDate.textContent = '• ' + secondaryReview.date;

        // Update navigation dots
        updateDots();
    }

    // Update navigation dots
    function updateDots() {
        for (let i = 0; i < reviews.length; i++) {
            const dot = document.getElementById(`dot-${i}`);
            if (dot) {
                if (i === currentIndex) {
                    dot.classList.remove('bg-gray-300');
                    dot.classList.add('bg-accent');
                } else {
                    dot.classList.remove('bg-accent');
                    dot.classList.add('bg-gray-300');
                }
            }
        }
    }

    // Go to next review
    function nextReview() {
        currentIndex = (currentIndex + 1) % reviews.length;
        updateReviews();
    }

    // Go to specific review
    function goToReview(index) {
        currentIndex = index;
        updateReviews();
    }

    // Start autoplay
    function startAutoplay() {
        autoplayInterval = setInterval(nextReview, 5000); // Change every 5 seconds
    }

    // Stop autoplay
    function stopAutoplay() {
        if (autoplayInterval) {
            clearInterval(autoplayInterval);
        }
    }

    // Initialize carousel
    function initCarousel() {
        updateReviews();

        // Add click listeners to dots
        for (let i = 0; i < reviews.length; i++) {
            const dot = document.getElementById(`dot-${i}`);
            if (dot) {
                dot.addEventListener('click', () => {
                    stopAutoplay();
                    goToReview(i);
                    startAutoplay();
                });
            }
        }

        // Add click listener to secondary review (to promote it to main)
        const secondaryReview = document.getElementById('secondary-review');
        if (secondaryReview) {
            secondaryReview.addEventListener('click', () => {
                stopAutoplay();
                nextReview();
                startAutoplay();
            });
            
            // Add cursor pointer to indicate it's clickable
            secondaryReview.style.cursor = 'pointer';
        }

        // Pause autoplay on hover
        const carousel = document.getElementById('reviews-carousel');
        if (carousel) {
            carousel.addEventListener('mouseenter', stopAutoplay);
            carousel.addEventListener('mouseleave', startAutoplay);
        }

        // Start autoplay
        startAutoplay();
    }

    // Initialize when DOM is ready
    initCarousel();
});