<template>
  <div class="home-container">
    <h1 class="title">财税政策日报</h1>
    <p class="slogan">本材料是为提供一般信息的用途编制，并非旨在成为可依赖的会计、税务、法律或其他专业意见。</p>
    <h3 class="welcome">欢迎 {{ username }} ，今天是 {{ today }}</h3>

    <div class="card-container">
      <!-- 中央政策 -->
      <el-card shadow="hover" class="info-card central" @click="goCentralEditor">
        <h3>中央政策</h3>
        <p class="count">
          今日 {{ centralCount }} 条，已选择 {{ selectedCentralCount }} 条
        </p>
      </el-card>

      <!-- 地方法规 -->
      <el-card shadow="hover" class="info-card local" @click="goLocalEditor">
        <h3>地方法规</h3>
        <p class="count">
          今日 {{ localCount }} 条，已选择 {{ selectedLocalCount }} 条
        </p>
      </el-card>

      <!-- 合规资讯 -->
      <el-card shadow="hover" class="info-card legal" @click="goLegalEditor">
        <h3>法律法规及合规资讯</h3>
        <p class="count">{{ legalStatus }}</p>
      </el-card>

      <!-- Agent 模式 -->
      <el-card shadow="hover" class="info-card agent" @click="goAgent">
        <h3>Agent 自主生成</h3>
        <p class="count">ReAct 模式 →</p>
      </el-card>
    </div>

    <div class="btn-container">
      <el-button class="glow-btn" type="primary" size="large" @click="exportReport">
        📄 导出日报
      </el-button>
    </div>

    <div v-if="exporting" class="progress-container">
      <el-progress :percentage="progress" status="active"></el-progress>
      <p style="color:#b2ebf2; margin-top:4px;">导出进度：{{ progress }}%</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElLoading } from 'element-plus'
import api from '@/api'

const router = useRouter()

// 用户信息 & 日期
const username = ref(localStorage.getItem('username') || '用户')
const today = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '.')

// 政策数据
const central = ref([])
const local = ref([])
const centralSelectedIds = ref([])
const localSelectedIds = ref([])
const legalText = ref(localStorage.getItem('legalText') || '')

// 统计信息
const centralCount = ref(0)
const localCount = ref(0)
const selectedCentralCount = computed(() => centralSelectedIds.value.length)
const selectedLocalCount = computed(() => localSelectedIds.value.length)
const legalStatus = computed(() => (legalText.value.trim() ? '已编写' : '未编写'))

// 初始化数据
async function initData() {
  try {
    const res = await api.get('/api/policies/', { params: { date: new Date().toISOString().split('T')[0] } })
    central.value = res.data.central || []
    local.value = res.data.local || []

    centralCount.value = central.value.length
    localCount.value = local.value.length

    const savedCentral = JSON.parse(localStorage.getItem('centralSelectedIds') || '[]')
    const savedLocal = JSON.parse(localStorage.getItem('localSelectedIds') || '[]')

    centralSelectedIds.value = savedCentral.filter(id => central.value.find(c => c.id === id))
    localSelectedIds.value = savedLocal.filter(id => local.value.find(l => l.id === id))
  } catch (err) {
    console.error('加载政策数据失败:', err)
    ElMessage.error('加载政策数据失败')
  }

  legalText.value = localStorage.getItem('legalText') || ''
}

// 跳转编辑页
function goCentralEditor() { router.push('/editor/central') }
function goLocalEditor() { router.push('/editor/local') }
function goLegalEditor() { router.push('/editor/legal') }
function goAgent() { router.push('/agent') }

// 监听 localStorage 变化
window.addEventListener('storage', (e) => {
  if (e.key === 'centralSelectedIds') centralSelectedIds.value = JSON.parse(e.newValue || '[]')
  if (e.key === 'localSelectedIds') localSelectedIds.value = JSON.parse(e.newValue || '[]')
  if (e.key === 'legalText') legalText.value = e.newValue || ''
})

// ====== 导出日报功能（弹窗 loading 显示） ======
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
    legal_text: legalText.value.trim()
  }

  // 打开全局 loading
  const loading = ElLoading.service({
    lock: true,
    text: '正在导出日报，请稍候...',
    background: 'rgba(0, 0, 0, 0.7)',
    spinner: 'el-icon-loading'
  })

  try {
    const res = await api.post(
        '/api/export/',
        payload,
        { responseType: 'blob' }
    )

    // 创建下载
    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `每日财税日报（${dateStr}）.docx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    ElMessage.success('日报导出成功')
  } catch (err) {
    console.error('导出失败:', err)
    ElMessage.error('日报导出失败')
  } finally {
    loading.close()
  }
}

onMounted(() => {
  initData()
})
</script>


<style scoped>
.home-container {
  min-height: 100vh;
  padding: 40px 60px;
  max-width: 900px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  font-family: 'Inter', sans-serif;
}

.title { text-align: center; font-weight: bold; font-size: 32px; margin-bottom: 12px; font-family: 'Orbitron', sans-serif; color: #00e5ff; letter-spacing: 2px; }
.slogan { text-align: center; font-size: 16px; color: #80deea; margin-bottom: 8px; }
.welcome { text-align: center; color: #b2ebf2; margin-bottom: 20px; }

.card-container { margin-top: 30px; display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
.info-card { width: 250px; text-align: center; background: rgba(255,255,255,0.05)!important; backdrop-filter: blur(8px); border-radius: 12px; transition: all 0.3s ease; color: #fff; box-shadow: 0 0 15px rgba(0,229,255,0.1); cursor: pointer; }
.info-card:hover { transform: translateY(-4px); transition: all 0.3s ease; }
.central.info-card:hover { box-shadow: 0 0 15px #00e5ff,0 0 40px #00e5ff; }
.local.info-card:hover { box-shadow: 0 0 15px #4cafef,0 0 40px #4cafef; }
.legal.info-card:hover { box-shadow: 0 0 15px #ffb74d,0 0 40px #ffb74d; }
.agent.info-card:hover { box-shadow: 0 0 15px #ab47bc,0 0 40px #ab47bc; }
.agent .count { color:#ab47bc; }

.count { font-size: 20px; font-weight: bold; margin-top: 10px; }
.central .count { color:#00e5ff; }
.local .count { color:#4cafef; }
.legal .count { color:#ffb74d; }

.btn-container { margin-top: 40px; text-align: center; }
.glow-btn { background: linear-gradient(90deg, #00e5ff, #2979ff); border:none; box-shadow:0 0 15px rgba(0,229,255,0.6); color:white; font-weight:bold; }
.glow-btn:hover { box-shadow:0 0 25px rgba(0,229,255,1); transform:translateY(-2px); }

.progress-container {
  margin-top: 20px;
  width: 60%;
  text-align: center;
  margin-left: auto;
  margin-right: auto;
}
</style>
