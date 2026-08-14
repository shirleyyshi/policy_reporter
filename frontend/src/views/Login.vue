<template>
  <div class="login-container">
    <!-- 背景装饰 -->
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>

    <div class="login-card">
      <!-- 品牌区 -->
      <div class="brand-area">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <h1 class="brand-title">Policy Reporter</h1>
        <p class="brand-sub">财税政策日报 · 智能生成平台</p>
      </div>

      <!-- 表单区 -->
      <div class="form-area">
        <div class="form-group">
          <label class="form-label">用户名</label>
          <el-input
            v-model="username"
            placeholder="请输入用户名"
            class="form-input"
            clearable
            @keyup.enter="login"
          >
            <template #prefix>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="color:#80deea">
                <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
              </svg>
            </template>
          </el-input>
        </div>

        <div class="form-group">
          <label class="form-label">密码</label>
          <el-input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            class="form-input"
            clearable
            show-password
            @keyup.enter="login"
          >
            <template #prefix>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="color:#80deea">
                <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/>
              </svg>
            </template>
          </el-input>
        </div>

        <el-button
          class="login-btn"
          type="primary"
          :loading="logging"
          @click="login"
        >
          {{ logging ? '登录中...' : '登 录' }}
        </el-button>
      </div>

      <div class="footer-note">
        ReAct Agent · RAG · Docx Export
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const username = ref('')
const password = ref('')
const logging = ref(false)
const router = useRouter()

async function login() {
  if (!username.value.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!password.value.trim()) {
    ElMessage.warning('请输入密码')
    return
  }
  logging.value = true
  try {
    const res = await api.post('/api/auth/login/', {
      username: username.value,
      password: password.value
    })
    localStorage.setItem('access_token', res.data.access)
    localStorage.setItem('refresh_token', res.data.refresh)
    localStorage.setItem('username', username.value)
    router.push('/home')
  } catch (err) {
    if (err.response?.status === 401) {
      ElMessage.error('用户名或密码错误')
    } else {
      ElMessage.error('登录失败，请检查网络或后端服务')
    }
  } finally {
    logging.value = false
  }
}
</script>

<style scoped>
.login-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  font-family: 'Inter', -apple-system, sans-serif;
  overflow: hidden;
}

/* 背景装饰光球 */
.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.3;
  animation: float 12s ease-in-out infinite;
}
.orb-1 {
  width: 300px;
  height: 300px;
  background: #00e5ff;
  top: -100px;
  left: -100px;
}
.orb-2 {
  width: 400px;
  height: 400px;
  background: #2979ff;
  bottom: -150px;
  right: -100px;
  animation-delay: -4s;
}
.orb-3 {
  width: 250px;
  height: 250px;
  background: #ab47bc;
  top: 50%;
  left: 60%;
  animation-delay: -8s;
}
@keyframes float {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(30px, -30px); }
  66% { transform: translate(-20px, 20px); }
}

/* 登录卡片 */
.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-radius: 20px;
  padding: 40px 36px 28px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255,255,255,0.05) inset;
}

/* 品牌区 */
.brand-area {
  text-align: center;
  margin-bottom: 32px;
}
.brand-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(0,229,255,0.2), rgba(41,121,255,0.2));
  border: 1px solid rgba(0,229,255,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #00e5ff;
  box-shadow: 0 0 24px rgba(0,229,255,0.2);
}
.brand-title {
  font-size: 24px;
  font-weight: 700;
  color: #00e5ff;
  letter-spacing: 2px;
  margin: 0 0 6px;
}
.brand-sub {
  font-size: 12px;
  color: #80deea;
  margin: 0;
  letter-spacing: 1px;
}

/* 表单区 */
.form-area { display: flex; flex-direction: column; gap: 18px; }
.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-label {
  font-size: 13px;
  color: #b2ebf2;
  font-weight: 500;
}
.form-input {
  --el-input-bg-color: rgba(255, 255, 255, 0.08);
  --el-input-border-color: rgba(0, 229, 255, 0.2);
  --el-input-hover-border-color: rgba(0, 229, 255, 0.5);
  --el-input-focus-border-color: #00e5ff;
  --el-input-text-color: #e0f7fa;
  --el-input-placeholder-color: #607d8b;
}
.form-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.08) !important;
  border-radius: 10px !important;
  box-shadow: 0 0 0 1px rgba(0, 229, 255, 0.2) inset !important;
  padding: 10px 14px;
  transition: all 0.3s ease;
}
.form-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px rgba(0, 229, 255, 0.5) inset !important;
}
.form-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #00e5ff inset, 0 0 12px rgba(0, 229, 255, 0.3) !important;
}
.form-input :deep(.el-input__inner) {
  color: #e0f7fa !important;
  height: 28px;
}
.form-input :deep(.el-input__inner::placeholder) {
  color: #607d8b !important;
}

/* 登录按钮 */
.login-btn {
  width: 100%;
  height: 44px;
  background: linear-gradient(90deg, #00e5ff, #2979ff) !important;
  border: none !important;
  color: #0f2027 !important;
  font-weight: 600 !important;
  font-size: 15px !important;
  letter-spacing: 4px;
  border-radius: 10px !important;
  box-shadow: 0 4px 16px rgba(0, 229, 255, 0.4);
  transition: all 0.3s ease;
  margin-top: 8px;
}
.login-btn:hover:not(:disabled) {
  box-shadow: 0 6px 24px rgba(0, 229, 255, 0.6);
  transform: translateY(-2px);
}

/* 底部说明 */
.footer-note {
  text-align: center;
  font-size: 11px;
  color: #607d8b;
  margin-top: 24px;
  letter-spacing: 1px;
}
</style>
