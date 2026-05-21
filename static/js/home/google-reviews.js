(function() {
  const dataScript = document.getElementById('google-reviews-data');
  const carousel = document.getElementById('google-reviews-carousel');

  if (!dataScript || !carousel) {
    return;
  }

  let reviews = [];
  try {
    reviews = JSON.parse(dataScript.textContent || '[]');
  } catch (error) {
    return;
  }

  if (!Array.isArray(reviews) || reviews.length === 0) {
    return;
  }

  const googleMapsUrl = carousel.dataset.googleMapsUrl || '#';
  let currentIndex = 0;

  function generateStars(rating) {
    const safeRating = Math.max(0, Math.min(5, Number(rating) || 0));
    const fullStars = Math.floor(safeRating);
    const hasHalfStar = safeRating % 1 !== 0;
    let stars = '';

    for (let index = 0; index < fullStars; index += 1) {
      stars += '<i class="fas fa-star"></i>';
    }

    if (hasHalfStar) {
      stars += '<i class="fas fa-star-half-alt"></i>';
    }

    for (let index = Math.ceil(safeRating); index < 5; index += 1) {
      stars += '<i class="far fa-star"></i>';
    }

    return stars;
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value || '';
    }
  }

  function setAvatar(prefix, review, sizeClass) {
    const photo = document.getElementById(`${prefix}-photo`);
    const avatar = document.getElementById(`${prefix}-avatar`);

    if (!photo || !avatar) {
      return;
    }

    if (review.profile_photo_url) {
      photo.src = review.profile_photo_url;
      photo.alt = review.name || 'Google review author';
      photo.className = `${sizeClass} rounded-full object-cover bg-gray-100`;
      avatar.classList.add('hidden');
      return;
    }

    photo.classList.add('hidden');
    avatar.textContent = review.avatar || 'G';
    avatar.className = `${sizeClass} bg-gradient-to-br ${review.avatar_color || 'from-blue-400 to-blue-600'} rounded-full flex items-center justify-center text-white font-bold ${prefix === 'main-review' ? 'text-base' : 'text-sm'}`;
  }

  function updateMainReview(review) {
    setAvatar('main-review', review, 'w-12 h-12');
    setText('main-review-author', review.name);
    setText('main-review-date', review.relative_time);
    setText('main-review-text', review.text);
    setText('main-review-rating', review.rating_display || Number(review.rating || 0).toFixed(1));

    const authorLink = document.getElementById('main-review-author');
    if (authorLink) {
      authorLink.href = review.author_url || googleMapsUrl;
    }

    const stars = document.getElementById('main-review-stars');
    if (stars) {
      stars.innerHTML = generateStars(review.rating);
    }
  }

  function updateNextReview(review) {
    if (!review) {
      return;
    }

    setAvatar('next-review', review, 'w-10 h-10');
    setText('next-review-author', review.name);
    setText('next-review-date', review.relative_time);
    setText('next-review-text', review.short_text || review.text);
  }

  function updateReviews() {
    const currentReview = reviews[currentIndex];
    const nextReview = reviews[(currentIndex + 1) % reviews.length];

    updateMainReview(currentReview);
    updateNextReview(nextReview);
  }

  function showNextReview() {
    currentIndex = (currentIndex + 1) % reviews.length;
    updateReviews();
  }

  function showPrevReview() {
    currentIndex = (currentIndex - 1 + reviews.length) % reviews.length;
    updateReviews();
  }

  const nextButton = document.getElementById('google-reviews-next');
  const prevButton = document.getElementById('google-reviews-prev');
  const nextPreview = document.getElementById('next-review');

  if (nextButton) {
    nextButton.addEventListener('click', showNextReview);
  }

  if (prevButton) {
    prevButton.addEventListener('click', showPrevReview);
  }

  if (nextPreview) {
    nextPreview.addEventListener('click', showNextReview);
  }

  updateReviews();

  if (reviews.length > 1) {
    window.setInterval(showNextReview, 5000);
  }
})();
