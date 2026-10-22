<script setup lang="ts">
type Row = { label: string; before: string; after: string };
type DetailData = {
  id: number; kind: string; property: string; project: string; actor: string;
  created_at: string; summary: string; rows: Row[];
  property_url: string; sync_run_url: string; back_url: string;
};
defineProps<{ data: DetailData }>();
</script>

<template>
  <a :href="data.back_url">← К истории изменений</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge">{{ data.kind }}</span><span class="muted">{{ data.created_at }}</span></div><h2>{{ data.property }}</h2><p class="muted">{{ data.project || 'Комплекс не указан' }} · {{ data.actor }}</p><p>{{ data.summary }}</p><div class="asset-list-actions"><a v-if="data.property_url" :href="data.property_url">Открыть карточку →</a><a v-if="data.sync_run_url" :href="data.sync_run_url">Открыть запуск синхронизации →</a></div></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Что изменилось</h2><p class="muted">Значения до и после изменения карточки.</p></div></div><div v-if="data.rows.length" class="property-change-rows"><div v-for="(row, index) in data.rows" :key="index" class="work-queue-item property-change-row"><h3>{{ row.label }}</h3><div><span class="muted">Было</span><p>{{ row.before }}</p></div><div><span class="muted">Стало</span><p>{{ row.after }}</p></div></div></div><p v-else>Подробные значения для этой записи не сохранены.</p></section>
</template>
