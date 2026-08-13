<template>
  <div class="editor-container">
    <!-- 返回按钮 -->
    <div class="btn-back">
      <el-button class="glow-btn" type="primary" @click="goBack(false)">⬅ 不保存返回首页</el-button>
      <el-button class="glow-btn" type="primary" @click="goBack(true)">💾 保存并返回首页</el-button>
    </div>

    <!-- 页面标题 -->
    <h1 class="title centered">中央政策编辑</h1>

    <!-- 筛选下拉框 -->
    <div class="filter-container">
      <span>筛选类型：</span>
      <el-select v-model="filterType" placeholder="请选择政策类型" clearable style="width: 200px">
        <el-option label="全部" value=""></el-option>
        <el-option label="海关" value="海关"></el-option>
        <el-option label="商务" value="商务"></el-option>
        <el-option label="税务" value="税务"></el-option>
      </el-select>
    </div>

    <!-- 分组列表 -->
    <div v-for="(group, policyType) in filteredGrouped" :key="policyType" class="policy-group">
      <h3>【{{ policyType }}】</h3>
      <el-checkbox-group v-model="selectedIds">
        <div class="checkbox-list">
          <el-checkbox
              v-for="item in group"
              :key="item.id"
              :label="item.id"
              class="checkbox-item"
          >
            <div class="policy-row">
              <span class="policy-title">{{ item.title }}</span>
              <span class="publish-time">{{ formatDate(item.publish_time) }}</span>
            </div>
          </el-checkbox>
        </div>
      </el-checkbox-group>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const policies = ref([])
const selectedIds = ref([])
const filterType = ref('')  // 筛选条件

// 分组中央政策
const centralGrouped = computed(() => {
  const groups = {}
  policies.value.forEach(item => {
    if (!groups[item.type]) groups[item.type] = []
    groups[item.type].push(item)
  })
  return groups
})

// 根据筛选条件生成分组
const filteredGrouped = computed(() => {
  if (!filterType.value) return centralGrouped.value
  const filtered = {}
  Object.entries(centralGrouped.value).forEach(([type, items]) => {
    if (type === filterType.value) filtered[type] = items
  })
  return filtered
})

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2,'0')}`
}

// 返回首页并保存
function goBack(save) {
  if (save) {
    localStorage.setItem('centralSelectedIds', JSON.stringify(selectedIds.value))
    ElMessage.success('已保存中央政策选择')
  }
  router.push('/home')
}

onMounted(async () => {
  try {
    const res = await api.get('/api/policies', { params: { date: new Date().toISOString().split('T')[0] } })
    policies.value = res.data.central || []
    selectedIds.value = JSON.parse(localStorage.getItem('centralSelectedIds') || '[]')
  } catch (error) {
    console.error(error)
    ElMessage.error('加载中央政策失败')
  }
})
</script>

<style scoped>
.editor-container {
  min-height: 100vh;
  padding: 40px;
  max-width: 900px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  font-family: 'Inter', sans-serif;
}

.centered { text-align: center; }

.btn-back { display: flex; gap: 12px; margin-bottom: 20px; }

.filter-container {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  font-weight: 500;
}

.checkbox-list { display: flex; flex-direction: column; gap: 6px; }

.checkbox-item { color: #d0e6fb; word-break: break-word; white-space: normal; }

.policy-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.policy-title { font-weight: 500; flex: 1; margin-left: 8px; }

.publish-time { font-size: 12px; color: #80deea; margin-left: 8px; white-space: nowrap; }

.glow-btn {
  background: linear-gradient(90deg, #00e5ff, #2979ff);
  border: none;
  color: #fff;
  font-weight: 600;
  padding: 8px 20px;
  border-radius: 6px;
}

.glow-btn:hover {
  box-shadow: 0 0 20px #00e5ff;
  transform: translateY(-2px);
}
</style>
