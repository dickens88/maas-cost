<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ option: Object, height: { type: String, default: '300px' } })
const emit = defineEmits(['click', 'legend'])
const el = ref(null)
let chart
let ro
const dark = window.matchMedia('(prefers-color-scheme: dark)')

function render() {
  chart?.dispose()
  chart = echarts.init(el.value, dark.matches ? 'dark' : null)
  chart.on('click', (p) => emit('click', p))
  chart.on('legendselectchanged', (p) => emit('legend', p))
  if (props.option) chart.setOption({ backgroundColor: 'transparent', ...props.option })
}

onMounted(() => {
  render()
  ro = new ResizeObserver(() => chart?.resize())
  ro.observe(el.value)
  dark.addEventListener('change', render)
})
onBeforeUnmount(() => {
  ro?.disconnect()
  dark.removeEventListener('change', render)
  chart?.dispose()
})
watch(() => props.option, (o) => o && chart?.setOption({ backgroundColor: 'transparent', ...o }, true), { deep: true })
</script>

<template>
  <div ref="el" :style="{ height, width: '100%' }" />
</template>
