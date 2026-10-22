<script setup lang="ts">
import { ref } from 'vue';

type Unit = {
  id: number; number: string; project: string; status: string; availability_status: string;
  price: string; currency: string; area: string; group: string; property: string;
  sync_enabled: boolean; is_deleted: boolean; is_skipped: boolean; skipped_url: string; url: string;
};
type UnitListData = {
  filter_url: string; vue_preview: boolean; status: string; linked: string;
  enabled: string; deleted: string; project: string; query: string;
  counts: { all: number; available: number; sold: number; unlinked: number };
  status_urls: Record<string, string>; result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  units: Unit[];
};
const props = defineProps<{ data: UnitListData }>();
const query = ref(props.data.query);
const enabled = ref(props.data.enabled);
const deleted = ref(props.data.deleted);
</script>

<template>
  <section class="workspace-intro"><h2>Предложения AREALISTING</h2><p>Проверьте доступность, цену и связь предложения с карточкой. Данные источника обновляются автоматически; здесь можно настроить группу и флаг синхронизации.</p><p v-if="data.project" class="muted">Комплекс №{{ data.project }} · <a :href="data.filter_url + (data.vue_preview ? '?vue=1' : '')">Показать все комплексы →</a></p></section>
  <nav class="price-review-statuses" aria-label="Статус предложений"><a :href="data.status_urls.all" :aria-current="!data.status && !data.linked ? 'page' : undefined">Все <strong>{{ data.counts.all }}</strong></a><a :href="data.status_urls.available" :aria-current="data.status === 'AVAILABLE' && !data.linked ? 'page' : undefined">Доступны <strong>{{ data.counts.available }}</strong></a><a :href="data.status_urls.sold" :aria-current="data.status === 'SOLD' && !data.linked ? 'page' : undefined">Проданы <strong>{{ data.counts.sold }}</strong></a><a :href="data.status_urls.unlinked" :aria-current="data.linked === '0' ? 'page' : undefined">Без группы <strong>{{ data.counts.unlinked }}</strong></a></nav>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Предложения · {{ data.result_count }}</h2><p class="muted">Поиск по номеру, ID источника и комплексу.</p></div></div>
    <form method="get" :action="data.filter_url" class="price-review-filters"><input type="hidden" name="availability_status__exact" :value="data.status"><input type="hidden" name="linked" :value="data.linked"><input v-if="data.project" type="hidden" name="project" :value="data.project"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><label>Поиск<input v-model="query" name="q" type="search" placeholder="Номер или комплекс"></label><label>Синхронизация<select v-model="enabled" name="sync_enabled__exact"><option value="">Все</option><option value="1">Включена</option><option value="0">Отключена</option></select></label><label>В источнике<select v-model="deleted" name="is_deleted__exact"><option value="0">Актуальные</option><option value="1">Удалённые</option><option value="all">Все</option></select></label><button type="submit">Показать</button></form>
    <div v-if="data.units.length" class="work-queue-list"><article v-for="unit in data.units" :key="unit.id" class="work-queue-item unit-list-card"><div><div class="price-review-meta"><span class="meta-badge" :data-status="unit.availability_status === 'AVAILABLE' ? 'ready' : 'pending'">{{ unit.status }}</span><span v-if="unit.is_skipped" class="meta-badge">Пропущено вручную</span><span v-if="!unit.sync_enabled" class="meta-badge">Синхронизация выключена</span><span v-if="unit.is_deleted" class="meta-badge">Удалено в источнике</span></div><h3><a :href="unit.url">Предложение {{ unit.number }}</a></h3><p class="muted">{{ unit.project }} · {{ unit.area ? `${unit.area} м²` : 'Площадь не указана' }} · {{ unit.price ? `${unit.price} ${unit.currency}` : 'Цена не указана' }}</p><p>Группа: {{ unit.group || 'не выбрана' }}<template v-if="unit.property"> · Карточка: {{ unit.property }}</template></p><a v-if="unit.skipped_url" :href="unit.skipped_url">Посмотреть причину пропуска →</a></div><a :href="unit.url">Открыть предложение →</a></article></div><p v-else>Предложений с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы предложений"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
