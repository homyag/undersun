// The global favorites helpers are defined in base.html / main.js.
// If they are missing (e.g. in isolated bundles), provide a minimal fallback.
(function() {
    if (typeof window.toggleFavorite === 'undefined') {
        window.toggleFavorite = function(propertyId) {
            const favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
            const id = parseInt(propertyId, 10);
            if (!Number.isInteger(id)) {
                return false;
            }
            const index = favorites.indexOf(id);

            let isFavorite = false;
            if (index > -1) {
                favorites.splice(index, 1);
            } else {
                favorites.push(id);
                isFavorite = true;
            }

            localStorage.setItem('favorites', JSON.stringify(favorites));

            if (typeof window.updateFavoriteButtons === 'function') {
                window.updateFavoriteButtons(id, isFavorite);
            }
            if (typeof window.updateFavoritesCounter === 'function') {
                window.updateFavoritesCounter();
            }

            return isFavorite;
        };
    }
})();
