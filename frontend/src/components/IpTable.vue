<script setup>
import { computed, ref, watch } from 'vue'
import { api, fmtInt, fmtMetric, fmtPct, fmtTokens, qs } from '../api'
import SkeletonRows from './SkeletonRows.vue'

// One MaaS call per IP. The global list only mounts when its tab is opened; in the drawer the
// unattributed bucket (playground + unlabeled keys, ~100 IPs) still waits for a click.
const props = defineProps({ filters: Object, metric: String, label: { type: String, default: null } })
const scoped = computed(() => props.label !== null)
const lazy = props.label === ''
const open = ref(!lazy)
const rows = ref([])
const loading = ref(false)
const error = ref('')

async function load() {
  if (!open.value) return
  loading.value = true
  error.value = ''
  try {
    rows.value = await api('/api/usage/ips?' + qs({ ...props.filters, label: props.label }))
  } catch (e) {
    error.value = e.message
    rows.value = []
  } finally { loading.value = false }
}
watch(() => [props.filters, props.label], load, { immediate: true, deep: true })

function toggle() {
  open.value = !open.value
  load()
}

const field = computed(() => (props.metric === 'tokens' ? 'total_kt' : 'requests'))
const total = computed(() => rows.value.reduce((a, r) => a + (r[field.value] || 0), 0))
const TOP = 10
const all = ref(false)
const sorted = computed(() => [...rows.value].sort((a, b) => (b[field.value] || 0) - (a[field.value] || 0)))
const shown = computed(() => (all.value ? sorted.value : sorted.value.slice(0, TOP)))
const cols = computed(() => (scoped.value ? 6 : 9))
</script>

<template>
  <div :class="scoped ? 'inline' : 'card block'">
    <component :is="scoped ? 'h4' : 'h3'">
      {{ scoped ? '来源 IP' : '来源 IP 排行' }}
      <span v-if="lazy || !scoped" class="sub">按客户端源 IP 统计；每个 IP 单独查询一次 MaaS，首次加载约需 30–60 秒</span>
      <span class="grow" />
      <button v-if="lazy" class="btn" @click="toggle">{{ open ? '收起' : '展开' }}</button>
    </component>
    <div v-if="error" class="notice">{{ error }}</div>
    <div v-if="open" class="scroll-x">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>IP</th>
            <th class="num">{{ metric === 'tokens' ? 'Tokens' : '调用次数' }}</th>
            <th>占比</th>
            <th class="num">调用</th>
            <template v-if="!scoped">
              <th class="num">输入</th>
              <th class="num">输出</th>
              <th class="num">错误率</th>
            </template>
            <th>主力模型</th>
          </tr>
        </thead>
        <tbody>
          <SkeletonRows v-if="loading" :rows="scoped ? 3 : 8" :cols="cols" />
          <tr v-for="(r, i) in shown" v-else :key="r.key">
            <td class="muted">{{ i + 1 }}</td>
            <td><code>{{ r.key }}</code></td>
            <td class="num strong">{{ fmtMetric(metric, r[field]) }}</td>
            <td class="share"><div class="bar"><span :style="{ width: (total ? (r[field] / total) * 100 : 0) + '%' }" /></div>{{ fmtPct(total ? r[field] / total : 0) }}</td>
            <td class="num">{{ fmtInt(r.requests) }}</td>
            <template v-if="!scoped">
              <td class="num">{{ fmtTokens(r.prompt_kt) }}</td>
              <td class="num">{{ fmtTokens(r.completion_kt) }}</td>
              <td class="num err" :class="{ up: r.error_rate > 0.05 }">
                {{ fmtPct(r.error_rate, 2) }}
                <div v-if="r.top_error_model" class="err-src muted" :title="`错误最多的模型：${r.top_error_model}，${r.top_error_count} 次`">{{ r.top_error_model }} {{ fmtInt(r.top_error_count) }} 次</div>
              </td>
            </template>
            <td>{{ r.top_model }}<span v-if="r.models > 1" class="muted"> +{{ r.models - 1 }}</span></td>
          </tr>
          <tr v-if="!loading && !error && !shown.length"><td :colspan="cols" class="empty">没有数据</td></tr>
        </tbody>
      </table>
      <button v-if="!loading && sorted.length > TOP" class="btn more" @click="all = !all">
        {{ all ? `只看前 ${TOP} 个` : `显示全部 ${sorted.length} 个 IP` }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.block { margin-bottom: 12px; }
h3, h4 { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
h4 { margin: 0 0 8px; font-size: 14px; }
.grow { flex: 1; }
.more { margin-top: 8px; }
code { font-size: 12px; }
.strong { font-weight: 600; }
.err { white-space: nowrap; }
.err-src { font-size: 11px; max-width: 180px; overflow: hidden; text-overflow: ellipsis; margin-left: auto; }
.share { min-width: 110px; white-space: nowrap; font-size: 12px; color: var(--fg-2); }
.bar { display: inline-block; width: 56px; height: 6px; background: var(--line); border-radius: 3px; margin-right: 6px; vertical-align: middle; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--pri); }
.notice { background: var(--bad-soft); color: var(--bad); border-radius: var(--radius); padding: 8px 14px; margin-bottom: 8px; font-size: 13px; }
</style>
