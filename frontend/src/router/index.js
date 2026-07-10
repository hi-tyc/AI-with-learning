import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useAppStore } from '../stores/app.js'

const routes = [
  // --- 登录页 ---
  { path: '/login', component: () => import('../views/Login.vue') },

  // --- 数学前端 (共用页面，去掉复习资料) ---
  { path: '/upload', component: () => import('../views/Upload.vue'), meta: { auth: true, subject: '数学' } },
  { path: '/solve', component: () => import('../views/Solve.vue'), meta: { auth: true, subject: '数学' } },
  { path: '/manage', component: () => import('../views/Manage.vue'), meta: { auth: true, subject: '数学' } },
  { path: '/library', redirect: '/manage' },
  { path: '/usage', component: () => import('../views/Usage.vue'), meta: { auth: true, subject: '数学' } },
  { path: '/problem/:id', component: () => import('../views/ProblemDetail.vue'), meta: { auth: true, subject: '数学' } },
  { path: '/settings/system', component: () => import('../views/SystemSettings.vue'), meta: { auth: true } },
  { path: '/settings', redirect: '/settings/system', meta: { auth: true } },
  { path: '/settings/profile', component: () => import('../views/Profile.vue'), meta: { auth: true } },
  { path: '/', redirect: '/solve' },

  // --- 英语前端 (独立页面) ---
  { path: '/english-upload', component: () => import('../views/EnglishUpload.vue'), meta: { auth: true, subject: '英语' } },
  { path: '/english/solve', component: () => import('../views/english/Solve.vue'), meta: { auth: true, subject: '英语' } },
  { path: '/english/library', component: () => import('../views/english/Library.vue'), meta: { auth: true, subject: '英语' } },
  { path: '/english/doc/:sourceFile', component: () => import('../views/english/DocDetail.vue'), meta: { auth: true, subject: '英语' } },
  { path: '/english/usage', component: () => import('../views/english/Usage.vue'), meta: { auth: true, subject: '英语' } },
  { path: '/english/wrong-book', component: () => import('../views/english/WrongBook.vue'), meta: { auth: true, subject: '英语' } },
  { path: '/english', redirect: '/english-upload' },

  // --- 对话模式 ---
  { path: '/chat', component: () => import('../views/Chat.vue'), meta: { auth: true, subject: '对话' } },

  // --- 文档查看器 ---
  { path: '/document-viewer', component: () => import('../views/DocumentViewer.vue'), meta: { auth: true } },

  // --- 管理员面板 ---
  { path: '/admin', component: () => import('../views/Admin.vue'), meta: { auth: true, admin: true } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

let lastFetchMe = 0

const SUBJECT_HOME = {
  '数学': '/solve',
  '英语': '/english-upload',
  '对话': '/chat',
}

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isLoggedIn) {
    const now = Date.now()
    if (now - lastFetchMe > 5000) {
      lastFetchMe = now
      await auth.fetchMe()
    }
  }
  if (to.meta.auth && !auth.isLoggedIn) {
    next('/login')
    return
  }

  // 管理员直接进管理页
  if (auth.isLoggedIn && auth.isAdmin) {
    if (to.path === '/' || to.path === '/login') {
      next('/admin')
      return
    }
    if (to.meta.subject && !to.meta.admin) {
      next('/admin')
      return
    }
    next()
    return
  }

  // 学科路由守卫：确保用户在正确的学科前端
  if (to.meta.subject && auth.isLoggedIn) {
    const routeSubject = to.meta.subject
    if (routeSubject !== auth.subject) {
      next(SUBJECT_HOME[auth.subject] || '/solve')
      return
    }
  }

  // 管理员路由守卫（非管理员禁止访问）
  if (to.meta.admin && auth.isLoggedIn && !auth.isAdmin) {
    next('/solve')
    return
  }

  next()
})

router.afterEach((to, from) => {
  if (to.path !== from.path) {
    const app = useAppStore()
    app.resetCurrentSessionUsage()
  }
})

export default router
