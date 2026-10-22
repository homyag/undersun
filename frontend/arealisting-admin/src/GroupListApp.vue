<script setup lang="ts">
import { ref } from 'vue';

type Issue = { reason: string; next_step: string; intentional: boolean; action: { label: string; url: string } | null };
type Group = {
  id: number; title: string; project: string; grouping: string; origin: string;
  property: string; property_url: string; available_units: number; price: string;
  currency: string; is_ready: boolean; is_active: boolean; updated_at: string;
  issues: Issue[]; issue_count: number; detail_url: string; readiness_url: string;
  preview_url: string; matching_url: string;
};
type GroupData = {
  base_url: string; overview_url: string; action_url: string; vue_preview: boolean;
  origin: string; mode: string; ready: string; activity: string;
  currency: string; attention: string; query: string; project: string;
  counts: { all: number; issues: number; unlinked: number; ready: number };
  attention_urls: Record<string, string>;
  origins: { value: string; label: string }[]; modes: { value: string; label: string }[];
  currencies: string[]; result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  can_change: boolean; add_url: string; groups: Group[];
};

const props = defineProps<{ data: GroupData }>();
const selected = ref<number[]>([]);
const query = ref(props.data.query);
const project = ref(props.data.project);
const origin = ref(props.data.origin);
const mode = ref(props.data.mode);
const ready = ref(props.data.ready);
const activity = ref(props.data.activity);
const currency = ref(props.data.currency);
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.group-list-page > input[name="csrfmiddlewaretoken"]')?.value || '';
function toggle(id: number) {
  if (selected.value.includes(id)) selected.value = selected.value.filter(value => value !== id);
  else if (selected.value.length < 10) selected.value = [...selected.value, id];
}
function toggleAll() {
  selected.value = props.data.groups.every(group => selected.value.includes(group.id))
    ? [] : props.data.groups.slice(0, 10).map(group => group.id);
}
</script>

<template>
  <section class="workspace-intro">
    <h2>Связи AREALISTING с карточками</h2>
    <p>Здесь видно, какой комплекс и какие предложения связаны с карточкой, какие данные требуют проверки и где настроить импорт фотографий.</p><p v-if="data.project" class="muted">Комплекс №{{ data.project }}<template v-if="data.overview_url"> · <a :href="data.overview_url + '#project-search'">Все комплексы →</a></template></p>
  </section>

  <nav class="price-review-statuses" aria-label="Состояние групп">
    <a :href="data.attention_urls['']" :aria-current="data.attention === '' ? 'page' : undefined">Все <strong>{{ data.counts.all }}</strong></a>
    <a :href="data.attention_urls.issues" :aria-current="data.attention === 'issues' ? 'page' : undefined">С замечаниями <strong>{{ data.counts.issues }}</strong></a>
    <a :href="data.attention_urls.unlinked" :aria-current="data.attention === 'unlinked' ? 'page' : undefined">Без карточки <strong>{{ data.counts.unlinked }}</strong></a>
    <span class="group-ready-count">Готовы к публикации: {{ data.counts.ready }}</span>
  </nav>

  <section class="work-queue">
    <div class="dashboard-heading"><div><h2>Группы · {{ data.result_count }}</h2><p class="muted">Фильтры и поиск применяются ко всем связям.</p></div><a v-if="data.add_url" :href="data.add_url">Создать группу →</a></div>
    <form method="get" :action="data.base_url" class="group-list-filters">
      <input type="hidden" name="attention" :value="data.attention"><input v-if="data.vue_preview" type="hidden" name="vue" value="1">
      <label>Поиск<input v-model="query" type="search" name="q" placeholder="Группа или комплекс"></label>
      <label>Комплекс №<input v-model="project" type="number" min="1" name="project" placeholder="Все"></label>
      <label>Происхождение<select v-model="origin" name="catalog_origin__exact"><option value="">Все</option><option v-for="item in data.origins" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <label>Группировка<select v-model="mode" name="grouping_mode__exact"><option value="">Все</option><option v-for="item in data.modes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <label>Готовность<select v-model="ready" name="is_ready_for_publication__exact"><option value="">Все</option><option value="1">Готовы</option><option value="0">Не готовы</option></select></label>
      <label>Активность<select v-model="activity" name="is_active__exact"><option value="">Все</option><option value="1">Активные</option><option value="0">Неактивные</option></select></label>
      <label>Валюта<select v-model="currency" name="currency__exact"><option value="">Все</option><option v-for="value in data.currencies" :key="value" :value="value">{{ value }}</option></select></label>
      <button type="submit">Показать</button>
    </form>
    <div v-if="data.can_change && data.groups.length" class="group-bulk-bar">
      <button type="button" class="secondary" :disabled="submitting" @click="toggleAll">Выбрать до 10 на странице</button><span>Выбрано: {{ selected.length }} из 10</span>
      <form method="post" :action="data.action_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input type="hidden" name="action" value="import_media"><input v-for="id in selected" :key="id" type="hidden" name="_selected_action" :value="id"><button type="submit" :disabled="submitting || !selected.length">Проверить фото выбранных</button></form>
      <form method="post" :action="data.action_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input type="hidden" name="action" value="recalculate_groups"><input v-for="id in selected" :key="id" type="hidden" name="_selected_action" :value="id"><button type="submit" class="secondary" :disabled="submitting || !selected.length">Пересчитать выбранные</button></form>
    </div>
    <div v-if="data.groups.length" class="work-queue-list">
      <article v-for="group in data.groups" :key="group.id" class="work-queue-item group-list-card" :class="{ 'has-issues': group.issue_count }">
        <div class="group-list-card-top"><div><div class="price-review-meta"><span class="meta-badge">{{ group.grouping }}</span><span class="meta-badge">{{ group.origin }}</span><span class="meta-badge" :data-status="group.is_ready ? 'ready' : 'pending'">{{ group.is_ready ? 'Готова к публикации' : 'Не готова' }}</span><span v-if="!group.is_active" class="meta-badge">Неактивна</span></div><h3><a :href="group.detail_url">{{ group.title }}</a></h3><p class="muted">{{ group.project }} · Обновлено {{ group.updated_at }}</p></div>
          <label v-if="data.can_change" class="asset-select"><input type="checkbox" :checked="selected.includes(group.id)" :disabled="submitting || (!selected.includes(group.id) && selected.length >= 10)" @change="toggle(group.id)">Выбрать</label>
        </div>
        <p>Карточка: <a v-if="group.property_url" :href="group.property_url">{{ group.property }}</a><span v-else>{{ group.property || 'пока не связана' }}</span></p>
        <p class="muted">Доступных предложений: {{ group.available_units }} · Цена: {{ group.price }}</p>
        <div v-if="group.issues.length" class="group-list-issues"><div v-for="(issue, index) in group.issues" :key="index" class="review-issue"><strong>{{ issue.reason }}</strong><p>{{ issue.next_step }}</p><small v-if="issue.intentional">Оставлено намеренно</small><a v-if="issue.action" :href="issue.action.url">{{ issue.action.label }} →</a></div><p v-if="group.issue_count > group.issues.length" class="muted">Ещё замечаний: {{ group.issue_count - group.issues.length }}. Откройте группу для полного списка.</p></div>
        <div class="asset-list-actions"><a :href="group.detail_url">Открыть группу →</a><a v-if="group.readiness_url" :href="group.readiness_url">Проверить готовность →</a><a v-if="group.preview_url" :href="group.preview_url">Проверить фото →</a><a v-if="group.matching_url" :href="group.matching_url">Изменить предложения →</a></div>
      </article>
    </div>
    <p v-else>Групп с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы групп"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
