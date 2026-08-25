<template>
  <div class="editor-container">
    <!-- 顶部导航条 -->
    <header class="top-bar">
      <div class="brand">
        <span class="brand-dot"></span>
        <span class="brand-name">合规资讯编辑</span>
      </div>
      <div class="top-actions">
        <el-button text class="text-btn" @click="returnWithoutSave">不保存返回</el-button>
        <el-button class="save-btn" type="primary" @click="saveAndReturn">
          <span>💾 保存并返回</span>
        </el-button>
      </div>
    </header>

    <!-- 信息条 -->
    <section class="info-bar">
      <span class="info-item">
        <span class="info-label">状态</span>
        <span class="info-value" :class="legalInput.trim() ? 'done' : 'pending'">
          {{ legalInput.trim() ? '已编写' : '未编写' }}
        </span>
      </span>
      <span class="info-divider"></span>
      <span class="info-item">
        <span class="info-label">字数</span>
        <span class="info-value">{{ legalInput.length }} 字</span>
      </span>
    </section>

    <!-- 编辑区 -->
    <div class="editor-card">
      <div class="editor-header">
        <span class="editor-title">法律法规及合规资讯正文</span>
        <span class="editor-hint">支持复制粘贴文本</span>
      </div>
      <textarea
        v-model="legalInput"
        placeholder="请输入法律法规及合规资讯内容，可以复制粘贴文本。"
        class="legal-textarea"
      ></textarea>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { selectionStore } from '@/stores/selection'

const router = useRouter()
// 绑定到内存 store（刷新即清空）
const legalInput = computed({
  get: () => selectionStore.legalText,
  set: (val) => { selectionStore.legalText = val }
})

// 进入页面时的快照："不保存返回"时回滚
let snapshotText = ''
onMounted(() => {
  snapshotText = selectionStore.legalText
})

function saveAndReturn() {
  selectionStore.legalText = legalInput.value.trim()
  ElMessage.success('已保存合规资讯')
  router.push('/home')
}

function returnWithoutSave() {
  selectionStore.legalText = snapshotText
  router.push('/home')
}
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
  align-items: center;
  gap: 16px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(0,229,255,0.15);
  border-radius: 12px;
  padding: 14px 20px;
  margin-bottom: 24px;
}
.info-item { display: flex; align-items: center; gap: 6px; }
.info-label { font-size: 12px; color: #80deea; }
.info-value { font-size: 14px; color: #e0f7fa; font-weight: 500; }
.info-value.done { color: #66bb6a; }
.info-value.pending { color: #ffb74d; }
.info-divider { width: 1px; height: 14px; background: rgba(0,229,255,0.2); }

.editor-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(0,229,255,0.15);
  border-radius: 12px;
  overflow: hidden;
}
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  background: rgba(0,229,255,0.06);
  border-bottom: 1px solid rgba(0,229,255,0.12);
}
.editor-title { font-size: 14px; font-weight: 600; color: #00e5ff; }
.editor-hint { font-size: 12px; color: #80deea; }

.legal-textarea {
  width: 100%;
  height: 420px;
  padding: 18px;
  font-size: 14px;
  border: none;
  resize: vertical;
  background: rgba(255, 255, 255, 0.05);
  color: #e0f7fa;
  font-family: 'Inter', -apple-system, sans-serif;
  line-height: 1.6;
  box-sizing: border-box;
  outline: none;
  transition: background 0.3s ease;
}

.legal-textarea:focus {
  background: rgba(255, 255, 255, 0.08);
}

.legal-textarea::placeholder { color: #607d8b; }
</style>
