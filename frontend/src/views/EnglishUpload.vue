<template>
  <div class="english-upload-page">
    <div class="content">
      <h1 class="page-title">上传资料</h1>
      <p class="page-subtitle">上传英语试卷、讲义等，AI 自动判断是题目、答案还是资料</p>

      <!-- 上传卡片 -->
      <div class="upload-card" @click="triggerUpload">
        <div class="upload-icon-wrap">
          <el-icon size="32" color="#2563eb"><Upload /></el-icon>
        </div>
        <h3>选择文件上传</h3>
        <p>支持 PDF、Word（docx）、JPG / PNG 图片，可多选</p>
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
      <el-dialog v-model="showDialog" title="上传英语资料" width="520px">
        <el-form label-position="top">
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
                <el-icon size="16" color="#64748b"><Document /></el-icon>
                <span class="pending-name">{{ file.name }}</span>
                <span class="pending-size">{{ formatSize(file.size) }}</span>
                <el-button text size="small" type="danger" @click="removeFile(idx)">
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
            </div>
            <el-empty v-else description="未选择文件" :image-size="60" />
          </el-form-item>

          <el-form-item label="考试标签">
            <el-select v-model="uploadTag" style="width:100%">
              <el-option label="月考1" value="月考1" />
              <el-option label="期中" value="期中" />
              <el-option label="月考2" value="月考2" />
              <el-option label="期末" value="期末" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="学期">
            <el-select v-model="uploadSemester" style="width:100%">
              <el-option label="不指定学期" value="" />
              <el-option label="25-26 第一学期" value="25-26 第一学期" />
              <el-option label="25-26 第二学期" value="25-26 第二学期" />
              <el-option label="26-27 第一学期" value="26-27 第一学期" />
              <el-option label="26-27 第二学期" value="26-27 第二学期" />
            </el-select>
          </el-form-item>
        </el-form>

        <template #footer>
          <el-button @click="showDialog = false" :disabled="isUploading">取消</el-button>
          <el-button type="primary" @click="doUpload" :loading="isUploading" :disabled="selectedFiles.length === 0">
            上传并分析
          </el-button>
        </template>
      </el-dialog>

      <!-- 流式输出（每个文档独立窗口） -->
      <div v-if="fileStreamKeys.length" class="stream-panel">
        <div class="panel-header">
          <el-icon><Loading /></el-icon>
          <span>AI 输出</span>
          <el-tag v-if="isUploading" size="small" type="primary" effect="light" class="animate-pulse">分析中</el-tag>
        </div>
        <el-tabs v-model="activeFileIndex" type="card" class="file-tabs" @tab-click="onTabClick">
          <el-tab-pane
            v-for="idx in fileStreamKeys"
            :key="idx"
            :name="String(idx)"
            :label="fileTabLabel(idx)"
            :closable="false"
          >
            <pre class="stream-text" :ref="el => { if (el) streamRefs[idx] = el }">{{ fileStreams[idx] || '(等待AI输出...)' }}</pre>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 失败文件 + 重试 -->
      <div v-if="failedFiles.length" class="failed-panel">
        <div class="panel-header">
          <el-icon><WarningFilled /></el-icon>
          <span>上传失败（可重试）</span>
        </div>
        <div class="failed-list">
          <div v-for="(f, idx) in failedFiles" :key="idx" class="failed-item">
            <el-icon size="16" color="#dc2626"><Close /></el-icon>
            <span class="failed-name">{{ f.file.name }}</span>
            <span class="failed-error">{{ f.error }}</span>
            <el-button size="small" type="warning" :disabled="isUploading" @click="retryFile(f)">
              <el-icon><Refresh /></el-icon> 重试
            </el-button>
          </div>
        </div>
      </div>

      <!-- 上传结果 -->
      <div v-if="results.length" class="results-panel">
        <div class="panel-header">
          <el-icon><DocumentChecked /></el-icon>
          <span>AI 分析结果</span>
        </div>
        <div class="results-list">
          <div
            v-for="(res, idx) in results"
            :key="idx"
            class="result-item"
            :class="res.type"
          >
            <div class="result-filename">{{ res.filename }}</div>
            <div class="result-type">
              <el-tag :type="tagType(res.type)" size="small" effect="dark">{{ res.type }}</el-tag>
              <span class="result-tag">{{ res.tag }}</span>
            </div>
            <p class="result-reason">{{ res.reason }}</p>
            <p v-if="res.summary" class="result-summary">摘要：{{ res.summary }}</p>
            <div class="result-meta">
              <span :class="res.confidence < 0.6 ? 'conf-low' : ''">置信度 {{ Math.round(res.confidence * 100) }}%</span>
              <span>共 {{ res.count }} 条</span>
              <el-button v-if="res.confidence < 0.6" size="small" text type="warning" @click="showManualClassify(res)">
                <el-icon><Edit /></el-icon> 手动分类
              </el-button>
              <el-button v-else size="small" text type="warning" @click="showAdjustType(res)">
                <el-icon><Edit /></el-icon> 调整类型
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 手动分类弹窗（识别失败时使用） -->
      <el-dialog v-model="manualClassify.visible" title="手动选择类型" width="600px" class="resize-dialog" draggable>
        <p style="margin:0 0 8px;color:#475569">AI 无法确定文件类型，请手动选择：</p>
        <p style="margin:0 0 16px;color:#64748b;font-size:13px">文件：<strong>{{ manualClassify.filename }}</strong></p>
        <el-form label-position="top">
          <el-form-item label="资料类型">
            <el-radio-group v-model="manualClassify.type">
              <el-radio value="题目">题目（练习题、试卷）</el-radio>
              <el-radio value="答案">答案（已填好的答案）</el-radio>
              <el-radio value="词单">词单（单词列表）</el-radio>
              <el-radio value="资料">资料（知识点整理）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="考试标签">
            <el-select v-model="manualClassify.tag" style="width:100%">
              <el-option label="未分类" value="" />
              <el-option label="月考1" value="月考1" />
              <el-option label="期中" value="期中" />
              <el-option label="月考2" value="月考2" />
              <el-option label="期末" value="期末" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="学期">
            <el-select v-model="manualClassify.semester" style="width:100%">
              <el-option label="不指定" value="" />
              <el-option label="25-26 第一学期" value="25-26 第一学期" />
              <el-option label="25-26 第二学期" value="25-26 第二学期" />
              <el-option label="26-27 第一学期" value="26-27 第一学期" />
              <el-option label="26-27 第二学期" value="26-27 第二学期" />
            </el-select>
          </el-form-item>
        </el-form>
        <p v-if="manualClassify.resultMsg" style="margin:12px 0 0;padding:10px;background:#f0fdf4;border-radius:8px;font-size:13px;color:#065f46">
          {{ manualClassify.resultMsg }}
        </p>
        <template #footer>
          <el-button @click="manualClassify.visible = false">取消</el-button>
          <el-button type="primary" @click="doManualClassify" :loading="manualClassify.loading">
            {{ manualClassify.extracted ? '保存完成' : '保存并让AI识别条目' }}
          </el-button>
        </template>
      </el-dialog>

      <!-- 调整类型弹窗 -->
      <el-dialog v-model="adjustDialog.visible" title="调整资料类型" width="520px" class="resize-dialog" draggable>
        <p style="margin:0 0 16px;color:#475569">当前文件：<strong>{{ adjustDialog.filename }}</strong></p>
        <p style="margin:0 0 12px;color:#64748b">当前类型：<el-tag :type="tagType(adjustDialog.currentType)" size="small" effect="dark">{{ adjustDialog.currentType }}</el-tag></p>
        <el-form label-position="top">
          <el-form-item label="调整为目标类型">
            <el-select v-model="adjustDialog.targetType" style="width:100%">
              <el-option v-for="t in adjustTypeOptions" :key="t" :label="t" :value="t" :disabled="t === adjustDialog.currentType" />
            </el-select>
          </el-form-item>
        </el-form>
        <p v-if="adjustDialog.resultMsg" style="margin:12px 0 0;padding:10px;background:#f0fdf4;border-radius:8px;font-size:13px;color:#065f46;white-space:pre-wrap">
          {{ adjustDialog.resultMsg }}
        </p>
        <template #footer>
          <el-button @click="adjustDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="doAdjustType" :loading="adjustDialog.loading">确认调整</el-button>
        </template>
      </el-dialog>

      <!-- 资料库 -->
      <div v-if="tagTreeKeys.length" class="tree-panel">
        <div class="panel-header">
          <el-icon><Collection /></el-icon>
          <span>我的文件库</span>
        </div>
        <el-collapse v-model="activeTags">
          <el-collapse-item
            v-for="tag in tagTreeKeys"
            :key="tag"
            :title="tag"
            :name="tag"
          >
            <template #title>
              <div class="collapse-title">
                <el-tag size="small">{{ tag }}</el-tag>
                <span class="tag-count">{{ tagTree[tag].count }} 份</span>
              </div>
            </template>
            <div class="file-list">
              <div
                v-for="item in tagTree[tag].items"
                :key="item.id"
                class="file-item"
              >
                <el-icon size="18" :color="fileIconColor(item.file_type)">
                  <component :is="fileIcon(item.file_type)" />
                </el-icon>
                <el-tag :type="item._type === '资料' ? 'warning' : item._type === '题目' ? 'primary' : 'success'" size="small" effect="plain">{{ item._type }}</el-tag>
                <span class="file-name">{{ item.filename }}</span>
                <span v-if="item.has_text" class="file-badge">已提取</span>
                <el-button text size="small" type="danger" @click="deleteMaterial(item)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <el-empty v-else-if="!results.length" description="暂无上传记录" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Collection, Delete, Document, Close, DocumentChecked, Loading, Refresh, WarningFilled, Edit } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app.js'

