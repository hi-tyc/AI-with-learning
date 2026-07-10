<template>
  <div class="chat-page">
    <div class="chat-layout">
      <div class="chat-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">对话历史</span>
          <el-button size="small" text @click="newChat">
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>
        <div class="session-list">
          <div
            v-for="s in sessions" :key="s.id"
            class="session-item"
            :class="{ active: s.id === currentSessionId }"
            @click="switchSession(s.id)"
          >
            <div class="session-title">{{ s.title }}</div>
            <div class="session-meta">
              <span>{{ s.message_count || 0 }} 条</span>
              <span class="session-cost">¥{{ (s.total_cost || 0).toFixed(4) }}</span>
              <el-button text size="small" type="danger" @click.stop="deleteSession(s.id)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          <div v-if="!sessions.length" class="empty-hint">暂无对话</div>
        </div>
        <div v-if="currentSessionId" class="usage-bar">
          <div class="usage-item">
            <span class="usage-label">本轮 tokens</span>
            <span class="usage-value">in {{ (liveTokens.hit || 0) + (liveTokens.miss || 0) }} / out {{ liveTokens.out }}</span>
          </div>
          <div class="usage-item">
            <span class="usage-label">本轮费用</span>
            <span class="usage-value">¥{{ (liveTokens.cost || 0).toFixed(6) }}</span>
          </div>
          <el-divider style="margin:6px 0" />
          <div class="usage-item">
            <span class="usage-label">累计 tokens</span>
            <span class="usage-value">{{ currentSession?.total_tokens || 0 }}</span>
          </div>
          <div class="usage-item">
            <span class="usage-label">累计费用</span>
            <span class="usage-value">¥{{ (currentSession?.total_cost || 0).toFixed(4) }}</span>
          </div>
        </div>
      </div>

      <div class="chat-main">
        <div class="messages" ref="messagesRef">
          <div v-if="!messages.length" class="empty-state">
            <el-icon size="48" color="#cbd5e1"><ChatLineRound /></el-icon>
            <h3>开始对话</h3>
            <p>输入问题开始对话，支持上传文件（图片/PDF/Word）</p>
          </div>

          <div
            v-for="(msg, idx) in messages" :key="idx"
            class="message" :class="msg.role"
          >
            <div class="avatar">
              <el-icon v-if="msg.role === 'user'" size="18" color="#fff"><User /></el-icon>
              <el-icon v-else size="18" color="#fff"><Cpu /></el-icon>
            </div>
            <div class="bubble">
              <div v-if="msg.role === 'assistant' && msg.reasoning" class="reasoning-block">
                <div class="reasoning-header" @click="msg._showReasoning = !msg._showReasoning">
                  <el-icon :size="12"><Cpu /></el-icon>
                  <span>AI 思考过程</span>
                  <el-icon :size="10" :class="{ rotated: msg._showReasoning }"><ArrowDown /></el-icon>
                </div>
                <div v-if="msg._showReasoning" class="reasoning-content">{{ msg.reasoning }}</div>
              </div>
              <div v-if="msg.role === 'assistant'" class="msg-content" v-html="renderMath(msg.content)"></div>
              <div v-else class="msg-content">{{ msg.content }}</div>
              <div v-if="msg.usage" class="msg-usage">
                in {{ (msg.usage.hit || 0) + (msg.usage.miss || 0) }} / out {{ msg.usage.out }} · ¥{{ (msg.usage.cost || 0).toFixed(6) }}
              </div>
            </div>
          </div>

          <div v-if="isStreaming" class="message assistant">
            <div class="avatar">
              <el-icon size="18" color="#fff"><Cpu /></el-icon>
            </div>
            <div class="bubble">
              <div v-if="showReasoning && bgStreamingReasoning" class="reasoning-block streaming">
                <div class="reasoning-header">
                  <el-icon :size="12"><Cpu /></el-icon>
                  <span>AI 正在思考... {{ bgStreamingContent.length }}字</span>
                  <span class="reasoning-dot"></span>
                </div>
                <div class="reasoning-content reasoning-scroll" ref="reasoningRef">{{ bgStreamingReasoning }}</div>
              </div>
              <div class="msg-content streaming-content" v-html="renderMath(bgStreamingContent)"></div>
              <div class="streaming-actions">
                <el-button size="small" type="danger" text @click="stopStream">
                  <el-icon><Close /></el-icon> 停止回答
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <div class="input-toolbar">
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              :on-change="onFileSelect"
              accept="image/*,.pdf,.docx"
            >
              <el-button size="small" text>
                <el-icon><FolderOpened /></el-icon>
                <span>文件</span>
              </el-button>
            </el-upload>
            <span v-if="selectedFile" class="file-badge">
              <el-icon><component :is="fileIcon" /></el-icon>
              {{ selectedFile.name }}
              <el-button text size="small" @click="selectedFile = null">
                <el-icon><Close /></el-icon>
              </el-button>
            </span>
            <span class="toolbar-spacer" />
            <span class="toggle-label">思考</span>
            <el-switch v-model="showReasoning" size="small" />
            <span class="engine-label">模型</span>
            <el-select v-model="engine" size="small" style="width: 120px">
              <el-option label="自动选择" value="auto" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="Kimi" value="kimi" />
            </el-select>
          </div>
          <div class="input-row">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="1"
              resize="none"
              placeholder="输入问题..."
              @keydown.enter.prevent="sendMessage"
            />
            <el-button
              type="primary"
              circle
              :disabled="!inputText.trim()"
              @click="sendMessage"
            >
              <el-icon><Position /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ChatLineRound, User, Cpu, Position, Document, Picture,
  Plus, Delete, ArrowDown, Close, FolderOpened,
} from '@element-plus/icons-vue'
import { renderMath } from '../utils/mathRender.js'
import { useAppStore } from '../stores/app.js'

