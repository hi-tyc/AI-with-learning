<template>
  <div class="materials-page">
    <div class="content">
      <h1 class="page-title">复习资料</h1>
      <p class="page-subtitle">上传试卷、讲义等复习资料，解题时可供 AI 参考</p>

      <!-- 上传卡片 -->
      <div class="upload-card" @click="triggerUpload">
        <div class="upload-icon-wrap">
          <el-icon size="32" color="#2563eb"><Upload /></el-icon>
        </div>
        <h3>上传复习资料</h3>
        <p>支持 PDF、Word（docx）、JPG / PNG 图片，可多选批量上传</p>
        <input
          ref="fileInputRef"
          type="file"
          style="display: none"
          accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
          multiple
          @change="handleFileChange"
        />
      </div>

      <!-- 上传弹窗 -->
      <el-dialog v-model="showUploadDialog" title="批量上传复习资料" width="560px">
        <el-form label-position="top">
          <!-- 文件列表 -->
          <el-form-item>
            <template #label>
              <span>已选文件 <span class="file-count">({{ selectedFiles.length }} 个)</span></span>
            </template>
            <div v-if="selectedFiles.length" class="pending-files">
              <div
                v-for="(file, idx) in selectedFiles"
                :key="idx"
                class="pending-file"
              >
                <el-icon size="16" :color="fileIconColor(guessType(file.name))">
                  <component :is="fileIcon(guessType(file.name))" />
                </el-icon>
                <span class="pending-name">{{ file.name }}</span>
                <span class="pending-size">{{ formatSize(file.size) }}</span>
                <el-button
                  text
                  size="small"
                  type="danger"
                  @click="removeFile(idx)"
                >
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
            </div>
            <el-empty v-else description="未选择文件" :image-size="60" />
          </el-form-item>

          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="学科">
                <el-select v-model="uploadSubject" style="width:100%">
                  <el-option label="数学" value="数学" />
                  <el-option label="物理" value="物理" />
                  <el-option label="化学" value="化学" />
                  <el-option label="语文" value="语文" />
                  <el-option label="英语" value="英语" />
                  <el-option label="历史" value="历史" />
                  <el-option label="地理" value="地理" />
                  <el-option label="生物" value="生物" />
                  <el-option label="政治" value="政治" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="时间">
                <el-date-picker
                  v-model="uploadTime"
                  type="date"
                  placeholder="选择日期"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                  style="width:100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <!-- 上传进度 -->
        <div v-if="isUploading" class="batch-progress">
          <el-progress
            :percentage="uploadPercent"
            :stroke-width="10"
            :status="uploadStatus"
          />
          <p class="progress-text">正在上传 {{ uploadDone }}/{{ uploadTotal }} …</p>
        </div>

        <template #footer>
          <el-button @click="showUploadDialog = false" :disabled="isUploading">取消</el-button>
          <el-button
            type="primary"
            @click="doBatchUpload"
            :loading="isUploading"
            :disabled="selectedFiles.length === 0"
          >
            批量上传
          </el-button>
        </template>
      </el-dialog>

      <!-- 资料列表 -->
      <div v-if="treeData.length" class="tree-panel">
        <div class="panel-header">
          <el-icon><Collection /></el-icon>
          <span>我的资料库</span>
          <span class="panel-count">共 {{ totalCount }} 份</span>
        </div>
        <el-collapse v-model="activeSubjects">
          <el-collapse-item
            v-for="subNode in treeData"
            :key="subNode.subject"
            :title="subNode.subject"
            :name="subNode.subject"
          >
            <template #title>
              <div class="collapse-title">
                <el-tag :type="subjectType(subNode.subject)" size="small">{{ subNode.subject }}</el-tag>
                <span class="sub-count">{{ subNode.count }} 份</span>
              </div>
            </template>
            <div class="time-list">
              <div
                v-for="timeNode in subNode.times"
                :key="timeNode.time"
                class="time-group"
              >
                <div class="time-label">
                  <el-icon><Calendar /></el-icon>
                  <span>{{ timeNode.time }}</span>
                  <span class="time-count">{{ timeNode.items.length }} 份</span>
                </div>
                <div class="file-list">
                  <div
                    v-for="item in timeNode.items"
                    :key="item.id"
                    class="file-item"
                  >
                    <el-icon size="18" :color="fileIconColor(item.file_type)">
                      <component :is="fileIcon(item.file_type)" />
                    </el-icon>
                    <span class="file-name">{{ item.filename }}</span>
                    <span v-if="item.has_text" class="file-badge">已提取</span>
                    <el-button
                      text
                      size="small"
                      type="danger"
                      @click="deleteMaterial(item.id)"
                    >
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <el-empty v-else description="暂无复习资料，点击上方上传" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, Collection, Calendar, Delete, Document, Picture, Close
} from '@element-plus/icons-vue'

