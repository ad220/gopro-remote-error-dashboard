<template>
  <div class="flex-1 overflow-auto px-7 py-6 max-w-2xl">

    <!-- Header -->
    <div class="mb-7">
      <h1 class="text-zinc-100 text-xs font-semibold tracking-widest uppercase mb-1">API Keys</h1>
      <p class="text-zinc-700 text-[11px]">One key per app version. Keys are shown only at creation.</p>
    </div>

    <!-- Create form -->
    <div class="mb-8 bg-zinc-900/50 border border-zinc-800/60 rounded-lg p-5">
      <div class="text-[10px] text-zinc-600 uppercase tracking-widest mb-3">New key</div>
      <div class="flex gap-2 items-start">
        <input
          v-model="newVersion"
          placeholder="e.g. v4.2"
          @keydown.enter="create"
          class="bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-300
                 px-3 py-2 w-40 focus:outline-none focus:border-zinc-600
                 placeholder-zinc-700 transition-colors"
        />
        <button @click="create" :disabled="!newVersion.trim() || creating"
                class="px-4 py-2 rounded text-xs font-medium transition-all
                       bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100
                       disabled:opacity-30 disabled:cursor-not-allowed">
          {{ creating ? 'creating...' : 'Generate' }}
        </button>
      </div>

      <!-- New key display — shown once -->
      <div v-if="newKey" class="mt-4">
        <div class="text-[10px] text-zinc-600 uppercase tracking-widest mb-1.5">
          Key generated — copy it now, it won't be shown again
        </div>
        <div class="flex items-center gap-2">
          <code class="flex-1 bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-[11px]"
                style="color: #E8430A; word-break: break-all">
            {{ newKey }}
          </code>
          <button @click="copyKey"
                  class="px-3 py-2 rounded border border-zinc-800 text-[11px] text-zinc-500
                         hover:text-zinc-300 hover:border-zinc-600 transition-colors shrink-0">
            {{ copied ? '✓ copied' : 'copy' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 text-xs text-rose-400">{{ error }}</div>

    <!-- Keys table -->
    <div class="border border-zinc-800/60 rounded-lg overflow-hidden">
      <div class="px-4 py-2.5 bg-zinc-900/50 border-b border-zinc-800/60">
        <span class="text-[10px] text-zinc-600 uppercase tracking-widest">Active keys</span>
      </div>

      <div v-if="loading" class="px-4 py-6 text-xs text-zinc-700">loading...</div>

      <div v-else-if="!versions.length" class="px-4 py-6 text-xs text-zinc-700">No keys yet.</div>

      <table v-else class="w-full text-xs">
        <thead>
          <tr class="border-b border-zinc-800/40">
            <th class="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-600 tracking-widest uppercase">Version</th>
            <th class="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-600 tracking-widest uppercase">Created</th>
            <th class="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-600 tracking-widest uppercase">Status</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in versions" :key="v.id"
              class="border-b border-zinc-900/60 last:border-0"
              :class="!v.active ? 'opacity-40' : ''">
            <td class="px-4 py-3 text-zinc-300">{{ v.version }}</td>
            <td class="px-4 py-3 text-zinc-600">{{ formatDate(v.created_at) }}</td>
            <td class="px-4 py-3">
              <span class="text-[10px] px-1.5 py-0.5 rounded border"
                    :class="v.active
                      ? 'text-teal-400 bg-teal-500/10 border-teal-500/20'
                      : 'text-zinc-600 bg-zinc-800/30 border-zinc-700/30'">
                {{ v.active ? 'active' : 'revoked' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right">
              <button v-if="v.active" @click="revoke(v.id)"
                      class="text-[11px] text-zinc-600 hover:text-rose-400 transition-colors">
                revoke
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'

const versions   = ref([])
const loading    = ref(false)
const creating   = ref(false)
const newVersion = ref('')
const newKey     = ref('')
const copied     = ref(false)
const error      = ref('')

async function fetchVersions() {
  loading.value = true
  try {
    versions.value = await api.versions.list()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function create() {
  if (!newVersion.value.trim()) return
  creating.value = true
  newKey.value   = ''
  error.value    = ''
  try {
    const result  = await api.versions.create(newVersion.value.trim())
    newKey.value  = result.key
    newVersion.value = ''
    await fetchVersions()
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}

async function revoke(id) {
  if (!confirm('Revoke this key? Reports already stored are kept.')) return
  try {
    await api.versions.revoke(id)
    await fetchVersions()
    if (newKey.value) newKey.value = '' // hide if the revoked key was just created
  } catch (e) {
    error.value = e.message
  }
}

async function copyKey() {
  await navigator.clipboard.writeText(newKey.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

onMounted(fetchVersions)
</script>
