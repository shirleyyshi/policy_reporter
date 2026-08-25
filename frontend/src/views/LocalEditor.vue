<template>
  <div class="editor-container">
    <!-- 顶部导航条 -->
    <header class="top-bar">
      <div class="brand">
        <span class="brand-dot"></span>
        <span class="brand-name">地方政策编辑</span>
      </div>
      <div class="top-actions">
        <el-button text class="text-btn" @click="goBack(false)">不保存返回</el-button>
        <el-button class="save-btn" type="primary" @click="goBack(true)">
          <span>💾 保存并返回</span>
        </el-button>
      </div>
    </header>

    <!-- 信息条 -->
    <section class="info-bar">
      <div class="info-left">
        <span class="info-item">
          <span class="info-label">日期</span>
          <span class="info-value">{{ selectedDate }}</span>
        </span>
        <span class="info-divider"></span>
        <span class="info-item">
          <span class="info-label">总数</span>
          <span class="info-value">{{ policies.length }} 条</span>
        </span>
        <span class="info-divider"></span>
        <span class="info-item">
          <span class="info-label">已选</span>
          <span class="info-value accent">{{ selectedIds.length }} 条</span>
        </span>
      </div>
      <div class="filter-container">
        <span class="filter-label">地区</span>
        <el-select v-model="filterProvince" placeholder="全部" clearable size="small" class="filter-select">
          <el-option label="全部" value=""></el-option>
          <el-option
            v-for="province in provinces"
            :key="province"
            :label="province"
            :value="province"
          ></el-option>
        </el-select>
      </div>
    </section>

    <!-- 分组卡片 -->
    <div v-if="Object.keys(filteredGrouped).length === 0" class="empty-state">
      <p>当前筛选下没有政策</p>
      <p class="hint-sub">试试更换筛选条件或切换日期</p>
    </div>

    <div v-for="(group, province) in filteredGrouped" :key="province" class="policy-group">
      <div class="group-header">
        <span class="group-tag">{{ province }}</span>
        <span class="group-count">{{ group.length }} 条</span>
      </div>
      <el-checkbox-group v-model="selectedIds" class="checkbox-list">
        <label
          v-for="item in group"
          :key="item.id"
          class="policy-item"
          :class="{ checked: selectedIds.includes(item.id) }"
        >
          <el-checkbox :value="item.id">
            <span class="policy-title link" @click.prevent="goDetail(item.id)">{{ item.title }}</span>
          </el-checkbox>
          <span class="publish-time">{{ formatDate(item.publish_time) }}</span>
        </label>
      </el-checkbox-group>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { ElMessage } from 'element-plus'
import { selectionStore } from '@/stores/selection'

const router = useRouter()
const policies = ref([])
// 绑定到内存 store（刷新即清空）
const selectedIds = computed({
  get: () => selectionStore.localIds,
  set: (val) => { selectionStore.localIds = val }
})
const filterProvince = ref('')
const selectedDate = ref(localStorage.getItem('selectedDate') || new Date().toISOString().split('T')[0])
// 进入页面时的选择快照：勾选实时写入 store，"不保存返回"时用它回滚
let snapshotIds = null

const provinces = computed(() => {
  const set = new Set(policies.value.map(p => p.province))
  return Array.from(set).sort()
})

const localGrouped = computed(() => {
  const groups = {}
  policies.value.forEach(item => {
    if (!groups[item.province]) groups[item.province] = []
    groups[item.province].push(item)
  })
  return groups
})

