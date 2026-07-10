<template>
  <div class="wrong-book-page">
    <div class="content">
      <div class="page-header">
        <div>
          <h1 class="page-title">英语错题本</h1>
          <p class="page-subtitle">管理标记为错题的题目，生成错题集进行复习</p>
        </div>
      </div>

      <div class="filter-bar">
        <el-select v-model="filterTimeRange" placeholder="时间范围" clearable size="large" style="width:150px">
          <el-option label="今日标记" value="today" />
          <el-option label="本周标记" value="week" />
          <el-option label="全部" value="all" />
        </el-select>
        <el-select v-model="filterExamTag" placeholder="考试标签" clearable size="large" style="width:160px">
          <el-option v-for="t in examTags" :key="t" :label="t" :value="t" />
        </el-select>
        <el-checkbox v-model="showAll" label="包含已匹配" border size="large" />
        <el-radio-group v-model="genType" size="large" style="margin-left:4px">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="problem">题目/答案</el-radio-button>
          <el-radio-button value="word">仅词单</el-radio-button>
        </el-radio-group>
        <el-button type="primary" size="large" :icon="Document" @click="showNameDialog = true">生成Word文档</el-button>
      </div>

      <div v-if="loading" class="loading-state">
        <el-icon class="spinning"><Loading /></el-icon>
        <span>加载中…</span>
      </div>

      <div v-else-if="items.length === 0" class="empty-state">
        <el-icon size="48" color="#cbd5e1"><CircleClose /></el-icon>
        <h3>错题本为空</h3>
        <p>在资料库的题目详情中选择小题加入错题本</p>
        <el-button type="success" @click="$router.push('/english/library')">前往资料库</el-button>
      </div>

      <div v-else class="wrong-list">
        <div class="list-header">
          <span class="total-count">共 {{ items.length }} 题</span>
          <el-button v-if="selectedIds.size > 0" size="small" type="danger" text @click="removeSelected">
            移出选中 ({{ selectedIds.size }})
          </el-button>
          <el-checkbox
            v-if="items.length"
            :model-value="selectedIds.size === items.length"
            :indeterminate="selectedIds.size > 0 && selectedIds.size < items.length"
            @change="toggleSelectAll"
          >全选</el-checkbox>
        </div>

        <div
          v-for="(item, idx) in items"
          :key="item.id"
          class="wrong-card"
          :class="{ selected: selectedIds.has(item.id) }"
        >
          <div class="card-index">
            <el-checkbox :model-value="selectedIds.has(item.id)" @change="toggleSelect(item.id)" />
            <span class="index-num">{{ idx + 1 }}</span>
          </div>
          <div class="card-body">
            <div v-if="item.type === 'word'" class="word-wrong-body">
              <span class="word-eng">{{ item.word_english }}</span>
              <span v-if="item.word_pos" class="word-pos">{{ item.word_pos }}</span>
              <span class="word-chi">{{ item.word_chinese }}</span>
            </div>
            <template v-else>
              <div class="card-content">{{ item.content }}</div>
              <div v-if="item.answer_contents && item.answer_contents.length" class="answer-block">
                <div class="answer-label">对应答案：</div>
                <div v-for="(ac, ai) in item.answer_contents" :key="ai" class="answer-text">{{ ac }}</div>
              </div>
            </template>
            <div class="card-meta">
              <el-tag v-if="item.mismatch_flag" size="small" type="danger">未匹配</el-tag>
              <el-tag v-if="item.has_solution" size="small" type="success">已解答</el-tag>
              <el-tag v-else size="small" type="info">未解答</el-tag>
              <span class="meta-tag">{{ item.exam_tag || item.tag }}</span>
              <span class="meta-source">{{ item.source_file }}</span>
              <span class="meta-time">{{ formatTime(item.created_at) }}</span>
            </div>
          </div>
          <div class="card-action">
            <el-button text size="small" type="danger" @click="removeItem(item.id)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="showNameDialog" title="错题本名称" width="420px" :close-on-click-modal="false">
      <div class="name-dialog-body">
        <p style="margin:0 0 12px;font-size:13px;color:#6b7280">设置生成文档的名称，学生版和答案版将自动添加后缀。</p>
        <el-input
          v-model="docName"
          placeholder="错题本"
          size="large"
          clearable
          @keydown.enter="confirmGenerate"
        >
          <template #prepend>名称</template>
          <template #append>_学生版.docx</template>
        </el-input>
        <p style="margin:8px 0 0;font-size:12px;color:#9ca3af">默认名称自动编号：错题本_001、错题本_002…</p>
      </div>
      <template #footer>
        <el-button @click="showNameDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmGenerate" :loading="generating">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Loading, CircleClose, Document, Delete } from '@element-plus/icons-vue'
import { useAppStore } from '../../stores/app.js'

const app = useAppStore()

const loading = ref(false)
const items = ref([])
const examTags = ref([])
const selectedIds = ref(new Set())
const filterTimeRange = ref('all')
const filterExamTag = ref('')
const showAll = ref(true)
const showNameDialog = ref(false)
const docName = ref('')
const generating = ref(false)
const genType = ref('all')

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadItems() {
  loading.value = true
  try {
    const params = { show_all: showAll.value }
    if (filterTimeRange.value && filterTimeRange.value !== 'all') params.time_range = filterTimeRange.value
    if (filterExamTag.value) params.exam_tag = filterExamTag.value
    const res = await axios.get('/english-wrong/list', { params })
    items.value = res.data.items || []
  } catch {
    ElMessage.error('加载错题本失败')
  } finally {
    loading.value = false
  }
}

