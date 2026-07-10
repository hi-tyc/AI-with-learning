<template>
  <div class="english-solve-page">
    <div class="chat-layout">
      <div class="session-sidebar" v-if="showSessions">
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
        <div class="content">
          <div class="page-header">
            <div>
              <h1 class="page-title">英语解题</h1>
              <p class="page-subtitle">输入英语题目或粘贴文本，AI 将为你解答</p>
            </div>
            <div class="header-hint">
              <el-button size="small" text @click="showSessions = !showSessions" :type="showSessions ? 'primary' : 'default'">
                <el-icon><Clock /></el-icon>
              </el-button>
              <el-tag v-if="engine === 'deepseek'" type="success" size="small" effect="dark">DeepSeek 引擎</el-tag>
              <el-tag v-else type="warning" size="small" effect="dark">Kimi 引擎</el-tag>
            </div>
          </div>

          <div class="messages" ref="messagesRef">
            <div v-if="messages.length === 0 && !isTyping" class="empty-state">
              <div class="empty-icon">
                <el-icon size="48" color="#cbd5e1"><ChatLineRound /></el-icon>
              </div>
              <h3>开始英语学习</h3>
              <p>在下方输入英语题目或疑难句子，AI 将为你翻译、解析和解答</p>
            </div>

            <div v-for="(msg, idx) in messages" :key="idx" class="message" :class="msg.role">
              <div class="avatar">
                <el-icon v-if="msg.role === 'user'" size="18" color="#fff"><User /></el-icon>
                <el-icon v-else size="18" color="#fff"><Cpu /></el-icon>
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
                <div v-if="msg.role === 'assistant' && msg._problemId && !isTyping && idx === messages.length - 1" class="bubble-actions">
                  <el-button
                    size="small"
                    :type="wrongStatus[msg._problemId] ? 'success' : 'danger'"
                    text
                    :icon="wrongStatus[msg._problemId] ? CircleCheck : CircleClose"
                    @click="toggleWrongBook(msg._problemId)"
                  >
                    {{ wrongStatus[msg._problemId] ? '已加入' : '加入错题本' }}
                  </el-button>
                </div>
              </div>
            </div>

            <div v-if="isTyping" class="message assistant">
              <div class="avatar">
                <el-icon size="18" color="#fff"><Cpu /></el-icon>
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

            <div v-if="stoppedContent" class="message assistant">
              <div class="avatar"><el-icon size="18" color="#fff"><Cpu /></el-icon></div>
              <div class="bubble">
                <div class="bubble-content" v-html="renderMarkdown(stoppedContent)"></div>
                <div class="streaming-actions">
                  <el-button size="small" type="primary" text @click="continueAnswer">
                    <el-icon><Position /></el-icon> 继续解答
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="selectedMaterials.length" class="selected-materials">
            <span class="mat-label">参考资料：</span>
            <el-tag
              v-for="m in selectedMaterials" :key="m.id"
              closable
              size="small"
              type="success"
              @close="removeMaterial(m.id)"
            >
              {{ m.filename }}
            </el-tag>
          </div>

          <div class="input-area">
            <div class="input-wrap">
              <el-input
                v-model="inputText"
                type="textarea"
                :rows="inputRows"
                resize="none"
                placeholder="输入英语题目或粘贴文本…"
                @keydown.enter.prevent="sendMessage"
              />
              <div class="input-buttons">
                <el-button size="small" text @click="toggleInputRows">
                  <el-icon><component :is="inputRows > 3 ? Minus : Plus" /></el-icon>
                </el-button>
                <el-button type="primary" circle :disabled="!inputText.trim() || isTyping" @click="sendMessage">
                  <el-icon><Position /></el-icon>
                </el-button>
              </div>
            </div>
            <div class="input-hint">
              <div class="hint-left">
                <el-button size="small" text @click="showMaterialPicker = true" :icon="Collection">
                  资料
                </el-button>
                <el-divider direction="vertical" />
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
                <span class="hint-text">Enter 发送</span>
                <span class="hint-divider">|</span>
                <span class="hint-text">说「看XX文件」让AI查阅资料</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="showMaterialPicker" title="选择参考资料" width="520px">
      <div v-if="materialTags.length === 0" class="empty-materials">
        <p>暂无资料，请先上传英语资料</p>
        <el-button type="success" @click="$router.push('/english-upload')">上传资料</el-button>
      </div>
      <div v-else class="mat-tree">
        <div v-for="tag in materialTags" :key="tag" class="mat-group">
          <div class="mat-group-header" @click="toggleGroupExpand(tag)">
            <el-checkbox
              :model-value="isGroupSelected(tag)"
              :indeterminate="isGroupIndeterminate(tag)"
              @click.stop="toggleGroup(tag)"
            />
            <el-icon :size="14" class="expand-icon" :class="{ expanded: expandedTags.has(tag) }"><ArrowDown /></el-icon>
            <span class="mat-group-name">{{ tag }}</span>
            <span class="mat-group-count">{{ materialTree[tag].items.length }} 项</span>
          </div>
          <div v-if="expandedTags.has(tag)" class="mat-children">
            <div
              v-for="m in materialTree[tag].items"
              :key="m.id"
              class="mat-item"
              :class="{ selected: isMaterialSelected(m.id) }"
            >
              <el-checkbox
                :model-value="isMaterialSelected(m.id)"
                @click.stop="toggleMaterial(m)"
              />
              <el-icon size="16" color="#059669"><Document /></el-icon>
              <span class="mat-name">{{ m.filename }}</span>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showMaterialPicker = false">取消</el-button>
        <el-button type="primary" @click="showMaterialPicker = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ChatLineRound, User, Cpu, Close, ArrowDown, Position, Collection, Document, CircleClose, CircleCheck, Clock, Delete, Plus, Minus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '../../stores/app.js'
