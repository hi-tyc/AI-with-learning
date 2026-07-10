<template>
  <div class="upload-page">
    <div class="content">
      <h1 class="page-title">录入题目</h1>
      <p class="page-subtitle">上传试卷或题目图片，AI 自动识别并入库</p>

      <!-- 模式选择 -->
      <div class="mode-selector" v-if="!aiResults.length && !isRecognizing">
        <el-radio-group v-model="uploadMode" size="large">
          <el-radio-button label="algebra">代数</el-radio-button>
          <el-radio-button label="geometry">几何</el-radio-button>
          <el-radio-button label="pdf">PDF</el-radio-button>
        </el-radio-group>
        <p class="mode-hint">
          {{ modeHint }}
        </p>
      </div>

      <div class="upload-card main-upload" @click="triggerUpload">
        <div class="upload-icon-wrap">
          <el-icon size="40" color="#2563eb"><Camera /></el-icon>
        </div>
        <h3>上传题目文档</h3>
        <p>支持 JPG、PNG 图片或 PDF 文件</p>
        <input
          ref="fileInputRef"
          type="file"
          style="display: none"
          :accept="uploadMode === 'pdf' ? '.pdf' : 'image/jpeg,image/png,.pdf'"
          @change="handleFileChange"
        />
      </div>

      <!-- AI 识别结果 -->
      <div v-if="aiResults.length" class="panel-card">
        <div class="panel-header">
          <el-icon><Document /></el-icon>
          <span>AI 识别结果 — 共 {{ aiResults.length }} 道题</span>
          <span class="panel-actions">
            <el-select v-model="selectedSessionId" placeholder="选择会话" size="small" style="width:140px;margin-right:8px">
              <el-option
                v-for="s in sessions"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
            <el-button type="primary" size="small" @click="saveAll" :icon="Plus">全部入库</el-button>
            <el-button size="small" @click="aiResults = []; uploadFile = null" :icon="Close">取消</el-button>
          </span>
        </div>
        <div v-for="(problem, idx) in aiResults" :key="idx" class="problem-item">
          <div class="problem-index">第 {{ idx + 1 }} 题</div>
          <el-row :gutter="12">
            <el-col :span="6">
              <el-form-item label="题型">
                <el-input v-model="problem.type" placeholder="如：选择题/填空题" size="small" />
              </el-form-item>
            </el-col>
            <el-col :span="18">
              <el-form-item label="知识点">
                <el-input v-model="problem.knowledge_point" placeholder="多个用逗号分隔" size="small" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="题目内容">
            <el-input v-model="problem.content" type="textarea" :rows="3" size="small" />
          </el-form-item>
          <el-form-item label="预览">
            <div class="latex-preview" v-html="renderMath(problem.content)"></div>
          </el-form-item>
          <el-form-item v-if="problem.answer" label="答案/解析">
            <el-input v-model="problem.answer" type="textarea" :rows="2" size="small" />
          </el-form-item>
          <el-form-item v-if="problem.answer" label="答案预览">
            <div class="latex-preview" v-html="renderMath(problem.answer)"></div>
          </el-form-item>
          <el-divider v-if="idx < aiResults.length - 1" />
        </div>
      </div>

      <!-- 识别中提示 -->
      <div v-if="isRecognizing" class="panel-card">
        <div class="panel-header">
          <el-icon class="spinning"><Loading /></el-icon>
          <span>AI 正在识别文档内容…</span>
          <el-button size="small" type="danger" text @click="stopRecognition" style="margin-left:auto">
            <el-icon><Close /></el-icon> 停止
          </el-button>
        </div>
        <el-progress :percentage="recognizeProgress" :stroke-width="14" />
        <p v-if="progressTotal > 0" class="progress-text">
          正在识别 第 {{ progressDone }}/{{ progressTotal }} 批…
        </p>
        <!-- 流式输出日志 -->
        <pre v-if="streamText" ref="streamRef" class="stream-log">{{ streamText }}</pre>
        <el-skeleton :rows="6" animated style="margin-top:16px" />
      </div>

      <!-- 本次会话用量 -->
      <div v-if="lastUsage" class="panel-card">
        <div class="panel-header">
          <el-icon><Coin /></el-icon>
          <span>本次会话用量</span>
        </div>
        <div class="usage-flex">
          <el-tag type="info">缓内输入 {{ lastUsage.input_cache_hit }}</el-tag>
          <el-tag type="info">缓外输入 {{ lastUsage.input_cache_miss }}</el-tag>
          <el-tag type="info">输出 {{ lastUsage.output }}</el-tag>
          <el-tag v-if="lastUsage.cost_yuan === null || lastUsage.cost_yuan === undefined" type="success">包月不计费</el-tag>
          <el-tag v-else type="success">花费 ¥{{ lastUsage.cost_yuan }}</el-tag>
        </div>
      </div>

      <!-- 历史录入会话 -->
      <div v-if="usageHistory.length" class="panel-card">
        <div class="panel-header">
          <el-icon><Coin /></el-icon>
          <span>历史录入用量</span>
        </div>
        <el-table :data="usageHistory" size="small" style="width: 100%">
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="文件" prop="filename" min-width="140" show-overflow-tooltip />
          <el-table-column label="缓内输入" prop="input_cache_hit" width="90" align="right" />
          <el-table-column label="缓外输入" prop="input_cache_miss" width="90" align="right" />
          <el-table-column label="输出" prop="output" width="80" align="right" />
          <el-table-column label="花费" width="90" align="right">
            <template #default="{ row }">
              <span v-if="row.cost_yuan === null || row.cost_yuan === undefined" class="free-text">包月</span>
              <span v-else>¥{{ row.cost_yuan }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Camera, Document, Loading, Plus, Close, Coin } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app.js'
