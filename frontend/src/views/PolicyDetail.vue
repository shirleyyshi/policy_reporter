<template>
  <div class="detail-container">
    <!-- 顶部导航 -->
    <header class="top-bar">
      <div class="brand">
        <span class="brand-dot"></span>
        <span class="brand-name">{{ policy.source === 'central' ? '中央政策详情' : '地方法规详情' }}</span>
      </div>
      <el-button text class="text-btn" @click="goBack">‹ 返回列表</el-button>
    </header>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="error" class="empty-state">
      <p>{{ error }}</p>
      <el-button text class="text-btn" @click="goBack">返回列表</el-button>
    </div>

    <template v-else>
      <!-- 标题与元信息 -->
      <section class="head-card">
        <h1 class="policy-title">{{ policy.title }}</h1>
        <div class="meta-row">
          <span v-if="policy.source === 'central'" class="meta-tag central-tag">中央 · {{ policy.type || '未分类' }}</span>
          <span v-else class="meta-tag local-tag">{{ policy.province }} · {{ policy.type || '未分类' }}</span>
          <span class="meta-item">发文日期 {{ formatDate(policy.publish_time) }}</span>
          <span v-if="policy.crawled_at" class="meta-item">采集于 {{ formatDateTime(policy.crawled_at) }}</span>
          <span v-else class="meta-item manual">手动录入</span>
        </div>
        <a
          v-if="policy.source_url"
          :href="policy.source_url"
          target="_blank"
          rel="noopener noreferrer"
          class="source-link"
        >
          查看原文 ↗
        </a>
      </section>

      <!-- 正文 -->
      <section class="content-card">
        <div class="content-text">{{ policy.content || '（无正文内容）' }}</div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const route = useRoute()
const router = useRouter()

const policy = ref({})
const loading = ref(true)
const error = ref('')

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return `${formatDate(dateStr)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function goBack() {
  router.back()
}

onMounted(async () => {
  const { source, id } = route.params
  if (!['central', 'local'].includes(source) || !id) {
    error.value = '链接参数错误'
    loading.value = false
    return
  }
  try {
    const res = await api.get('/api/policies/detail/', { params: { source, id } })
    policy.value = res.data
  } catch (err) {
    error.value = err.response?.status === 404 ? '政策不存在或已被删除' : '加载失败，请稍后重试'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.detail-container {
  min-height: 100vh;
  padding: 24px 48px 60px;
  max-width: 1100px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  box-sizing: border-box;
}

/* 顶部导航 */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #80deea;
  font-size: 14px;
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
.text-btn {
  color: #80deea !important;
  font-size: 14px;
}
.text-btn:hover { color: #00e5ff !important; }

/* 标题卡片 */
.head-card {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 24px 28px;
  margin-bottom: 16px;
}
.policy-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.6;
  color: #fff;
  margin: 0 0 14px;
}
.meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}
.meta-tag {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
  font-weight: 500;
}
.central-tag {
  background: rgba(0, 229, 255, 0.15);
  color: #00e5ff;
  border: 1px solid rgba(0, 229, 255, 0.3);
}
.local-tag {
  background: rgba(76, 175, 239, 0.15);
  color: #4cafef;
  border: 1px solid rgba(76, 175, 239, 0.3);
}
.meta-item {
  font-size: 12px;
  color: #80deea;
}
.meta-item.manual { color: #ffb74d; }
.source-link {
  display: inline-block;
  font-size: 13px;
  color: #00e5ff;
  text-decoration: none;
  border-bottom: 1px dashed rgba(0, 229, 255, 0.4);
  padding-bottom: 1px;
  transition: all 0.2s;
}
.source-link:hover { border-bottom-style: solid; text-shadow: 0 0 8px rgba(0, 229, 255, 0.4); }

/* 正文卡片 */
.content-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 28px 32px;
}
.content-text {
  font-size: 14px;
  line-height: 2;
  color: #b2ebf2;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 加载与空状态 */
.loading-state, .empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #80deea;
}
.empty-state p { margin-bottom: 12px; }
@media (max-width: 640px) {
  .detail-container { padding: 20px 16px 40px; }
  .top-bar { align-items: flex-start; gap: 12px; }
  .head-card { padding: 20px 18px; }
  .content-card { padding: 22px 18px; }
  .policy-title { font-size: 18px; }
}
</style>
