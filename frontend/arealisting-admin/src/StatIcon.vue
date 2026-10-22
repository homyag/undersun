<script setup lang="ts">
defineProps<{ name: string }>();
</script>

<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <template v-if="name === 'building'">
      <rect x="5" y="3" width="14" height="18" rx="1.5" />
      <path d="M9 7h1m4 0h1M9 11h1m4 0h1M9 15h1m4 0h1M10 21v-3h4v3" />
    </template>
    <template v-else-if="name === 'home'">
      <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10Z" />
      <path d="M9 21v-8h6v8" />
    </template>
    <template v-else-if="name === 'link'">
      <path d="m10 13 4-4M8 16H7a4 4 0 0 1 0-8h3m4 0h3a4 4 0 0 1 0 8h-3" />
    </template>
    <template v-else-if="name === 'attention'">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v6m0 4h.01" />
    </template>
    <template v-else-if="name === 'cards'">
      <rect x="7" y="7" width="13" height="13" rx="2" />
      <path d="M16 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h2" />
    </template>
    <template v-else-if="name === 'inbox'">
      <path d="M4 4h16l2 12v4H2v-4L4 4Z" />
      <path d="M2 15h6l2 3h4l2-3h6" />
    </template>
    <template v-else-if="name === 'check'">
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12 3 3 5-6" />
    </template>
  </svg>
</template>
