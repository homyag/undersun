(function () {
  'use strict';

  const SELECTOR = '.blog-property-picker';
  let modal = null;
  let activePicker = null;
  let currentPage = 1;
  let hasNextPage = false;
  let lastResults = new Map();
  let searchTimer = null;

  const text = {
    title: 'Выбор объекта недвижимости',
    subtitle: 'Найдите объект по названию, ID, комплексу, району или локации.',
    searchPlaceholder: 'Например: Anchan, 127, Bang Tao, villa',
    allTypes: 'Все типы',
    sale: 'Продажа',
    rent: 'Аренда',
    activeOnly: 'Только активные',
    includeInactive: 'Показывать скрытые',
    close: 'Закрыть',
    loading: 'Ищем объекты...',
    empty: 'Ничего не найдено. Попробуйте другой запрос или включите скрытые объекты.',
    choose: 'Выбрать',
    openSite: 'Открыть на сайте',
    selected: 'Выбранный объект',
    noImage: 'Нет фото',
    loadMore: 'Показать еще',
    clear: 'Очистить',
    notSelected: 'Объект не выбран',
    searchHint: 'Нажмите “Выбрать объект”, чтобы найти карточку по названию, ID, району или комплексу.',
    deleteLink: 'Удалить',
    undoDelete: 'Отменить',
    deletePending: 'Будет удалено после сохранения',
    deleteColumn: 'Действие',
  };

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function getInput(picker) {
    return picker.querySelector('.blog-property-picker__input');
  }

  function getSearchUrl(picker) {
    return picker.dataset.searchUrl;
  }

  function buildUrl(baseUrl, params) {
    const url = new URL(baseUrl, window.location.origin);
    Object.keys(params).forEach((key) => {
      const value = params[key];
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value);
      }
    });
    return url.toString();
  }

  function fetchJson(url) {
    return fetch(url, {
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    }).then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    });
  }

  function renderImage(property) {
    if (property.image_url) {
      return `<img src="${escapeHtml(property.image_url)}" alt="" loading="lazy">`;
    }
    return `<div class="blog-property-picker__no-image">${text.noImage}</div>`;
  }

  function renderTranslationBadges(property) {
    const translations = property.translations || {};
    return ['ru', 'en', 'th'].map((language) => {
      const isReady = Boolean(translations[language]);
      return `
        <span class="blog-property-picker__translation ${isReady ? 'is-ready' : 'is-missing'}">
          ${language.toUpperCase()}
        </span>
      `;
    }).join('');
  }

  function renderMeta(property) {
    const parts = [
      property.property_type,
      property.deal_type,
      property.location,
    ].filter(Boolean);
    return parts.map(escapeHtml).join(' · ');
  }

  function renderFacts(property) {
    const facts = [];
    if (property.legacy_id) {
      facts.push(`ID ${escapeHtml(property.legacy_id)}`);
    } else if (property.id) {
      facts.push(`#${escapeHtml(property.id)}`);
    }
    if (property.complex_name) {
      facts.push(escapeHtml(property.complex_name));
    }
    if (property.bedrooms) {
      facts.push(`${escapeHtml(property.bedrooms)} сп.`);
    }
    if (property.area_total) {
      facts.push(`${escapeHtml(property.area_total)} м²`);
    }
    return facts.join(' · ');
  }

  function renderSelected(picker, property) {
    const preview = picker.querySelector('[data-property-picker-preview]');
    const clearButton = picker.querySelector('[data-property-picker-clear]');

    if (!property) {
      preview.innerHTML = `
        <div class="blog-property-picker__empty">
          <strong>${text.notSelected}</strong>
          <span>${text.searchHint}</span>
        </div>
      `;
      if (clearButton) {
        clearButton.hidden = true;
      }
      return;
    }

    preview.innerHTML = `
      <div class="blog-property-picker__selected">
        <div class="blog-property-picker__thumb">${renderImage(property)}</div>
        <div class="blog-property-picker__selected-body">
          <div class="blog-property-picker__eyebrow">${text.selected}</div>
          <strong>${escapeHtml(property.title)}</strong>
          <span>${renderMeta(property)}</span>
          <span>${renderFacts(property)}</span>
          <div class="blog-property-picker__badges">
            <span class="blog-property-picker__status ${property.is_active ? 'is-active' : 'is-hidden'}">
              ${property.is_active ? 'Активен' : 'Скрыт'}
            </span>
            ${renderTranslationBadges(property)}
          </div>
          <div class="blog-property-picker__selected-footer">
            <span class="blog-property-picker__price">${escapeHtml(property.price)}</span>
            <a href="${escapeHtml(property.url)}" target="_blank" rel="noopener">${text.openSite}</a>
          </div>
        </div>
      </div>
    `;

    if (clearButton) {
      clearButton.hidden = false;
    }
  }

  function loadSelectedPreview(picker) {
    const input = getInput(picker);
    const selectedId = input && input.value;
    if (!selectedId) {
      renderSelected(picker, null);
      return;
    }

    fetchJson(buildUrl(getSearchUrl(picker), { ids: selectedId }))
      .then((data) => {
        renderSelected(picker, data.results && data.results[0]);
      })
      .catch(() => {
        renderSelected(picker, null);
      });
  }

  function ensureModal() {
    if (modal) {
      return modal;
    }

    document.body.insertAdjacentHTML('beforeend', `
      <div class="blog-property-picker-modal" id="blog-property-picker-modal" hidden>
        <div class="blog-property-picker-modal__backdrop" data-picker-close></div>
        <div class="blog-property-picker-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="blog-property-picker-modal-title">
          <div class="blog-property-picker-modal__header">
            <div>
              <h2 id="blog-property-picker-modal-title">${text.title}</h2>
              <p>${text.subtitle}</p>
            </div>
            <button type="button" class="blog-property-picker-modal__close" data-picker-close aria-label="${text.close}">×</button>
          </div>
          <div class="blog-property-picker-modal__toolbar">
            <input type="search" class="blog-property-picker-modal__search" placeholder="${text.searchPlaceholder}" autocomplete="off">
            <select class="blog-property-picker-modal__type" aria-label="Тип объекта">
              <option value="">${text.allTypes}</option>
              <option value="villa">Villa</option>
              <option value="condo">Condo</option>
              <option value="townhouse">Townhouse</option>
              <option value="land">Land</option>
            </select>
            <select class="blog-property-picker-modal__deal" aria-label="Тип сделки">
              <option value="">Все сделки</option>
              <option value="sale">${text.sale}</option>
              <option value="rent">${text.rent}</option>
            </select>
            <label class="blog-property-picker-modal__checkbox">
              <input type="checkbox" class="blog-property-picker-modal__inactive">
              <span>${text.includeInactive}</span>
            </label>
          </div>
          <div class="blog-property-picker-modal__results" data-picker-results></div>
          <div class="blog-property-picker-modal__footer">
            <button type="button" class="button blog-property-picker-modal__more" data-picker-more hidden>${text.loadMore}</button>
          </div>
        </div>
      </div>
    `);

    modal = document.getElementById('blog-property-picker-modal');
    modal.querySelectorAll('[data-picker-close]').forEach((button) => {
      button.addEventListener('click', closeModal);
    });
    modal.querySelector('[data-picker-more]').addEventListener('click', () => {
      currentPage += 1;
      runSearch(true);
    });
    modal.querySelector('[data-picker-results]').addEventListener('click', (event) => {
      const selectButton = event.target.closest('[data-picker-select]');
      if (!selectButton || !activePicker) {
        return;
      }

      const property = lastResults.get(String(selectButton.dataset.propertyId));
      if (!property) {
        return;
      }

      const input = getInput(activePicker);
      input.value = property.id;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      renderSelected(activePicker, property);
      closeModal();
    });

    ['input', 'change'].forEach((eventName) => {
      modal.querySelector('.blog-property-picker-modal__search').addEventListener(eventName, debounceSearch);
      modal.querySelector('.blog-property-picker-modal__type').addEventListener(eventName, debounceSearch);
      modal.querySelector('.blog-property-picker-modal__deal').addEventListener(eventName, debounceSearch);
      modal.querySelector('.blog-property-picker-modal__inactive').addEventListener(eventName, debounceSearch);
    });

    modal.querySelector('.blog-property-picker-modal__search').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        runSearch(false);
      }
      if (event.key === 'Escape') {
        closeModal();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && modal && !modal.hidden) {
        closeModal();
      }
    });

    return modal;
  }

  function openModal(picker) {
    activePicker = picker;
    currentPage = 1;
    hasNextPage = false;
    lastResults = new Map();

    const currentModal = ensureModal();
    currentModal.hidden = false;
    document.body.classList.add('blog-property-picker-is-open');
    currentModal.querySelector('.blog-property-picker-modal__search').focus();
    runSearch(false);
  }

  function closeModal() {
    if (!modal) {
      return;
    }
    modal.hidden = true;
    document.body.classList.remove('blog-property-picker-is-open');
    activePicker = null;
  }

  function debounceSearch() {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      currentPage = 1;
      runSearch(false);
    }, 250);
  }

  function getSearchParams() {
    return {
      q: modal.querySelector('.blog-property-picker-modal__search').value.trim(),
      property_type: modal.querySelector('.blog-property-picker-modal__type').value,
      deal_type: modal.querySelector('.blog-property-picker-modal__deal').value,
      include_inactive: modal.querySelector('.blog-property-picker-modal__inactive').checked ? '1' : '',
      page: currentPage,
    };
  }

  function runSearch(append) {
    if (!activePicker || !modal) {
      return;
    }

    const resultsContainer = modal.querySelector('[data-picker-results]');
    const moreButton = modal.querySelector('[data-picker-more]');
    if (!append) {
      resultsContainer.innerHTML = `<div class="blog-property-picker-modal__state">${text.loading}</div>`;
      moreButton.hidden = true;
      lastResults = new Map();
    }

    fetchJson(buildUrl(getSearchUrl(activePicker), getSearchParams()))
      .then((data) => {
        hasNextPage = Boolean(data.has_next);
        const results = data.results || [];
        results.forEach((property) => {
          lastResults.set(String(property.id), property);
        });
        renderResults(results, append);
        moreButton.hidden = !hasNextPage;
      })
      .catch(() => {
        resultsContainer.innerHTML = `<div class="blog-property-picker-modal__state is-error">Не удалось загрузить объекты.</div>`;
        moreButton.hidden = true;
      });
  }

  function renderResults(results, append) {
    const resultsContainer = modal.querySelector('[data-picker-results]');
    if (!append) {
      resultsContainer.innerHTML = '';
    }

    if (!results.length && !append) {
      resultsContainer.innerHTML = `<div class="blog-property-picker-modal__state">${text.empty}</div>`;
      return;
    }

    const html = results.map((property) => `
      <article class="blog-property-picker-result ${property.is_active ? '' : 'is-hidden'}">
        <div class="blog-property-picker-result__image">${renderImage(property)}</div>
        <div class="blog-property-picker-result__body">
          <div class="blog-property-picker-result__topline">
            <span>${escapeHtml(property.property_type || 'Property')}</span>
            <span>${escapeHtml(property.deal_type || '')}</span>
            <span class="${property.is_active ? 'is-active' : 'is-hidden'}">${property.is_active ? 'Активен' : 'Скрыт'}</span>
          </div>
          <h3>${escapeHtml(property.title)}</h3>
          <p>${renderMeta(property)}</p>
          <p>${renderFacts(property)}</p>
          <div class="blog-property-picker-result__bottom">
            <div>
              <strong>${escapeHtml(property.price)}</strong>
              <div class="blog-property-picker__badges">${renderTranslationBadges(property)}</div>
            </div>
            <button type="button" class="button button-primary" data-picker-select data-property-id="${escapeHtml(property.id)}">
              ${text.choose}
            </button>
          </div>
        </div>
      </article>
    `).join('');

    resultsContainer.insertAdjacentHTML('beforeend', html);
  }

  function getPickerElements(scope) {
    const pickers = [];
    if (scope.matches && scope.matches(SELECTOR)) {
      pickers.push(scope);
    }
    pickers.push(...scope.querySelectorAll(SELECTOR));
    return pickers;
  }

  function isEmptyFormTemplate(picker) {
    const row = picker.closest('.empty-form, [id$="-empty"]');
    return Boolean(row && (row.classList.contains('empty-form') || (row.id || '').endsWith('-empty')));
  }

  function getInlineRows(scope) {
    const rows = [];
    if (scope.matches && scope.matches('tr.form-row')) {
      rows.push(scope);
    }
    rows.push(...scope.querySelectorAll('tr.form-row'));
    return rows;
  }

  function isEmptyRowTemplate(row) {
    return row.classList.contains('empty-form') || (row.id || '').endsWith('-empty');
  }

  function setDeletePending(row, checkbox, isPending) {
    const deleteButton = row.querySelector('[data-blog-property-link-delete]');
    const undoButton = row.querySelector('[data-blog-property-link-undo-delete]');
    const status = row.querySelector('[data-blog-property-link-delete-status]');

    checkbox.checked = isPending;
    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
    row.classList.toggle('blog-property-link-row--delete-pending', isPending);

    if (deleteButton) {
      deleteButton.hidden = isPending;
    }
    if (undoButton) {
      undoButton.hidden = !isPending;
    }
    if (status) {
      status.hidden = !isPending;
    }
  }

  function initInlineDeleteButtons(scope, options) {
    const force = Boolean(options && options.force);

    document.querySelectorAll('th.delete').forEach((heading) => {
      heading.textContent = text.deleteColumn;
    });

    getInlineRows(scope).forEach((row) => {
      if (!force && isEmptyRowTemplate(row)) {
        return;
      }

      const checkbox = row.querySelector('td.delete input[type="checkbox"][name$="-DELETE"]');
      const deleteCell = checkbox && checkbox.closest('td.delete');
      if (!checkbox || !deleteCell) {
        return;
      }

      if (!force && deleteCell.dataset.blogDeleteReady === '1') {
        return;
      }

      deleteCell.dataset.blogDeleteReady = '1';
      checkbox.classList.add('blog-property-link-delete-checkbox');

      deleteCell.insertAdjacentHTML('beforeend', `
        <div class="blog-property-link-delete-control">
          <button type="button" class="button blog-property-link-delete-button" data-blog-property-link-delete>
            ${text.deleteLink}
          </button>
          <button type="button" class="button blog-property-link-undo-button" data-blog-property-link-undo-delete hidden>
            ${text.undoDelete}
          </button>
          <span class="blog-property-link-delete-status" data-blog-property-link-delete-status hidden>
            ${text.deletePending}
          </span>
        </div>
      `);

      deleteCell.querySelector('[data-blog-property-link-delete]').addEventListener('click', () => {
        setDeletePending(row, checkbox, true);
      });

      deleteCell.querySelector('[data-blog-property-link-undo-delete]').addEventListener('click', () => {
        setDeletePending(row, checkbox, false);
      });

      if (checkbox.checked) {
        setDeletePending(row, checkbox, true);
      }
    });
  }

  function initPickers(scope, options) {
    const force = Boolean(options && options.force);

    getPickerElements(scope).forEach((picker) => {
      if (!force && isEmptyFormTemplate(picker)) {
        return;
      }

      if (!force && picker.dataset.pickerReady === '1') {
        return;
      }

      picker.dataset.pickerReady = '1';
      picker.querySelector('[data-property-picker-open]').addEventListener('click', () => openModal(picker));
      picker.querySelector('[data-property-picker-clear]').addEventListener('click', () => {
        const input = getInput(picker);
        input.value = '';
        input.dispatchEvent(new Event('change', { bubbles: true }));
        renderSelected(picker, null);
      });
      loadSelectedPreview(picker);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initPickers(document);
    initInlineDeleteButtons(document);
  });

  document.addEventListener('formset:added', (event) => {
    initPickers(event.target, { force: true });
    initInlineDeleteButtons(event.target, { force: true });
  });
})();
