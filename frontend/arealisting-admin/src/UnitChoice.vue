<script setup lang="ts">
import type { Unit } from './model';
defineProps<{ unit: Unit; modelValue: boolean; linked?: boolean; suggested?: boolean; reason?: string; disabled?: boolean }>();
defineEmits<{ 'update:modelValue': [value: boolean] }>();
const format = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value);
const statuses: Record<string, string> = { AVAILABLE: 'Доступен', SOLD: 'Продан' };
const types: Record<string, string> = { CONDO: 'Кондо', VILLA: 'Вилла', HOUSE: 'Таунхаус', TOWNHOUSE: 'Таунхаус' };
</script>
<template>
  <label class="unit-choice" :class="{ suggested, 'is-linked': linked, 'is-skipped': unit.skipped, 'is-unavailable': disabled }">
    <input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked)">
    <span class="unit-choice-content">
      <span class="unit-choice-heading"><strong class="unit-number">№ {{ unit.number || 'без номера' }}</strong>
        <span class="status-badge" :class="{ 'is-available': unit.status === 'AVAILABLE', 'is-sold': unit.status === 'SOLD' }">{{ statuses[unit.status] || 'Статус не указан' }}</span>
        <span v-if="unit.property_type" class="meta-badge">{{ types[unit.property_type] || unit.property_type }}</span>
        <span v-if="linked" class="meta-badge is-linked">Связано сейчас</span>
      </span>
      <span class="unit-choice-meta">{{ unit.bedrooms ?? '—' }} сп. · {{ format(unit.area_total) }} м² · этаж {{ unit.floor ?? '—' }} · {{ format(unit.price) }} {{ unit.currency || '' }}</span>
      <small v-if="reason" class="unit-choice-reason">{{ reason }}</small>
    </span>
  </label>
</template>
