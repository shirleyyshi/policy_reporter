<template>
  <div class="register-container">
    <div class="register-card">
      <div class="brand-area">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <h1 class="brand-title">创建账户</h1>
        <p class="brand-sub">注册后即可使用 Policy Reporter</p>
      </div>

      <el-form @submit.prevent="register">
        <div class="form-group">
          <label>用户名</label>
          <el-input v-model="username" placeholder="请输入用户名" class="form-input" clearable />
        </div>
        <div class="form-group">
          <label>密码</label>
          <el-input v-model="password" type="password" placeholder="至少 8 位" class="form-input" show-password />
        </div>
        <div class="form-group">
          <label>确认密码</label>
          <el-input v-model="confirmPassword" type="password" placeholder="请再次输入密码" class="form-input" show-password @keyup.enter="register" />
        </div>
        <el-button class="register-btn" type="primary" :loading="registering" @click="register">
          {{ registering ? '注册中...' : '注 册' }}
        </el-button>
      </el-form>

      <div class="login-link">已有账户？<router-link to="/login">返回登录</router-link></div>
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
const confirmPassword = ref('')
const registering = ref(false)
const router = useRouter()

async function register() {
  const name = username.value.trim()
  if (!name) return ElMessage.warning('请输入用户名')
  if (password.value.length < 8) return ElMessage.warning('密码至少需要 8 位')
  if (password.value !== confirmPassword.value) return ElMessage.warning('两次输入的密码不一致')

  registering.value = true
  try {
    await api.post('/api/auth/register/', { username: name, password: password.value })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err) {
    const detail = err.response?.data?.detail || err.response?.data?.username
    ElMessage.error(detail || '注册失败，请检查网络或输入内容')
  } finally {
    registering.value = false
  }
}
</script>

<style scoped>
.register-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  overflow: hidden;
}
.register-container::before,
.register-container::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.25;
  pointer-events: none;
}
.register-container::before {
  width: 300px;
  height: 300px;
  background: #00e5ff;
  top: -100px;
  left: -100px;
}
.register-container::after {
  width: 400px;
  height: 400px;
  background: #2979ff;
  right: -120px;
  bottom: -160px;
}
.register-card {
  position: relative;
  z-index: 1;
  width: 400px;
  padding: 40px 36px 28px;
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(20px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05) inset;
  box-sizing: border-box;
}
.brand-area {
  text-align: center;
  margin-bottom: 32px;
}
.brand-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(0, 229, 255, 0.2), rgba(41, 121, 255, 0.2));
  border: 1px solid rgba(0, 229, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #00e5ff;
  box-shadow: 0 0 24px rgba(0, 229, 255, 0.2);
}
.brand-title {
  margin: 0 0 6px;
  color: #00e5ff;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 2px;
}
.brand-sub {
  margin: 0;
  color: #80deea;
  font-size: 12px;
  letter-spacing: 1px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 18px;
}
.form-group label {
  color: #b2ebf2;
  font-size: 13px;
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
  height: 28px;
  color: #e0f7fa !important;
}
.form-input :deep(.el-input__inner::placeholder) {
  color: #607d8b !important;
}
.register-btn {
  width: 100%;
  height: 44px;
  margin-top: 4px;
  background: linear-gradient(90deg, #00e5ff, #2979ff) !important;
  border: none !important;
  border-radius: 10px !important;
  color: #0f2027 !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  letter-spacing: 4px;
  box-shadow: 0 4px 16px rgba(0, 229, 255, 0.4);
  transition: all 0.3s ease;
}
.register-btn:hover:not(:disabled) {
  box-shadow: 0 6px 24px rgba(0, 229, 255, 0.6);
  transform: translateY(-2px);
}
.login-link {
  margin-top: 18px;
  text-align: center;
  color: #80deea;
  font-size: 13px;
}
a {
  color: #00e5ff;
  text-decoration: none;
  font-weight: 600;
}
a:hover {
  text-decoration: underline;
}

@media (max-width: 480px) {
  .register-card {
    width: calc(100% - 32px);
    padding: 32px 24px 24px;
  }
}
</style>
