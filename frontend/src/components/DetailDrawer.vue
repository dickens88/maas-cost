<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { api, fmtInt, fmtPct, fmtTokens, qs } from '../api'
import TrendChart from './TrendChart.vue'
import SkeletonRows from './SkeletonRows.vue'

const props = defineProps({ item: Object, filters: Object, metric: String })
const emit = defineEmits(['close'])
const models = ref([])
const loadingModels = ref(true)
const scoped = computed(() => ({ start: props.filters.start, end: props.filters.end }))

onMounted(async () => {
  models.value = (await api('/api/usage/models?' + qs({ ...scoped.value, label: props.item.key })))
  loadingModels.value = false
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
function onKey(e) { if (e.key === 'Escape') emit('close') }
</script>

<template>
  <div class="mask" @click.self="emit('close')">
    <aside class="drawer">
      <header>
        <div>
          <div class="title">{{ item.name }}</div>
          <div class="muted small">{{ item.description }}</div>
        </div>
        <button class="btn" @click="emit('close')">关闭</button>
      </header>
      <section class="facts">
        <div><span>输入 / 输出</span><b>{{ fmtTokens(item.prompt_kt) }} / {{ fmtTokens(item.completion_kt) }}</b></div>
        <div><span>Tokens</span><b>{{ fmtTokens(item.total_kt) }}</b></div>
        <div><span>调用</span><b>{{ fmtInt(item.requests) }}</b></div>
        <div><span>缓存命中</span><b>{{ fmtPct(item.cache_hit_ratio) }}</b></div>
        <div><span>错误率</span><b>{{ fmtPct(item.error_rate, 2) }}</b></div>
        <div><span>输出/输入</span><b>{{ fmtPct(item.output_input_ratio) }}</b></div>
      </section>
      <section class="meta">
        <div v-if="item.key_ids && item.key_ids.length"><span class="muted">Key ID</span><code>{{ item.key_ids.join(', ') }}</code></div>
        <div v-if="item.open_access"><span class="muted">访问控制</span><span class="tag warn">未配置 IP 白名单</span></div>
        <div v-if="item.unlabeled_keys && item.unlabeled_keys.length">
          <span class="muted">说明</span>以下 Key 未设置标签，MaaS 无法单独统计，用量都计入本桶：{{ item.unlabeled_keys.join('、') }}
        </div>
      </section>
      <TrendChart :filters="scoped" :metric="metric" :label="item.key" compact />
      <h4>模型拆分</h4>
      <table>
        <thead><tr><th>模型</th><th class="num">Tokens</th><th class="num">调用</th><th class="num">缓存命中</th><th class="num">错误率</th></tr></thead>
        <tbody>
          <SkeletonRows v-if="loadingModels" :rows="4" :cols="5" />
          <tr v-for="m in models" v-else :key="m.key">
            <td>{{ m.key }}</td>
            <td class="num">{{ fmtTokens(m.total_kt) }}</td>
            <td class="num">{{ fmtInt(m.requests) }}</td>
            <td class="num">{{ fmtPct(m.cache_hit_ratio) }}</td>
            <td class="num">{{ fmtPct(m.error_rate, 2) }}</td>
          </tr>
          <tr v-if="!loadingModels && !models.length"><td colspan="5" class="empty">没有数据</td></tr>
        </tbody>
      </table>
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
.meta { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.meta span.muted { display: inline-block; width: 72px; }
code { font-size: 12px; word-break: break-all; }
h4 { margin: 0; font-size: 14px; }
@media (max-width: 520px) { .facts { grid-template-columns: repeat(2, 1fr); } .drawer { padding: 16px; } }
</style>