const app = useAppStore()
const fileInputRef = ref(null)
const showDialog = ref(false)
const isUploading = ref(false)
const selectedFiles = ref([])
const uploadTag = ref('期中')
const uploadSemester = ref('')
const results = ref([])
const failedFiles = ref([])
const tagTree = ref({})
const activeTags = ref([])
const rawAllProblems = ref([])
const rawAllAnswers = ref([])
const manualClassify = ref({
  visible: false,
  filename: '',
  fileId: '',
  type: '题目',
  tag: '',
  semester: '',
  loading: false,
  extracted: false,
  resultMsg: '',
})

const adjustDialog = ref({
  visible: false,
  filename: '',
  fileId: '',
  sourceFile: '',
  currentType: '',
  targetType: '',
  tag: '',
  semester: '',
  loading: false,
  resultMsg: '',
})

const adjustTypeOptions = computed(() => {
  const all = ['题目', '答案', '词单', '资料']
  const cur = adjustDialog.value.currentType
  return all.filter(t => t !== cur)
})

function showManualClassify(res) {
  manualClassify.value = {
    visible: true,
    filename: res.filename,
    fileId: res.file_id || '',
    type: '题目',
    tag: '',
    semester: '',
    loading: false,
    extracted: false,
    resultMsg: '',
  }
}