const filteredGrouped = computed(() => {
  if (!filterProvince.value) return localGrouped.value
  const filtered = {}
  if (localGrouped.value[filterProvince.value]) {
    filtered[filterProvince.value] = localGrouped.value[filterProvince.value]
  }
  return filtered
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`
}

function goBack(save) {
  if (save) {
    // 已通过 computed setter 实时写入 store，这里只提示
    ElMessage.success('已保存地方政策选择')
  } else {
    // 回滚到进入页面时的选择
    if (snapshotIds) selectionStore.localIds = [...snapshotIds]
  }
  router.push('/home')
}

function goDetail(id) {
  router.push(`/policy/local/${id}`)
}

onMounted(async () => {
  // 快照要在任何修改前取（下面的过滤也会改 store）
  snapshotIds = [...selectionStore.localIds]
  try {
    const res = await api.get('/api/policies/', { params: { date: selectedDate.value } })
    policies.value = res.data.local || []
    // 只保留当前列表中存在的选中 id，避免"已选 > 总数"
    const idSet = new Set(policies.value.map(p => p.id))
    selectionStore.localIds = selectionStore.localIds.filter(id => idSet.has(id))
  } catch (error) {
    console.error(error)
    ElMessage.error('加载地方政策失败')
  }
})
</script>

<style scoped>
.editor-container {
  min-height: 100vh;
  padding: 24px 48px 60px;
  max-width: 1100px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  box-sizing: border-box;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(0,229,255,0.15);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #00e5ff;
}
.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00e5ff;
  box-shadow: 0 0 12px #00e5ff;
}
.top-actions { display: flex; gap: 12px; align-items: center; }
.text-btn { color: #80deea !important; }
.text-btn:hover { color: #00e5ff !important; }
.save-btn {
  background: linear-gradient(90deg, #00e5ff, #2979ff) !important;
  border: none !important;
  color: #0f2027 !important;
  font-weight: 600 !important;
  border-radius: 8px !important;
  box-shadow: 0 4px 12px rgba(0,229,255,0.3);
}
.save-btn:hover { box-shadow: 0 6px 18px rgba(0,229,255,0.5); transform: translateY(-1px); }

.info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(0,229,255,0.15);
  border-radius: 12px;
  padding: 14px 20px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}
.info-left { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.info-item { display: flex; align-items: center; gap: 6px; }
.info-label { font-size: 12px; color: #80deea; }
.info-value { font-size: 14px; color: #e0f7fa; font-weight: 500; }
.info-value.accent { color: #00e5ff; font-weight: 700; }
.info-divider { width: 1px; height: 14px; background: rgba(0,229,255,0.2); }
.filter-container { display: flex; align-items: center; gap: 8px; }
.filter-label { font-size: 12px; color: #80deea; }
.filter-select { width: 140px; }

.policy-group {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  margin-bottom: 16px;
  overflow: hidden;
}
.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  background: rgba(0,229,255,0.06);
  border-bottom: 1px solid rgba(0,229,255,0.12);
}
.group-tag {
  font-size: 14px;
  font-weight: 600;
  color: #00e5ff;
  letter-spacing: 1px;
}
.group-count { font-size: 12px; color: #80deea; }

.checkbox-list { display: flex; flex-direction: column; }
.policy-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  transition: background 0.2s;
  cursor: pointer;
}
.policy-item:last-child { border-bottom: none; }
.policy-item:hover { background: rgba(0,229,255,0.05); }
.policy-item.checked { background: rgba(0,229,255,0.08); }
.policy-title { color: #e0f7fa; font-size: 14px; flex: 1; }
.policy-title.link { cursor: pointer; transition: color 0.2s; }
.policy-title.link:hover { color: #00e5ff; }
.publish-time {
  font-size: 12px;
  color: #80deea;
  margin-left: 12px;
  white-space: nowrap;
  background: rgba(0,229,255,0.08);
  padding: 2px 8px;
  border-radius: 4px;
}

.policy-item :deep(.el-checkbox__label) { color: #e0f7fa; }
.policy-item :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background: #00e5ff;
  border-color: #00e5ff;
}
.policy-item :deep(.el-checkbox__inner) {
  background: rgba(255,255,255,0.1);
  border-color: rgba(0,229,255,0.3);
}
.policy-item :deep(.el-checkbox__input.is-checked + .el-checkbox__label) { color: #00e5ff; }

.filter-select :deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.08) !important;
  box-shadow: 0 0 0 1px rgba(0,229,255,0.2) inset !important;
  border-radius: 6px !important;
}
.filter-select :deep(.el-input__inner) { color: #e0f7fa !important; }

.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: #80deea;
  background: rgba(255,255,255,0.03);
  border-radius: 12px;
  border: 1px dashed rgba(0,229,255,0.2);
}
.hint-sub { font-size: 13px; color: #607d8b; margin-top: 6px; }
</style>
