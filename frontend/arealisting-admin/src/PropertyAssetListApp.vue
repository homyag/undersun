<script setup lang="ts">
import { ref } from 'vue';

type Link = {
  id: number; role: string; group: string; property: string; project: string;
  asset_type: string; source_url: string; preview_url: string; has_image: boolean;
  is_main: boolean; updated_at: string; url: string;
};
type ListData = {
  filter_url: string; vue_preview: boolean; role: string; image_state: string;
  project: string; query: string; roles: { value: string; label: string }[];
  counts: Record<string, number>; state_urls: Record<string, string>;
  result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  links: Link[];
};
const props = defineProps<{ data: ListData }>();
const query = ref(props.data.query);
const role = ref(props.data.role);
const project = ref(props.data.project);
</script>

<template>
  <section class="workspace-intro"><h2>Фото в карточках</h2><p>Здесь видно, какие материалы AREALISTING связаны с изображениями Undersun. Состав фото меняется через связь с карточкой и импорт.</p></section>
  <nav class="price-review-statuses" aria-label="Состояние фото в карточках"><a v-for="item in [{ value: 'all', label: 'Все' }, { value: 'linked', label: 'Фото создано' }, { value: 'missing', label: 'Фото отсутствует' }]" :key="item.value" :href="data.state_urls[item.value]" :aria-current="data.image_state === item.value ? 'page' : undefined">{{ item.label }} <strong>{{ data.counts[item.value] }}</strong></a></nav>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Связи · {{ data.result_count }}</h2><p class="muted">Поиск по карточке, комплексу, группе или исходному материалу.</p></div></div><form method="get" :action="data.filter_url" class="price-review-filters"><input type="hidden" name="image_state" :value="data.image_state"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" type="search" name="q" placeholder="Карточка, комплекс или материал"></label><label>Назначение<select v-model="role" name="role"><option value="">Все</option><option v-for="item in data.roles" :key="item.value" :value="item.value">{{ item.label }}</option></select></label><label>Комплекс №<input v-model="project" type="number" min="1" name="project" placeholder="Все"></label><button type="submit">Показать</button></form>
    <div v-if="data.links.length" class="asset-list-grid"><article v-for="link in data.links" :key="link.id" class="project-card asset-list-card"><div class="asset-list-media"><a v-if="link.preview_url" :href="link.preview_url" target="_blank" rel="noopener noreferrer" :aria-label="`Открыть фото для ${link.property || link.group} в полном размере`"><img :src="link.preview_url" alt="" loading="lazy"></a><div v-else class="asset-list-placeholder">Фото отсутствует</div></div><div class="asset-list-copy"><div class="price-review-meta"><span class="meta-badge">{{ link.role }}</span><span class="meta-badge">{{ link.has_image ? 'Фото создано' : 'Фото отсутствует' }}</span><span v-if="link.is_main" class="meta-badge">Главное фото</span></div><h3><a :href="link.url">{{ link.property || link.group }}</a></h3><p class="muted">{{ link.project }} · {{ link.asset_type }}</p><p class="muted">Обновлено {{ link.updated_at }}</p><a :href="link.url">Посмотреть связь →</a></div></article></div><p v-else>Связей с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы фото в карточках"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
