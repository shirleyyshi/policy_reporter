import axios from 'axios'

// 创建 axios 实例，baseURL 从环境变量读取，未配置时回退到空串（用相对路径）
const baseURL = import.meta.env.VITE_API_BASE || ''

if (!baseURL && import.meta.env.DEV) {
  console.warn('[api] VITE_API_BASE 未配置，使用相对路径。生产环境需确保 Nginx 反代 /api 到后端。')
}

const api = axios.create({
  baseURL,
  timeout: 30000
})

// 请求拦截器：自动附加 JWT token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 时清除 token 并跳转登录页
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('username')
      window.location.href = '/login'
    }
    // 网络错误 / CORS 明确提示
    if (error.message === 'Network Error') {
      console.error('[api] 网络错误：可能是后端未启动或 CORS 配置问题')
    }
    return Promise.reject(error)
  }
)

export default api
