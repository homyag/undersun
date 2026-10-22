<script setup lang="ts">
import { ref } from 'vue';

type Field = { label: string; value: string | number | null };
type UnitData = {
  id: number; number: string; external_id: string; project: string; status: string;
  availability_status: string; is_deleted: boolean; can_change: boolean;
  vue_preview: boolean; sync_enabled: boolean; listing_group: string;
  group_choices: { id: string; label: string }[]; group_url: string;
  property: string; property_url: string; project_url: string;
  is_skipped: boolean; skipped_url: string; skip_reason: string;
  source_fields: Field[]; furnishing: string; gallery_count: number;
  last_seen_at: string; synced_at: string;
  errors: Record<string, string[]>; save_url: string; back_url: string;
  return_fields: Record<string, string>;
};
const props = defineProps<{ data: UnitData }>();
const group = ref(props.data.listing_group);
const syncEnabled = ref(props.data.sync_enabled);
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.unit-detail-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <a :href="data.back_url">← К списку предложений</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge" :data-status="data.availability_status === 'AVAILABLE' ? 'ready' : 'pending'">{{ data.status }}</span><span v-if="data.is_skipped" class="meta-badge">Пропущено вручную</span><span v-if="!data.sync_enabled" class="meta-badge">Синхронизация выключена</span><span v-if="data.is_deleted" class="meta-badge">Удалено в источнике</span></div><h2>Предложение {{ data.number }}</h2><p class="muted">{{ data.project }} · ID источника {{ data.external_id }}</p><p v-if="data.is_skipped">Причина пропуска: {{ data.skip_reason || 'не указана' }}</p><div class="asset-list-actions"><a v-if="data.project_url" :href="data.project_url">Открыть комплекс →</a><a v-if="data.group_url" :href="data.group_url">Открыть группу →</a><a v-if="data.property_url" :href="data.property_url">Открыть карточку →</a><a v-if="data.skipped_url" :href="data.skipped_url">Открыть решение о пропуске →</a></div></section>
  <section class="sync-dashboard"><div class="dashboard-heading"><div><h2>Данные из AREALISTING</h2><p class="muted">Обновляются при получении данных источника.</p></div></div><dl class="unit-source-grid"><div v-for="field in data.source_fields" :key="field.label"><dt>{{ field.label }}</dt><dd>{{ field.value === null || field.value === '' ? '—' : field.value }}</dd></div><div><dt>Материалов в галерее источника</dt><dd>{{ data.gallery_count }}</dd></div><div v-if="data.furnishing"><dt>Меблировка</dt><dd>{{ data.furnishing }}</dd></div><div v-if="data.last_seen_at"><dt>Последний раз получено</dt><dd>{{ data.last_seen_at }}</dd></div><div v-if="data.synced_at"><dt>Синхронизировано</dt><dd>{{ data.synced_at }}</dd></div></dl></section>
  <section class="sync-dashboard"><div class="dashboard-heading"><div><h2>Настройки предложения</h2><p class="muted">Выберите группу этого комплекса. После изменения группы проверьте цену и состав предложений в карточке.</p></div></div>
    <form v-if="data.can_change" method="post" :action="data.save_url" class="unit-settings-form" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input v-for="(value, key) in data.return_fields" :key="key" type="hidden" :name="key" :value="value">
      <p v-if="data.errors.__all__?.length" class="dashboard-alert" role="alert">{{ data.errors.__all__.join(' ') }}</p><label>Группа публикации<select v-model="group" name="listing_group" :aria-invalid="!!data.errors.listing_group?.length"><option value="">Без группы</option><option v-for="item in data.group_choices" :key="item.id" :value="item.id">{{ item.label }}</option></select></label><p v-if="data.errors.listing_group?.length" class="group-field-error" role="alert">{{ data.errors.listing_group.join(' ') }}</p><label class="group-check"><input v-model="syncEnabled" name="sync_enabled" type="checkbox">Синхронизация предложения включена</label><button type="submit" :disabled="submitting">{{ submitting ? 'Сохраняем…' : 'Сохранить настройки' }}</button></form>
    <div v-else><p><strong>Группа:</strong> {{ data.group_choices.find(item => item.id === data.listing_group)?.label || 'Не выбрана' }}</p><p><strong>Синхронизация:</strong> {{ data.sync_enabled ? 'Включена' : 'Отключена' }}</p></div>
  </section>
</template>
