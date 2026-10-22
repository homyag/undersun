<script setup lang="ts">
type DetailData = {
  id: number; role: string; group: string; property: string; project: string;
  asset_type: string; source_key: string; source_url: string; asset_error: string;
  is_active: boolean; preview_url: string; card_image_url: string;
  has_image: boolean; is_main: boolean; position: number;
  created_at: string; updated_at: string; back_url: string;
  asset_url: string; group_url: string; property_url: string;
};
defineProps<{ data: DetailData }>();
</script>

<template>
  <a :href="data.back_url">← К фото в карточках</a>
  <section class="workspace-intro"><div class="price-review-meta"><span class="meta-badge">{{ data.role }}</span><span class="meta-badge">{{ data.has_image ? 'Фото создано' : 'Фото отсутствует' }}</span><span v-if="data.is_main" class="meta-badge">Главное фото</span></div><h2>{{ data.property || data.group }}</h2><p class="muted">{{ data.project }} · {{ data.asset_type }}</p><div class="asset-list-actions"><a v-if="data.group_url" :href="data.group_url">Связь с карточкой →</a><a v-if="data.property_url" :href="data.property_url">Карточка Undersun →</a><a v-if="data.asset_url" :href="data.asset_url">Материал AREALISTING →</a></div></section>
  <section class="work-queue"><div class="dashboard-heading"><div><h2>Изображение</h2><p class="muted">Откройте полный размер, чтобы проверить фото.</p></div></div><div class="property-asset-preview"><a v-if="data.preview_url" :href="data.preview_url" target="_blank" rel="noopener noreferrer"><img :src="data.preview_url" :alt="`Фото для ${data.property || data.group}`"><span>Открыть в полном размере ↗</span></a><p v-else>Файл пока недоступен.</p></div><p v-if="!data.has_image" class="dashboard-alert">Изображение карточки отсутствует. Откройте связь с карточкой и проверьте импорт фотографий.</p><p v-if="data.asset_error" class="dashboard-alert">Ошибка материала: {{ data.asset_error }}</p><dl class="asset-detail-facts"><div><dt>Исходный материал</dt><dd>{{ data.source_key }}</dd></div><div><dt>Позиция в источнике</dt><dd>{{ data.position }}</dd></div><div><dt>Активность материала</dt><dd>{{ data.is_active ? 'Активен' : 'Неактивен' }}</dd></div><div><dt>Добавлено</dt><dd>{{ data.created_at }}</dd></div><div><dt>Обновлено</dt><dd>{{ data.updated_at }}</dd></div></dl><div class="asset-list-actions"><a v-if="data.source_url" :href="data.source_url" target="_blank" rel="noopener noreferrer">Открыть оригинал AREALISTING ↗</a><a v-if="data.card_image_url" :href="data.card_image_url" target="_blank" rel="noopener noreferrer">Открыть файл карточки ↗</a></div></section>
</template>
