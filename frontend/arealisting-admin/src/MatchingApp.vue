<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import UnitChoice from './UnitChoice.vue';
import Card from 'primevue/card';
import StatIcon from './StatIcon.vue';
import { postAction } from './api';
import { buildSaveRow, fieldLocked, rowChanged, sourceFieldValue } from './model';
import type { FieldValue, MatchingData, Property, RowState, SavedRows, Unit } from './model';

const props = defineProps<{ data: MatchingData; unlinkedUrl: string; projectsUrl: string }>();
const data = props.data;
const previewSuffix = new URLSearchParams(window.location.search).get('vue') === '1' ? '&vue=1' : '';
const draftKey = `arealisting:matching:${data.user}:${data.project}`;
const unmatchedSelectionKey = `${draftKey}:unmatched`;
function storedRows(): SavedRows {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(draftKey) || '{}');
    const rows = parsed?.rows;
    if (!rows || typeof rows !== 'object' || Array.isArray(rows)) return {};
    return Object.fromEntries(Object.entries(rows).filter(([key, row]) =>
      /^\d+$/.test(key) && row && typeof row === 'object' && Array.isArray((row as RowState).units)
      && typeof (row as RowState).active === 'boolean')) as SavedRows;
  } catch { return {}; }
}
const saved = reactive<SavedRows>(storedRows());
const rows = reactive<Record<number, RowState>>(Object.fromEntries(data.properties.map(property => {
  const restored = saved[property.id];
  return [property.id, {
    title: property.title,
    units: restored?.units || data.units.filter(unit => unit.property === property.id).map(unit => unit.id),
    active: restored?.active ?? property.is_active,
    fields: restored?.fields || [...property.managed_fields],
  }];
})));
const stage = ref<'select' | 'review' | 'done'>('select');
const tab = ref<'matches' | 'unmatched'>('matches');
const message = ref('');
const messageTone = ref('');
const busy = ref(false);
const resultRows = ref<SaveReport[]>([]);
const free = data.units.filter(unit => !unit.occupied && !unit.skipped);
const skipped = data.units.filter(unit => !unit.occupied && unit.skipped);
function restoredFreeSelection(): number[] {
  try {
    const raw = sessionStorage.getItem(unmatchedSelectionKey);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    const available = new Set(free.map(unit => unit.id));
    const valid = Array.isArray(parsed) ? [...new Set(parsed.filter((id): id is number =>
      typeof id === 'number' && Number.isInteger(id) && available.has(id)))] : [];
    if (JSON.stringify(valid) !== raw) {
      if (valid.length) sessionStorage.setItem(unmatchedSelectionKey, JSON.stringify(valid));
      else sessionStorage.removeItem(unmatchedSelectionKey);
    }
    return valid;
  } catch {
    try { sessionStorage.removeItem(unmatchedSelectionKey); } catch { /* Storage unavailable. */ }
    return [];
  }
}
const selectedFree = ref<number[]>(restoredFreeSelection());
if (selectedFree.value.length && !new URLSearchParams(window.location.search).has('property')) tab.value = 'unmatched';
const selectedSkipped = ref<number[]>([]);
const propertyFilter = ref<'all' | 'unlinked' | 'changed'>('all');
const statusFilter = ref('all');
const numberFilter = ref('');
const bedroomsFilter = ref('all');
const skipReason = ref('');
const draftPreview = ref<DraftPreview | null>(null);
const draftUnits = ref<number[]>([]);
const locationChoice = ref('');
const selectedMedia = ref<number[]>([]);
const draftResult = ref<{ title: string; url: string; media_job_url: string } | null>(null);
const shownImages = reactive<Record<string, number>>({});
let transientDirty = false;
function persistSelectedFree() {
  try {
    if (selectedFree.value.length) sessionStorage.setItem(unmatchedSelectionKey, JSON.stringify(selectedFree.value));
    else sessionStorage.removeItem(unmatchedSelectionKey);
  } catch { transientDirty = true; }
}
watch(selectedFree, persistSelectedFree, { flush: 'sync' });

type Image = { id: number; url: string; role: string };
type MediaGroup = { id: number; number: string; status: string; images: Image[]; images_total: number };
type DraftPreview = {
  title_ru: string; title_en: string; property_type: string; build_status: string; developer: string;
  district: string; location: string; bedrooms: number | null; bathrooms: number | null;
  area_total: number | null; area_land: number | null; floor: number | null; furnished: boolean | null;
  features_count: number; has_description_ru: boolean; has_description_en: boolean;
  latitude: number | null; longitude: number | null; source_price: number | null; source_currency: string;
  location_choice_required: boolean; selected_location_choice: string | number | null;
  location_options: { id: number; district: string; location: string; source_names: string[] }[];
  media_assets_total: number; project_images: Image[]; project_images_total: number; unit_images: MediaGroup[];
};
type SaveReport = {
  property_id: number; title: string; url: string; media_preview_url: string;
  changed_fields?: { field: string; before: FieldValue; after: FieldValue }[];
  activity_change?: { before: boolean; after: boolean };
  unchanged_fields?: string[]; managed_added?: string[]; managed_removed?: string[];
  not_applied?: { field: string; reason: string }[];
  unavailable_fields?: { field: string; reason: string }[];
};

