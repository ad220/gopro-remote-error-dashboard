<template>
  <div class="flex-1 flex flex-col overflow-hidden">

    <!-- Header bar -->
    <div class="px-7 py-4 border-b border-zinc-800/60 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-4">
        <h1 class="text-zinc-100 text-xs font-semibold tracking-widest uppercase">Error Log</h1>
        <span class="text-zinc-700 text-xs">{{ total.toLocaleString() }} reports</span>
      </div>
      <button @click="fetchErrors"
              class="text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors flex items-center gap-1.5">
        <span :class="loading ? 'animate-spin inline-block' : ''">↻</span>
        refresh
      </button>
    </div>

    <!-- Filter bar -->
    <div class="px-7 py-2.5 border-b border-zinc-800/40 flex items-center gap-2.5 shrink-0 bg-zinc-950/50">
      <select v-model="filters.version" class="filter-select">
        <option value="">All versions</option>
        <option v-for="v in availableVersions" :key="v" :value="v">{{ v }}</option>
      </select>
      <select v-model="filters.error_category" class="filter-select">
        <option value="">All categories</option>
        <option v-for="cat in ERROR_CATEGORIES" :key="cat" :value="cat">{{ cat }}</option>
      </select>
      <select v-model="filters.gopro_id" class="filter-select">
        <option value="">All cameras</option>
        <option v-for="(name, idx) in GOPRO_MODELS" :key="idx" :value="String(idx)">
          {{ name }}
        </option>
      </select>
      <button v-if="hasFilters" @click="clearFilters"
              class="ml-2 text-[11px] text-zinc-600 hover:text-accent transition-colors">
        ✕ clear
      </button>
    </div>

    <!-- Table -->
    <div class="flex-1 overflow-auto">
      <div v-if="loading && !errors.length"
           class="flex items-center justify-center h-24 text-zinc-700 text-xs">
        loading...
      </div>
      <div v-else-if="!errors.length"
           class="flex items-center justify-center h-24 text-zinc-700 text-xs">
        no errors found
      </div>
      <table v-else class="w-full text-xs border-collapse">
        <thead class="sticky top-0 z-10 bg-zinc-950">
          <tr class="border-b border-zinc-800/60">
            <th v-for="col in columns" :key="col.key ?? col.label"
                class="px-4 py-2.5 text-left text-[10px] font-medium tracking-widest uppercase text-zinc-600 whitespace-nowrap"
                :class="col.sortKey ? 'cursor-pointer hover:text-zinc-400 transition-colors select-none' : ''"
                @click="col.sortKey && toggleSort(col.sortKey)">
              {{ col.label }}
              <span v-if="sortBy === col.sortKey" class="ml-0.5 opacity-50">
                {{ order === 'desc' ? '↓' : '↑' }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in errors" :key="e.id"
              class="border-b border-zinc-900/60 hover:bg-zinc-900/30 transition-colors group">
            <td class="px-4 py-2.5 text-zinc-600 group-hover:text-zinc-500 whitespace-nowrap"
                :title="e.timestamp">
              {{ relativeTime(e.timestamp) }}
            </td>
            <td class="px-4 py-2.5 text-zinc-500">{{ e.version }}</td>
            <td class="px-4 py-2.5 font-medium tracking-wide text-accent">{{ e.error_hex }}</td>
            <td class="px-4 py-2.5">
              <span class="px-1.5 py-0.5 rounded text-[10px] font-medium border"
                    :class="categoryStyle(e.error_category)">
                {{ e.error_category }}
              </span>
            </td>
            <td class="px-4 py-2.5 text-zinc-500">{{ e.gopro_model }}</td>
            <td class="px-4 py-2.5">
              <span class="px-1.5 py-0.5 rounded text-[10px] border"
                    :class="buildStyle(e.build_flags)">
                {{ e.build_flags }}
              </span>
            </td>
            <td class="px-4 py-2.5 text-zinc-600">{{ e.error_data }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="px-7 py-3 border-t border-zinc-800/60 flex items-center justify-between shrink-0">
      <span class="text-[11px] text-zinc-700">
        <template v-if="total > 0">
          {{ offset + 1 }}–{{ Math.min(offset + LIMIT, total) }}
          <span class="text-zinc-800">of</span>
          {{ total.toLocaleString() }}
        </template>
      </span>
      <div class="flex gap-1.5">
        <button :disabled="offset === 0" @click="offset = Math.max(0, offset - LIMIT)"
                class="px-3 py-1 text-[11px] rounded border border-zinc-800 text-zinc-600
                       hover:text-zinc-300 hover:border-zinc-700
                       disabled:opacity-25 disabled:cursor-not-allowed transition-colors">
          ← prev
        </button>
        <button :disabled="offset + LIMIT >= total" @click="offset += LIMIT"
                class="px-3 py-1 text-[11px] rounded border border-zinc-800 text-zinc-600
                       hover:text-zinc-300 hover:border-zinc-700
                       disabled:opacity-25 disabled:cursor-not-allowed transition-colors">
          next →
        </button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { api } from '../api.js'

// --- Constants (mirrors backend) ---

const GOPRO_MODELS = [
  'Unknown', 'HERO4 Silver', 'HERO4 Black', 'HERO5 Black', 'HERO5 Session',
  'Fusion', 'HERO6 Black', 'HERO7 Black', 'HERO7 White', 'HERO7 Silver',
  'HERO 2018', 'HERO8 Black', 'MAX', 'HERO9 Black', 'HERO10 Black',
  'HERO11 Black', 'HERO11 Black Mini', 'HERO12 Black', 'MAX2',
  'HERO13 Black', 'HERO (2024)', 'HERO Lit',
]

const ERROR_CATEGORIES = ['ERR_CAM', 'ERR_COMM', 'ERR_SYS', 'ERR_NULL', 'ERR_MSG', 'ERR_EXT']

const CATEGORY_STYLES = {
  ERR_CAM:  'bg-amber-500/10 text-amber-400 border-amber-500/20',
  ERR_COMM: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  ERR_SYS:  'bg-red-500/10 text-red-400 border-red-500/20',
  ERR_NULL: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  ERR_MSG:  'bg-violet-500/10 text-violet-400 border-violet-500/20',
  ERR_EXT:  'bg-zinc-500/10 text-zinc-500 border-zinc-500/20',
}

const BUILD_STYLES = {
  ble:            'bg-teal-500/10 text-teal-400 border-teal-500/20',
  mobile_highend: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  mobile_lowend:  'bg-orange-500/10 text-orange-400 border-orange-500/20',
}

const columns = [
  { sortKey: 'timestamp',      label: 'Time' },
  { sortKey: 'version',        label: 'Version' },
  { sortKey: null,             label: 'Error' },
  { sortKey: 'error_category', label: 'Category' },
  { sortKey: 'gopro_id',       label: 'Camera' },
  { sortKey: 'build_flags',    label: 'Build' },
  { sortKey: null,             label: 'Data' },
]

const LIMIT = 50

// --- State ---

const emit = defineEmits(['total'])

const errors           = ref([])
const total            = ref(0)
const loading          = ref(false)
const sortBy           = ref('timestamp')
const order            = ref('desc')
const offset           = ref(0)
const availableVersions = ref([])

const filters = reactive({ version: '', error_category: '', gopro_id: '' })
const hasFilters = computed(() => Object.values(filters).some(v => v !== ''))

// --- Fetch ---

async function fetchErrors() {
  loading.value = true
  try {
    const data = await api.errors.list({
      sort_by: sortBy.value,
      order:   order.value,
      offset:  offset.value,
      limit:   LIMIT,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
    })
    errors.value = data.errors
    total.value  = data.total
    emit('total', data.total)
  } catch (e) {
    console.error('Failed to fetch errors:', e)
  } finally {
    loading.value = false
  }
}

async function fetchVersions() {
  try {
    const data = await api.versions.list()
    availableVersions.value = [...new Set(data.map(v => v.version))].sort()
  } catch (e) {
    console.error('Failed to fetch versions:', e)
  }
}

// Reset to page 1 when filters or sort changes, then refetch
watch([sortBy, order, () => filters.version, () => filters.error_category, () => filters.gopro_id],
  () => { offset.value = 0 })

// Refetch whenever any query param changes
watch([sortBy, order, offset, () => filters.version, () => filters.error_category, () => filters.gopro_id],
  fetchErrors, { immediate: true })

fetchVersions()

// --- Actions ---

function toggleSort(key) {
  if (sortBy.value === key) {
    order.value = order.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = key
    order.value  = 'desc'
  }
}

function clearFilters() {
  filters.version        = ''
  filters.error_category = ''
  filters.gopro_id       = ''
}

// --- Display helpers ---

function categoryStyle(cat) {
  return CATEGORY_STYLES[cat] ?? 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20'
}

function buildStyle(flags) {
  return BUILD_STYLES[flags] ?? 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20'
}

function relativeTime(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60)   return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}
</script>

<style scoped>
@reference "../style.css";

.filter-select {
  @apply bg-zinc-900 border border-zinc-800 rounded text-[11px] text-zinc-400
         px-3 py-1.5 focus:outline-none focus:border-zinc-600 transition-colors
         hover:border-zinc-700 cursor-pointer;
}
</style>
