<script setup lang="ts">
import { ref } from 'vue';

type DetailData = {
  id: number; unit: string; external_id: string; project: string; project_id: number;
  reason: string; skipped_by: string; created_at: string;
  is_deleted: boolean; is_linked: boolean; status: string; can_restore: boolean;
  unit_url: string; matching_url: string; restore_url: string; back_url: string;
  return_fields: Record<string, string>; vue_preview: boolean;
};
const props = defineProps<{ data: DetailData }>();
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.skipped-unit-detail-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <a :href="data.back_url">← К пропущенным предложениям</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge">Пропущено</span><span class="meta-badge">{{ data.status }}</span><span v-if="data.is_deleted" class="meta-badge">Удалено в источнике</span><span v-if="data.is_linked" class="meta-badge">Уже связано</span></div><h2>Предложение {{ data.unit }}</h2><p class="muted">{{ data.project }} · ID {{ data.external_id }}</p><p>Причина: <strong>{{ data.reason || 'не указана' }}</strong></p><p class="muted">Пропущено {{ data.created_at }}<template v-if="data.skipped_by"> · {{ data.skipped_by }}</template></p><div class="asset-list-actions"><a v-if="data.unit_url" :href="data.unit_url">Посмотреть данные предложения →</a><a v-if="data.matching_url" :href="data.matching_url">Открыть сопоставление комплекса →</a></div></section>
  <section class="sync-dashboard"><h2>Вернуть в работу</h2><p v-if="data.can_restore">Предложение снова появится в очереди сопоставления этого комплекса.</p><p v-else-if="data.is_deleted">Предложение удалено в источнике. Вернуть его в очередь нельзя.</p><p v-else-if="data.is_linked">Предложение уже связано с группой. Проверьте связь в карточке предложения.</p><p v-else>Для возврата нужны права на сопоставление карточек.</p><form v-if="data.can_restore" method="post" :action="data.restore_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input v-for="(value, key) in data.return_fields" :key="key" type="hidden" :name="key" :value="value"><button type="submit" :disabled="submitting">{{ submitting ? 'Возвращаем…' : 'Вернуть в очередь' }}</button></form></section>
</template>
