<script setup lang="ts">
import { ref } from 'vue';

type Group = { title: string; property: string; url: string; preview_url: string };
type DetailData = {
  id: number; title: string; type_label: string; project: string; unit: string;
  source_key: string; source_url: string; local_url: string; is_image: boolean;
  position: number; is_active: boolean; state: string; error: string;
  downloaded_at: string; updated_at: string; back_url: string; retry_url: string;
  can_retry: boolean; can_view_groups: boolean; groups_url: string;
  group_count: number; groups: Group[];
};

const props = defineProps<{ data: DetailData }>();
const state = ref(props.data.state);
const error = ref(props.data.error);
const canRetry = ref(props.data.can_retry);
const running = ref(false);
const result = ref('');
const csrfToken = document.querySelector<HTMLInputElement>('.asset-detail-page > input[name="csrfmiddlewaretoken"]')?.value || '';
async function retry() {
  if (running.value || !canRetry.value) return;
  running.value = true;
  result.value = '';
  try {
    const body = new URLSearchParams({ format: 'json', csrfmiddlewaretoken: csrfToken });
    const response = await fetch(props.data.retry_url, {
      method: 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' }, body,
    });
    if (!response.ok) throw new Error(`Сервер вернул ${response.status}.`);
    const data = await response.json() as { downloaded: number; failed: number; skipped: number; state: string; error: string };
    state.value = data.state;
    error.value = data.error;
    if (data.downloaded) {
      canRetry.value = false;
      result.value = 'Изображение скачано. Чтобы добавить его в карточку, запустите импорт в подходящей группе.';
    } else if (data.failed) result.value = `Загрузка не удалась: ${data.error || 'причина не указана'}`;
    else result.value = 'Материал пропущен: файл уже загружен или не подходит для скачивания.';
  } catch (cause) {
    result.value = cause instanceof Error ? cause.message : 'Не удалось выполнить запрос.';
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <a :href="data.back_url">← К списку материалов</a>
  <section class="workspace-intro">
    <div class="price-review-meta"><span class="meta-badge" :data-status="state">{{ state === 'error' ? 'Ошибка' : state === 'downloaded' ? 'Загружено' : 'Только URL' }}</span><span class="meta-badge">{{ data.type_label }}</span><span v-if="!data.is_active" class="meta-badge">Неактивен</span></div>
    <h2>{{ data.title }}</h2>
    <p class="muted">{{ data.project || 'Комплекс не указан' }}<template v-if="data.unit"> · {{ data.unit }}</template> · позиция {{ data.position }}</p>
    <p v-if="error" class="dashboard-alert"><strong>Причина ошибки:</strong> {{ error }}</p>
    <p v-else-if="state === 'downloaded'">Изображение скачано. Если его нет в карточке, запустите импорт фотографий для связанной группы.</p>
    <p v-else>Есть только ссылка на источник. Фото скачиваются после подтверждения импорта группы; документы остаются ссылками.</p>
    <div class="asset-list-actions"><button v-if="canRetry" type="button" :disabled="running" @click="retry">{{ running ? 'Скачиваем…' : 'Повторить скачивание изображения' }}</button><a :href="data.source_url" target="_blank" rel="noopener noreferrer">Открыть источник ↗</a><a v-if="data.local_url" :href="data.local_url" target="_blank" rel="noopener noreferrer">Открыть локальный файл ↗</a></div>
    <p v-if="result" role="status" aria-live="polite">{{ result }}</p>
  </section>
  <section class="sync-dashboard asset-detail-layout">
    <div v-if="data.is_image && (data.local_url || data.source_url)" class="asset-detail-preview"><a :href="data.source_url" target="_blank" rel="noopener noreferrer"><img :src="data.local_url || data.source_url" alt="Предпросмотр материала" loading="lazy"></a></div>
    <div><h2>Данные материала</h2><dl class="asset-detail-facts"><div><dt>Ключ источника</dt><dd>{{ data.source_key }}</dd></div><div><dt>Обновлено</dt><dd>{{ data.updated_at }}</dd></div><div v-if="data.downloaded_at"><dt>Загружено</dt><dd>{{ data.downloaded_at }}</dd></div></dl></div>
  </section>
  <section v-if="data.can_view_groups" class="work-queue">
    <div class="dashboard-heading"><div><h2>Подходящие группы · {{ data.group_count }}</h2><p class="muted">Скачанный файл сам по себе в карточке не появляется. Выберите группу и проверьте импорт.</p></div></div>
    <div v-if="data.groups.length" class="work-queue-list"><article v-for="group in data.groups" :key="group.url" class="work-queue-item"><div><h3>{{ group.title }}</h3><p class="muted">{{ group.property || 'Карточка ещё не связана' }}</p></div><div class="review-queue-actions"><a :href="group.url">Открыть группу →</a><a v-if="group.preview_url" :href="group.preview_url">Проверить импорт фото →</a></div></article></div>
    <p v-else>Связанная группа для этого материала пока не найдена.</p>
    <p v-if="data.group_count > data.groups.length"><a :href="data.groups_url">Все связи с карточками →</a></p>
  </section>
</template>
