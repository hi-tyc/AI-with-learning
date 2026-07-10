<template>
  <div class="admin-page">
    <div class="admin-header">
      <div class="header-left">
        <el-icon size="24" color="#7c3aed"><Setting /></el-icon>
        <h1>管理员控制台</h1>
        <el-tag type="danger" effect="dark" size="small">root</el-tag>
      </div>
      <el-tag type="info" effect="plain" size="small" class="header-hint">使用左侧菜单切换功能</el-tag>
    </div>

    <div class="admin-content">
      <!-- ═══════ 系统概览 ═══════ -->
      <template v-if="activeTab === 'dashboard'">
        <el-row :gutter="16" class="stats-row">
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-users">
              <div class="stat-value">{{ stats.user_count || '-' }}</div>
              <div class="stat-label">注册用户</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-files">
              <div class="stat-value">{{ stats.data_files || '-' }}</div>
              <div class="stat-label">数据文件</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-size">
              <div class="stat-value">{{ stats.data_size_mb || '0' }}</div>
              <div class="stat-label">数据 (MB)</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card" :class="stats.low_space_warning ? 'stat-warning' : 'stat-ok'">
              <div class="stat-value">{{ stats.disk_free_percent || '0' }}%</div>
              <div class="stat-label">磁盘剩余</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-ok">
              <div class="stat-value">{{ uploadsCount }}</div>
              <div class="stat-label">上传文件</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-info">
              <div class="stat-value">{{ activeUsers }}</div>
              <div class="stat-label">活跃用户 (7天)</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="hover" class="detail-card">
              <template #header>
                <div class="card-title">
                  <el-icon><DataAnalysis /></el-icon><span>系统信息</span>
                  <el-button text size="small" @click="loadStatus" style="margin-left:auto"><el-icon><Refresh /></el-icon></el-button>
                </div>
              </template>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="操作系统">{{ info.platform }}</el-descriptions-item>
                <el-descriptions-item label="Python">{{ info.python_version }}</el-descriptions-item>
                <el-descriptions-item label="主机名">{{ info.hostname }}</el-descriptions-item>
                <el-descriptions-item label="数据目录">{{ info.data_dir }}</el-descriptions-item>
                <el-descriptions-item label="用户目录">{{ info.users_dir }}</el-descriptions-item>
                <el-descriptions-item label="磁盘占用">{{ stats.disk_used_mb }} MB / {{ stats.disk_total_mb }} MB</el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="hover" class="detail-card">
              <template #header>
                <div class="card-title">
                  <el-icon><WarningFilled /></el-icon><span>维护操作</span>
                </div>
              </template>
              <div class="action-list">
                <div class="action-item">
                  <div class="action-info">
                    <strong>清理临时文件</strong>
                    <span class="action-desc">删除 temp 目录中的临时文件</span>
                  </div>
                  <el-button size="small" type="danger" plain @click="purgeTemp">执行</el-button>
                </div>
                <div class="action-item">
                  <div class="action-info">
                    <strong>系统诊断</strong>
                    <span class="action-desc">运行系统健康检查</span>
                  </div>
                  <el-button size="small" type="primary" plain @click="runDiagnose">诊断</el-button>
                </div>
              </div>
              <el-alert v-if="diagnoseResult" :title="diagnoseResult" type="warning" show-icon :closable="true" style="margin-top:12px" />
            </el-card>
          </el-col>
        </el-row>
      </template>

      <!-- ═══════ 用户管理 ═══════ -->
      <template v-if="activeTab === 'users'">
        <el-card shadow="hover">
          <template #header>
            <div class="card-title">
              <el-icon><User /></el-icon>
              <span>用户列表 ({{ users.length }})</span>
              <el-input v-model="userSearch" placeholder="搜索用户名..." clearable prefix-icon="Search" size="small" style="width:200px;margin-left:auto" />
              <el-button text size="small" @click="loadUsers" style="margin-left:8px"><el-icon><Refresh /></el-icon></el-button>
            </div>
          </template>
          <el-table :data="filteredUsers" stripe style="width:100%" max-height="600px" @row-click="viewUser">
            <el-table-column prop="username" label="用户名" width="160" />
            <el-table-column prop="grade" label="年级" width="90" />
            <el-table-column prop="school" label="学校" width="140" />
            <el-table-column label="创建时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="最后活跃" width="170">
              <template #default="{ row }">{{ formatTime(row.last_modified) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row, $index }">
                <el-button size="small" text @click.stop="viewUser(row)"><el-icon><View /></el-icon></el-button>
                <el-button size="small" text type="danger" :disabled="row.username === 'root'" @click.stop="confirmDeleteUser(row.username)"><el-icon><Delete /></el-icon></el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-drawer v-model="showUserDetail" :title="'用户详情: ' + currentUser" size="520px">
          <template v-if="userDetail.user">
            <el-tabs v-model="userDetailTab">
              <el-tab-pane label="基本信息" name="info">
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="用户名">{{ currentUser }}</el-descriptions-item>
                  <el-descriptions-item label="年级">{{ userDetail.user.grade || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="学校">{{ userDetail.user.school || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="创建时间">{{ formatTime(userDetail.user.created_at) }}</el-descriptions-item>
                  <el-descriptions-item label="偏好设置">{{ userDetail.user.preferences || '-' }}</el-descriptions-item>
                </el-descriptions>
              </el-tab-pane>
              <el-tab-pane label="API 配置" name="config">
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="学科">{{ userDetail.config.subject || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="DeepSeek 模型">{{ userDetail.config.deepseek_model || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="DeepSeek Key">{{ maskKey(userDetail.config.deepseek_api_key) }}</el-descriptions-item>
                  <el-descriptions-item label="Kimi 模型">{{ userDetail.config.kimi_model || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="Kimi Key">{{ maskKey(userDetail.config.kimi_api_key) }}</el-descriptions-item>
                  <el-descriptions-item label="每日限额">¥{{ userDetail.config.daily_cost_limit || '-' }}</el-descriptions-item>
                </el-descriptions>
              </el-tab-pane>
              <el-tab-pane label="数据文件" name="files">
                <el-table :data="userDetail.data_files || []" stripe size="small" max-height="400px">
                  <el-table-column prop="filename" label="文件名" min-width="200">
                    <template #default="{ row }"><span style="font-size:12px;word-break:break-all">{{ row.filename }}</span></template>
                  </el-table-column>
                  <el-table-column prop="size_bytes" label="大小" width="100">
                    <template #default="{ row }">{{ (row.size_bytes / 1024).toFixed(1) }} KB</template>
                  </el-table-column>
                  <el-table-column prop="last_modified" label="修改时间" width="170">
                    <template #default="{ row }">{{ formatTime(row.last_modified) }}</template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
            </el-tabs>
            <div style="margin-top:16px">
              <el-popconfirm title="确定删除此用户？" @confirm="doDeleteUser(currentUser)">
                <template #reference>
                  <el-button type="danger" size="small" :disabled="currentUser === 'root'"><el-icon><Delete /></el-icon> 删除用户</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-drawer>
      </template>

      <!-- ═══════ 用量统计 ═══════ -->
      <template v-if="activeTab === 'usage'">
        <el-card shadow="hover">
          <template #header>
            <div class="card-title">
              <el-icon><Coin /></el-icon>
              <span>用户用量统计</span>
              <el-button text size="small" @click="loadUsage" style="margin-left:auto"><el-icon><Refresh /></el-icon></el-button>
            </div>
          </template>
          <el-table :data="usageList" stripe style="width:100%" max-height="600px" v-loading="usageLoading">
            <el-table-column prop="username" label="用户名" width="140" />
            <el-table-column prop="subject" label="学科" width="80" />
            <el-table-column label="今日输入 tokens" width="130">
              <template #default="{ row }">{{ row.today_tokens_in || 0 }}</template>
            </el-table-column>
            <el-table-column label="今日输出 tokens" width="130">
              <template #default="{ row }">{{ row.today_tokens_out || 0 }}</template>
            </el-table-column>
            <el-table-column label="今日费用 (¥)" width="120">
              <template #default="{ row }">{{ (row.today_cost || 0).toFixed(4) }}</template>
            </el-table-column>
            <el-table-column label="API 调用" width="100">
              <template #default="{ row }">{{ row.today_count || 0 }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="usageList.length === 0 && !usageLoading" description="暂无用量数据" />
        </el-card>
      </template>

      <!-- ═══════ 系统日志 ═══════ -->
      <template v-if="activeTab === 'logs'">
        <el-card shadow="hover">
          <template #header>
            <div class="card-title">
              <el-icon><Document /></el-icon>
              <span>系统日志</span>
              <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
                <el-select v-model="logLines" size="small" style="width:120px">
                  <el-option label="50 行" :value="50" />
                  <el-option label="100 行" :value="100" />
                  <el-option label="200 行" :value="200" />
                  <el-option label="500 行" :value="500" />
                </el-select>
                <el-button text size="small" @click="loadLogs"><el-icon><Refresh /></el-icon></el-button>
              </div>
            </div>
          </template>
          <el-tabs v-model="activeLogTab">
            <el-tab-pane v-for="lf in logFiles" :key="lf.filename" :label="lf.filename + ' (' + lf.lines + '行)'" :name="lf.filename">
              <div class="log-viewer">
                <div v-if="lf.error" class="log-error">{{ lf.error }}</div>
                <pre v-else class="log-content">{{ lf.tail || '(空)' }}</pre>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </template>

      <!-- ═══════ 修改密码 ═══════ -->
      <template v-if="activeTab === 'settings'">
        <el-card shadow="hover" style="max-width:500px;margin:0 auto">
          <template #header>
            <div class="card-title">
              <el-icon><Lock /></el-icon>
              <span>修改管理员密码</span>
            </div>
          </template>
          <el-form @submit.prevent="changePassword" label-position="top">
            <el-form-item label="当前密码">
              <el-input v-model="pwdForm.old" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="pwdForm.new1" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认新密码">
              <el-input v-model="pwdForm.new2" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="changePassword" :icon="CircleCheck">修改密码</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import {
  Setting, DataBoard, User, Coin, Document, Lock, Refresh,
  DataAnalysis, WarningFilled, View, Delete, CircleCheck,
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const VALID_TABS = ['dashboard', 'users', 'usage', 'logs', 'settings']
const activeTab = ref('dashboard')
const activeLogTab = ref('')
const logLines = ref(100)
const showUserDetail = ref(false)
const currentUser = ref('')
const userSearch = ref('')
const userDetailTab = ref('info')
const usageLoading = ref(false)
const diagnoseResult = ref('')

const stats = ref({})
const info = ref({})
const users = ref([])
const userDetail = ref({})
const logFiles = ref([])
const usageList = ref([])
const pwdForm = ref({ old: '', new1: '', new2: '' })

const uploadsCount = computed(() => {
  return stats.value.data_files || 0
})

const activeUsers = computed(() => {
  if (!users.value.length) return '0'
  const now = Date.now()
  const sevenDays = 7 * 24 * 60 * 60 * 1000
  return users.value.filter(u => {
    const lm = u.last_modified ? new Date(u.last_modified).getTime() : 0
    return now - lm < sevenDays
  }).length
})

const filteredUsers = computed(() => {
  if (!userSearch.value) return users.value
  const q = userSearch.value.toLowerCase()
  return users.value.filter(u => u.username.toLowerCase().includes(q))
})

function maskKey(key) {
  if (!key || key.length < 8) return key || '-'
  return key.slice(0, 6) + '****' + key.slice(-4)
}

function formatTime(t) {
  if (!t) return '-'
  try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
}

async function loadStatus() {
  try {
    const [res, infoRes] = await Promise.all([
      axios.get('/admin/status'),
      axios.get('/admin/info'),
    ])
    stats.value = res.data
    info.value = infoRes.data
  } catch { ElMessage.error('加载系统状态失败') }
}

async function loadUsers() {
  try {
    const res = await axios.get('/admin/users')
    users.value = res.data.items || []
  } catch { ElMessage.error('加载用户列表失败') }
}

async function viewUser(row) {
  const username = typeof row === 'string' ? row : row.username
  currentUser.value = username
  showUserDetail.value = true
  try {
    const res = await axios.get(`/admin/users/${encodeURIComponent(username)}`)
    userDetail.value = res.data
  } catch { ElMessage.error('加载用户详情失败') }
}

async function doDeleteUser(username) {
  if (username === 'root') return
  try {
    await axios.delete(`/admin/users/${encodeURIComponent(username)}`)
    ElMessage.success(`用户 ${username} 已删除`)
    showUserDetail.value = false
    await loadUsers()
  } catch { ElMessage.error('删除失败') }
}

async function confirmDeleteUser(username) {
  try {
    await ElMessageBox.confirm(`确定永久删除「${username}」及其所有数据？`, '警告', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await doDeleteUser(username)
  } catch {}
}

async function loadUsage() {
  usageLoading.value = true
  try {
    const res = await axios.get('/admin/usage-summary')
    usageList.value = res.data.items || []
  } catch { ElMessage.error('加载用量失败') }
  usageLoading.value = false
}

async function changePassword() {
  if (!pwdForm.value.old || !pwdForm.value.new1) {
    ElMessage.warning('请填写完整')
    return
  }
  if (pwdForm.value.new1 !== pwdForm.value.new2) {
    ElMessage.warning('两次密码不一致')
    return
  }
  if (pwdForm.value.new1.length < 6) {
    ElMessage.warning('密码至少6个字符')
    return
  }
  try {
    await axios.post('/admin/change-password', {
      old_password: pwdForm.value.old,
      new_password: pwdForm.value.new1,
    })
    ElMessage.success('密码已修改')
    pwdForm.value = { old: '', new1: '', new2: '' }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  }
}

async function loadLogs() {
  try {
    const res = await axios.get('/admin/logs', { params: { lines: logLines.value } })
    logFiles.value = res.data.logs || []
    if (logFiles.value.length && !activeLogTab.value) {
      activeLogTab.value = logFiles.value[0].filename
    }
  } catch { ElMessage.error('加载日志失败') }
}

async function purgeTemp() {
  try {
    await ElMessageBox.confirm('确定清理临时文件？', '提示')
    const res = await axios.post('/admin/purge-temp')
    ElMessage.success(res.data.message)
    await loadStatus()
  } catch {}
}

async function runDiagnose() {
  try {
    const res = await axios.post('/admin/diagnose')
    const s = res.data.suggestions || []
    diagnoseResult.value = s.length ? s.join('；') : '系统状态正常，暂无问题'
    setTimeout(() => { diagnoseResult.value = '' }, 8000)
  } catch { ElMessage.error('诊断失败') }
}

function goBack() {
  router.push('/admin')
}

function updateTabFromRoute() {
  const tab = route.query.tab
  if (tab && VALID_TABS.includes(tab)) {
    activeTab.value = tab
  } else if (!route.query.tab) {
    activeTab.value = 'dashboard'
  }
}

onMounted(() => {
  updateTabFromRoute()
  loadStatus()
  loadUsers()
  loadLogs()
  loadUsage()
})

watch(() => route.query.tab, () => {
  updateTabFromRoute()
})
</script>

<style scoped>
.admin-page { min-height: 100vh; background: #f0f2f5; }
.admin-header {
  background: #fff; padding: 16px 24px;
  display: flex; align-items: center; gap: 16px;
  border-bottom: 1px solid #e2e8f0; flex-wrap: wrap;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.header-left h1 { font-size: 20px; font-weight: 700; color: #1e293b; margin: 0; }
.header-hint { margin-left: auto; font-size: 12px; }
.header-actions { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }
.admin-content { max-width: 1200px; margin: 0 auto; padding: 24px; }
.stats-row { margin-bottom: 24px; }

.stat-card {
  text-align: center; border-radius: 12px; cursor: default;
  transition: transform 0.15s;
}
.stat-card:hover { transform: translateY(-2px); }
.stat-value {
  font-size: 28px; font-weight: 700; color: #1e293b;
  font-family: 'Courier New', monospace;
}
.stat-label { font-size: 12px; color: #64748b; margin-top: 4px; }
.stat-card.stat-ok .stat-value { color: #059669; }
.stat-card.stat-warning .stat-value { color: #dc2626; }
.stat-card.stat-info .stat-value { color: #7c3aed; }
.stat-card.stat-users .stat-value { color: #2563eb; }
.stat-card.stat-files .stat-value { color: #0891b2; }
.stat-card.stat-size .stat-value { color: #d97706; }

.detail-card { border-radius: 12px; margin-bottom: 16px; }
.card-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }

.action-list { display: flex; flex-direction: column; gap: 12px; }
.action-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px; background: #f8fafc; border-radius: 8px;
}
.action-info { display: flex; flex-direction: column; gap: 2px; }
.action-info strong { font-size: 14px; color: #334155; }
.action-desc { font-size: 12px; color: #94a3b8; }

.log-viewer {
  background: #1e293b; border-radius: 8px; padding: 16px;
  max-height: 600px; overflow: auto;
}
.log-content {
  margin: 0; font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px; line-height: 1.5; color: #e2e8f0;
  white-space: pre-wrap; word-break: break-all;
}
.log-error { color: #fc8181; font-size: 14px; }

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .admin-header {
    padding: 12px;
    gap: 8px;
  }
  .header-left h1 {
    font-size: 16px;
  }
  .header-actions {
    margin-left: 0;
    width: 100%;
  }
  .admin-content {
    padding: 16px 12px;
  }
  .stat-value {
    font-size: 22px;
  }
  .action-item {
    flex-wrap: wrap;
    gap: 8px;
  }
.log-viewer {
    padding: 12px;
    max-height: 400px;
  }
  :deep(.el-col-4),
  :deep(.el-col-12) {
    max-width: 100%;
    flex: 0 0 100%;
  }
}
</style>
