<template>
  <div class="chat-page">
    <div class="chat-layout">
      <!-- 解题会话侧栏 -->
      <div class="session-sidebar" v-show="showSessions" :class="{ 'show-mobile': showSessions && isMobile }">
        <div class="sidebar-header">
          <span class="sidebar-title">解题记录</span>
          <el-button size="small" text @click="showSessions = false"><el-icon><Close /></el-icon></el-button>
        </div>
        <div class="session-list">
          <div v-for="s in solveSessions" :key="s.id" class="session-item" :class="{ active: s.id === activeSolveSession }" @click="loadSolveSession(s)">
            <div class="session-title">{{ s.title }}</div>
            <div class="session-meta">
              <span>{{ s.message_count || '?' }}条</span>
              <span>in {{ (s.input_cache_hit || 0) + (s.input_cache_miss || 0) }}</span>
              <span>out {{ s.output || 0 }}</span>
              <el-button text size="small" type="danger" @click.stop="deleteSolveSession(s.id)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          <div v-if="!solveSessions.length" class="empty-hint">暂无解题记录</div>
        </div>
      </div>
      <div class="chat-content">
      <!-- 选择栏：选择目录 / 选择题目 / 自由输入 -->
      <div class="select-bar">
        <div class="select-bar-inner">
          <el-button size="small" text @click="showSessions = !showSessions" :type="showSessions ? 'primary' : 'default'">
            <el-icon><Clock /></el-icon>
          </el-button>
          <el-radio-group v-model="solveMode" size="small">
            <el-radio-button label="自由输入" />
            <el-radio-button label="选择目录" />
            <el-radio-button label="选择题目" />
          </el-radio-group>

          <!-- 选择目录模式 -->
          <div v-if="solveMode === '选择目录'" class="select-area">
            <el-select
              v-model="selectedPath"
              placeholder="选择目录..."
              clearable
              style="width: 220px"
              size="small"
              @change="onPathChange"
            >
              <el-option
                v-for="opt in pathOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <el-select
              v-if="pathProblems.length"
              v-model="selectedProblemId"
              placeholder="选择该目录下的题目..."
              clearable
              style="width: 320px"
              size="small"
              @change="onSelectProblem"
            >
              <el-option
                v-for="p in pathProblems"
                :key="p.id"
                :label="p.content.slice(0, 40) + (p.content.length > 40 ? '...' : '')"
                :value="p.id"
              />
            </el-select>
          </div>

          <!-- 选择题目模式 -->
          <div v-if="solveMode === '选择题目'" class="select-area">
            <el-input
              v-model="searchKeyword"
              placeholder="输入关键词搜索题目..."
              size="small"
              clearable
              style="width: 200px"
              @keyup.enter="searchProblems"
            />
            <el-button size="small" @click="searchProblems" :icon="Search">搜索</el-button>
            <el-select
              v-if="searchResults.length"
              v-model="selectedProblemId"
              placeholder="选择题目..."
              clearable
              style="width: 320px"
              size="small"
              @change="onSelectProblem"
            >
              <el-option
                v-for="p in searchResults"
                :key="p.id"
                :label="p.content.slice(0, 40) + (p.content.length > 40 ? '...' : '')"
                :value="p.id"
              />
            </el-select>
          </div>

          <!-- 已选题目信息 -->
          <div v-if="currentProblem" class="current-problem-chip">
            <el-tag size="small" :type="subjectType(currentProblem.subject)">{{ currentProblem.subject }}</el-tag>
            <span class="chip-text">{{ currentProblem.content.slice(0, 50) + (currentProblem.content.length > 50 ? '...' : '') }}</span>
            <el-button text size="small" @click="clearProblem" :icon="Close">清除</el-button>
          </div>
        </div>
      </div>

      <!-- 顶部：题目信息（如果选中了题目） -->
      <div v-if="currentProblem" class="problem-bar">
        <el-tag :type="subjectType(currentProblem.subject)" size="small">{{ currentProblem.subject }}</el-tag>
        <el-tag v-if="currentProblem.has_figure" size="small" type="warning">几何题</el-tag>
        <span class="problem-text">{{ currentProblem.content }}</span>
        <el-image
          v-if="currentProblem.image_file_id"
          :src="`/data/uploads/${currentProblem.image_file_id}_compressed.jpg`"
          fit="contain"
          style="max-width:120px;max-height:80px;cursor:pointer;flex-shrink:0"
          :preview-src-list="[`/data/uploads/${currentProblem.image_file_id}_compressed.jpg`]"
          preview-teleported
        />
      </div>

      <!-- 对话列表 -->
      <div class="messages" ref="messagesRef">
        <!-- 空状态：提示选择题目 -->
        <div v-if="!currentProblem && messages.length === 0" class="empty-state">
          <div class="empty-icon">
            <el-icon size="48" color="#cbd5e1"><ChatLineRound /></el-icon>
          </div>
          <h3>开始解题</h3>
          <p v-if="solveMode === '自由输入'">直接在下方输入框发送题目内容，AI 将直接解答</p>
          <p v-else-if="solveMode === '选择目录'">从上方选择目录和题目，或点击下方输入框发送消息</p>
          <p v-else-if="solveMode === '选择题目'">从上方搜索并选择题目，或点击下方输入框发送消息</p>
          <p v-else>从左侧选择一道题目，或点击下方输入框发送消息</p>
        </div>

        <!-- 消息气泡 -->
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="message"
          :class="msg.role"
        >
          <div class="avatar">
            <el-icon v-if="msg.role === 'user'" size="20" color="#fff"><User /></el-icon>
            <el-icon v-else size="20" color="#fff"><Cpu /></el-icon>
          </div>
          <div class="bubble">
            <div v-if="msg.role === 'assistant' && msg.thinking" class="reasoning-block" :class="{ streaming: msg.isReasoning }">
              <div class="reasoning-header" @click="msg._showReasoning = !msg._showReasoning">
                <el-icon :size="14"><Cpu /></el-icon>
                <span>{{ msg.isReasoning ? 'AI 正在思考...' : 'AI 思考过程' }}</span>
                <div class="reasoning-actions">
                  <span v-if="msg.isReasoning" class="reasoning-dot"></span>
                  <el-icon :size="12" :class="{ rotated: msg._showReasoning }"><ArrowDown /></el-icon>
                </div>
              </div>
              <div v-if="msg._showReasoning || msg.isReasoning" class="reasoning-content" v-html="renderMarkdown(msg.thinking)"></div>
            </div>
            <div v-if="msg.content" class="bubble-content" v-html="renderMarkdown(msg.content)"></div>
          </div>
        </div>

        <!-- 流式输出区域 -->
        <div v-if="isTyping" class="message assistant">
          <div class="avatar">
            <el-icon size="20" color="#fff"><Cpu /></el-icon>
          </div>
          <div class="bubble">
            <div v-if="streamingReasoning && showReasoning" class="reasoning-block streaming">
              <div class="reasoning-header">
                <el-icon :size="12"><Cpu /></el-icon>
                <span>AI 正在思考... {{ streamingReasoning.length }}字</span>
                <span class="reasoning-dot"></span>
              </div>
              <div class="reasoning-content reasoning-scroll" ref="reasoningRef">{{ streamingReasoning }}</div>
            </div>
            <div class="bubble-content streaming-content" v-html="renderMarkdown(streamingContent)"></div>
            <div class="streaming-actions">
              <span v-if="liveProgress" class="live-tokens">
                in {{ liveProgress.input }} / out {{ liveProgress.output }} · ¥{{ liveProgress.cost.toFixed(6) }}
              </span>
              <el-button size="small" type="danger" text @click="cancelStream">
                <el-icon><Close /></el-icon> 停止回答
              </el-button>
            </div>
          </div>
        </div>

        <!-- 中断后继续按钮 -->
        <div v-if="stoppedContent" class="message assistant">
          <div class="avatar"><el-icon size="18" color="#fff"><Cpu /></el-icon></div>
          <div class="bubble">
            <div class="msg-content" v-html="renderMarkdown(stoppedContent)"></div>
            <div class="streaming-actions">
              <el-button size="small" type="primary" text @click="continueAnswer">
                <el-icon><Position /></el-icon> 继续解答
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部输入框 -->
      <div class="input-area">
        <div class="input-wrap">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="1"
            resize="none"
            :placeholder="inputPlaceholder"
            @keydown.enter.prevent="sendMessage"
          />
          <el-button
            type="primary"
            circle
            :disabled="!inputText.trim() || isTyping"
            @click="sendMessage"
          >
            <el-icon><Position /></el-icon>
          </el-button>
        </div>
        <div class="input-hint">
          <div class="hint-left">
            <span class="engine-label">模型</span>
            <el-select v-model="engine" size="small" style="width: 110px">
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="Kimi" value="kimi" />
            </el-select>
            <el-divider direction="vertical" />
            <span class="toggle-label">思考</span>
            <el-switch v-model="showReasoning" size="small" />
            <span v-if="showReasoning" class="depth-label">深度</span>
            <el-slider v-if="showReasoning" v-model="reasoningDepth" :min="1" :max="10" :step="1" size="small" style="width:80px" show-input />
          </div>
          <div class="hint-right">
            <el-tag v-if="currentProblem" size="small" effect="plain">{{ currentProblem.strategy === 'geometry' ? '📐 几何模式' : '🤖 自动模式' }}</el-tag>
            <span v-if="currentProblem" class="hint-text">Enter 发送</span>
            <span v-else class="hint-text">{{ solveMode === '自由输入' ? '直接输入题目，Enter 发送' : 'Enter 发送' }}</span>
            <el-button v-if="isTyping" size="small" type="danger" text @click="cancelStream">
              <el-icon><Close /></el-icon> 停止
            </el-button>
          </div>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineRound, User, Cpu, Loading, Position, Close, Search, ArrowDown, Clock } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app.js'
