<template>
  <div class="home-container">
    <!-- 顶部品牌区 -->
    <header class="hero">
      <div class="brand-row">
        <div class="brand">
          <span class="brand-dot"></span>
          <span class="brand-name">Policy Reporter</span>
        </div>
        <el-dropdown trigger="hover" @command="handleUserCommand">
          <div class="user-chip">
            <span class="user-avatar">{{ username.charAt(0).toUpperCase() }}</span>
            <span class="user-name">{{ username }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <h1 class="title">财税政策日报</h1>
      <p class="slogan">本材料是为提供一般信息的用途编制，并非旨在成为可依赖的会计、税务、法律或其他专业意见。</p>
    </header>

    <!-- 日期控制条 -->
    <section class="date-bar">
      <div class="date-left">
        <span class="date-label">政策日期</span>
        <PolicyDatePicker v-model="selectedDate" @change="onDateChange" />
      </div>
      <div class="date-quick">
        <el-button text class="quick-btn" @click="shiftDate(-1)">前一天</el-button>
        <el-button text class="quick-btn today-btn" @click="goToday">今天</el-button>
        <el-button text class="quick-btn" :disabled="isMaxDate" @click="shiftDate(1)">后一天</el-button>
      </div>
    </section>

    <!-- 统计卡片网格 -->
    <section class="card-grid">
      <div class="info-card central" @click="goCentralEditor">
        <div class="card-icon">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div class="card-body">
          <h3 class="card-title">中央政策</h3>
          <p class="card-stat">
            <span class="stat-num">{{ centralCount }}</span>
            <span class="stat-unit">条</span>
          </p>
          <p class="card-sub">已选 {{ selectedCentralCount }} 条</p>
        </div>
        <div class="card-arrow">›</div>
      </div>

      <div class="info-card local" @click="goLocalEditor">
        <div class="card-icon">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 010-5 2.5 2.5 0 010 5z"/>
          </svg>
        </div>
        <div class="card-body">
          <h3 class="card-title">地方法规</h3>
          <p class="card-stat">
            <span class="stat-num">{{ localCount }}</span>
            <span class="stat-unit">条</span>
          </p>
          <p class="card-sub">已选 {{ selectedLocalCount }} 条</p>
        </div>
        <div class="card-arrow">›</div>
      </div>

      <div class="info-card legal" @click="goLegalEditor">
        <div class="card-icon">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
            <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 14H7v-2h10v2zm0-4H7v-2h10v2zm0-4H7V7h10v2z"/>
          </svg>
        </div>
        <div class="card-body">
          <h3 class="card-title">合规资讯</h3>
          <p class="card-stat">
            <span class="stat-text" :class="legalStatusClass">{{ legalStatus }}</span>
          </p>
          <p class="card-sub">法律法规与资讯</p>
        </div>
        <div class="card-arrow">›</div>
      </div>

      <div class="info-card agent" @click="goAgent">
        <div class="card-icon">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
            <path d="M12 2a3 3 0 013 3v1h2a3 3 0 013 3v2h1v2h-1v2a3 3 0 01-3 3h-2v1a3 3 0 01-6 0v-1H7a3 3 0 01-3-3v-2H3v-2h1V9a3 3 0 013-3h2V5a3 3 0 013-3zm-2 14a1 1 0 102 0 1 1 0 00-2 0zm4 0a1 1 0 102 0 1 1 0 00-2 0z"/>
          </svg>
        </div>
        <div class="card-body">
          <h3 class="card-title">Agent 自主生成</h3>
          <p class="card-stat">
            <span class="stat-text accent">ReAct</span>
          </p>
          <p class="card-sub">智能体自动日报</p>
        </div>
        <div class="card-arrow">›</div>
      </div>
    </section>

    <!-- 导出区 -->
    <section class="export-section">
      <el-button
        class="glow-btn"
        type="primary"
        size="large"
        :loading="exporting"
        :disabled="exporting"
        @click="exportReport"
      >
        <span v-if="!exporting">📄 导出日报（{{ totalSelected }} 条政策）</span>
        <span v-else>导出中...</span>
      </el-button>
      <div v-if="exporting" class="progress-container">
        <el-progress :percentage="progress" status="success" :stroke-width="6" />
      </div>
    </section>

    <!-- 空状态提示 -->
    <div v-if="!loading && centralCount === 0 && localCount === 0" class="empty-hint">
      <p>当前日期没有政策数据</p>
      <p class="hint-sub">试试切换日期，或运行爬虫抓取更多政策</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElLoading } from 'element-plus'
import api from '@/api'
import { selectionStore } from '@/stores/selection'
import PolicyDatePicker from '@/components/PolicyDatePicker.vue'