const appChatStore = useAppStore()

const messages = ref([])
const inputText = ref('')
const sessions = ref([])
const currentSessionId = ref(null)
const selectedFile = ref(null)
const engine = ref('auto')
const showReasoning = ref(true)
const messagesRef = ref(null)
const reasoningRef = ref(null)

const currentSession = computed(() => {
  return sessions.value.find(s => s.id === currentSessionId.value) || null
})

const fileIcon = computed(() => {
  if (!selectedFile.value) return 'Document'
  const name = selectedFile.value.name.toLowerCase()
  if (name.endsWith('.pdf') || name.endsWith('.docx')) return 'Document'
  return 'Picture'
})

const liveTokens = ref({ hit: 0, miss: 0, out: 0, cost: 0 })

let bgStreamingContent = ref('')
let bgStreamingReasoning = ref('')
let isStreaming = ref(false)
let bgAbortController = null
let bgSessionId = null
let bgEngine = ''
let bgMessage = ''
let bgFileText = ''

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

watch([messages], scrollToBottom, { deep: true })
watch(bgStreamingContent, scrollToBottom)
watch(bgStreamingReasoning, () => { scrollToBottom(); scrollReasoning() })

async function loadSessions() {
  try {
    const res = await axios.get('/chat/sessions')
    sessions.value = res.data.items || []
  } catch {}
}

async function newChat() {
  try {
    await loadSessions()
    const res = await axios.post('/chat/sessions')
    currentSessionId.value = res.data.id
    messages.value = []
    liveTokens.value = { hit: 0, miss: 0, out: 0, cost: 0 }
    await loadSessions()
  } catch {
    ElMessage.error('创建会话失败')
  }
}

async function switchSession(id) {
  if (id === currentSessionId.value) return
  currentSessionId.value = id
  messages.value = []
  liveTokens.value = { hit: 0, miss: 0, out: 0, cost: 0 }
  try {
    const res = await axios.get(`/chat/sessions/${id}`)
    messages.value = (res.data.messages || []).map(m => ({
      ...m,
      _showReasoning: false,
    }))
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].usage) {
        liveTokens.value = messages.value[i].usage
        break
      }
    }
  } catch {
    ElMessage.error('加载失败')
  }
}

async function deleteSession(id) {
  if (id === bgSessionId) return
  try {
    await ElMessageBox.confirm('删除此对话？', '提示', { type: 'warning' })
    await axios.delete(`/chat/sessions/${id}`)
    if (currentSessionId.value === id) {
      currentSessionId.value = null
      messages.value = []
    }
    await loadSessions()
  } catch {}
}

