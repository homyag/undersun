<script setup lang="ts">
type Project = { id: number; name: string; developer: string; external_id: string; url: string };
type SelectData = { query: string; page: number; pages: number; base_url: string; vue_preview: boolean; rows: Project[] };
const props = defineProps<{ data: SelectData }>();
function pageUrl(page: number) {
  const params = new URLSearchParams();
  if (props.data.query) params.set('q', props.data.query);
  if (page > 1) params.set('page', String(page));
  if (props.data.vue_preview) params.set('vue', '1');
  const query = params.toString();
  return `${props.data.base_url}${query ? `?${query}` : ''}`;
}
</script>

<template>
  <section class="workspace-intro">
    <h2>Выберите комплекс</h2>
    <p>После выбора можно подобрать предложения к карточкам Undersun и проверить изменения перед сохранением.</p>
  </section>
  <form class="matching-toolbar search-toolbar" method="get" :action="data.base_url">
    <input v-if="data.vue_preview" type="hidden" name="vue" value="1">
    <label>Комплекс, застройщик или ID<input type="search" name="q" :value="data.query" placeholder="Введите название или ID"></label>
    <button type="submit">Найти</button>
    <a v-if="data.query" :href="data.base_url + (data.vue_preview ? '?vue=1' : '')">Сбросить</a>
  </form>
  <div v-if="data.rows.length" class="matching-select-grid">
    <article v-for="project in data.rows" :key="project.id" class="matching-select-card">
      <div><h3>{{ project.name }}</h3><p class="muted">{{ project.developer || 'Застройщик не указан' }} · ID {{ project.external_id }}</p></div>
      <a class="primary-action" :href="project.url">Открыть сопоставление →</a>
    </article>
  </div>
  <p v-else class="workspace-intro">Комплексы по запросу не найдены.</p>
  <nav v-if="data.pages > 1" class="pagination-bar" aria-label="Страницы комплексов">
    <a v-if="data.page > 1" class="pagination-action" :href="pageUrl(data.page - 1)">← Назад</a>
    <span v-else class="pagination-action is-disabled" aria-disabled="true">← Назад</span>
    <span class="pagination-current" aria-current="page">Страница {{ data.page }} из {{ data.pages }}</span>
    <a v-if="data.page < data.pages" class="pagination-action" :href="pageUrl(data.page + 1)">Далее →</a>
    <span v-else class="pagination-action is-disabled" aria-disabled="true">Далее →</span>
  </nav>
</template>
