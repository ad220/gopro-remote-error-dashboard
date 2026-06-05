<template>
  <div class="flex-1 overflow-auto px-7 py-6">

    <!-- Header -->
    <div class="mb-5">
      <h1 class="text-zinc-100 text-xs font-semibold tracking-widest uppercase mb-1">Statistics</h1>
      <p class="text-zinc-500 text-[11px]">Aggregated counts across all reports</p>
    </div>

    <!-- Filter bar -->
    <div class="flex items-center gap-2.5 mb-7">
      <select v-model="filters.version" class="filter-select">
        <option value="">All versions</option>
        <option v-for="v in availableVersions" :key="v" :value="v">{{ v }}</option>
      </select>
      <select v-model="filters.error_category" class="filter-select">
        <option value="">All categories</option>
        <option v-for="cat in ERROR_CATEGORIES" :key="cat" :value="cat">{{ cat }}</option>
      </select>
      <button v-if="hasFilters" @click="clearFilters"
              class="text-[11px] text-zinc-500 hover:text-accent transition-colors ml-1">
        ✕ clear
      </button>
      <span class="ml-auto text-[11px] text-zinc-500">
        {{ stats ? stats.total_reports.toLocaleString() + ' reports' : '' }}
      </span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-zinc-500 text-xs">loading...</div>

    <template v-else-if="stats">

      <!-- Total -->
      <div class="mb-7">
        <div class="text-[10px] text-zinc-500 uppercase tracking-widest mb-1">
          Total{{ hasFilters ? ' (filtered)' : '' }}
        </div>
        <div class="text-4xl font-light text-zinc-100 tracking-tight">
          {{ stats.total_reports.toLocaleString() }}
        </div>
      </div>

      <!-- Stat cards -->
      <div class="grid grid-cols-2 gap-4 max-w-3xl xl:grid-cols-4">
        <StatCard title="By Version"    :data="stats.by_version" />
        <StatCard title="By Category"   :data="stats.by_error_category" :style-fn="categoryStyle" />
        <StatCard title="By Camera"     :data="stats.by_gopro_model" />
        <StatCard title="By Build"      :data="stats.by_build_flags"    :style-fn="buildStyle" />
      </div>

    </template>

    <div v-else class="text-zinc-500 text-xs">No data available.</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { api } from '../api.js'
import StatCard from './StatCard.vue'

const ERROR_CATEGORIES = ['ERR_CAM', 'ERR_COMM', 'ERR_SYS', 'ERR_NULL', 'ERR_MSG', 'ERR_EXT']

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

const stats            = ref(null)
const loading          = ref(false)
const availableVersions = ref([])

const filters   = reactive({ version: '', error_category: '' })
const hasFilters = computed(() => Object.values(filters).some(v => v !== ''))

function categoryStyle(key) { return CATEGORY_STYLES[key] ?? 'text-zinc-400' }
function buildStyle(key)    { return BUILD_STYLES[key]    ?? 'text-zinc-400' }

function clearFilters() {
  filters.version        = ''
  filters.error_category = ''
}

async function fetchStats() {
  loading.value = true
  try {
    stats.value = await api.stats.get(
      Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
    )
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function fetchVersions() {
  try {
    const data = await api.versions.list()
    availableVersions.value = [...new Set(data.map(v => v.version))].sort()
  } catch (e) {
    console.error(e)
  }
}

watch(filters, fetchStats, { deep: true })
onMounted(() => { fetchStats(); fetchVersions() })
</script>

<style scoped>
@reference "../style.css";

.filter-select {
  @apply bg-zinc-900 border border-zinc-800 rounded text-[11px] text-zinc-400
         px-3 py-1.5 focus:outline-none focus:border-zinc-600 transition-colors
         hover:border-zinc-700 cursor-pointer;
}
</style>
