<template>
  <div ref="rootRef" class="pdp-root">
    <button
      type="button"
      class="pdp-trigger"
      :class="{ open: panelOpen, 'no-policy': !selectedHasPolicy }"
      @click="panelOpen = !panelOpen"
    >
      <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" class="pdp-icon">
        <path d="M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2zm0 16H5V10h14v10zM5 8V6h14v2H5z"/>
      </svg>
      <span class="pdp-value">{{ modelValue || '选择日期' }}</span>
      <span class="pdp-caret" :class="{ open: panelOpen }">▾</span>
    </button>

    <transition name="pdp-fade">
      <div v-if="panelOpen" class="pdp-panel">
        <div class="pdp-header">
          <button type="button" class="pdp-nav" @click="changeMonth(-1)">‹</button>
          <span class="pdp-month">{{ viewYear }} 年 {{ viewMonth }} 月</span>
          <button type="button" class="pdp-nav" :disabled="atCurrentMonth" @click="changeMonth(1)">›</button>
        </div>

        <div class="pdp-weekdays">
          <span v-for="w in weekdays" :key="w">{{ w }}</span>
        </div>

        <div class="pdp-grid">
          <template v-for="(cell, i) in cells" :key="i">
            <span v-if="cell.blank" class="pdp-cell blank"></span>
            <button
              v-else
              type="button"
              class="pdp-cell"
              :class="{
                today: cell.isToday,
                selected: cell.isSelected,
                future: cell.isFuture,
                'has-policy': cell.hasPolicy,
                'no-policy': !cell.hasPolicy
              }"
              :disabled="cell.isFuture"
              :title="cell.hasPolicy ? `${cell.dateStr} 有 ${dateCounts[cell.dateStr]} 条政策` : `${cell.dateStr} 暂无政策`"
              @click="pick(cell)"
            >
              {{ cell.day }}
            </button>
          </template>
        </div>

        <div class="pdp-legend">
          <span><i class="dot has"></i>有政策</span>
          <span><i class="dot none"></i>无政策</span>
          <span class="legend-note">未来日期不可选</span>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import api from '@/api'

const props = defineProps({
  modelValue: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'change'])

const weekdays = ['日', '一', '二', '三', '四', '五', '六']
const panelOpen = ref(false)
const rootRef = ref(null)

// 日期 -> 政策条数（后端 /api/policy-dates/）
const dateCounts = ref({})
const datesLoaded = ref(false)

function pad(n) {
  return String(n).padStart(2, '0')
}

// 面板当前显示的年月（跟随选中日期初始化）
const now = new Date()
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth() + 1)

const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`

const atCurrentMonth = computed(
  () => viewYear.value === now.getFullYear() && viewMonth.value === now.getMonth() + 1
)

const selectedHasPolicy = computed(() => {
  if (!datesLoaded.value) return true
  return (dateCounts.value[props.modelValue] || 0) > 0
})

const cells = computed(() => {
  const y = viewYear.value
  const m = viewMonth.value
  const firstWeekday = new Date(y, m - 1, 1).getDay()
  const daysInMonth = new Date(y, m, 0).getDate()
  const list = []
  for (let i = 0; i < firstWeekday; i++) {
    list.push({ blank: true })
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${y}-${pad(m)}-${pad(d)}`
    list.push({
      blank: false,
      day: d,
      dateStr,
      isToday: dateStr === todayStr,
      isSelected: dateStr === props.modelValue,
      isFuture: dateStr > todayStr,
      hasPolicy: (dateCounts.value[dateStr] || 0) > 0
    })
  }
  return list
})

function changeMonth(delta) {
  let m = viewMonth.value + delta
  let y = viewYear.value
  if (m < 1) { m = 12; y -= 1 }
  if (m > 12) { m = 1; y += 1 }
  // 不能翻到当前月份之后
  if (y > now.getFullYear() || (y === now.getFullYear() && m > now.getMonth() + 1)) return
  viewYear.value = y
  viewMonth.value = m
}

function pick(cell) {
  if (cell.isFuture) return
  emit('update:modelValue', cell.dateStr)
  emit('change', cell.dateStr)
  panelOpen.value = false
}

