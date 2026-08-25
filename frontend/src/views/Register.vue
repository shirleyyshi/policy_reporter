<template>
  <div class="register-container">
    <div class="register-card">
      <div class="brand-area">
        <div class="brand-logo">PR</div>
        <h1>创建账户</h1>
        <p>注册后即可使用 Policy Reporter</p>
      </div>

      <el-form @submit.prevent="register">
        <div class="form-group">
          <label>用户名</label>
          <el-input v-model="username" placeholder="请输入用户名" clearable />
        </div>
        <div class="form-group">
          <label>密码</label>
          <el-input v-model="password" type="password" placeholder="至少 8 位" show-password />
        </div>
        <div class="form-group">
          <label>确认密码</label>
          <el-input v-model="confirmPassword" type="password" placeholder="请再次输入密码" show-password @keyup.enter="register" />
        </div>
        <el-button class="register-btn" type="primary" :loading="registering" @click="register">
          {{ registering ? '注册中...' : '注 册' }}
        </el-button>
      </el-form>

      <div class="login-link">已有帐户？<router-link to="/login">返回登录</router-link></div>
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
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
}
.register-card {
  width: 400px;
  padding: 40px 36px 30px;
  border: 1px solid rgba(0, 229, 255, .2);
  border-radius: 20px;
  background: rgba(255, 255, 255, .07);
  backdrop-filter: blur(20px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, .4), 0 0 0 1px rgba(255,255,255,.05) inset;
}
.brand-area { text-align: center; margin-bottom: 28px; }
.brand-logo {
  width: 56px; height: 56px; margin: 0 auto 14px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  color: #0f2027; background: #00e5ff; font-weight: 800;
}
h1 {
  margin: 0 0 8px;
  color: #00e5ff;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 2px;
}
.brand-area p { margin: 0; color: #80deea; font-size: 13px; }
.form-group { display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px; }
.form-group label { color: #b2ebf2; font-size: 13px; }
.register-btn { width: 100%; height: 44px; margin-top: 4px; background: linear-gradient(90deg, #00e5ff, #2979ff) !important; border: 0 !important; color: #0f2027 !important; font-weight: 600; }
.login-link { margin-top: 20px; text-align: center; color: #80deea; font-size: 13px; }
a { color: #00e5ff; text-decoration: none; font-weight: 600; }
a:hover { text-decoration: underline; }
</style>
