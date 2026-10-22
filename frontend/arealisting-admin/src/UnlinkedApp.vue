<script setup lang="ts">
import { ref } from 'vue';

type Card = {
  id: number; title: string; property_url: string; photo: string; is_active: boolean;
  type: string; bedrooms: string; area: string; complex: string;
  select_url: string; manual_url: string;
};
type Project = {
  id: number; title: string; type: string; developer: string;
  unit_count: number; available_count: number; sold_count: number;
  matching_url: string; load_url: string;
};
type Page = { number: number; total: number; previous_url: string; next_url: string };
type Selected = {
  id: number; title: string; is_active: boolean; close_url: string; project_query: string;
  project_search_fields: Record<string, string>;
  project_count: number | null; project_page: Page | null; projects: Project[];
};
type UnlinkedData = {
  base_url: string; vue_preview: boolean; state: string; activity: string; query: string;
  pending_count: number; manual_count: number;
  activity_counts: { all: number; active: number; inactive: number };
  result_count: number; pending_url: string; manual_url: string;
  activity_urls: { all: string; active: string; inactive: string }; reset_search_url: string;
  page: Page; cards: Card[]; selected: Selected | null;
  source_fields: Record<string, string | number | null>;
  can_load: boolean; can_match: boolean;
};

const props = defineProps<{ data: UnlinkedData }>();
const search = ref(props.data.query);
const projectSearch = ref(props.data.selected?.project_query || '');
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.unlinked-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <section class="workspace-intro">
    <h2>Карточки Undersun без связи</h2>
    <p>Найдите для карточки комплекс AREALISTING или отметьте, что она ведётся вручную. Неопубликованные карточки тоже включены.</p>
  </section>

  <section class="queue-controls" aria-label="Фильтры очереди">
    <nav class="segmented-control" aria-label="Статус разбора">
      <a :href="data.pending_url" :aria-current="data.state === 'pending' ? 'page' : undefined">Нужно разобрать <strong>{{ data.pending_count }}</strong></a>
      <a :href="data.manual_url" :aria-current="data.state === 'manual' ? 'page' : undefined">Ведём вручную <strong>{{ data.manual_count }}</strong></a>
    </nav>
    <nav class="segmented-control compact" aria-label="Активность карточек">
      <span>Активность:</span>
      <a :href="data.activity_urls.all" :aria-current="data.activity === 'all' ? 'page' : undefined">Все ({{ data.activity_counts.all }})</a>
      <a :href="data.activity_urls.active" :aria-current="data.activity === 'active' ? 'page' : undefined">Активные ({{ data.activity_counts.active }})</a>
      <a :href="data.activity_urls.inactive" :aria-current="data.activity === 'inactive' ? 'page' : undefined">Неактивные ({{ data.activity_counts.inactive }})</a>
    </nav>
  </section>

  <section v-if="data.selected" id="selected-property" class="workspace-intro selected-property-panel">
    <div class="selected-property-heading">
      <div><span class="publication-state" :class="data.selected.is_active ? 'is-active' : 'is-inactive'">{{ data.selected.is_active ? 'Активна на сайте' : 'Неактивна' }}</span>
        <h2>Подбираем комплекс для «{{ data.selected.title }}»</h2>
        <p class="muted">Карточка #{{ data.selected.id }}. Связь появится только после проверки на следующем экране.</p>
      </div><a :href="data.selected.close_url">Закрыть подбор</a>
    </div>
    <form method="get" :action="data.base_url" class="matching-toolbar search-toolbar">
      <input v-for="(value, name) in data.selected.project_search_fields" :key="name" type="hidden" :name="name" :value="value">
      <label>Название комплекса или застройщика<input v-model="projectSearch" type="search" name="project_q" placeholder="Например, Lavisco"></label>
      <button type="submit">Найти комплекс</button>
    </form>
    <template v-if="data.selected.project_page">
      <p class="muted">Найдено комплексов: {{ data.selected.project_count }}</p>
      <div v-if="data.selected.projects.length" class="project-grid project-choice-grid">
        <article v-for="project in data.selected.projects" :key="project.id" class="project-card project-choice-card">
          <div class="card-badges"><span class="meta-badge">{{ project.type }}</span></div>
          <h3>{{ project.title }}</h3><p>{{ project.developer }}</p>
          <template v-if="project.unit_count">
            <dl class="inventory-counters"><div class="is-available"><dt>Доступно</dt><dd>{{ project.available_count }}</dd></div><div class="is-sold"><dt>Продано</dt><dd>{{ project.sold_count }}</dd></div></dl>
            <a v-if="data.can_match" class="primary-action" :href="project.matching_url">Подобрать предложения →</a>
            <p v-else class="muted">Для сопоставления нужны дополнительные права.</p>
          </template>
          <template v-else-if="data.can_load">
            <p class="muted">Предложения этого комплекса ещё не загружены.</p>
            <form method="post" :action="project.load_url" @submit="submitting = true">
              <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken">
              <input v-for="(value, name) in data.source_fields" :key="name" type="hidden" :name="name" :value="value">
              <button type="submit" :disabled="submitting">{{ submitting ? 'Получаем предложения…' : 'Загрузить предложения' }}</button>
            </form>
          </template>
          <p v-else class="muted">Для загрузки предложений нужны дополнительные права.</p>
        </article>
      </div>
      <div v-else class="empty-state"><h3>Комплекс не найден</h3><p>Попробуйте часть названия или застройщика. Если комплекса нет в источнике, карточку можно вести вручную.</p></div>
      <nav v-if="data.selected.project_page.total > 1" class="pagination-bar" aria-label="Страницы комплексов">
        <a v-if="data.selected.project_page.previous_url" class="pagination-action" :href="data.selected.project_page.previous_url">← Назад</a>
        <span v-else class="pagination-action is-disabled" aria-disabled="true">← Назад</span>
        <span class="pagination-current" aria-current="page">Страница {{ data.selected.project_page.number }} из {{ data.selected.project_page.total }}</span>
        <a v-if="data.selected.project_page.next_url" class="pagination-action" :href="data.selected.project_page.next_url">Далее →</a>
        <span v-else class="pagination-action is-disabled" aria-disabled="true">Далее →</span>
      </nav>
    </template>
    <p v-else class="muted">Введите название комплекса или застройщика и нажмите «Найти комплекс».</p>
  </section>

  <form method="get" :action="data.base_url" class="matching-toolbar search-toolbar">
    <input type="hidden" name="state" :value="data.state"><input type="hidden" name="activity" :value="data.activity"><input v-if="data.vue_preview" type="hidden" name="vue" value="1">
    <label>Поиск по карточкам<input v-model="search" type="search" name="q" placeholder="Название, комплекс или ID"></label>
    <button type="submit">Найти</button><a v-if="data.query" :href="data.reset_search_url">Сбросить поиск</a>
    <span class="result-count">Найдено: {{ data.result_count }}</span>
  </form>
  <nav v-if="data.page.total > 1" class="pagination-bar" aria-label="Страницы карточек">
    <a v-if="data.page.previous_url" class="pagination-action" :href="data.page.previous_url">← Назад</a>
    <span v-else class="pagination-action is-disabled" aria-disabled="true">← Назад</span>
    <span class="pagination-current" aria-current="page">Страница {{ data.page.number }} из {{ data.page.total }}</span>
    <a v-if="data.page.next_url" class="pagination-action" :href="data.page.next_url">Далее →</a>
    <span v-else class="pagination-action is-disabled" aria-disabled="true">Далее →</span>
  </nav>

  <div v-if="data.cards.length" class="project-grid property-queue-grid">
    <article v-for="card in data.cards" :key="card.id" class="project-card property-queue-card" :class="{ 'is-selected': data.selected?.id === card.id }">
      <div class="property-card-layout">
        <img v-if="card.photo" class="property-card-photo" :src="card.photo" alt="" loading="lazy">
        <div v-else class="property-card-photo placeholder" aria-hidden="true">Нет фото</div>
        <div class="property-card-copy"><div class="card-badges"><span class="publication-state" :class="card.is_active ? 'is-active' : 'is-inactive'">{{ card.is_active ? 'Активна' : 'Неактивна' }}</span><span class="meta-badge">#{{ card.id }}</span></div>
          <h3><a :href="card.property_url" target="_blank" rel="noopener">{{ card.title }}</a></h3>
          <p class="muted">{{ card.type }}<template v-if="card.bedrooms"> · {{ card.bedrooms }} сп.</template><template v-if="card.area"> · {{ card.area }} м²</template></p>
          <p>{{ card.complex }}</p>
        </div>
      </div>
      <div class="card-actions"><a class="primary-action" :href="card.select_url">Найти комплекс</a>
        <form method="post" :action="card.manual_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input type="hidden" name="activity" :value="data.activity"><input type="hidden" name="q" :value="data.query"><input type="hidden" name="page" :value="data.page.number"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input type="hidden" name="action" :value="data.state === 'manual' ? 'pending' : 'manual'"><button class="secondary" type="submit" :disabled="submitting">{{ submitting ? 'Сохраняем…' : (data.state === 'manual' ? 'Вернуть в подбор' : 'Ведём вручную') }}</button></form>
      </div>
    </article>
  </div>
  <div v-else class="empty-state"><h3>{{ data.query ? 'Карточки не найдены' : data.state === 'manual' ? 'Ручная очередь пуста' : 'Все карточки разобраны' }}</h3><p>{{ data.query ? 'Попробуйте другой запрос или сбросьте поиск.' : data.state === 'manual' ? 'Здесь появятся карточки, которые вы решите вести без AREALISTING.' : 'Все карточки связаны с AREALISTING либо отмечены для ручного ведения.' }}</p></div>
</template>