// 选中日期变化时（如"前一天/今天"快捷按钮），面板年月跟随
watch(() => props.modelValue, (val) => {
  if (val && /^\d{4}-\d{2}-\d{2}$/.test(val)) {
    viewYear.value = Number(val.slice(0, 4))
    viewMonth.value = Number(val.slice(5, 7))
  }
})

function onDocClick(e) {
  if (rootRef.value && !rootRef.value.contains(e.target)) {
    panelOpen.value = false
  }
}

onMounted(async () => {
  document.addEventListener('click', onDocClick)
  try {
    const res = await api.get('/api/policy-dates/')
    dateCounts.value = res.data || {}
    datesLoaded.value = true
  } catch (err) {
    console.error('加载政策日期分布失败:', err)
  }
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.pdp-root {
  position: relative;
  display: inline-block;
  font-family: inherit;
}

/* 触发按钮：视觉与 Element 输入框一致 */
.pdp-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 170px;
  padding: 0 12px;
  height: 32px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 6px;
  color: #e0f7fa;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  box-sizing: border-box;
}
.pdp-trigger:hover {
  border-color: rgba(0, 229, 255, 0.6);
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.2);
}
.pdp-trigger.open {
  border-color: #00e5ff;
  box-shadow: 0 0 0 1px #00e5ff inset, 0 0 10px rgba(0, 229, 255, 0.3);
}
.pdp-trigger.no-policy .pdp-value {
  color: #ffb74d;
}
.pdp-icon {
  color: #80deea;
  flex-shrink: 0;
}
.pdp-value {
  flex: 1;
  text-align: left;
  letter-spacing: 0.5px;
}
.pdp-caret {
  color: #80deea;
  font-size: 10px;
  transition: transform 0.2s;
}
.pdp-caret.open {
  transform: rotate(180deg);
}

/* 弹层面板 */
.pdp-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 200;
  width: 280px;
  padding: 14px;
  background: rgba(13, 27, 36, 0.98);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 20px rgba(0, 229, 255, 0.08);
  backdrop-filter: blur(12px);
  box-sizing: border-box;
}

.pdp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.pdp-month {
  font-size: 14px;
  font-weight: 600;
  color: #00e5ff;
  letter-spacing: 1px;
}
.pdp-nav {
  width: 26px;
  height: 26px;
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  color: #80deea;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.pdp-nav:hover:not(:disabled) {
  color: #00e5ff;
  border-color: rgba(0, 229, 255, 0.6);
}
.pdp-nav:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.pdp-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: 4px;
}
.pdp-weekdays span {
  text-align: center;
  font-size: 12px;
  color: #607d8b;
  padding: 4px 0;
}

.pdp-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}
.pdp-cell {
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  position: relative;
  transition: background 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
.pdp-cell.blank {
  background: transparent;
  cursor: default;
}

/* 核心着色：有政策 = 青白色，无政策 = 橙色 */
.pdp-cell.has-policy {
  color: #e0f7fa;
  font-weight: 600;
}
.pdp-cell.no-policy {
  color: #ffb74d;
}
.pdp-cell.future {
  color: #455a64 !important;
  cursor: not-allowed;
}

.pdp-cell:not(.blank):not(.future):hover {
  background: rgba(0, 229, 255, 0.12);
}
.pdp-cell.today::after {
  content: '';
  position: absolute;
  bottom: 3px;
  left: 50%;
  transform: translateX(-50%);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #00e5ff;
}
.pdp-cell.selected {
  background: linear-gradient(135deg, #00e5ff, #2979ff);
  color: #0f2027 !important;
  font-weight: 700;
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.4);
}
.pdp-cell.selected.today::after {
  background: #0f2027;
}

/* 图例 */
.pdp-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(0, 229, 255, 0.12);
  font-size: 11px;
  color: #80deea;
}
.pdp-legend span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}
.dot.has { background: #e0f7fa; box-shadow: 0 0 4px rgba(224, 247, 250, 0.8); }
.dot.none { background: #ffb74d; box-shadow: 0 0 4px rgba(255, 183, 77, 0.6); }
.legend-note {
  margin-left: auto;
  color: #607d8b;
}

/* 弹出动画 */
.pdp-fade-enter-active,
.pdp-fade-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.pdp-fade-enter-from,
.pdp-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