async function doManualClassify() {
  manualClassify.value.loading = true
  manualClassify.value.resultMsg = ''
  manualClassify.value.extracted = false
  let hasError = false
  let finalResult = null

  try {
    const payload = {
      filename: manualClassify.value.filename,
      type: manualClassify.value.type,
      file_id: manualClassify.value.fileId,
      tag: manualClassify.value.tag,
      semester: manualClassify.value.semester,
    }
    const res = await fetch('/api/english-upload/extract-known', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include',
    })
    if (!res.ok) {
      const detail = await res.text().catch(() => '请求失败')
      throw new Error(detail)
    }
    if (!res.body) {
      throw new Error('服务器响应体为空')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        if (buffer.trim()) {
          const lines = buffer.split(/\r?\n/)
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data: ')) continue
            const p = trimmed.slice(6)
            if (p === '[DONE]') break
            try { processPayload(p) } catch { }
          }
        }
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const lines = part.split(/\r?\n/)
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const p = trimmed.slice(6)
          if (p === '[DONE]') break
          try { processPayload(p) } catch { }
        }
      }
    }

    function processPayload(p) {
      const msg = JSON.parse(p)
      if (msg.type === 'text' || msg.type === 'ai_token') {
        manualClassify.value.resultMsg += msg.text
      } else if (msg.type === 'result') {
        finalResult = msg
        manualClassify.value.extracted = true
        const isWordList = msg.doc_type === '词单'
        const count = isWordList ? (msg.word_count || 0) + '词' : (msg.count || 0) + '条'
        manualClassify.value.resultMsg += `\n已保存为「${msg.doc_type || msg.type}」，共 ${count}`

        const r = results.value.find(r => r.filename === manualClassify.value.filename)
        if (r) {
          r.type = msg.doc_type || msg.type
          r.count = isWordList ? (msg.word_count || 0) : (msg.count || 0)
          r.confidence = 0.95
        }
      } else if (msg.type === 'error') {
        hasError = true
        manualClassify.value.resultMsg += '\n❌ ' + (msg.text || '操作失败')
      }
    }

    if (!finalResult && !hasError) {
      throw new Error('未收到完整结果')
    }
    await loadTree()
  } catch (e) {
    manualClassify.value.resultMsg = '❌ ' + (e.message || '操作失败')
  } finally {
    manualClassify.value.loading = false
  }
}

