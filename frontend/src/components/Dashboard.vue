<script setup>
import { computed, ref, watch } from 'vue'
import { addDays, api, bizToday, qs } from '../api'
import KpiCards from './KpiCards.vue'
import TrendChart from './TrendChart.vue'
import RankTable from './RankTable.vue'
import ModelPanel from './ModelPanel.vue'
import IpTable from './IpTable.vue'
import DetailDrawer from './DetailDrawer.vue'

const props = defineProps({ tzOffset: { type: Number, required: true } })
// Recomputed on preset click so a tab left open past midnight moves to the new day
const today = ref(bizToday(props.tzOffset))
// MaaS rejects ranges older than 30 days
const minDate = computed(() => addDays(today.value, -29))
const presets = [
  { id: 'today', name: '今天', range: (t) => [t, t] },
  { id: '7d', name: '近 7 天', range: (t) => [addDays(t, -6), t] },
  { id: '30d', name: '近 30 天', range: (t) => [addDays(t, -29), t] },
]
const preset = ref('today')
const start = ref(today.value)
const end = ref(today.value)
const metric = ref('tokens')
// Only the active view is mounted, so only it queries MaaS (the IP view costs one call per IP)
const views = [
  { id: 'keys', name: 'API Key 视图' },
  { id: 'models', name: '模型视图' },
  { id: 'ips', name: 'IP 视图' },
]
const view = ref('keys')
const model = ref('')
const overview = ref(null)
const models = ref([])
const detail = ref(null)
const error = ref('')
const loading = ref(false)

function pick(p) {
  preset.value = p.id
  today.value = bizToday(props.tzOffset)
  ;[start.value, end.value] = p.range(today.value)
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
  <nav class="tabs" role="tablist">
    <button v-for="v in views" :key="v.id" role="tab" :aria-selected="view === v.id" :class="{ on: view === v.id }" @click="view = v.id">{{ v.name }}</button>
  </nav>
  <RankTable v-if="view === 'keys'" :filters="filters" :metric="metric" @open="detail = $event" />
  <ModelPanel v-else-if="view === 'models'" :filters="filters" :metric="metric" />
  <IpTable v-else :filters="filters" :metric="metric" />
  <DetailDrawer v-if="detail" :item="detail" :filters="filters" :metric="metric" @close="detail = null" />
</template>

<style scoped>
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 10px 16px; margin-bottom: 12px; }
.grow { flex: 1; }
.tabs { display: flex; gap: 4px; box-shadow: inset 0 -1px var(--line); margin: 4px 0 12px; overflow-x: auto; overflow-y: hidden; }
.tabs button { border: 0; background: transparent; color: var(--fg-2); padding: 8px 14px; font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.tabs button:hover { color: var(--fg-1); }
.tabs button.on { color: var(--pri); border-bottom-color: var(--pri); font-weight: 600; }
.notice { background: var(--bad-soft); color: var(--bad); border-radius: var(--radius); padding: 8px 14px; margin-bottom: 12px; font-size: 13px; }
</style>
