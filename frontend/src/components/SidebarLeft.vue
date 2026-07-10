<template>
  <aside class="sidebar-left">
    <div class="brand">
      <el-icon size="20"><School /></el-icon>
      <span class="brand-text">StudyBuddy</span>
      <el-tag
        :type="subjectTagType"
        size="small"
        effect="dark"
        class="sidebar-subject-tag"
      >
        {{ auth.subject }}
      </el-tag>
    </div>

    <!-- 管理员侧栏 -->
    <template v-if="auth.isAdmin">
      <div class="section">
        <div class="section-title">管理控制台</div>
        <div class="tab-list">
          <div class="tab-item" :class="{ active: adminTab === 'dashboard' }" @click="goAdminTab('dashboard')">
            <el-icon size="16" color="#7c3aed"><DataBoard /></el-icon>
            <span class="tab-label">系统概览</span>
          </div>
          <div class="tab-item" :class="{ active: adminTab === 'users' }" @click="goAdminTab('users')">
            <el-icon size="16" color="#2563eb"><User /></el-icon>
            <span class="tab-label">用户管理</span>
          </div>
          <div class="tab-item" :class="{ active: adminTab === 'usage' }" @click="goAdminTab('usage')">
            <el-icon size="16" color="#059669"><Coin /></el-icon>
            <span class="tab-label">用量统计</span>
          </div>
          <div class="tab-item" :class="{ active: adminTab === 'logs' }" @click="goAdminTab('logs')">
            <el-icon size="16" color="#d97706"><Document /></el-icon>
            <span class="tab-label">系统日志</span>
          </div>
          <div class="tab-item" :class="{ active: adminTab === 'settings' }" @click="goAdminTab('settings')">
            <el-icon size="16" color="#dc2626"><Lock /></el-icon>
            <span class="tab-label">修改密码</span>
          </div>
        </div>
      </div>
      <el-divider class="divider" />
      <div class="admin-sidebar-info">
        <div class="info-row">
          <span class="info-label">用户数</span>
          <span class="info-value">{{ sidebarStats.user_count || '-' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">数据大小</span>
          <span class="info-value">{{ sidebarStats.data_size_mb || '0' }} MB</span>
        </div>
        <div class="info-row">
          <span class="info-label">磁盘剩余</span>
          <span class="info-value" :class="{ 'text-danger': sidebarStats.low_space_warning }">{{ sidebarStats.disk_free_percent || '0' }}%</span>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="section">
        <div class="section-title">功能</div>
        <div class="tab-list">
          <div
            v-for="tab in app.tabs" :key="tab.id"
            class="tab-item" :class="{ active: app.activeTab === tab.id }"
            @click="switchTab(tab.id)"
          >
            <el-icon :size="16" :color="tab.color"><component :is="tab.icon" /></el-icon>
            <span class="tab-label">{{ tab.label }}</span>
          </div>
        </div>
      </div>

      <el-divider class="divider" />
    </template>

    <div class="section session-section" v-if="!auth.isAdmin && auth.subject === '数学'">
      <div class="section-header">
        <span class="section-title">题目列表</span>
        <el-button text size="small" @click="loadAll"><el-icon><Refresh /></el-icon></el-button>
      </div>
      <div v-if="sidebarSelected.length > 0" class="sidebar-batch-bar">
        <span class="batch-label">已选 {{ sidebarSelected.length }} 题</span>
        <el-button text size="small" type="danger" @click.stop="sidebarBatchDelete">
          <el-icon><Delete /></el-icon>
        </el-button>
        <el-button text size="small" @click.stop="sidebarSelected = []">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <div v-if="showTrash" class="problem-list sidebar-trash">
        <div class="trash-header" @click="showTrash = false">
          <el-icon size="14"><Delete /></el-icon>
          <span>废纸篓 ({{ trashItems.length }})</span>
          <el-icon size="12"><ArrowUp /></el-icon>
        </div>
        <div v-for="p in trashItems" :key="p.id" class="problem-item trash-item">
          <span class="prob-content muted">{{ p.content.slice(0, 30) }}{{ p.content.length > 30 ? '...' : '' }}</span>
          <el-button text size="small" @click.stop="restoreProblem(p.id)">
            <el-icon size="12"><Refresh /></el-icon>
          </el-button>
        </div>
        <div v-if="!trashItems.length" class="empty-hint">废纸篓为空</div>
      </div>
      <div class="problem-list">
        <div
          v-for="p in allProblems" :key="p.id"
          class="problem-item" :class="{ solved: p.solved_at }"
        >
          <el-checkbox v-model="sidebarSelected" :label="p.id" @click.stop class="sidebar-cb" />
          <span class="prob-status" :class="{ solved: p.solved_at }" @click="clickProblem(p)">
            {{ p.solved_at ? '已解' : '未解' }}
          </span>
          <span class="prob-content" @click="clickProblem(p)">{{ p.content.slice(0, 40) }}{{ p.content.length > 40 ? '...' : '' }}</span>
          <span v-if="p.upload_mode === 'geometry'" class="prob-geo">几何</span>
        </div>
        <div v-if="allProblems.length === 0" class="empty-hint">暂无题目</div>
      </div>
    </div>

    <!-- 英语模式侧栏提示 -->
    <div v-else-if="!auth.isAdmin && auth.subject === '英语'" class="english-sidebar-hint">
      <div class="hint-icon">
        <el-icon size="32" color="#6ee7b7"><Reading /></el-icon>
      </div>
      <p>英语学习模式</p>
      <p class="hint-desc">上传资料 → AI 识别 → 解题练习</p>
    </div>

    <!-- 对话模式侧栏提示 -->
    <div v-else-if="!auth.isAdmin && auth.subject === '对话'" class="english-sidebar-hint">
      <div class="hint-icon">
        <el-icon size="32" color="#a78bfa"><ChatLineRound /></el-icon>
      </div>
      <p>对话模式</p>
      <p class="hint-desc">与 AI 自由对话，支持图片上传</p>
    </div>

    <div class="bottom-bar">
      <div class="bottom-actions">
        <el-button v-if="!auth.isAdmin" text size="small" @click="app.showSolveInfo = !app.showSolveInfo">
          <el-icon><DataAnalysis /></el-icon><span>解题信息</span>
        </el-button>
        <el-button v-if="auth.isAdmin" text size="small" @click="goAdminTab('dashboard')"><el-icon><DataBoard /></el-icon><span>控制台</span></el-button>
        <el-button text size="small" @click="goSettings"><el-icon><Setting /></el-icon><span>设置</span></el-button>
        <el-button text size="small" @click="logout"><el-icon><SwitchButton /></el-icon><span>退出</span></el-button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useAppStore } from '../stores/app.js'
import { School, Refresh, Setting, SwitchButton, Delete, Close, ArrowUp, ArrowDown, Reading, ChatLineRound, DataAnalysis, DataBoard, User, Coin, Document, Lock } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const subjectTagType = computed(() => {
  if (auth.subject === '数学') return 'primary'
  if (auth.subject === '英语') return 'success'
  return 'warning'
})

const adminTab = ref(sessionStorage.getItem('adminTab') || 'dashboard')
const sidebarStats = ref({})

const allProblems = ref([])
const sidebarSelected = ref([])
const showTrash = ref(false)
const trashItems = ref([])

async function loadSidebarStats() {
  try {
    const res = await axios.get('/admin/status')
    sidebarStats.value = res.data
  } catch {}
}

function goAdminTab(tab) {
  adminTab.value = tab
  router.push('/admin?tab=' + tab)
}

async function loadAll() {
  try {
    const [res, trashRes] = await Promise.all([
      axios.get('/problems?page_size=500'),
      axios.get('/problems/trash'),
    ])
    allProblems.value = res.data.items || []
    trashItems.value = trashRes.data.items || []
  } catch (e) { console.error('加载失败', e) }
}

async function restoreProblem(id) {
  try {
    await axios.post('/problems/trash/restore', { ids: [id] })
    ElMessage.success('已恢复')
    await loadAll()
  } catch (e) {
    ElMessage.error('恢复失败')
  }
}

async function sidebarBatchDelete() {
  if (!sidebarSelected.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除 ${sidebarSelected.value.length} 道题？`, '提示', { type: 'warning' })
    await axios.post('/problems/batch-delete', { ids: sidebarSelected.value })
    ElMessage.success('已删除')
    sidebarSelected.value = []
    await loadAll()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function clickProblem(p) {
  if (!p || !p.id) return
  app.setActiveSession(p.id)
  app.setActiveTab('解题')
  sessionStorage.setItem('quickSolve', JSON.stringify({
    id: p.id, content: p.content || '', subject: p.subject || '',
    knowledge_point: p.knowledge_point || '', image_file_id: p.image_file_id || '',
    upload_mode: p.upload_mode || 'algebra',
    existingSolution: p.solution || '', solvedBy: p.solved_by || '', solvedAt: p.solved_at || '',
  }))
  router.push('/solve')
}

function switchTab(tabId) {
  app.setActiveTab(tabId)
  if (auth.subject === '英语') {
    const englishRouteMap = { '录入': '/english-upload', '解题': '/english/solve', '资料': '/english/library', '错题': '/english/wrong-book', '用量': '/english/usage' }
    router.push(englishRouteMap[tabId] || '/english-upload')
  } else if (auth.subject === '对话') {
    router.push('/chat')
  } else {
    const mathRouteMap = { '录入': '/upload', '解题': '/solve', '管理': '/manage', '题库': '/library', '用量': '/usage' }
    router.push(mathRouteMap[tabId] || '/solve')
  }
  // 移动端点击后自动关闭侧边栏
  closeMobileSidebar()
}

function closeMobileSidebar() {
  // 通过事件通知父组件关闭（移动端）
  const overlay = document.querySelector('.mobile-overlay')
  if (overlay) overlay.click()
}

function goSettings() { closeMobileSidebar(); router.push('/settings'); app.setActiveTab('') }
function goAdmin() { closeMobileSidebar(); router.push('/admin'); app.setActiveTab('') }
function logout() { closeMobileSidebar(); auth.logout(); router.push('/login') }

onMounted(() => {
  if (auth.isAdmin) {
    loadSidebarStats()
  } else if (auth.subject === '数学') {
    loadAll()
  }
})
</script>

<style scoped>
.sidebar-left {
  width: clamp(200px, 18vw, 280px); min-width: 200px;
  background: #fff; border-right: 1px solid #e2e8f0;
  display: flex; flex-direction: column; overflow: hidden;
}
.brand {
  display: flex; align-items: center; gap: 8px;
  padding: 16px 20px; font-weight: 700; font-size: 16px;
  color: #1e3a5f; border-bottom: 1px solid #f1f5f9; flex-shrink: 0;
}
.sidebar-subject-tag {
  margin-left: auto;
  font-weight: 600;
  font-size: 11px;
}
.section { padding: 12px 0; flex-shrink: 0; }
.section-title {
  font-size: 11px; font-weight: 600; color: #94a3b8;
  text-transform: uppercase; letter-spacing: 0.5px; padding: 0 16px 8px;
}
.section-header {
  display: flex; align-items: center; justify-content: space-between; padding: 0 12px 0 16px;
}
.divider { margin: 4px 16px; border-color: #f1f5f9; flex-shrink: 0; }
.tab-list { padding: 0 8px; }
.tab-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-radius: 8px; cursor: pointer;
  transition: all 0.15s ease; margin-bottom: 2px;
  font-size: 14px; color: #475569;
}
.tab-item:hover { background: #f1f5f9; }
.tab-item.active { background: #eff6ff; color: #2563eb; font-weight: 600; }
.tab-label { flex: 1; }
.session-section { flex: 1; overflow: hidden; display: flex; flex-direction: column; min-height: 0; }
.problem-list {
  flex: 1; overflow-y: auto; padding: 0 8px 12px; min-height: 0;
}
.problem-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 8px; cursor: pointer;
  transition: all 0.15s ease; font-size: 13px; color: #334155;
  margin-bottom: 2px;
}
.problem-item:hover { background: #f1f5f9; }
.problem-item.solved { color: #059669; }
.prob-status {
  font-size: 10px; font-weight: 600; color: #94a3b8;
  background: #f1f5f9; padding: 2px 6px; border-radius: 4px; flex-shrink: 0;
}
.prob-status.solved { color: #fff; background: #059669; }
.prob-content { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.prob-geo {
  font-size: 10px; color: #2563eb; background: #eff6ff;
  padding: 1px 5px; border-radius: 3px; flex-shrink: 0;
}
.empty-hint { text-align: center; padding: 20px; font-size: 13px; color: #94a3b8; }
.sidebar-trash {
  border-top: 1px solid #f1f5f9;
  padding-top: 4px;
  margin-top: 4px;
}
.trash-header {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; font-size: 12px; color: #94a3b8;
  cursor: pointer; border-radius: 6px; margin-bottom: 2px;
}
.trash-header:hover { background: #f1f5f9; }
.trash-item { opacity: 0.7; font-size: 12px; }
.trash-item .muted { color: #94a3b8; }
.sidebar-cb { margin-right: 2px; }
.sidebar-batch-bar {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 12px; margin: 0 8px 6px;
  background: #fef2f2; border-radius: 8px;
  border: 1px solid #fecaca; flex-shrink: 0;
}
.batch-label { font-size: 12px; color: #dc2626; font-weight: 600; margin-right: auto; }
.english-sidebar-hint {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  gap: 8px;
}
.english-sidebar-hint p {
  font-size: 14px;
  color: #475569;
  margin: 0;
  font-weight: 600;
}
.english-sidebar-hint .hint-desc {
  font-size: 12px;
  color: #94a3b8;
  font-weight: normal;
}
.hint-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #f0fdf4;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}
.bottom-bar {
  border-top: 1px solid #f1f5f9; padding: 12px 16px; flex-shrink: 0; background: #fff;
}
.bottom-actions { display: flex; gap: 4px; }
.bottom-actions :deep(.el-button) {
  flex: 1; justify-content: center; color: #64748b; font-size: 12px; padding: 4px 8px; height: 28px;
}
.bottom-actions :deep(.el-button:hover) { color: #2563eb; background: #f1f5f9; }
.admin-sidebar-info {
  padding: 12px 16px;
  flex-shrink: 0;
}
.info-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}
.info-label { color: #64748b; }
.info-value { font-weight: 600; color: #334155; }
.info-value.text-danger { color: #dc2626; }

/* ========== 移动端响应式：侧边栏变为抽屉 ========== */
@media (max-width: 768px) {
  .sidebar-left {
    position: fixed;
    left: 0;
    top: 0;
    height: 100vh;
    height: 100dvh;
    z-index: 160;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    width: 260px;
    min-width: 260px;
    box-shadow: 2px 0 12px rgba(0,0,0,0.12);
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
  }
  .sidebar-left.mobile-open {
    transform: translateX(0);
  }
  .brand {
    display: none;
  }
  .tab-item {
    padding: 10px 12px;
    font-size: 14px;
  }
  .bottom-actions :deep(.el-button) {
    font-size: 11px;
    padding: 3px 6px;
    height: 26px;
  }
}
</style>
