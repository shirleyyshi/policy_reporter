<template>
  <div class="agent-container">
    <h1 class="title">Agent 自主日报生成</h1>
    <p class="slogan">输入日期，Agent 将自主抓取、清洗、摘要并生成日报（ReAct 模式）</p>

    <!-- 顶部导航 -->
    <div class="nav-bar">
      <el-button text class="nav-btn" @click="$router.push('/home')">← 手动模式</el-button>
      <el-button text class="nav-btn" @click="$router.push('/agent/runs')">历史运行记录</el-button>
    </div>

    <!-- 输入区 -->
    <div class="input-section">
      <div class="input-row">
        <label class="input-label">政策日期</label>
        <el-date-picker
          v-model="date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          class="date-picker"
        />
      </div>
      <div class="input-row">
        <label class="input-label">合规资讯（可选）</label>
        <el-input
          v-model="legalText"
          type="textarea"
          :rows="3"
          placeholder="输入法律法规及合规资讯正文，留空则不包含"
          class="legal-input"
        />
      </div>
      <el-button
        class="glow-btn"
        type="primary"
        size="large"
        :loading="running"
        :disabled="!date || running"
        @click="runAgent"
      >
        {{ running ? 'Agent 运行中...' : '启动 Agent' }}
      </el-button>
    </div>

    <!-- 运行结果 -->
    <div v-if="result" class="result-section">
      <div class="status-cards">
        <div class="status-card" :class="result.status">
          <span class="status-label">状态</span>
          <span class="status-value">{{ statusText }}</span>
        </div>
        <div class="status-card">
          <span class="status-label">步数</span>
          <span class="status-value">{{ result.step }}</span>
        </div>
        <div class="status-card">
          <span class="status-label">工具调用</span>
          <span class="status-value">{{ toolCallCount }}</span>
        </div>
        <div class="status-card">
          <span class="status-label">Critic 触发</span>
          <span class="status-value">{{ criticCount }}</span>
        </div>
      </div>

      <!-- 下载按钮 -->
      <div v-if="result.docx_available" class="download-bar">
        <el-button class="glow-btn" type="success" @click="downloadDocx(result.run_id)">
          下载日报 docx
        </el-button>
      </div>

      <!-- Trace 时间线 -->
      <h3 class="section-title">运行轨迹（Trace）</h3>
      <el-timeline class="trace-timeline">
        <el-timeline-item
          v-for="t in result.trace"
          :key="t.step + '-' + t.action"
          :type="timelineType(t)"
          :timestamp="`Step ${t.step}`"
          placement="top"
        >
          <div class="trace-item">
            <div class="trace-header">
              <el-tag :type="actionTagType(t.action)" size="small" effect="dark">
                {{ t.action }}
              </el-tag>
              <span v-if="t.tool" class="trace-tool">{{ t.tool }}</span>
            </div>
            <div v-if="t.reasoning && t.reasoning !== 'None'" class="trace-reasoning">
              {{ t.reasoning }}
            </div>
            <div v-if="t.output" class="trace-output">
              <pre>{{ formatOutput(t.output) }}</pre>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </div>

    <!-- 空状态提示 -->
    <div v-if="!result && !running" class="empty-hint">
      <p>选择日期后点击「启动 Agent」开始</p>
      <p class="hint-sub">Agent 会自主决策工具调用顺序，每次运行路径可能不同</p>
    </div>

    <!-- 人在回路弹窗 -->
    <el-dialog
      v-model="humanDialog.visible"
      title="Agent 请求人工介入"
      width="500px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="human-dialog-body">
        <p class="human-question">{{ humanDialog.question }}</p>
        <el-radio-group v-model="humanDialog.answer" class="human-options">
          <el-radio
            v-for="opt in humanDialog.options"
            :key="opt"
            :value="opt"
            class="human-option"
          >
            {{ opt }}
          </el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <el-button
          type="primary"
          :loading="humanDialog.submitting"
          @click="submitHumanAnswer"
        >
          提交回答
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElLoading } from 'element-plus'
import api from '@/api'

