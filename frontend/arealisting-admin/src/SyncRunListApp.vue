<script setup lang="ts">
import { ref } from 'vue';

type Run = {
  id: number; mode: string; status: string; status_label: string;
  started_at: string; finished_at: string; resources: string[];
  error: string; url: string;
};
type RunListData = {
  filter_url: string; vue_preview: boolean; status: string; mode: string; query: string;
  statuses: { value: string; label: string; count: number; url: string }[];
  all_count: number; all_url: string;
  modes: { value: string; label: string }[]; result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  runs: Run[];
};

const props = defineProps<{ data: RunListData }>();
const mode = ref(props.data.mode);
const query = ref(props.data.query);
</script>

<template>
  <section class="workspace-intro"><h2>История обновлений AREALISTING</h2><p>Здесь видно, когда данные загружались, сколько записей изменилось и были ли ошибки. Откройте запуск для подробного итога.</p></section>
  <nav class="price-review-statuses" aria-label="Статус обновления"><a :href="data.all_url" :aria-current="!data.status ? 'page' : undefined">Все <strong>{{ data.all_count }}</strong></a><a v-for="item in data.statuses" :key="item.value" :href="item.url" :aria-current="data.status === item.value ? 'page' : undefined">{{ item.label }} <strong>{{ item.count }}</strong></a></nav>
  <section class="work-queue">
    <div class="dashboard-heading"><div><h2>Запуски · {{ data.result_count }}</h2><p class="muted">Поиск работает по номеру запуска и тексту ошибки.</p></div></div>
    <form method="get" :action="data.filter_url" class="price-review-filters"><input type="hidden" name="status" :value="data.status"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" name="q" type="search" placeholder="Номер или ошибка"></label><label>Режим<select v-model="mode" name="mode"><option value="">Все режимы</option><option v-for="item in data.modes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label><button type="submit">Показать</button></form>
    <div v-if="data.runs.length" class="work-queue-list"><article v-for="run in data.runs" :key="run.id" class="work-queue-item sync-run-card" :class="{ 'has-error': run.status === 'FAILED' }"><div><div class="price-review-meta"><span class="meta-badge" :data-status="run.status.toLowerCase()">{{ run.status_label }}</span><span class="meta-badge">{{ run.mode }}</span></div><h3><a :href="run.url">Обновление #{{ run.id }}</a></h3><p class="muted">Начато {{ run.started_at }}<template v-if="run.finished_at"> · завершено {{ run.finished_at }}</template></p><p>Ресурсы: {{ run.resources.join(', ') || 'не указаны' }}</p><p v-if="run.error" class="dashboard-alert">{{ run.error }}</p></div><a :href="run.url">Посмотреть итог →</a></article></div>
    <p v-else>Запусков с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы истории"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
