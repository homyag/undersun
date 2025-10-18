// Favorites functionality
function toggleFavorite(propertyId) {
    const icon = document.getElementById(`favorite-${propertyId}`);
    if (!icon) return;
    
    // Get current favorites from localStorage
    let favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
    
    if (favorites.includes(propertyId)) {
        // Remove from favorites
        favorites = favorites.filter(id => id !== propertyId);
        icon.classList.remove('fas');
        icon.classList.add('far');
    } else {
        // Add to favorites
        favorites.push(propertyId);
        icon.classList.remove('far');
        icon.classList.add('fas');
    }
    
    // Save to localStorage
    localStorage.setItem('favorites', JSON.stringify(favorites));
    
    // Update favorites counter in header
    updateFavoritesCounter(favorites.length);
    
    // Optional: Show notification
    showNotification(favorites.includes(propertyId) ? 
        'Добавлено в избранное' : 
        'Удалено из избранного'
    );
}

function formatFavoritesCount(count) {
    return count > 99 ? '99+' : count;
}

// Update favorites counter in header
function updateFavoritesCounter(count) {
    const counters = document.querySelectorAll('.favorites-count');
    counters.forEach(counter => {
        counter.textContent = formatFavoritesCount(count);

        if (count > 0) {
            counter.classList.remove('hidden');
            counter.classList.add('inline-flex');
            counter.style.display = 'inline-flex';
        } else {
            counter.classList.add('hidden');
            counter.style.display = 'none';
        }
    });
}

// Simple notification function
function showNotification(message) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'fixed top-4 right-4 bg-primary text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-all duration-300 transform translate-x-full';
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Slide in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 100);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}