import { useAuthStore } from '../stores/auth.js'
import { renderMath } from '../utils/mathRender'

const app = useAppStore()
const auth = useAuthStore()

const isMobile = ref(false)
function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

const solveMode = ref('自由输入')
const messages = ref([])
const inputText = ref('')
const isTyping = ref(false)
const streamingContent = ref('')
const streamingReasoning = ref('')
const liveProgress = ref(null)
const realUsage = ref(null)
const stoppedContent = ref('')
const messagesRef = ref(null)
const reasoningRef = ref(null)
const currentProblem = ref(null)
const showSessions = ref(false)
const solveSessions = ref([])
const activeSolveSession = ref(null)
const problems = ref([])
const engine = ref('auto')
const showReasoning = ref(true)
const reasoningDepth = ref(5)
let engineManuallySet = false
let suppressEngineWatch = false
let abortController = null
let lastQuestion = ''

watch(engine, () => {
  if (suppressEngineWatch) {
    suppressEngineWatch = false
    return
  }
  engineManuallySet = true
})

// 选择目录相关
const selectedPath = ref('')
const pathOptions = ref([])
const pathProblems = ref([])

// 选择题目相关
const searchKeyword = ref('')
const searchResults = ref([])
const selectedProblemId = ref('')

const isEnglish = computed(() => auth.subject === '英语')