import { useAuthStore } from '../stores/auth.js'
import { renderMath } from '../utils/mathRender'

const app = useAppStore()
const auth = useAuthStore()
const router = useRouter()

onMounted(() => {
  if (auth.subject === '英语') {
    router.replace('/english-upload')
    return
  }
  app.setActiveTab('录入')
  loadSessions()
  loadUsageHistory()
})

const fileInputRef = ref(null)
const uploadFile = ref(null)
const aiResults = ref([])
const isRecognizing = ref(false)
const recognizeProgress = ref(0)
let abortRecognize = null
const progressTotal = ref(0)
const progressDone = ref(0)
const lastUsage = ref(null)
const sessions = ref([])
const selectedSessionId = ref('')
const uploadMode = ref('algebra')
const modeHint = computed(() => {
  const hints = {
    algebra: '代数题图片：AI 自动识别文字后入库',
    geometry: '几何题图片：不识别文字，直接保存图片，解题时上传图片给 AI',
    pdf: 'PDF 文档：Kimi 自动拆分题目并识别入库',
  }
  return hints[uploadMode.value] || ''
})
const streamText = ref('')
const streamRef = ref(null)

function autoScrollStream() {
  nextTick(() => {
    if (streamRef.value) {
      streamRef.value.scrollTop = streamRef.value.scrollHeight
    }
  })
}

// 加载会话列表供选择
async function loadSessions() {
  try {
    const res = await axios.get('/sessions')
    sessions.value = res.data.items || []
    if (sessions.value.length > 0 && !selectedSessionId.value) {
      selectedSessionId.value = sessions.value[0].id
    }
  } catch (e) {
    console.error('加载会话失败', e)
  }
}

const usageHistory = ref([])

