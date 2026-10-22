<script setup lang="ts">
import { computed, ref } from 'vue';

type Action = { url: string; label: string } | null;
type Issue = { reason: string; next_step: string; intentional: boolean; is_current?: boolean; action: Action };
type Change = { source_field: string; label: string; before: string; after: string; card_value: string;
  has_card_field: boolean; status: string; action: Action; can_lock: boolean;
  expected_card_value: string; expected_source_value: string };
type Event = { id: number; kind: string; title: string; created_at: string; unit: string; detail: string;
  guidance: Issue | null; field_changes: Change[]; reviewed_at: string; reviewed_by: string;
  url: string; action: string; checked_url: string; keep_url: string };
type ReviewData = {
  state: string; kind: string; kinds: { value: string; label: string }[];
  filter_url: string; vue_preview: boolean; return_fields: Record<string, string>;
  event_count: number; page: { number: number; total: number; previous_url: string; next_url: string };
  can_mark_checked: boolean; price_list_url: string;
  price_reviews: { id: number; property: string; percent: string; before: string; after: string; created_at: string; url: string }[];
  group_errors: { id: number; property: string; project: string; issues: Issue[]; url: string }[];
  events: Event[];
};

const props = defineProps<{ data: ReviewData }>();
const search = ref('');
const state = ref(props.data.state);
const kind = ref(props.data.kind);
const submitting = ref(false);
const csrfToken = document.querySelector<HTMLInputElement>('.review-queue-page > input[name="csrfmiddlewaretoken"]')?.value || '';
const visibleEvents = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('ru-RU');
  if (!query) return props.data.events;
  return props.data.events.filter((event) => [event.title, event.kind, event.unit, event.detail,
    event.guidance?.reason || '', String(event.id)].some((value) => value.toLocaleLowerCase('ru-RU').includes(query)));
});
</script>

