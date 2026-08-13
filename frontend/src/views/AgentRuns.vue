<template>
  <div class="runs-container">
    <h1 class="title">历史运行记录</h1>
    <p class="slogan">查看所有 Agent 运行的 trace，对比不同 run 的决策路径</p>

    <div class="nav-bar">
      <el-button text class="nav-btn" @click="$router.push('/agent')">← 运行新 Agent</el-button>
      <el-button text class="nav-btn" @click="$router.push('/home')">手动模式</el-button>
    </div>

    <div v-if="loading" class="loading-hint">加载中...</div>

    <div v-else-if="runs.length === 0" class="empty-hint">
      <p>暂无运行记录</p>
      <el-button class="glow-btn" type="primary" @click="$router.push('/agent')">运行第一个 Agent</el-button>
    </div>

    <div v-else class="table-wrapper">
      <el-table :data="runs" style="width: 100%" class="runs-table" stripe>
        <el-table-column label="Run ID" width="280">
          <template #default="{ row }">
            <span class="run-id">{{ row.run_id.substring(0, 8) }}...</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="dark" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="step_count" label="步数" width="80" />
        <el-table-column prop="trace_count" label="Trace 条数" width="110" />
        <el-table-column label="docx" width="80">
          <template #default="{ row }">
            <span :class="row.has_docx ? 'docx-yes' : 'docx-no'">{{ row.has_docx ? '有' : '无' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">
            {{ formatTime(row.last_updated) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewTrace(row.run_id)">
              查看 trace
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="total-hint">共 {{ total }} 条运行记录</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const router = useRouter()
const runs = ref([])
const total = ref(0)
const loading = ref(true)

async function loadRuns() {
  loading.value = true
  try {
    const res = await api.get('/api/agent/runs/')
    runs.value = res.data.runs || []
    total.value = res.data.total || 0
  } catch (err) {
    ElMessage.error('加载历史记录失败：' + (err.response?.data?.error || err.message))
  } finally {
    loading.value = false
  }
}

function viewTrace(runId) {
  router.push(`/agent?run_id=${runId}`)
}

function statusText(status) {
  const map = { done: '完成', failed: '失败', incomplete: '未完成', unknown: '未知', running: '运行中', waiting_human: '等待人工' }
  return map[status] || status
}

function statusTagType(status) {
  const map = { done: 'success', failed: 'danger', incomplete: 'warning', unknown: 'info', running: 'primary', waiting_human: 'warning' }
  return map[status] || 'info'
}

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

onMounted(() => {
  loadRuns()
})
</script>

<style scoped>
.runs-container {
  min-height: 100vh;
  padding: 40px 60px;
  max-width: 1000px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  font-family: 'Inter', sans-serif;
}

.title { text-align: center; font-weight: bold; font-size: 32px; margin-bottom: 12px; font-family: 'Orbitron', sans-serif; color: #00e5ff; letter-spacing: 2px; }
.slogan { text-align: center; font-size: 15px; color: #80deea; margin-bottom: 20px; }

.nav-bar { display: flex; justify-content: space-between; margin-bottom: 24px; }
.nav-btn { color: #80deea !important; }
.nav-btn:hover { color: #00e5ff !important; }

.loading-hint, .empty-hint { text-align: center; margin-top: 60px; color: #80deea; }
.empty-hint .glow-btn { margin-top: 16px; }

.table-wrapper { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; }
.runs-table { background: transparent !important; --el-table-bg-color: transparent; --el-table-tr-bg-color: transparent; --el-table-header-bg-color: rgba(0,229,255,0.1); --el-table-border-color: rgba(0,229,255,0.1); color: #e0f7fa !important; }
.runs-table :deep(.el-table__cell) { color: #e0f7fa; }
.runs-table :deep(th) { color: #00e5ff !important; }

.run-id { font-family: monospace; color: #80deea; font-size: 13px; }
.docx-yes { color: #4caf50; font-weight: bold; }
.docx-no { color: #607d8b; }
.total-hint { text-align: center; color: #607d8b; font-size: 13px; margin-top: 16px; }

.glow-btn { background: linear-gradient(90deg, #00e5ff, #2979ff); border: none; box-shadow: 0 0 15px rgba(0,229,255,0.6); color: white !important; font-weight: bold; }
.glow-btn:hover { box-shadow: 0 0 25px rgba(0,229,255,1); transform: translateY(-2px); }
</style>
