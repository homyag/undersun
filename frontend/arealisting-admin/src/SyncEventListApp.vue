<script setup lang="ts">
import { ref } from 'vue';

type EventRow = {
  id: number; kind: string; created_at: string; title: string;
  detail: string; next_step: string; run_id: number; reviewed: boolean; url: string;
};
type ListData = {
  filter_url: string; vue_preview: boolean; state: string; kind: string;
  run: string; query: string; counts: Record<string, number>;
  state_urls: Record<string, string>; kinds: { value: string; label: string }[];
  result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  events: EventRow[];
};
const props = defineProps<{ data: ListData }>();
const query = ref(props.data.query);
const kind = ref(props.data.kind);
const run = ref(props.data.run);
</script>

<template>
  <section class="workspace-intro"><h2>События синхронизации</h2><p>Полный журнал изменений, полученных при обновлении AREALISTING. Откройте событие, чтобы увидеть подробности и связанные записи.</p><p v-if="data.run" class="muted">Показан запуск #{{ data.run }} · <a :href="data.filter_url + (data.vue_preview ? '?vue=1' : '')">Все запуски →</a></p></section>
  <nav class="price-review-statuses" aria-label="Проверка событий"><a v-for="item in [{ value: 'all', label: 'Все' }, { value: 'open', label: 'Не проверены' }, { value: 'checked', label: 'Проверены' }]" :key="item.value" :href="data.state_urls[item.value]" :aria-current="data.state === item.value ? 'page' : undefined">{{ item.label }} <strong>{{ data.counts[item.value] }}</strong></a></nav>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>События · {{ data.result_count }}</h2><p class="muted">Поиск по предложению, комплексу и карточке.</p></div></div>
    <form method="get" :action="data.filter_url" class="price-review-filters"><input type="hidden" name="state" :value="data.state"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" type="search" name="q" placeholder="Предложение или комплекс"></label><label>Вид события<select v-model="kind" name="kind"><option value="">Все виды</option><option v-for="item in data.kinds" :key="item.value" :value="item.value">{{ item.label }}</option></select></label><label>Номер запуска<input v-model="run" type="number" min="1" name="run" placeholder="Все запуски"></label><button type="submit">Показать</button></form>
    <div v-if="data.events.length" class="work-queue-list"><article v-for="event in data.events" :key="event.id" class="work-queue-item sync-event-card"><div><div class="price-review-meta"><span class="meta-badge">{{ event.kind }}</span><span class="meta-badge">{{ event.reviewed ? 'Проверено' : 'Ожидает проверки' }}</span></div><h3><a :href="event.url">{{ event.title }}</a></h3><p class="muted">{{ event.created_at }} · запуск #{{ event.run_id }}</p><p v-if="event.detail">{{ event.detail }}</p><p class="muted">{{ event.next_step }}</p></div><a :href="event.url">Подробности →</a></article></div><p v-else>Событий с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы событий"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
