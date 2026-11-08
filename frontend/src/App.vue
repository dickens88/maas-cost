<script setup>
import Dashboard from './components/Dashboard.vue'
</script>

<template>
  <header class="top">
    <div class="brand">MaaS Token 用量看板</div>
    <div class="hint">数据实时查询自华为云 MaaS（西南-贵阳一），最长 30 天，约 5 分钟延迟</div>
  </header>
  <main>
    <Dashboard />
  </main>
</template>

<style scoped>
.top { display: flex; align-items: center; gap: 24px; padding: 0 24px; height: 56px; background: var(--card); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 10; }
.brand { font-weight: 700; font-size: 16px; }
.hint { margin-left: auto; color: var(--fg-3); font-size: 12px; }
main { padding: 16px 24px 48px; max-width: 1600px; margin: 0 auto; }
@media (max-width: 760px) {
  .top { flex-wrap: wrap; height: auto; padding: 8px 16px; gap: 4px; }
  .hint { margin-left: 0; }
  main { padding: 12px 16px 32px; }
}
</style>