import { useAuthStore } from '../../stores/auth.js'
import { renderMath } from '../../utils/mathRender'

const app = useAppStore()
const auth = useAuthStore()
const router = useRouter()

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
const currentProblemId = ref('')
const wrongStatus = ref({})
const engine = ref('deepseek')
const showReasoning = ref(true)
const reasoningDepth = ref(5)
const solveSessions = ref([])
const activeSolveSession = ref(null)
const showSessions = ref(false)
let abortController = null
let lastQuestion = ''

// 资料选择
const inputRows = ref(2)
function toggleInputRows() {
  inputRows.value = inputRows.value > 3 ? 2 : 8
}
const showMaterialPicker = ref(false)
const materialTree = ref({})
const expandedTags = ref(new Set())
const selectedMaterials = ref([])

const materialTags = computed(() => {
  return Object.keys(materialTree.value).sort()
})

function renderMarkdown(text) {
  return renderMath(text)
}

function isMaterialSelected(id) {
  return selectedMaterials.value.some(m => m.id === id)
}

function toggleMaterial(m) {
  const idx = selectedMaterials.value.findIndex(x => x.id === m.id)
  if (idx >= 0) {
    selectedMaterials.value.splice(idx, 1)
  } else {
    selectedMaterials.value.push(m)
  }
}

function removeMaterial(id) {
  selectedMaterials.value = selectedMaterials.value.filter(m => m.id !== id)
}

function toggleGroup(tag) {
  const group = materialTree.value[tag]
  if (!group) return
  const allSelected = group.items.every(m => isMaterialSelected(m.id))
  if (allSelected) {
    selectedMaterials.value = selectedMaterials.value.filter(m => !group.items.some(gm => gm.id === m.id))
  } else {
    for (const m of group.items) {
      if (!isMaterialSelected(m.id)) {
        selectedMaterials.value.push(m)
      }
    }
  }
}

