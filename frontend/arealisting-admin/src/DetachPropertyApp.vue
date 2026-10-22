<script setup lang="ts">
import { ref } from 'vue';

type DetachData = {
  property_title: string; property_id: number; project_title: string;
  group_id: number; unit_count: number; action_url: string;
  group_url: string; property_url: string; vue_preview: boolean;
};
defineProps<{ data: DetachData }>();
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.detach-property-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <a :href="data.group_url">← К связи с карточкой</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge">Подтверждение действия</span></div><h2>Отвязать карточку от AREALISTING?</h2><p>Карточка <strong>{{ data.property_title }}</strong> (№{{ data.property_id }}) сейчас связана с комплексом <strong>{{ data.project_title }}</strong>.</p></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Что произойдёт</h2></div></div><ul class="detach-effects"><li>Связь с комплексом будет удалена.</li><li>{{ data.unit_count }} выбранных предложений AREALISTING снова станут свободными для сопоставления.</li><li>Карточка, её поля и фотографии сохранятся.</li><li>После отвязки можно выбрать другой комплекс.</li></ul><form method="post" :action="data.action_url" class="asset-list-actions" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input type="hidden" name="group_id" :value="data.group_id"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><button type="submit" :disabled="submitting">{{ submitting ? 'Отвязываем…' : 'Отвязать карточку' }}</button><a :href="data.group_url">Отмена</a><a :href="data.property_url">Открыть карточку</a></form></section>
</template>
