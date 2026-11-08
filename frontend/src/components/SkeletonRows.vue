<script setup>
defineProps({ rows: { type: Number, default: 6 }, cols: { type: Number, default: 6 } })
</script>

<template>
  <tr v-for="r in rows" :key="r" aria-busy="true">
    <td v-for="c in cols" :key="c"><span class="sk" :style="{ height: '14px', width: c === 2 ? '80%' : 40 + ((r * 13 + c * 17) % 50) + '%', marginLeft: c > 2 ? 'auto' : 0 }" /></td>
  </tr>
</template>
