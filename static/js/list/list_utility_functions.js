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
    if (!form) {
        return;
    }
    const sortInput = form.querySelector('input[name="sort"]');
    
    if (sortInput) {
        sortInput.value = value;
    }

    if (typeof window.dispatchMetrikaGoal === 'function') {
        window.dispatchMetrikaGoal('catalog_sort_change', { sort: value });
    }

    if (typeof window.submitPropertyFilters === 'function') {
        window.submitPropertyFilters({ trigger: 'sort', origin: 'sort' });
    } else if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
    } else {
        form.submit();
    }
}

function getResultsCountTranslations() {
    const translations = window.djangoTranslations || {};
    if (!translations.resultsCount) {
        return null;
    }

    return translations.resultsCount;
}

function getLocalizedResultsCountText(element, count) {
    if (!element) {
        return '';
    }

    const translationSet = getResultsCountTranslations();

    if (count === 0) {
        if (translationSet && translationSet.zero) {
            return translationSet.zero;
        }
        return 'No properties found';
    }

    if (translationSet) {
        const locale = document.documentElement.lang || 'ru';
        let pluralCategory = 'other';

        if (typeof Intl !== 'undefined' && Intl.PluralRules) {
            try {
                const pluralRules = new Intl.PluralRules(locale);
                pluralCategory = pluralRules.select(count);
            } catch (error) {
                pluralCategory = 'other';
            }
        }

        const normalizedCategory = pluralCategory.toLowerCase();
        let template = null;

        if (normalizedCategory === 'one' && translationSet.one) {
            template = translationSet.one;
        } else if ((normalizedCategory === 'few' || normalizedCategory === 'two') && translationSet.few) {
            template = translationSet.few;
        } else if (translationSet.many) {
            template = translationSet.many;
        }

        if (template) {
            return template.replace('%(count)s', count).replace('%(counter)s', count);
        }
    }

    return count === 1 ? `Found ${count} property` : `Found ${count} properties`;
}

window.getLocalizedResultsCountText = getLocalizedResultsCountText;

// Update results counter 
function updateResultsCounter() {
    const resultsCountElement = document.querySelector('.results-count');
    if (!resultsCountElement) return;

    const totalCount = parseInt(resultsCountElement.dataset.totalCount) || 0;
    const localizedText = getLocalizedResultsCountText(resultsCountElement, totalCount);

    if (localizedText) {
        resultsCountElement.textContent = localizedText;
        resultsCountElement.dataset.totalCount = totalCount;
    }
}
