<template>
  <aside class="sidebar-left">
    <div class="brand">
      <el-icon size="18"><School /></el-icon>
      <span class="brand-text">StudyBuddy</span>
      <el-tag size="small" effect="dark" :type="auth.isAdmin ? 'danger' : 'success'">
        {{ auth.isAdmin ? '管理员' : '教师' }}
      </el-tag>
    </div>

    <div class="section">
      <div class="section-title">导航</div>
      <div class="tab-list">
        <div
          v-for="item in navItems"
          :key="item.path"
          class="tab-item"
          :class="{ active: route.path === item.path }"
          @click="go(item.path)"
        >
          <el-icon :size="16"><component :is="item.icon" /></el-icon>
          <span class="tab-label">{{ item.label }}</span>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">当前账号</div>
      <div class="profile-box">
        <div class="profile-name">{{ auth.displayName || auth.user?.username }}</div>
        <div class="profile-meta">{{ auth.user?.username }}</div>
      </div>
    </div>

    <div class="bottom-bar">
      <el-button text size="small" @click="go('/settings/system')"><el-icon><Setting /></el-icon><span>系统设置</span></el-button>
      <el-button text size="small" @click="go('/settings/profile')"><el-icon><User /></el-icon><span>个人资料</span></el-button>
      <el-button text size="small" @click="logout"><el-icon><SwitchButton /></el-icon><span>退出</span></el-button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { School, Notebook, DataBoard, Setting, User, SwitchButton } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = computed(() => {
  if (auth.isAdmin) {
    return [{ path: '/admin', label: '管理员工作台', icon: DataBoard }]
  }
  return [
    { path: '/teacher', label: '教师工作台', icon: Notebook },
  ]
})

function go(path) {
  router.push(path)
}

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar-left {
  width: 260px;
  background: #0f172a;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 18px 14px;
  gap: 18px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.brand-text {
  font-weight: 700;
  flex: 1;
}
.section-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}
.tab-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tab-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: #cbd5e1;
}
.tab-item.active,
.tab-item:hover {
  background: #1e293b;
  color: #fff;
}
.profile-box {
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
}
.profile-name {
  font-weight: 600;
}
.profile-meta {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
}
.bottom-bar {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.bottom-bar :deep(.el-button) {
  color: #cbd5e1;
}
@media (max-width: 768px) {
  .sidebar-left {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    z-index: 160;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }
  .sidebar-left.mobile-open {
    transform: translateX(0);
  }
}
</style>
