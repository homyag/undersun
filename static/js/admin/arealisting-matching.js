(() => {
  'use strict';

  const bootstrap = document.getElementById('matching-data');
  if (!bootstrap) return;

  const data = JSON.parse(bootstrap.textContent);
  const draftKey = `arealisting:matching:${data.user}:${data.project}`;
  let savedRows = {};
  let savedFields = null;
  try {
    const draft = JSON.parse(sessionStorage.getItem(draftKey) || 'null');
    if (draft && typeof draft.rows === 'object' && !Array.isArray(draft.rows)) {
      savedRows = Object.fromEntries(Object.entries(draft.rows || {}).filter(([id, row]) => (
        /^\d+$/.test(id) && row && Array.isArray(row.units) && typeof row.active === 'boolean'
      )));
      savedFields = Array.isArray(draft.fields) ? draft.fields : null;
    }
  } catch (error) {
    // Private browsing or disabled storage must not block matching.
  }
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  const numberFormatter = new Intl.NumberFormat('ru-RU', {maximumFractionDigits: 2});
  const statusLabels = {
    AVAILABLE: 'Доступен',
    SOLD: 'Продан',
  };
  const typeLabels = {
    CONDO: 'Кондо',
    VILLA: 'Вилла',
    HOUSE: 'Таунхаус',
    TOWNHOUSE: 'Таунхаус',
  };
  const projectFieldKeys = new Set(data.project_field_keys || []);
  const projectValues = data.project_values || {};
  const mediaPreviewBatchSize = 4;

  const el = (tag, text, parent) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  };

  const checkbox = (parent, text, checked = false) => {
    const label = el('label', undefined, parent);
    const input = el('input', undefined, label);
    input.type = 'checkbox';
    input.checked = checked;
    label.append(document.createTextNode(` ${text}`));
    return input;
  };

  const formatValue = value => (
    value === null || value === undefined || value === ''
      ? '—'
      : numberFormatter.format(Number(value))
  );

  const displayFieldValue = (key, value) => {
    if (value === null || value === undefined || value === '') return '—';
    if (key === 'build_status') {
      return {completed: 'Готовый объект', under_construction: 'Строящийся объект'}[value] || value;
    }
    return String(value);
  };

  const sourceFieldValue = (key, units) => {
    if (projectFieldKeys.has(key)) {
      if (Object.hasOwn(projectValues, key)) return {available: true, value: projectValues[key]};
      return {available: false, reason: key === 'year_built'
        ? 'Год доступен только для завершённого проекта с датой окончания.'
        : 'У проекта нет данных для этого поля.'};
    }
    if (!units.length) return {available: false, reason: 'Сначала выберите предложение.'};
    const values = units.map(unit => unit[key]);
    if (values.some(value => value === null || value === undefined || value === '')) {
      return {available: false, reason: 'Нет значения у одного или нескольких предложений.'};
    }
    if (new Set(values).size !== 1) {
      return {available: false, reason: 'У выбранных предложений разные значения.'};
    }
    return {available: true, value: values[0]};
  };

  const isFieldLocked = (property, key) => {
    const locked = new Set(property.locked_fields || []);
    return locked.has(key) || locked.has(key.replace(/_(ru|en)$/, ''));
  };

  const imageGallery = (parent, images, altPrefix, selections, activators) => {
    const gallery = el('div', undefined, parent);
    gallery.className = 'draft-unit-gallery';
    const cards = [];
    images.forEach((source, index) => {
      const option = el('div', undefined, gallery);
      option.className = 'draft-media-option';
      option.hidden = index >= mediaPreviewBatchSize;
      const label = el('label', undefined, option);
      const input = el('input', undefined, label);
      input.type = 'checkbox';
      input.checked = true;
      input.value = source.id;
      input.setAttribute('aria-label', `Добавить: ${altPrefix}, изображение ${index + 1}`);
      const image = el('img', undefined, label);
      image.dataset.src = source.url;
      image.alt = `${altPrefix}, изображение ${index + 1}`;
      image.loading = 'lazy';
      image.decoding = 'async';
      const footer = el('div', undefined, option);
      footer.className = 'draft-media-option-footer';
      el(
        'span',
        source.role === 'FLOOR_PLAN' ? 'Планировка' : 'Галерея',
        footer,
      ).className = `meta-badge ${source.role === 'FLOOR_PLAN' ? 'is-floorplan' : ''}`;
      const link = el('a', 'Открыть', footer);
      link.href = source.url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.title = 'Открыть изображение в полном размере';
      selections.push(input);
      cards.push(option);
    });
    const hydrate = cardsToLoad => cardsToLoad.forEach(card => {
      const image = card.querySelector('img[data-src]');
      if (!image) return;
      image.src = image.dataset.src;
      delete image.dataset.src;
    });
    activators.push(() => hydrate(cards.filter(card => !card.hidden)));
    if (cards.length > mediaPreviewBatchSize) {
      let shown = mediaPreviewBatchSize;
      const more = el('button', '', parent);
      more.type = 'button';
      more.className = 'secondary draft-media-more';
      const updateMore = () => {
        const remaining = cards.length - shown;
        more.textContent = remaining > 0
          ? `Показать ещё ${Math.min(mediaPreviewBatchSize, remaining)} из ${remaining}`
          : '';
        more.hidden = remaining <= 0;
      };
      more.addEventListener('click', () => {
        const next = cards.slice(shown, shown + mediaPreviewBatchSize);
        next.forEach(card => { card.hidden = false; });
        shown += next.length;
        hydrate(next);
        updateMore();
      });
      updateMore();
    }
  };

  const unitChoice = (parent, unit, options = {}) => {
    const label = el('label', undefined, parent);
    label.className = [
      'unit-choice',
      options.suggested ? 'suggested' : '',
      options.skipped ? 'is-skipped' : '',
      options.linked ? 'is-linked' : '',
    ].filter(Boolean).join(' ');

    const input = el('input', undefined, label);
    input.type = 'checkbox';
    input.checked = Boolean(options.checked);

    const content = el('span', undefined, label);
    content.className = 'unit-choice-content';
    const heading = el('span', undefined, content);
    heading.className = 'unit-choice-heading';
    const title = el('strong', `№ ${unit.number || 'без номера'}`, heading);
    title.className = 'unit-number';

    const status = el(
      'span',
      statusLabels[unit.status] || 'Статус не указан',
      heading,
    );
    status.className = `status-badge ${unit.status === 'AVAILABLE' ? 'is-available' : unit.status === 'SOLD' ? 'is-sold' : ''}`;

    if (unit.property_type) {
      const type = el(
        'span',
        typeLabels[unit.property_type] || unit.property_type,
        heading,
      );
      type.className = 'meta-badge';
    }
    if (options.linked) {
      const linked = el('span', 'Связано сейчас', heading);
      linked.className = 'meta-badge is-linked';
    }

    const meta = el(
      'span',
      `${unit.bedrooms ?? '—'} сп. · ${formatValue(unit.area_total)} м² · этаж ${unit.floor ?? '—'} · ${formatValue(unit.price)} ${unit.currency || ''}`.trim(),
      content,
    );
    meta.className = 'unit-choice-meta';

    if (options.reason) {
      const reason = el('small', options.reason, content);
      reason.className = 'unit-choice-reason';
    }
    return input;
  };

  const post = async payload => {
    const response = await fetch(window.location.href, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
      body: JSON.stringify(payload),
    });
    const responseText = await response.text();
    let result = {};
    try {
      result = responseText ? JSON.parse(responseText) : {};
    } catch (error) {
      result = {};
    }
    if (!response.ok) {
      throw new Error(result.error || 'Не удалось выполнить действие. Обновите страницу и повторите попытку.');
    }
    return result;
  };

  const matches = document.getElementById('matches');
  const unmatched = document.getElementById('unmatched');
  const comparison = document.getElementById('comparison');
  const saveReport = document.getElementById('save-report');
  const save = document.getElementById('save');
  const message = document.getElementById('matching-message');
  const selectionStage = document.getElementById('selection-stage');
  const reviewStage = document.getElementById('review-stage');
  const selections = [];
  const draftStatus = document.getElementById('matching-draft-status');
  let hasUnsavedChanges = false;

  const setMessage = (text, tone = '') => {
    message.textContent = text;
    message.className = tone ? `is-${tone}` : '';
  };

  const renderSaveReport = rows => {
    saveReport.replaceChildren();
    saveReport.hidden = !rows.length;
    if (!rows.length) return;
    el('h2', 'Результат по карточкам', saveReport);
    const priceNote = el(
      'p',
      'Цена пересчитывается отдельно при следующем успешном получении данных AREALISTING.',
      saveReport,
    );
    priceNote.className = 'muted';
    rows.forEach(row => {
      const card = el('article', undefined, saveReport);
      card.className = 'matching-save-card';
      const title = el('h3', undefined, card);
      const link = el('a', row.title || `Карточка #${row.property_id}`, title);
      link.href = row.url;
      if (row.media_preview_url) {
        const mediaHelp = el('p', 'Связь сохранена. Фотографии добавляются отдельно: сначала проверьте, какие фото изменятся.', card);
        mediaHelp.className = 'muted';
        const mediaLink = el('a', 'Проверить и импортировать фото →', card);
        mediaLink.href = row.media_preview_url;
        mediaLink.className = 'primary-action';
      }
      const changes = row.changed_fields || [];
      if (changes.length) {
        el('strong', 'Изменено сейчас:', card);
        const list = el('ul', undefined, card);
        changes.forEach(change => el(
          'li',
          `${data.fields[change.field] || change.field}: ${displayFieldValue(change.field, change.before)} → ${displayFieldValue(change.field, change.after)}`,
          list,
        ));
      }
      if (row.activity_change) {
        el(
          'p',
          `Публикация: ${row.activity_change.before ? 'активна' : 'неактивна'} → ${row.activity_change.after ? 'активна' : 'неактивна'}.`,
          card,
        );
      }
      if (row.unchanged_fields?.length) {
        el('p', `Уже совпадали: ${row.unchanged_fields.map(field => data.fields[field] || field).join(', ')}.`, card);
      }
      if (row.managed_added?.length) {
        el('p', `Включено дальнейшее обновление: ${row.managed_added.map(field => data.fields[field] || field).join(', ')}.`, card);
      }
      if (row.managed_removed?.length) {
        el('p', `Отключено дальнейшее обновление: ${row.managed_removed.map(field => data.fields[field] || field).join(', ')}.`, card);
      }
      if (row.not_applied?.length) {
        el('strong', 'Не обновлено сейчас:', card);
        const list = el('ul', undefined, card);
        row.not_applied.forEach(item => el('li', `${data.fields[item.field] || item.field}: ${item.reason}`, list));
      }
      if (row.unavailable_fields?.length) {
        const details = el('details', undefined, card);
        el('summary', `Поля без готовых данных в AREALISTING (${row.unavailable_fields.length})`, details);
        const list = el('ul', undefined, details);
        row.unavailable_fields.forEach(item => el('li', `${data.fields[item.field] || item.field}: ${item.reason}`, list));
      }
      if (!changes.length && !row.activity_change && !row.unchanged_fields?.length
          && !row.managed_added?.length && !row.managed_removed?.length && !row.not_applied?.length) {
        el('p', 'Связь с предложениями сохранена. Другие поля карточки не менялись.', card);
      }
    });
  };
  const renderDraftStatus = () => {
    draftStatus.replaceChildren();
    const entries = Object.entries(savedRows);
    draftStatus.hidden = entries.length === 0;
    if (!entries.length) return;
    const visible = new Set(selections.map(item => String(item.property.id)));
    el('strong', `Сохранён выбор для ${entries.length} карточек в этой вкладке.`, draftStatus);
    const hidden = entries.filter(([id]) => !visible.has(id));
    if (hidden.length) {
      const links = el('div', undefined, draftStatus);
      links.className = 'matching-draft-links';
      el('span', 'Вернуться к выбору: ', links);
      hidden.forEach(([id, row]) => {
        const link = el('a', row.title || `Карточка #${id}`, links);
        link.href = `${window.location.pathname}?project=${encodeURIComponent(data.project)}&property=${encodeURIComponent(id)}`;
      });
    }
    const clear = el('button', 'Очистить сохранённый выбор', draftStatus);
    clear.type = 'button';
    clear.className = 'secondary';
    clear.addEventListener('click', () => {
      savedRows = {};
      savedFields = null;
      try { sessionStorage.removeItem(draftKey); } catch (error) { /* Storage unavailable. */ }
      hasUnsavedChanges = false;
      window.location.reload();
    });
  };

  const writeDraft = () => {
    let saved = true;
    try {
      if (Object.keys(savedRows).length) {
        sessionStorage.setItem(draftKey, JSON.stringify({rows: savedRows}));
      } else {
        sessionStorage.removeItem(draftKey);
      }
    } catch (error) {
      saved = false;
    }
    renderDraftStatus();
    return saved;
  };

  const saveDraft = () => {
    selections.forEach(({property, choices, activeInput, fieldKeys}) => {
      const selectedUnits = choices.filter(choice => choice.input.checked).map(choice => choice.unit.id).sort();
      const originalUnits = choices.filter(choice => choice.unit.property === property.id).map(choice => choice.unit.id).sort();
      const fields = [...fieldKeys].sort();
      const originalFields = [...(property.managed_fields || [])].sort();
      const changed = selectedUnits.join(',') !== originalUnits.join(',')
        || (selectedUnits.length && activeInput.checked !== property.is_active)
        || (selectedUnits.length && fields.join(',') !== originalFields.join(','));
      if (changed) {
        savedRows[property.id] = {
          title: property.title, units: selectedUnits, active: activeInput.checked, fields,
        };
      } else {
        delete savedRows[property.id];
      }
    });
    return writeDraft();
  };

  const markDirty = () => { hasUnsavedChanges = !saveDraft() || hasUnsavedChanges; };
  const markTransientDirty = () => { hasUnsavedChanges = true; };
  window.addEventListener('beforeunload', event => {
    if (!hasUnsavedChanges) return;
    event.preventDefault();
    event.returnValue = '';
  });

  const setStep = step => {
    ['two', 'three', 'done'].forEach(name => {
      const item = document.getElementById(`step-${name}`);
      if (name === step) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    document.getElementById('step-done').hidden = step !== 'done';
    document.getElementById('step-help').hidden = step !== 'two';
  };

  const invalidate = () => {
    comparison.replaceChildren();
    save.hidden = true;
  };

  const updateCount = () => {
    const count = selections.filter(selection => selection.selected.checked).length;
    document.getElementById('selection-count').textContent = count
      ? `Карточек к проверке: ${count}`
      : 'Выберите хотя бы одно предложение справа от карточки';
    document.getElementById('preview').disabled = count === 0;
  };

  document.getElementById('back').addEventListener('click', () => {
    selectionStage.hidden = false;
    reviewStage.hidden = true;
    setStep('two');
  });

  data.properties.forEach(property => {
    const card = el('article', undefined, matches);
    card.className = 'match-row';
    const local = el('div', undefined, card);
    local.className = 'local-property';
    el('small', 'КАРТОЧКА UNDERSUN', local);
    const title = el('a', property.title, local);
    title.href = property.url;
    title.target = '_blank';
    title.rel = 'noopener';
    title.className = 'property-title';
    if (property.photo) {
      const photo = el('img', undefined, local);
      photo.src = property.photo;
      photo.alt = '';
      photo.loading = 'lazy';
      photo.className = 'local-photo';
    }
    el(
      'p',
      `${property.values.bedrooms ?? '—'} сп. · ${formatValue(property.values.area_total)} м² · этаж ${property.values.floor ?? '—'}`,
      local,
    );
    const state = el('p', property.is_active ? 'Активна на сайте' : 'Неактивна', local);
    state.className = `publication-state ${property.is_active ? 'is-active' : 'is-inactive'}`;
    const activeInput = checkbox(local, 'Показывать карточку на сайте', property.is_active);
    activeInput.parentElement.className = 'activity-toggle';

    const remote = el('div', undefined, card);
    remote.className = 'remote-units';
    el('small', 'ПРЕДЛОЖЕНИЯ AREALISTING', remote);
    const areaDifference = unit => {
      const sourceArea = Number(unit.area_total);
      const targetArea = Number(property.values.area_total);
      return Number.isFinite(sourceArea) && Number.isFinite(targetArea)
        ? Math.abs(sourceArea - targetArea)
        : Number.POSITIVE_INFINITY;
    };
    const isSuggested = unit => (
      unit.bedrooms !== null
      && unit.area_total !== null
      && property.values.area_total !== null
      && unit.bedrooms === property.values.bedrooms
      && areaDifference(unit) <= 1
    );
    const candidates = data.units
      .filter(unit => (!unit.occupied || unit.property === property.id) && !unit.skipped)
      .sort((left, right) => (
        Number(isSuggested(right)) - Number(isSuggested(left))
        || Number(right.status === 'AVAILABLE') - Number(left.status === 'AVAILABLE')
        || areaDifference(left) - areaDifference(right)
      ));
    const primaryUnits = candidates.filter(unit => isSuggested(unit) || unit.property === property.id);
    const otherUnits = candidates.filter(unit => !primaryUnits.includes(unit));
    const linkedUnits = candidates.filter(unit => unit.property === property.id);
    const suggestedUnits = candidates.filter(isSuggested);
    const summary = el(
      'p',
      linkedUnits.length
        ? `Сейчас связано: ${linkedUnits.length}. Близких по параметрам: ${suggestedUnits.length}.`
        : `Близких по параметрам: ${suggestedUnits.length}.`,
      remote,
    );
    summary.className = 'candidate-summary';

    const top = el('div', undefined, remote);
    top.className = 'unit-list';
    const choices = [];
    const selected = {checked: false};
    const restored = savedRows[property.id];
    const initialFields = Array.isArray(restored?.fields)
      ? restored.fields
      : [...(property.managed_fields || []), ...(savedFields || [])];
    const fieldKeys = new Set(initialFields.filter(key => Object.hasOwn(data.fields, key)));
    const fieldPanel = el('section', undefined, card);
    fieldPanel.className = 'match-field-panel';
    el('h3', 'Какие данные перенести в эту карточку?', fieldPanel);
    const fieldHelp = el('p', 'Отметьте поля для этой карточки. Снятие отметки с уже управляемого поля отключит его обновление из AREALISTING.', fieldPanel);
    fieldHelp.className = 'muted';
    const fieldGrid = el('div', undefined, fieldPanel);
    fieldGrid.className = 'match-field-grid';
    const renderFields = () => {
      const selectedUnits = choices.filter(choice => choice.input.checked).map(choice => choice.unit);
      fieldPanel.hidden = !selectedUnits.length;
      fieldGrid.replaceChildren();
      if (!selectedUnits.length) return;
      Object.entries(data.fields).forEach(([key, label]) => {
        const source = sourceFieldValue(key, selectedUnits);
        const wasManaged = (property.managed_fields || []).includes(key);
        const locked = isFieldLocked(property, key);
        if ((!source.available || locked) && !wasManaged) fieldKeys.delete(key);
        const row = el('label', undefined, fieldGrid);
        row.className = `match-field-option${!source.available || locked ? ' is-unavailable' : ''}`;
        const input = el('input', undefined, row);
        input.type = 'checkbox';
        input.checked = fieldKeys.has(key);
        input.disabled = (!source.available || locked) && !wasManaged;
        const content = el('span', undefined, row);
        el('strong', label, content);
        const detail = source.available
          ? `Сейчас: ${displayFieldValue(key, property.values[key])} → AREALISTING: ${displayFieldValue(key, source.value)}`
          : source.reason;
        el('small', detail, content);
        if (wasManaged) el('small', locked ? 'Уже управляется, но защищено от обновления' : 'Уже обновляется из AREALISTING', content);
        if (locked && !wasManaged) el('small', 'Поле защищено от обновления', content);
        input.addEventListener('change', () => {
          if (input.checked) fieldKeys.add(key);
          else fieldKeys.delete(key);
          invalidate();
          markDirty();
        });
      });
    };
    const syncSelection = ({dirty = true} = {}) => {
      selected.checked = choices.some(choice => choice.input.checked);
      card.classList.toggle('has-selection', selected.checked);
      activeInput.disabled = !selected.checked;
      if (!selected.checked) activeInput.checked = property.is_active;
      renderFields();
      invalidate();
      updateCount();
      if (dirty) markDirty();
    };
    const renderChoice = (container, unit) => {
      const suggested = isSuggested(unit);
      const difference = areaDifference(unit);
      let reason = '';
      if (suggested) {
        reason = difference < 0.001
          ? 'Совпадают спальни и площадь — всё равно проверьте номер и цену.'
          : `Столько же спален, разница площади ${numberFormatter.format(difference)} м².`;
      }
      const input = unitChoice(container, unit, {
        checked: unit.property === property.id,
        linked: unit.property === property.id,
        suggested,
        reason,
      });
      const choice = {input, unit};
      choices.push(choice);
      input.addEventListener('change', () => syncSelection());
    };
    primaryUnits.forEach(unit => renderChoice(top, unit));
    if (otherUnits.length) {
      const details = el('details', undefined, remote);
      details.className = 'other-units';
      el('summary', `Остальные предложения комплекса (${otherUnits.length})`, details);
      const otherList = el('div', undefined, details);
      otherList.className = 'unit-list';
      otherUnits.forEach(unit => renderChoice(otherList, unit));
    }

    if (linkedUnits.length && linkedUnits.every(unit => unit.status === 'SOLD') && property.is_active) {
      const warning = el('p', 'Все связанные предложения проданы, но карточка Undersun активна. При необходимости снимите галочку публикации.', top);
      warning.className = 'matching-warning';
    }
    if (suggestedUnits.length && suggestedUnits.every(unit => unit.status === 'SOLD')) {
      const warning = el('p', 'Все близкие варианты проданы. Активность карточки меняется только вручную.', top);
      warning.className = 'matching-warning';
    }
    if (!suggestedUnits.length && candidates.length) {
      const hint = el('p', 'Точного кандидата по спальням и площади нет — проверьте остальные предложения.', top);
      hint.className = 'muted';
    }
    if (!candidates.length) {
      const empty = el('p', 'Нет свободных предложений для связи с этой карточкой.', top);
      empty.className = 'empty-inline';
    }

    activeInput.addEventListener('change', () => {
      invalidate();
      markDirty();
    });
    if (restored && Array.isArray(restored.units)) {
      choices.forEach(choice => { choice.input.checked = restored.units.includes(choice.unit.id); });
      activeInput.checked = Boolean(restored.active);
    }
    syncSelection({dirty: false});
    selections.push({property, selected, choices, activeInput, fieldKeys, renderFields});
  });

  updateCount();
  if (!data.properties.length) {
    const empty = el('div', undefined, matches);
    empty.className = 'empty-state';
    el('h3', 'Карточки не найдены', empty);
    el('p', 'Уточните поиск по названию Undersun или вернитесь к списку комплексов.', empty);
  }

  const free = data.units.filter(unit => !unit.occupied && !unit.skipped);
  const skipped = data.units.filter(unit => !unit.occupied && unit.skipped);
  el('h2', 'Предложения без карточки Undersun', unmatched);
  el('p', 'Сначала убедитесь, что нужной карточки нет во вкладке «Карточки Undersun». Затем можно создать неактивный черновик или пропустить предложение.', unmatched);
  const statusFilter = document.getElementById('unmatched-status-filter');
  const statusFilterSummary = document.getElementById('unmatched-filter-summary');
  const statusFilterButtons = [...statusFilter.querySelectorAll('[data-unit-status]')];
  statusFilter.hidden = false;
  unmatched.append(statusFilter);
  const freeList = el('div', undefined, unmatched);
  freeList.className = 'unit-list standalone-unit-list';
  const freeChoices = free.map(unit => {
    const input = unitChoice(freeList, unit);
    return {input, unit};
  });
  if (!free.length) {
    const empty = el('p', 'Новых предложений для разбора нет.', unmatched);
    empty.className = 'empty-inline';
  }

  const unmatchedActions = el('div', undefined, unmatched);
  unmatchedActions.className = 'unmatched-actions';
  const freeSelectionCount = el('strong', 'Ничего не выбрано', unmatchedActions);
  freeSelectionCount.className = 'action-selection-count';
  const draftButton = el('button', 'Проверить черновик', unmatchedActions);
  draftButton.type = 'button';
  draftButton.hidden = !data.can_create_draft;
  const skipButton = el('button', 'Пропустить', unmatchedActions);
  skipButton.type = 'button';
  skipButton.className = 'secondary';
  const reasonLabel = el('label', undefined, unmatchedActions);
  reasonLabel.className = 'skip-reason';
  reasonLabel.append(document.createTextNode('Причина пропуска '));
  const reasonInput = el('input', undefined, reasonLabel);
  reasonInput.type = 'text';
  reasonInput.maxLength = 255;
  reasonInput.placeholder = 'Необязательно';

  const selectedFreeIds = () => freeChoices
    .filter(choice => choice.input.checked)
    .map(choice => choice.unit.id);
  const updateFreeActions = () => {
    const count = selectedFreeIds().length;
    freeSelectionCount.textContent = count ? `Выбрано: ${count}` : 'Ничего не выбрано';
    draftButton.disabled = count === 0;
    skipButton.disabled = count === 0;
  };
  freeChoices.forEach(choice => choice.input.addEventListener('change', () => {
    updateFreeActions();
    markTransientDirty();
  }));
  updateFreeActions();

  const statusCounts = {
    all: free.length,
    AVAILABLE: free.filter(unit => unit.status === 'AVAILABLE').length,
    SOLD: free.filter(unit => unit.status === 'SOLD').length,
  };
  const statusButtonLabels = {
    all: 'Все',
    AVAILABLE: 'Доступные',
    SOLD: 'Проданные',
  };
  const applyStatusFilter = status => {
    let visibleCount = 0;
    let selectionChanged = false;
    freeChoices.forEach(choice => {
      const isVisible = status === 'all' || choice.unit.status === status;
      choice.input.parentElement.hidden = !isVisible;
      if (isVisible) visibleCount += 1;
      if (!isVisible && choice.input.checked) {
        choice.input.checked = false;
        selectionChanged = true;
      }
    });
    statusFilterButtons.forEach(button => {
      const buttonStatus = button.dataset.unitStatus;
      button.textContent = `${statusButtonLabels[buttonStatus]} (${statusCounts[buttonStatus]})`;
      button.setAttribute('aria-pressed', String(buttonStatus === status));
    });
    statusFilterSummary.textContent = `Показано: ${visibleCount}`;
    updateFreeActions();
    if (selectionChanged) markTransientDirty();
  };
  statusFilterButtons.forEach(button => button.addEventListener('click', () => {
    applyStatusFilter(button.dataset.unitStatus);
  }));
  applyStatusFilter('all');

  const draftReview = el('section', undefined, unmatched);
  draftReview.className = 'draft-review';
  draftReview.hidden = true;
  draftButton.addEventListener('click', async () => {
    draftButton.disabled = true;
    draftReview.hidden = true;
    draftReview.replaceChildren();
    setMessage('Проверяем данные…');
    try {
      const units = selectedFreeIds();
      const result = await post({action: 'preview_draft', project: data.project, units});
      const preview = result.preview;
      const locationOptions = Array.isArray(preview.location_options) ? preview.location_options : [];
      let selectedLocationChoice = preview.selected_location_choice || '';
      const selectedLocation = () => locationOptions.find(
        option => String(option.id) === String(selectedLocationChoice),
      );
      setMessage('');
      el('h3', 'Проверьте неактивный черновик', draftReview);
      const previewGrid = el('dl', undefined, draftReview);
      previewGrid.className = 'draft-preview-grid';
      let districtValue;
      let locationValue;
      [
        ['Название RU', preview.title_ru],
        ['Название EN', preview.title_en],
        ['Тип', preview.property_type],
        ['Стадия', preview.build_status === 'completed' ? 'Готовый объект' : 'Строящийся объект'],
        ['Застройщик', preview.developer || '—'],
        ['Район', selectedLocation()?.district || preview.district || 'требуется выбор'],
        ['Локация', selectedLocation()?.location || preview.location || 'требуется выбор'],
        ['Параметры', `${preview.bedrooms ?? '—'} сп. · ${preview.bathrooms ?? '—'} ванн. · ${formatValue(preview.area_total)} м² · этаж ${preview.floor ?? '—'}`],
        ['Участок', preview.area_land == null ? '—' : `${formatValue(preview.area_land)} м²`],
        ['Меблировка', preview.furnished == null ? 'не указана' : (preview.furnished ? 'с мебелью' : 'без мебели')],
        ['Удобства', `${preview.features_count} характеристик`],
        ['Описания', `RU: ${preview.has_description_ru ? 'есть' : 'нет'} · EN: ${preview.has_description_en ? 'есть' : 'нет'}`],
        ['Координаты', preview.latitude == null || preview.longitude == null ? '—' : `${preview.latitude}, ${preview.longitude}`],
        ['Цена источника', `от ${formatValue(preview.source_price)} ${preview.source_currency}`],
      ].forEach(([label, value]) => {
        const item = el('div', undefined, previewGrid);
        el('dt', label, item);
        const valueNode = el('dd', value, item);
        if (label === 'Район') districtValue = valueNode;
        if (label === 'Локация') locationValue = valueNode;
      });

      let locationSelect;
      if (preview.location_choice_required) {
        const locationChoice = el('section', undefined, draftReview);
        locationChoice.className = 'draft-location-choice';
        el('h4', 'Выберите локацию для этого черновика', locationChoice);
        el(
          'p',
          'У комплекса подтверждено несколько локаций. AREALISTING не указывает, к какой из них относится каждый юнит, поэтому система не выбирает автоматически. Для другой локации создайте отдельный черновик из соответствующих юнитов.',
          locationChoice,
        );
        const label = el('label', undefined, locationChoice);
        label.append(document.createTextNode('Локация Undersun '));
        locationSelect = el('select', undefined, label);
        const placeholder = el('option', '— выберите локацию —', locationSelect);
        placeholder.value = '';
        locationOptions.forEach(option => {
          const sourceSuffix = option.source_names?.length
            ? ` · AREALISTING: ${option.source_names.join(', ')}`
            : '';
          const optionNode = el(
            'option',
            `${option.district}${option.location ? ` → ${option.location}` : ''}${sourceSuffix}`,
            locationSelect,
          );
          optionNode.value = option.id;
        });
        locationSelect.value = selectedLocationChoice;
        locationSelect.addEventListener('change', () => {
          selectedLocationChoice = locationSelect.value;
          const option = selectedLocation();
          districtValue.textContent = option?.district || 'требуется выбор';
          locationValue.textContent = option?.location || (option ? '—' : 'требуется выбор');
          confirmButton.disabled = !selectedLocationChoice;
        });
      }

      const mediaReview = el('details', undefined, draftReview);
      mediaReview.className = 'draft-media-review';
      const mediaSummary = el(
        'summary',
        `Фотографии и планировки из AREALISTING (${preview.media_assets_total || 0})`,
        mediaReview,
      );
      const mediaContent = el('div', undefined, mediaReview);
      mediaContent.className = 'draft-media-content';
      el(
        'p',
        'Изображения не загружаются, пока вы не откроете этот раздел. Отметьте файлы, которые нужно сразу добавить в черновик.',
        mediaContent,
      ).className = 'muted';
      const mediaSelections = [];
      const mediaActivators = [];
      const mediaControls = el('div', undefined, mediaContent);
      mediaControls.className = 'draft-media-controls';
      const mediaCount = el('strong', '', mediaControls);
      const selectAllMedia = el('button', 'Выбрать все', mediaControls);
      selectAllMedia.type = 'button';
      selectAllMedia.className = 'secondary';
      const clearMedia = el('button', 'Снять все', mediaControls);
      clearMedia.type = 'button';
      clearMedia.className = 'secondary';

      const projectImages = Array.isArray(preview.project_images) ? preview.project_images : [];
      if (projectImages.length) {
        const projectMedia = el('article', undefined, mediaContent);
        projectMedia.className = 'draft-unit-media';
        const projectHeading = el('div', undefined, projectMedia);
        projectHeading.className = 'draft-media-heading';
        el('strong', 'Общая галерея комплекса', projectHeading);
        const total = Number(preview.project_images_total) || projectImages.length;
        el('span', `Показано ${projectImages.length} из ${total}`, projectHeading).className = 'muted';
        imageGallery(
          projectMedia,
          projectImages,
          'AREALISTING: общая галерея комплекса',
          mediaSelections,
          mediaActivators,
        );
      }

      const unitImages = Array.isArray(preview.unit_images) ? preview.unit_images : [];
      const unitsWithImages = unitImages.filter(unit => Array.isArray(unit.images) && unit.images.length);
      unitsWithImages.forEach(unit => {
        const unitMedia = el('article', undefined, mediaContent);
        unitMedia.className = 'draft-unit-media';
        const heading = el('div', undefined, unitMedia);
        heading.className = 'draft-media-heading';
        el('strong', `Юнит № ${unit.number || 'без номера'}`, heading);
        const status = el('span', statusLabels[unit.status] || 'Статус не указан', heading);
        status.className = `status-badge ${unit.status === 'AVAILABLE' ? 'is-available' : unit.status === 'SOLD' ? 'is-sold' : ''}`;
        const total = Number(unit.images_total) || unit.images.length;
        if (total > unit.images.length) {
          el('span', `Показано ${unit.images.length} из ${total}`, heading).className = 'muted';
        }
        imageGallery(
          unitMedia,
          unit.images,
          `AREALISTING: юнит № ${unit.number || 'без номера'}`,
          mediaSelections,
          mediaActivators,
        );
      });
      const unitsWithoutImages = unitImages.filter(unit => !Array.isArray(unit.images) || !unit.images.length);
      if (unitsWithoutImages.length) {
        const hiddenGalleries = unitsWithoutImages.filter(unit => Number(unit.images_total) > 0);
        if (hiddenGalleries.length) {
          const numbers = hiddenGalleries.map(unit => unit.number || 'без номера').join(', ');
          el('p', `Изображения для юнитов ${numbers} уже показаны у другого выбранного юнита или не вошли в предпросмотр.`, mediaContent).className = 'muted';
        }
        const emptyGalleries = unitsWithoutImages.filter(unit => Number(unit.images_total) === 0);
        if (emptyGalleries.length) {
          const numbers = emptyGalleries.map(unit => unit.number || 'без номера').join(', ');
          const note = projectImages.length
            ? `У юнитов ${numbers} нет собственной галереи; выше показаны общие изображения комплекса.`
            : `У юнитов ${numbers} нет собственной галереи.`;
          el('p', note, mediaContent).className = 'muted';
        }
      }
      if (Number(preview.media_assets_total) === 0) {
        el('p', 'AREALISTING не передал изображений для комплекса и выбранных юнитов.', mediaContent).className = 'empty-inline';
      }
      if (Number(preview.media_assets_total) > Number(preview.media_selection_limit)) {
        el(
          'p',
          `Для одного черновика можно выбрать первые ${preview.media_selection_limit} изображений из ${preview.media_assets_total}. Остальные можно добавить позднее через группу связи.`,
          mediaContent,
        ).className = 'matching-warning';
      }
      const selectedMediaIds = () => mediaSelections
        .filter(input => input.checked)
        .map(input => Number(input.value));
      const updateMediaSelection = () => {
        const selected = selectedMediaIds().length;
        mediaCount.textContent = `Выбрано изображений: ${selected} из ${mediaSelections.length}`;
        mediaSummary.textContent = `Фотографии и планировки из AREALISTING — выбрано ${selected} из ${mediaSelections.length}`;
        selectAllMedia.disabled = selected === mediaSelections.length;
        clearMedia.disabled = selected === 0;
      };
      mediaSelections.forEach(input => input.addEventListener('change', updateMediaSelection));
      selectAllMedia.addEventListener('click', () => {
        mediaSelections.forEach(input => { input.checked = true; });
        updateMediaSelection();
      });
      clearMedia.addEventListener('click', () => {
        mediaSelections.forEach(input => { input.checked = false; });
        updateMediaSelection();
      });
      mediaControls.hidden = mediaSelections.length === 0;
      updateMediaSelection();
      mediaReview.addEventListener('toggle', () => {
        if (mediaReview.open) mediaActivators.forEach(activate => activate());
      }, {once: true});
      const note = el('p', 'Карточка будет создана неактивной и не появится на сайте до отдельной публикации.', draftReview);
      note.className = 'matching-warning';
      const confirmButton = el('button', 'Создать неактивный черновик', draftReview);
      confirmButton.type = 'button';
      confirmButton.disabled = Boolean(preview.location_choice_required && !selectedLocationChoice);
      confirmButton.addEventListener('click', async () => {
        confirmButton.disabled = true;
        setMessage('Создаём черновик…');
        try {
          const created = await post({
            action: 'create_draft',
            project: data.project,
            units,
            location_choice: selectedLocationChoice || null,
            media_assets: selectedMediaIds(),
          });
          hasUnsavedChanges = false;
          setMessage(
            created.media_job_url
              ? 'Черновик создан. Выбранные фото загружаются в фоне.'
              : 'Черновик создан без импорта фото.',
            'success',
          );
          draftReview.replaceChildren();
          el('h3', `Черновик «${created.title}» создан`, draftReview);
          el(
            'p',
            created.media_job_url
              ? 'Загрузка фото продолжается в фоне. Прогресс и ошибки видны на странице задания.'
              : 'Фото можно добавить позже через группу связи.',
            draftReview,
          );
          if (created.media_job_url) {
            const mediaLink = el('a', 'Посмотреть загрузку фото →', draftReview);
            mediaLink.href = created.media_job_url;
            mediaLink.className = 'primary-action';
          }
          const link = el('a', 'Открыть и проверить карточку →', draftReview);
          link.href = created.url;
          link.className = 'primary-action';
        } catch (error) {
          setMessage(error.message, 'error');
          confirmButton.disabled = false;
        }
      });
      draftReview.hidden = false;
      draftReview.scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (error) {
      setMessage(error.message, 'error');
    }
    updateFreeActions();
  });

  skipButton.addEventListener('click', async () => {
    skipButton.disabled = true;
    setMessage('Сохраняем решение…');
    try {
      await post({
        action: 'skip_units',
        project: data.project,
        units: selectedFreeIds(),
        reason: reasonInput.value.trim(),
      });
      hasUnsavedChanges = false;
      window.location.reload();
    } catch (error) {
      setMessage(error.message, 'error');
      updateFreeActions();
    }
  });

  if (skipped.length) {
    const skippedSection = el('details', undefined, unmatched);
    skippedSection.className = 'skipped-section';
    el('summary', `Пропущенные предложения (${skipped.length})`, skippedSection);
    const skippedList = el('div', undefined, skippedSection);
    skippedList.className = 'unit-list';
    const skippedChoices = skipped.map(unit => ({
      input: unitChoice(skippedList, unit, {
        skipped: true,
        reason: unit.skip_reason ? `Причина: ${unit.skip_reason}` : 'Причина не указана',
      }),
      unit,
    }));
    const restoreButton = el('button', 'Вернуть выбранные в очередь', skippedSection);
    restoreButton.type = 'button';
    restoreButton.className = 'secondary';
    const updateRestore = () => {
      restoreButton.disabled = !skippedChoices.some(choice => choice.input.checked);
    };
    skippedChoices.forEach(choice => choice.input.addEventListener('change', () => {
      updateRestore();
      markTransientDirty();
    }));
    updateRestore();
    restoreButton.addEventListener('click', async () => {
      restoreButton.disabled = true;
      setMessage('Возвращаем предложения в очередь…');
      const units = skippedChoices
        .filter(choice => choice.input.checked)
        .map(choice => choice.unit.id);
      try {
        await post({action: 'restore_units', project: data.project, units});
        hasUnsavedChanges = false;
        window.location.reload();
      } catch (error) {
        setMessage(error.message, 'error');
        updateRestore();
      }
    });
  }

  const showMatches = document.getElementById('show-matches');
  const showUnmatched = document.getElementById('show-unmatched');
  showMatches.textContent = `Карточки Undersun (${data.properties.length})`;
  showUnmatched.textContent = `Ещё не связаны (${free.length})`;
  const setTab = tab => {
    const isMatches = tab === 'matches';
    matches.hidden = !isMatches;
    unmatched.hidden = isMatches;
    document.getElementById('matching-actions').hidden = !isMatches;
    showMatches.setAttribute('aria-pressed', String(isMatches));
    showMatches.setAttribute('aria-selected', String(isMatches));
    showUnmatched.setAttribute('aria-pressed', String(!isMatches));
    showUnmatched.setAttribute('aria-selected', String(!isMatches));
  };
  showMatches.addEventListener('click', () => setTab('matches'));
  showUnmatched.addEventListener('click', () => setTab('unmatched'));

  renderDraftStatus();

  let pending = [];
  document.getElementById('preview').addEventListener('click', () => {
    invalidate();
    pending = [];
    setMessage('');
    const used = new Set();
    for (const selection of selections.filter(item => item.selected.checked)) {
      const units = selection.choices
        .filter(choice => choice.input.checked)
        .map(choice => choice.unit);
      if (!units.length || units.some(unit => used.has(unit.id))) {
        invalidate();
        setMessage('Выберите предложения для каждой карточки. Одно предложение нельзя связать с двумя карточками.', 'error');
        return;
      }
      units.forEach(unit => used.add(unit.id));
      const block = el('article', undefined, comparison);
      block.className = 'review-card';
      el('h3', selection.property.title, block);
      el('p', `Связать с: ${units.map(unit => `№ ${unit.number || 'без номера'}`).join(', ')}`, block);
      if (units.every(unit => unit.status === 'SOLD') && selection.activeInput.checked) {
        const warning = el('p', 'Все выбранные предложения проданы, но карточка останется активной.', block);
        warning.className = 'matching-warning';
      }
      if (selection.activeInput.checked !== selection.property.is_active) {
        const before = selection.property.is_active ? 'активна' : 'неактивна';
        const after = selection.activeInput.checked ? 'активна' : 'неактивна';
        const activity = el('p', `Активность: ${before} → ${after}`, block);
        activity.className = 'review-change';
      }
      const ownershipHelp = el(
        'p',
        'Отметка означает, что AREALISTING управляет полем при следующих обновлениях. Снимите её, чтобы оставить поле под ручным управлением.',
        block,
      );
      ownershipHelp.className = 'muted';
      const fields = [];
      const currentManaged = new Set(selection.property.managed_fields || []);
      const requested = new Set(selection.fieldKeys);
      const keys = [...new Set([...requested, ...currentManaged])];
      keys.forEach(key => {
        const source = sourceFieldValue(key, units);
        const isLocked = isFieldLocked(selection.property, key);
        if (!source.available && !currentManaged.has(key)) {
          const skippedField = el('p', `${data.fields[key]}: ${source.reason}`, block);
          skippedField.className = 'muted';
          return;
        }
        if (isLocked && !currentManaged.has(key)) {
          const skippedField = el('p', `${data.fields[key]}: защищено от обновления. Снимите защиту в группе связи.`, block);
          skippedField.className = 'muted';
          return;
        }
        const detail = isLocked
          ? 'защищено от обновления'
          : source.available
            ? `${displayFieldValue(key, selection.property.values[key])} → ${displayFieldValue(key, source.value)}`
            : source.reason;
        const input = checkbox(
          block,
          `${data.fields[key]}: ${detail}`,
          requested.has(key),
        );
        input.parentElement.className = 'review-field';
        input.addEventListener('change', () => {
          if (input.checked) selection.fieldKeys.add(key);
          else selection.fieldKeys.delete(key);
          selection.renderFields();
          markDirty();
        });
        fields.push({
          key, input, before: selection.property.values[key], after: source.value,
          apply: source.available && !isLocked,
        });
      });
      pending.push({
        property: selection.property.id,
        original_units: selection.property.original_units,
        original_managed_fields: selection.property.managed_fields || [],
        units: units.map(unit => unit.id),
        fields,
        is_active: selection.activeInput.checked,
        expected_is_active: selection.property.is_active,
      });
    }
    save.hidden = !pending.length;
    if (pending.length) {
      selectionStage.hidden = true;
      reviewStage.hidden = false;
      setStep('three');
      save.textContent = `Сохранить (${pending.length})`;
      reviewStage.scrollIntoView({behavior: 'smooth', block: 'start'});
    } else {
      setMessage('Выберите хотя бы одну карточку и предложение для сопоставления.', 'error');
    }
  });

  save.addEventListener('click', async () => {
    save.disabled = true;
    setMessage('Сохраняем соответствия…');
    try {
      const result = await post({
        action: 'save_links',
        project: data.project,
        rows: pending.map(row => ({
          ...row,
          expected: Object.fromEntries(row.fields.filter(field => field.input.checked && field.apply).map(field => [field.key, {
            before: field.before,
            after: field.after,
          }])),
          fields: row.fields.filter(field => field.input.checked && field.apply).map(field => field.key),
          managed_fields: row.fields.filter(field => field.input.checked).map(field => field.key),
        })),
      });
      hasUnsavedChanges = false;
      pending.forEach(row => { delete savedRows[row.property]; });
      writeDraft();
      setMessage(`Готово: сохранено соответствий — ${result.count}.`, 'success');
      renderSaveReport(result.rows || []);
      reviewStage.hidden = true;
      setStep('done');
      document.getElementById('success-actions').hidden = false;
    } catch (error) {
      setMessage(error.message, 'error');
      save.disabled = false;
    }
  });
})();
