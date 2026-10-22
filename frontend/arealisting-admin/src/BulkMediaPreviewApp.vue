<script setup lang="ts">
import { computed } from 'vue';

type Group = {
  id: number; name: string; property_name: string; property_url: string; preview_url: string;
  available_count: number; selected_count: number;
  additions: number; updates: number; removals: number; missing_removals: number;
  manual_count: number; can_import: boolean; fingerprint: string;
  sample_images: { url: string; title: string }[];
};
type BulkData = { groups: Group[]; action_url: string; back_url: string; vue_preview: boolean };

const { data } = defineProps<{ data: BulkData }>();
const csrfToken = document.querySelector<HTMLInputElement>('.bulk-media-page > input[name="csrfmiddlewaretoken"]')?.value || '';
const importable = computed(() => data.groups.filter(group => group.can_import).length);
const additions = computed(() => data.groups.reduce((total, group) => total + group.additions, 0));
const updates = computed(() => data.groups.reduce((total, group) => total + group.updates, 0));
const removals = computed(() => data.groups.reduce((total, group) => total + group.removals, 0));
</script>

<template>
  <a :href="data.back_url">← К списку групп</a>
  <section class="workspace-intro">
    <h2>Проверьте массовый импорт фото</h2>
    <p>AREALISTING обновит выбранные фото и удалит ранее импортированные фото, отсутствующие в источнике. Ручные фото и защищённые разделы останутся в карточках.</p>
    <p><strong>Для исключения отдельных фото откройте группу и измените выбор там.</strong> Вернувшись к массовому импорту, заново выберите группы: состав фото проверяется ещё раз перед запуском.</p>
  </section>
  <div class="bulk-media-summary" aria-label="Итог по группам">
    <div><strong>{{ data.groups.length }}</strong><span>Групп выбрано</span></div>
    <div><strong>{{ importable }}</strong><span>Готовы к импорту</span></div>
    <div><strong>{{ additions }}</strong><span>Добавится</span></div>
    <div><strong>{{ updates }}</strong><span>Обновится</span></div>
    <div><strong>{{ removals }}</strong><span>Удалится</span></div>
  </div>
  <section v-for="group in data.groups" :key="group.id" class="sync-dashboard bulk-media-group">
    <div class="dashboard-heading"><div><h3>{{ group.name }}</h3><p class="muted">Карточка: <a v-if="group.property_url" :href="group.property_url">{{ group.property_name }}</a><span v-else>не связана</span></p></div>
      <span class="bulk-media-state" :class="group.can_import ? 'is-ready' : 'is-empty'">{{ group.can_import ? 'Готова к импорту' : 'Нет фото для импорта' }}</span></div>
    <p v-if="group.can_import"><strong>Добавится: {{ group.additions }} · Обновится: {{ group.updates }} · Удалится: {{ group.removals }}</strong> · Ручных фото: {{ group.manual_count }}</p>
    <p v-else class="dashboard-alert">Проверьте связь с карточкой, исходные материалы и защиту фото.</p>
    <p v-if="group.missing_removals" class="dashboard-alert">Фото, исчезнувших из источника: {{ group.missing_removals }}. Они удалятся из карточки после подтверждения.</p>
    <div v-if="group.sample_images.length"><p class="muted">Первые выбранные фото:</p><div class="bulk-media-samples"><a v-for="(image, index) in group.sample_images" :key="index" :href="image.url" target="_blank" rel="noopener noreferrer" :aria-label="`Открыть ${image.title} в полном размере`"><img :src="image.url" alt="" loading="lazy"></a></div></div>
    <p class="muted">Выбрано фото: {{ group.selected_count }} из {{ group.available_count }}.</p>
    <a :href="group.preview_url" target="_blank" rel="noopener noreferrer">Просмотреть и настроить фото этой группы →</a>
  </section>
  <form class="bulk-media-confirm" method="post" :action="data.action_url">
    <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken">
    <input type="hidden" name="action" value="import_media">
    <input type="hidden" name="confirm_media_import" value="1">
    <input v-if="data.vue_preview" type="hidden" name="vue" value="1">
    <template v-for="group in data.groups" :key="group.id"><input type="hidden" name="_selected_action" :value="group.id"><input type="hidden" :name="`fingerprint_${group.id}`" :value="group.fingerprint"></template>
    <button type="submit" class="primary-action" :disabled="!importable">Подтвердить импорт ({{ importable }})</button>
    <a :href="data.back_url">Отмена</a>
  </form>
</template>