function isGroupSelected(tag) {
  const group = materialTree.value[tag]
  return group && group.items.length > 0 && group.items.every(m => isMaterialSelected(m.id))
}

function isGroupIndeterminate(tag) {
  const group = materialTree.value[tag]
  if (!group || group.items.length === 0) return false
  const some = group.items.some(m => isMaterialSelected(m.id))
  return some && !isGroupSelected(tag)
}

function toggleGroupExpand(tag) {
  const s = new Set(expandedTags.value)
  if (s.has(tag)) { s.delete(tag) } else { s.add(tag) }
  expandedTags.value = s
}

async function loadMaterials() {
  try {
    const [matRes, wordsRes] = await Promise.all([
      axios.get('/materials/tree'),
      axios.get('/english-upload/words'),
    ])
    const tree = matRes.data || {}
    // 将词单作为资料加入对应标签
    const wordItems = wordsRes.data.items || []
    for (const wl of wordItems) {
      const tag = wl.tag || '词单'
      if (!tree[tag]) {
        tree[tag] = { count: 0, items: [] }
      }
      tree[tag].items.push({
        id: wl.id,
        filename: wl.filename + (wl.is_student ? ' (学生版)' : ''),
        file_type: 'word',
        has_text: true,
        word_count: wl.word_count || 0,
        created_at: wl.created_at || '',
        _isWordList: true,
      })
      tree[tag].count++
    }
    materialTree.value = tree
  } catch (e) {
    console.error('加载资料失败', e)
  }
}

onMounted(async () => {
  app.setActiveTab('解题')
  await loadMaterials()
  loadSolveSessions()
  // 从资料库跳转过来时自动选中资料
  const matData = sessionStorage.getItem('solveMaterials')
  if (matData) {
    try {
      const { materialIds } = JSON.parse(matData)
      if (materialIds && materialIds.length) {
        const checkAndSelect = setInterval(() => {
          const tree = materialTree.value
          if (Object.keys(tree).length) {
            for (const id of materialIds) {
              for (const tag in tree) {
                const found = tree[tag].items.find(m => m.id === id)
                if (found && !isMaterialSelected(id)) { toggleMaterial(found); break }
              }
            }
            sessionStorage.removeItem('solveMaterials')
            clearInterval(checkAndSelect)
          }
        }, 100)
        setTimeout(() => clearInterval(checkAndSelect), 5000)
      }
    } catch {}
  }
  // 从详情页跳转过来时填充题目和答案到输入框
  const qs = sessionStorage.getItem('quickSolve')
  if (qs) {
    try {
      const data = JSON.parse(qs)
      currentProblemId.value = data.id || ''

      if (currentProblemId.value) {
        try {
          const res = await axios.get(`/english-wrong/check/${currentProblemId.value}`)
          wrongStatus.value = { [currentProblemId.value]: res.data.is_wrong }
        } catch {}
      }

      sessionStorage.removeItem('quickSolve')

      // 已有历史解答，直接展示
      if (data.existingSolution) {
        messages.value.push({ role: 'user', content: data.content || '' })
        messages.value.push({
          role: 'assistant',
          content: data.existingSolution,
          thinking: '',
          isReasoning: false,
          _showReasoning: true,
          _problemId: data.id || '',
        })
        return
      }

      // 将题目和标准答案填入输入框，不自动发送
      let inputContent = data.content || ''
      if (data.matchedAnswer) {
        inputContent = `【题目】\n${inputContent}\n\n【标准答案】\n${data.matchedAnswer}\n\n请解答以上题目，并解释为什么选该答案。`
      }
      inputText.value = inputContent
    } catch {}
  }
})

