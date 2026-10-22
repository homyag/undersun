<script setup lang="ts">
import { ref } from 'vue';

type Change = {
  id: number; kind: string; property: string; project: string; actor: string;
  created_at: string; summary: string; property_url: string; url: string;
};
type ChangeListData = {
  filter_url: string; vue_preview: boolean; kind: string; card: string; query: string;
  kinds: { value: string; label: string; count: number; url: string }[];
  all_count: number; all_url: string; result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  changes: Change[];
};
const props = defineProps<{ data: ChangeListData }>();
const query = ref(props.data.query);
</script>

<template>
  <section class="workspace-intro"><h2>История изменений карточек</h2><p>Здесь записаны сопоставления, отвязки, изменения характеристик и цены. Откройте запись, чтобы увидеть значения до и после.</p><p v-if="data.card" class="muted">Показана только карточка №{{ data.card }}. <a :href="data.filter_url + (data.vue_preview ? '?vue=1' : '')">Посмотреть все карточки →</a></p></section>
  <nav class="price-review-statuses" aria-label="Тип изменения"><a :href="data.all_url" :aria-current="!data.kind ? 'page' : undefined">Все <strong>{{ data.all_count }}</strong></a><a v-for="item in data.kinds" :key="item.value" :href="item.url" :aria-current="data.kind === item.value ? 'page' : undefined">{{ item.label }} <strong>{{ item.count }}</strong></a></nav>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Записи · {{ data.result_count }}</h2><p class="muted">Поиск работает по названию карточки или комплекса.</p></div></div>
    <form method="get" :action="data.filter_url" class="price-review-filters"><input type="hidden" name="kind" :value="data.kind"><input v-if="data.card" type="hidden" name="card" :value="data.card"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" type="search" name="q" placeholder="Карточка или комплекс"></label><button type="submit">Показать</button></form>
    <div v-if="data.changes.length" class="work-queue-list"><article v-for="change in data.changes" :key="change.id" class="work-queue-item property-change-card"><div><div class="price-review-meta"><span class="meta-badge">{{ change.kind }}</span><span class="muted">{{ change.created_at }}</span></div><h3><a :href="change.url">{{ change.property }}</a></h3><p class="muted">{{ change.project || 'Комплекс не указан' }} · {{ change.actor }}</p><p>{{ change.summary }}</p></div><a :href="change.url">Посмотреть изменения →</a></article></div><p v-else>Изменений с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы изменений"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
