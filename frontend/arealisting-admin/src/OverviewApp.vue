<script setup lang="ts">
import { computed } from 'vue';
import Card from 'primevue/card';
import StatIcon from './StatIcon.vue';

type Totals = { projects: number; available_units: number; linked_properties: number };
const props = defineProps<{ totals: Totals; attentionCount: number }>();
const metrics = computed(() => [
  { label: 'Комплексов в базе', value: props.totals.projects, icon: 'building', detail: 'Выбрать комплекс →', tone: 'neutral', href: '#project-search' },
  { label: 'Доступных предложений', value: props.totals.available_units, icon: 'home', detail: 'Открыть комплексы →', tone: 'neutral', href: '#project-search' },
  { label: 'Связанных карточек', value: props.totals.linked_properties, icon: 'link', detail: 'Посмотреть комплексы →', tone: 'neutral', href: '#project-search' },
  { label: 'Требуют внимания', value: props.attentionCount, icon: 'attention', detail: 'Перейти к списку →', tone: props.attentionCount ? 'attention' : 'neutral', href: '#needs-attention' },
]);
const format = (value: number) => new Intl.NumberFormat('ru-RU').format(value);
</script>

<template>
  <section class="arealisting-overview-metrics" aria-label="Сводка AREALISTING">
    <a v-for="metric in metrics" :key="metric.label" class="overview-metric-link" :href="metric.href" :aria-label="`${metric.label}: ${format(metric.value)}. ${metric.detail}`">
      <Card class="arealisting-stat-card" :class="`is-${metric.tone}`">
        <template #content>
          <div class="arealisting-stat-top"><span>{{ metric.label }}</span><StatIcon :name="metric.icon" /></div>
          <strong>{{ format(metric.value) }}</strong>
          <small>{{ metric.detail }}</small>
        </template>
      </Card>
    </a>
  </section>
</template>