const fileInputRef = ref(null)
const showUploadDialog = ref(false)
const isUploading = ref(false)
const rawTree = ref({})
const activeSubjects = ref([])

const selectedFiles = ref([])
const uploadSubject = ref('数学')
const uploadTime = ref('')

const uploadTotal = ref(0)
const uploadDone = ref(0)
const uploadStatus = ref('')

const uploadPercent = computed(() => {
  if (uploadTotal.value === 0) return 0
  return Math.round((uploadDone.value / uploadTotal.value) * 100)
})

const totalCount = computed(() => {
  let count = 0
  for (const sub in rawTree.value) {
    for (const t in rawTree.value[sub]) {
      count += rawTree.value[sub][t].count
    }
  }
  return count
})

const treeData = computed(() => {
  const result = []
  for (const subject in rawTree.value) {
    const times = []
    let subCount = 0
    for (const time in rawTree.value[subject]) {
      const node = rawTree.value[subject][time]
      times.push({
        time,
        items: node.items || [],
        count: node.count,
      })
      subCount += node.count
    }
    times.sort((a, b) => b.time.localeCompare(a.time))
    result.push({
      subject,
      count: subCount,
      times,
    })
  }
  const order = ['数学', '物理', '化学', '语文', '英语', '历史', '地理', '生物', '政治']
  result.sort((a, b) => {
    const ai = order.indexOf(a.subject)
    const bi = order.indexOf(b.subject)
    if (ai !== -1 && bi !== -1) return ai - bi
    if (ai !== -1) return -1
    if (bi !== -1) return 1
    return a.subject.localeCompare(b.subject)
  })
  return result
})

function triggerUpload() {
  fileInputRef.value?.click()
}

function handleFileChange(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  selectedFiles.value = files
  uploadTime.value = new Date().toISOString().split('T')[0]
  showUploadDialog.value = true
  event.target.value = ''
}

function removeFile(idx) {
  selectedFiles.value.splice(idx, 1)
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function guessType(filename) {
  const lower = filename.toLowerCase()
  if (lower.endsWith('.pdf')) return 'pdf'
  if (lower.endsWith('.docx')) return 'docx'
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.png')) return 'image'
  return 'pdf'
}

async function doBatchUpload() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadSubject.value) {
    ElMessage.warning('请选择学科')
    return
  }
  if (!uploadTime.value) {
    ElMessage.warning('请选择时间')
    return
  }

  isUploading.value = true
  uploadTotal.value = selectedFiles.value.length
  uploadDone.value = 0
  uploadStatus.value = ''
  let successCount = 0
  let failCount = 0

  try {
    for (const file of selectedFiles.value) {
      const form = new FormData()
      form.append('file', file)
      form.append('subject', uploadSubject.value)
      form.append('time', uploadTime.value)

      try {
        await axios.post('/materials', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        successCount++
      } catch (e) {
        failCount++
        console.error('上传失败', file.name, e)
      }
      uploadDone.value++
    }

    if (successCount > 0) {
      uploadStatus.value = 'success'
      ElMessage.success(`${successCount} 个文件上传成功`)
      if (failCount > 0) {
        ElMessage.warning(`${failCount} 个文件上传失败`)
      }
      showUploadDialog.value = false
      selectedFiles.value = []
      uploadSubject.value = '数学'
      uploadTime.value = ''
      await loadTree()
    } else {
      uploadStatus.value = 'exception'
      ElMessage.error('所有文件上传失败')
    }
  } finally {
    isUploading.value = false
    uploadTotal.value = 0
    uploadDone.value = 0
  }
}

async function loadTree() {
  try {
    const res = await axios.get('/materials/tree')
    rawTree.value = res.data || {}
    activeSubjects.value = treeData.value.map(n => n.subject)
  } catch (e) {
    console.error('加载资料失败', e)
  }
}

