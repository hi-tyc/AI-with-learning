<template>
  <div class="doc-detail-page">
    <div class="content">
      <div class="page-header">
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <div class="header-row">
          <h1 class="page-title">{{ pageTitle }}</h1>
          <el-button size="small" text type="primary" @click="viewSourceDoc" :icon="Document">查看文档</el-button>
        </div>
        <p class="page-subtitle">源文件：{{ sourceFile }}</p>
        <div v-if="docType === '题目' || docType === '答案'" class="wrong-action-bar">
          <el-button
            size="small"
            type="warning"
            :icon="CircleClose"
            :disabled="items.length === 0 || selectedWrong.size === 0"
            @click="batchToggleWrong"
          >
            {{ selectedWrong.size > 0 ? (allSelectedInWrong ? '移出选中错题本' : '加入选中到错题本') : (docType === '答案' ? '请选择答案' : '请选择题目') }}
          </el-button>
          <el-checkbox
            :model-value="selectedWrong.size === items.length && items.length > 0"
            :indeterminate="selectedWrong.size > 0 && selectedWrong.size < items.length"
            @change="toggleSelectAllWrong"
          >全选</el-checkbox>
          <span v-if="selectedWrong.size > 0" class="wrong-count">已选 {{ selectedWrong.size }} 项</span>
        </div>
        <div v-if="docType === '题目' || docType === '答案'" class="view-option-bar">
          <el-checkbox v-model="showMatched" size="small">显示匹配内容</el-checkbox>
        </div>
        <div v-if="docType === '词单' && displayWords.length" class="wrong-action-bar">
          <el-button
            size="small"
            type="warning"
            :icon="CircleClose"
            :disabled="selectedWordIndices.size === 0"
            @click="batchToggleWrongWords"
          >
            {{ anyWordInWrong ? '移出选中错题本' : '加入选中到错题本' }}
          </el-button>
          <el-checkbox
            :model-value="selectedWordIndices.size === displayWords.length && displayWords.length > 0"
            :indeterminate="selectedWordIndices.size > 0 && selectedWordIndices.size < displayWords.length"
            @change="toggleSelectAllWords"
          >全选</el-checkbox>
          <span v-if="selectedWordIndices.size > 0" class="wrong-count">已选 {{ selectedWordIndices.size }} 词</span>
        </div>
      </div>

      <div v-if="loading" class="loading-state">
        <el-icon class="spinning"><Loading /></el-icon>
        <span>加载中…</span>
      </div>

      <div v-else-if="docType === '词单' && wordListData" class="word-list-panel">
        <div class="word-list-header">
          <span class="word-list-title">{{ wordListData.filename }}</span>
          <span v-if="wordListData.is_student" class="student-badge">学生版</span>
          <el-tag size="small" type="info">{{ displayWordCount }} 个单词</el-tag>
        </div>
        <div v-if="wordListData.is_student && wordListData.teacher_version" class="teacher-hint">
          已关联教师版：<span class="teacher-name">{{ wordListData.teacher_version.filename }}</span>
        </div>
        <div v-if="displayWords.length">
          <div class="word-grid">
            <div
              v-for="(w, idx) in displayWords"
              :key="idx"
              class="word-card"
              :class="{ selected: selectedWordIndices.has(idx), wrong: wordWrongStatus.has(idx) }"
            >
              <div class="word-cb" @click.stop="toggleWordSelect(idx)">
                <el-checkbox :model-value="selectedWordIndices.has(idx) || wordWrongStatus.has(idx)" @click.stop />
              </div>
              <span class="word-english">{{ w.english }}</span>
              <span v-if="w.pos" class="word-pos">{{ w.pos }}</span>
              <span class="word-chinese">{{ w.chinese }}</span>
              <el-button size="small" text type="primary" @click.stop="showEditWord(wordListData.id, idx, w)">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button size="small" text type="danger" @click.stop="deleteSingleWord(wordListData.id, idx)">
                <el-icon><Close /></el-icon>
              </el-button>
              <el-button
                v-if="wordWrongStatus.has(idx)"
                size="small"
                text
                type="success"
                @click.stop="toggleSingleWord(idx)"
              >
                <el-icon><CircleCheck /></el-icon>
              </el-button>
              <el-button
                v-else
                size="small"
                text
                type="danger"
                @click.stop="toggleSingleWord(idx)"
              >
                <el-icon><CircleClose /></el-icon>
              </el-button>
            </div>
          </div>
          <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
            <el-input v-model="newWord.english" placeholder="英文" size="small" style="width:180px" />
            <el-input v-model="newWord.chinese" placeholder="中文" size="small" style="width:180px" />
            <el-input v-model="newWord.pos" placeholder="词性" size="small" style="width:100px" />
            <el-button size="small" type="primary" @click="addSingleWord" :loading="newWord.saving">添加单词</el-button>
          </div>
        </div>
        <div v-else class="empty-hint">暂无单词数据</div>
      </div>
      <div v-else-if="items.length === 0" class="empty-state">
        <p>{{ docType === '词单' ? '未找到词单数据' : '未找到小题' }}</p>
      </div>

      <div v-else class="item-list">
        <div
          v-for="(item, idx) in items"
          :key="item.id"
          class="item-card"
          :class="{ clickable: true, selected: selectedWrong.has(item.id) }"
        >
          <div v-if="docType === '题目' || docType === '答案'" class="item-cb" @click.stop="toggleWrongSelect(item.id)">
            <el-checkbox :model-value="selectedWrong.has(item.id)" @click.stop />
          </div>
          <div class="item-index" @click="docType === '题目' ? solveItem(item) : openMatchedProblem(item)">{{ idx + 1 }}</div>
          <div class="item-content" @click="docType === '题目' ? solveItem(item) : openMatchedProblem(item)">
            {{ item.content }}
            <div v-if="showMatched && docType === '题目' && matchedItems[item.id]" class="matched-block matched-answer-block">
              <div class="matched-label">对应答案：</div>
              <div v-for="m in matchedItems[item.id]" :key="m.id" class="matched-text">{{ m.content }}</div>
            </div>
            <div v-else-if="showMatched && docType === '题目'" class="matched-block unmatched-block">
              <div class="matched-label">未对应答案</div>
            </div>
            <div v-if="showMatched && docType === '答案' && matchedItems[item.id]" class="matched-block matched-problem-block">
              <div class="matched-label">对应题目：</div>
              <div v-for="m in matchedItems[item.id]" :key="m.id" class="matched-text">{{ m.content }}</div>
            </div>
            <div v-else-if="showMatched && docType === '答案'" class="matched-block unmatched-block">
              <div class="matched-label">未对应题目</div>
            </div>
          </div>
          <div class="item-action">
            <el-button v-if="docType === '题目'" size="small" type="primary" text @click.stop="solveItem(item)">解题</el-button>
            <el-button
              v-if="docType === '题目'"
              size="small"
              :type="selectedWrong.has(item.id) ? 'success' : 'danger'"
              text
              @click.stop="toggleSingleProblem(item)"
            >
              <el-icon><component :is="selectedWrong.has(item.id) ? 'CircleCheck' : 'CircleClose'" /></el-icon>
            </el-button>
            <el-button
              v-if="docType === '答案'"
              size="small"
              :type="selectedWrong.has(item.id) ? 'success' : 'danger'"
              text
              @click.stop="toggleSingleAnswer(item)"
            >
              <el-icon><component :is="selectedWrong.has(item.id) ? 'CircleCheck' : 'CircleClose'" /></el-icon>
            </el-button>
            <el-button v-if="docType === '答案' && matchedItems[item.id]" size="small" type="primary" text @click.stop="openMatchedProblem(item)">解题</el-button>
            <el-button
              v-if="docType === '题目' || docType === '答案'"
              size="small"
              text
              type="warning"
              @click.stop="showEditItem(item)"
            >
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button
              v-if="docType === '题目' || docType === '答案'"
              size="small"
              text
              type="warning"
              @click.stop="showManualMatch(item)"
            >
              <el-icon><Link /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="previewVisible" title="源文档内容" width="820px" top="5vh">
      <div class="preview-mode-bar">
        <span class="preview-mode-label">文本预览</span>
        <span v-if="previewFileType" class="preview-type-tag">
          <el-tag size="small" type="info">{{ previewFileType.toUpperCase() }}</el-tag>
        </span>
      </div>

      <div v-if="previewLoading" class="preview-loading">加载中…</div>
      <div v-else-if="previewError" class="preview-error">{{ previewError }}</div>
      <div v-else-if="previewIsHtml" class="preview-content docx-html" v-html="previewHtml"></div>
      <div v-else class="preview-content" v-html="renderMath(previewText)"></div>

      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
        <template v-if="previewFileId">
          <el-button type="success" :icon="View" tag="a" :href="originalFileUrl" target="_blank" rel="noopener">打开原文</el-button>
          <el-button :icon="Printer" @click="printDocument">打印</el-button>
          <el-button type="primary" :icon="Download" tag="a" :href="downloadFileUrl" rel="noopener">下载</el-button>
        </template>
        <el-button v-else type="success" :icon="View" disabled>原文缺失</el-button>
      </template>
    </el-dialog>

    <!-- 编辑条目对话框 -->
    <el-dialog v-model="editDialog.visible" :title="'编辑' + (docType === '题目' ? '题目' : '答案')" width="650px" top="10vh">
      <el-form label-position="top">
        <el-form-item :label="docType === '答案' ? '答案内容' : '题目内容'">
          <el-input v-model="editDialog.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item v-if="docType === '答案'" label="答案说明">
          <el-input v-model="editDialog.answer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editDialog.tag" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveEditItem" :loading="editDialog.saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑单词对话框 -->
    <el-dialog v-model="wordEdit.visible" title="编辑单词" width="450px">
      <el-form label-position="top">
        <el-form-item label="英文">
          <el-input v-model="wordEdit.english" />
        </el-form-item>
        <el-form-item label="词性">
          <el-input v-model="wordEdit.pos" placeholder="如 v./adj./n." />
        </el-form-item>
        <el-form-item label="中文">
          <el-input v-model="wordEdit.chinese" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="wordEdit.visible = false">取消</el-button>
        <el-button type="primary" @click="saveWordEdit" :loading="wordEdit.saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 手动对应对话框 -->
    <el-dialog v-model="manualMatch.visible" :title="docType === '题目' ? '对应答案' : '对应题目'" width="600px" top="10vh">
      <div v-if="manualMatch.loading" class="preview-loading">加载中…</div>
      <div v-else>
        <p style="margin:0 0 16px;color:#475569;font-size:13px">
          {{ docType === '题目' ? '选择一条答案来与当前题目对应：' : '选择一道题目来与当前答案对应：' }}
        </p>
        <div v-if="unmatchedItems.length" class="match-list">
          <div
            v-for="item in unmatchedItems"
            :key="item.id"
            class="match-item"
            :class="{ selected: manualMatch.selectedId === item.id }"
            @click="manualMatch.selectedId = item.id"
          >
            <div class="match-content">{{ (item.content || '').slice(0, 200) }}</div>
            <div class="match-id">#{{ item.id.slice(0, 8) }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无未{{ docType === '题目' ? '对应的答案' : '对应的题目' }}" :image-size="60" />
      </div>
      <template #footer>
        <el-button @click="manualMatch.visible = false">关闭</el-button>
        <el-button v-if="manualMatch.selectedId" type="primary" @click="createManualMatch" :loading="manualMatch.saving">确认对应</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Loading, Document, CircleClose, CircleCheck, Link, Edit, Close, View, Printer, Download } from '@element-plus/icons-vue'
