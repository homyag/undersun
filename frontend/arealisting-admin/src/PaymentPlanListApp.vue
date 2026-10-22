<script setup lang="ts">
import { ref } from 'vue';

type Plan = {
  id: number; name: string; project: string; description: string;
  item_count: number; is_deleted: boolean; remote_updated_at: string; url: string;
};
type ListData = {
  filter_url: string; vue_preview: boolean; query: string; project: string;
  deleted: string; counts: { all: number; active: number; deleted: number };
  status_urls: Record<string, string>; result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  plans: Plan[];
};
const props = defineProps<{ data: ListData }>();
const query = ref(props.data.query);
</script>

<template>
  <section class="workspace-intro"><h2>Планы оплаты AREALISTING</h2><p>Планы и этапы платежей приходят из источника. Откройте план, чтобы увидеть его описание и каждый этап.</p><p v-if="data.project" class="muted">Комплекс №{{ data.project }} · <a :href="data.filter_url + (data.vue_preview ? '?vue=1' : '')">Все комплексы →</a></p></section>
  <nav class="price-review-statuses" aria-label="Актуальность планов"><a :href="data.status_urls.active" :aria-current="data.deleted === '0' ? 'page' : undefined">Актуальные <strong>{{ data.counts.active }}</strong></a><a :href="data.status_urls.deleted" :aria-current="data.deleted === '1' ? 'page' : undefined">Удалены в источнике <strong>{{ data.counts.deleted }}</strong></a><a :href="data.status_urls.all" :aria-current="data.deleted === 'all' ? 'page' : undefined">Все <strong>{{ data.counts.all }}</strong></a></nav>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Планы · {{ data.result_count }}</h2><p class="muted">Поиск по названию, описанию и комплексу.</p></div></div><form method="get" :action="data.filter_url" class="price-review-filters"><input type="hidden" name="is_deleted__exact" :value="data.deleted"><input v-if="data.project" type="hidden" name="project" :value="data.project"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" type="search" name="q" placeholder="План или комплекс"></label><button type="submit">Показать</button></form>
    <div v-if="data.plans.length" class="work-queue-list"><article v-for="plan in data.plans" :key="plan.id" class="work-queue-item payment-plan-card"><div><div class="price-review-meta"><span class="meta-badge">Этапов: {{ plan.item_count }}</span><span v-if="plan.is_deleted" class="meta-badge">Удалён в источнике</span></div><h3><a :href="plan.url">{{ plan.name }}</a></h3><p class="muted">{{ plan.project }}<template v-if="plan.remote_updated_at"> · обновлён в источнике {{ plan.remote_updated_at }}</template></p><p v-if="plan.description">{{ plan.description }}</p></div><a :href="plan.url">Посмотреть этапы →</a></article></div><p v-else>Планов с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы планов оплаты"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
