<script setup lang="ts">
import { computed, ref, watch } from 'vue';

type MediaItem = {
  id: number; title: string; url: string; role: string;
  selected: boolean; existing: boolean; last_error: string;
};
type MediaPreviewData = {
  group_name: string; property_name: string; property_url: string;
  available: MediaItem[]; additions: number; updates: number; removals: number;
  manual_count: number; missing_removals: string[];
  preferred_main_asset_id: number | null; main_message: string;
  fingerprint: string; can_import: boolean;
  preview_url: string; confirm_url: string; back_url: string;
};

const { data } = defineProps<{ data: MediaPreviewData }>();
const initialSelected = data.available.filter(item => item.selected).map(item => item.id).sort((a, b) => a - b);
const selected = ref<number[]>([...initialSelected]);
const initialMain = data.preferred_main_asset_id ? String(data.preferred_main_asset_id) : '';
const preferredMain = ref(initialMain);
const csrfToken = document.querySelector<HTMLInputElement>('.media-preview-page > input[name="csrfmiddlewaretoken"]')?.value || '';
const dirty = computed(() => preferredMain.value !== initialMain
  || JSON.stringify([...selected.value].sort((a, b) => a - b)) !== JSON.stringify(initialSelected));
watch(selected, () => {
  if (preferredMain.value && !selected.value.includes(Number(preferredMain.value))) preferredMain.value = '';
});
function itemState(item: MediaItem) {
  if (selected.value.includes(item.id)) return item.existing ? 'Обновится' : 'Добавится';
  return item.existing ? 'Удалится из карточки' : 'Исключено';
}
</script>

<template>
  <a :href="data.back_url">← Вернуться к группе</a>
  <section class="workspace-intro">
    <h2>Проверьте изменения фотографий</h2>
    <p>Импорт обновит фото, которыми управляет AREALISTING, и удалит из карточки ранее импортированные фото, отсутствующие в источнике. Ручные фото и защищённые разделы останутся в карточке.</p>
    <p><strong>Снимите галочки с неподходящих фото и при желании выберите главное.</strong> Нажмите на миниатюру, чтобы открыть полный размер. Затем пересчитайте изменения и подтвердите выбор.</p>
    <p>После подтверждения загрузка продолжится в фоне. Страницу можно будет закрыть.</p>
  </section>
  <form class="vue-media-review-form" method="post" :action="data.confirm_url">
    <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken">
    <input type="hidden" name="selection_confirmed" value="1">
    <input type="hidden" name="preview_fingerprint" :value="data.fingerprint">
    <section class="sync-dashboard media-preview-group">
      <div class="dashboard-heading"><div><h2>{{ data.group_name }}</h2><p class="muted">Карточка: <a :href="data.property_url">{{ data.property_name }}</a></p></div></div>
      <template v-if="data.available.length">
        <h3>Какие фото импортировать</h3>
        <div class="media-selection-list">
          <div v-for="item in data.available" :key="item.id" class="media-selection-item">
            <input :id="`media-${item.id}`" v-model="selected" type="checkbox" name="asset" :value="item.id">
            <a :href="item.url" target="_blank" rel="noopener noreferrer" :aria-label="`Открыть фото ${item.title} в полном размере`" title="Открыть в полном размере"><img :src="item.url" alt="" loading="lazy"></a>
            <div><label :for="`media-${item.id}`">{{ item.title }} · {{ item.role === 'FLOOR_PLAN' ? 'Планировка' : 'Галерея' }}</label>
              <small class="media-selection-state" :class="{ 'will-remove': item.existing && !selected.includes(item.id) }">{{ itemState(item) }}</small>
              <small v-if="item.last_error">Предыдущая ошибка: {{ item.last_error }}</small>
              <label v-if="item.role === 'GALLERY'" class="media-main-choice"><input v-model="preferredMain" type="radio" name="preferred_main_asset_id" :value="String(item.id)" :disabled="!selected.includes(item.id)"> Сделать главным</label>
            </div>
          </div>
        </div>
      </template>
      <p v-if="dirty" class="dashboard-alert" role="status">Выбор изменён. Нажмите «Пересчитать изменения», чтобы увидеть итог перед импортом.</p>
      <p v-else-if="data.can_import"><strong>Добавится: {{ data.additions }} · Обновится: {{ data.updates }} · Удалится: {{ data.removals }}</strong> · Ручных фото: {{ data.manual_count }}</p>
      <p v-else class="dashboard-alert">{{ data.available.length ? 'Фото не выбраны. Сохраните выбор, чтобы они не добавлялись при следующих импортах.' : 'Для этой группы сейчас нет доступных изменений: проверьте связь с карточкой, исходные материалы и защиту фото.' }}</p>
      <h3>Главное фото</h3>
      <label v-if="data.available.length" class="media-main-auto"><input v-model="preferredMain" type="radio" name="preferred_main_asset_id" value=""> Сохранить текущее главное, если оно останется в карточке</label>
      <p v-if="!dirty">{{ data.main_message }}</p>
      <p v-if="data.missing_removals.length" class="dashboard-alert"><strong>Также удалятся фото, исчезнувшие из источника: {{ data.missing_removals.length }}.</strong> Они больше не доступны для выбора. {{ data.missing_removals.join(', ') }}.</p>
    </section>
    <div class="vue-media-actions">
      <button v-if="data.available.length" type="submit" class="secondary" :formaction="data.preview_url">Пересчитать изменения</button>
      <button v-if="data.can_import || data.available.length" type="submit" class="primary-action" :disabled="dirty">{{ data.can_import ? 'Применить изменения фото' : 'Сохранить выбор' }}</button>
      <a :href="data.back_url">Отмена</a>
    </div>
  </form>
</template>
