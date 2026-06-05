<template>
  <div class="bg-zinc-900/50 border border-zinc-800/60 rounded-lg p-4">
    <div class="text-[10px] text-zinc-500 uppercase tracking-widest mb-3">{{ title }}</div>
    <div v-if="rows.length === 0" class="text-[11px] text-zinc-500">-</div>
    <div v-else class="space-y-1.5">
      <div v-for="[key, count] in rows" :key="key"
           class="flex items-center justify-between gap-3">
        <span class="text-[11px] truncate"
              :class="styleFn ? styleFn(key) : 'text-zinc-400'">
          {{ key }}
        </span>
        <div class="flex items-center gap-2 shrink-0">
          <!-- Mini bar -->
          <div class="w-16 h-1 bg-zinc-800 rounded-full overflow-hidden">
            <div class="h-full rounded-full bg-zinc-600"
                 :style="{ width: barWidth(count) + '%' }"/>
          </div>
          <span class="text-[11px] text-zinc-500 w-8 text-right tabular-nums">
            {{ count.toLocaleString() }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title:   { type: String,   required: true },
  data:    { type: Object,   required: true },
  styleFn: { type: Function, default: null },
})

const rows = computed(() =>
  Object.entries(props.data).sort(([, a], [, b]) => b - a)
)

const maxCount = computed(() =>
  rows.value.length ? rows.value[0][1] : 1
)

function barWidth(count) {
  return Math.round((count / maxCount.value) * 100)
}
</script>
