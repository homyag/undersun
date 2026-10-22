<script setup lang="ts">
import { ref } from 'vue';

type Issue = { reason: string; next_step: string; intentional: boolean; action: { label: string; url: string } | null };
type GroupData = {
  id: number; title: string; project: string; grouping: string; origin: string;
  property: string; property_url: string; available_units: number; price: string;
  currency: string; is_ready: boolean; updated_at: string; issues: Issue[];
  can_change: boolean; vue_preview: boolean; name: string; is_active: boolean;
  protected_fields: string[]; protection_choices: { value: string; label: string }[];
  errors: Record<string, string[]>; save_url: string; back_url: string;
  readiness_url: string; detach_url: string; preview_url: string; matching_url: string; history_url: string;
  media_candidate_count: number; media_link_count: number; media_error_count: number;
  media_errors: { title: string; error: string; url: string }[];
  latest_job: { status: string; url: string } | null;
};

const props = defineProps<{ data: GroupData }>();
const name = ref(props.data.name);
const active = ref(props.data.is_active);
const protectedFields = ref([...props.data.protected_fields]);
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.group-detail-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <a :href="data.back_url">← К списку связей</a>
  <section class="workspace-intro">
    <div class="price-review-meta"><span class="meta-badge">{{ data.grouping }}</span><span class="meta-badge">{{ data.origin }}</span><span class="meta-badge" :data-status="data.is_ready ? 'ready' : 'pending'">{{ data.is_ready ? 'Готова к публикации' : 'Не готова' }}</span><span v-if="!data.is_active" class="meta-badge">Неактивна</span></div>
    <h2>{{ data.title }}</h2>
    <p class="muted">{{ data.project }} · обновлено {{ data.updated_at }}</p>
    <p>Карточка: <a v-if="data.property_url" :href="data.property_url">{{ data.property }}</a><span v-else>{{ data.property || 'пока не связана' }}</span></p>
    <p>Доступных предложений: {{ data.available_units }} · Цена: {{ data.price }}</p>
    <div class="asset-list-actions"><a v-if="data.matching_url" :href="data.matching_url">Изменить связь и предложения →</a><a v-if="data.readiness_url" :href="data.readiness_url">Проверить готовность →</a><a v-if="data.history_url" :href="data.history_url">История изменений →</a></div>
  </section>

  <section v-if="data.issues.length" class="work-queue">
    <div class="dashboard-heading"><div><h2>Требуют внимания · {{ data.issues.length }}</h2><p class="muted">Замечания последней проверки. После исправления обновите данные группы.</p></div></div>
    <div class="group-list-issues"><div v-for="(issue, index) in data.issues" :key="index" class="review-issue"><strong>{{ issue.reason }}</strong><p>{{ issue.next_step }}</p><small v-if="issue.intentional">Оставлено намеренно</small><a v-if="issue.action" :href="issue.action.url">{{ issue.action.label }} →</a></div></div>
  </section>

  <section class="sync-dashboard">
    <div class="dashboard-heading"><div><h2>Настройки группы</h2><p class="muted">Защита полей влияет на следующие обновления AREALISTING. Изменение связи с карточкой выполняется на экране сопоставления.</p></div></div>
    <form v-if="data.can_change" method="post" :action="data.save_url" class="group-detail-form" @submit="submitting = true">
      <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1">
      <div v-if="data.errors.__all__?.length" class="dashboard-alert" role="alert">{{ data.errors.__all__.join(' ') }}</div>
      <label>Название группы<input v-model="name" name="name" type="text" maxlength="255" :aria-invalid="!!data.errors.name?.length"></label>
      <p v-if="data.errors.name?.length" class="group-field-error" role="alert">{{ data.errors.name.join(' ') }}</p>
      <label class="group-check"><input v-model="active" name="is_active" type="checkbox">Активная группа</label>
      <p class="muted">Если доступных предложений не останется, пересчёт автоматически сделает группу неактивной.</p>
      <fieldset class="group-protection"><legend>Защищено от обновления AREALISTING</legend><p class="muted">Ручное изменение карточки включает защиту автоматически. Снимите отметку, чтобы снова разрешить обновление.</p>
        <div v-if="data.protection_choices.length" class="group-protection-grid"><label v-for="field in data.protection_choices" :key="field.value"><input v-model="protectedFields" name="protected_fields" type="checkbox" :value="field.value">{{ field.label }}</label></div>
        <p v-else>Поля под управлением AREALISTING пока не выбраны.</p>
        <p v-if="data.errors.protected_fields?.length" class="group-field-error" role="alert">{{ data.errors.protected_fields.join(' ') }}</p>
      </fieldset>
      <button type="submit" :disabled="submitting">{{ submitting ? 'Сохраняем…' : 'Сохранить настройки' }}</button>
    </form>
    <div v-else class="group-detail-readonly"><p><strong>Название:</strong> {{ data.name || 'Без названия' }}</p><p><strong>Состояние:</strong> {{ data.is_active ? 'Активная' : 'Неактивная' }}</p><p><strong>Защищённые поля:</strong> {{ data.protection_choices.filter(field => data.protected_fields.includes(field.value)).map(field => field.label).join(', ') || 'Нет' }}</p></div>
  </section>

  <section class="sync-dashboard">
    <div class="dashboard-heading"><div><h2>Фотографии и планировки</h2><p class="muted">Подходящих материалов: {{ data.media_candidate_count }} · Уже в карточке: {{ data.media_link_count }} · С ошибками: {{ data.media_error_count }}</p></div></div>
    <p v-if="!data.property">Сначала свяжите группу с карточкой Undersun, затем проверьте импорт фотографий.</p>
    <template v-else><p>Импорт обновит фото, которыми управляет AREALISTING, и удалит из карточки ранее импортированные фото, отсутствующие в источнике. Перед подтверждением можно исключить неподходящие изображения.</p>
      <a v-if="data.preview_url" class="primary-action" :href="data.preview_url">Проверить и импортировать фото →</a>
      <p v-else>Импорт сейчас недоступен: нет подходящих изображений или фотографии и планировки защищены от обновления.</p>
    </template>
    <p v-if="data.latest_job"><a :href="data.latest_job.url">Последний импорт фото · {{ data.latest_job.status }} →</a></p>
    <div v-if="data.media_errors.length" class="group-media-errors"><h3>Материалы с ошибками</h3><ul><li v-for="asset in data.media_errors" :key="asset.url"><a :href="asset.url">{{ asset.title }}</a> — {{ asset.error }}</li></ul><p v-if="data.media_error_count > data.media_errors.length" class="muted">Показаны первые {{ data.media_errors.length }} из {{ data.media_error_count }} ошибок.</p></div>
  </section>

  <section v-if="data.detach_url" class="sync-dashboard group-detach-section"><h2>Изменить связь с карточкой</h2><p>Если комплекс выбран ошибочно, можно отвязать карточку. Её данные и фотографии сохранятся, а предложения станут доступны для нового сопоставления.</p><a :href="data.detach_url">Перейти к отвязке карточки →</a></section>
</template>
