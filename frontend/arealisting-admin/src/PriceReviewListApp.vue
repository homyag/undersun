<script setup lang="ts">
import { ref } from 'vue';

type Review = {
  id: number; property: string; property_url: string; project: string;
  percent: string; status: string; status_label: string;
  before: string; after: string; created_at: string;
  reviewed_at: string; reviewed_by: string; url: string;
};
type ListData = {
  filter_url: string; vue_preview: boolean;
  status: string; period: string; query: string; order: string;
  statuses: { value: string; label: string; count: number; url: string }[];
  all_count: number; all_url: string; result_count: number;
  page: { number: number; total: number; previous_url: string; next_url: string };
  reviews: Review[];
};

const props = defineProps<{ data: ListData }>();
const query = ref(props.data.query);
const period = ref(props.data.period);
const order = ref(props.data.order);
</script>

<template>
  <section class="workspace-intro">
    <h2>Предложения новых цен</h2>
    <p>Большие изменения цены ждут решения. Откройте предложение, проверьте выбранные объекты и подтвердите или отклоните новую цену.</p>
  </section>
  <nav class="price-review-statuses" aria-label="Статус предложений цены">
    <a :href="data.all_url" :aria-current="data.status === '' ? 'page' : undefined">Все <strong>{{ data.all_count }}</strong></a>
    <a v-for="item in data.statuses" :key="item.value" :href="item.url" :aria-current="data.status === item.value ? 'page' : undefined">{{ item.label }} <strong>{{ item.count }}</strong></a>
  </nav>
  <section class="work-queue">
    <div class="dashboard-heading"><div><h2>Предложения · {{ data.result_count }}</h2><p class="muted">Показаны {{ data.status ? data.statuses.find(item => item.value === data.status)?.label.toLowerCase() : 'все статусы' }}.</p></div></div>
    <form method="get" :action="data.filter_url" class="price-review-filters">
      <input type="hidden" name="status__exact" :value="data.status">
      <input v-if="data.vue_preview" type="hidden" name="vue" value="1">
      <label>Поиск по карточке или комплексу <input v-model="query" type="search" name="q" placeholder="Название карточки или комплекса"></label>
      <label>Создано <select v-model="period" name="period"><option value="all">За всё время</option><option value="7d">За 7 дней</option><option value="30d">За 30 дней</option></select></label>
      <label>Порядок <select v-model="order" name="order"><option value="newest">Сначала новые</option><option value="oldest">Сначала старые</option><option value="largest">Наибольшее изменение</option></select></label>
      <button type="submit">Показать</button>
    </form>
    <div v-if="data.reviews.length" class="work-queue-list">
      <article v-for="review in data.reviews" :key="review.id" class="work-queue-item price-review-row">
        <div>
          <div class="price-review-meta"><span class="meta-badge" :data-status="review.status">{{ review.status_label }}</span><span class="muted">{{ review.created_at }}</span></div>
          <h3>{{ review.property }}</h3>
          <p class="muted">{{ review.project }}</p>
          <p class="price-review-amount"><strong>{{ review.before }}</strong><span aria-hidden="true">→</span><strong>{{ review.after }}</strong> THB <span class="meta-badge">{{ review.percent }}%</span></p>
          <p v-if="review.reviewed_at" class="muted">Решение принято {{ review.reviewed_at }}<template v-if="review.reviewed_by"> · {{ review.reviewed_by }}</template></p>
        </div>
        <div class="review-queue-actions"><a :href="review.url">{{ review.status === 'PENDING' ? 'Проверить цену' : 'Посмотреть решение' }} →</a><a v-if="review.property_url" :href="review.property_url">Открыть карточку</a></div>
      </article>
    </div>
    <p v-else>Предложений с такими фильтрами нет.</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы предложений цен"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
