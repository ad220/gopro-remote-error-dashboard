<template>
  <div class="flex h-screen bg-zinc-950 text-zinc-300 overflow-hidden">

    <!-- Sidebar -->
    <aside class="w-56 shrink-0 bg-zinc-950 border-r border-zinc-800/60 flex flex-col">
      <!-- Brand -->
      <div class="px-5 py-5 border-b border-zinc-800/60">
        <div class="flex items-center gap-2.5">
          <span class="w-5 h-5 rounded-sm flex items-center justify-center text-[10px] font-bold"
                style="background: #E8430A">GP</span>
          <div>
            <div class="text-zinc-100 text-xs font-semibold tracking-wide">Error Reports</div>
            <div class="text-zinc-600 text-[10px] mt-0.5">admin console</div>
          </div>
        </div>
      </div>

      <!-- Nav -->
      <nav class="p-3 flex-1 space-y-0.5">
        <button
          v-for="item in navItems" :key="item.id"
          @click="current = item.id"
          class="w-full flex items-center gap-2.5 px-3 py-2 rounded text-xs transition-all duration-150"
          :class="current === item.id
            ? 'bg-zinc-800 text-zinc-100'
            : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900'"
        >
          <span class="text-[11px] opacity-70">{{ item.icon }}</span>
          {{ item.label }}
          <span v-if="item.id === 'errors' && errorCount !== null"
                class="ml-auto text-[10px] text-zinc-600">
            {{ errorCount.toLocaleString() }}
          </span>
        </button>
      </nav>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-zinc-800/60">
        <div class="text-[10px] text-zinc-700 leading-relaxed">
          Local network only<br>
          <span class="text-zinc-800">gopro-remote v0.1</span>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-hidden flex flex-col">
      <ErrorGrid  v-if="current === 'errors'"   @total="errorCount = $event" />
      <StatsPanel v-else-if="current === 'stats'" />
      <VersionManager v-else-if="current === 'versions'" />
    </main>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import ErrorGrid     from './components/ErrorGrid.vue'
import StatsPanel    from './components/StatsPanel.vue'
import VersionManager from './components/VersionManager.vue'

const current    = ref('errors')
const errorCount = ref(null)

const navItems = [
  { id: 'errors',   icon: '▤', label: 'Error Log' },
  { id: 'stats',    icon: '◈', label: 'Statistics' },
  { id: 'versions', icon: '◇', label: 'API Keys' },
]
</script>
