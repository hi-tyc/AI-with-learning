<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h1>管理员工作台</h1>
        <p>创建班型、班级和教师账号。教师资料分发与统计在教师工作台完成。</p>
      </div>
      <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-card">
          <div class="label">班型</div>
          <div class="value">{{ summary.class_type_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-card">
          <div class="label">班级</div>
          <div class="value">{{ summary.class_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-card">
          <div class="label">教师/学生档案</div>
          <div class="value">{{ managedUsers.length }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-card">
          <div class="label">待审核申请</div>
          <div class="value">{{ pendingRegistrations.length }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="admin-grid">
      <section class="surface">
        <div class="surface-header">
          <h2>新建班型</h2>
        </div>
        <el-form label-position="top">
          <el-form-item label="班型名称">
            <el-input v-model="classTypeForm.name" placeholder="例如：初一南外" />
          </el-form-item>
          <el-form-item label="说明">
            <el-input v-model="classTypeForm.description" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="createClassType">创建班型</el-button>
          </el-form-item>
        </el-form>
      </section>

      <section class="surface">
        <div class="surface-header">
          <h2>新建班级</h2>
        </div>
        <el-form label-position="top">
          <el-form-item label="班型">
            <el-select v-model="classForm.classTypeId" style="width:100%">
              <el-option v-for="item in classTypes" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="班级名称">
            <el-input v-model="classForm.name" placeholder="例如：周四下午" />
          </el-form-item>
          <el-form-item label="授课教师用户名">
            <el-select v-model="classForm.teacherUsernames" multiple filterable allow-create default-first-option style="width:100%">
              <el-option v-for="item in teacherOptions" :key="item.username" :label="item.username" :value="item.username" />
            </el-select>
          </el-form-item>
          <el-form-item label="学生名单">
            <el-input v-model="classForm.rosterText" type="textarea" :rows="5" placeholder="每行一个姓名，或用逗号分隔" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="createClass">创建班级</el-button>
          </el-form-item>
        </el-form>
      </section>
    </div>

    <div class="admin-grid">
      <section class="surface">
        <div class="surface-header">
          <h2>创建教师/学生账号</h2>
          <span>为后续审批流程预留了学生角色字段。</span>
        </div>
        <el-form label-position="top">
          <el-form-item label="用户名">
            <el-input v-model="userForm.username" />
          </el-form-item>
          <el-form-item label="真实姓名">
            <el-input v-model="userForm.realName" />
          </el-form-item>
          <el-form-item label="角色">
            <el-radio-group v-model="userForm.role">
              <el-radio-button label="teacher">教师</el-radio-button>
              <el-radio-button label="student">学生</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="初始密码">
            <el-input v-model="userForm.password" type="password" show-password />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="userForm.activateNow">立即激活</el-checkbox>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="createManagedUser">创建账号</el-button>
          </el-form-item>
        </el-form>
      </section>

      <section class="surface">
        <div class="surface-header">
          <h2>终端提权工具</h2>
        </div>
        <el-alert
          title="本地 CLI 已加入仓库，可直接把现有用户设为管理员。"
          type="info"
          :closable="false"
          show-icon
        />
        <pre class="cli-block">python3 tools/manage_users.py promote-admin 用户名</pre>
        <pre class="cli-block">python3 tools/manage_users.py set-role 用户名 teacher --activate</pre>
      </section>
    </div>

    <section class="surface">
      <div class="surface-header">
        <h2>注册审核</h2>
      </div>
      <el-table :data="registrations" stripe>
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="real_name" label="真实姓名" width="140" />
        <el-table-column prop="submitted_at" label="提交时间" width="180">
          <template #default="{ row }">{{ row.submitted_at ? new Date(row.submitted_at).toLocaleString('zh-CN') : '-' }}</template>
        </el-table-column>
        <el-table-column label="申请班级" min-width="160">
          <template #default="{ row }">{{ classNames(row.class_ids).join('、') || '-' }}</template>
        </el-table-column>
        <el-table-column label="验证" width="160">
          <template #default="{ row }">
            <div>{{ row.captcha_verified ? '人机已过' : '人机未过' }}</div>
            <div>{{ row.face_aligned ? '人脸已对齐' : '人脸未对齐' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="授权" min-width="220">
          <template #default="{ row }">
            <div>{{ row.face_consent_accepted ? '已确认授权' : '未确认授权' }}</div>
            <div class="table-subline">{{ row.face_consent_version || '-' }}</div>
            <div class="table-subline">{{ formatDateTime(row.face_consent_at) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">{{ row.approval_status }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" :disabled="!row.face_video_available" @click="openVideo(row)">
              {{ row.face_video_available ? '查看视频' : '视频已删除' }}
            </el-button>
            <el-button text size="small" type="primary" @click="openReviewDialog(row, 'approve')">通过</el-button>
            <el-button text size="small" type="danger" @click="openReviewDialog(row, 'reject')">拒绝</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="surface">
      <div class="surface-header">
        <h2>班型与班级</h2>
      </div>
      <el-table :data="classes" stripe>
        <el-table-column prop="class_type_name" label="班型" width="160" />
        <el-table-column prop="name" label="班级" width="180" />
        <el-table-column label="教师" min-width="180">
          <template #default="{ row }">{{ (row.teacher_usernames || []).join('、') || '-' }}</template>
        </el-table-column>
        <el-table-column label="学生数" width="90">
          <template #default="{ row }">{{ row.student_count || 0 }}</template>
        </el-table-column>
      </el-table>
    </section>

    <section class="surface">
      <div class="surface-header">
        <h2>账号列表</h2>
      </div>
      <el-table :data="managedUsers" stripe>
        <el-table-column prop="username" label="用户名" width="160" />
        <el-table-column prop="real_name" label="真实姓名" width="140" />
        <el-table-column prop="role" label="角色" width="100" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="班级数" width="100">
          <template #default="{ row }">{{ row.class_ids?.length || 0 }}</template>
        </el-table-column>
        <el-table-column prop="expires_at" label="有效期" min-width="180">
          <template #default="{ row }">{{ row.expires_at || '长期有效' }}</template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="reviewDialog.visible" :title="reviewDialog.action === 'approve' ? '通过申请' : '拒绝申请'" width="520px">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input :model-value="reviewDialog.username" disabled />
        </el-form-item>
        <el-form-item label="人脸授权">
          <div class="consent-review">
            <div>{{ reviewDialog.faceConsentAccepted ? '申请人已确认人脸采集授权' : '申请人未确认人脸采集授权' }}</div>
            <div class="table-subline">版本：{{ reviewDialog.faceConsentVersion || '-' }}</div>
            <div class="table-subline">确认时间：{{ formatDateTime(reviewDialog.faceConsentAt) }}</div>
          </div>
        </el-form-item>
        <el-form-item v-if="reviewDialog.action === 'approve'" label="分配班级">
          <el-select v-model="reviewDialog.classIds" multiple filterable style="width:100%">
            <el-option v-for="item in classes" :key="item.id" :label="item.class_type_name ? `${item.class_type_name} / ${item.name}` : item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="reviewDialog.action === 'approve'" label="有效期">
          <el-input v-model="reviewDialog.expiresAt" placeholder="2026-12-31T23:59:59，可留空" />
        </el-form-item>
        <el-alert
          v-if="reviewDialog.action === 'approve'"
          title="确认通过后，人脸审核视频会立刻从本机永久删除，只保留审核记录。"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
        <el-form-item label="审核备注">
          <el-input v-model="reviewDialog.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialog.visible = false">取消</el-button>
        <el-button :type="reviewDialog.action === 'approve' ? 'primary' : 'danger'" @click="submitReview">
          {{ reviewDialog.action === 'approve' ? '确认通过' : '确认拒绝' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="videoDialog.visible" title="人脸审核视频" width="720px" @closed="closeVideoDialog">
      <div class="video-review-box">
        <video
          v-if="videoDialog.visible"
          :key="videoDialog.src"
          :src="videoDialog.src"
          controls
          controlsList="nodownload noplaybackrate"
          disablePictureInPicture
          playsinline
          class="review-video"
          @contextmenu.prevent
        ></video>
        <div class="table-subline">视频仅用于在线审核；通过申请后会立即从本机删除。</div>
      </div>
      <template #footer>
        <el-button @click="videoDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const summary = ref({})
const classTypes = ref([])
const classes = ref([])
const managedUsers = ref([])
const registrations = ref([])

const classTypeForm = ref({
  name: '',
  description: '',
})

const classForm = ref({
  classTypeId: '',
  name: '',
  teacherUsernames: [],
  rosterText: '',
})

const userForm = ref({
  username: '',
  realName: '',
  role: 'teacher',
  password: '',
  activateNow: true,
})

const reviewDialog = ref({
  visible: false,
  action: 'approve',
  username: '',
  classIds: [],
  expiresAt: '',
  note: '',
  faceConsentAccepted: false,
  faceConsentVersion: '',
  faceConsentAt: '',
})

const videoDialog = ref({
  visible: false,
  username: '',
  src: '',
})

const teacherOptions = computed(() => managedUsers.value.filter(item => item.role === 'teacher'))
const pendingRegistrations = computed(() => registrations.value.filter(item => item.approval_status === 'pending'))

function classNames(ids = []) {
  const map = new Map(classes.value.map(item => [item.id, item.name]))
  return ids.map(id => map.get(id) || id)
}

function formatDateTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

async function loadAll() {
  const [summaryRes, classTypesRes, classesRes, usersRes, registrationsRes] = await Promise.all([
    axios.get('/school/summary'),
    axios.get('/school/class-types'),
    axios.get('/school/classes'),
    axios.get('/school/users'),
    axios.get('/school/registrations'),
  ])
  summary.value = summaryRes.data
  classTypes.value = classTypesRes.data.items || []
  classes.value = classesRes.data.items || []
  managedUsers.value = usersRes.data.items || []
  registrations.value = registrationsRes.data.items || []
}

async function createClassType() {
  try {
    await axios.post('/school/class-types', {
      name: classTypeForm.value.name,
      description: classTypeForm.value.description,
    })
    ElMessage.success('班型已创建')
    classTypeForm.value = { name: '', description: '' }
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

async function createClass() {
  try {
    await axios.post('/school/classes', {
      name: classForm.value.name,
      class_type_id: classForm.value.classTypeId,
      teacher_usernames: classForm.value.teacherUsernames,
      roster_text: classForm.value.rosterText,
    })
    ElMessage.success('班级已创建')
    classForm.value = { classTypeId: '', name: '', teacherUsernames: [], rosterText: '' }
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

async function createManagedUser() {
  try {
    await axios.post('/school/users', {
      username: userForm.value.username,
      real_name: userForm.value.realName,
      role: userForm.value.role,
      password: userForm.value.password,
      activate_now: userForm.value.activateNow,
    })
    ElMessage.success('账号已创建')
    userForm.value = { username: '', realName: '', role: 'teacher', password: '', activateNow: true }
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

function openVideo(row) {
  if (!row.face_video_available) {
    ElMessage.warning('视频已删除或不可用')
    return
  }
  videoDialog.value = {
    visible: true,
    username: row.username,
    src: `/api/auth/registration-video/${encodeURIComponent(row.username)}?t=${Date.now()}`,
  }
}

function closeVideoDialog() {
  videoDialog.value = {
    visible: false,
    username: '',
    src: '',
  }
}

function openReviewDialog(row, action) {
  reviewDialog.value = {
    visible: true,
    action,
    username: row.username,
    classIds: [...(row.class_ids || [])],
    expiresAt: row.expires_at || '',
    note: row.review_notes || '',
    faceConsentAccepted: !!row.face_consent_accepted,
    faceConsentVersion: row.face_consent_version || '',
    faceConsentAt: row.face_consent_at || '',
  }
}

async function submitReview() {
  try {
    await axios.post(`/school/registrations/${encodeURIComponent(reviewDialog.value.username)}/review`, {
      action: reviewDialog.value.action,
      class_ids: reviewDialog.value.classIds,
      expires_at: reviewDialog.value.expiresAt || null,
      note: reviewDialog.value.note,
    })
    ElMessage.success('审核已更新')
    reviewDialog.value.visible = false
    if (reviewDialog.value.action === 'approve' && videoDialog.value.username === reviewDialog.value.username) {
      closeVideoDialog()
    }
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '审核失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.admin-page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header,
.surface-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-header h1,
.surface-header h2 {
  margin: 0;
}
.page-header p,
.surface-header span {
  margin: 6px 0 0;
  color: #64748b;
}
.summary-card,
.surface {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 18px;
}
.label {
  color: #64748b;
  font-size: 13px;
}
.value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 700;
  color: #0f172a;
}
.admin-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.cli-block {
  margin: 12px 0 0;
  padding: 12px;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  overflow: auto;
}
.table-subline {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.consent-review {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
}
.video-review-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.review-video {
  width: 100%;
  max-height: 64vh;
  background: #020617;
  border-radius: 8px;
}
@media (max-width: 960px) {
  .admin-grid {
    grid-template-columns: 1fr;
  }
}
</style>
