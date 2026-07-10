import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/register', component: () => import('../views/Register.vue') },
  { path: '/teacher', component: () => import('../views/TeacherWorkspace.vue'), meta: { auth: true, roles: ['teacher', 'admin'] } },
  { path: '/admin', component: () => import('../views/AdminWorkspace.vue'), meta: { auth: true, roles: ['admin'] } },
  { path: '/document-viewer', component: () => import('../views/DocumentViewer.vue'), meta: { auth: true, roles: ['teacher', 'admin'] } },
  { path: '/settings/system', component: () => import('../views/SystemSettings.vue'), meta: { auth: true } },
  { path: '/settings/profile', component: () => import('../views/Profile.vue'), meta: { auth: true } },
  { path: '/settings', redirect: '/settings/system', meta: { auth: true } },
  { path: '/', redirect: '/login' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

let lastFetchMe = 0

function homePath(auth) {
  return auth.isAdmin ? '/admin' : '/teacher'
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

  if (auth.isLoggedIn && to.path === '/login') {
    next(homePath(auth))
    return
  }

  if (to.meta.roles && auth.isLoggedIn) {
    const allowed = to.meta.roles.includes(auth.role)
    if (!allowed) {
      next(homePath(auth))
      return
    }
  }

  next()
})

export default router
