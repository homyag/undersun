<script setup lang="ts">
type DetailData = {
  id: number; kind: string; created_at: string; title: string;
  detail: string; next_step: string; reviewed_at: string; reviewed_by: string;
  details: string; back_url: string; run_url: string; project_url: string;
  unit_url: string; property_url: string; review_url: string;
};
defineProps<{ data: DetailData }>();
</script>

<template>
  <a :href="data.back_url">← К журналу событий</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge">{{ data.kind }}</span><span class="muted">{{ data.created_at }}</span></div><h2>{{ data.title }}</h2><p v-if="data.detail">{{ data.detail }}</p><p><strong>Что проверить:</strong> {{ data.next_step }}</p><p class="muted">{{ data.reviewed_at ? `Проверено ${data.reviewed_at} · ${data.reviewed_by || 'Сотрудник не указан'}` : 'Ожидает проверки' }}</p><div class="asset-list-actions"><a v-if="data.run_url" :href="data.run_url">Запуск синхронизации →</a><a v-if="data.project_url" :href="data.project_url">Комплекс →</a><a v-if="data.unit_url" :href="data.unit_url">Предложение →</a><a v-if="data.property_url" :href="data.property_url">Карточка →</a><a v-if="data.review_url" :href="data.review_url">{{ data.kind === 'Цена ждёт подтверждения' ? 'Проверка цены' : 'Очередь проверки' }} →</a></div></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Данные события</h2><p class="muted">Подробности, сохранённые во время синхронизации.</p></div></div><pre class="sync-event-details">{{ data.details }}</pre></section>
</template>
