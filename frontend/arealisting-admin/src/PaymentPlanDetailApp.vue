<script setup lang="ts">
type Field = { label: string; value: string };
type Item = { title: string; fields: Field[] };
type DetailData = {
  id: number; name: string; external_id: string; project: string;
  description: string; items: Item[]; is_deleted: boolean;
  remote_updated_at: string; last_seen_at: string; synced_at: string;
  project_url: string; back_url: string;
};
defineProps<{ data: DetailData }>();
</script>

<template>
  <a :href="data.back_url">← К планам оплаты</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge">Этапов: {{ data.items.length }}</span><span v-if="data.is_deleted" class="meta-badge">Удалён в источнике</span></div><h2>{{ data.name }}</h2><p class="muted">{{ data.project }} · ID источника {{ data.external_id }}</p><p v-if="data.description" class="payment-plan-description">{{ data.description }}</p><a v-if="data.project_url" :href="data.project_url">Открыть комплекс →</a></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Этапы оплаты</h2><p class="muted">Поля и значения получены из AREALISTING.</p></div></div><div v-if="data.items.length" class="payment-plan-items"><article v-for="(item, index) in data.items" :key="index" class="work-queue-item"><h3>{{ item.title }}</h3><dl class="payment-plan-fields"><div v-for="(field, fieldIndex) in item.fields" :key="fieldIndex"><dt>{{ field.label }}</dt><dd>{{ field.value }}</dd></div></dl></article></div><p v-else>Источник не передал этапы оплаты для этого плана.</p></section>
  <section class="sync-dashboard"><h2>Данные источника</h2><dl class="asset-detail-facts"><div v-if="data.remote_updated_at"><dt>Обновлено в AREALISTING</dt><dd>{{ data.remote_updated_at }}</dd></div><div v-if="data.last_seen_at"><dt>Последний раз получено</dt><dd>{{ data.last_seen_at }}</dd></div><div v-if="data.synced_at"><dt>Сохранено в Undersun</dt><dd>{{ data.synced_at }}</dd></div></dl></section>
</template>
