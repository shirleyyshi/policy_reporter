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

function clearAuth() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('username')
  window.location.href = '/login'
}

// 并发 401 时只发起一次 refresh，其余请求等待同一 Promise（单飞 single-flight）
let refreshingPromise = null

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null
  if (!refreshingPromise) {
    // 用裸 axios 调用，避免走本拦截器造成递归
    refreshingPromise = axios
      .post(`${baseURL}/api/auth/refresh/`, { refresh: refreshToken })
      .then(res => {
        localStorage.setItem('access_token', res.data.access)
        return res.data.access
      })
      .catch(() => null)
      .finally(() => { refreshingPromise = null })
  }
  return refreshingPromise
}

// 响应拦截器：
// - 401 且非登录接口：尝试 refresh（access 过期但 refresh 仍有效），成功后重放原请求
// - refresh 失败或 refresh token 缺失/过期：清除凭据跳登录页
api.interceptors.response.use(
  response => response,
  async error => {
    const original = error.config
    const status = error.response?.status
    const isLoginUrl = original?.url?.includes('/api/auth/login/')

    if (status === 401 && original && !original._retried && !isLoginUrl) {
      const newToken = await refreshAccessToken()
      if (newToken) {
        original._retried = true
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
      clearAuth()
    } else if (status === 401 && !isLoginUrl) {
      // 已重放过仍 401（refresh token 也失效）：登出
      clearAuth()
    }

    // 网络错误 / CORS 明确提示
    if (error.message === 'Network Error') {
      console.error('[api] 网络错误：可能是后端未启动或 CORS 配置问题')
    }
    return Promise.reject(error)
  }
)

export default api