const inputPlaceholder = computed(() => {
  if (solveMode.value === '自由输入') {
    return '直接输入题目内容，AI 将为您解答...'
  }
  if (currentProblem.value) {
    return '输入追问或补充说明...'
  }
  return '输入题目或追问...'
})

function subjectType(subject) {
  const map = { '数学': 'primary', '物理': 'success', '化学': 'warning', '语文': '', '英语': 'info' }
  return map[subject] || ''
}

function renderMarkdown(text) {
  return renderMath(text)
}

// 加载题目列表
async function loadProblems() {
  try {
    const res = await axios.get('/problems?page_size=100')
    problems.value = res.data.items.map(p => ({ ...p, strategy: 'auto' }))
    buildPathOptions()
  } catch (e) {
    console.error('加载题目失败', e)
  }
}

// 构建目录选项
function buildPathOptions() {
  const paths = new Set()
  for (const p of problems.value) {
    const parts = []
    if (p.subject) parts.push(p.subject)
    if (p.exam) parts.push(p.exam)
    if (p.source) parts.push(p.source)
    if (parts.length) {
      paths.add(parts.join('/'))
    }
  }
  pathOptions.value = Array.from(paths).map(path => ({ value: path, label: path }))
}

// 选择目录变化
async function onPathChange() {
  if (!selectedPath.value) {
    pathProblems.value = []
    return
  }
  try {
    const res = await axios.get(`/problems?path=${encodeURIComponent(selectedPath.value)}&page_size=100`)
    pathProblems.value = res.data.items
  } catch (e) {
    console.error('加载目录题目失败', e)
  }
}