import { useAppStore } from '../../stores/app.js'
import { renderMath } from '../../utils/mathRender.js'

const app = useAppStore()
const route = useRoute()
const router = useRouter()

const sourceFile = ref('')
const docType = ref('')
const items = ref([])
const loading = ref(true)
const matchedItems = ref({})
const showMatched = ref(true)
const wordListData = ref(null)
const selectedWrong = ref(new Set())
const selectedWordIndices = ref(new Set())
const wordWrongStatus = ref(new Set())

const pageTitle = computed(() => {
  if (docType.value === '题目') return '题目详情'
  if (docType.value === '答案') return '答案详情'
  return '词单详情'
})

const allSelectedInWrong = computed(() => {
  return selectedWrong.value.size > 0 && [...selectedWrong.value].every(id => existingWrongIds.value.has(id))
})

const existingWrongIds = computed(() => {
  const s = new Set()
  for (const item of items.value) {
    if (selectedWrong.value.has(item.id)) s.add(item.id)
  }
  return s
})

const anyWordInWrong = computed(() => {
  return [...selectedWordIndices.value].some(idx => wordWrongStatus.value.has(idx))
})

const displayWords = computed(() => {
  if (!wordListData.value) return []
  if (wordListData.value.teacher_version) return wordListData.value.teacher_version.words || []
  return wordListData.value.words || []
})

