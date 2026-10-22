<script setup lang="ts">
type QueuedData = { jobs: { id: number; group_name: string; url: string }[]; back_url: string };
defineProps<{ data: QueuedData }>();
</script>

<template>
  <section class="workspace-intro">
    <h2>Фото поставлены в очередь</h2>
    <p>Загрузка продолжится в фоне. Откройте задание, чтобы увидеть прогресс и результат каждого фото.</p>
  </section>
  <div class="queued-media-list">
    <a v-for="job in data.jobs" :key="job.id" class="queued-media-link" :href="job.url"><strong>{{ job.group_name }}</strong><span>Импорт #{{ job.id }} · посмотреть прогресс →</span></a>
  </div>
  <p><a :href="data.back_url">← К списку групп</a></p>
</template>
