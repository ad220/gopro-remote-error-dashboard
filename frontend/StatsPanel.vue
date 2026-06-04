<template>
  <div class="flex-1 overflow-auto px-7 py-6">

    <!-- Header -->
    <div class="mb-7">
      <h1 class="text-zinc-100 text-xs font-semibold tracking-widest uppercase mb-1">Statistics</h1>
      <p class="text-zinc-700 text-[11px]">Aggregated counts across all reports</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-zinc-700 text-xs">loading...</div>

    <template v-else-if="stats">

      <!-- Total -->
      <div class="mb-7 inline-block">
        <div class="text-[10px] text-zinc-600 uppercase tracking-widest mb-1">Total reports</div>
        <div class="text-4xl font-light text-zinc-100 tracking-tight">
          {{ stats.total_reports.toLocaleString() }}
        </div>
      </div>

      <!-- Stat cards grid -->
      <div class="grid grid-cols-2 gap-4 max-w-3xl xl:grid-cols-4">

        <StatCard title="By Version"    :data="stats.by_version" />
        <StatCard title="By Category"   :data="stats.by_error_category" :style-fn="categoryStyle" />
        <StatCard title="By Camera"     :data="stats.by_gopro_model" />
        <StatCard title="By Build"      :data="stats.by_build_flags" :style-fn="buildStyle" />

      </div>
    </template>

    <div v-else class="text-zinc-700 text-xs">No data available.</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'
import StatCard from './StatCard.vue'

const stats   = ref(null)
const loading = ref(false)

const CATEGORY_STYLES = {
  ERR_CAM:  'text-amber-400',
  ERR_COMM: 'text-sky-400',
  ERR_SYS:  'text-red-400',
  ERR_NULL: 'text-rose-400',
  ERR_MSG:  'text-violet-400',
  ERR_EXT:  'text-zinc-500',
}

const BUILD_STYLES = {
  ble:            'text-teal-400',
  mobile_highend: 'text-blue-400',
  mobile_lowend:  'text-orange-400',
}

function categoryStyle(key) { return CATEGORY_STYLES[key] ?? 'text-zinc-400' }
function buildStyle(key)    { return BUILD_STYLES[key]    ?? 'text-zinc-400' }

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await api.stats.get()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>
