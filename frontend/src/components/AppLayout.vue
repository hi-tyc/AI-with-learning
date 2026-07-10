<template>
  <div class="app-layout">
    <!-- 移动端顶部导航栏 -->
    <div class="mobile-header" v-if="!isLoginPage && !isTeacherWorkspace">
      <div class="mobile-header-left">
        <el-button text circle size="small" @click="toggleSidebar" class="hamburger-btn">
          <el-icon size="20"><Fold v-if="sidebarOpen" /><Expand v-else /></el-icon>
        </el-button>
        <span class="mobile-brand">StudyBuddy</span>
      </div>
      <div class="mobile-header-right">
        <el-tag v-if="auth.isLoggedIn" :type="auth.isAdmin ? 'danger' : 'success'" size="small" effect="dark">
          {{ auth.isAdmin ? '管理员' : '教师' }}
        </el-tag>
      </div>
    </div>

    <!-- 移动端遮罩层 -->
    <div
      v-if="sidebarOpen && isMobile"
      class="mobile-overlay"
      @click="sidebarOpen = false"
    ></div>

    <SidebarLeft v-if="!isTeacherWorkspace" :class="{ 'mobile-open': sidebarOpen && isMobile }" />
    <main class="main-content" :class="{ 'mobile-login': isLoginPage, 'teacher-shell': isTeacherWorkspace }">
      <slot />
    </main>
    <SidebarRight />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import SidebarLeft from './SidebarLeft.vue'
import SidebarRight from './SidebarRight.vue'

const route = useRoute()
const auth = useAuthStore()
const isLoginPage = computed(() => ['/login', '/register'].includes(route.path))
const isTeacherWorkspace = computed(() => route.path === '/teacher' || route.path.startsWith('/teacher/'))

// 移动端检测
const isMobile = ref(false)
const sidebarOpen = ref(false)

function checkMobile() {
  isMobile.value = window.innerWidth <= 768
  if (!isMobile.value) sidebarOpen.value = false
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

provide('mobileSidebarOpen', sidebarOpen)
provide('isMobile', isMobile)
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #f8fafc;
}
.main-content {
  flex: 1 1 0;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
}
.main-content.teacher-shell {
  height: 100vh;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }
  .main-content {
    height: calc(100vh - 48px);
    width: 100%;
  }
  .main-content.mobile-login {
    height: 100vh;
  }
  .mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 0 12px;
    background: rgba(255,255,255,0.92);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(0,0,0,0.06);
    flex-shrink: 0;
    z-index: 110;
  }
  .mobile-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .mobile-brand {
    font-weight: 700;
    font-size: 15px;
    color: #1e3a5f;
  }
  .mobile-header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .hamburger-btn {
    color: #475569;
  }
  .mobile-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    z-index: 150;
  }
}

/* 桌面端隐藏移动端元素 */
@media (min-width: 769px) {
  .mobile-header {
    display: none !important;
  }
  .mobile-overlay {
    display: none !important;
  }
}
</style>
