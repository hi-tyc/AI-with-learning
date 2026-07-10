import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { ElMessage, ElLoading } from 'element-plus'
import { useAppStore } from './app.js'

axios.defaults.withCredentials = true
axios.defaults.baseURL = '/api'

let loadingInstance = null
let requestCount = 0
let loadingTimer = null

// 不显示全局 loading 的路径前缀（config.url 不含 query params）
const SKIP_LOADING_PATHS = ['/materials/tree', '/materials/tags', '/sessions', '/usage']

function shouldSkipLoading(config) {
  const url = config.url || ''
  if (SKIP_LOADING_PATHS.some(p => url === p || url.startsWith(p))) return true
  // 关键词搜索题目也跳过 loading
  if (url === '/problems' && config.params && config.params.keyword) return true
  return false
}

axios.interceptors.request.use(
  (config) => {
    if (shouldSkipLoading(config)) return config
    requestCount++
    if (!loadingTimer) {
      loadingTimer = setTimeout(() => {
        if (requestCount > 0 && !loadingInstance) {
          loadingInstance = ElLoading.service({ lock: true, text: '加载中...', background: 'rgba(255,255,255,0.4)' })
        }
      }, 300) // 延迟300ms，短请求不显示
    }
    return config
  },
  (error) => {
    requestCount = Math.max(0, requestCount - 1)
    if (requestCount === 0) clearLoading()
    return Promise.reject(error)
  }
)

function clearLoading() {
  if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
  if (loadingInstance) { loadingInstance.close(); loadingInstance = null }
}

axios.interceptors.response.use(
  (response) => {
    if (!shouldSkipLoading(response.config)) {
      requestCount = Math.max(0, requestCount - 1)
      if (requestCount === 0) clearLoading()
    }
    return response
  },
  (error) => {
    if (!shouldSkipLoading(error.config)) {
      requestCount = Math.max(0, requestCount - 1)
      if (requestCount === 0) clearLoading()
    }
    if (error.response?.status === 401) {
      // 只在非登录页面显示过期提示
      const currentPath = window.location.hash.replace(/^#/, '') || '/'
      if (!currentPath.includes('/login')) {
        ElMessage.error('登录已过期，请重新登录')
        window.location.href = '/#/login'
      }
    } else if (error.response?.status === 429) {
      ElMessage.warning(error.response?.data?.detail || '请求过于频繁，请稍后重试')
    } else if (error.response?.status >= 500) {
      ElMessage.error('服务器错误，请稍后重试')
    } else if (error.message === 'Network Error' && !window.location.hash.includes('/login')) {
      ElMessage.error('网络连接失败，请检查后端是否启动')
    }
    return Promise.reject(error)
  }
)

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isLoggedIn = ref(false)
  const subject = ref('数学')
  const isAdmin = computed(() => user.value?.is_admin === true || user.value?.username === 'root')

  function syncAppSubject() {
    try {
      const app = useAppStore()
      app.currentSubject = subject.value
    } catch {}
  }

  async function login(username, selectedSubject = '数学', password = '') {
    const res = await axios.post('/auth/login', { username, password, subject: selectedSubject })
    user.value = { username: res.data.username, subject: res.data.subject, is_admin: res.data.is_admin || false }
    subject.value = res.data.subject
    isLoggedIn.value = true
    syncAppSubject()
    return res.data
  }

  async function logout() {
    await axios.post('/auth/logout')
    user.value = null
    isLoggedIn.value = false
    subject.value = '数学'
    syncAppSubject()
  }

  async function fetchMe() {
    try {
      const res = await axios.get('/auth/me')
      user.value = res.data
      subject.value = res.data.subject || '数学'
      isLoggedIn.value = true
      syncAppSubject()
      return res.data
    } catch {
      user.value = null
      isLoggedIn.value = false
      subject.value = '数学'
      syncAppSubject()
    }
  }

  async function switchSubject(newSubject) {
    try {
      const res = await axios.put('/auth/subject', { subject: newSubject })
      subject.value = res.data.subject
      user.value = { ...user.value, subject: res.data.subject }
      syncAppSubject()
      ElMessage.success(`已切换到 ${newSubject} 模式`)
      return res.data
    } catch (e) {
      ElMessage.error('切换学科失败')
    }
  }

  return { user, isLoggedIn, subject, isAdmin, login, logout, fetchMe, switchSubject }
})