// 搜索题目
async function searchProblems() {
  if (!searchKeyword.value.trim()) {
    searchResults.value = []
    return
  }
  try {
    const res = await axios.get(`/problems?keyword=${encodeURIComponent(searchKeyword.value)}&page_size=20`)
    searchResults.value = res.data.items
  } catch (e) {
    console.error('搜索题目失败', e)
  }
}

// 选择题目
function onSelectProblem(problemId) {
  if (!problemId) {
    currentProblem.value = null
    return
  }
  const found = problems.value.find(p => p.id === problemId)
  if (found) {
    selectProblem(found)
  }
}

function selectProblem(problem) {
  currentProblem.value = problem
  messages.value = []
  inputText.value = problem.content
  if (!engineManuallySet) {
    suppressEngineWatch = true
    engine.value = problem.has_figure ? 'kimi' : 'auto'
  }
  app.setActiveProblem(problem)
  app.setActiveTab('解题')
  app.currentSolveSession = null
}

async function cancelStream() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  if (streamingContent.value) {
    const partialAnswer = streamingContent.value
    const partialReasoning = streamingReasoning.value
    stoppedContent.value = partialAnswer
    stoppedReasoning.value = partialReasoning
    messages.value.push({ role: 'assistant', content: partialAnswer, thinking: partialReasoning, _showReasoning: true })
    try {
      const actualEngine = engine.value === 'auto' ? (currentProblem.value?.has_figure ? 'kimi' : 'deepseek') : engine.value
      await axios.post('/solve-sessions', {
        problem_id: currentProblem.value?.id || null,
        problem_content: currentProblem.value?.content || null,
        model: actualEngine,
        engine: actualEngine,
        question: lastQuestion || currentProblem.value?.content || '',
        answer: partialAnswer,
        reasoning: partialReasoning || '',
        has_figure: currentProblem.value?.has_figure || false,
        image_file_id: currentProblem.value?.image_file_id || '',
        usage: realUsage.value || (liveProgress.value ? { prompt_tokens: liveProgress.value.input, completion_tokens: liveProgress.value.output } : undefined),
      })
      app.currentSolveSession = null
      await loadSolveSessions()
      app.loadTodayUsage()
    } catch (e) {
      console.error('保存部分解题会话失败', e)
    }
  }
  streamingContent.value = ''
  streamingReasoning.value = ''
  liveProgress.value = null
  realUsage.value = null
  isTyping.value = false
}