const displayWordCount = computed(() => {
  if (!wordListData.value) return 0
  if (wordListData.value.teacher_version) return wordListData.value.teacher_version.word_count || 0
  return wordListData.value.word_count || 0
})

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const previewText = ref('')
const previewHtml = ref('')
const previewIsHtml = ref(false)
const previewFileId = ref('')
const previewFileType = ref('')

const originalFileUrl = computed(() => {
  if (!previewFileId.value) return ''
  const ft = (previewFileType.value || '').toLowerCase()
  if (['pdf', 'jpg', 'jpeg', 'png', 'image'].includes(ft)) {
    return `/api/materials/${encodeURIComponent(previewFileId.value)}/file`
  }
  return `/api/materials/${encodeURIComponent(previewFileId.value)}/pdf`
})

const downloadFileUrl = computed(() => {
  if (!previewFileId.value) return ''
  return `/api/materials/${encodeURIComponent(previewFileId.value)}/file?download=1`
})

// 编辑条目
const editDialog = ref({
  visible: false, saving: false, itemId: '', content: '', tag: '', answer: '',
})

// 编辑单词
const wordEdit = ref({
  visible: false, saving: false, wordId: '', wordIdx: -1, english: '', pos: '', chinese: '',
})

// 新增单词
const newWord = ref({ english: '', pos: '', chinese: '', saving: false })

