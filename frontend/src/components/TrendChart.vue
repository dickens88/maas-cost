<script setup>
import { computed, ref, watch } from 'vue'
import { api, fmtMetric, qs } from '../api'
import EChart from './EChart.vue'
import SkeletonChart from './SkeletonChart.vue'

const props = defineProps({ filters: Object, metric: String, label: String, compact: Boolean, drill: Boolean })
const emit = defineEmits(['drill'])
const gran = ref('day')
const data = ref(null)
const loading = ref(false)
const error = ref('')
const days = computed(() => (new Date(props.filters.end) - new Date(props.filters.start)) / 86400000 + 1)
const hourOk = computed(() => days.value <= 2)

watch(days, (d) => { gran.value = d <= 2 ? 'hour' : gran.value === 'hour' ? 'day' : gran.value }, { immediate: true })

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api('/api/trend?' + qs({ ...props.filters, label: props.label ?? null, granularity: gran.value, metric: props.metric }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
watch(() => [props.filters, props.metric, props.label, gran.value], load, { immediate: true, deep: true })

// The "other" bucket is not a model, keep its default legend toggle
function onDrill(name) {
  const s = data.value?.series.find((x) => x.name === name)
  if (props.drill && s && !s.other) emit('drill', name)
}

const option = computed(() => {
  if (!data.value) return null
  const m = props.metric
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, confine: true, valueFormatter: (v) => fmtMetric(m, v) },
    legend: { type: 'scroll', top: 0 },
    grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: data.value.axis },
    yAxis: { type: 'value', axisLabel: { formatter: (v) => fmtMetric(m, v) } },
    series: data.value.series.map((s) => ({ name: s.name, type: 'bar', stack: 't', data: s.data, emphasis: { focus: 'series' }, barMaxWidth: 36 })),
  }
})
</script>

<template>
  <div class="card block" :class="{ flat: compact }">
    <h3>
      趋势
      <span class="sub">按模型堆叠，Top 8 + 其他<template v-if="drill">；点击模型下钻</template></span>
      <span class="grow" />
      <div class="seg">
        <button :disabled="!hourOk" :class="{ on: gran === 'hour' }" @click="gran = 'hour'" :title="hourOk ? '' : '小时粒度最多 2 天'">小时</button>
        <button :class="{ on: gran === 'day' }" @click="gran = 'day'">天</button>
        <button :class="{ on: gran === 'week' }" @click="gran = 'week'">周</button>
      </div>
    </h3>
    <SkeletonChart v-if="loading" :height="compact ? '240px' : '320px'" />
    <div v-else-if="error" class="empty">{{ error }}</div>
    <EChart v-else-if="option && data.series.length" :option="option" :height="compact ? '240px' : '320px'"
      @click="onDrill($event.seriesName)" @legend="onDrill($event.name)" />
    <div v-else class="empty">所选范围内没有数据</div>
  </div>
</template>

<style scoped>
.block { margin-bottom: 12px; }
.flat { border: 0; padding: 0; }
.seg button:disabled { opacity: 0.4; cursor: not-allowed; }
h3 { flex-wrap: wrap; }
</style>
