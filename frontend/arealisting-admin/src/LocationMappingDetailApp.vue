<script setup lang="ts">
import { computed, ref } from 'vue';

type DetailData = {
  id: number; source_name: string; source_type: string; external_id: string;
  parent_external_id: string; description_en: string; description_ru: string;
  is_deleted: boolean; last_seen_at: string;
  mode: string; district: string; location: string; is_confirmed: boolean;
  can_change: boolean; vue_preview: boolean;
  modes: { value: string; label: string }[];
  districts: { id: string; name: string }[];
  locations: { id: string; name: string; district: string }[];
  errors: Record<string, string[]>; save_url: string; back_url: string;
  return_fields: Record<string, string>;
};
const props = defineProps<{ data: DetailData }>();
const mode = ref(props.data.mode);
const district = ref(props.data.district);
const location = ref(props.data.location);
const confirmed = ref(props.data.is_confirmed);
const locationSearch = ref('');
const filteredLocations = computed(() => props.data.locations.filter(item =>
  `${item.name} ${item.district}`.toLocaleLowerCase().includes(locationSearch.value.toLocaleLowerCase())
  || item.id === location.value,
));
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.location-mapping-detail-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <a :href="data.back_url">← К списку локаций</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge" :data-status="data.is_confirmed ? 'ready' : 'pending'">{{ data.is_confirmed ? 'Подтверждена' : 'Ждёт проверки' }}</span><span v-if="data.is_deleted" class="meta-badge">Удалена в источнике</span></div><h2>{{ data.source_name }}</h2><p class="muted">{{ data.source_type || 'Тип не указан' }} · ID {{ data.external_id }}<template v-if="data.parent_external_id"> · родитель {{ data.parent_external_id }}</template></p><p v-if="data.last_seen_at" class="muted">Последний раз получена {{ data.last_seen_at }}</p><div v-if="data.description_ru || data.description_en" class="location-source-description"><p v-if="data.description_ru">{{ data.description_ru }}</p><p v-if="data.description_en" lang="en">{{ data.description_en }}</p></div></section>
  <section class="sync-dashboard"><div class="dashboard-heading"><div><h2>Сопоставление с Undersun</h2><p class="muted">Выберите район или локацию и подтвердите связь после проверки. Для записи, которую не нужно использовать, выберите «Игнорировать».</p></div></div>
    <form v-if="data.can_change" method="post" :action="data.save_url" class="location-mapping-form" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input v-for="(value, key) in data.return_fields" :key="key" type="hidden" :name="key" :value="value">
      <p v-if="data.errors.__all__?.length" class="dashboard-alert" role="alert">{{ data.errors.__all__.join(' ') }}</p>
      <label>Как использовать<select v-model="mode" name="mapping_mode"><option v-for="item in data.modes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <p v-if="data.errors.mapping_mode?.length" class="group-field-error" role="alert">{{ data.errors.mapping_mode.join(' ') }}</p>
      <label v-if="mode === 'DISTRICT'">Район Undersun<select v-model="district" name="district" :aria-invalid="!!data.errors.district?.length"><option value="">Выберите район</option><option v-for="item in data.districts" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <p v-if="data.errors.district?.length" class="group-field-error" role="alert">{{ data.errors.district.join(' ') }}</p>
      <template v-if="mode === 'LOCATION'"><label>Найти локацию<input v-model="locationSearch" type="search" placeholder="Название или район"></label><label>Локация Undersun<select v-model="location" name="location" :aria-invalid="!!data.errors.location?.length"><option value="">Выберите локацию</option><option v-for="item in filteredLocations" :key="item.id" :value="item.id">{{ item.name }}, {{ item.district }}</option></select></label></template>
      <p v-if="data.errors.location?.length" class="group-field-error" role="alert">{{ data.errors.location.join(' ') }}</p>
      <p v-if="mode === 'IGNORE'" class="muted">Эта запись не будет использоваться для определения района или локации карточки.</p><p v-if="mode === 'UNMAPPED'" class="muted">Связь пока не выбрана. Карточкам из этой локации может потребоваться ручная проверка.</p>
      <label class="group-check"><input v-model="confirmed" name="is_confirmed" type="checkbox">Сопоставление проверено и подтверждено</label>
      <p v-if="data.errors.is_confirmed?.length" class="group-field-error" role="alert">{{ data.errors.is_confirmed.join(' ') }}</p>
      <button type="submit" :disabled="submitting">{{ submitting ? 'Сохраняем…' : 'Сохранить сопоставление' }}</button>
    </form>
    <div v-else><p><strong>Режим:</strong> {{ data.modes.find(item => item.value === data.mode)?.label }}</p><p><strong>Район:</strong> {{ data.districts.find(item => item.id === data.district)?.name || 'не выбран' }}</p><p><strong>Локация:</strong> {{ data.locations.find(item => item.id === data.location)?.name || 'не выбрана' }}</p></div>
  </section>
</template>
