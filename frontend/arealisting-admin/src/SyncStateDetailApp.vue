<script setup lang="ts">
type StateRow = {
  id: number; key: string; name: string; is_lock: boolean; stale: boolean;
  status: string; status_label: string; current_started_at: string;
  last_successful_sync_at: string; updated_at: string; last_error: string; url: string;
};
type DetailData = { row: StateRow; back_url: string; history_url: string };
defineProps<{ data: DetailData }>();
</script>

<template>
  <a :href="data.back_url">← К состоянию синхронизации</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge" :data-status="data.row.status.toLowerCase()">{{ data.row.status_label }}</span></div><h2>{{ data.row.name }}</h2><p class="muted">Ключ: {{ data.row.key }}</p><p v-if="data.row.stale" class="dashboard-alert">Запуск числится активным дольше двух часов. Проверьте историю обновлений и последнюю ошибку.</p><p v-if="data.row.last_error" class="dashboard-alert" role="alert">{{ data.row.last_error }}</p></section>
  <section class="work-queue"><h2>Даты и состояние</h2><dl class="asset-detail-facts"><div v-if="data.row.current_started_at"><dt>Текущий запуск начат</dt><dd>{{ data.row.current_started_at }}</dd></div><div v-if="!data.row.is_lock"><dt>Данные успешно обработаны по</dt><dd>{{ data.row.last_successful_sync_at || 'Ещё не обработаны' }}</dd></div><div><dt>Состояние обновлено</dt><dd>{{ data.row.updated_at }}</dd></div></dl><p class="muted">{{ data.row.is_lock ? 'Это общая блокировка одновременных запусков.' : 'Эта дата используется при следующем получении изменений раздела.' }}</p><a v-if="data.history_url" :href="data.history_url">Открыть историю обновлений →</a></section>
</template>
