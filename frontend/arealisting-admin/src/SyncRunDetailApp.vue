<script setup lang="ts">
type Resource = { name: string; seen: number; created: number; updated: number; deleted: number; skipped: number; errors: number };
type RunData = {
  id: number; mode: string; status: string; status_label: string;
  started_at: string; finished_at: string; since: string;
  resources: Resource[]; project_ids: string[];
  property_update_count: number; price_update_count: number;
  error: string; back_url: string; review_url: string;
};
defineProps<{ data: RunData }>();
</script>

<template>
  <a :href="data.back_url">← К истории обновлений</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge" :data-status="data.status.toLowerCase()">{{ data.status_label }}</span><span class="meta-badge">{{ data.mode }}</span></div><h2>Обновление #{{ data.id }}</h2><p>Начато {{ data.started_at }}<template v-if="data.finished_at"> · завершено {{ data.finished_at }}</template></p><p v-if="data.since" class="muted">Изменения в источнике с {{ data.since }}</p><p v-if="data.project_ids.length" class="muted">Выбранные комплексы: {{ data.project_ids.join(', ') }}</p><p v-if="data.error" class="dashboard-alert" role="alert"><strong>Ошибка:</strong> {{ data.error }}</p></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Что произошло</h2><p class="muted">Числа отражают ответ источника и обработку данных в этом запуске.</p></div></div>
    <div v-if="data.resources.length" class="sync-run-resources"><article v-for="resource in data.resources" :key="resource.name" class="work-queue-item"><h3>{{ resource.name }}</h3><dl class="sync-run-stats"><div><dt>Получено</dt><dd>{{ resource.seen }}</dd></div><div><dt>Добавлено</dt><dd>{{ resource.created }}</dd></div><div><dt>Обновлено</dt><dd>{{ resource.updated }}</dd></div><div><dt>Удалено</dt><dd>{{ resource.deleted }}</dd></div><div><dt>Пропущено</dt><dd>{{ resource.skipped }}</dd></div><div :class="{ 'sync-run-error-count': resource.errors }"><dt>Ошибок</dt><dd>{{ resource.errors }}</dd></div></dl></article></div>
    <p v-else>Подробный итог по ресурсам отсутствует.</p>
  </section>
  <section class="sync-dashboard"><h2>Карточки Undersun</h2><p>Обновлений данных карточек: <strong>{{ data.property_update_count }}</strong> · изменений цены: <strong>{{ data.price_update_count }}</strong>.</p><a v-if="data.review_url" :href="data.review_url">Открыть очередь изменений →</a></section>
</template>
