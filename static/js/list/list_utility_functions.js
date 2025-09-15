// Price presets function
function setPriceRange(min, max) {
    const minInput = document.querySelector('input[name="min_price"]');
    const maxInput = document.querySelector('input[name="max_price"]');
    
    if (minInput) minInput.value = min || '';
    if (maxInput) maxInput.value = max || '';
    
    // Trigger filter update
    if (typeof updatePropertyFilters === 'function') {
        updatePropertyFilters();
    }
}

function updateSort(value) {
    // Update sort field in form
    const form = document.getElementById('filter-form');
    const sortInput = form.querySelector('input[name="sort"]');
    
    if (sortInput) {
        sortInput.value = value;
    }
    
    // Submit the form directly
    form.submit();
}

// Update results counter 
function updateResultsCounter() {
    const resultsCountElement = document.querySelector('.results-count');
    if (!resultsCountElement) return;
    
    // Get total count from data attribute (server-provided total count)
    const totalCount = parseInt(resultsCountElement.dataset.totalCount) || 0;
    
    // Update counter text with proper Russian pluralization
    let counterText;
    if (totalCount === 0) {
        counterText = 'Объекты не найдены';
    } else if (totalCount === 1) {
        counterText = 'Найден 1 объект';
    } else if (totalCount >= 2 && totalCount <= 4) {
        counterText = `Найдено ${totalCount} объекта`;
    } else {
        counterText = `Найдено ${totalCount} объектов`;
    }
    
    resultsCountElement.textContent = counterText;
    console.log(`Updated results counter: ${totalCount} total properties found (${document.querySelectorAll('.property-card').length} on current page)`);
}