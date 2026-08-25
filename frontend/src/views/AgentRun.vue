<template>
  <div class="agent-container">
    <h1 class="title">Agent 自主日报生成</h1>
    <p class="slogan">Agent 将按当前所选日期自主抓取、清洗、摘要并生成日报（ReAct 模式）</p>

    <!-- 顶部导航 -->
    <div class="nav-bar">
      <el-button text class="nav-btn" @click="$router.push('/home')">← 手动模式</el-button>
      <el-button text class="nav-btn" @click="$router.push('/agent/runs')">历史运行记录</el-button>
    </div>

    <!-- 输入区 -->
    <div class="input-section">
      <div class="input-row">
        <label class="input-label">政策日期（在首页调整）</label>
        <div class="date-display">
          <span class="date-value">{{ date }}</span>
          <el-button text size="small" class="change-date-btn" @click="$router.push('/home')">修改日期</el-button>
        </div>
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
      class="agent-dialog"
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

// 日期统一在首页调整（localStorage.selectedDate，与编辑页同源），本页只读
const date = ref(localStorage.getItem('selectedDate') || new Date().toISOString().split('T')[0])
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
    ElMessage.error('提交失败：' + (err.response?.data?.detail || err.response?.data?.error || '请稍后重试'))
  } finally {
    humanDialog.submitting = false
  }
}

async function loadHistory(runId) {
  running.value = true
  try {
    const res = await api.get(`/api/agent/runs/${runId}/`)
    result.value = res.data
    // 不回写 date：历史 run 的日期只属于该 run，不改变当前全局所选日期
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
    // 文件名与手动导出口径一致：每日财税日报（YYYY.MM.DD）.docx
    const dateStr = (date.value || '').replace(/-/g, '.')
    link.setAttribute('download', dateStr ? `每日财税日报（${dateStr}）.docx` : `agent_report_${runId}.docx`)
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
        const body = JSON.parse(await err.response.data.text())
        msg = body.detail || body.error || msg
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
  padding: 24px 48px 60px;
  max-width: 1100px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  box-sizing: border-box;
}

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
.slogan { text-align: center; font-size: 13px; color: #80deea; margin: 0 0 20px; opacity: 0.85; }

.nav-bar { display: flex; justify-content: space-between; margin-bottom: 24px; }
.nav-btn { color: #80deea !important; }
.nav-btn:hover { color: #00e5ff !important; }

.input-section { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 24px; margin-bottom: 30px; }
.input-row { margin-bottom: 16px; }
.input-label { display: block; margin-bottom: 8px; color: #b2ebf2; font-size: 14px; }
.date-display {
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(0, 0, 0, 0.2); border: 1px solid rgba(0, 229, 255, 0.15);
  border-radius: 8px; padding: 10px 14px;
}
.date-value { color: #00e5ff; font-size: 15px; font-weight: 600; letter-spacing: 1px; }
.change-date-btn { color: #80deea !important; }
.change-date-btn:hover { color: #00e5ff !important; }
.legal-input {
  width: 100%;
  --el-input-bg-color: rgba(255, 255, 255, 0.08);
  --el-input-border-color: rgba(0, 229, 255, 0.2);
  --el-input-hover-border-color: rgba(0, 229, 255, 0.5);
  --el-input-focus-border-color: #00e5ff;
  --el-input-text-color: #e0f7fa;
  --el-input-placeholder-color: #607d8b;
}
.legal-input :deep(.el-textarea__inner) {
  min-height: 96px !important;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.08) !important;
  border: 1px solid rgba(0, 229, 255, 0.2) !important;
  border-radius: 10px !important;
  box-shadow: none !important;
  color: #e0f7fa !important;
  transition: all 0.3s ease;
}
.legal-input :deep(.el-textarea__inner:hover) {
  border-color: rgba(0, 229, 255, 0.5) !important;
}
.legal-input :deep(.el-textarea__inner:focus) {
  border-color: #00e5ff !important;
  box-shadow: 0 0 12px rgba(0, 229, 255, 0.2) !important;
}
.legal-input :deep(.el-textarea__inner::placeholder) {
  color: #607d8b !important;
}

.glow-btn {
  background: linear-gradient(90deg, #00e5ff, #2979ff) !important;
  border: none !important;
  box-shadow: 0 4px 16px rgba(0,229,255,0.4);
  color: #0f2027 !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  transition: all 0.3s ease;
}
.glow-btn:hover:not(:disabled) { box-shadow: 0 6px 24px rgba(0,229,255,0.6); transform: translateY(-2px); }
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
.human-question { font-size: 15px; color: #e0f7fa; line-height: 1.6; margin-bottom: 20px; }
.human-options { display: flex; flex-direction: column; gap: 12px; }
.human-option { margin-right: 0 !important; color: #e0f7fa; }

:deep(.agent-dialog) {
  background: #162b35;
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 14px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
:deep(.agent-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 20px 24px 12px;
  border-bottom: 1px solid rgba(0, 229, 255, 0.12);
}
:deep(.agent-dialog .el-dialog__title) {
  color: #00e5ff;
  font-weight: 600;
}
:deep(.agent-dialog .el-dialog__body) { padding: 20px 24px; }
:deep(.agent-dialog .el-dialog__footer) { padding: 12px 24px 20px; }
:deep(.agent-dialog .el-radio) { color: #e0f7fa; }
:deep(.agent-dialog .el-radio__label) { color: #e0f7fa; }
:deep(.agent-dialog .el-radio__inner) { background: transparent; border-color: #80deea; }
:deep(.agent-dialog .el-radio.is-checked .el-radio__inner) { border-color: #00e5ff; background: #00e5ff; }

@media (max-width: 640px) {
  .agent-container { padding: 20px 16px 40px; }
  .title { font-size: 26px; letter-spacing: 2px; }
  .nav-bar { flex-wrap: wrap; gap: 8px; }
  :deep(.agent-dialog) { width: calc(100% - 32px) !important; }
}
</style>
