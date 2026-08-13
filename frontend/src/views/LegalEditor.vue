<template>
  <div class="editor-container">
    <div class="btn-back">
      <el-button class="glow-btn" type="primary" @click="returnWithoutSave">⬅ 不保存返回首页</el-button>
      <el-button class="glow-btn" type="primary" @click="saveAndReturn">💾 保存并返回首页</el-button>
    </div>

    <h1 class="title centered">法律法规及合规资讯编辑</h1>

    <textarea
        v-model="legalInput"
        placeholder="请输入法律法规及合规资讯内容，可以复制粘贴文本。"
        class="legal-textarea"
    ></textarea>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const legalInput = ref('')

// 初始化输入框内容
onMounted(() => {
  legalInput.value = localStorage.getItem('legalText') || ''
})

// 保存并返回首页
function saveAndReturn() {
  localStorage.setItem('legalText', legalInput.value.trim())
  router.push('/home')
}

// 不保存直接返回首页
function returnWithoutSave() {
  router.push('/home')
}
</script>

<style scoped>
.editor-container {
  min-height: 100vh;
  padding: 40px 60px;
  max-width: 900px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  font-family: 'Inter', sans-serif;
  box-sizing: border-box;
}

.centered { text-align: center; }

.btn-back {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.legal-textarea {
  width: 100%;
  height: 300px;
  padding: 12px;
  font-size: 15px;
  border-radius: 10px;
  border: none;
  resize: vertical;
  background: rgba(255, 255, 255, 0.07);
  color: #d0e6fb;
  box-shadow: inset 0 0 10px #00bfff;
  transition: box-shadow 0.3s ease;
  font-family: 'Inter', sans-serif;
}

.legal-textarea:focus {
  outline: none;
  box-shadow: 0 0 12px #00e5ff;
  background: rgba(255, 255, 255, 0.15);
}


.glow-btn {
  background: linear-gradient(90deg, #00e5ff, #2979ff);
  border: none;
  color: white !important;
  font-weight: 600;
  font-size: 14px;
  padding: 10px 20px;
  border-radius: 6px;
  box-shadow: 0 0 15px rgba(0, 229, 255, 0.6);
  cursor: pointer;
  user-select: none;
  transition: all 0.3s ease;
}

.glow-btn:hover {
  box-shadow: 0 0 25px rgba(0, 229, 255, 1);
  transform: translateY(-2px);
}
</style>



