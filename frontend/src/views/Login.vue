<template>
  <div class="login-container">
    <h2 class="login-title">登录</h2>
    <el-input
        v-model="username"
        placeholder="用户名"
        class="login-input"
        clearable
    />
    <el-input
        v-model="password"
        type="password"
        placeholder="密码"
        class="login-input"
        clearable
    />
    <el-button class="glow-btn" type="primary" @click="login">
      登录
    </el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const username = ref('')
const password = ref('')
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
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  color: #e0f7fa;
  font-family: 'Inter', sans-serif;
  padding: 20px;
  box-sizing: border-box;
}

.login-title {
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 30px;
  font-family: 'Orbitron', sans-serif;
  color: #00e5ff;
  letter-spacing: 2px;
  text-align: center;
}

.login-input {
  width: 250px;
  margin-bottom: 20px;
  font-size: 15px;
  color: #d0e6fb;
  background: rgba(255, 255, 255, 0.07);
  border-radius: 8px;
  padding: 10px;
  border: none;
  box-shadow: inset 0 0 10px #00bfff;
  transition: all 0.3s ease;
}

.login-input input {
  color: #d0e6fb !important;
}

.login-input:focus-within {
  box-shadow: 0 0 12px #00e5ff;
  background: rgba(255, 255, 255, 0.15);
}

.glow-btn {
  background: linear-gradient(90deg, #00e5ff, #2979ff);
  border: none;
  box-shadow: 0 0 15px rgba(0, 229, 255, 0.6);
  color: white !important;
  font-weight: 600;
  font-size: 16px;
  padding: 10px 28px;
  border-radius: 6px;
  transition: all 0.3s ease;
  cursor: pointer;
  user-select: none;
}

.glow-btn:hover {
  box-shadow: 0 0 25px rgba(0, 229, 255, 1);
  transform: translateY(-2px);
}
</style>
