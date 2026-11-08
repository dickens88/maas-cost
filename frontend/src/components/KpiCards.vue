<script setup>
import { computed } from 'vue'
import { change, fmtInt, fmtPct, fmtTokens } from '../api'

const props = defineProps({ data: Object })
const c = computed(() => props.data?.current)
const p = computed(() => props.data?.previous)
const parts = computed(() => {
  if (!c.value) return []
  const t = c.value.prompt_kt + c.value.completion_kt || 1
  return [
    { name: '输入(未命中)', v: c.value.prompt_kt - c.value.cache_kt, color: 'var(--pri)' },
    { name: '缓存命中', v: c.value.cache_kt, color: 'var(--ok)' },
    { name: '输出', v: c.value.completion_kt, color: 'var(--warn)' },
  ].map((x) => ({ ...x, w: (x.v / t) * 100 }))
})
// Previous period is unavailable once it falls outside MaaS retention
const ch = (k) => (p.value ? change(c.value[k], p.value[k]) : { text: '超出保留期', cls: 'muted' })
const prevPct = (k, d) => (p.value ? fmtPct(p.value[k], d) : '—')
</script>

<template>
  <div v-if="!data" class="kpis" aria-busy="true">
    <div v-for="i in 5" :key="i" class="card kpi" :class="{ wide: i === 1 }">
      <span class="sk" style="width: 64px; height: 12px" />
      <span class="sk" style="width: 55%; height: 28px; margin: 10px 0" />
      <span class="sk" style="width: 85%; height: 12px" />
    </div>
  </div>
  <div v-else class="kpis">
    <div class="card kpi wide">
      <div class="lbl">总 Tokens</div>
      <div class="val">{{ fmtTokens(c.total_kt) }}</div>
      <div class="stack">
        <span v-for="x in parts" :key="x.name" :style="{ width: x.w + '%', background: x.color }" :title="`${x.name} ${fmtTokens(x.v)}`" />
      </div>
      <div class="sub legend">
        <span v-for="x in parts" :key="x.name"><i :style="{ background: x.color }" />{{ x.name }} {{ fmtTokens(x.v) }}</span>
      </div>
      <div class="sub">环比 <b :class="ch('total_kt').cls">{{ ch('total_kt').text }}</b></div>
    </div>
    <div class="card kpi">
      <div class="lbl">调用次数</div>
      <div class="val">{{ fmtInt(c.requests) }}</div>
      <div class="sub">环比 <b :class="ch('requests').cls">{{ ch('requests').text }}</b> · 平均 {{ fmtTokens(c.avg_kt_per_request) }}/次</div>
    </div>
    <div class="card kpi">
      <div class="lbl">缓存命中率</div>
      <div class="val">{{ fmtPct(c.cache_hit_ratio) }}</div>
      <div class="sub">上期 {{ prevPct('cache_hit_ratio') }}</div>
    </div>
    <div class="card kpi">
      <div class="lbl">错误率</div>
      <div class="val" :class="{ up: c.error_rate > 0.05 }">{{ fmtPct(c.error_rate, 2) }}</div>
      <div class="sub">{{ fmtInt(c.errors) }} 次失败 · 上期 {{ prevPct('error_rate', 2) }}</div>
    </div>
    <div class="card kpi">
      <div class="lbl">未归属用量</div>
      <div class="val" :class="{ up: data.unattributed_share > 0.05 }">{{ fmtPct(data.unattributed_share) }}</div>
      <div class="sub">在线体验 + 无标签 Key · {{ data.active_keys }} 个活跃 Key</div>
    </div>
  </div>
</template>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.kpi.wide { grid-column: span 2; }
.lbl { color: var(--fg-3); font-size: 12px; }
.val { font-size: 26px; font-weight: 700; margin: 4px 0; font-variant-numeric: tabular-nums; }
.sub { color: var(--fg-2); font-size: 12px; }
.stack { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: var(--line); margin: 6px 0; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-bottom: 2px; }
.legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; }
@media (max-width: 1100px) { .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 760px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
