<script setup lang="ts">
import { ref } from 'vue';

type Row = {
  id: number; unit_id: number; unit: string; project: string; project_id: number;
  reason: string; skipped_by: string; created_at: string; is_deleted: boolean;
  is_linked: boolean; can_restore: boolean; unit_url: string;
  detail_url: string; restore_url: string; matching_url: string;
};
type ListData = {
  filter_url: string; vue_preview: boolean; project: string; query: string;
  result_count: number; page: { number: number; total: number; previous_url: string; next_url: string };
  rows: Row[];
};
const props = defineProps<{ data: ListData }>();
const query = ref(props.data.query);
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.skipped-unit-list-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <section class="workspace-intro"><h2>Пропущенные предложения</h2><p>Эти предложения исключены из очереди сопоставления. Проверьте причину и верните нужное предложение в очередь, чтобы снова выбрать для него карточку.</p><p v-if="data.project" class="muted">Комплекс №{{ data.project }} · <a :href="data.filter_url + (data.vue_preview ? '?vue=1' : '')">Показать все комплексы →</a></p></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Пропущено · {{ data.result_count }}</h2><p class="muted">Поиск по номеру предложения, комплексу или причине.</p></div></div><form method="get" :action="data.filter_url" class="price-review-filters"><input v-if="data.project" type="hidden" name="project" :value="data.project"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" type="search" name="q" placeholder="Номер, комплекс или причина"></label><button type="submit">Показать</button></form>
    <div v-if="data.rows.length" class="work-queue-list"><article v-for="row in data.rows" :key="row.id" class="work-queue-item skipped-unit-card"><div><div class="price-review-meta"><span class="meta-badge">Пропущено</span><span v-if="row.is_deleted" class="meta-badge">Удалено в источнике</span><span v-if="row.is_linked" class="meta-badge">Уже связано</span></div><h3><a :href="row.detail_url">Предложение {{ row.unit }}</a></h3><p class="muted">{{ row.project }} · {{ row.created_at }}<template v-if="row.skipped_by"> · {{ row.skipped_by }}</template></p><p>Причина: {{ row.reason || 'не указана' }}</p><div class="asset-list-actions"><a v-if="row.unit_url" :href="row.unit_url">Данные предложения →</a><a v-if="row.matching_url" :href="row.matching_url">Сопоставление комплекса →</a></div></div><form v-if="row.can_restore" method="post" :action="row.restore_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input type="hidden" name="return_project" :value="data.project"><input type="hidden" name="return_q" :value="data.query"><input type="hidden" name="return_page" :value="data.page.number"><button type="submit" class="secondary" :disabled="submitting">Вернуть в очередь</button></form><a v-else :href="row.detail_url">Подробнее →</a></article></div><p v-else>Пропущенных предложений с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы пропущенных предложений"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