async function toggleWrongBook(problemId) {
  if (!problemId) {
    ElMessage.warning('未关联题目')
    return
  }
  try {
    const res = await axios.post(`/english-wrong/toggle-problem/${problemId}`)
    wrongStatus.value = { ...wrongStatus.value, [problemId]: res.data.is_wrong }
    ElMessage.success(res.data.message)
  } catch {
    ElMessage.error('操作失败')
  }
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
      await axios.post('/solve-sessions', {
        problem_id: null,
        problem_content: null,
        model: engine.value,
        engine: engine.value,
        question: lastQuestion || '',
        answer: partialAnswer,
        reasoning: partialReasoning || '',
        usage: realUsage.value || (liveProgress.value ? { prompt_tokens: liveProgress.value.input, completion_tokens: liveProgress.value.output } : undefined),
      })
      await loadSolveSessions()
      app.loadTodayUsage()
    } catch {}
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
  lastQuestion = '请继续解答'
  streamSolve('请继续解答')
  stoppedContent.value = ''
  stoppedReasoning.value = ''
}

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
    messages.value = []
    if (session.question) {
      messages.value.push({ role: 'user', content: session.question })
    }
    if (session.answer) {
      messages.value.push({ role: 'assistant', content: session.answer, thinking: session.reasoning || '', _showReasoning: false })
    }
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

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return

  messages.value.push({ role: 'user', content: text })
  lastQuestion = text
  inputText.value = ''
  isTyping.value = true

  const problemIdForAnswer = currentProblemId.value
  currentProblemId.value = ''

  await streamSolve(text, problemIdForAnswer)
}