const route = useRoute()
const router = useRouter()

const date = ref(new Date().toISOString().split('T')[0])
const legalText = ref('')
const running = ref(false)
const result = ref(null)

const humanDialog = reactive({
  visible: false,
  question: '',
  options: [],
  answer: '',
  submitting: false,
})

let pollTimer = null

const statusText = computed(() => {
  const map = { done: '完成', failed: '失败', running: '运行中', waiting_human: '等待人工介入', incomplete: '未完成', unknown: '未知' }
  return map[result.value?.status] || result.value?.status || '-'
})

const toolCallCount = computed(() =>
  (result.value?.trace || []).filter(t => t.action === 'actuate').length
)

const criticCount = computed(() =>
  (result.value?.trace || []).filter(t => t.action === 'critique').length
)

async function runAgent() {
  running.value = true
  result.value = null
  const loading = ElLoading.service({
    lock: true,
    text: 'Agent 启动中...',
    background: 'rgba(0, 0, 0, 0.7)',
  })
  try {
    const res = await api.post('/api/agent/run/', {
      date: date.value,
      legal_text: legalText.value.trim()
    }, { timeout: 30000 })
    const runId = res.data.run_id
    loading.close()
    startPolling(runId)
  } catch (err) {
    loading.close()
    running.value = false
    ElMessage.error('Agent 启动失败：' + (err.response?.data?.error || err.message))
  }
}

