<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

type Result = {
  asset_id: number | null; title: string | null; source_url: string | null;
  role: string | null; status: string | null; error: string | null;
};
type JobData = {
  id: number; status: string; status_label: string;
  group_name: string; property_name: string; group_url: string; property_url: string;
  preview_url: string; retry_url: string; job_url: string; poll_url: string;
  total: number; processed: number;
  totals: { created: number; updated: number; deleted: number; errors: number };
  error: string; results: Result[];
  preferred_main_asset_id: number | null; preferred_main_failed: boolean; can_retry: boolean;
};

const props = defineProps<{ data: JobData }>();
const job = ref<JobData>(props.data);
const pollError = ref('');
const lastUpdated = ref('');
const loading = ref(false);
const retrying = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.media-job-page > input[name="csrfmiddlewaretoken"]')?.value || '';
const active = computed(() => job.value.status === 'PENDING' || job.value.status === 'RUNNING');
let timer: number | undefined;
let controller: AbortController | undefined;
let closed = false;

function schedule() {
  if (closed || !active.value) return;
  timer = window.setTimeout(refresh, pollError.value ? 5000 : 3000);
}
async function refresh() {
  if (loading.value || closed) return;
  if (timer) window.clearTimeout(timer);
  loading.value = true;
  controller = new AbortController();
  try {
    const response = await fetch(job.value.poll_url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('Не удалось получить состояние загрузки.');
    job.value = await response.json() as JobData;
    pollError.value = '';
    lastUpdated.value = new Date().toLocaleTimeString('ru-RU');
  } catch (error) {
    if (!closed) pollError.value = error instanceof Error ? error.message : 'Не удалось получить состояние загрузки.';
  } finally {
    loading.value = false;
    schedule();
  }
}
function resultLabel(status: string | null) {
  return ({ created: 'Добавлено', updated: 'Обновлено', deleted: 'Удалено из карточки', error: 'Ошибка загрузки' } as Record<string, string>)[status || ''] || 'Обработано';
}
onMounted(() => { if (active.value) refresh(); });
onBeforeUnmount(() => {
  closed = true;
  if (timer) window.clearTimeout(timer);
  controller?.abort();
});
</script>

<template>
  <a :href="job.group_url">← К группе</a>
  <section class="workspace-intro">
    <h2>Импорт фото #{{ job.id }}: <span class="media-job-status" :data-status="job.status">{{ job.status_label }}</span></h2>
    <p>{{ job.group_name }} · Карточка <a v-if="job.property_url" :href="job.property_url">{{ job.property_name }}</a></p>
    <template v-if="active">
      <p>Загрузка продолжается в фоне. Страницу можно закрыть; данные обновляются автоматически.</p>
      <template v-if="job.total"><progress :value="job.processed" :max="job.total">{{ job.processed }} / {{ job.total }}</progress><p aria-live="polite">Обработано {{ job.processed }} из {{ job.total }}.</p></template>
      <p v-else>Ожидаем начала обработки…</p>
      <p v-if="lastUpdated" class="muted">Обновлено в {{ lastUpdated }}</p>
      <p v-if="pollError" class="dashboard-alert" role="alert">{{ pollError }} Повторим проверку автоматически. <button type="button" class="secondary" :disabled="loading" @click="refresh">Проверить сейчас</button></p>
    </template>
    <template v-else>
      <p><strong>Добавлено: {{ job.totals.created }} · Обновлено: {{ job.totals.updated }} · Удалено: {{ job.totals.deleted }} · Ошибок: {{ job.totals.errors }}</strong></p>
      <p v-if="job.error" class="dashboard-alert">{{ job.error }}</p>
      <p v-if="job.preferred_main_asset_id && job.preferred_main_failed" class="dashboard-alert">Выбранное главное фото не загрузилось. Проверьте текущее главное в карточке.</p>
      <p v-else-if="job.preferred_main_asset_id && job.status !== 'FAILED'">Выбранное фото установлено главным. Проверьте результат в карточке.</p>
      <div class="vue-media-job-links"><a v-if="job.property_url" class="primary-action" :href="job.property_url">Проверить фото в карточке →</a><a :href="job.preview_url">Изменить выбор фото</a></div>
    </template>
  </section>
  <section v-if="job.results.length" class="sync-dashboard">
    <h2>Результат по фотографиям</h2>
    <div class="media-job-results">
      <article v-for="(row, index) in job.results" :key="`${row.asset_id}-${index}`" class="media-job-result" :class="{ 'has-error': row.status === 'error' }">
        <a v-if="row.source_url" :href="row.source_url" target="_blank" rel="noopener noreferrer" :aria-label="`Открыть ${row.title || 'фото'} в полном размере`"><img :src="row.source_url" alt="" loading="lazy"></a>
        <div><strong>{{ row.title || `Фото #${row.asset_id}` }}</strong><p>{{ resultLabel(row.status) }} · {{ row.role === 'FLOOR_PLAN' ? 'Планировка' : 'Галерея' }}</p><p v-if="row.error" class="dashboard-alert">{{ row.error }}</p></div>
      </article>
    </div>
  </section>
  <form v-if="job.can_retry" method="post" :action="job.retry_url" @submit="retrying = true">
    <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken">
    <button type="submit" class="primary-action" :disabled="retrying">{{ retrying ? 'Запускаем повтор…' : 'Повторить только фото с ошибками' }}</button>
  </form>
</template>