const number = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value);
const display = (key: string, value: FieldValue | undefined) => value == null || value === '' ? '—'
  : key === 'build_status' ? ({ completed: 'Готовый объект', under_construction: 'Строящийся объект' }[String(value)] || String(value)) : String(value);
function originalProjectUnits(property: Property): number[] {
  return data.units.filter(unit => unit.property === property.id).map(unit => unit.id);
}
function changed(property: Property): boolean {
  return rowChanged(property, rows[property.id], originalProjectUnits(property));
}
const selectedProperties = computed(() => data.properties.filter(property => rows[property.id].units.length > 0));
const selectedUnitCount = computed(() => selectedProperties.value.reduce((count, property) => count + rows[property.id].units.length, 0));
const changedProperties = computed(() => selectedProperties.value.filter(changed));
const changedPropertyCount = computed(() => changedProperties.value.length);
const unlinkedPropertyCount = computed(() => data.properties.filter(property => !rows[property.id].units.length).length);
const changedPropertyCountInList = computed(() => data.properties.filter(changed).length);
const visibleProperties = computed(() => data.properties.filter(property =>
  propertyFilter.value === 'all' || (propertyFilter.value === 'unlinked'
    ? !rows[property.id].units.length : changed(property)))
  .sort((a, b) => Number(changed(b)) - Number(changed(a))));
const hiddenSaved = computed(() => Object.entries(saved).filter(([id]) => !data.properties.some(property => String(property.id) === id)));
const allMedia = computed(() => draftPreview.value ? [
  ...(draftPreview.value.project_images || []),
  ...(draftPreview.value.unit_images || []).flatMap(unit => unit.images || []),
] : []);
const selectedLocation = computed(() => draftPreview.value?.location_options?.find(option => String(option.id) === locationChoice.value));
const bedroomOptions = [...new Set(free.map(unit => unit.bedrooms).filter((value): value is number => value != null))]
  .sort((a, b) => a - b);
const hasUnknownBedrooms = free.some(unit => unit.bedrooms == null);
const selectedDraftUnits = computed(() => free.filter(unit => selectedFree.value.includes(unit.id)));
const visibleFree = computed(() => {
  const query = numberFilter.value.trim().toLocaleLowerCase('ru').replace(/^№\s*/, '');
  return free.filter(unit => !selectedFree.value.includes(unit.id)
    && (statusFilter.value === 'all' || unit.status === statusFilter.value)
    && (bedroomsFilter.value === 'all' || (bedroomsFilter.value === 'unknown'
      ? unit.bedrooms == null : String(unit.bedrooms) === bedroomsFilter.value))
    && (!query || String(unit.number || '').toLocaleLowerCase('ru').includes(query)));
});
const filtersActive = computed(() => statusFilter.value !== 'all' || bedroomsFilter.value !== 'all' || numberFilter.value.trim() !== '');