function showAdjustType(res) {
  adjustDialog.value = {
    visible: true,
    filename: res.filename,
    fileId: res.file_id || '',
    sourceFile: res.source_file || res.filename,
    currentType: res.type,
    targetType: '',
    tag: res.tag || res.exam || '',
    semester: res.semester || '',
    loading: false,
    resultMsg: '',
  }
}

async function doAdjustType() {
  if (!adjustDialog.value.targetType) {
    ElMessage.warning('请选择目标类型')
    return
  }
  adjustDialog.value.loading = true
  adjustDialog.value.resultMsg = ''
  let hasError = false
  let finalResult = null

  try {
    const res = await fetch('/api/english-upload/adjust-type', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_file: adjustDialog.value.sourceFile,
        current_type: adjustDialog.value.currentType,
        new_type: adjustDialog.value.targetType,
        file_id: adjustDialog.value.fileId,
        filename: adjustDialog.value.filename,
        tag: adjustDialog.value.tag,
        semester: adjustDialog.value.semester,
      }),
      credentials: 'include',
    })
    if (!res.ok) {
      const detail = await res.text().catch(() => '请求失败')
      throw new Error(detail)
    }
    if (!res.body) {
      throw new Error('服务器响应体为空')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        if (buffer.trim()) {
          const lines = buffer.split(/\r?\n/)
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data: ')) continue
            const p = trimmed.slice(6)
            if (p === '[DONE]') break
            try { processPayload(p) } catch { }
          }
        }
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const lines = part.split(/\r?\n/)
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const p = trimmed.slice(6)
          if (p === '[DONE]') break
          try { processPayload(p) } catch { }
        }
      }
    }

    function processPayload(p) {
      const msg = JSON.parse(p)
      if (msg.type === 'text' || msg.type === 'ai_token') {
        adjustDialog.value.resultMsg += msg.text
      } else if (msg.type === 'result') {
        finalResult = msg
        adjustDialog.value.resultMsg += '\n' + (msg.message || '类型调整成功')
        ElMessage.success(msg.message || '类型调整成功')
        adjustDialog.value.visible = false
        const r = results.value.find(r => r.filename === adjustDialog.value.filename)
        if (r) {
          r.type = adjustDialog.value.targetType
          r.count = msg.word_count || msg.count || 0
        }
      } else if (msg.type === 'error') {
        hasError = true
        adjustDialog.value.resultMsg += '\n❌ ' + (msg.text || '操作失败')
        ElMessage.error(msg.text || '调整失败')
      }
    }

    if (!finalResult && !hasError) {
      throw new Error('未收到完整结果')
    }
    await loadTree()
  } catch (e) {
    adjustDialog.value.resultMsg = '❌ ' + (e.message || '调整失败')
    ElMessage.error(e.message || '调整失败')
  } finally {
    adjustDialog.value.loading = false
  }
}

// 每个文档的独立AI输出窗口
const fileStreams = ref({})
const activeFileIndex = ref('')
const fileNames = ref({})
const fileStatuses = ref({})

const fileStreamKeys = computed(() => {
  return Object.keys(fileStreams.value).sort((a, b) => Number(a) - Number(b))
})

