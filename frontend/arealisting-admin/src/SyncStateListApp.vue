<script setup lang="ts">
type StateRow = {
  id: number; key: string; name: string; is_lock: boolean; stale: boolean;
  status: string; status_label: string; current_started_at: string;
  last_successful_sync_at: string; updated_at: string; last_error: string; url: string;
};
type ListData = {
  lock: StateRow | null; resources: StateRow[];
  latest_job: { status: string; status_label: string; created_at: string; error: string } | null;
  last_successful_at: string;
  latest_run: { id: number; status: string; status_label: string; started_at: string; url: string } | null;
  history_url: string;
};
defineProps<{ data: ListData }>();
</script>

<template>
  <section class="workspace-intro"><h2>Состояние синхронизации</h2><p>Здесь видно, идёт ли обновление и до какого момента обработаны данные каждого раздела AREALISTING.</p><div class="asset-list-actions"><a v-if="data.history_url" :href="data.history_url">История обновлений →</a></div></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Интеграция сейчас</h2><p class="muted">Общая блокировка защищает от одновременных запусков.</p></div></div>
    <article v-if="data.latest_job" class="work-queue-item sync-state-card" :class="{ 'has-error': data.latest_job.status === 'FAILED' }"><div><div class="price-review-meta"><span class="meta-badge" :data-status="data.latest_job.status.toLowerCase()">Фоновое обновление: {{ data.latest_job.status_label }}</span></div><p class="muted">Запрошено {{ data.latest_job.created_at }}</p><p v-if="data.latest_job.error" class="dashboard-alert">{{ data.latest_job.error }}</p></div></article>
    <article v-if="data.lock" class="work-queue-item sync-state-card" :class="{ 'has-error': data.lock.stale || data.lock.status === 'FAILED' }"><div><div class="price-review-meta"><span class="meta-badge" :data-status="data.lock.status.toLowerCase()">{{ data.lock.status_label }}</span></div><h3><a :href="data.lock.url">{{ data.lock.name }}</a></h3><p v-if="data.lock.current_started_at">Запуск начат {{ data.lock.current_started_at }}</p><p v-if="data.lock.stale" class="dashboard-alert">Блокировка висит дольше двух часов. Проверьте последний запуск и ошибку.</p><p v-if="data.lock.last_error" class="dashboard-alert">{{ data.lock.last_error }}</p><p class="muted">Состояние обновлено {{ data.lock.updated_at }}</p></div><a :href="data.lock.url">Подробности →</a></article>
    <p v-else>Общая блокировка ещё не создана. Она появится после начала синхронизации.</p>
    <p v-if="data.last_successful_at" class="sync-state-latest">Последнее успешное обновление завершено {{ data.last_successful_at }}.</p>
    <p v-if="data.latest_run" class="sync-state-latest">Последний запуск: <a :href="data.latest_run.url">#{{ data.latest_run.id }} · {{ data.latest_run.status_label }}</a> · {{ data.latest_run.started_at }}</p>
  </section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Разделы источника</h2><p class="muted">Дата в строке означает, до какого момента успешно обработаны изменения раздела.</p></div></div><div v-if="data.resources.length" class="work-queue-list"><article v-for="row in data.resources" :key="row.id" class="work-queue-item sync-state-card" :class="{ 'has-error': row.status === 'FAILED' }"><div><div class="price-review-meta"><span class="meta-badge" :data-status="row.status.toLowerCase()">{{ row.status_label }}</span></div><h3><a :href="row.url">{{ row.name }}</a></h3><p>Обработано по: <strong>{{ row.last_successful_sync_at || 'успешного обновления ещё не было' }}</strong></p><p v-if="row.last_error" class="dashboard-alert">{{ row.last_error }}</p><p class="muted">Состояние обновлено {{ row.updated_at }}</p></div><a :href="row.url">Подробности →</a></article></div><p v-else>Состояния разделов ещё не появились. Они создаются при синхронизации.</p></section>
</template>