// 手动对应
const manualMatch = ref({
  visible: false, selectedId: '', loading: false, saving: false, itemId: '',
})
const unmatchedItems = ref([])

onMounted(async () => {
  app.setActiveTab('资料')
  sourceFile.value = route.params.sourceFile
  docType.value = route.query.type || '题目'
  await loadItems()
  if (docType.value === '题目') {
    await loadWrongStatus()
  } else if (docType.value === '答案') {
    await loadAnswerWrongStatus()
  } else if (docType.value === '词单') {
    await loadWordWrongStatus()
  }
})

async function loadWordWrongStatus() {
  try {
    const status = new Set()
    for (let idx = 0; idx < displayWords.value.length; idx++) {
      const wid = wordListData.value ? wordListData.value.id : ''
      if (wid) {
        const res = await axios.get(`/english-wrong/check-word/${wid}/${idx}`)
        if (res.data.is_wrong) status.add(idx)
      }
    }
    wordWrongStatus.value = status
  } catch {}
}

async function loadAnswerWrongStatus() {
  try {
    const s = new Set()
    for (const item of items.value) {
      const res = await axios.get(`/english-wrong/check-answer/${item.id}`)
      if (res.data.is_wrong) s.add(item.id)
    }
    selectedWrong.value = s
  } catch {}
}

async function loadWrongStatus() {
  try {
    const wrongStatus = {}
    for (const item of items.value) {
      const res = await axios.get(`/english-wrong/check/${item.id}`)
      wrongStatus[item.id] = res.data.is_wrong
    }
    const s = new Set()
    for (const [id, isW] of Object.entries(wrongStatus)) {
      if (isW) s.add(id)
    }
    selectedWrong.value = s
  } catch {}
}