async function deleteMaterial(id) {
  try {
    await ElMessageBox.confirm('确定删除这份复习资料？', '提示', { type: 'warning' })
    await axios.delete(`/materials/${id}`)
    ElMessage.success('已删除')
    await loadTree()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function subjectType(subject) {
  const map = { '数学': 'primary', '物理': 'success', '化学': 'warning', '语文': '', '英语': 'info' }
  return map[subject] || ''
}

function fileIcon(type) {
  if (type === 'image') return Picture
  if (type === 'docx') return Document
  return Document
}

function fileIconColor(type) {
  if (type === 'image') return '#10b981'
  if (type === 'docx') return '#2563eb'
  return '#f59e0b'
}

loadTree()
</script>

<style scoped>
.materials-page {
  min-height: 100vh;
  background: #f8fafc;
}
.content {
  max-width: min(960px, 100% - 48px);
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}
.page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0 0 32px;
}

.upload-card {
  background: #fff;
  border: 2px dashed #e2e8f0;
  border-radius: 16px;
  padding: 40px 24px;
  cursor: pointer;
  transition: all 0.25s ease;
  text-align: center;
  margin-bottom: 24px;
}
.upload-card:hover {
  border-color: #2563eb;
  background: #f8fafc;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
}
.upload-icon-wrap {
  width: 64px;
  height: 64px;
  border-radius: 18px;
  background: #eff6ff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}
.upload-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 6px;
}
.upload-card p {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.tree-panel {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 24px;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 16px;
}
.panel-count {
  margin-left: auto;
  font-size: 13px;
  color: #94a3b8;
  font-weight: normal;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 4px;
}
.sub-count {
  font-size: 12px;
  color: #94a3b8;
}

.time-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-left: 8px;
}
.time-group {
  border-left: 2px solid #e2e8f0;
  padding-left: 12px;
}
.time-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #475569;
  font-weight: 500;
  margin-bottom: 8px;
}
.time-count {
  font-size: 12px;
  color: #94a3b8;
  font-weight: normal;
  margin-left: auto;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 10px;
  transition: all 0.15s ease;
}
.file-item:hover {
  background: #f1f5f9;
}
.file-name {
  flex: 1;
  font-size: 13px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-badge {
  font-size: 11px;
  color: #059669;
  background: #f0fdf4;
  padding: 2px 8px;
  border-radius: 4px;
}

/* 待上传文件列表 */
.file-count {
  font-size: 12px;
  color: #94a3b8;
  font-weight: normal;
}
.pending-files {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}
.pending-file {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 8px;
}
.pending-name {
  flex: 1;
  font-size: 13px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pending-size {
  font-size: 11px;
  color: #94a3b8;
  font-family: monospace;
}

/* 批量进度 */
.batch-progress {
  margin-top: 12px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
}
.progress-text {
  font-size: 13px;
  color: #64748b;
  margin: 8px 0 0;
  text-align: center;
}

@media (max-width: 768px) {
  .content {
    padding: 16px 12px;
  }
  .page-title {
    font-size: 22px;
  }
  .page-subtitle {
    font-size: 13px;
    margin-bottom: 20px;
  }
  .upload-card {
    padding: 24px 16px;
  }
  .upload-card h3 {
    font-size: 16px;
  }
  .upload-card p {
    font-size: 13px;
  }
  .upload-icon-wrap {
    width: 52px;
    height: 52px;
    border-radius: 14px;
  }
  .tree-panel {
    padding: 16px;
  }
  .panel-header {
    font-size: 14px;
    margin-bottom: 12px;
  }
  .time-list {
    padding-left: 0;
  }
  .time-group {
    padding-left: 8px;
  }
  .file-item {
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 10px;
  }
  .file-name {
    flex: 1 0 60%;
    font-size: 12px;
  }
  .pending-file {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 10px;
  }
  .pending-name {
    flex: 1 0 60%;
    font-size: 12px;
  }
  .collapse-title {
    padding-left: 0;
  }
  :deep(.el-dialog) {
    width: 92% !important;
    max-width: 92%;
    margin: 0 auto;
  }
  :deep(.el-row) {
    flex-wrap: wrap;
  }
  :deep(.el-col-12) {
    max-width: 100%;
    flex: 0 0 100%;
  }
}
</style>
