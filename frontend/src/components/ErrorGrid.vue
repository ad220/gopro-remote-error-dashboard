<template>
  <div class="flex-1 flex flex-col overflow-hidden">

    <!-- Header bar -->
    <div class="px-7 py-4 border-b border-zinc-800/60 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-4">
        <h1 class="text-zinc-100 text-xs font-semibold tracking-widest uppercase">Error Log</h1>
        <span class="text-zinc-500 text-xs">{{ total.toLocaleString() }} reports</span>
      </div>
      <button @click="fetchErrors"
              class="text-[11px] text-zinc-500 hover:text-zinc-400 transition-colors flex items-center gap-1.5">
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
      <select v-model="filters.gopro_id" class="filter-select">
        <option value="">All cameras</option>
        <option v-for="(name, idx) in GOPRO_MODELS" :key="idx" :value="String(idx)">
          {{ name }}
        </option>
      </select>
      <select v-model="filters.error_category" class="filter-select">
        <option value="">All categories</option>
        <option v-for="[key, name] in Object.entries(CATEGORY_MAP)" :key="key" :value="Number(key)">{{ name }}</option>
      </select>
      <select v-model="filters.error_subtype" class="filter-select"
              :disabled="!filters.error_category">
        <option value="">All subtypes</option>
        <option v-for="opt in subtypeOptions" :key="opt.value" :value="String(opt.value)">
          {{ opt.label }}
        </option>
      </select>
      <button v-if="hasFilters" @click="clearFilters"
              class="ml-2 text-[11px] text-zinc-500 hover:text-accent transition-colors">
        ✕ clear
      </button>
    </div>

    <div v-if="activeBatch" class="px-7 py-2 bg-zinc-800/60 border-b border-zinc-700/60 flex items-center justify-between shrink-0">
      <span class="text-[11px] text-zinc-400">
        {{ total }} error{{ total !== 1 ? 's' : '' }} in this batch
      </span>
      <button @click="clearBatch"
              class="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors">
        ← back to all
      </button>
    </div>

    <!-- Table -->
    <div class="flex-1 overflow-auto">
      <div v-if="loading && !errors.length"
           class="flex items-center justify-center h-24 text-zinc-500 text-xs">
        loading...
      </div>
      <div v-else-if="!errors.length"
           class="flex items-center justify-center h-24 text-zinc-500 text-xs">
        no errors found
      </div>
      <table v-else class="w-auto text-xs border-collapse table-auto">
        <thead class="sticky top-0 z-10 bg-zinc-950">
          <tr class="border-b border-zinc-800/60">
            <th v-for="col in columns" :key="col.key ?? col.label"
                class="px-8 py-2.5 text-left text-[10px] font-medium tracking-widest uppercase text-zinc-500 whitespace-nowrap"
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
              @click="onRowClick(e)"
              class="border-b border-zinc-900/80 hover:bg-zinc-900/80 transition-colors group text-slate-400 hover:text-slate-300 cursor-pointer"
              :class="activeBatch?.focusedId === e.id ? 'bg-zinc-700/30 !text-zinc-200' : ''">
            <td class="px-8 py-2.5 whitespace-nowrap"
                :title="e.timestamp">
              {{ relativeTime(e.timestamp) }}
            </td>
            <td class="px-8 py-2.5">{{ e.version }}</td>
            <td class="px-8 py-2.5">{{ GOPRO_MODELS[e.gopro_id] ?? `id:${e.gopro_id}` }}</td>
            <td class="px-8 py-2.5">
              <span class="px-1.5 py-0.5 rounded text-[10px] font-medium border"
                    :class="categoryStyle(e.error_category)">
                {{ CATEGORY_MAP[e.error_category] ?? `0x${e.error_category.toString(16).toUpperCase()}` }}
              </span>
            </td>
            <td class="px-8 py-2.5">
              <span v-if="e.error_subtype !== null"
                    class="px-1.5 py-0.5 rounded text-[10px] border"
                    :class="subtypeStyle(e.error_category, e.error_subtype)">
                {{ subtypeLabel(e.error_category, e.error_subtype) }}
              </span>
              <span v-else></span>
            </td>
            <td class="px-8 py-2.5 tabular-nums">
              <span v-if="e.error_index !== null">{{ e.error_index }}</span>
              <span v-else></span>
            </td>
            <td class="px-8 py-2.5">
              <span class="px-1.5 py-0.5 rounded text-[10px] border"
                    :class="buildStyle(e.build_flags)">
                {{ BUILD_MAP[e.build_flags] ?? `0b${e.build_flags.toString(2)}` }}
              </span>
            </td>
            <td class="px-8 py-2.5 font-medium tracking-wide text-zinc-300">{{ e.error_hex }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="px-7 py-3 border-t border-zinc-800/60 flex items-center justify-between shrink-0">
      <span class="text-[11px] text-zinc-500">
        <template v-if="total > 0">
          {{ offset + 1 }}-{{ Math.min(offset + LIMIT, total) }}
          <span class="text-zinc-500">of</span>
          {{ total.toLocaleString() }}
        </template>
      </span>
      <div class="flex gap-1.5">
        <button :disabled="offset === 0" @click="offset = Math.max(0, offset - LIMIT)"
                class="px-3 py-1 text-[11px] rounded border border-zinc-800 text-zinc-500
                       hover:text-zinc-300 hover:border-zinc-700
                       disabled:opacity-25 disabled:cursor-not-allowed transition-colors">
          ← prev
        </button>
        <button :disabled="offset + LIMIT >= total" @click="offset += LIMIT"
                class="px-3 py-1 text-[11px] rounded border border-zinc-800 text-zinc-500
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

const CATEGORY_MAP = {
  0x80: 'CAM',
  0x40: 'MSG',
  0x30: 'EXT',
  0x20: 'COMM',
  0x10: 'SYS',
  0x00: 'NULL',
}

const CATEGORY_STYLES = {
  CAM:  'bg-amber-500/10 text-amber-400 border-amber-500/20',
  COMM: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  SYS:  'bg-red-500/10 text-red-400 border-red-500/20',
  NULL: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  MSG:  'bg-violet-500/10 text-violet-400 border-violet-500/20',
  EXT:  'bg-zinc-500/10 text-zinc-500 border-zinc-500/20',
}

const SUBTYPE_MAP = {
  0x80: [
    { label: 'ID',    value: 0x00 },
    { label: 'VAL',   value: 0x10 },
    { label: 'NULL',  value: 0x20 },
    { label: 'AVAIL', value: 0x30 },
  ],
  0x40: [
    { label: 'STATUS', value: 0x00 },
    { label: 'QUERY',  value: 0x10 },
    { label: 'STRUCT', value: 0x20 },
  ],
  0x20: [
    { label: 'STATUS', value: 0x00 },
    { label: 'CONN',   value: 0x10 },
    { label: 'NULLQ',  value: 0x40 },
    { label: 'BADSCD', value: 0x80 },
    { label: 'WRITE',  value: 0x90 },
    { label: 'TO',     value: 0xA0 },
    { label: 'API',    value: 0xF0 },
  ],
}

const SUBTYPE_STYLES = {
  0x80: {
    ID:     'bg-yellow-400/10   text-yellow-400   border-yellow-400/20',
    VAL:    'bg-orange-500/10   text-orange-400   border-orange-500/20',
    NULL:   'bg-red-500/10      text-red-400      border-red-500/20',
    AVAIL:  'bg-amber-500/10    text-amber-500    border-amber-500/20',
  },
  0x40: {
    STATUS: 'bg-purple-500/10   text-purple-400   border-purple-500/20',
    QUERY:  'bg-pink-500/10     text-pink-400     border-pink-500/20',
    STRUCT: 'bg-fuchsia-500/10  text-fuchsia-400  border-fuchsia-500/20',
  },
  0x20: {
    STATUS: 'bg-cyan-500/10     text-cyan-400     border-cyan-500/20',
    CONN:   'bg-sky-500/10      text-sky-400      border-sky-500/20',
    NULLQ:  'bg-blue-500/10     text-blue-400     border-blue-500/20',
    BADSCD: 'bg-indigo-500/10   text-indigo-400   border-indigo-500/20',
    WRITE:  'bg-teal-500/10     text-teal-400     border-teal-500/20',
    TO:     'bg-emerald-500/10  text-emerald-400  border-emerald-500/20',
    API:    'bg-green-500/10    text-green-400    border-green-500/20',
  },
}

const BUILD_MAP = {
  0: 'ble',
  1: 'mobile_highend',
  3: 'mobile_lowend',
}

const BUILD_STYLES = {
  ble:            'bg-teal-500/10 text-teal-400 border-teal-500/20',
  mobile_highend: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  mobile_lowend:  'bg-orange-500/10 text-orange-400 border-orange-500/20',
}

const columns = [
  { sortKey: 'timestamp',      label: 'Time' },
  { sortKey: 'version',        label: 'Version' },
  { sortKey: 'gopro_id',       label: 'Camera' },
  { sortKey: 'error_category', label: 'Category' },
  { sortKey: 'error_subtype',  label: 'Subtype' },
  { sortKey: 'error_index',    label: 'Index' },
  { sortKey: 'build_flags',    label: 'Build' },
  { sortKey: null,             label: 'Error' },
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

const filters = reactive({ version: '', error_category: '', error_subtype: '', gopro_id: '' })
const hasFilters = computed(() => Object.values(filters).some(v => v !== ''))
const activeBatch = ref(null) // { batchId, focusedId } | null

watch(() => filters.error_category, () => { filters.error_subtype = '' })

// --- Fetch ---

async function fetchErrors() {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
    if (params.error_category !== undefined) {
      params.error_category = `0x${Number(params.error_category).toString(16).toUpperCase()}`
    }
    if (activeBatch.value) params.batch_id = activeBatch.value.batchId

    const data = await api.errors.list({
      sort_by: sortBy.value,
      order: order.value,
      offset: offset.value,
      limit: LIMIT, ...params 
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
watch(
  [sortBy, order, activeBatch, () => filters.version, () => filters.error_category, () => filters.gopro_id],
  () => { offset.value = 0 }
)

// Refetch whenever any query param changes
watch(
  [sortBy, order, offset, activeBatch, () => filters.version, () => filters.error_category, () => filters.gopro_id],
  fetchErrors, { immediate: true }
)

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
  filters.error_subtype  = ''
  filters.gopro_id       = ''
}

function onRowClick(e) {
  offset.value = 0
  activeBatch.value = { batchId: e.batch_id, focusedId: e.id }
}

function clearBatch() {
  activeBatch.value = null
  offset.value = 0
}

// --- Display helpers ---

const defaultTagStyle = 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20'
const subtypeOptions = computed(() => SUBTYPE_MAP[filters.error_category] ?? [])

function subtypeLabel(cat, sub) {
  const entry = (SUBTYPE_MAP[cat] ?? []).find(e => e.value === sub)
  return entry?.label ?? `0x${sub.toString(16).toUpperCase()}`
}

function categoryStyle(cat)     { return CATEGORY_STYLES[CATEGORY_MAP[cat]] ?? defaultTagStyle }
function subtypeStyle(cat, sub) { return SUBTYPE_STYLES[cat]?.[subtypeLabel(cat, sub)] ?? defaultTagStyle }
function buildStyle(flags)      { return BUILD_STYLES[BUILD_MAP[flags]] ?? defaultTagStyle }

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

.filter-select:disabled {
  @apply opacity-30 cursor-not-allowed pointer-events-none;
}
</style>