const tagTreeKeys = computed(() => {
  return Object.keys(tagTree.value).sort()
})

function fileTabLabel(idx) {
  const raw = fileNames.value[idx] || `文件 ${idx}`
  const name = raw.length > 18 ? raw.slice(0, 16) + '…' : raw
  const status = fileStatuses.value[idx] || ''
  const icons = { uploading: '⏳', done: '✅', error: '❌' }
  return (icons[status] || '⏳') + ' ' + name
}

const streamRefs = {}
function scrollStream() {
  const el = streamRefs[activeFileIndex.value]
  if (el) { nextTick(() => { el.scrollTop = el.scrollHeight }) }
}
function onTabClick() {
  scrollStream()
}

function ensureFileStream(idx, filename) {
  if (!fileStreams.value[idx]) {
    fileStreams.value = { ...fileStreams.value, [idx]: '' }
    fileNames.value = { ...fileNames.value, [idx]: filename }
    fileStatuses.value = { ...fileStatuses.value, [idx]: 'uploading' }
  }
  if (!activeFileIndex.value) {
    activeFileIndex.value = String(idx)
  }
}

function triggerUpload() {
  fileInputRef.value?.click()
}

function handleFileChange(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  selectedFiles.value = files
  showDialog.value = true
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

function tagType(type) {
  if (type === '题目') return 'primary'
  if (type === '答案') return 'success'
  if (type === '词单') return 'info'
  return 'warning'
}

function fileIcon(type) {
  if (type === 'image') return 'Picture'
  if (type === 'docx') return 'Document'
  return 'Document'
}

function fileIconColor(type) {
  if (type === 'image') return '#10b981'
  if (type === 'docx') return '#2563eb'
  return '#f59e0b'
}

async function uploadSingleFile(file, idx, tag, semester) {
  ensureFileStream(idx, file.name)
  const form = new FormData()
  form.append('file', file)
  form.append('tag', tag)
  form.append('semester', semester)

  let fileResult = null
  let fileError = null

  const timeoutPromise = new Promise((_, reject) =>
    setTimeout(() => reject(new Error('上传超时（5分钟）')), 300000)
  )

  const uploadPromise = (async () => {
    const res = await fetch('/api/english-upload/classify', {
      method: 'POST', body: form, credentials: 'include',
    })

    if (!res.ok) {
      const detail = await res.text().catch(() => '上传失败')
      throw new Error(detail)
    }
    if (!res.body) {
      throw new Error('服务器响应体为空')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        // Flush remaining buffer (last message may not end with \n\n)
        if (buffer.trim()) {
          const lines = buffer.split(/\r?\n/)
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data: ')) continue
            const payload = trimmed.slice(6)
            if (payload === '[DONE]') return
            try { processPayload(payload) } catch { /* ignore */ }
          }
        }
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const lines = part.split(/\r?\n/)
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const payload = trimmed.slice(6)
          if (payload === '[DONE]') return
          try { processPayload(payload) } catch { /* ignore parse error */ }
        }
      }
    }

    function processPayload(payload) {
      const msg = JSON.parse(payload)
      if (msg.type === 'text') {
        fileStreams.value = { ...fileStreams.value, [idx]: (fileStreams.value[idx] || '') + msg.text }
        if (String(idx) === activeFileIndex.value) { scrollStream() }
      } else if (msg.type === 'ai_token') {
        fileStreams.value = { ...fileStreams.value, [idx]: (fileStreams.value[idx] || '') + msg.text }
        if (String(idx) === activeFileIndex.value) { scrollStream() }
      } else if (msg.type === 'usage') {
        let u = msg.text
        if (typeof u === 'string') try { u = JSON.parse(u) } catch {}
        if (u) {
          app.setCurrentSessionUsage({
            tokens_in: (u.hit || 0) + (u.miss || 0),
            tokens_out: u.out || 0,
            cost: u.cost || 0,
          })
        }
      } else if (msg.type === 'result') {
        fileResult = msg
        const displayCount = msg.doc_type === '词单' ? (msg.word_count || 0) + ' 词' : (msg.count || 0) + ' 条'
        results.value.push({
          type: msg.doc_type,
          confidence: msg.confidence,
          reason: msg.reason,
          tag: msg.tag,
          count: msg.doc_type === '词单' ? (msg.word_count || 0) : (msg.count || 0),
          summary: msg.summary || '',
          filename: file.name,
          source_file: file.name,
          file_id: msg.file_id || '',
        })
        if (msg.usage) {
          app.setCurrentSessionUsage({
            tokens_in: (msg.usage.input_cache_hit || 0) + (msg.usage.input_cache_miss || 0),
            tokens_out: msg.usage.output || 0,
            cost: msg.usage.cost_yuan || 0,
          })
        }
        app.loadTodayUsage()
      } else if (msg.type === 'error') {
        fileError = msg.text || '未知错误'
      }
    }
  })()

  try {
    await Promise.race([uploadPromise, timeoutPromise])
  } catch (e) {
    fileError = e.message || '未知错误'
  }
  if (fileResult) {
    fileStatuses.value = { ...fileStatuses.value, [idx]: 'done' }
  } else if (fileError) {
    fileStatuses.value = { ...fileStatuses.value, [idx]: 'error' }
  }
  return { fileResult, fileError }
}