function showError(error: unknown) {
  message.value = error instanceof Error ? error.message : 'Не удалось выполнить действие. Повторите попытку.';
  messageTone.value = 'error';
  nextTick(() => document.getElementById('matching-message')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
}

function persist() {
  for (const property of data.properties) {
    const row = rows[property.id];
    if (changed(property)) saved[property.id] = { ...row, units: [...row.units], fields: [...row.fields] };
    else delete saved[property.id];
  }
  try {
    if (Object.keys(saved).length) sessionStorage.setItem(draftKey, JSON.stringify({ rows: saved }));
    else sessionStorage.removeItem(draftKey);
  } catch { transientDirty = true; }
}
watch(rows, persist, { deep: true });
function beforeUnload(event: BeforeUnloadEvent) {
  if (!transientDirty) return;
  event.preventDefault();
  event.returnValue = '';
}
window.addEventListener('beforeunload', beforeUnload);
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload));
function clearDraft() {
  Object.keys(saved).forEach(key => delete saved[key]);
  try { sessionStorage.removeItem(draftKey); } catch { /* Storage unavailable. */ }
  transientDirty = false;
  window.location.reload();
}
function selectedUnits(property: Property): Unit[] { return data.units.filter(unit => rows[property.id].units.includes(unit.id)); }
function candidates(property: Property): Unit[] {
  return data.units.filter(unit => (!unit.occupied || unit.property === property.id) && !unit.skipped)
    .sort((a, b) => Number(suggested(property, b)) - Number(suggested(property, a))
      || Number(b.status === 'AVAILABLE') - Number(a.status === 'AVAILABLE')
      || areaDifference(property, a) - areaDifference(property, b));
}
function areaDifference(property: Property, unit: Unit) {
  return unit.area_total == null || property.values.area_total == null ? Infinity
    : Math.abs(Number(unit.area_total) - Number(property.values.area_total));
}
function suggested(property: Property, unit: Unit) {
  return unit.bedrooms != null && unit.area_total != null && property.values.area_total != null
    && unit.bedrooms === property.values.bedrooms && areaDifference(property, unit) <= 1;
}
function primary(property: Property) { return candidates(property).filter(unit => suggested(property, unit) || unit.property === property.id); }
function other(property: Property) { return candidates(property).filter(unit => !suggested(property, unit) && unit.property !== property.id); }
function reason(property: Property, unit: Unit) {
  if (!suggested(property, unit)) return '';
  const difference = areaDifference(property, unit);
  return difference < .001 ? 'Совпадают спальни и площадь — всё равно проверьте номер и цену.'
    : `Столько же спален, разница площади ${number(difference)} м².`;
}
function toggleUnit(property: Property, unit: Unit, checked: boolean) {
  if (checked && assignedToOther(property, unit)) return;
  const row = rows[property.id];
  row.units = checked ? [...new Set([...row.units, unit.id])] : row.units.filter(id => id !== unit.id);
  if (!row.units.length) row.active = property.is_active;
  normalizeFields(property);
}
function assignedToOther(property: Property, unit: Unit): Property | undefined {
  return data.properties.find(candidate => candidate.id !== property.id && rows[candidate.id].units.includes(unit.id));
}
function lastRequiredUnit(property: Property, unit: Unit): boolean {
  const selected = rows[property.id].units;
  return selected.length === 1 && selected.includes(unit.id) && originalProjectUnits(property).length > 0;
}
function unitHint(property: Property, unit: Unit): string {
  const other = assignedToOther(property, unit);
  if (other) return `Уже выбрано для «${other.title}»`;
  if (lastRequiredUnit(property, unit)) return 'Чтобы заменить связь, сначала выберите другое предложение.';
  return reason(property, unit);
}
function normalizeFields(property: Property) {
  const row = rows[property.id];
  const units = selectedUnits(property);
  row.fields = row.fields.filter(key => property.managed_fields.includes(key)
    || (sourceFieldValue(data, key, units).available && !fieldLocked(property, key)));
}
function fieldChecked(property: Property, key: string) { return rows[property.id].fields.includes(key); }
function toggleField(property: Property, key: string, checked: boolean) {
  const row = rows[property.id];
  row.fields = checked ? [...new Set([...row.fields, key])] : row.fields.filter(field => field !== key);
}
function review() {
  message.value = '';
  const used = new Set<number>();
  for (const property of selectedProperties.value) {
    for (const id of rows[property.id].units) {
      if (used.has(id)) {
        message.value = 'Одно предложение нельзя связать с двумя карточками.';
        messageTone.value = 'error';
        nextTick(() => document.getElementById('matching-message')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
        return;
      }
      used.add(id);
    }
  }
  if (!selectedProperties.value.length) { message.value = 'Выберите хотя бы одну карточку и предложение.'; messageTone.value = 'error'; nextTick(() => document.getElementById('matching-message')?.scrollIntoView({ behavior: 'smooth', block: 'center' })); return; }
  stage.value = 'review';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function reviewFields(property: Property) {
  return [...new Set([...rows[property.id].fields, ...property.managed_fields])].filter(key => Object.hasOwn(data.fields, key));
}
async function save() {
  if (!changedProperties.value.length) return;
  busy.value = true;
  message.value = 'Сохраняем соответствия…';
  messageTone.value = '';
  try {
    const pending = changedProperties.value;
    const result = await postAction<{ count: number; rows: SaveReport[] }>({
      action: 'save_links', project: data.project,
      rows: pending.map(property => buildSaveRow(data, property, rows[property.id])),
    });
    for (const property of pending) delete saved[property.id];
    try { if (Object.keys(saved).length) sessionStorage.setItem(draftKey, JSON.stringify({ rows: saved }));
      else sessionStorage.removeItem(draftKey); } catch { /* Storage unavailable. */ }
    transientDirty = false;
    resultRows.value = result.rows || [];
    stage.value = 'done';
    message.value = `Готово: сохранено соответствий — ${result.count}.`;
    messageTone.value = 'success';
  } catch (error) { showError(error); }
  finally { busy.value = false; }
}
function toggleNumber(list: number[], id: number, checked: boolean): number[] {
  transientDirty = true;
  return checked ? [...new Set([...list, id])] : list.filter(value => value !== id);
}
function toggleSelectedFree(id: number, checked: boolean) {
  selectedFree.value = checked ? [...new Set([...selectedFree.value, id])] : selectedFree.value.filter(value => value !== id);
  draftPreview.value = null;
  draftUnits.value = [];
}
function clearSelectedFree() {
  selectedFree.value = [];
  draftPreview.value = null;
  draftUnits.value = [];
  selectedMedia.value = [];
}
function filterStatus(value: string) {
  statusFilter.value = value;
}
function clearUnitFilters() {
  statusFilter.value = 'all';
  bedroomsFilter.value = 'all';
  numberFilter.value = '';
}
async function previewDraft() {
  busy.value = true; draftPreview.value = null; draftResult.value = null; message.value = 'Проверяем данные…';
  messageTone.value = '';
  try {
    draftUnits.value = [...selectedFree.value];
    const result = await postAction<{ preview: DraftPreview }>({ action: 'preview_draft', project: data.project, units: draftUnits.value });
    draftPreview.value = result.preview;
    locationChoice.value = String(result.preview.selected_location_choice || '');
    selectedMedia.value = allMedia.value.map(image => image.id);
    message.value = '';
    await nextTick();
    document.querySelector('.draft-review')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) { showError(error); }
  finally { busy.value = false; }
}
async function createDraft() {
  busy.value = true; message.value = 'Создаём черновик…';
  messageTone.value = '';
  try {
    const created = await postAction<{ title: string; url: string; media_job_url: string }>({ action: 'create_draft', project: data.project,
      units: draftUnits.value, location_choice: locationChoice.value || null, media_assets: selectedMedia.value });
    draftResult.value = created;
    draftPreview.value = null;
    clearSelectedFree();
    transientDirty = false;
    message.value = created.media_job_url ? 'Черновик создан. Выбранные фото загружаются в фоне.' : 'Черновик создан без импорта фото.';
    messageTone.value = 'success';
    await nextTick();
    document.querySelector('.draft-review')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) { showError(error); }
  finally { busy.value = false; }
}
async function skip() {
  busy.value = true; message.value = 'Сохраняем решение…';
  messageTone.value = '';
  try { await postAction({ action: 'skip_units', project: data.project, units: selectedFree.value, reason: skipReason.value.trim() }); clearSelectedFree(); transientDirty = false; window.location.reload(); }
  catch (error) { showError(error); busy.value = false; }
}
async function restore() {
  busy.value = true; message.value = 'Возвращаем предложения в очередь…';
  messageTone.value = '';
  try { await postAction({ action: 'restore_units', project: data.project, units: selectedSkipped.value }); transientDirty = false; window.location.reload(); }
  catch (error) { showError(error); busy.value = false; }
}
function previewValues(): [string, string][] {
  const p = draftPreview.value;
  if (!p) return [];
  return [
    ['Название RU', p.title_ru], ['Название EN', p.title_en], ['Тип', p.property_type],
    ['Стадия', display('build_status', p.build_status)], ['Застройщик', p.developer || '—'],
    ['Район', selectedLocation.value?.district || p.district || 'требуется выбор'],
    ['Локация', selectedLocation.value?.location || p.location || 'требуется выбор'],
    ['Параметры', `${p.bedrooms ?? '—'} сп. · ${p.bathrooms ?? '—'} ванн. · ${number(p.area_total)} м² · этаж ${p.floor ?? '—'}`],
    ['Участок', p.area_land == null ? '—' : `${number(p.area_land)} м²`],
    ['Меблировка', p.furnished == null ? 'не указана' : p.furnished ? 'с мебелью' : 'без мебели'],
    ['Удобства', `${p.features_count} характеристик`],
    ['Описания', `RU: ${p.has_description_ru ? 'есть' : 'нет'} · EN: ${p.has_description_en ? 'есть' : 'нет'}`],
    ['Координаты', p.latitude == null || p.longitude == null ? '—' : `${p.latitude}, ${p.longitude}`],
    ['Цена источника', `от ${number(p.source_price)} ${p.source_currency}`],
  ];
}
</script>
<template>
  <div class="workflow-steps" aria-label="Этапы работы"><span>1. Выберите комплекс</span><span :aria-current="stage === 'select' ? 'step' : undefined">2. Подберите карточки</span><span :aria-current="stage === 'review' ? 'step' : undefined">3. Проверьте и сохраните</span><span v-if="stage === 'done'" aria-current="step">✓ Готово</span></div>
  <div v-if="message" id="matching-message" role="status" aria-live="polite" :class="messageTone ? `is-${messageTone}` : ''">{{ message }}</div>
  <section v-if="stage === 'select'" class="vue-matching-overview" aria-label="Сводка по комплексу">
    <Card class="arealisting-stat-card"><template #content><div class="arealisting-stat-top"><span>Карточки в подборе</span><StatIcon name="cards" /></div><strong>{{ data.properties.length }}</strong><small>Карточки Undersun</small></template></Card>
    <Card class="arealisting-stat-card"><template #content><div class="arealisting-stat-top"><span>Без карточки</span><StatIcon name="inbox" /></div><strong>{{ free.length }}</strong><small>Нужен выбор действия</small></template></Card>
    <Card class="arealisting-stat-card"><template #content><div class="arealisting-stat-top"><span>Выбрано предложений</span><StatIcon name="check" /></div><strong>{{ selectedUnitCount }}</strong><small>В текущем выборе</small></template></Card>
  </section>
  <p v-if="stage === 'select'" class="vue-matching-help">Сначала выберите карточку Undersun и подходящие предложения AREALISTING. Затем проверьте, какие данные перейдут в карточку, и сохраните результат.</p>
  <section v-if="Object.keys(saved).length" class="matching-draft-status" aria-live="polite">
    <strong>Сохранён выбор для {{ Object.keys(saved).length }} карточек в этой вкладке.</strong>
    <div v-if="hiddenSaved.length" class="matching-draft-links">Вернуться к выбору:
      <a v-for="[id, row] in hiddenSaved" :key="id" :href="`?project=${data.project}&property=${id}${previewSuffix}`">{{ row.title || `Карточка #${id}` }}</a>
    </div>
    <button type="button" class="secondary" @click="clearDraft">Очистить выбор карточек</button>
  </section>

  <template v-if="stage === 'select'">
    <p class="muted">Показываем до 100 карточек. Незавершённый выбор сохраняется в этой вкладке браузера для каждого комплекса.</p>
    <div class="matching-toolbar matching-tabs" role="tablist">
      <button type="button" role="tab" :aria-selected="tab === 'matches'" :aria-pressed="tab === 'matches'" @click="tab = 'matches'">Карточки Undersun ({{ data.properties.length }})</button>
      <button type="button" role="tab" :aria-selected="tab === 'unmatched'" :aria-pressed="tab === 'unmatched'" @click="tab = 'unmatched'">Ещё не связаны ({{ free.length }})</button>
    </div>
    <section v-if="tab === 'matches'" id="matches">
      <section class="matching-field-intro"><h2>Какие данные перенести в карточки?</h2><p>Выберите предложения справа, затем отметьте нужные поля внутри каждой карточки. Значения AREALISTING видны сразу; поля без данных или с разными значениями выбрать нельзя. Включённое поле будет обновляться при следующих синхронизациях, а снятая галочка отключит обновление ранее выбранного поля. Цена обновляется отдельно по минимальной цене доступных выбранных предложений после следующего успешного получения данных.</p></section>
      <div v-if="!data.properties.length" class="empty-state"><h3>Карточки для этого комплекса не найдены</h3><p>Поищите карточку по названию выше. Если её ещё нет, откройте предложения без карточки и проверьте создание черновика.</p><button type="button" @click="tab = 'unmatched'">Посмотреть предложения без карточки →</button></div>
      <nav v-if="data.properties.length" class="segmented-control property-work-filter" aria-label="Фильтр карточек Undersun"><span>Показать:</span><button type="button" :aria-pressed="propertyFilter === 'all'" @click="propertyFilter = 'all'">Все ({{ data.properties.length }})</button><button type="button" :aria-pressed="propertyFilter === 'unlinked'" @click="propertyFilter = 'unlinked'">Без предложения ({{ unlinkedPropertyCount }})</button><button type="button" :aria-pressed="propertyFilter === 'changed'" @click="propertyFilter = 'changed'">С изменениями ({{ changedPropertyCountInList }})</button><span class="filter-summary" aria-live="polite">Показано: {{ visibleProperties.length }}</span></nav>
      <p v-if="data.properties.length && !visibleProperties.length" class="empty-inline">{{ propertyFilter === 'unlinked' ? 'Все показанные карточки уже с предложениями.' : 'В показанных карточках пока нет изменений.' }}</p>
      <article v-for="property in visibleProperties" :key="property.id" class="match-row" :class="{ 'has-selection': rows[property.id].units.length }">
        <div class="local-property"><small>КАРТОЧКА UNDERSUN</small>
          <a class="property-title" :href="property.url" target="_blank" rel="noopener">{{ property.title }}</a>
          <img v-if="property.photo" class="local-photo" :src="property.photo" alt="" loading="lazy">
          <p>{{ property.values.bedrooms ?? '—' }} сп. · {{ number(property.values.area_total as number | null) }} м² · этаж {{ property.values.floor ?? '—' }}</p>
          <p class="publication-state" :class="property.is_active ? 'is-active' : 'is-inactive'">{{ property.is_active ? 'Активна на сайте' : 'Неактивна' }}</p>
          <label class="activity-toggle"><input v-model="rows[property.id].active" type="checkbox" :disabled="!rows[property.id].units.length"> Показывать карточку на сайте</label>
        </div>
        <div class="remote-units"><small>ПРЕДЛОЖЕНИЯ AREALISTING</small><span v-if="rows[property.id].units.length" class="vue-selection-badge">Выбрано: {{ rows[property.id].units.length }}</span>
          <p class="candidate-summary">{{ candidates(property).filter(unit => unit.property === property.id).length ? `Сейчас связано: ${candidates(property).filter(unit => unit.property === property.id).length}. ` : '' }}Близких по параметрам: {{ candidates(property).filter(unit => suggested(property, unit)).length }}.</p>
          <div class="unit-list">
            <UnitChoice v-for="unit in primary(property)" :key="unit.id" :unit="unit" :model-value="rows[property.id].units.includes(unit.id)" :linked="unit.property === property.id" :suggested="suggested(property, unit)" :disabled="Boolean(assignedToOther(property, unit)) || lastRequiredUnit(property, unit)" :reason="unitHint(property, unit)" @update:model-value="toggleUnit(property, unit, $event)" />
            <p v-if="!candidates(property).length" class="empty-inline">Нет свободных предложений для связи с этой карточкой.</p>
            <p v-else-if="!candidates(property).some(unit => suggested(property, unit))" class="muted">Точного кандидата по спальням и площади нет — проверьте остальные предложения.</p>
            <p v-if="selectedUnits(property).length && selectedUnits(property).every(unit => unit.status === 'SOLD') && rows[property.id].active" class="matching-warning">Все выбранные предложения проданы, но карточка останется активной.</p>
          </div>
          <details v-if="other(property).length" class="other-units"><summary>Остальные предложения комплекса ({{ other(property).length }})</summary><div class="unit-list"><UnitChoice v-for="unit in other(property)" :key="unit.id" :unit="unit" :model-value="rows[property.id].units.includes(unit.id)" :disabled="Boolean(assignedToOther(property, unit)) || lastRequiredUnit(property, unit)" :reason="unitHint(property, unit)" @update:model-value="toggleUnit(property, unit, $event)" /></div></details>
        </div>
        <details v-if="rows[property.id].units.length" class="match-field-panel"><summary>Настроить перенос данных в карточку <span class="vue-selection-badge">Выбрано полей: {{ rows[property.id].fields.length }}</span></summary><p class="muted">Отметьте поля для этой карточки. Снятие отметки с уже управляемого поля отключит его обновление из AREALISTING.</p>
          <div class="match-field-grid"><label v-for="(label, key) in data.fields" :key="key" class="match-field-option" :class="{ 'is-unavailable': !sourceFieldValue(data, String(key), selectedUnits(property)).available || fieldLocked(property, String(key)) }">
            <input type="checkbox" :checked="fieldChecked(property, String(key))" :disabled="(!sourceFieldValue(data, String(key), selectedUnits(property)).available || fieldLocked(property, String(key))) && !property.managed_fields.includes(String(key))" @change="toggleField(property, String(key), ($event.target as HTMLInputElement).checked)">
            <span><strong>{{ label }}</strong><small>{{ sourceFieldValue(data, String(key), selectedUnits(property)).available ? `Сейчас: ${display(String(key), property.values[String(key)])} → AREALISTING: ${display(String(key), (sourceFieldValue(data, String(key), selectedUnits(property)) as {value: FieldValue}).value)}` : (sourceFieldValue(data, String(key), selectedUnits(property)) as {reason: string}).reason }}</small><small v-if="property.managed_fields.includes(String(key))">{{ fieldLocked(property, String(key)) ? 'Уже управляется, но защищено от обновления' : 'Уже обновляется из AREALISTING' }}</small><small v-else-if="fieldLocked(property, String(key))">Поле защищено от обновления</small></span>
          </label></div>
        </details>
      </article>
      <div class="matching-footer"><span aria-live="polite">{{ selectedProperties.length ? `Карточки: ${selectedProperties.length} · предложения: ${selectedUnitCount} · изменено: ${changedPropertyCount}` : 'Выберите хотя бы одно предложение справа от карточки' }}</span><button type="button" :disabled="!selectedProperties.length || busy" @click="review">Проверить выбор →</button></div>
    </section>
    <section v-else id="unmatched"><h2>Предложения без карточки Undersun</h2><p>Сначала убедитесь, что нужной карточки нет во вкладке «Карточки Undersun». Затем можно создать неактивный черновик или пропустить предложение.</p>
      <div class="unmatched-filter-bar">
        <label>Номер предложения<input v-model="numberFilter" type="search" placeholder="Например, A-101" autocomplete="off"></label>
        <label>Спальни<select v-model="bedroomsFilter"><option value="all">Любое количество</option><option v-for="bedrooms in bedroomOptions" :key="bedrooms" :value="String(bedrooms)">{{ bedrooms }} сп.</option><option v-if="hasUnknownBedrooms" value="unknown">Не указано</option></select></label>
        <button v-if="filtersActive" type="button" class="secondary" @click="clearUnitFilters">Сбросить фильтры</button>
      </div>
      <nav class="segmented-control unit-status-filter" aria-label="Статус предложений AREALISTING"><span>Статус:</span><button v-for="status in ['all', 'AVAILABLE', 'SOLD']" :key="status" type="button" :aria-pressed="statusFilter === status" @click="filterStatus(status)">{{ { all: 'Все', AVAILABLE: 'Доступные', SOLD: 'Проданные' }[status] }} ({{ status === 'all' ? free.length : free.filter(unit => unit.status === status).length }})</button><span class="filter-summary" aria-live="polite">Найдено: {{ visibleFree.length }}</span></nav>
      <section v-if="selectedDraftUnits.length" class="selected-unit-panel" aria-label="Выбранные предложения"><div class="selected-unit-heading"><h3>Выбрано для действия · {{ selectedDraftUnits.length }}</h3><button type="button" class="secondary" :disabled="busy" @click="clearSelectedFree">Снять весь выбор</button></div><p class="muted">Выбор сохраняется в этой вкладке браузера и восстановится после обновления страницы.</p><div class="unit-list standalone-unit-list"><UnitChoice v-for="unit in selectedDraftUnits" :key="unit.id" :unit="unit" :model-value="true" :disabled="busy" @update:model-value="toggleSelectedFree(unit.id, $event)" /></div></section>
      <div class="unit-list standalone-unit-list"><UnitChoice v-for="unit in visibleFree" :key="unit.id" :unit="unit" :model-value="false" :disabled="busy" @update:model-value="toggleSelectedFree(unit.id, $event)" /></div>
      <p v-if="!free.length" class="empty-inline">Новых предложений для разбора нет.</p><p v-else-if="!visibleFree.length" class="empty-inline">{{ selectedDraftUnits.length ? 'Других предложений по фильтрам нет.' : 'По этим фильтрам предложений нет.' }}</p>
      <div class="unmatched-actions"><strong class="action-selection-count">{{ selectedFree.length ? `Выбрано: ${selectedFree.length}` : 'Ничего не выбрано' }}</strong><button v-if="data.can_create_draft" type="button" :disabled="busy || !selectedFree.length" @click="previewDraft">Проверить черновик</button><button type="button" class="secondary" :disabled="busy || !selectedFree.length" @click="skip">Пропустить</button><label class="skip-reason">Причина пропуска <input v-model="skipReason" type="text" maxlength="255" placeholder="Необязательно"></label></div>
      <section v-if="draftPreview" class="draft-review"><h3>Проверьте неактивный черновик</h3><dl class="draft-preview-grid"><div v-for="[label, value] in previewValues()" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div></dl>
        <section v-if="draftPreview.location_choice_required" class="draft-location-choice"><h4>Выберите локацию для этого черновика</h4><p>У комплекса подтверждено несколько локаций. AREALISTING не указывает, к какой из них относится каждый юнит. Для другой локации создайте отдельный черновик из соответствующих юнитов.</p><label>Локация Undersun <select v-model="locationChoice"><option value="">— выберите локацию —</option><option v-for="option in draftPreview.location_options" :key="option.id" :value="String(option.id)">{{ option.district }}{{ option.location ? ` → ${option.location}` : '' }}{{ option.source_names?.length ? ` · AREALISTING: ${option.source_names.join(', ')}` : '' }}</option></select></label></section>
        <details class="draft-media-review"><summary>Фотографии и планировки из AREALISTING — выбрано {{ selectedMedia.length }} из {{ allMedia.length }}</summary><div class="draft-media-content"><p class="muted">Изображения загружаются при открытии раздела. Отметьте файлы, которые нужно добавить в черновик.</p><div class="draft-media-controls"><strong>Выбрано изображений: {{ selectedMedia.length }} из {{ allMedia.length }}</strong><button type="button" class="secondary" :disabled="selectedMedia.length === allMedia.length" @click="selectedMedia = allMedia.map(image => image.id)">Выбрать все</button><button type="button" class="secondary" :disabled="!selectedMedia.length" @click="selectedMedia = []">Снять все</button></div>
          <article v-if="draftPreview.project_images.length" class="draft-unit-media"><div class="draft-media-heading"><strong>Общая галерея комплекса</strong><span class="muted">Показано {{ draftPreview.project_images.length }} из {{ draftPreview.project_images_total }}</span></div><div class="draft-unit-gallery"><div v-for="image in draftPreview.project_images.slice(0, shownImages.project || 4)" :key="image.id" class="draft-media-option"><label><input v-model="selectedMedia" type="checkbox" :value="image.id"><img :src="image.url" alt="Фото общей галереи" loading="lazy"></label><div class="draft-media-option-footer"><span class="meta-badge" :class="{ 'is-floorplan': image.role === 'FLOOR_PLAN' }">{{ image.role === 'FLOOR_PLAN' ? 'Планировка' : 'Галерея' }}</span><a :href="image.url" target="_blank" rel="noopener">Открыть</a></div></div></div><button v-if="(shownImages.project || 4) < draftPreview.project_images.length" type="button" class="secondary draft-media-more" @click="shownImages.project = (shownImages.project || 4) + 4">Показать ещё</button></article>
          <article v-for="unit in draftPreview.unit_images" :key="unit.id" class="draft-unit-media"><div class="draft-media-heading"><strong>Юнит № {{ unit.number || 'без номера' }}</strong><span class="status-badge" :class="unit.status === 'AVAILABLE' ? 'is-available' : 'is-sold'">{{ unit.status === 'AVAILABLE' ? 'Доступен' : 'Продан' }}</span><span v-if="unit.images_total > unit.images.length" class="muted">Показано {{ unit.images.length }} из {{ unit.images_total }}</span></div><div v-if="unit.images.length" class="draft-unit-gallery"><div v-for="image in unit.images.slice(0, shownImages[unit.id] || 4)" :key="image.id" class="draft-media-option"><label><input v-model="selectedMedia" type="checkbox" :value="image.id"><img :src="image.url" :alt="`Фото юнита № ${unit.number}`" loading="lazy"></label><div class="draft-media-option-footer"><span class="meta-badge" :class="{ 'is-floorplan': image.role === 'FLOOR_PLAN' }">{{ image.role === 'FLOOR_PLAN' ? 'Планировка' : 'Галерея' }}</span><a :href="image.url" target="_blank" rel="noopener">Открыть</a></div></div></div><p v-else class="muted">Фото не найдены.</p><button v-if="(shownImages[unit.id] || 4) < unit.images.length" type="button" class="secondary draft-media-more" @click="shownImages[unit.id] = (shownImages[unit.id] || 4) + 4">Показать ещё</button></article>
        </div></details><p class="matching-warning">Карточка будет создана неактивной и не появится на сайте до отдельной публикации.</p><button type="button" :disabled="busy || (draftPreview.location_choice_required && !locationChoice)" @click="createDraft">Создать неактивный черновик</button>
      </section>
      <section v-if="draftResult" class="draft-review"><h3>Черновик «{{ draftResult.title }}» создан</h3><p>{{ draftResult.media_job_url ? 'Загрузка фото продолжается в фоне. Прогресс и ошибки видны на странице задания.' : 'Фото можно добавить позже через группу связи.' }}</p><a v-if="draftResult.media_job_url" class="primary-action" :href="draftResult.media_job_url">Посмотреть загрузку фото →</a> <a class="primary-action" :href="draftResult.url">Открыть и проверить карточку →</a></section>
      <details v-if="skipped.length" class="skipped-section"><summary>Пропущенные предложения ({{ skipped.length }})</summary><div class="unit-list"><UnitChoice v-for="unit in skipped" :key="unit.id" :unit="unit" :reason="unit.skip_reason ? `Причина: ${unit.skip_reason}` : 'Причина не указана'" :model-value="selectedSkipped.includes(unit.id)" @update:model-value="selectedSkipped = toggleNumber(selectedSkipped, unit.id, $event)" /></div><button type="button" class="secondary" :disabled="busy || !selectedSkipped.length" @click="restore">Вернуть выбранные в очередь</button></details>
    </section>
  </template>

  <section v-if="stage === 'review'" class="review-stage"><h2>Проверьте перед сохранением</h2><p>Ниже показаны выбранные связи. Сохраняются только карточки с изменениями. Для уже управляемого поля снятая галочка отключит последующее обновление из AREALISTING.</p>
    <p v-if="!changedPropertyCount" class="vue-no-changes">Изменений пока нет. Вернитесь к выбору, чтобы изменить предложение, публикацию или поля.</p>
    <article v-for="property in selectedProperties" :key="property.id" class="review-card"><h3>{{ property.title }} <span class="vue-selection-badge">{{ changed(property) ? 'Будет сохранено' : 'Без изменений' }}</span></h3><p>Связать с: {{ selectedUnits(property).map(unit => `№ ${unit.number || 'без номера'}`).join(', ') }}</p><p v-if="selectedUnits(property).every(unit => unit.status === 'SOLD') && rows[property.id].active" class="matching-warning">Все выбранные предложения проданы, но карточка останется активной.</p><p v-if="rows[property.id].active !== property.is_active" class="review-change">Активность: {{ property.is_active ? 'активна' : 'неактивна' }} → {{ rows[property.id].active ? 'активна' : 'неактивна' }}</p><p class="muted">Отметка означает, что AREALISTING управляет полем при следующих обновлениях. Снимите её, чтобы оставить поле под ручным управлением.</p><label v-for="key in reviewFields(property)" :key="key" class="review-field"><input type="checkbox" :checked="fieldChecked(property, key)" @change="toggleField(property, key, ($event.target as HTMLInputElement).checked)"> {{ data.fields[key] }}: {{ fieldLocked(property, key) ? 'защищено от обновления' : sourceFieldValue(data, key, selectedUnits(property)).available ? `${display(key, property.values[key])} → ${display(key, (sourceFieldValue(data, key, selectedUnits(property)) as {value: FieldValue}).value)}` : (sourceFieldValue(data, key, selectedUnits(property)) as {reason: string}).reason }}</label></article>
    <div class="matching-footer"><button type="button" class="secondary" :disabled="busy" @click="stage = 'select'">← Вернуться к выбору</button><button type="button" :disabled="busy || !changedPropertyCount" @click="save">{{ busy ? 'Сохраняем…' : `Сохранить изменения (${changedPropertyCount})` }}</button></div>
  </section>
  <section v-if="stage === 'done'" class="matching-save-report" aria-live="polite"><h2>Результат по карточкам</h2><p class="muted">Цена пересчитывается отдельно при следующем успешном получении данных AREALISTING.</p><article v-for="row in resultRows" :key="row.property_id" class="matching-save-card"><h3><a :href="row.url">{{ row.title || `Карточка #${row.property_id}` }}</a></h3><template v-if="row.media_preview_url"><p class="muted">Связь сохранена. Фотографии добавляются отдельно: сначала проверьте, какие фото изменятся.</p><a class="primary-action" :href="row.media_preview_url">Проверить и импортировать фото →</a></template><template v-if="row.changed_fields?.length"><strong>Изменено сейчас:</strong><ul><li v-for="change in row.changed_fields" :key="change.field">{{ data.fields[change.field] || change.field }}: {{ display(change.field, change.before) }} → {{ display(change.field, change.after) }}</li></ul></template><p v-if="row.activity_change">Публикация: {{ row.activity_change.before ? 'активна' : 'неактивна' }} → {{ row.activity_change.after ? 'активна' : 'неактивна' }}.</p><p v-if="row.unchanged_fields?.length">Уже совпадали: {{ row.unchanged_fields.map(key => data.fields[key] || key).join(', ') }}.</p><p v-if="row.managed_added?.length">Включено дальнейшее обновление: {{ row.managed_added.map(key => data.fields[key] || key).join(', ') }}.</p><p v-if="row.managed_removed?.length">Отключено дальнейшее обновление: {{ row.managed_removed.map(key => data.fields[key] || key).join(', ') }}.</p><template v-if="row.not_applied?.length"><strong>Не обновлено сейчас:</strong><ul><li v-for="item in row.not_applied" :key="item.field">{{ data.fields[item.field] || item.field }}: {{ item.reason }}</li></ul></template><details v-if="row.unavailable_fields?.length"><summary>Поля без готовых данных в AREALISTING ({{ row.unavailable_fields.length }})</summary><ul><li v-for="item in row.unavailable_fields" :key="item.field">{{ data.fields[item.field] || item.field }}: {{ item.reason }}</li></ul></details><p v-if="!row.changed_fields?.length && !row.activity_change && !row.unchanged_fields?.length && !row.managed_added?.length && !row.managed_removed?.length && !row.not_applied?.length">Связь с предложениями сохранена. Другие поля карточки не менялись.</p></article></section>
  <div v-if="stage === 'done'" class="success-actions"><a class="primary-action" :href="unlinkedUrl">Объекты Undersun без связи</a><a :href="`?project=${data.project}${previewSuffix}`">Продолжить с этим комплексом</a><a :href="projectsUrl">Выбрать другой комплекс</a></div>
</template>