const router = useRouter()

// 用户信息
const username = ref(localStorage.getItem('username') || '用户')

// 日期：从 localStorage 读取，默认今天
const todayStr = new Date().toISOString().split('T')[0]
const selectedDate = ref(localStorage.getItem('selectedDate') || todayStr)

// 当前已是今天时，禁用"后一天"按钮（未来日期禁用逻辑在 PolicyDatePicker 内部处理）
const isMaxDate = computed(() => selectedDate.value >= todayStr)

// 政策数据
const central = ref([])
const local = ref([])
const loading = ref(false)

// 选择状态：从内存 store 读取（刷新即清空，不持久化）
const centralSelectedIds = computed(() => selectionStore.centralIds)
const localSelectedIds = computed(() => selectionStore.localIds)
const legalText = computed(() => selectionStore.legalText)

// 统计信息
const centralCount = computed(() => central.value.length)
const localCount = computed(() => local.value.length)
const selectedCentralCount = computed(() => centralSelectedIds.value.length)
const selectedLocalCount = computed(() => localSelectedIds.value.length)
const totalSelected = computed(() => selectedCentralCount.value + selectedLocalCount.value)
const legalStatus = computed(() => (legalText.value.trim() ? '已编写' : '未编写'))
const legalStatusClass = computed(() => (legalText.value.trim() ? 'done' : 'pending'))

// 导出状态
const exporting = ref(false)
const progress = ref(0)

// 日期切换
function onDateChange(val) {
  if (!val) return
  localStorage.setItem('selectedDate', val)
  loadData(val)
}

function shiftDate(delta) {
  const d = new Date(selectedDate.value)
  d.setDate(d.getDate() + delta)
  const newStr = d.toISOString().split('T')[0]
  selectedDate.value = newStr
  localStorage.setItem('selectedDate', newStr)
  loadData(newStr)
}

function goToday() {
  selectedDate.value = todayStr
  localStorage.setItem('selectedDate', todayStr)
  loadData(todayStr)
}

// 加载数据
async function loadData(dateStr) {
  loading.value = true
  try {
    const res = await api.get('/api/policies/', { params: { date: dateStr } })
    central.value = res.data.central || []
    local.value = res.data.local || []
  } catch (err) {
    console.error('加载政策数据失败:', err)
    ElMessage.error('加载政策数据失败')
  } finally {
    loading.value = false
  }
}

// 跳转编辑页
function goCentralEditor() { router.push('/editor/central') }
function goLocalEditor() { router.push('/editor/local') }
function goLegalEditor() { router.push('/editor/legal') }
function goAgent() { router.push('/agent') }

// 头像下拉菜单
function handleUserCommand(command) {
  if (command === 'logout') {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('username')
    router.push('/login')
  }
}