async function doUpload() {
  if (!selectedFiles.value.length) return
  showDialog.value = false
  isUploading.value = true
  results.value = []
  failedFiles.value = []
  fileStreams.value = {}
  fileNames.value = {}
  fileStatuses.value = {}
  activeFileIndex.value = ''
  const files = [...selectedFiles.value]
  selectedFiles.value = []
  const currentTag = uploadTag.value
  const currentSemester = uploadSemester.value
  const totalFiles = files.length
  let successCount = 0
  let failCount = 0
  const MAX_CONCURRENT = 5
  let nextIdx = 0
  let activeCount = 0

  async function startOne(idx) {
    activeCount++
    let fileResult = null
    let fileError = null
    try {
      const file = files[idx]
      const res = await uploadSingleFile(file, idx, currentTag, currentSemester)
      fileResult = res.fileResult
      fileError = res.fileError
    } catch (e) {
      fileError = e.message || '上传异常'
    } finally {
      activeCount--
    }

    if (fileResult) {
      successCount++
    } else if (fileError) {
      failCount++
      failedFiles.value.push({ file: files[idx], tag: currentTag, semester: currentSemester, error: fileError })
    } else {
      failCount++
      failedFiles.value.push({ file: files[idx], tag: currentTag, semester: currentSemester, error: '未返回结果' })
    }

    // 完成一个立即启动下一个（滑窗模式）
    if (nextIdx < totalFiles) {
      startOne(nextIdx++)
    }
  }

  // 启动前 MAX_CONCURRENT 个
  for (let i = 0; i < Math.min(MAX_CONCURRENT, totalFiles); i++) {
    startOne(nextIdx++)
  }

  // 等待所有完成（带超时兜底）
  const startWait = Date.now()
  const MAX_WAIT_MS = Math.max(30_000, totalFiles * 60_000)
  await new Promise((resolve, reject) => {
    const check = setInterval(() => {
      if (nextIdx >= totalFiles && activeCount === 0) {
        clearInterval(check)
        resolve()
      }
      if (Date.now() - startWait > MAX_WAIT_MS) {
        clearInterval(check)
        reject(new Error('上传等待超时'))
      }
    }, 200)
  })

  isUploading.value = false

  if (successCount > 0) {
    ElMessage.success(`${successCount} 个文件上传完成${failCount > 0 ? `，${failCount} 个失败` : ''}`)
  } else if (failCount > 0) {
    ElMessage.error('所有文件上传失败，请检查网络或 API Key')
  }
  await loadTree()
}

async function retryFile(failed) {
  failedFiles.value = failedFiles.value.filter(f => f !== failed)
  isUploading.value = true

  const idx = Date.now()
  const { fileResult, fileError } = await uploadSingleFile(
    failed.file, idx, failed.tag, failed.semester
  )

  if (fileResult) {
    // file already added to results by uploadSingleFile
  } else if (fileError) {
    failedFiles.value.push({ ...failed, error: fileError })
  } else {
    failedFiles.value.push({ ...failed, error: '未返回结果' })
  }

  isUploading.value = false
  await loadTree()
}