async function loadItems() {
  loading.value = true
  try {
    const sourceFileName = sourceFile.value
    if (docType.value === '题目') {
      const res = await axios.get('/problems?page_size=5000')
      const problems = (res.data.items || []).filter(p => p.subject === '英语')
      items.value = problems.filter(p => (p.source_file || p.filename) === sourceFileName)
    } else if (docType.value === '词单') {
      const res = await axios.get('/english-upload/words')
      let found = (res.data.items || []).find(w => w.id === sourceFileName)
      if (found && found.is_student) {
        try {
          const matchRes = await axios.get(`/match-answers/word-match/${sourceFileName}`)
          if (matchRes.data.teacher) {
            found = { ...found, teacher_version: matchRes.data.teacher }
          }
        } catch {}
      }
      wordListData.value = found || null
      return
    } else {
      const res = await axios.get('/english-upload/answers')
      items.value = (res.data.items || []).filter(a => (a.source_file || a.filename) === sourceFileName)
    }
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
  if (items.value.length) {
    const matched = {}
    for (const item of items.value) {
      try {
        let res
        if (docType.value === '题目') {
          res = await axios.get(`/match-answers/for-problem/${item.id}`)
          if (res.data.answers && res.data.answers.length) {
            matched[item.id] = res.data.answers
          }
        } else {
          res = await axios.get(`/match-answers/for-answer/${item.id}`)
          if (res.data.problems && res.data.problems.length) {
            matched[item.id] = res.data.problems
          }
        }
      } catch {}
    }
    matchedItems.value = matched
  }
}

function toggleWrongSelect(id) {
  const s = new Set(selectedWrong.value)
  if (s.has(id)) { s.delete(id) } else { s.add(id) }
  selectedWrong.value = s
}

function toggleSelectAllWrong(checked) {
  if (checked) {
    selectedWrong.value = new Set(items.value.map(i => i.id))
  } else {
    selectedWrong.value = new Set()
  }
}

function toggleWordSelect(idx) {
  const s = new Set(selectedWordIndices.value)
  if (s.has(idx)) { s.delete(idx) } else { s.add(idx) }
  selectedWordIndices.value = s
}

function toggleSelectAllWords(checked) {
  if (checked) {
    selectedWordIndices.value = new Set(displayWords.value.map((_, i) => i))
  } else {
    selectedWordIndices.value = new Set()
  }
}

async function batchToggleWrong() {
  if (!selectedWrong.value.size) return
  const toggleEndpoint = docType.value === '答案' ? 'toggle-answer' : 'toggle-problem'
  const ids = [...selectedWrong.value]
  const s = new Set(selectedWrong.value)
  let successCount = 0
  for (const id of ids) {
    try {
      const res = await axios.post(`/english-wrong/${toggleEndpoint}/${id}`)
      if (res.data.is_wrong) { s.add(id) } else { s.delete(id) }
      successCount++
    } catch { /* skip failed */ }
  }
  selectedWrong.value = s
  ElMessage.success(`已处理 ${successCount}/${ids.length} 项`)
}

async function toggleSingleAnswer(item) {
  try {
    const res = await axios.post(`/english-wrong/toggle-answer/${item.id}`)
    const s = new Set(selectedWrong.value)
    if (res.data.is_wrong) {
      s.add(item.id)
    } else {
      s.delete(item.id)
    }
    selectedWrong.value = s
    ElMessage.success(res.data.message)
  } catch {
    ElMessage.error('操作失败')
  }
}

async function toggleSingleProblem(item) {
  try {
    const res = await axios.post(`/english-wrong/toggle-problem/${item.id}`)
    const isNowWrong = res.data.is_wrong
    const s = new Set(selectedWrong.value)
    if (isNowWrong) {
      s.add(item.id)
    } else {
      s.delete(item.id)
    }
    selectedWrong.value = s
    ElMessage.success(res.data.message)
  } catch {
    ElMessage.error('操作失败')
  }
}

async function toggleSingleWord(idx) {
  const wid = wordListData.value ? wordListData.value.id : ''
  if (!wid) return
  try {
    const res = await axios.post(`/english-wrong/toggle-word/${wid}/${idx}`)
    const isNowWrong = res.data.is_wrong
    const s = new Set(wordWrongStatus.value)
    if (isNowWrong) {
      s.add(idx)
    } else {
      s.delete(idx)
    }
    wordWrongStatus.value = s
    ElMessage.success(res.data.message)
  } catch {
    ElMessage.error('操作失败')
  }
}

async function batchToggleWrongWords() {
  const wid = wordListData.value ? wordListData.value.id : ''
  if (!wid || !selectedWordIndices.value.size) return

  const indices = [...selectedWordIndices.value]
  const s = new Set(wordWrongStatus.value)
  let successCount = 0
  for (const idx of indices) {
    try {
      const res = await axios.post(`/english-wrong/toggle-word/${wid}/${idx}`)
      if (res.data.is_wrong) { s.add(idx) } else { s.delete(idx) }
      successCount++
    } catch { /* skip failed */ }
  }
  wordWrongStatus.value = s
  selectedWordIndices.value = new Set()
  ElMessage.success(`已处理 ${successCount}/${indices.length} 词`)
}

function openMatchedProblem(item) {
  const problems = matchedItems.value[item.id]
  if (problems && problems.length) {
    const p = problems[0]
    sessionStorage.setItem('quickSolve', JSON.stringify({
      id: p.id, content: p.content || '', subject: '英语',
      knowledge_point: p.knowledge_point || '',
      image_file_id: p.image_file_id || '',
      existingSolution: p.solution || '',
      solvedBy: p.solved_by || '',
      matchedAnswer: item.content || '',
    }))
    router.push('/english/solve')
  }
}

async function viewSourceDoc() {
  previewVisible.value = true
  previewText.value = ''
  previewHtml.value = ''
  previewIsHtml.value = false
  previewError.value = ''
  previewLoading.value = true
  previewFileId.value = ''
  previewFileType.value = ''
  try {
    let fileId = null
    let fileType = ''
    let hasText = false
    if (docType.value === '词单') {
      const wordRes = await axios.get('/english-upload/words')
      const found = (wordRes.data.items || []).find(w => w.id === sourceFile.value)
      if (found) {
        fileId = found.upload_file_id || found.id
        fileType = found.file_type || 'docx'
      }
      if (!fileId && found && found.source_file) {
        const matRes = await axios.get('/materials')
        const mat = (matRes.data.items || []).find(m => m.filename === found.source_file)
        if (mat) {
          fileId = mat.id
          fileType = mat.file_type || found.file_type || 'docx'
        }
      }
    } else {
      const matRes = await axios.get('/materials')
      const materials = matRes.data.items || []
      const mat = materials.find(m => m.filename === sourceFile.value)
      if (mat) {
        fileId = mat.id
        fileType = mat.file_type || ''
        hasText = mat.has_text
      }
      if (!fileId) {
        const probRes = await axios.get('/problems?page_size=5000')
        const prob = (probRes.data.items || []).find(p =>
          (p.source_file || p.filename) === sourceFile.value && p.upload_file_id
        )
        if (prob) {
          fileId = prob.upload_file_id
          fileType = prob.file_type || inferFileType(prob.source_file || prob.filename || '')
          const uploadMat = materials.find(m => m.id === prob.upload_file_id)
          hasText = uploadMat ? uploadMat.has_text : hasText
        }
      }
      if (!fileId) {
        const ansRes = await axios.get('/english-upload/answers')
        const ans = (ansRes.data.items || []).find(a =>
          (a.source_file || a.filename) === sourceFile.value && a.upload_file_id
        )
        if (ans) {
          fileId = ans.upload_file_id
          fileType = ans.file_type || inferFileType(ans.source_file || ans.filename || '')
          const uploadMat = materials.find(m => m.id === ans.upload_file_id)
          hasText = uploadMat ? uploadMat.has_text : hasText
        }
      }
    }
    if (fileId) {
      previewFileId.value = fileId
      previewFileType.value = fileType || inferFileType(sourceFile.value)
      const ft = (previewFileType.value || '').toLowerCase()
      if (['jpg','jpeg','png','image'].includes(ft)) {
        previewHtml.value = `<img src="/api/materials/${encodeURIComponent(fileId)}/file" style="max-width:100%;display:block;">`
        previewIsHtml.value = true
      } else if (ft === 'pdf') {
        previewHtml.value = `<iframe src="/api/materials/${encodeURIComponent(fileId)}/file" style="width:100%;height:65vh;border:none;"></iframe>`
        previewIsHtml.value = true
      } else {
        const textRes = await axios.get(`/materials/${fileId}/text`)
        const text = textRes.data.text || ''
        if (text) {
          previewText.value = text
        } else {
          previewError.value = '该文档未提取到文字内容。'
        }
      }
    } else {
      previewError.value = '未找到源文档'
    }
  } catch {
    previewError.value = '加载失败'
  } finally {
    previewLoading.value = false
  }
}

function buildDocViewerUrl(fileId, fileType, fileName, extra) {
  const base = `${window.location.origin}${window.location.pathname}#/document-viewer`
  const params = new URLSearchParams({
    fileId: fileId || previewFileId.value,
    fileType: fileType || previewFileType.value,
    fileName: fileName || sourceFile.value,
  })
  if (extra) Object.entries(extra).forEach(([k, v]) => { if (v) params.set(k, v) })
  return `${base}?${params.toString()}`
}

function getFileUrl(id) {
  return `/api/materials/${encodeURIComponent(id || previewFileId.value)}/file`
}

function printDocument() {
  const id = previewFileId.value
  if (!id) return
  const ft = (previewFileType.value || '').toLowerCase()
  const url = ['pdf', 'jpg', 'jpeg', 'png', 'image'].includes(ft)
    ? `/api/materials/${encodeURIComponent(id)}/file`
    : `/api/materials/${encodeURIComponent(id)}/pdf`

  const iframe = document.createElement('iframe')
  iframe.style.cssText = 'position:fixed;left:-9999px;top:-9999px;width:1200px;height:800px;border:none'
  iframe.src = url

  let printed = false
  const doPrint = () => {
    if (printed) return
    printed = true
    try {
      iframe.contentWindow.print()
    } catch {}
    setTimeout(() => { if (iframe.parentNode) iframe.parentNode.removeChild(iframe) }, 3000)
  }

  iframe.onload = () => { setTimeout(doPrint, 2000) }
  setTimeout(doPrint, 8000)
  document.body.appendChild(iframe)
}

function inferFileType(filename) {
  if (!filename) return ''
  const ext = filename.split('.').pop().toLowerCase()
  if (ext === 'pdf') return 'pdf'
  if (ext === 'docx') return 'docx'
  if (['jpg', 'jpeg', 'png'].includes(ext)) return ext === 'png' ? 'png' : 'jpg'
  return ext
}

function solveItem(item) {
  const ans = (item.id && matchedItems.value[item.id]) || []
  sessionStorage.setItem('quickSolve', JSON.stringify({
    id: item.id, content: item.content || '', subject: '英语',
    knowledge_point: item.knowledge_point || '',
    image_file_id: item.image_file_id || '',
    existingSolution: item.solution || '',
    solvedBy: item.solved_by || '',
    matchedAnswer: ans.map(a => a.content).join('\n'),
  }))
  router.push('/english/solve')
}

// 编辑条目
function showEditItem(item) {
  editDialog.value = {
    visible: true, saving: false,
    itemId: item.id,
    content: item.content || '',
    tag: item.tag || '',
    answer: item.answer || '',
  }
}

async function saveEditItem() {
  editDialog.value.saving = true
  try {
    if (docType.value === '题目') {
      await axios.put(`/problems/${editDialog.value.itemId}`, {
        content: editDialog.value.content,
      })
    } else {
      await axios.put(`/english-upload/answers/${editDialog.value.itemId}`, {
        content: editDialog.value.content,
        tag: editDialog.value.tag,
        answer: editDialog.value.answer,
      })
    }
    ElMessage.success('保存成功')
    editDialog.value.visible = false
    await loadItems()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    editDialog.value.saving = false
  }
}

// 编辑单词
function showEditWord(wlId, idx, word) {
  wordEdit.value = {
    visible: true, saving: false,
    wordId: wlId, wordIdx: idx,
    english: word.english || '',
    pos: word.pos || '',
    chinese: word.chinese || '',
  }
}

async function saveWordEdit() {
  wordEdit.value.saving = true
  try {
    await axios.put(`/english-upload/words/${wordEdit.value.wordId}/words/${wordEdit.value.wordIdx}`, {
      english: wordEdit.value.english,
      pos: wordEdit.value.pos,
      chinese: wordEdit.value.chinese,
    })
    ElMessage.success('保存成功')
    wordEdit.value.visible = false
    await loadItems()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    wordEdit.value.saving = false
  }
}

async function addSingleWord() {
  if (!newWord.value.english.trim()) { ElMessage.warning('请输入英文'); return }
  newWord.value.saving = true
  try {
    await axios.post(`/english-upload/words/${wordListData.value.id}/words`, {
      english: newWord.value.english.trim(),
      pos: newWord.value.pos.trim(),
      chinese: newWord.value.chinese.trim(),
    })
    ElMessage.success('已添加')
    newWord.value = { english: '', pos: '', chinese: '', saving: false }
    await loadItems()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  } finally {
    newWord.value.saving = false
  }
}

async function deleteSingleWord(wlId, idx) {
  try {
    await axios.delete(`/english-upload/words/${wlId}/words/${idx}`)
    ElMessage.success('已删除')
    await loadItems()
  } catch {
    ElMessage.error('删除失败')
  }
}

// 手动对应
async function showManualMatch(item) {
  manualMatch.value = {
    visible: true,
    selectedId: '',
    loading: true,
    saving: false,
    itemId: item.id,
  }
  unmatchedItems.value = []
  try {
    const res = await axios.get('/match-answers/unmatched')
    // 如果是题目，显示未对应的答案；如果是答案，显示未对应的题目
    const items = docType.value === '题目' ? (res.data.answers || []) : (res.data.problems || [])
    unmatchedItems.value = items.map(i => ({
      id: i.id, content: i.content || '',
    }))
  } catch {
    ElMessage.error('加载数据失败')
  } finally {
    manualMatch.value.loading = false
  }
}

async function createManualMatch() {
  if (!manualMatch.value.selectedId) return
  manualMatch.value.saving = true
  try {
    const params = docType.value === '题目'
      ? { problem_id: manualMatch.value.itemId, answer_id: manualMatch.value.selectedId }
      : { problem_id: manualMatch.value.selectedId, answer_id: manualMatch.value.itemId }
    await axios.post('/match-answers/manual-match', params)
    ElMessage.success('对应成功')
    manualMatch.value.visible = false
    await loadItems()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '对应失败')
  } finally {
    manualMatch.value.saving = false
  }
}
</script>