function onFileSelect(file) {
  selectedFile.value = file.raw
}

function stopStream() {
  if (bgAbortController) {
    bgAbortController.abort()
    bgAbortController = null
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return

  bgEngine = engine.value
  bgMessage = text
  bgFileText = ''

  let targetSessionId = currentSessionId.value
  if (!targetSessionId) {
    try {
      const res = await axios.post('/chat/sessions')
      targetSessionId = res.data.id
      currentSessionId.value = targetSessionId
      await loadSessions()
    } catch {
      ElMessage.error('创建会话失败')
      return
    }
  }

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  isStreaming.value = true
  bgStreamingContent.value = ''
  bgStreamingReasoning.value = ''
  bgSessionId = targetSessionId
  liveTokens.value = { hit: 0, miss: 0, out: 0, cost: 0 }

  const formData = new FormData()
  formData.append('message', text)
  formData.append('engine', bgEngine)
  formData.append('reasoning', showReasoning.value ? 'true' : 'false')
  formData.append('session_id', targetSessionId)
  if (selectedFile.value) {
    formData.append('file', selectedFile.value)
    selectedFile.value = null
  }

  let fullText = ''
  let fullReasoning = ''

  try {
    bgAbortController = new AbortController()
    const res = await fetch('/api/chat/send', {
      method: 'POST',
      body: formData,
      credentials: 'include',
      signal: bgAbortController.signal,
    })

    if (!res.ok) {
      let detail = `请求失败 (${res.status})`
      try { const t = await res.text(); try { detail = JSON.parse(t).detail || detail } catch { detail = t || detail } } catch {}
      isStreaming.value = false
      messages.value.push({ role: 'assistant', content: detail })
      bgStreamingContent.value = ''
      bgStreamingReasoning.value = ''
      return
    }

    if (!res.body) {
      isStreaming.value = false
      messages.value.push({ role: 'assistant', content: '服务器无响应' })
      bgStreamingContent.value = ''
      bgStreamingReasoning.value = ''
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalUsage = null

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
          const newMsg = { role: 'assistant', content: fullText, reasoning: fullReasoning, usage: finalUsage, _showReasoning: false }
          if (currentSessionId.value === bgSessionId) {
            messages.value.push(newMsg)
            bgStreamingContent.value = ''
            bgStreamingReasoning.value = ''
          }
          isStreaming.value = false
          await loadSessions()
          return
        }
        try {
          const msg = JSON.parse(payload)
          if (msg.type === 'content') {
            fullText += msg.text
            bgStreamingContent.value = fullText
          } else if (msg.type === 'reasoning') {
            fullReasoning += msg.text
            bgStreamingReasoning.value = fullReasoning
          } else if (msg.type === 'progress') {
            liveTokens.value.hit = msg.hit_tokens || 0
            liveTokens.value.miss = msg.miss_tokens || (msg.input_tokens || 0)
            liveTokens.value.out = msg.output_tokens || 0
            liveTokens.value.cost = msg.cost || 0
            appChatStore.setCurrentSessionUsage({ tokens_in: (liveTokens.value.hit || 0) + (liveTokens.value.miss || 0), tokens_out: liveTokens.value.out || 0, cost: liveTokens.value.cost || 0 })
          } else if (msg.type === 'done') {
            finalUsage = msg.usage
            liveTokens.value = finalUsage
            appChatStore.loadTodayUsage()
          } else if (msg.type === 'error') {
            if (currentSessionId.value === bgSessionId) {
              messages.value.push({ role: 'assistant', content: msg.text })
            }
            isStreaming.value = false
            bgStreamingContent.value = ''
            bgStreamingReasoning.value = ''
          }
        } catch {}
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      if (fullText) {
        const newMsg = { role: 'assistant', content: fullText, reasoning: fullReasoning, _showReasoning: false }
        if (currentSessionId.value === bgSessionId) {
          messages.value.push(newMsg)
        }
      }
    }
    isStreaming.value = false
    bgStreamingContent.value = ''
    bgStreamingReasoning.value = ''
  }
}

