<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, fmtInt, fmtPct, fmtTokens, qs } from '../api'
import EChart from './EChart.vue'
import SkeletonChart from './SkeletonChart.vue'

const props = defineProps({ item: Object, filters: Object })
const emit = defineEmits(['close'])
const data = ref(null)
const loading = ref(true)
const error = ref('')

// Meanings from the MaaS API reference (error-code-chart, ErrorCodeCount)
const MEANING = {
  400: '请求体参数有问题',
  401: '无权限，检查鉴权信息',
  403: '请求或生成内容不合规',
  404: '找不到资源，请求路径可能有误',
  413: '请求体过大被拒绝',
  429: '触发请求限流',
  499: '客户端主动断开或取消',
  500: '服务端未知错误',
  503: '底层无可用推理服务',
  504: '请求超时',
}
// 4xx (caller side) in distinct hues, 5xx (platform side) in reds
const COLOR = {
  400: '#f59e0b', 401: '#8b5cf6', 403: '#ec4899', 404: '#64748b', 413: '#14b8a6', 429: '#3b82f6', 499: '#94a3b8',
  500: '#ef4444', 503: '#991b1b', 504: '#f97316',
}
const colorOf = (code) => COLOR[code] || (String(code).startsWith('5') ? '#dc2626' : '#f97316')

onMounted(async () => {
  document.addEventListener('keydown', onKey)
  try {
    const q = qs({ start: props.filters.start, end: props.filters.end })
    data.value = await api(`/api/models/${encodeURIComponent(props.item.service_id)}/error-codes?` + q)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
function onKey(e) { if (e.key === 'Escape') emit('close') }

const codes = computed(() => [...(data.value?.series || [])].sort((a, b) => b.total - a.total))
const sum = (prefix) => codes.value.filter((c) => c.code.startsWith(prefix)).reduce((a, c) => a + c.total, 0)

const option = computed(() => {
  const d = data.value
  if (!d?.series.length) return null
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, confine: true },
    legend: { type: 'scroll', top: 0 },
    grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: d.axis },
    yAxis: { type: 'value', minInterval: 1 },
    series: d.series.map((s) => ({
      name: s.code, type: 'bar', stack: 'e', data: s.data, barMaxWidth: 28,
      itemStyle: { color: colorOf(s.code) }, emphasis: { focus: 'series' },
    })),
  }
})
</script>

<template>
  <div class="mask" @click.self="emit('close')">
    <aside class="drawer">
      <header>
        <div>
          <div class="title">{{ item.key }}</div>
          <div class="muted small">{{ item.generation_type }} · {{ filters.start }} 至 {{ filters.end }}</div>
        </div>
        <button class="btn" @click="emit('close')">关闭</button>
      </header>
      <section class="facts">
        <div><span>调用</span><b>{{ fmtInt(item.requests) }}</b></div>
        <div><span>错误</span><b>{{ fmtInt(item.errors) }}</b></div>
        <div><span>错误率</span><b :class="{ up: item.error_rate > 0.05 }">{{ fmtPct(item.error_rate, 2) }}</b></div>
        <div><span>Tokens</span><b>{{ fmtTokens(item.total_kt) }}</b></div>
        <div><span>平均时延</span><b>{{ (item.avg_latency_ms / 1000).toFixed(1) }} s</b></div>
        <div><span>使用的 Key</span><b>{{ item.keys }}</b></div>
      </section>

      <div>
        <h4>
          错误码时间分布
          <span v-if="data?.available" class="muted sub">按{{ data.granularity === 'hour' ? '小时' : '天' }}，北京时间</span>
        </h4>
        <template v-if="loading">
          <SkeletonChart height="260px" />
          <div class="muted small wait">MaaS 限制该接口每 20 秒只能查询 1 次，连续打开多个模型时可能需要等待。</div>
        </template>
        <div v-else-if="error" class="notice">{{ error }}</div>
        <div v-else-if="!data.available" class="notice soft">
          该模型服务已不在当前订阅列表中（已下线或已退订），MaaS 不再提供它的错误码分布。调用与错误总数仍可在上方查看。
        </div>
        <div v-else-if="!codes.length" class="empty">所选范围内没有错误</div>
        <EChart v-else :option="option" height="260px" />
      </div>

      <div v-if="!loading && data?.available && codes.length">
        <h4>
          错误码汇总
          <span class="muted sub">4xx 共 {{ fmtInt(sum('4')) }}，5xx 共 {{ fmtInt(sum('5')) }}</span>
        </h4>
        <table>
          <thead><tr><th>错误码</th><th>含义</th><th class="num">次数</th><th class="num">占错误</th></tr></thead>
          <tbody>
            <tr v-for="c in codes" :key="c.code">
              <td><span class="dot" :style="{ background: colorOf(c.code) }" />{{ c.code }}</td>
              <td class="muted">{{ MEANING[c.code] || '—' }}</td>
              <td class="num">{{ fmtInt(c.total) }}</td>
              <td class="num">{{ fmtPct(data.total ? c.total / data.total : 0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: 50; display: flex; justify-content: flex-end; }
.drawer { width: min(820px, 100vw); height: 100%; overflow-y: auto; background: var(--card); padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.title { font-size: 18px; font-weight: 700; word-break: break-all; }
.small { font-size: 12px; }
.facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.facts div { background: var(--bg); border-radius: 8px; padding: 8px 12px; display: flex; flex-direction: column; }
.facts span { color: var(--fg-3); font-size: 12px; }
.facts b { font-size: 18px; font-variant-numeric: tabular-nums; }
h4 { margin: 0 0 8px; font-size: 14px; display: flex; align-items: baseline; gap: 8px; }
.sub { font-weight: 400; font-size: 12px; }
.wait { margin-top: 6px; }
.notice { background: var(--bad-soft); color: var(--bad); border-radius: var(--radius); padding: 8px 14px; font-size: 13px; }
.notice.soft { background: var(--bg); color: var(--fg-2); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
@media (max-width: 520px) { .facts { grid-template-columns: repeat(2, 1fr); } .drawer { padding: 16px; } }
</style>