<style scoped>
.doc-detail-page { min-height: 100vh; background: #f0fdf4; }
.content { max-width: 800px; margin: 0 auto; padding: 32px 24px; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 28px; font-weight: 700; color: #065f46; margin: 8px 0 4px; }
.page-subtitle { font-size: 14px; color: #6b7280; margin: 0; }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.wrong-action-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; background: #fef2f2;
  border: 1px solid #fecaca; border-radius: 10px; font-size: 13px; margin-top: 12px;
}
.view-option-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 0; font-size: 13px; color: #475569;
}
.wrong-count { font-size: 12px; color: #dc2626; font-weight: 600; }
.loading-state { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 60px 0; color: #6b7280; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.empty-state { text-align: center; padding: 60px 0; color: #94a3b8; }
.item-list { display: flex; flex-direction: column; gap: 12px; }
.item-card {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 16px; background: #fff; border-radius: 12px;
  border: 1px solid #e2e8f0; transition: all 0.15s ease;
}
.item-card.clickable { cursor: pointer; }
.item-card.clickable:hover { border-color: #a7f3d0; box-shadow: 0 4px 12px rgba(0,0,0,0.04); }
.item-card.selected { background: #fef2f2; border-color: #fecaca; }
.item-cb { flex-shrink: 0; padding-top: 4px; }
.item-index {
  width: 28px; height: 28px; border-radius: 50%; background: #059669;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600; flex-shrink: 0; cursor: pointer;
}
.item-content { flex: 1; font-size: 14px; line-height: 1.7; color: #334155; white-space: pre-wrap; word-break: break-word; }
.matched-block { margin-top: 8px; padding: 8px 12px; border-radius: 8px; border-left: 3px solid; }
.matched-answer-block { background: #f0fdf4; border-left-color: #059669; }
.matched-problem-block { background: #eff6ff; border-left-color: #2563eb; }
.matched-label { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.matched-answer-block .matched-label { color: #059669; }
.matched-problem-block .matched-label { color: #2563eb; }
.unmatched-block .matched-label { color: #94a3b8; }
.matched-text { font-size: 13px; line-height: 1.6; }
.matched-answer-block .matched-text { color: #065f46; }
.matched-problem-block .matched-text { color: #1e40af; }
.unmatched-block { opacity: 0.7; }
.item-action { flex-shrink: 0; display: flex; gap: 4px; align-items: center; }
.preview-loading { padding: 40px; text-align: center; color: #94a3b8; }
.preview-error { padding: 40px; text-align: center; color: #dc2626; }
.preview-mode-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}
.preview-mode-label {
  font-weight: 600;
  color: #334155;
}
.open-original-link {
  text-decoration: none;
  display: inline-block;
}
.preview-content { font-size: 14px; line-height: 1.8; color: #334155; max-height: 60vh; overflow-y: auto; word-break: break-word; }
.preview-content h1, .preview-content h2, .preview-content h3 { margin: 16px 0 8px; color: #1e293b; }
.preview-content h1 { font-size: 20px; }
.preview-content h2 { font-size: 18px; }
.preview-content h3 { font-size: 16px; }
.preview-content table { border-collapse: collapse; width: 100%; margin: 12px 0; }
.preview-content th, .preview-content td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
.preview-content th { background: #f8fafc; font-weight: 600; }
.preview-content tr:nth-child(even) { background: #f8fafc; }
.preview-content ul, .preview-content ol { padding-left: 24px; margin: 8px 0; }
.preview-content li { margin: 4px 0; }
.preview-content code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.preview-content pre { background: #f8fafc; padding: 12px; border-radius: 8px; overflow-x: auto; }
.word-list-panel { background: #fff; border-radius: 16px; border: 1px solid #e2e8f0; padding: 24px; }
.word-list-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #e2e8f0; }
.word-list-title { font-size: 16px; font-weight: 600; color: #1e293b; }
.word-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 8px; }
.word-card {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; background: #f8fafc; border-radius: 8px;
  border: 1px solid #e2e8f0; transition: all 0.15s;
}
.word-card:hover { background: #f1f5f9; border-color: #cbd5e1; }
.word-card.selected { background: #fef2f2; border-color: #fecaca; }
.word-card.wrong { background: #fef2f2; border-color: #fca5a5; }
.word-cb { flex-shrink: 0; }
.word-english { flex: 1; font-size: 14px; font-weight: 600; color: #1e293b; font-family: 'Courier New', monospace; }
.word-pos { font-size: 11px; color: #475569; background: #e2e8f0; padding: 1px 6px; border-radius: 4px; font-weight: 500; }
.word-chinese { font-size: 13px; color: #64748b; min-width: 80px; }
.student-badge { font-size: 11px; background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.teacher-hint { font-size: 12px; color: #64748b; margin-bottom: 16px; padding: 8px 12px; background: #f0f9ff; border-radius: 8px; }
.teacher-name { color: #2563eb; font-weight: 600; }
.empty-hint { text-align: center; padding: 40px; color: #94a3b8; font-size: 14px; }
.match-list { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.match-item {
  padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0;
  cursor: pointer; transition: all 0.15s; background: #f8fafc;
}
.match-item:hover { border-color: #2563eb; background: #eff6ff; }
.match-item.selected { border-color: #2563eb; background: #dbeafe; }
.match-content { font-size: 13px; color: #334155; line-height: 1.5; margin-bottom: 4px; }
.match-id { font-size: 11px; color: #94a3b8; font-family: monospace; }

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .doc-detail-page {
    padding: 16px 12px;
  }
  .doc-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .doc-title {
    font-size: 18px;
  }
  .content-section {
    padding: 12px;
  }
  .word-grid {
    grid-template-columns: 1fr;
  }
  .word-card {
    flex-wrap: wrap;
    padding: 8px 10px;
  }
  .word-list-panel {
    padding: 16px;
  }
  .preview-content {
    max-height: 50vh;
  }
  .preview-content h1 { font-size: 18px; }
  .preview-content h2 { font-size: 16px; }
  .preview-content h3 { font-size: 14px; }
}
</style>