onMounted(async () => {
  await loadSessions()
  if (sessions.value.length > 0) {
    await switchSession(sessions.value[0].id)
  } else {
    await newChat()
  }
})
</script>

<style scoped>
.chat-page {
  height: 100vh;
  display: flex;
  background: #f8fafc;
}
.chat-layout {
  display: flex;
  width: 100%;
  height: 100%;
}
.chat-sidebar {
  width: 240px;
  min-width: 240px;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
}
.sidebar-title {
  font-weight: 600;
  font-size: 14px;
  color: #1e3a5f;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.session-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.15s;
}
.session-item:hover { background: #f1f5f9; }
.session-item.active { background: #eff6ff; }
.session-title {
  font-size: 13px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.session-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #94a3b8;
}
.session-meta .session-cost {
  margin-left: auto;
  font-weight: 500;
  color: #64748b;
}
.empty-hint {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #94a3b8;
}
.usage-bar {
  border-top: 1px solid #f1f5f9;
  padding: 12px 16px;
  font-size: 11px;
  color: #64748b;
}
.usage-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 3px;
}
.usage-label { color: #94a3b8; }
.usage-value { font-weight: 500; color: #334155; }

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
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
  gap: 12px;
  color: #94a3b8;
}
.empty-state h3 {
  margin: 0;
  font-size: 16px;
  color: #475569;
}
.empty-state p {
  margin: 0;
  font-size: 13px;
}
.message {
  display: flex;
  gap: 10px;
  max-width: 80%;
}
.message.user { align-self: flex-end; flex-direction: row-reverse; }
.message.assistant { align-self: flex-start; }
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.message.user .avatar { background: #2563eb; }
.message.assistant .avatar { background: linear-gradient(135deg, #667eea, #764ba2); }
.bubble {
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;
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
.msg-content { white-space: pre-wrap; }
.message.user .msg-content { color: #fff; }
.streaming-content { color: #1e40af; }
.msg-usage {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #f1f5f9;
  font-size: 10px;
  color: #94a3b8;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.message.user .msg-usage { border-top-color: rgba(255,255,255,0.2); color: rgba(255,255,255,0.6); }
.streaming-actions {
  margin-top: 8px;
  display: flex;
  justify-content: center;
}
.reasoning-block {
  margin-bottom: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}
.reasoning-block.streaming { border-color: #93c5fd; }
.reasoning-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: 11px;
  color: #64748b;
  cursor: pointer;
  background: #f1f5f9;
  user-select: none;
}
.reasoning-header .rotated { transform: rotate(180deg); transition: transform 0.2s; }
.reasoning-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #3b82f6;
  margin-left: auto;
  animation: pulse 0.8s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.reasoning-content {
  padding: 10px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  border-top: 1px solid #e2e8f0;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
}
.reasoning-scroll {
  max-height: 300px;
  overflow-y: auto;
}

.input-area {
  flex-shrink: 0;
  padding: 16px 24px 24px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
}
.input-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.file-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: #f1f5f9;
  border-radius: 12px;
  font-size: 12px;
  color: #475569;
}
.toolbar-spacer { flex: 1; }
.engine-label, .toggle-label { font-size: 12px; color: #94a3b8; }
.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
.input-row :deep(.el-textarea__inner) {
  border-radius: 14px;
  padding: 10px 14px;
  resize: none;
  max-height: 120px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  border: none;
}
.input-row :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 2px #2563eb33 inset;
}
.input-row :deep(.el-button) {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
}
:deep(.katex-error) { color: #cc0000; }
:deep(.math-inline) { color: #2563eb; font-family: 'Courier New', monospace; }
:deep(.math-block) {
  color: #2563eb; font-family: 'Courier New', monospace;
  display: block; margin: 8px 0; padding: 8px 12px;
  background: #eff6ff; border-radius: 6px;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .chat-page {
    height: calc(100vh - 48px);
  }
  .chat-sidebar {
    position: fixed;
    left: 0;
    top: 48px;
    height: calc(100vh - 48px);
    z-index: 140;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    width: 220px;
    min-width: 220px;
  }
  .chat-sidebar.show-mobile {
    transform: translateX(0);
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
  .input-toolbar {
    flex-wrap: wrap;
    gap: 6px;
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