async function loadTree() {
  try {
    const [matRes, probRes, ansRes, wordRes] = await Promise.all([
      axios.get('/materials'),
      axios.get('/problems?page_size=5000'),
      axios.get('/english-upload/answers'),
      axios.get('/english-upload/words'),
    ])
    rawAllProblems.value = (probRes.data.items || []).filter(p => p.subject === '英语')
    rawAllAnswers.value = ansRes.data.items || []

    const tree = {}
    // 收集已被归类（题目/答案/词单）的源文件名，过滤资料中的重复
    const classifiedFiles = new Set()
    for (const p of rawAllProblems.value) { if (p.source_file) classifiedFiles.add(p.source_file) }
    for (const a of rawAllAnswers.value) { if (a.source_file) classifiedFiles.add(a.source_file) }
    for (const w of (wordRes.data.items || [])) { if (w.filename) classifiedFiles.add(w.filename) }

    for (const m of (matRes.data.items || [])) {
      if (m.subject !== '英语' && m.subject) continue
      if (classifiedFiles.has(m.filename)) continue
      const tag = m.tag || m.time || '未分类'
      if (!tree[tag]) tree[tag] = { count: 0, items: [] }
      tree[tag].count++
      tree[tag].items.push({
        id: m.id, filename: m.filename, file_type: m.file_type || 'pdf',
        has_text: m.has_text, created_at: m.created_at,
        _type: '资料', _deleteType: 'material',
      })
    }
    // 题目按源文件分组加入
    const probSeen = new Set()
    for (const p of rawAllProblems.value) {
      const key = p.source_file || p.filename || p.id
      if (probSeen.has(key)) continue
      probSeen.add(key)
      const tag = p.exam || '未分类'
      if (!tree[tag]) tree[tag] = { count: 0, items: [] }
      tree[tag].count++
      tree[tag].items.push({
        id: key, filename: p.filename || key, file_type: 'docx',
        has_text: false, created_at: p.created_at,
        _type: '题目', _deleteType: 'problem', _sourceFile: key,
      })
    }
    // 答案按源文件分组加入
    const ansSeen = new Set()
    for (const a of rawAllAnswers.value) {
      const key = a.source_file || a.filename || a.id
      if (ansSeen.has(key)) continue
      ansSeen.add(key)
      const tag = a.tag || '未分类'
      if (!tree[tag]) tree[tag] = { count: 0, items: [] }
      tree[tag].count++
      tree[tag].items.push({
        id: key, filename: a.filename || key, file_type: 'docx',
        has_text: false, created_at: a.created_at,
        _type: '答案', _deleteType: 'answer', _sourceFile: key,
      })
    }
    // 词单
    const rawWords = wordRes.data.items || []
    for (const w of rawWords) {
      const tag = w.tag || '未分类'
      if (!tree[tag]) tree[tag] = { count: 0, items: [] }
      tree[tag].count++
      tree[tag].items.push({
        id: w.id, filename: w.filename || w.id, file_type: 'docx',
        has_text: false, created_at: w.created_at,
        _type: '词单', _deleteType: 'word',
      })
    }
    tagTree.value = tree
    activeTags.value = Object.keys(tree)
  } catch (e) {
    console.error('加载文件库失败', e)
  }
}

async function deleteMaterial(item) {
  const label = item._type || '资料'
  try {
    await ElMessageBox.confirm(`确定删除这条${label}？`, '提示', { type: 'warning' })
    if (item._type === '资料') {
      await axios.delete(`/materials/${item.id}`)
    } else if (item._type === '题目') {
      const ids = rawAllProblems.value.filter(p => (p.source_file || p.filename) === item._sourceFile).map(p => p.id)
      await axios.post('/problems/batch-delete', { ids })
    } else if (item._type === '答案') {
      const ids = rawAllAnswers.value.filter(a => (a.source_file || a.filename) === item._sourceFile).map(a => a.id)
      if (ids.length === 1) {
        await axios.delete(`/english-upload/answers/${ids[0]}`)
      } else if (ids.length > 1) {
        await axios.post('/english-upload/answers/batch-delete', { ids })
      }
    } else if (item._type === '词单') {
      await axios.delete(`/english-upload/words/${item.id}`)
    }
    ElMessage.success('已删除')
    await loadTree()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  app.setActiveTab('录入')
  loadTree()
})
</script>