async function loadUsageHistory() {
  try {
    const res = await axios.get('/usage')
    usageHistory.value = res.data.sessions || []
  } catch (e) {
    console.error('加载历史用量失败', e)
  }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

function triggerUpload() {
  fileInputRef.value?.click()
}

async function handleFileChange(event) {
  const file = event.target.files[0]
  if (!file) return

  uploadFile.value = file
  event.target.value = ''

  const form = new FormData()
  form.append('file', file)
  form.append('mode', uploadMode.value)  // 上传模式：algebra / geometry

  isRecognizing.value = true
  aiResults.value = []
  lastUsage.value = null
  recognizeProgress.value = 0
  progressDone.value = 0
  progressTotal.value = 0
  streamText.value = '开始识别...\n'

  abortRecognize = new AbortController()
  try {
    const res = await fetch('/api/upload/recognize_stream', {
      method: 'POST',
      body: form,
      credentials: 'include',
      signal: abortRecognize.signal,
    })

    if (!res.ok) {
      let detail = 'AI 识别失败，请重试'
      try {
        const txt = await res.text()
        try { detail = JSON.parse(txt).detail || detail } catch { detail = txt || detail }
      } catch {}
      ElMessage.error(detail)
      streamText.value += `错误: ${detail}\n`
      autoScrollStream()
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let done = false
    while (!done) {
      const { value, done: streamDone } = await reader.read()
      if (streamDone) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop()
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        if (payload === '[DONE]') { done = true; continue }
        let msg
        try { msg = JSON.parse(payload) } catch { continue }
        if (msg.type === 'progress') {
          progressDone.value = msg.done
          progressTotal.value = msg.total
          recognizeProgress.value = msg.total ? Math.round(msg.done / msg.total * 100) : 0
          streamText.value += `[进度] 第 ${msg.done}/${msg.total} 批完成\n`
          autoScrollStream()
        } else if (msg.type === 'text') {
          streamText.value += msg.text
          autoScrollStream()
        } else if (msg.type === 'recog_text') {
          streamText.value += `[识别] ${msg.text}\n`
          autoScrollStream()
        } else if (msg.type === 'result') {
          aiResults.value = msg.problems || []
          lastUsage.value = msg.usage
          if (msg.warning) ElMessage.warning(msg.warning)
          recognizeProgress.value = 100
          streamText.value += `\n✅ 识别完成！共 ${aiResults.value.length} 道题\n`
          if (lastUsage.value) {
            streamText.value += `📊 用量: 输入 ${lastUsage.value.input_cache_miss || 0} / 输出 ${lastUsage.value.output || 0} / 费用 ¥${lastUsage.value.cost_yuan || 0}\n`
            app.setCurrentSessionUsage({
              tokens_in: (lastUsage.value.input_cache_hit || 0) + (lastUsage.value.input_cache_miss || 0),
              tokens_out: lastUsage.value.output || 0,
              cost: lastUsage.value.cost_yuan || 0,
            })
          }
          autoScrollStream()
          ElMessage.success(`识别完成，共 ${aiResults.value.length} 道题`)
          loadUsageHistory()
          app.loadTodayUsage()
        } else if (msg.type === 'error') {
          ElMessage.error(msg.detail || 'AI 识别失败')
          streamText.value += `❌ 错误: ${msg.detail || 'AI 识别失败'}\n`
          autoScrollStream()
        }
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      streamText.value += '\n⏹ 已停止识别\n'
    } else {
      ElMessage.error('AI 识别失败，请重试')
      streamText.value += `\n❌ 连接失败: ${e.message || '未知错误'}\n`
    }
  } finally {
    isRecognizing.value = false
    abortRecognize = null
    autoScrollStream()
  }
}

function stopRecognition() {
  if (abortRecognize) {
    abortRecognize.abort()
    abortRecognize = null
    isRecognizing.value = false
    streamText.value += '\n--- 用户已停止识别 ---\n'
  }
}

async function saveAll() {
  let successCount = 0
  for (const problem of aiResults.value) {
    if (!problem.content.trim()) continue
    try {
      // 大题处理：先创建大题，再创建子题
      if (problem.is_big_question && problem.sub_problems && problem.sub_problems.length > 0) {
        // 1. 创建大题（不含子题字段）
        const bigRes = await axios.post('/problems', {
          subject: auth.subject || '数学',
          exam: '', source: '', school: '',
          big_question: problem.big_question || '',
          small_question: '',
          content: problem.content,
          image_file_id: problem.image_file_id || '',
          knowledge_point: problem.knowledge_point || '',
          is_wrong: false,
          is_shared: false,
          session_id: selectedSessionId.value || undefined,
          is_big_question: true,
        })
        const bigId = bigRes.data.id
        successCount++

        // 2. 创建子题
        for (const sub of problem.sub_problems) {
          if (!sub.content || !sub.content.trim()) continue
          await axios.post('/problems', {
            subject: auth.subject || '数学',
            exam: '', source: '', school: '',
            big_question: problem.big_question || '',
            small_question: sub.small_question || '',
            content: sub.content,
            image_file_id: sub.image_file_id || problem.image_file_id || '',
            knowledge_point: sub.knowledge_point || problem.knowledge_point || '',
            is_wrong: false,
            is_shared: false,
            session_id: selectedSessionId.value || undefined,
            parent_id: bigId,
            is_big_question: false,
          })
          successCount++
        }
      } else {
        // 普通题直接创建，学科由登录学科决定，不再使用AI识别结果
        await axios.post('/problems', {
          ...problem,
          subject: auth.subject || '数学',
          exam: '', source: '', school: '',
          big_question: '', small_question: '', image_file_id: problem.image_file_id || '',
          is_shared: false,
          session_id: selectedSessionId.value || undefined,
          upload_mode: uploadMode.value,
        })
        successCount++
      }
    } catch (e) {
      console.error('入库失败', e)
    }
  }
  ElMessage.success(`${successCount} 道题已入库`)
  aiResults.value = []
  uploadFile.value = null
  // 刷新侧栏会话列表
  app.loadSessions()
}
</script>

<style scoped>
.upload-page {
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

.main-upload {
  background: #fff;
  border: 2px dashed #e2e8f0;
  border-radius: 16px;
  padding: 48px 24px;
  cursor: pointer;
  transition: all 0.25s ease;
  text-align: center;
  margin-bottom: 24px;
}
.mode-selector {
  text-align: center;
  margin-bottom: 20px;
}
.mode-hint {
  font-size: 13px;
  color: #64748b;
  margin: 12px 0 0;
}
.main-upload:hover {
  border-color: #2563eb;
  background: #f8fafc;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
}

.upload-icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: #eff6ff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}
.main-upload h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px;
}
.main-upload p {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.panel-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 24px;
  margin-bottom: 20px;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 20px;
}
.panel-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.problem-item {
  margin-bottom: 16px;
}
.problem-index {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
  padding: 6px 12px;
  background: #f8fafc;
  border-radius: 6px;
  display: inline-block;
}

.spinning {
  animation: spin 1s linear infinite;
}
.progress-text {
  font-size: 13px;
  color: #64748b;
  margin: 12px 0 0;
}
.usage-flex {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.free-text {
  color: #16a34a;
  font-weight: 600;
}

.latex-preview {
  width: 100%;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
}

.stream-log {
  margin: 12px 0 0;
  padding: 12px 16px;
  background: #1e293b;
  border-radius: 10px;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
  .main-upload {
    padding: 32px 16px;
  }
  .upload-icon-wrap {
    width: 56px;
    height: 56px;
    border-radius: 16px;
  }
  .main-upload h3 {
    font-size: 16px;
  }
  .main-upload p {
    font-size: 13px;
  }
  .panel-card {
    padding: 16px;
    margin-bottom: 14px;
  }
  .panel-header {
    flex-wrap: wrap;
    gap: 8px;
    font-size: 15px;
    margin-bottom: 14px;
  }
  .panel-actions {
    width: 100%;
    margin-left: 0;
    flex-wrap: wrap;
  }
  .problem-item {
    margin-bottom: 12px;
  }
:deep(.el-col-6),
  :deep(.el-col-18) {
    max-width: 100%;
    flex: 0 0 100%;
  }
}
</style>