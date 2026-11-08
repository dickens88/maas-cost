<script setup>
const props = defineProps({
  height: { type: String, default: '320px' },
  horizontal: Boolean,
  grid: Boolean,
  bars: { type: Number, default: 12 },
})
// Fixed pseudo-random sizes so the placeholder does not jump between renders
const sizes = Array.from({ length: props.bars }, (_, i) => 35 + ((i * 37) % 55))
</script>

<template>
  <div v-if="grid" class="skg" :style="{ height }" aria-busy="true" aria-label="加载中">
    <span v-for="i in 80" :key="i" class="sk" :style="{ opacity: 0.35 + ((i * 29) % 65) / 100 }" />
  </div>
  <div v-else class="skc" :class="{ horizontal }" :style="{ height }" aria-busy="true" aria-label="加载中">
    <span v-for="(s, i) in sizes" :key="i" class="sk" :style="horizontal ? { width: s + '%' } : { height: s + '%' }" />
  </div>
</template>

<style scoped>
.skc { display: flex; align-items: flex-end; gap: 10px; padding: 24px 8px 8px 48px; border-bottom: 1px solid var(--line); }
.skc .sk { flex: 1; border-radius: 4px 4px 0 0; }
.skc.horizontal { flex-direction: column; align-items: flex-start; justify-content: space-around; padding: 8px 8px 8px 120px; border-bottom: 0; border-left: 1px solid var(--line); }
.skc.horizontal .sk { flex: 0 0 14px; border-radius: 0 4px 4px 0; }
.skg { display: grid; grid-template-columns: repeat(10, 1fr); grid-template-rows: repeat(8, 1fr); gap: 3px; padding: 8px 8px 48px 120px; }
.skg .sk { border-radius: 2px; }
</style>
