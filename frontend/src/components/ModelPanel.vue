<script setup>
import { computed, ref, watch } from 'vue'
import { api, fmtInt, fmtMetric, fmtPct, fmtTokens, qs } from '../api'
import EChart from './EChart.vue'
import SkeletonChart from './SkeletonChart.vue'
import SkeletonRows from './SkeletonRows.vue'

const props = defineProps({ filters: Object, metric: String })
const models = ref([])
const cells = ref([])
const loading = ref(false)
const field = computed(() => (props.metric === 'tokens' ? 'total_kt' : 'requests'))

async function load() {
  const q = qs(props.filters)
  loading.value = true
  try {
    ;[models.value, cells.value] = await Promise.all([api('/api/usage/models?' + q), api('/api/usage-matrix?' + q)])
  } finally {
    loading.value = false
  }
}
watch(() => props.filters, load, { immediate: true, deep: true })

const active = computed(() => [...models.value].sort((a, b) => b[field.value] - a[field.value]))

const barOption = computed(() => {
  const list = active.value.slice(0, 10).reverse()
  const m = props.metric
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmtMetric(m, v) },
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: (v) => fmtMetric(m, v) } },
    yAxis: { type: 'category', data: list.map((x) => x.key) },
    series: [{ type: 'bar', data: list.map((x) => x[field.value]), barMaxWidth: 18, itemStyle: { borderRadius: [0, 4, 4, 0] } }],
  }
})

const heatOption = computed(() => {
  const f = field.value
  const byKey = {}
  for (const c of cells.value) byKey[c.name] = (byKey[c.name] || 0) + c[f]
  const keys = Object.keys(byKey).sort((a, b) => byKey[b] - byKey[a]).slice(0, 12)
  const ms = active.value.slice(0, 10).map((x) => x.key)
  const data = cells.value
    .filter((c) => keys.includes(c.name) && ms.includes(c.model) && c[f] > 0)
    .map((c) => [ms.indexOf(c.model), keys.indexOf(c.name), c[f]])
  const max = Math.max(...data.map((d) => d[2]), 1)
  const m = props.metric
  return {
    tooltip: { formatter: (p) => `${keys[p.value[1]]}<br/>${ms[p.value[0]]}：${fmtMetric(m, p.value[2])}` },
    grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: ms, axisLabel: { rotate: 30, fontSize: 11 }, splitArea: { show: true } },
    yAxis: { type: 'category', data: keys.map((k) => (k.length > 18 ? k.slice(0, 18) + '…' : k)), inverse: true, splitArea: { show: true } },
    visualMap: { min: 0, max, show: false, inRange: { color: ['#dbe6ff', '#2f6bff'] } },
    series: [{ type: 'heatmap', data, label: { show: false } }],
  }
})
</script>

<template>
  <div class="grid">
    <div class="card">
      <h3>模型分布 <span class="sub">Top 10</span></h3>
      <SkeletonChart v-if="loading" height="340px" horizontal />
      <EChart v-else-if="active.length" :option="barOption" height="340px" />
      <div v-else class="empty">没有数据</div>
    </div>
    <div class="card">
      <h3>Key × 模型 <span class="sub">颜色越深用量越大，Top 12 Key × Top 10 模型</span></h3>
      <SkeletonChart v-if="loading" height="340px" grid />
      <EChart v-else-if="cells.length" :option="heatOption" height="340px" />
      <div v-else class="empty">没有数据</div>
    </div>
  </div>
  <div class="card block scroll-x">
    <h3>模型明细</h3>
    <table>
      <thead>
        <tr>
          <th>模型</th><th>类型</th><th class="num">Tokens</th><th class="num">调用</th><th class="num">输入</th>
          <th class="num">输出</th><th class="num">缓存命中</th><th class="num">错误率</th><th class="num">平均时延</th><th class="num">Key 数</th>
        </tr>
      </thead>
      <tbody>
        <SkeletonRows v-if="loading" :rows="6" :cols="10" />
        <tr v-for="m in active" v-else :key="m.key">
          <td>{{ m.key }}</td>
          <td class="muted">{{ m.generation_type }}</td>
          <td class="num">{{ fmtTokens(m.total_kt) }}</td>
          <td class="num">{{ fmtInt(m.requests) }}</td>
          <td class="num">{{ fmtTokens(m.prompt_kt) }}</td>
          <td class="num">{{ fmtTokens(m.completion_kt) }}</td>
          <td class="num">{{ fmtPct(m.cache_hit_ratio) }}</td>
          <td class="num" :class="{ up: m.error_rate > 0.05 }">{{ fmtPct(m.error_rate, 2) }}</td>
          <td class="num">{{ (m.avg_latency_ms / 1000).toFixed(1) }} s</td>
          <td class="num">{{ m.keys }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); gap: 12px; margin-bottom: 12px; }
.block { margin-bottom: 12px; }
@media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
</style>
