<script setup lang="ts">
import { ref } from 'vue';

type PriceData = {
  id: number; property: string; project: string; property_url: string; back_url: string;
  decision_url: string; vue_preview: boolean; change_percent: string; status: string;
  return_fields: Record<string, string>;
  created_at: string; reviewed_at: string; reviewed_by: string; can_decide: boolean;
  prices: { currency: string; before: string; after: string }[];
  units: { number: string; source_price: string; currency: string; price_thb: string }[];
};

defineProps<{ data: PriceData }>();
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.readiness-page > input[name="csrfmiddlewaretoken"]')?.value || '';
</script>

<template>
  <a :href="data.back_url">← К предложениям цен</a>
  <section class="workspace-intro">
    <h2><a :href="data.property_url">{{ data.property }}</a></h2>
    <p class="muted">{{ data.project }} · Изменение {{ data.change_percent }}% · {{ data.status }} · {{ data.created_at }}</p>
    <p v-if="data.can_decide">До вашего решения цена карточки остаётся прежней. Перед подтверждением система заново проверит выбранные предложения, цену и курсы валют.</p>
    <p v-else-if="data.reviewed_at">Решение принято {{ data.reviewed_at }}<template v-if="data.reviewed_by"> · {{ data.reviewed_by }}</template>.</p>
  </section>
  <section class="sync-dashboard">
    <h2>Текущая и предложенная цена</h2>
    <div class="review-comparison-scroll"><table class="review-comparison"><thead><tr><th scope="col">Валюта</th><th scope="col">Сейчас в карточке</th><th scope="col">Предложено</th></tr></thead><tbody>
      <tr v-for="price in data.prices" :key="price.currency"><th scope="row">{{ price.currency }}</th><td>{{ price.before }}</td><td>{{ price.after }}</td></tr>
    </tbody></table></div>
    <h3>Выбранные доступные предложения</h3>
    <p class="muted">В цену карточки попадёт минимальная стоимость в THB из списка ниже.</p>
    <div class="review-comparison-scroll"><table class="review-comparison"><thead><tr><th scope="col">Предложение</th><th scope="col">Цена в источнике</th><th scope="col">После пересчёта в THB</th></tr></thead><tbody>
      <tr v-for="(unit, index) in data.units" :key="`${unit.number}-${index}`"><td>{{ unit.number }}</td><td>{{ unit.source_price }} {{ unit.currency }}</td><td>{{ unit.price_thb }}</td></tr>
    </tbody></table></div>
    <div v-if="data.can_decide" class="review-decisions">
      <form method="post" :action="data.decision_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input v-for="(value, name) in data.return_fields" :key="name" type="hidden" :name="name" :value="value"><input type="hidden" name="decision" value="approve"><button type="submit" :disabled="submitting">Подтвердить новую цену</button></form>
      <form method="post" :action="data.decision_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-if="data.vue_preview" type="hidden" name="vue" value="1"><input v-for="(value, name) in data.return_fields" :key="name" type="hidden" :name="name" :value="value"><input type="hidden" name="decision" value="reject"><button type="submit" class="secondary" :disabled="submitting">Отклонить изменение</button></form>
    </div>
  </section>
</template>
