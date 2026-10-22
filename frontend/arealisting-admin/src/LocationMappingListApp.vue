<script setup lang="ts">
import { ref } from 'vue';

type Mapping = {
  id: number; source_name: string; source_type: string; external_id: string;
  parent_external_id: string; mode: string; target: string; is_confirmed: boolean;
  is_deleted: boolean; synced_at: string; url: string;
};
type ListData = {
  filter_url: string; sync_overview_url: string; vue_preview: boolean; mode: string; confirmed: string;
  deleted: string; query: string; counts: { all: number; pending: number; confirmed: number };
  confirmed_urls: Record<string, string>; modes: { value: string; label: string }[];
  result_count: number; page: { number: number; total: number; previous_url: string; next_url: string };
  mappings: Mapping[];
};
const props = defineProps<{ data: ListData }>();
const mode = ref(props.data.mode);
const deleted = ref(props.data.deleted);
const query = ref(props.data.query);
</script>

<template>
  <section class="workspace-intro"><h2>Локации AREALISTING</h2><p>Сопоставьте названия из источника с районами и локациями Undersun. Подтверждённые связи используются при создании карточек из AREALISTING.</p><p class="muted">Новые локации появляются здесь после обновления списка комплексов. Затем откройте запись и подтвердите сопоставление.</p><a v-if="data.sync_overview_url" :href="data.sync_overview_url">Перейти к обновлению комплексов →</a></section>
  <nav class="price-review-statuses" aria-label="Подтверждение локаций"><a :href="data.confirmed_urls['']" :aria-current="!data.confirmed ? 'page' : undefined">Все <strong>{{ data.counts.all }}</strong></a><a :href="data.confirmed_urls['0']" :aria-current="data.confirmed === '0' ? 'page' : undefined">Ждут проверки <strong>{{ data.counts.pending }}</strong></a><a :href="data.confirmed_urls['1']" :aria-current="data.confirmed === '1' ? 'page' : undefined">Подтверждены <strong>{{ data.counts.confirmed }}</strong></a></nav>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Локации · {{ data.result_count }}</h2><p class="muted">По умолчанию показаны только записи, которые ещё есть в источнике.</p></div></div>
    <form method="get" :action="data.filter_url" class="price-review-filters"><input type="hidden" name="is_confirmed__exact" :value="data.confirmed"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" name="q" type="search" placeholder="Название или ID"></label><label>Режим<select v-model="mode" name="mapping_mode__exact"><option value="">Все режимы</option><option v-for="item in data.modes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label><label>В источнике<select v-model="deleted" name="is_deleted__exact"><option value="0">Актуальные</option><option value="1">Удалённые</option><option value="all">Все</option></select></label><button type="submit">Показать</button></form>
    <div v-if="data.mappings.length" class="work-queue-list"><article v-for="mapping in data.mappings" :key="mapping.id" class="work-queue-item location-mapping-card"><div><div class="price-review-meta"><span class="meta-badge" :data-status="mapping.is_confirmed ? 'ready' : 'pending'">{{ mapping.is_confirmed ? 'Подтверждена' : 'Ждёт проверки' }}</span><span class="meta-badge">{{ mapping.mode }}</span><span v-if="mapping.is_deleted" class="meta-badge">Удалена в источнике</span></div><h3><a :href="mapping.url">{{ mapping.source_name }}</a></h3><p class="muted">{{ mapping.source_type || 'Тип не указан' }} · ID {{ mapping.external_id }}<template v-if="mapping.parent_external_id"> · родитель {{ mapping.parent_external_id }}</template></p><p>Undersun: <strong>{{ mapping.target || 'не выбрано' }}</strong></p><p v-if="mapping.synced_at" class="muted">Обновлено {{ mapping.synced_at }}</p></div><a :href="mapping.url">{{ mapping.is_confirmed ? 'Открыть связь' : 'Проверить связь' }} →</a></article></div>
    <p v-else>Локаций с такими фильтрами нет. Проверьте поиск и фильтры; если запись ещё не получена, обновите список комплексов.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы локаций"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
