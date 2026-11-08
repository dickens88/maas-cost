<script setup>
import { computed, ref, watch } from 'vue'
import { api, fmtInt, fmtMetric, fmtPct, fmtTokens, qs } from '../api'
import SkeletonRows from './SkeletonRows.vue'

const props = defineProps({ filters: Object, metric: String })
const emit = defineEmits(['open'])
const rows = ref([])
const loading = ref(false)
const showIdle = ref(false)
const sortBy = ref(null)
const desc = ref(true)

async function load() {
  loading.value = true
  try { rows.value = await api('/api/usage/keys?' + qs(props.filters)) } finally { loading.value = false }
}
watch(() => props.filters, load, { immediate: true, deep: true })

const field = computed(() => (props.metric === 'tokens' ? 'total_kt' : 'requests'))
const total = computed(() => rows.value.reduce((a, r) => a + (r[field.value] || 0), 0))
const idleCount = computed(() => rows.value.filter((r) => !r.requests).length)

const shown = computed(() => {
  const list = rows.value.filter((r) => showIdle.value || r.requests > 0)
  const k = sortBy.value || field.value
  return [...list].sort((a, b) => (desc.value ? 1 : -1) * ((b[k] ?? 0) - (a[k] ?? 0)))
})

function sort(k) {
  if (sortBy.value === k) desc.value = !desc.value
  else { sortBy.value = k; desc.value = true }
}
</script>

<template>
  <div class="card block">
    <h3>
      API Key 排行
      <span class="sub">点击行查看该 Key 的趋势与模型拆分</span>
      <span class="grow" />
      <label class="muted idle"><input type="checkbox" v-model="showIdle" /> 显示零调用 Key（{{ idleCount }}）</label>
    </h3>
    <div class="scroll-x">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>API Key 标签</th>
            <th class="num sortable" @click="sort(field)">{{ metric === 'tokens' ? 'Tokens' : '调用次数' }}</th>
            <th>占比</th>
            <th class="num sortable" @click="sort('requests')">调用</th>
            <th class="num sortable" @click="sort('prompt_kt')">输入</th>
            <th class="num sortable" @click="sort('completion_kt')">输出</th>
            <th class="num sortable" @click="sort('cache_hit_ratio')">缓存命中</th>
            <th class="num sortable" @click="sort('error_rate')">错误率</th>
            <th class="num sortable" @click="sort('avg_kt_per_request')">平均/次</th>
            <th>主力模型</th>
          </tr>
        </thead>
        <tbody>
          <SkeletonRows v-if="loading" :rows="8" :cols="11" />
          <tr v-for="(r, i) in shown" v-else :key="r.key" class="click" @click="emit('open', r)">
            <td class="muted">{{ i + 1 }}</td>
            <td class="name">
              <span>{{ r.name }}</span>
              <span v-if="r.open_access" class="tag warn" title="未配置 IP 白名单，任意来源都可调用">无 IP 白名单</span>
              <span v-if="r.unlabeled_keys.length" class="tag bad" :title="r.unlabeled_keys.join('\n')">含 {{ r.unlabeled_keys.length }} 个无标签 Key</span>
              <div v-if="r.description" class="desc muted">{{ r.description }}</div>
            </td>
            <td class="num strong">{{ fmtMetric(metric, r[field]) }}</td>
            <td class="share"><div class="bar"><span :style="{ width: (total ? (r[field] / total) * 100 : 0) + '%' }" /></div>{{ fmtPct(total ? r[field] / total : 0) }}</td>
            <td class="num">{{ fmtInt(r.requests) }}</td>
            <td class="num">{{ fmtTokens(r.prompt_kt) }}</td>
            <td class="num">{{ fmtTokens(r.completion_kt) }}</td>
            <td class="num">{{ fmtPct(r.cache_hit_ratio) }}</td>
            <td class="num" :class="{ up: r.error_rate > 0.05 }">{{ fmtPct(r.error_rate, 2) }}</td>
            <td class="num">{{ fmtTokens(r.avg_kt_per_request) }}</td>
            <td>{{ r.top_model || '—' }}<span v-if="r.models > 1" class="muted"> +{{ r.models - 1 }}</span></td>
          </tr>
          <tr v-if="!loading && !shown.length"><td colspan="11" class="empty">所选范围内没有数据</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.block { margin-bottom: 12px; }
h3 { flex-wrap: wrap; }
.idle { font-size: 12px; display: flex; align-items: center; gap: 4px; font-weight: 400; }
.name { min-width: 200px; }
.desc { font-size: 11px; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.strong { font-weight: 600; }
.share { min-width: 110px; white-space: nowrap; font-size: 12px; color: var(--fg-2); }
.bar { display: inline-block; width: 56px; height: 6px; background: var(--line); border-radius: 3px; margin-right: 6px; vertical-align: middle; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--pri); }
</style>