<template>
  <section class="workspace-intro">
    <h2>Очередь изменений AREALISTING</h2>
    <p>Проверьте изменения в карточке или комплексе, затем отметьте событие проверенным. Для характеристик показаны данные конкретного предложения и текущее значение карточки.</p>
  </section>

  <section v-if="data.price_reviews.length" class="work-queue">
    <div class="dashboard-heading"><div><h2>Цены ждут решения · {{ data.price_reviews.length }}</h2><p class="muted">Пока решение не принято, прежняя цена остаётся в карточке.</p></div></div>
    <div class="work-queue-list"><article v-for="review in data.price_reviews" :key="review.id" class="work-queue-item">
      <div><span class="meta-badge">{{ review.percent }}%</span><h3>{{ review.property }}</h3><p class="muted">{{ review.before }} → {{ review.after }} THB · {{ review.created_at }}</p></div>
      <a :href="review.url">Проверить цену →</a>
    </article></div>
    <p v-if="data.price_reviews.length === 20"><a :href="data.price_list_url">Все предложения цен →</a></p>
  </section>

  <section v-if="data.group_errors.length" class="work-queue">
    <div class="dashboard-heading"><div><h2>Почему данные не обновились · {{ data.group_errors.length }}</h2><p class="muted">Замечания последней проверки связанных карточек. После исправления обновите данные, чтобы проверить результат.</p></div></div>
    <div class="work-queue-list"><article v-for="entry in data.group_errors" :key="entry.id" class="work-queue-item">
      <div><span class="meta-badge">Карточка</span><h3>{{ entry.property }}</h3><p class="muted">{{ entry.project }}</p>
        <div v-for="(issue, index) in entry.issues" :key="index" class="review-issue"><strong>{{ issue.reason }}</strong><p>{{ issue.next_step }}</p><small v-if="issue.intentional">Оставлено намеренно</small><a v-if="issue.action" :href="issue.action.url">{{ issue.action.label }} →</a></div>
      </div><a :href="entry.url">Открыть группу →</a>
    </article></div>
  </section>

  <section class="work-queue">
    <div class="dashboard-heading"><div><h2>События синхронизации · {{ data.event_count }}</h2><p class="muted">Новые предложения, продажи, изменения характеристик и цен. Проверенные события остаются в истории.</p></div></div>
    <form method="get" :action="data.filter_url" class="review-queue-filters">
      <label>Статус <select v-model="state" name="state"><option value="open">Открытые</option><option value="checked">Проверенные</option></select></label>
      <label>Тип <select v-model="kind" name="kind"><option value="">Все изменения</option><option v-for="item in data.kinds" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <input v-if="data.vue_preview" type="hidden" name="vue" value="1">
      <button type="submit">Показать</button>
    </form>
    <label v-if="data.events.length" class="review-page-search">Найти на этой странице <input v-model="search" type="search" placeholder="Карточка, тип, предложение или ID"></label>
    <p v-if="search" class="muted">Найдено на текущей странице: {{ visibleEvents.length }} из {{ data.events.length }}. Фильтры выше ищут по всей очереди.</p>

    <div v-if="visibleEvents.length" class="work-queue-list"><article v-for="event in visibleEvents" :id="`event-${event.id}`" :key="event.id" class="work-queue-item">
      <div><span class="meta-badge">{{ event.kind }}</span><h3>{{ event.title }}</h3><p class="muted">{{ event.created_at }}<template v-if="event.unit"> · {{ event.unit }}</template></p>
        <p v-if="event.detail && !event.guidance">{{ event.detail }}</p>
        <div v-if="event.guidance" class="review-issue"><strong>{{ event.guidance.reason }}</strong><p>{{ event.guidance.next_step }}</p><small>{{ event.guidance.is_current ? 'Причина всё ещё актуальна' : 'Причина последнего события; текущее состояние проверьте заново' }}<template v-if="event.guidance.intentional"> · Оставлено намеренно</template></small><a v-if="event.guidance.action" :href="event.guidance.action.url">{{ event.guidance.action.label }} →</a></div>
        <div v-if="event.field_changes.length" class="review-comparison-scroll"><table class="review-comparison"><thead><tr><th>Поле</th><th>Было в AREALISTING</th><th>Стало в AREALISTING</th><th>Сейчас в Undersun</th><th>Состояние</th></tr></thead><tbody>
          <tr v-for="change in event.field_changes" :key="change.source_field"><th scope="row">{{ change.label }}</th><td>{{ change.before }}</td><td>{{ change.after }}</td><td>{{ change.has_card_field ? change.card_value : '—' }}</td><td>{{ change.status }}<p v-if="change.action"><a :href="change.action.url">{{ change.action.label }} →</a></p>
            <form v-if="change.can_lock && !event.reviewed_at" method="post" :action="event.keep_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-for="(value, name) in data.return_fields" :key="name" type="hidden" :name="name" :value="value"><input type="hidden" name="source_field" :value="change.source_field"><input type="hidden" name="expected_card_value" :value="change.expected_card_value"><input type="hidden" name="expected_source_value" :value="change.expected_source_value"><button type="submit" class="secondary" :disabled="submitting">Сохранить значение Undersun</button></form>
          </td></tr>
        </tbody></table></div>
        <p v-if="event.reviewed_at" class="muted">Проверено {{ event.reviewed_at }}<template v-if="event.reviewed_by"> · {{ event.reviewed_by }}</template></p>
      </div>
      <div class="review-queue-actions"><a :href="event.url">{{ event.action }} →</a><form v-if="data.can_mark_checked && !event.reviewed_at" method="post" :action="event.checked_url" @submit="submitting = true"><input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken"><input v-for="(value, name) in data.return_fields" :key="name" type="hidden" :name="name" :value="value"><button type="submit" class="secondary" :disabled="submitting">Отметить проверенным</button></form></div>
    </article></div>
    <p v-else>{{ search ? 'На этой странице совпадений нет.' : 'Событий с такими фильтрами нет.' }}</p>
    <nav v-if="data.page.total > 1" class="review-queue-pagination" aria-label="Страницы очереди"><a v-if="data.page.previous_url" :href="data.page.previous_url">← Назад</a><span>{{ data.page.number }} / {{ data.page.total }}</span><a v-if="data.page.next_url" :href="data.page.next_url">Далее →</a></nav>
  </section>
</template>