<style scoped>
.english-upload-page {
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

.file-count {
  font-size: 12px;
  color: #94a3b8;
}
.pending-files {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
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
}

.stream-panel {
  background: #1e293b;
  border-radius: 16px;
  border: 1px solid #334155;
  padding: 24px;
  margin-bottom: 24px;
}
.stream-panel .panel-header {
  color: #f1f5f9;
  margin-bottom: 12px;
}
.stream-text {
  margin: 0;
  padding: 16px;
  background: #0f172a;
  border-radius: 10px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.file-tabs {
  margin-top: 8px;
}
.file-tabs :deep(.el-tabs__header) {
  margin: 0 0 8px;
  border-bottom: none;
}
.file-tabs :deep(.el-tabs__nav) {
  border: none;
}
.file-tabs :deep(.el-tabs__item) {
  color: #64748b;
  background: #0f172a;
  border: 1px solid #334155 !important;
  border-radius: 6px 6px 0 0 !important;
  font-size: 12px;
  padding: 4px 12px;
  height: 32px;
  line-height: 32px;
  margin-right: 4px;
}
.file-tabs :deep(.el-tabs__item.is-active) {
  color: #e2e8f0;
  background: #1e293b;
  border-bottom-color: #1e293b !important;
}
.file-tabs :deep(.el-tabs__content) {
  overflow: visible;
}

.animate-pulse {
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.results-panel {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 24px;
  margin-bottom: 24px;
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
.results-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.result-item {
  padding: 14px 16px;
  border-radius: 10px;
  background: #f8fafc;
  border-left: 4px solid #e2e8f0;
}
.result-item.题目 {
  border-left-color: #2563eb;
  background: #eff6ff;
}
.result-item.答案 {
  border-left-color: #059669;
  background: #f0fdf4;
}
.result-item.资料 {
  border-left-color: #f59e0b;
  background: #fffbeb;
}
.result-type {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.result-tag {
  font-size: 13px;
  color: #64748b;
}
.result-filename {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-reason {
  font-size: 13px;
  color: #475569;
  margin: 0 0 8px;
  line-height: 1.5;
}
.result-summary {
  font-size: 12px;
  color: #059669;
  margin: 0 0 6px;
  font-style: italic;
}
.result-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #94a3b8;
}

.tree-panel {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 24px;
}
.collapse-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 4px;
}
.tag-count {
  font-size: 12px;
  color: #94a3b8;
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

.failed-panel {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #fecaca;
  padding: 24px;
  margin-bottom: 24px;
}
.failed-panel .panel-header {
  color: #991b1b;
}
.failed-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.failed-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #fef2f2;
  border-radius: 10px;
}
.failed-name {
  flex: 1;
  font-size: 13px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conf-low { color: #dc2626; font-weight: 600; }
.failed-error {
  font-size: 11px;
  color: #dc2626;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .content {
    max-width: 100%;
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
    padding: 28px 16px;
  }
  .upload-icon-wrap {
    width: 52px;
    height: 52px;
    border-radius: 14px;
  }
  .upload-card h3 {
    font-size: 16px;
  }
  .upload-card p {
    font-size: 13px;
  }
  .stream-panel {
    padding: 16px;
  }
  .results-panel {
    padding: 16px;
  }
  .tree-panel {
    padding: 16px;
  }
  .panel-header {
    flex-wrap: wrap;
    gap: 8px;
    font-size: 15px;
  }
  .failed-panel {
    padding: 16px;
  }
  .file-item {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 10px;
  }
  .failed-item {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 10px;
  }
  .failed-name {
    max-width: 100%;
  }
  .failed-error {
    max-width: 100%;
  }
  .result-item {
    padding: 10px 12px;
  }
  .result-meta {
    flex-wrap: wrap;
    gap: 8px;
  }
  .result-filename {
    max-width: 100%;
  }
}

.resize-dialog .el-dialog {
  resize: both;
  overflow: hidden;
  min-width: 360px;
  min-height: 240px;
}
.resize-dialog .el-dialog__body {
  overflow: auto;
  max-height: 70vh;
}
</style>
