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
let sessionExpiryRedirecting = false

const SKIP_LOADING_PATHS = ['/materials/tree', '/materials/tags', '/school/summary']

function shouldSkipLoading(config) {
  const url = config.url || ''
  return SKIP_LOADING_PATHS.some(p => url === p || url.startsWith(p))
}

function clearLoading() {
  if (loadingTimer) {
    clearTimeout(loadingTimer)
    loadingTimer = null
  }
  if (loadingInstance) {
    loadingInstance.close()
    loadingInstance = null
  }
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
      }, 300)
    }
    return config
  },
  (error) => {
    requestCount = Math.max(0, requestCount - 1)
    if (requestCount === 0) clearLoading()
    return Promise.reject(error)
  }
)

axios.interceptors.response.use(
  (response) => {
    if (!shouldSkipLoading(response.config)) {
      requestCount = Math.max(0, requestCount - 1)
      if (requestCount === 0) clearLoading()
    }
    return response
  },
  (error) => {
    if (!shouldSkipLoading(error.config || {})) {
      requestCount = Math.max(0, requestCount - 1)
      if (requestCount === 0) clearLoading()
    }
    if (error.response?.status === 401) {
      const currentPath = window.location.hash.replace(/^#/, '') || '/'
      if (!sessionExpiryRedirecting && !currentPath.includes('/login') && !currentPath.includes('/register')) {
        sessionExpiryRedirecting = true
        ElMessage.error('登录已过期，请重新登录')
        // A hash-only redirect preserves Pinia's in-memory login state. Changing the
        // query string forces a full navigation, so the route guard starts on login
        // with a clean auth store instead of reloading the protected current route.
        const loginUrl = new URL(window.location.href)
        loginUrl.searchParams.set('session_expired', String(Date.now()))
        loginUrl.hash = '#/login'
        window.location.replace(loginUrl.toString())
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
  const role = ref('')

  const isAdmin = computed(() => role.value === 'admin' || user.value?.role === 'admin')
  const isTeacher = computed(() => role.value === 'teacher' || user.value?.role === 'teacher')
  const displayName = computed(() => user.value?.real_name || user.value?.username || '')

  function syncAppRole() {
    try {
      const app = useAppStore()
      app.currentRole = role.value || ''
    } catch {}
  }

  async function login(username, password = '') {
    const res = await axios.post('/auth/login', { username, password })
    user.value = {
      username: res.data.username,
      real_name: res.data.real_name,
      role: res.data.role,
      is_admin: res.data.is_admin || false,
    }
    role.value = res.data.role
    isLoggedIn.value = true
    syncAppRole()
    return res.data
  }

  async function logout() {
    await axios.post('/auth/logout')
    user.value = null
    isLoggedIn.value = false
    role.value = ''
    syncAppRole()
  }

  async function fetchMe() {
    try {
      const res = await axios.get('/auth/me')
      user.value = res.data
      role.value = res.data.role || ''
      isLoggedIn.value = true
      syncAppRole()
      return res.data
    } catch {
      user.value = null
      isLoggedIn.value = false
      role.value = ''
      syncAppRole()
    }
  }

  return { user, isLoggedIn, role, isAdmin, isTeacher, displayName, login, logout, fetchMe }
})
