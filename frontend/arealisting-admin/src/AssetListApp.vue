<script setup lang="ts">
import { computed, ref } from 'vue';

type Asset = {
  id: number; title: string; type: string; type_label: string;
  project: string; unit: string; source_url: string; preview_url: string; source_key: string;
  position: number; is_active: boolean; state: string; error: string; updated_at: string;
  can_retry: boolean; detail_url: string; retry_url: string;
  linked_cards: { title: string; url: string }[];
};
type AssetData = {
  base_url: string; vue_preview: boolean;
  state: string; asset_type: string; activity: string; query: string; project: string;
  types: { value: string; label: string }[];
  counts: { all: number; error: number; downloaded: number; url: number };
  state_urls: Record<string, string>; result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  can_retry: boolean; can_view_groups: boolean; groups_url: string;
  assets: Asset[];
};

const props = defineProps<{ data: AssetData }>();
const assets = ref<Asset[]>(props.data.assets);
const selected = ref<number[]>([]);
const query = ref(props.data.query);
const project = ref(props.data.project);
const assetType = ref(props.data.asset_type);
const activity = ref(props.data.activity);
const running = ref(false);
const progress = ref({ done: 0, total: 0 });
const results = ref<string[]>([]);
const csrfToken = document.querySelector<HTMLInputElement>('.asset-list-page > input[name="csrfmiddlewaretoken"]')?.value || '';
const eligible = computed(() => assets.value.filter(asset => asset.can_retry).map(asset => asset.id));
const selectedCount = computed(() => selected.value.length);