const stoppedReasoning = ref('')
function continueAnswer() {
  if (!stoppedContent.value) return
  messages.value.push({ role: 'user', content: '请继续解答' })
  streamSolve('请继续解答', currentProblem.value?.id || null)
  stoppedContent.value = ''
  stoppedReasoning.value = ''
}

function clearProblem() {
  currentProblem.value = null
  selectedProblemId.value = ''
  selectedPath.value = ''
  pathProblems.value = []
  searchResults.value = []
  messages.value = []
  app.currentSolveSession = null
}

// 发送消息
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return

  messages.value.push({ role: 'user', content: text })
  lastQuestion = text
  inputText.value = ''
  isTyping.value = true

  await streamSolve(text, currentProblem.value?.id || null)
}

// 流式解题
async function streamSolve(text, problemId) {
  try {
    const url = problemId
      ? `/api/problems/${problemId}/solve`
      : '/api/problems/solve'

    isTyping.value = true
    streamingContent.value = ''
    streamingReasoning.value = ''
    liveProgress.value = null

    abortController = new AbortController()
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategy: currentProblem.value?.strategy || 'auto',
        message: text,
        engine: engine.value,
        reasoning: showReasoning.value,
        reasoning_depth: reasoningDepth.value,
      }),
      credentials: 'include',
      signal: abortController.signal,
    })

    if (!res.ok) {
      let detail = `请求失败 (${res.status})`
      try { const t = await res.text(); try { detail = JSON.parse(t).detail || detail } catch { detail = t || detail } } catch {}
      messages.value.push({ role: 'assistant', content: detail })
      isTyping.value = false
      streamingContent.value = ''
      streamingReasoning.value = ''
      return
    }

    if (!res.body) {
      messages.value.push({ role: 'assistant', content: '服务器无响应，请稍后重试' })
      isTyping.value = false
      streamingContent.value = ''
      streamingReasoning.value = ''
      return
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullText = ''
    let fullReasoning = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        if (payload === '[DONE]') {
          messages.value.push({ role: 'assistant', content: fullText, thinking: fullReasoning, _showReasoning: true })
          isTyping.value = false
          streamingContent.value = ''
          streamingReasoning.value = ''
          liveProgress.value = null
          realUsage.value = null
          app.currentSolveSession = null
          loadSolveSessions()
          app.loadTodayUsage()
          return
        }
        try {
          const msg = JSON.parse(payload)
          if (msg.type === 'content') {
            fullText += msg.text
            streamingContent.value = fullText
          } else if (msg.type === 'reasoning') {
            fullReasoning += msg.text
            streamingReasoning.value = fullReasoning
          } else if (msg.type === 'progress') {
            liveProgress.value = { input: msg.input_tokens, output: msg.output_tokens, cost: msg.cost }
            app.setCurrentSessionUsage({ tokens_in: msg.input_tokens || 0, tokens_out: msg.output_tokens || 0, cost: msg.cost || 0 })
          } else if (msg.type === 'usage') {
            let u = msg.text
            if (typeof u === 'string') try { u = JSON.parse(u) } catch {}
            realUsage.value = u
            app.setCurrentSessionUsage({ tokens_in: (u.miss || 0) + (u.hit || 0), tokens_out: u.out || 0, cost: u.cost ?? app.currentSessionUsage.cost })
          } else if (msg.type === 'error') {
            messages.value.push({ role: 'assistant', content: msg.text })
            isTyping.value = false
            streamingContent.value = ''
            streamingReasoning.value = ''
          }
        } catch {
          fullText += payload
          streamingContent.value = fullText
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      ElMessage.error('解题连接失败')
    }
    isTyping.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function scrollReasoning() {
  nextTick(() => {
    const el = reasoningRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(messages, scrollToBottom, { deep: true })
watch(streamingContent, scrollToBottom)
watch(streamingReasoning, () => { scrollToBottom(); scrollReasoning() })

async function loadSolveSessions() {
  try {
    const res = await axios.get('/solve-sessions?page_size=50')
    solveSessions.value = res.data.items || []
  } catch {}
}

async function loadSolveSession(s) {
  if (isTyping.value) return
  activeSolveSession.value = s.id
  try {
    const res = await axios.get(`/solve-sessions/${s.id}`)
    const session = res.data
    currentProblem.value = {
      id: session.problem_id,
      content: session.problem_content || session.question,
      has_figure: session.has_figure || false,
      image_file_id: session.image_file_id || '',
      subject: auth.subject || '数学',
    }
    messages.value = []
    if (session.question) {
      messages.value.push({ role: 'user', content: session.question })
    }
    if (session.answer) {
      const msg = { role: 'assistant', content: session.answer, thinking: session.reasoning || '', reasoning: session.reasoning || '', _showReasoning: false }
      messages.value.push(msg)
    }
    app.currentSolveSession = session
  } catch {
    ElMessage.error('加载解题记录失败')
  }
}

async function deleteSolveSession(id) {
  try {
    await ElMessageBox.confirm('删除此解题记录？', '提示', { type: 'warning' })
    await axios.delete(`/solve-sessions/${id}`)
    if (activeSolveSession.value === id) { activeSolveSession.value = null; messages.value = [] }
    await loadSolveSessions()
  } catch {}
}

onMounted(() => {
  const quickData = sessionStorage.getItem('quickSolve')
  if (quickData) {
    try {
      const q = JSON.parse(quickData)
      currentProblem.value = q
      inputText.value = q.content || ''
      messages.value = []
      if (q.existingSolution) {
        messages.value.push({ role: 'user', content: q.content || '' })
        messages.value.push({ role: 'assistant', content: q.existingSolution || '', thinking: '', isReasoning: false, _showReasoning: false })
        inputText.value = ''
      }
    } catch (e) { /* ignore */ }
    sessionStorage.removeItem('quickSolve')
  }
  loadProblems()
  loadSolveSessions()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8fafc;
}
.chat-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.session-sidebar {
  width: 220px;
  min-width: 220px;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
}
.sidebar-title {
  font-weight: 600;
  font-size: 13px;
  color: #1e3a5f;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}
.session-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
  font-size: 12px;
}
.session-item:hover { background: #f1f5f9; }
.session-item.active { background: #eff6ff; }
.session-title {
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}
.session-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: #94a3b8;
}
.empty-hint {
  text-align: center;
  padding: 16px;
  font-size: 12px;
  color: #94a3b8;
}
.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* 选择栏 */
.select-bar {
  flex-shrink: 0;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}
.select-bar-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.select-area {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.current-problem-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: #f1f5f9;
  border-radius: 20px;
  font-size: 13px;
  color: #475569;
}
.chip-text {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 题目信息栏 */
.problem-bar {
  flex-shrink: 0;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #475569;
}
.problem-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

/* 消息列表 */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #94a3b8;
  gap: 12px;
}
.empty-state h3 {
  font-size: 18px;
  font-weight: 600;
  color: #475569;
  margin: 0;
}
.empty-state p {
  font-size: 14px;
  margin: 0;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
}
.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.message.assistant {
  align-self: flex-start;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.message.user .avatar {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.bubble {
  padding: 14px 18px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
  word-break: break-word;
}
.message.user .bubble {
  background: #2563eb;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.message.assistant .bubble {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
}

.reasoning-block {
  margin-bottom: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  background: #f8fafc;
}
.reasoning-block.streaming {
  border-color: #93c5fd;
  box-shadow: 0 0 0 1px #93c5fd;
}
.reasoning-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  user-select: none;
  background: #f1f5f9;
}
.reasoning-header:hover {
  background: #e2e8f0;
}
.reasoning-header .rotated {
  transform: rotate(180deg);
  transition: transform 0.2s;
}
.reasoning-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}
.reasoning-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  animation: reasoningPulse 0.8s ease-in-out infinite;
}
@keyframes reasoningPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}
.reasoning-content {
  padding: 12px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
  border-top: 1px solid #e2e8f0;
  background: #fff;
  max-height: 300px;
  overflow-y: auto;
}
.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}
.thinking-icon {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.streaming-content {
  color: #1e40af;
}
.streaming-actions {
  margin-top: 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
}
.live-tokens {
  font-size: 11px;
  color: #94a3b8;
  font-family: 'Courier New', monospace;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}
.reasoning-scroll {
  max-height: 300px;
  overflow-y: auto;
}

/* 打字动画 */
.bubble.typing {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 16px 18px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
  animation: bounce 1.4s ease-in-out infinite both;
}
.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); }
  40% { transform: scale(1); }
}

/* 输入区 */
.input-area {
  flex-shrink: 0;
  padding: 16px 24px 24px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
}
.input-wrap {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
.input-wrap :deep(.el-textarea__inner) {
  border-radius: 16px;
  padding: 12px 16px;
  resize: none;
  max-height: 200px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  border: none;
  font-size: 14px;
}
.input-wrap :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 2px #2563eb33 inset;
}
.input-wrap :deep(.el-button) {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.input-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding: 0 4px;
}

.hint-text {
  font-size: 12px;
  color: #94a3b8;
}
.hint-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hint-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.engine-label, .toggle-label, .depth-label {
  font-size: 12px;
  color: #94a3b8;
}
:deep(.katex-error) {
  color: #cc0000;
}

:deep(.math-inline) {
  color: #2563eb;
  font-family: 'Courier New', monospace;
}
:deep(.math-block) {
  color: #2563eb;
  font-family: 'Courier New', monospace;
  display: block;
  margin: 8px 0;
  padding: 8px 12px;
  background: #eff6ff;
  border-radius: 6px;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .chat-page {
    height: calc(100vh - 48px);
  }
  .session-sidebar {
    position: fixed;
    left: 0;
    top: 48px;
    height: calc(100vh - 48px);
    z-index: 140;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    width: 240px;
    min-width: 240px;
  }
  .session-sidebar.show-mobile {
    transform: translateX(0);
  }
  .select-bar {
    padding: 8px 12px;
  }
  .select-bar-inner {
    gap: 8px;
  }
  .select-bar-inner :deep(.el-radio-group) {
    display: flex;
    flex-wrap: wrap;
    width: 100%;
  }
  .select-bar-inner :deep(.el-radio-button__inner) {
    padding: 5px 10px;
    font-size: 12px;
  }
  .select-area {
    width: 100%;
    flex-wrap: wrap;
  }
  .select-area :deep(.el-select) {
    width: 100% !important;
    max-width: 100%;
  }
  .select-area :deep(.el-input) {
    width: 100% !important;
    max-width: 100%;
  }
  .select-area .el-input {
    width: 100% !important;
    max-width: 100%;
  }
  .current-problem-chip {
    max-width: 100%;
    flex-wrap: wrap;
  }
  .chip-text {
    max-width: 200px;
  }
  .problem-bar {
    padding: 8px 12px;
    gap: 8px;
    font-size: 13px;
    flex-wrap: wrap;
  }
  .messages {
    padding: 12px;
    gap: 12px;
  }
  .message {
    max-width: 92%;
  }
  .avatar {
    width: 28px;
    height: 28px;
  }
  .bubble {
    padding: 10px 12px;
    font-size: 13px;
  }
  .input-area {
    padding: 10px 12px 14px;
  }
  .input-hint {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .hint-left {
    flex-wrap: wrap;
    gap: 6px;
    width: 100%;
  }
  .hint-right {
    flex-wrap: wrap;
    gap: 6px;
    width: 100%;
  }
  .empty-state h3 {
    font-size: 16px;
  }
  .empty-state p {
    font-size: 13px;
  }
  .reasoning-content {
    max-height: 200px;
  }
}
</style>
