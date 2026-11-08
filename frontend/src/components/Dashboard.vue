<script setup>
import { computed, ref, watch } from 'vue'
import { addDays, api, localDate, qs } from '../api'
import KpiCards from './KpiCards.vue'
import TrendChart from './TrendChart.vue'
import RankTable from './RankTable.vue'
import ModelPanel from './ModelPanel.vue'
import DetailDrawer from './DetailDrawer.vue'

const today = localDate()
// MaaS rejects ranges older than 30 days
const minDate = addDays(today, -29)
const presets = [
  { id: 'today', name: '今天', range: () => [today, today] },
  { id: '7d', name: '近 7 天', range: () => [addDays(today, -6), today] },
  { id: '30d', name: '近 30 天', range: () => [minDate, today] },
]
const preset = ref('7d')
const start = ref(addDays(today, -6))
const end = ref(today)
const metric = ref('tokens')
const model = ref('')
const overview = ref(null)
const models = ref([])
const detail = ref(null)
const error = ref('')
const loading = ref(false)

function pick(p) {
  preset.value = p.id
  ;[start.value, end.value] = p.range()
}

const filters = computed(() => ({ start: start.value, end: end.value, model: model.value || null }))

async function loadOverview() {
  error.value = ''
  loading.value = true
  try {
    overview.value = await api('/api/overview?' + qs(filters.value))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function loadModels() {
  try {
    models.value = (await api('/api/usage/models?' + qs({ start: start.value, end: end.value }))).map((x) => x.key)
  } catch { models.value = [] }
}
watch(filters, loadOverview, { immediate: true })
watch([start, end], loadModels, { immediate: true })
</script>

<template>
  <div class="bar card">
    <div class="seg">
      <button v-for="p in presets" :key="p.id" :class="{ on: preset === p.id }" @click="pick(p)">{{ p.name }}</button>
    </div>
    <input type="date" v-model="start" @change="preset = ''" :min="minDate" :max="end" />
    <span class="muted">至</span>
    <input type="date" v-model="end" @change="preset = ''" :min="start" :max="today" />
    <select v-model="model">
      <option value="">全部模型</option>
      <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
    </select>
    <span class="grow" />
    <span class="muted">口径</span>
    <div class="seg">
      <button :class="{ on: metric === 'tokens' }" @click="metric = 'tokens'">Tokens</button>
      <button :class="{ on: metric === 'requests' }" @click="metric = 'requests'">调用次数</button>
    </div>
  </div>

  <div v-if="error" class="notice">{{ error }}</div>
  <KpiCards v-if="!error" :data="loading ? null : overview" />
  <TrendChart :filters="filters" :metric="metric" drill @drill="model = $event" />
  <RankTable :filters="filters" :metric="metric" @open="detail = $event" />
  <ModelPanel :filters="filters" :metric="metric" />
  <DetailDrawer v-if="detail" :item="detail" :filters="filters" :metric="metric" @close="detail = null" />
</template>

<style scoped>
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 10px 16px; margin-bottom: 12px; }
.grow { flex: 1; }
.notice { background: var(--bad-soft); color: var(--bad); border-radius: var(--radius); padding: 8px 14px; margin-bottom: 12px; font-size: 13px; }
</style>