async function loadExamTags() {
  try {
    const res = await axios.get('/english-wrong/exam-tags')
    examTags.value = res.data.tags || []
  } catch {}
}

function toggleSelect(id) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
}

function toggleSelectAll(checked) {
  if (checked) {
    selectedIds.value = new Set(items.value.map(i => i.id))
  } else {
    selectedIds.value.clear()
  }
}

async function removeItem(id) {
  try {
    await axios.post('/english-wrong/remove', { ids: [id] })
    ElMessage.success('已移出错题本')
    selectedIds.value.delete(id)
    await loadItems()
  } catch {
    ElMessage.error('移除失败')
  }
}

async function removeSelected() {
  if (!selectedIds.value.size) return
  try {
    await axios.post('/english-wrong/remove', { ids: [...selectedIds.value] })
    ElMessage.success(`已移出 ${selectedIds.value.size} 题`)
    selectedIds.value.clear()
    await loadItems()
  } catch {
    ElMessage.error('批量移除失败')
  }
}

function getNextDocNumber() {
  try {
    const key = 'wrong_book_gen_count'
    const val = parseInt(localStorage.getItem(key) || '0', 10)
    const next = val + 1
    localStorage.setItem(key, String(next))
    return String(next).padStart(3, '0')
  } catch {
    return '001'
  }
}

function confirmGenerate() {
  let name = (docName.value || '').trim()
  if (!name) {
    name = '错题本_' + getNextDocNumber()
  }
  showNameDialog.value = false
  generateWord(name)
}

async function generateWord(name) {
  generating.value = true
  try {
    const res = await fetch('/api/english-wrong/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        time_range: filterTimeRange.value || 'all',
        exam_tag: filterExamTag.value || '',
        show_all: showAll.value,
        gen_type: genType.value,
      }),
      credentials: 'include',
    })
    if (!res.ok) {
      ElMessage.error('生成失败')
      return
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let resultData = null
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        if (payload === '[DONE]') continue
        try {
          const msg = JSON.parse(payload)
          if (msg.type === 'result') {
            resultData = msg
          } else if (msg.type === 'error') {
            ElMessage.error(msg.text)
            return
          }
        } catch {}
      }
    }
    if (resultData) {
      downloadDocx(resultData.student_docx, `${name}_学生版.docx`)
      downloadDocx(resultData.answer_docx, `${name}_答案版.docx`)
      ElMessage.success(`已生成 ${resultData.count} 题的错题本：${name}`)
    } else {
      ElMessage.error('未获取到文档数据')
    }
  } catch (e) {
    ElMessage.error('生成Word失败: ' + (e.message || ''))
  } finally {
    generating.value = false
  }
}

function downloadDocx(hexStr, filename) {
  const bytes = new Uint8Array(hexStr.match(/.{1,2}/g).map(b => parseInt(b, 16)))
  const blob = new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

watch([filterTimeRange, filterExamTag, showAll], () => {
  selectedIds.value.clear()
  loadItems()
})

onMounted(() => {
  app.setActiveTab('错题')
  loadItems()
  loadExamTags()
})
</script>

<style scoped>
.wrong-book-page {
  min-height: 100vh;
  background: #f0fdf4;
}
.content {
  max-width: 800px;
  margin: 0 auto;
  padding: 32px 24px;
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
  margin: 0 0 24px;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  align-items: center;
}
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  color: #6b7280;
}
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: #94a3b8;
  gap: 12px;
}
.empty-state h3 { font-size: 18px; font-weight: 600; color: #475569; margin: 0; }
.empty-state p { font-size: 14px; margin: 0; }
.list-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 12px;
}
.total-count {
  font-size: 13px;
  color: #6b7280;
  margin-right: auto;
}
.wrong-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wrong-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: all 0.15s ease;
}
.wrong-card:hover {
  border-color: #a7f3d0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.wrong-card.selected {
  background: #f0fdf4;
  border-color: #6ee7b7;
}
.card-index {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.index-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #059669;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}
.card-body {
  flex: 1;
  min-width: 0;
}
.card-content {
  font-size: 14px;
  line-height: 1.7;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}
.word-wrong-body {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  font-size: 14px; line-height: 1.7; color: #334155;
}
.word-eng { font-weight: 600; font-family: 'Courier New', monospace; }
.word-pos { font-size: 11px; color: #475569; background: #e2e8f0; padding: 1px 6px; border-radius: 4px; }
.word-chi { color: #64748b; }
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
}
.meta-tag {
  font-size: 11px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
}
.meta-source {
  font-size: 11px;
  color: #9ca3af;
}
.meta-time {
  font-size: 11px;
  color: #9ca3af;
  margin-left: auto;
}
.answer-block {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f0fdf4;
  border-left: 3px solid #059669;
  border-radius: 6px;
}
.answer-label {
  font-size: 12px;
  font-weight: 600;
  color: #059669;
  margin-bottom: 4px;
}
.answer-text {
  font-size: 13px;
  line-height: 1.6;
  color: #065f46;
}
.card-action {
  flex-shrink: 0;
}
.name-dialog-body {
  padding: 8px 0;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .wrong-book-page {
    padding: 16px 12px;
  }
  .page-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .page-title {
    font-size: 22px;
  }
  .filter-bar {
    flex-wrap: wrap;
    gap: 8px;
  }
  .filter-bar .el-input,
  .filter-bar .el-select {
    width: 100% !important;
  }
  .problem-card {
    padding: 12px;
  }
  .card-header {
    flex-wrap: wrap;
    gap: 6px;
  }
  .card-content {
    font-size: 13px;
  }
  .answer-text {
    font-size: 12px;
  }
}
</style>