async function streamSolve(text, problemIdForAnswer) {
  const materialsPath = selectedMaterials.value.map(m => m.id).join(',')

  try {
    abortController = new AbortController()
    isTyping.value = true
    streamingContent.value = ''
    streamingReasoning.value = ''
    liveProgress.value = null

    const res = await fetch('/api/problems/solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategy: 'auto',
        message: text,
        engine: engine.value,
        reasoning: showReasoning.value,
        reasoning_depth: reasoningDepth.value,
        materials_path: materialsPath || undefined,
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
          messages.value.push({ role: 'assistant', content: fullText, thinking: fullReasoning, _showReasoning: true, _problemId: problemIdForAnswer || '' })
          isTyping.value = false
          streamingContent.value = ''
          streamingReasoning.value = ''
          liveProgress.value = null
          realUsage.value = null
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

function scrollIfNearBottom() {
  const el = messagesRef.value
  if (!el) return
  const threshold = 80
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  if (nearBottom) scrollToBottom()
}

watch(messages, scrollToBottom, { deep: true })
watch(streamingContent, scrollIfNearBottom)
watch(streamingReasoning, () => { scrollIfNearBottom(); scrollReasoning() })
</script>

<style scoped>
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
.english-solve-page {
  height: 100vh;
  background: #f0fdf4;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.content {
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.page-header {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 32px 0 16px;
  gap: 16px;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #065f46;
  margin: 0 0 4px;
}
.page-subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}
.header-hint {
  flex-shrink: 0;
  padding-top: 4px;
}
.messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 0;
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
.message.user { align-self: flex-end; flex-direction: row-reverse; }
.message.assistant { align-self: flex-start; }
.avatar {
  width: 36px; height: 36px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.message.assistant .avatar { background: linear-gradient(135deg, #059669, #047857); }
.message.user .avatar { background: linear-gradient(135deg, #2563eb, #1d4ed8); }
.bubble :deep(p) { margin: 4px 0; }
.bubble :deep(ul), .bubble :deep(ol) { margin: 4px 0; padding-left: 20px; }
.bubble :deep(li) { margin: 1px 0; }
.bubble :deep(.katex-display) { margin: 4px 0; }
.bubble {
  padding: 14px 18px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.5;
  color: #334155;
  word-break: break-word;
  white-space: pre-wrap;
}
.message.user .bubble { background: #2563eb; color: #fff; border-bottom-right-radius: 4px; }
.message.assistant .bubble { background: #fff; border: 1px solid #e2e8f0; border-bottom-left-radius: 4px; }
.reasoning-block {
  margin-bottom: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  background: #f8fafc;
}
.reasoning-block.streaming { border-color: #6ee7b7; box-shadow: 0 0 0 1px #6ee7b7; }
.reasoning-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px; font-size: 12px; color: #64748b;
  cursor: pointer; user-select: none; background: #f1f5f9;
}
.reasoning-header:hover { background: #e2e8f0; }
.reasoning-header .rotated { transform: rotate(180deg); transition: transform 0.2s; }
.reasoning-actions { margin-left: auto; display: flex; align-items: center; gap: 6px; }
.reasoning-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #059669; animation: reasoningPulse 0.8s ease-in-out infinite;
}
@keyframes reasoningPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}
.reasoning-content {
  padding: 12px; font-size: 13px; color: #64748b;
  line-height: 1.4; border-top: 1px solid #e2e8f0;
  background: #fff; max-height: 300px; overflow-y: auto;
}
.reasoning-scroll { max-height: 300px; overflow-y: auto; }
.bubble-actions {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #e2e8f0;
}
.streaming-content { color: #065f46; }
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
.input-area {
  flex-shrink: 0;
  padding: 16px 0 24px;
  background: transparent;
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
  box-shadow: 0 0 0 1px #d1d5db inset;
  border: none;
  font-size: 14px;
}
.input-wrap :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 2px #05966933 inset;
}
.input-buttons {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}
.input-buttons :deep(.el-button) { width: 40px; height: 40px; }
.input-wrap :deep(.el-button) { flex-shrink: 0; }
.input-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding: 0 4px;
  font-size: 12px;
  color: #94a3b8;
}
.hint-left { display: flex; align-items: center; gap: 6px; }
.hint-right { display: flex; align-items: center; gap: 4px; }
.hint-divider { margin: 0 6px; color: #d1d5db; }
.engine-label, .toggle-label, .depth-label { font-size: 12px; color: #94a3b8; }
.selected-materials {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  flex-wrap: wrap;
}
.mat-label {
  font-size: 12px;
  color: #6b7280;
}
.mat-tree {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 420px;
  overflow-y: auto;
}
.mat-group {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
.mat-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f8fafc;
  cursor: pointer;
  user-select: none;
  transition: background 0.1s;
}
.mat-group-header:hover { background: #f1f5f9; }
.expand-icon { transition: transform 0.2s; }
.expand-icon.expanded { transform: rotate(0deg); }
.expand-icon:not(.expanded) { transform: rotate(-90deg); }
.mat-group-name { flex: 1; font-size: 13px; font-weight: 600; color: #1e293b; }
.mat-group-count { font-size: 11px; color: #94a3b8; }
.mat-children {
  border-top: 1px solid #e2e8f0;
  padding: 4px 0;
}
.mat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 8px 28px;
  cursor: pointer;
  transition: background 0.1s;
}
.mat-item:hover { background: #f0fdf4; }
.mat-item.selected { background: #ecfdf5; }
.mat-name { flex: 1; font-size: 13px; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-materials {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
  color: #6b7280;
}
.empty-materials p { margin: 0; }

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .english-solve-page {
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
  .content {
    max-width: 100%;
    padding: 0 12px;
  }
  .page-header {
    padding: 16px 0 10px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .page-title {
    font-size: 22px;
  }
  .page-subtitle {
    font-size: 13px;
  }
  .messages {
    padding: 10px 0;
    gap: 10px;
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
    padding: 10px 0 16px;
  }
  .input-hint {
    flex-wrap: wrap;
    gap: 6px;
  }
  .hint-left {
    flex-wrap: wrap;
    gap: 6px;
  }
  .hint-right {
    flex-wrap: wrap;
    gap: 4px;
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
  .selected-materials {
    padding: 6px 0;
  }
  .mat-tree {
    max-height: 320px;
  }
}
</style>
