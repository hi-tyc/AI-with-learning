<template>
  <el-menu mode="horizontal" :router="true" class="navbar" :default-active="$route.path">
    <div class="nav-brand">
      <el-icon size="20"><School /></el-icon>
      <span class="brand-text">StudyBuddy</span>
      <el-tag
        v-if="auth.subject"
        :type="subjectTagType"
        size="small"
        effect="dark"
        class="subject-tag"
      >
        <el-icon size="12"><component :is="subjectIcon" /></el-icon>
        {{ auth.subject }}
      </el-tag>
    </div>
    <div class="nav-spacer" />

    <!-- 管理员导航 -->
    <template v-if="auth.isAdmin">
      <el-menu-item index="/admin">
        <el-icon><Setting /></el-icon>
        <span>系统概览</span>
      </el-menu-item>
      <el-menu-item index="/admin" @click="switchAdminTab('users')">
        <el-icon><User /></el-icon>
        <span>用户管理</span>
      </el-menu-item>
      <el-menu-item index="/admin" @click="switchAdminTab('usage')">
        <el-icon><Coin /></el-icon>
        <span>用量统计</span>
      </el-menu-item>
      <el-menu-item index="/admin" @click="switchAdminTab('logs')">
        <el-icon><Document /></el-icon>
        <span>系统日志</span>
      </el-menu-item>
    </template>

    <!-- 数学导航 -->
    <template v-else-if="auth.subject === '数学'">
      <el-menu-item index="/solve">
        <el-icon><EditPen /></el-icon>
        <span>解题</span>
      </el-menu-item>
      <el-menu-item index="/upload">
        <el-icon><Camera /></el-icon>
        <span>录入题目</span>
      </el-menu-item>
      <el-menu-item index="/library">
        <el-icon><Collection /></el-icon>
        <span>题库</span>
      </el-menu-item>
      <el-menu-item index="/manage">
        <el-icon><Tools /></el-icon>
        <span>管理</span>
      </el-menu-item>
      <el-menu-item index="/usage">
        <el-icon><Coin /></el-icon>
        <span>用量</span>
      </el-menu-item>
    </template>

    <!-- 英语导航 -->
    <template v-else-if="auth.subject === '英语'">
      <el-menu-item index="/english-upload">
        <el-icon><Upload /></el-icon>
        <span>上传资料</span>
      </el-menu-item>
      <el-menu-item index="/english/solve">
        <el-icon><EditPen /></el-icon>
        <span>解题</span>
      </el-menu-item>
      <el-menu-item index="/english/library">
        <el-icon><Collection /></el-icon>
        <span>题库</span>
      </el-menu-item>
      <el-menu-item index="/english/usage">
        <el-icon><Coin /></el-icon>
        <span>用量</span>
      </el-menu-item>
    </template>

    <!-- 对话导航 -->
    <template v-else-if="auth.subject === '对话'">
      <el-menu-item index="/chat">
        <el-icon><ChatLineRound /></el-icon>
        <span>对话</span>
      </el-menu-item>
    </template>
    <el-sub-menu index="/settings">
      <template #title>
        <el-icon><Tools /></el-icon>
        <span>设置</span>
      </template>
      <el-menu-item index="/settings/system">
        <el-icon><Cpu /></el-icon>
        <span>系统设置</span>
      </el-menu-item>
      <el-menu-item index="/settings/profile">
        <el-icon><User /></el-icon>
        <span>个人资料</span>
      </el-menu-item>
    </el-sub-menu>
    <el-menu-item @click="logout">
      <el-icon><SwitchButton /></el-icon>
      <span>退出</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup>
import { computed } from 'vue'
import { School, Monitor, Reading, ChatLineRound, EditPen, Camera, Collection, Tools, Upload, Coin, Setting, Cpu, User, SwitchButton, Document } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

const subjectTagType = computed(() => {
  if (auth.subject === '数学') return 'primary'
  if (auth.subject === '英语') return 'success'
  return 'warning'
})

const subjectIcon = computed(() => {
  if (auth.subject === '数学') return 'Monitor'
  if (auth.subject === '英语') return 'Reading'
  return 'ChatLineRound'
})

function switchAdminTab(tab) {
  router.push({ path: '/admin', query: { tab } })
}
function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0,0,0,0.04);
  display: flex;
  align-items: center;
  padding: 0 16px;
  height: 56px;
}
.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  font-weight: 700;
  font-size: 16px;
  color: #1e3a5f;
  margin-right: 8px;
}
.brand-text {
  color: #1e3a5f;
  letter-spacing: -0.3px;
}
.subject-tag {
  margin-left: 8px;
  font-weight: 600;
  font-size: 12px;
}
.nav-spacer {
  flex: 1;
}
:deep(.el-menu-item),
:deep(.el-sub-menu .el-sub-menu__title) {
  height: 56px;
  line-height: 56px;
  border-bottom: none !important;
  font-size: 14px;
  color: #4a5568;
}
:deep(.el-menu-item.is-active) {
  color: #2563eb;
  font-weight: 600;
}
:deep(.el-menu-item:hover) {
  color: #2563eb;
  background: transparent;
}
</style>