// 导出日报
async function exportReport() {
  const selected_ids = [
    ...centralSelectedIds.value.map(id => ({ id, source: 'central' })),
    ...localSelectedIds.value.map(id => ({ id, source: 'local' }))
  ]

  if (selected_ids.length === 0) {
    ElMessage.warning('请选择至少一条政策进行导出')
    return
  }

  const payload = {
    selected_ids,
    legal_text: legalText.value.trim(),
    date: selectedDate.value
  }

  exporting.value = true
  progress.value = 10
  const timer = setInterval(() => {
    if (progress.value < 90) progress.value += 5
  }, 300)

  const loadingService = ElLoading.service({
    lock: true,
    text: '正在导出日报，请稍候...',
    background: 'rgba(0, 0, 0, 0.7)',
    spinner: 'el-icon-loading'
  })

  try {
    const res = await api.post('/api/export/', payload, { responseType: 'blob' })

    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `每日财税日报（${selectedDate.value.replace(/-/g, '.')}）.docx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    progress.value = 100
    ElMessage.success('日报导出成功')
  } catch (err) {
    console.error('导出失败:', err)
    ElMessage.error('日报导出失败')
  } finally {
    clearInterval(timer)
    loadingService.close()
    setTimeout(() => { exporting.value = false; progress.value = 0 }, 500)
  }
}

onMounted(() => {
  loadData(selectedDate.value)
})
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  padding: 24px 48px 60px;
  max-width: 1100px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  box-sizing: border-box;
}

/* 顶部品牌区 */
.hero { margin-bottom: 20px; }
.brand-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #80deea;
  font-size: 13px;
  letter-spacing: 1px;
}
.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00e5ff;
  box-shadow: 0 0 12px #00e5ff;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.brand-name { font-weight: 500; }
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(0,229,255,0.2);
  padding: 4px 12px 4px 4px;
  border-radius: 20px;
  cursor: pointer;
  outline: none;
}
.user-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00e5ff, #2979ff);
  color: #0f2027;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 12px;
}
.user-name { color: #e0f7fa; font-size: 13px; }

.title {
  text-align: center;
  font-weight: 700;
  font-size: 32px;
  margin: 0 0 6px;
  color: #00e5ff;
  letter-spacing: 3px;
  text-shadow: 0 0 20px rgba(0,229,255,0.3);
  font-family: 'Orbitron', 'Inter', 'Microsoft YaHei', sans-serif;
}
.slogan {
  text-align: center;
  font-size: 13px;
  color: #80deea;
  margin: 0;
  opacity: 0.85;
}

/* 日期控制条 */
.date-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255,255,255,0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0,229,255,0.15);
  border-radius: 10px;
  padding: 10px 16px;
  margin-bottom: 18px;
}
.date-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.date-label {
  color: #b2ebf2;
  font-size: 13px;
  font-weight: 500;
}
.date-quick { display: flex; gap: 4px; }
.quick-btn {
  color: #80deea !important;
  font-size: 13px;
}
.quick-btn:hover { color: #00e5ff !important; }
.today-btn { font-weight: 600; }

/* 卡片网格：2x2 布局 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
@media (max-width: 640px) {
  .card-grid { grid-template-columns: 1fr; }
}
.info-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 18px;
  background: rgba(255,255,255,0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}
.info-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  opacity: 0.6;
}
.info-card.central::before { background: linear-gradient(90deg, #00e5ff, transparent); }
.info-card.local::before { background: linear-gradient(90deg, #4cafef, transparent); }
.info-card.legal::before { background: linear-gradient(90deg, #ffb74d, transparent); }
.info-card.agent::before { background: linear-gradient(90deg, #ab47bc, transparent); }

.info-card:hover {
  transform: translateY(-3px);
  border-color: rgba(0,229,255,0.4);
  background: rgba(255,255,255,0.08);
}
.info-card.central:hover { box-shadow: 0 6px 18px rgba(0,229,255,0.25); }
.info-card.local:hover { box-shadow: 0 6px 18px rgba(76,175,239,0.25); }
.info-card.legal:hover { box-shadow: 0 6px 18px rgba(255,183,77,0.25); }
.info-card.agent:hover { box-shadow: 0 6px 18px rgba(171,71,188,0.25); }

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.info-card.central .card-icon { background: rgba(0,229,255,0.15); color: #00e5ff; }
.info-card.local .card-icon { background: rgba(76,175,239,0.15); color: #4cafef; }
.info-card.legal .card-icon { background: rgba(255,183,77,0.15); color: #ffb74d; }
.info-card.agent .card-icon { background: rgba(171,71,188,0.15); color: #ab47bc; }

.card-body { flex: 1; min-width: 0; }
.card-title {
  font-size: 13px;
  font-weight: 500;
  color: #b2ebf2;
  margin: 0 0 4px;
}
.card-stat {
  margin: 0 0 2px;
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.stat-num {
  font-size: 25px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}
.stat-unit { font-size: 12px; color: #80deea; }
.stat-text { font-size: 16px; font-weight: 600; }
.stat-text.done { color: #66bb6a; }
.stat-text.pending { color: #ffb74d; }
.stat-text.accent { color: #ab47bc; }
.card-sub {
  font-size: 11px;
  color: #80deea;
  margin: 0;
  opacity: 0.8;
}

.card-arrow {
  font-size: 22px;
  color: #80deea;
  opacity: 0.4;
  transition: all 0.3s;
}
.info-card:hover .card-arrow {
  opacity: 1;
  transform: translateX(4px);
}

/* 导出区 */
.export-section {
  text-align: center;
  margin-top: 8px;
}
.glow-btn {
  background: linear-gradient(90deg, #00e5ff, #2979ff) !important;
  border: none !important;
  box-shadow: 0 4px 16px rgba(0,229,255,0.4);
  color: #0f2027 !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  padding: 10px 28px !important;
  height: auto !important;
  border-radius: 8px !important;
  transition: all 0.3s ease;
}
.glow-btn:hover:not(:disabled) {
  box-shadow: 0 6px 24px rgba(0,229,255,0.6);
  transform: translateY(-2px);
}
.glow-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.progress-container {
  margin: 14px auto 0;
  width: 60%;
  max-width: 400px;
}

/* 空状态 */
.empty-hint {
  text-align: center;
  margin-top: 20px;
  padding: 18px;
  color: #80deea;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
  border: 1px dashed rgba(0,229,255,0.2);
}
.hint-sub {
  font-size: 13px;
  color: #607d8b;
  margin-top: 6px;
}
</style>