function toggleAll() {
  selected.value = eligible.value.every(id => selected.value.includes(id))
    ? [] : eligible.value.slice(0, 10);
}
function toggle(id: number) {
  if (selected.value.includes(id)) selected.value = selected.value.filter(value => value !== id);
  else if (selected.value.length < 10) selected.value = [...selected.value, id];
}
function isImage(asset: Asset) {
  return ['PROJECT_GALLERY', 'UNIT_GALLERY', 'FLOOR_PLAN', 'MASTER_PLAN', 'PHOTOS_RENDERS'].includes(asset.type);
}
function stateLabel(state: string) {
  return ({ error: 'Ошибка', downloaded: 'Загружено', url: 'Только URL' } as Record<string, string>)[state] || state;
}
async function retry(ids: number[]) {
  if (running.value || !ids.length) return;
  running.value = true;
  progress.value = { done: 0, total: ids.length };
  results.value = [];
  for (const id of ids) {
    const asset = assets.value.find(item => item.id === id);
    if (!asset) continue;
    try {
      const body = new URLSearchParams({ format: 'json', csrfmiddlewaretoken: csrfToken });
      const response = await fetch(asset.retry_url, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      if (!response.ok) throw new Error(`Сервер вернул ${response.status}.`);
      const result = await response.json() as { downloaded: number; failed: number; skipped: number; state: string; error: string };
      asset.state = result.state;
      asset.error = result.error;
      if (result.downloaded) {
        asset.can_retry = false;
        results.value.push(`#${id}: изображение загружено.`);
      } else if (result.failed) results.value.push(`#${id}: ${result.error || 'Загрузка не удалась.'}`);
      else results.value.push(`#${id}: пропущено; файл уже загружен или материал не подходит.`);
    } catch (error) {
      results.value.push(`#${id}: ${error instanceof Error ? error.message : 'Не удалось выполнить запрос.'}`);
    }
    progress.value.done += 1;
    selected.value = selected.value.filter(value => value !== id);
  }
  running.value = false;
}
</script>

<template>
  <section class="workspace-intro">
    <h2>Материалы AREALISTING</h2>
    <p>Здесь хранятся исходные фото, планировки и документы. «Только URL» означает, что файл ещё не скачивали; документам локальный файл обычно не нужен.</p>
    <p v-if="data.can_view_groups">Чтобы добавить скачанное фото в карточку, откройте <a :href="data.groups_url">связь с карточкой</a> и запустите импорт фотографий.</p>
    <p v-if="data.project" class="muted">Комплекс №{{ data.project }} · <a :href="data.base_url + (data.vue_preview ? '?vue=1' : '')">Все комплексы →</a></p>
  </section>

  <nav class="price-review-statuses" aria-label="Состояние загрузки материалов">
    <a :href="data.state_urls['']" :aria-current="data.state === '' ? 'page' : undefined">Все <strong>{{ data.counts.all }}</strong></a>
    <a :href="data.state_urls.error" :aria-current="data.state === 'error' ? 'page' : undefined">С ошибкой <strong>{{ data.counts.error }}</strong></a>
    <a :href="data.state_urls.downloaded" :aria-current="data.state === 'downloaded' ? 'page' : undefined">Загружено <strong>{{ data.counts.downloaded }}</strong></a>
    <a :href="data.state_urls.url" :aria-current="data.state === 'url' ? 'page' : undefined">Только URL <strong>{{ data.counts.url }}</strong></a>
  </nav>

  <section class="work-queue">
    <div class="dashboard-heading"><div><h2>Материалы · {{ data.result_count }}</h2><p class="muted">Фильтры и поиск применяются ко всем материалам.</p></div></div>
    <form method="get" :action="data.base_url" class="price-review-filters">
      <input type="hidden" name="download_state" :value="data.state"><input v-if="data.vue_preview" type="hidden" name="vue" value="1">
      <label>Поиск<input v-model="query" type="search" name="q" placeholder="URL, ключ, комплекс или предложение"></label>
      <label>Комплекс №<input v-model="project" type="number" min="1" name="project" placeholder="Все"></label>
      <label>Тип<select v-model="assetType" name="asset_type__exact"><option value="">Все типы</option><option v-for="item in data.types" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <label>Активность<select v-model="activity" name="is_active__exact"><option value="">Все</option><option value="1">Активные</option><option value="0">Неактивные</option></select></label>
      <button type="submit">Показать</button>
    </form>
    <div v-if="data.can_retry && eligible.length" class="asset-bulk-bar">
      <button type="button" class="secondary" :disabled="running" @click="toggleAll">Выбрать до 10 на странице</button>
      <span>Выбрано: {{ selectedCount }} из 10</span>
      <button type="button" :disabled="running || !selectedCount" @click="retry([...selected])">Повторить загрузку выбранных</button>
    </div>
    <div v-if="running || results.length" class="asset-retry-report" role="status" aria-live="polite">
      <p v-if="running">Проверено {{ progress.done }} из {{ progress.total }}. Можно дождаться результата на этой странице.</p>
      <p v-else>Повтор завершён. <a :href="data.state_urls[data.state]">Обновить список и счётчики →</a></p>
      <ul><li v-for="(result, index) in results" :key="index">{{ result }}</li></ul>
    </div>
    <div v-if="assets.length" class="asset-list-grid">
      <article v-for="asset in assets" :key="asset.id" class="project-card asset-list-card" :class="{ 'has-error': asset.state === 'error' }">
        <div class="asset-list-media">
          <a v-if="isImage(asset) && asset.preview_url" :href="asset.source_url" target="_blank" rel="noopener noreferrer" :aria-label="`Открыть ${asset.title} в полном размере`"><img :src="asset.preview_url" alt="" loading="lazy"></a>
          <div v-else class="asset-list-placeholder">{{ asset.type_label }}</div>
        </div>
        <div class="asset-list-copy">
          <div class="price-review-meta"><span class="meta-badge" :data-status="asset.state">{{ stateLabel(asset.state) }}</span><span class="meta-badge">{{ asset.type_label }}</span><span v-if="!asset.is_active" class="meta-badge">Неактивен</span></div>
          <h3><a :href="asset.detail_url">{{ asset.title }}</a></h3>
          <p class="muted">{{ asset.project || 'Комплекс не указан' }}<template v-if="asset.unit"> · {{ asset.unit }}</template></p>
          <p class="muted">{{ asset.source_key }} · позиция {{ asset.position }} · {{ asset.updated_at }}</p>
          <p v-if="asset.error" class="dashboard-alert">{{ asset.error }}</p>
          <p v-if="asset.linked_cards.length" class="muted">Карточка: <a v-for="(card, index) in asset.linked_cards" :key="card.url" :href="card.url">{{ index ? ', ' : '' }}{{ card.title }}</a></p>
          <div class="asset-list-actions"><a :href="asset.detail_url">Подробнее →</a><a :href="asset.source_url" target="_blank" rel="noopener noreferrer">Открыть источник ↗</a>
            <button v-if="asset.can_retry" type="button" class="secondary" :disabled="running" @click="retry([asset.id])">Повторить загрузку</button>
            <label v-if="asset.can_retry" class="asset-select"><input type="checkbox" :checked="selected.includes(asset.id)" :disabled="running || (!selected.includes(asset.id) && selectedCount >= 10)" @change="toggle(asset.id)">Выбрать</label>
          </div>
        </div>
      </article>
    </div>
    <p v-else>Материалов с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы материалов"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
