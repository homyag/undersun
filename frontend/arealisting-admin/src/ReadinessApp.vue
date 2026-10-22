<script setup lang="ts">
type Check = {
  key: string; title: string; detail: string; required: boolean; ok: boolean;
  action: string; action_label: string; action_url: string;
};
type ReadinessData = {
  property_title: string; property_id: number; property_active: boolean;
  project_title: string; group_url: string; property_url: string;
  ready: boolean; required_missing: number; warnings: number; checks: Check[];
};
defineProps<{ data: ReadinessData }>();
</script>

<template>
  <a :href="data.group_url">← К связи с карточкой</a>
  <section class="workspace-intro">
    <div class="price-review-meta">
      <span class="meta-badge" :data-status="data.ready ? 'ready' : 'pending'">{{ data.ready ? 'Основные пункты выполнены' : 'Нужны исправления' }}</span>
      <span class="meta-badge">{{ data.property_active ? 'Опубликована' : 'Черновик' }}</span>
    </div>
    <h2>{{ data.property_title }}</h2>
    <p class="muted">{{ data.project_title }} · Карточка №{{ data.property_id }}</p>
    <p v-if="data.ready">{{ data.property_active ? 'Проверьте предупреждения ниже и содержание опубликованной карточки.' : 'Проверьте карточку целиком, затем включите «Активно», когда она будет готова к публикации.' }}</p>
    <p v-else class="dashboard-alert"><strong>Не пройдены обязательные проверки: {{ data.required_missing }}.</strong> Перед публикацией исправьте замечания ниже.</p>
    <div class="asset-list-actions"><a v-if="data.property_url" class="primary-action" :href="data.property_url">Открыть карточку →</a><a :href="data.group_url">Открыть связь →</a></div>
  </section>
  <section class="sync-dashboard" aria-labelledby="readiness-checks-title">
    <div class="dashboard-heading"><div><h2 id="readiness-checks-title">Проверка перед публикацией</h2><p class="muted">Проверены данные, сохранённые в Undersun. Для фотографий проверяется наличие записи в карточке.</p></div></div>
    <div class="readiness-list">
      <article v-for="check in data.checks" :key="check.key" class="readiness-item" :class="{ 'needs-attention': !check.ok }">
        <div><span class="meta-badge" :data-status="check.ok ? 'ready' : 'pending'">{{ check.ok ? 'Готово' : check.required ? 'Нужно исправить' : 'Рекомендуется проверить' }}</span><h3>{{ check.title }}</h3><p>{{ check.detail }}</p></div>
        <a v-if="!check.ok && check.action_url" :href="check.action_url">{{ check.action_label }} →</a>
      </article>
    </div>
  </section>
</template>
