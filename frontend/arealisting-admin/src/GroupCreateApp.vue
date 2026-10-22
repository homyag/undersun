<script setup lang="ts">
import { ref } from 'vue';

type Choice = { id: number; label: string };
type CreateData = {
  action_url: string; lookup_url: string; back_url: string; vue_preview: boolean;
  can_choose_property: boolean;
  project: Choice | null; property: Choice | null;
  grouping_mode: string; name: string; is_active: boolean;
  modes: { value: string; label: string }[]; errors: Record<string, string[]>;
};
const props = defineProps<{ data: CreateData }>();
const project = ref<Choice | null>(props.data.project);
const property = ref<Choice | null>(props.data.property);
const projectQuery = ref('');
const propertyQuery = ref('');
const projectResults = ref<Choice[]>([]);
const propertyResults = ref<Choice[]>([]);
const projectSearching = ref(false);
const propertySearching = ref(false);
const projectSearchError = ref('');
const propertySearchError = ref('');
const mode = ref(props.data.grouping_mode);
const name = ref(props.data.name);
const active = ref(props.data.is_active);
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.group-create-page > input[name="csrfmiddlewaretoken"]')?.value || '';

async function search(kind: 'projects' | 'properties') {
  const isProject = kind === 'projects';
  const query = isProject ? projectQuery.value : propertyQuery.value;
  if (isProject) { projectSearching.value = true; projectSearchError.value = ''; }
  else { propertySearching.value = true; propertySearchError.value = ''; }
  try {
    const url = new URL(props.data.lookup_url, window.location.href);
    url.searchParams.set('lookup', kind);
    url.searchParams.set('q', query.trim());
    const response = await fetch(url.toString(), { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Поиск недоступен. Повторите попытку.');
    const body = await response.json() as { results: Choice[] };
    if (isProject) projectResults.value = body.results;
    else propertyResults.value = body.results;
  } catch {
    if (isProject) projectSearchError.value = 'Не удалось найти комплексы. Повторите попытку.';
    else propertySearchError.value = 'Не удалось найти карточки. Повторите попытку.';
  } finally {
    if (isProject) projectSearching.value = false;
    else propertySearching.value = false;
  }
}
</script>

<template>
  <a :href="data.back_url">← К списку связей</a>
  <section class="workspace-intro"><h2>Создать группу AREALISTING</h2><p>Выберите комплекс и способ группировки. Карточку можно привязать сейчас или позже на экране сопоставления.</p></section>
  <section class="work-queue">
    <form method="post" :action="data.action_url" class="group-create-form" @submit="submitting = true">
      <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1">
      <div v-if="data.errors.__all__?.length" class="dashboard-alert" role="alert">{{ data.errors.__all__.join(' ') }}</div>
      <fieldset class="group-create-picker"><legend>1. Комплекс AREALISTING</legend>
        <p v-if="project" class="group-create-selected">Выбран: <strong>{{ project.label }}</strong> <button type="button" class="secondary" @click="project = null">Изменить</button></p>
        <div class="group-create-search"><label for="group-project-search">Поиск комплекса</label><div><input id="group-project-search" v-model="projectQuery" type="search" placeholder="Название или ID в источнике" @keydown.enter.prevent="search('projects')"><button type="button" class="secondary" :disabled="projectSearching" @click="search('projects')">{{ projectSearching ? 'Ищем…' : 'Найти' }}</button></div></div>
        <p v-if="projectSearchError" class="group-field-error" role="alert">{{ projectSearchError }}</p>
        <div v-if="projectResults.length" class="group-create-results"><button v-for="item in projectResults" :key="item.id" type="button" class="secondary" :aria-pressed="project?.id === item.id" @click="project = item">{{ item.label }} · №{{ item.id }}</button></div>
        <p v-else-if="!project && !projectSearching" class="muted">Введите название и нажмите «Найти». Пустой поиск покажет последние комплексы.</p>
        <input type="hidden" name="project" :value="project?.id || ''"><p v-if="data.errors.project?.length" class="group-field-error" role="alert">{{ data.errors.project.join(' ') }}</p>
      </fieldset>
      <fieldset v-if="data.can_choose_property" class="group-create-picker"><legend>2. Карточка Undersun · необязательно</legend>
        <p v-if="property" class="group-create-selected">Выбрана: <strong>{{ property.label }}</strong> <button type="button" class="secondary" @click="property = null">Убрать</button></p>
        <div class="group-create-search"><label for="group-property-search">Поиск свободной карточки</label><div><input id="group-property-search" v-model="propertyQuery" type="search" placeholder="Название или URL карточки" @keydown.enter.prevent="search('properties')"><button type="button" class="secondary" :disabled="propertySearching" @click="search('properties')">{{ propertySearching ? 'Ищем…' : 'Найти' }}</button></div></div>
        <p v-if="propertySearchError" class="group-field-error" role="alert">{{ propertySearchError }}</p>
        <div v-if="propertyResults.length" class="group-create-results"><button v-for="item in propertyResults" :key="item.id" type="button" class="secondary" :aria-pressed="property?.id === item.id" @click="property = item">{{ item.label }} · №{{ item.id }}</button></div>
        <p v-else class="muted">Показываются карточки, ещё не связанные с AREALISTING.</p>
        <input type="hidden" name="property" :value="property?.id || ''"><p v-if="data.errors.property?.length" class="group-field-error" role="alert">{{ data.errors.property.join(' ') }}</p>
      </fieldset>
      <p v-else class="muted">Карточку сможет привязать сотрудник с доступом к объектам Undersun.</p>
      <div class="group-create-fields"><label>Способ группировки<select v-model="mode" name="grouping_mode"><option v-for="item in data.modes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label><p v-if="data.errors.grouping_mode?.length" class="group-field-error" role="alert">{{ data.errors.grouping_mode.join(' ') }}</p>
        <label>Название группы<input v-model="name" name="name" type="text" maxlength="255" placeholder="Например, корпус A"></label><p v-if="data.errors.name?.length" class="group-field-error" role="alert">{{ data.errors.name.join(' ') }}</p>
        <label class="group-check"><input v-model="active" name="is_active" type="checkbox"> Активная группа</label>
      </div>
      <p class="muted">Предложения и фото добавляются после создания группы на экране сопоставления.</p>
      <button type="submit" :disabled="submitting || !project">{{ submitting ? 'Создаём…' : 'Создать группу' }}</button>
    </form>
  </section>
</template>