function startPolling(runId) {
  stopPolling()
  running.value = true
  const poll = async () => {
    try {
      const res = await api.get(`/api/agent/runs/${runId}/`)
      result.value = res.data
      if (res.data.status === 'waiting_human' && res.data.pending_question) {
        humanDialog.visible = true
        humanDialog.question = res.data.pending_question.question
        humanDialog.options = res.data.pending_question.options || []
        humanDialog.answer = humanDialog.options[0] || ''
      } else if (res.data.status === 'done') {
        stopPolling()
        ElMessage.success(`Agent 完成，共 ${res.data.step} 步`)
      } else if (res.data.status === 'failed') {
        stopPolling()
        ElMessage.error('Agent 运行失败')
      }
    } catch (err) {
      if (err.response?.status !== 404) {
        console.error('轮询失败:', err)
      }
    }
  }
  poll()
  pollTimer = setInterval(poll, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  running.value = false
}

async function submitHumanAnswer() {
  if (!humanDialog.answer) {
    ElMessage.warning('请选择一个答案')
    return
  }
  humanDialog.submitting = true
  try {
    const runId = result.value?.run_id
    await api.post(`/api/agent/runs/${runId}/answer/`, { answer: humanDialog.answer })
    humanDialog.visible = false
    ElMessage.success('已提交回答，Agent 继续运行')
  } catch (err) {
    ElMessage.error('提交失败：' + (err.response?.data?.error || err.message))
  } finally {
    humanDialog.submitting = false
  }
}

async function loadHistory(runId) {
  running.value = true
  try {
    const res = await api.get(`/api/agent/runs/${runId}/`)
    result.value = res.data
    date.value = res.data.trace?.[0]?.input?.date || date.value
    if (res.data.status === 'running' || res.data.status === 'waiting_human') {
      startPolling(runId)
      if (res.data.status === 'waiting_human' && res.data.pending_question) {
        humanDialog.visible = true
        humanDialog.question = res.data.pending_question.question
        humanDialog.options = res.data.pending_question.options || []
        humanDialog.answer = humanDialog.options[0] || ''
      }
    } else {
      running.value = false
    }
  } catch (err) {
    ElMessage.error('加载历史 run 失败：' + (err.response?.data?.error || '不存在'))
    router.replace('/agent')
    running.value = false
  }
}

async function downloadDocx(runId) {
  try {
    // 走 axios 实例：baseURL 回退逻辑与其它请求一致（VITE_API_BASE 未配置时为相对路径），
    // 且 401 时拦截器自动 refresh 并重放下载
    const res = await api.get(`/api/agent/runs/${runId}/download/`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `agent_report_${runId}.docx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success('docx 下载成功')
  } catch (err) {
    // 后端错误体在 blob 模式下是 Blob，需读出 JSON 里的 error
    let msg = err.message
    if (err.response?.data instanceof Blob) {
      try {
        msg = JSON.parse(await err.response.data.text()).error || msg
      } catch { /* 保持默认提示 */ }
    }
    ElMessage.error('docx 下载失败：' + msg)
  }
}

function timelineType(t) {
  if (t.action === 'terminate') return t.reasoning?.includes?.('done') ? 'success' : 'danger'
  if (t.action === 'critique') return 'warning'
  return 'primary'
}

function actionTagType(action) {
  if (action === 'actuate') return 'primary'
  if (action === 'critique') return 'warning'
  if (action === 'terminate') return 'danger'
  return 'info'
}

function formatOutput(output) {
  if (!output) return ''
  if (typeof output === 'string') return output
  return JSON.stringify(output, null, 2)
}

onMounted(() => {
  const runId = route.query.run_id
  if (runId) {
    loadHistory(runId)
  }
})

onUnmounted(() => stopPolling())
</script>

<style scoped>
.agent-container {
  min-height: 100vh;
  padding: 40px 60px;
  max-width: 900px;
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

.input-section { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 24px; margin-bottom: 30px; }
.input-row { margin-bottom: 16px; }
.input-label { display: block; margin-bottom: 8px; color: #b2ebf2; font-size: 14px; }
.date-picker { width: 100%; }
.legal-input { width: 100%; }

.glow-btn { background: linear-gradient(90deg, #00e5ff, #2979ff); border: none; box-shadow: 0 0 15px rgba(0,229,255,0.6); color: white !important; font-weight: bold; }
.glow-btn:hover { box-shadow: 0 0 25px rgba(0,229,255,1); transform: translateY(-2px); }
.glow-btn:disabled { opacity: 0.5; }

.result-section { margin-top: 20px; }
.status-cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.status-card { flex: 1; min-width: 120px; background: rgba(255,255,255,0.05); border-radius: 10px; padding: 16px; text-align: center; border: 1px solid rgba(0,229,255,0.15); }
.status-card.done { border-color: #4caf50; }
.status-card.failed { border-color: #f44336; }
.status-card.waiting_human { border-color: #ff9800; }
.status-label { display: block; font-size: 12px; color: #80deea; margin-bottom: 6px; }
.status-value { display: block; font-size: 22px; font-weight: bold; color: #fff; }

.download-bar { margin-bottom: 24px; text-align: center; }

.section-title { color: #00e5ff; margin: 24px 0 16px; font-size: 18px; }

.trace-timeline { padding: 10px 0; }
.trace-item { background: rgba(255,255,255,0.04); border-radius: 8px; padding: 12px 16px; }
.trace-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.trace-tool { color: #00e5ff; font-weight: bold; font-size: 14px; }
.trace-reasoning { color: #b2ebf2; font-size: 13px; margin-bottom: 6px; font-style: italic; }
.trace-output pre { color: #a5d6a7; font-size: 12px; margin: 4px 0 0; white-space: pre-wrap; word-break: break-all; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 6px; max-height: 200px; overflow-y: auto; }

.empty-hint { text-align: center; margin-top: 60px; color: #80deea; }
.hint-sub { font-size: 13px; color: #607d8b; margin-top: 8px; }

.human-dialog-body { padding: 0 4px; }
.human-question { font-size: 15px; color: #303133; line-height: 1.6; margin-bottom: 20px; }
.human-options { display: flex; flex-direction: column; gap: 12px; }
.human-option { margin-right: 0 !important; }
</style>
