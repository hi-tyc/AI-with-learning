<template>
  <div class="english-library-page">
    <div class="content">
      <div class="page-header">
        <h1 class="page-title">英语资料</h1>
        <p class="page-subtitle">浏览所有已上传的资料、题目和答案</p>
      </div>

      <div class="filter-bar">
        <el-select v-model="filterTag" placeholder="考试" clearable size="large" style="width:140px">
          <el-option label="月考1" value="月考1" />
          <el-option label="期中" value="期中" />
          <el-option label="月考2" value="月考2" />
          <el-option label="期末" value="期末" />
          <el-option label="其他" value="其他" />
        </el-select>
        <el-select v-model="filterSemester" placeholder="学期" clearable size="large" style="width:160px">
          <el-option label="不指定学期" value="" />
          <el-option label="25-26 第一学期" value="25-26 第一学期" />
          <el-option label="25-26 第二学期" value="25-26 第二学期" />
          <el-option label="26-27 第一学期" value="26-27 第一学期" />
          <el-option label="26-27 第二学期" value="26-27 第二学期" />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索内容…"
          clearable
          size="large"
          style="flex:1"
        />
      </div>

      <div v-if="loading" class="loading-state">
        <el-icon class="spinning"><Loading /></el-icon>
        <span>加载中…</span>
      </div>

      <div v-else-if="filteredItems.length === 0" class="empty-state">
        <el-icon size="48" color="#cbd5e1"><Collection /></el-icon>
        <h3>暂无数据</h3>
        <p>请先上传英语资料</p>
        <el-button type="success" @click="$router.push('/english-upload')">上传资料</el-button>
      </div>

      <div v-else class="tree-panel">
        <div class="panel-header">
          <el-icon><Collection /></el-icon>
          <span>资料库</span>
          <span class="panel-count">共 {{ filteredItems.length }} 项</span>
          <el-button size="small" text @click="openMatchModeDialog" :icon="Link" type="primary">对应</el-button>
          <el-button size="small" text @click="runWordMatch" :icon="Link" type="warning">匹配词单</el-button>
          <el-button size="small" text @click="showDocPairing = true" :icon="Link" type="success">文档对应</el-button>
          <el-button size="small" text @click="showTrash = true" :icon="Delete">废纸篓</el-button>
        </div>

        <!-- 批量操作栏 -->
        <div v-if="selectedUids.size > 0" class="batch-bar">
          <el-checkbox :model-value="selectedUids.size === filteredItems.length" :indeterminate="selectedUids.size > 0 && selectedUids.size < filteredItems.length" @change="toggleSelectAll">
            已选 {{ selectedUids.size }} 项
          </el-checkbox>
          <el-button size="small" type="danger" @click="batchDelete" :icon="Delete">批量删除</el-button>
          <el-button size="small" text @click="matchSelected" :icon="Link">匹配选中</el-button>
          <el-button size="small" text @click="selectedUids.clear()">取消选择</el-button>
        </div>

        <el-collapse v-model="activeTypes">
          <el-collapse-item
            v-for="group in groupedItems"
            :key="group.type"
            :title="group.type"
            :name="group.type"
          >
            <template #title>
              <div class="collapse-title">
                <el-tag :type="typeTagType(group.type)" size="small" effect="dark">{{ group.type }}</el-tag>
                <span class="group-count">{{ group.items.length }} 项</span>
              </div>
            </template>
            <div class="file-list">
              <div
                v-for="item in group.items"
                :key="item._uid"
                class="file-item"
                :class="{ clickable: item._clickable, selected: selectedUids.has(item._uid) }"
                @click="item._clickable && openItem(item)"
              >
                <el-checkbox v-if="item._deleteType" :model-value="selectedUids.has(item._uid)" @click.stop="toggleSelect(item)" class="item-cb" />
                <div class="file-info">
                  <span class="file-name">{{ item.displayName }}</span>
                  <span class="file-meta">{{ item.meta }}</span>
                </div>
                <el-button v-if="item.type !== '词单'" text size="small" type="warning" @click.stop="showAdjustType(item)">
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button v-if="item.type === '题目' || item.type === '答案'" text size="small" type="primary" @click.stop="showManualMatch(item)">
                  <el-icon><Link /></el-icon> 对应
                </el-button>
                <el-button v-if="item._deleteType" text size="small" type="danger" @click.stop="deleteItem(item)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <!-- 废纸篓对话框 -->
    <el-dialog v-model="showTrash" title="废纸篓" width="600px" top="5vh">
      <div v-if="trashLoading" class="preview-loading">加载中…</div>
      <div v-else-if="trashItems.length === 0" class="empty-state" style="padding:40px 0">
        <p>废纸篓为空</p>
      </div>
      <div v-else class="trash-list">
        <div v-for="item in trashItems" :key="item.id" class="trash-item">
          <el-icon size="16" :color="item._origin_type === 'material' ? '#f59e0b' : '#059669'">
            <component :is="item._origin_type === 'material' ? 'Document' : 'Document'" />
          </el-icon>
          <div class="trash-info">
            <span class="trash-name">{{ item.filename || item.content?.slice(0, 50) || '未命名' }}</span>
            <span class="trash-meta">{{ item._origin_type === 'material' ? '资料' : '答案' }} · {{ formatTime(item.trashed_at) }}</span>
          </div>
          <el-button size="small" text type="primary" @click="restoreTrashItem(item.id)">恢复</el-button>
          <el-button size="small" text type="danger" @click="permanentDelete(item.id)">永久删除</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="showTrash = false">关闭</el-button>
        <el-button v-if="trashItems.length" type="danger" @click="emptyTrash">清空废纸篓</el-button>
      </template>
    </el-dialog>

    <!-- 对应范围选择对话框 -->
    <el-dialog v-model="showMatchModeDialog" title="选择对应范围" width="360px" top="30vh">
      <el-radio-group v-model="selectedMatchMode" style="display:flex;flex-direction:column;gap:12px">
        <el-radio value="today">对应今天上传的文档</el-radio>
        <el-radio value="all">对应所有未匹配的文档</el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="showMatchModeDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmMatchMode">确定</el-button>
      </template>
    </el-dialog>

    <!-- 题目答案对应对话框 -->
    <el-dialog v-model="showMatchDialog" :title="matchTitle" width="680px" top="10vh" :close-on-click-modal="false" class="resize-dialog" draggable>
      <div>
        <p style="margin:0 0 16px;color:#475569">
          {{ matchMode === 'word' ? '自动为学生版词单匹配对应的教师版词单。' : matchMode === 'today' ? '仅匹配今天上传的文档。' : matchMode === 'selected' ? '匹配选中的文档。' : '匹配所有未匹配的文档。' }}
          {{ matchMode === 'word' ? '系统会根据文件名和中文释义重叠度进行匹配。' : 'AI 先匹配文件名，再逐文件匹配题目与答案。' }}
        </p>
        <div v-if="matchMode !== 'word'" class="match-stats">
          <div class="stat-row"><span>题目总数</span><span>{{ matchStatus.total_problems }}</span></div>
          <div class="stat-row"><span>已对应题目</span><span class="stat-highlight">{{ matchStatus.matched_problems }}</span></div>
          <div class="stat-row"><span>答案总数</span><span>{{ matchStatus.total_answers }}</span></div>
          <div class="stat-row"><span>已对应答案</span><span class="stat-highlight">{{ matchStatus.matched_answers }}</span></div>
          <div class="stat-row"><span>已匹配文档对</span><span>{{ matchStatus.matched_files || 0 }}</span></div>
          <div v-if="matchMode === 'today'" class="stat-row"><span>今日题目</span><span>{{ matchStatus.today_problems || 0 }}</span></div>
          <div v-if="matchMode === 'today'" class="stat-row"><span>今日答案</span><span>{{ matchStatus.today_answers || 0 }}</span></div>
        </div>

        <div v-if="matchMode !== 'word'" style="margin:12px 0">
          <el-checkbox v-model="matchForce" :disabled="matchRunning">
            强制重新匹配已对应文件（会覆盖旧对应关系）
          </el-checkbox>
        </div>
        <!-- 实时进度 -->
        <div v-if="matchProgress" class="match-progress" :class="{ 'match-error': matchProgress.startsWith('❌'), 'match-done': matchProgress.startsWith('✅') || matchProgress.startsWith('⏹') }">
          <el-icon v-if="matchRunning" class="spinning"><Loading /></el-icon>
          <el-icon v-else-if="matchProgress.startsWith('✅')" color="#059669"><CircleCheck /></el-icon>
          <el-icon v-else-if="matchProgress.startsWith('❌')" color="#dc2626"><CircleClose /></el-icon>
          <span>{{ matchProgress }}</span>
        </div>
        <!-- AI输出日志（实时滚动，最多显示5行） -->
        <div v-if="matchLines.length || streamingAiOutput" class="match-log" ref="matchLogRef">
          <div v-for="line in visibleMatchLines" :key="line.id" class="match-log-line">{{ line.text }}</div>
          <div v-if="streamingAiOutput" class="match-log-line streaming-line">🤖 {{ streamingAiOutput }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showMatchDialog = false" :disabled="matchRunning && !matchCancelled">关闭</el-button>
        <el-button v-if="!matchRunning" type="primary" @click="runMatch" :icon="Link">开始对应</el-button>
        <el-button v-else type="danger" :disabled="matchCancelled" @click="cancelMatch">
          <el-icon><Close /></el-icon> 取消
        </el-button>
        <el-button v-if="!matchRunning && matchStatus.matched_files > 0" size="small" text type="danger" @click="resetMatches">清空对应</el-button>
      </template>
    </el-dialog>

    <!-- 资料预览对话框 -->
    <el-dialog v-model="previewVisible" title="资料预览" width="820px" top="5vh">
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
        <template v-if="previewMaterialId">
          <el-button type="success" :icon="View" tag="a" :href="originalFileUrl" target="_blank" rel="noopener">打开原文</el-button>
          <el-button :icon="Printer" @click="printDocument">打印</el-button>
          <el-button type="primary" :icon="Download" tag="a" :href="downloadFileUrl" rel="noopener">下载</el-button>
        </template>
        <el-button v-else type="success" :icon="View" disabled>原文缺失</el-button>
        <el-button type="primary" @click="solveWithMaterial" :icon="Lightning">解题</el-button>
      </template>
    </el-dialog>

    <!-- 调整类型对话框 -->
    <el-dialog v-model="adjustDialog.visible" title="调整资料类型" width="480px" class="resize-dialog" draggable>
      <p style="margin:0 0 16px;color:#475569">当前文件：<strong>{{ adjustDialog.filename }}</strong></p>
      <p style="margin:0 0 12px;color:#64748b">当前类型：<el-tag :type="adjustDialog.currentType === '题目' ? 'primary' : adjustDialog.currentType === '答案' ? 'success' : 'warning'" size="small" effect="dark">{{ adjustDialog.currentType }}</el-tag></p>
      <el-form label-position="top">
        <el-form-item label="调整为目标类型">
          <el-select v-model="adjustDialog.targetType" style="width:100%">
            <el-option v-for="t in adjustTypeOptions" :key="t" :label="t" :value="t" :disabled="t === adjustDialog.currentType" />
          </el-select>
        </el-form-item>
      </el-form>
      <div v-if="adjustDialog.resultMsg" style="margin-top:12px;max-height:200px;overflow:auto;padding:10px;background:#f8fafc;border-radius:8px;font-size:13px;white-space:pre-wrap;line-height:1.5;">
        {{ adjustDialog.resultMsg }}
      </div>
      <template #footer>
        <el-button @click="adjustDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="doAdjustType" :loading="adjustDialog.loading">确认调整</el-button>
      </template>
    </el-dialog>

    <!-- 文档对应对话框 -->
    <el-dialog v-model="showDocPairing" title="文档对应" width="680px" top="5vh">
      <div v-if="docPairing.loading" class="preview-loading">加载中…</div>
      <div v-else>
        <div style="display:flex;gap:16px;margin-bottom:20px">
          <div style="flex:1">
            <label style="font-size:13px;font-weight:600;color:#334155;display:block;margin-bottom:6px">题目文件</label>
            <el-select v-model="docPairing.probFile" filterable style="width:100%">
              <el-option v-for="f in docPairing.unmatchedProbFiles" :key="f" :label="f" :value="f" />
            </el-select>
          </div>
          <div style="flex:1">
            <label style="font-size:13px;font-weight:600;color:#334155;display:block;margin-bottom:6px">答案文件</label>
            <el-select v-model="docPairing.ansFile" filterable style="width:100%">
              <el-option v-for="f in docPairing.unmatchedAnsFiles" :key="f" :label="f" :value="f" />
            </el-select>
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:20px">
          <el-button type="primary" :disabled="!docPairing.probFile || !docPairing.ansFile" @click="saveDocPair(false)" :icon="Link">保存对应</el-button>
          <el-button type="success" :disabled="!docPairing.probFile || !docPairing.ansFile" @click="saveDocPair(true)" :loading="docPairing.matching">
            <el-icon><Cpu /></el-icon> 保存并AI匹配题目
          </el-button>
        </div>

        <el-divider>已对应文档</el-divider>
        <div v-if="docPairing.pairs.length" class="match-select-list" style="max-height:240px">
          <div v-for="(pair, idx) in docPairing.pairs" :key="idx" class="match-select-item" style="display:flex;align-items:center;gap:8px">
            <el-icon color="#2563eb"><Document /></el-icon>
            <span style="flex:1;font-size:12px">{{ pair.actual_problem_file || pair.problem_file }}</span>
            <el-icon><ArrowRight /></el-icon>
            <span style="flex:1;font-size:12px">{{ pair.actual_answer_file || pair.answer_file }}</span>
            <el-button text size="small" type="danger" @click="deleteDocPair(pair)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
        <el-empty v-else description="暂无已对应文档" :image-size="50" />

        <el-divider>词单对应</el-divider>
        <div style="display:flex;gap:16px;margin-bottom:12px">
          <div style="flex:1">
            <label style="font-size:13px;font-weight:600;color:#334155;display:block;margin-bottom:6px">学生版词单</label>
            <el-select v-model="docPairing.wordStudentFile" filterable style="width:100%">
              <el-option v-for="f in docPairing.wordStudentFiles" :key="f.id" :label="f.filename" :value="f.id" />
            </el-select>
          </div>
          <div style="flex:1">
            <label style="font-size:13px;font-weight:600;color:#334155;display:block;margin-bottom:6px">教师版词单</label>
            <el-select v-model="docPairing.wordTeacherFile" filterable style="width:100%">
              <el-option v-for="f in docPairing.wordTeacherFiles" :key="f.id" :label="f.filename" :value="f.id" />
            </el-select>
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:20px">
          <el-button type="primary" :disabled="!docPairing.wordStudentFile || !docPairing.wordTeacherFile" @click="saveWordPair" :icon="Link">保存词单对应</el-button>
        </div>
        <div v-if="docPairing.wordPairs.length" class="match-select-list" style="max-height:180px">
          <div v-for="(pair, idx) in docPairing.wordPairs" :key="idx" class="match-select-item" style="display:flex;align-items:center;gap:8px">
            <el-icon color="#2563eb"><Document /></el-icon>
            <span style="flex:1;font-size:12px">{{ pair.student_filename }}</span>
            <el-icon><ArrowRight /></el-icon>
            <span style="flex:1;font-size:12px">{{ pair.teacher_filename }}</span>
            <el-button text size="small" type="danger" @click="deleteWordPair(pair)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
        <el-empty v-else description="暂无已对应词单" :image-size="50" />
      </div>
      <template #footer>
        <el-button @click="showDocPairing = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 手动对应对话框 -->
    <el-dialog v-model="manualMatch.visible" title="手动对应题目与答案" width="800px" top="5vh">
      <div v-if="manualMatch.loading" class="preview-loading">加载中…</div>
      <div v-else>
        <p style="margin:0 0 8px;color:#475569">当前文件：<strong>{{ manualMatch.currentName }}</strong></p>
        <p style="margin:0 0 16px;color:#64748b;font-size:13px">
          左侧选择要对应的{{ manualMatch.currentType }}条目，右侧选择对应的{{ manualMatch.currentType === '题目' ? '答案' : '题目' }}条目。
        </p>

        <div style="display:flex;gap:16px;max-height:420px">
          <!-- 当前文件条目 -->
          <div style="flex:1;display:flex;flex-direction:column;min-width:0">
            <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#334155">{{ manualMatch.currentType }}条目</p>
            <div v-if="manualMatch.currentFileItems.length" class="match-select-list" style="flex:1;overflow:auto">
              <div
                v-for="item in manualMatch.currentFileItems"
                :key="item.id"
                class="match-select-item"
                :class="{ selected: manualMatch.currentItemId === item.id }"
                @click="manualMatch.currentItemId = item.id"
              >
                <div class="match-select-content">{{ (item.content || '').slice(0, 180) }}</div>
                <div class="match-select-meta">{{ item.id }}</div>
              </div>
            </div>
            <el-empty v-else description="无条目" :image-size="50" />
          </div>

          <!-- 未对应条目 -->
          <div style="flex:1;display:flex;flex-direction:column;min-width:0">
            <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#334155">{{ manualMatch.currentType === '题目' ? '未对应答案' : '未对应题目' }}</p>
            <div v-if="unmatchedItems.length" class="match-select-list" style="flex:1;overflow:auto">
              <div
                v-for="item in unmatchedItems"
                :key="item.id"
                class="match-select-item"
                :class="{ selected: manualMatch.selectedId === item.id }"
                @click="manualMatch.selectedId = item.id"
              >
                <div class="match-select-content">{{ (item.content || '').slice(0, 180) }}</div>
                <div class="match-select-meta">{{ item.id }}</div>
              </div>
            </div>
            <el-empty v-else :description="'没有未对应的' + (manualMatch.currentType === '题目' ? '答案' : '题目')" :image-size="50" />
          </div>
        </div>

        <div v-if="existingMatch" class="existing-match-info">
          <p style="margin:16px 0 0;color:#059669;font-size:13px">已存在对应关系</p>
          <el-button size="small" type="danger" text @click="deleteManualMatch">取消对应</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="manualMatch.visible = false">关闭</el-button>
        <el-button v-if="!manualMatch.loading && manualMatch.currentItemId && manualMatch.selectedId" type="primary" @click="createManualMatch" :loading="manualMatch.saving">确认对应</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, Loading, Delete, Lightning, Link, Close, CircleCheck, CircleClose, Edit, Document, ArrowRight, Cpu, View, Printer, Download } from '@element-plus/icons-vue'
import { useAppStore } from '../../stores/app.js'
import { renderMath } from '../../utils/mathRender.js'


const app = useAppStore()
const router = useRouter()

const keyword = ref('')
const filterTag = ref('')
const filterSemester = ref('')
const loading = ref(false)
const activeTypes = ref(['资料', '题目', '答案', '词单'])
const selectedUids = ref(new Set())

const rawMaterials = ref([])
const rawProblems = ref([])
const rawAnswers = ref([])
const rawWords = ref([])

// 预览
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const previewText = ref('')
const previewHtml = ref('')
const previewIsHtml = ref(false)
const previewMaterialId = ref('')
const previewFileType = ref('')
const previewFileName = ref('')

// 调整类型
const adjustDialog = ref({
  visible: false, filename: '', sourceFile: '', currentType: '', targetType: '', loading: false, fileId: '', resultMsg: '',
})
const adjustTypeOptions = computed(() => ['题目', '答案', '资料'].filter(t => t !== adjustDialog.value.currentType))

const originalFileUrl = computed(() => {
  if (!previewMaterialId.value) return ''
  const ft = (previewFileType.value || '').toLowerCase()
  if (['pdf', 'jpg', 'jpeg', 'png', 'image'].includes(ft)) {
    return `/api/materials/${encodeURIComponent(previewMaterialId.value)}/file`
  }
  return `/api/materials/${encodeURIComponent(previewMaterialId.value)}/pdf`
})

const downloadFileUrl = computed(() => {
  if (!previewMaterialId.value) return ''
  return `/api/materials/${encodeURIComponent(previewMaterialId.value)}/file?download=1`
})

// 文档对应
const showDocPairing = ref(false)
const docPairing = ref({
  loading: false, matching: false,
  probFile: '', ansFile: '',
  unmatchedProbFiles: [], unmatchedAnsFiles: [],
  pairs: [],
  wordStudentFile: '', wordTeacherFile: '',
  wordStudentFiles: [], wordTeacherFiles: [],
  wordPairs: [],
})

// 手动对应
const manualMatch = ref({
  visible: false, currentType: '', currentName: '', currentId: '',
  currentFileItems: [], currentItemId: '', selectedId: '', loading: false, saving: false,
})
const unmatchedItems = ref([])
const existingMatch = ref(null)

// 废纸篓
const showTrash = ref(false)
const trashItems = ref([])
const trashLoading = ref(false)

// 题目答案对应
const showMatchDialog = ref(false)
const showMatchModeDialog = ref(false)
const selectedMatchMode = ref('today')
const matchMode = ref('all')

const matchRunning = ref(false)
const matchStatus = ref({ total_problems: 0, matched_problems: 0, total_answers: 0, matched_answers: 0, matched_files: 0, today_problems: 0, today_answers: 0 })
const matchProgress = ref('')
const matchCancelled = ref(false)
const matchLines = ref([])
const matchSelectedFiles = ref([])
const matchForce = ref(false)
const streamingAiOutput = ref('')
const streamingAiPair = ref(-1)
const matchLogRef = ref(null)
let matchAbortController = null
let matchLineId = 0

function parseTag(tagStr) {
  if (!tagStr) return { tag: '', semester: '' }
  const parts = tagStr.split(' / ')
  if (parts.length >= 2) return { tag: parts[0], semester: parts.slice(1).join(' / ') }
  return { tag: parts[0], semester: '' }
}

function matchesFilter(tagStr) {
  const { tag, semester } = parseTag(tagStr)
  if (filterTag.value && tag !== filterTag.value) return false
  if (filterSemester.value && semester !== filterSemester.value) return false
  return true
}

const combinedItems = computed(() => {
  // 收集所有已被归类（题目/答案/词单）的源文件名，用于过滤资料中的重复项
  const classifiedFiles = new Set()
  for (const p of rawProblems.value) {
    if (p.source_file) classifiedFiles.add(p.source_file)
  }
  for (const a of rawAnswers.value) {
    if (a.source_file) classifiedFiles.add(a.source_file)
  }
  for (const w of rawWords.value) {
    if (w.filename) classifiedFiles.add(w.filename)
  }

  const items = []
  for (const m of rawMaterials.value) {
    if (!matchesFilter(m.tag || m.time)) continue
    if (classifiedFiles.has(m.filename)) continue
    const ft = m.file_type
    const typeLabel = ft === 'pdf' ? 'PDF' : ft === 'docx' ? 'Word' : ft === 'image' || ft === 'jpg' || ft === 'png' ? '图片' : ft || ''
    items.push({
      _uid: 'mat_' + m.id,
      type: '资料',
      displayName: m.filename || '未命名',
      meta: `${typeLabel} · ${m.tag || '未分类'} · ${formatTime(m.created_at)}`,
      created_at: m.created_at,
      _clickable: true,
      _matId: m.id,
      _matHasText: m.has_text,
      _matFileType: m.file_type,
      _deleteType: 'material',
      _deleteId: m.id,
    })
  }
  // 题目按源文件分组
  const probGroups = {}
  for (const p of rawProblems.value) {
    if (!matchesFilter(p.exam)) continue
    const key = p.source_file || p.filename || p.id
    if (!probGroups[key]) {
      probGroups[key] = { filename: p.filename || key, exam: p.exam || '未分类', created_at: p.created_at, ids: [], count: 0 }
    }
    probGroups[key].ids.push(p.id)
    probGroups[key].count++
  }
  for (const key in probGroups) {
    const g = probGroups[key]
    items.push({
      _uid: 'prob_group_' + key,
      type: '题目',
      displayName: g.filename,
      meta: `${g.exam} · ${g.count} 题 · 上传 ${formatTime(g.created_at)}`,
      created_at: g.created_at,
      _clickable: true,
      _sourceFile: key,
      _docType: '题目',
      _deleteType: 'problem',
      _deleteIds: g.ids,
    })
  }
  // 答案按源文件分组
  const ansGroups = {}
  for (const a of rawAnswers.value) {
    if (!matchesFilter(a.tag)) continue
    const key = a.source_file || a.filename || a.id
    if (!ansGroups[key]) {
      ansGroups[key] = { filename: a.filename || key, tag: a.tag || '未分类', created_at: a.created_at, ids: [], count: 0 }
    }
    ansGroups[key].ids.push(a.id)
    ansGroups[key].count++
  }
  for (const key in ansGroups) {
    const g = ansGroups[key]
    items.push({
      _uid: 'ans_group_' + key,
      type: '答案',
      displayName: g.filename,
      meta: `${g.tag} · ${g.count} 条 · 上传 ${formatTime(g.created_at)}`,
      created_at: g.created_at,
      _clickable: true,
      _sourceFile: key,
      _docType: '答案',
      _deleteType: 'answer',
      _deleteIds: g.ids,
    })
  }
  // 词单
  for (const w of rawWords.value) {
    if (!matchesFilter(w.tag)) continue
    items.push({
      _uid: 'word_' + w.id,
      type: '词单',
      displayName: w.filename || '未命名',
      meta: `${w.tag || '未分类'} · ${w.word_count || 0} 词 · 上传 ${formatTime(w.created_at)}`,
      created_at: w.created_at,
      _clickable: true,
      _wordId: w.id,
      _wordCount: w.word_count || 0,
      _deleteType: 'word',
      _deleteId: w.id,
    })
  }
  items.sort((a, b) => {
    if (a.created_at && b.created_at) return b.created_at.localeCompare(a.created_at)
    return 0
  })
  return items
})

const filteredItems = computed(() => {
  let items = combinedItems.value
  if (keyword.value.trim()) {
    const kw = keyword.value.trim().toLowerCase()
    items = items.filter(item => item.displayName.toLowerCase().includes(kw))
  }
  return items
})

const groupedItems = computed(() => {
  const typeOrder = ['资料', '题目', '答案', '词单']
  const groups = {}
  for (const t of typeOrder) groups[t] = []
  for (const item of filteredItems.value) {
    if (groups[item.type]) groups[item.type].push(item)
  }
  return typeOrder.filter(t => groups[t].length).map(type => ({ type, items: groups[type] }))
})

const matchTitle = computed(() => {
  if (matchMode.value === 'word') return '匹配词单'
  if (matchMode.value === 'today') return '匹配今天上传'
  if (matchMode.value === 'selected') return `匹配选中（${matchSelectedFiles.value.length} 个文件）`
  return '匹配所有'
})

const visibleMatchLines = computed(() => {
  return matchLines.value.slice(-5)
})

function typeTagType(type) {
  if (type === '资料') return 'warning'
  if (type === '题目') return 'primary'
  if (type === '词单') return 'info'
  return 'success'
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function toggleSelect(item) {
  if (selectedUids.value.has(item._uid)) {
    selectedUids.value.delete(item._uid)
  } else {
    selectedUids.value.add(item._uid)
  }
}

function toggleSelectAll(checked) {
  if (checked) {
    for (const item of filteredItems.value) {
      if (item._deleteType) selectedUids.value.add(item._uid)
    }
  } else {
    selectedUids.value.clear()
  }
}

async function batchDelete() {
  if (selectedUids.value.size === 0) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedUids.value.size} 项？此操作不可恢复。`, '批量删除', { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' })
    const allMatIds = []
    const allProbIds = []
    const allAnsIds = []
    const allWordIds = []
    for (const uid of selectedUids.value) {
      const item = allItemsMap.value[uid]
      if (!item || !item._deleteType) continue
      if (item._deleteType === 'material') {
        allMatIds.push(item._deleteId)
      } else if (item._deleteType === 'problem') {
        allProbIds.push(...(item._deleteIds || []))
      } else if (item._deleteType === 'answer') {
        allAnsIds.push(...(item._deleteIds || []))
      } else if (item._deleteType === 'word') {
        allWordIds.push(item._deleteId)
      }
    }
    // 每种类型一个批量请求
    await Promise.allSettled([
      allMatIds.length ? Promise.allSettled(allMatIds.map(id => axios.delete(`/materials/${id}`).catch(() => {}))) : null,
      allProbIds.length ? axios.post('/problems/batch-delete', { ids: allProbIds }).catch(() => {}) : null,
      allAnsIds.length === 1 ? axios.delete(`/english-upload/answers/${allAnsIds[0]}`).catch(() => {}) : null,
      allAnsIds.length > 1 ? axios.post('/english-upload/answers/batch-delete', { ids: allAnsIds }).catch(() => {}) : null,
      allWordIds.length ? Promise.allSettled(allWordIds.map(id => axios.delete(`/english-upload/words/${id}`).catch(() => {}))) : null,
    ].filter(Boolean))
    selectedUids.value.clear()
    ElMessage.success('删除完成')
    await loadAll()
  } catch { /* cancelled */ }
}

async function loadTrash() {
  trashLoading.value = true
  try {
    const res = await axios.get('/library-trash')
    trashItems.value = res.data.items || []
  } catch {
    ElMessage.error('加载废纸篓失败')
  } finally {
    trashLoading.value = false
  }
}

async function restoreTrashItem(id) {
  try {
    await axios.post('/library-trash/restore', { ids: [id] })
    ElMessage.success('已恢复')
    await loadTrash()
    await loadAll()
  } catch {
    ElMessage.error('恢复失败')
  }
}

async function permanentDelete(id) {
  try {
    await ElMessageBox.confirm('确定永久删除？不可恢复。', '提示', { type: 'warning' })
    await axios.delete(`/library-trash/${id}`)
    ElMessage.success('已永久删除')
    await loadTrash()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function emptyTrash() {
  try {
    await ElMessageBox.confirm('确定清空废纸篓？所有项目将被永久删除，不可恢复。', '清空废纸篓', { type: 'warning', confirmButtonText: '清空', confirmButtonClass: 'el-button--danger' })
    await axios.post('/library-trash/empty')
    ElMessage.success('废纸篓已清空')
    trashItems.value = []
    await loadAll()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('清空失败')
  }
}

watch(showTrash, (val) => { if (val) loadTrash() })
watch(showMatchDialog, (val) => { if (val) loadMatchStatus() })
function scrollMatchLog() {
  nextTick(() => {
    const el = matchLogRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
watch(matchLines, scrollMatchLog, { deep: true })
watch(streamingAiOutput, scrollMatchLog)

function openMatchModeDialog() {
  selectedMatchMode.value = 'today'
  showMatchModeDialog.value = true
}

function confirmMatchMode() {
  showMatchModeDialog.value = false
  openMatch(selectedMatchMode.value)
}

function openMatch(mode) {
  matchMode.value = mode
  showMatchDialog.value = true
}

function matchSelected() {
  const files = new Set()
  for (const uid of selectedUids.value) {
    const item = allItemsMap.value[uid]
    if (!item) continue
    if (item._sourceFile) files.add(item._sourceFile)
    if (item.type === '资料' && item.displayName) files.add(item.displayName)
  }
  if (files.size === 0) {
    ElMessage.warning('请选择要匹配的文档')
    return
  }
  matchMode.value = 'selected'
  matchSelectedFiles.value = [...files]
  showMatchDialog.value = true
}

async function loadMatchStatus() {
  try {
    const res = await axios.get('/match-answers/status')
    matchStatus.value = res.data
  } catch {}
}

async function runMatch() {
  matchRunning.value = true
  matchCancelled.value = false
  matchProgress.value = '正在连接...'
  matchLines.value = []
  matchLineId = 0
  matchAbortController = new AbortController()
  try {
    const res = await fetch('/api/match-answers/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: matchMode.value,
        source_files: matchMode.value === 'selected' ? matchSelectedFiles.value : [],
        force: matchForce.value,
      }),
      credentials: 'include',
      signal: matchAbortController.signal,
    })
    if (!res.ok) {
      let detail = '匹配失败'
      try { detail = (await res.json()).detail || detail } catch {}
      matchProgress.value = '❌ ' + detail
      if (detail.includes('API Key')) {
        matchLines.value.push({ id: ++matchLineId, text: '请先在「设置」中配置 DeepSeek API Key' })
      }
      return
    }
    const reader = res.body.getReader()
    const { resultData, hasError } = await consumeMatchStream(reader, {
      onText: (msg) => {
        matchProgress.value = msg.text
        matchLines.value.push({ id: ++matchLineId, text: msg.text })
      },
      onAiTokenReset: (msg) => {
        streamingAiOutput.value = ''
        streamingAiPair.value = msg.pair_idx
      },
      onAiToken: (msg) => {
        streamingAiOutput.value += msg.text
      },
      onAiTokenDone: (msg) => {
        if (streamingAiOutput.value) {
          matchLines.value.push({ id: ++matchLineId, text: streamingAiOutput.value.slice(0, 200) + (streamingAiOutput.value.length > 200 ? '...' : '') })
          streamingAiOutput.value = ''
        }
        streamingAiPair.value = -1
      },
      onResult: (msg) => {
        matchProgress.value = `✅ 匹配成功：${msg.matched} 条对应关系（${msg.file_pairs} 对文件）`
        // 立即更新匹配统计
        matchStatus.value = {
          ...matchStatus.value,
          matched_problems: matchStatus.value.matched_problems + (msg.matched || 0),
          matched_answers: matchStatus.value.matched_answers + (msg.matched || 0),
          matched_files: matchStatus.value.matched_files + (msg.file_pairs || 0),
        }
      },
      onError: (msg) => {
        matchProgress.value = '❌ ' + msg.text
        matchLines.value.push({ id: ++matchLineId, text: '❌ ' + msg.text })
      },
    })
    if (matchCancelled.value) {
      matchProgress.value = '⏹ 已取消'
    } else if (hasError && !resultData) {
      // already set
    } else if (!resultData) {
      matchProgress.value = '⚠ 匹配完成，但未返回结果数据'
    }
    matchSelectedFiles.value = []
    await loadAll()
    // 等待后端写入完成后再刷新统计
    await new Promise(r => setTimeout(r, 500))
    await loadMatchStatus()
  } catch (e) {
    if (e.name === 'AbortError' || matchCancelled.value) {
      matchProgress.value = '⏹ 已取消'
    } else {
      matchProgress.value = '❌ ' + (e.message || '匹配失败')
    }
  } finally {
    matchRunning.value = false
    matchAbortController = null
  }
}

function cancelMatch() {
  matchCancelled.value = true
  matchProgress.value = '正在取消...'
  if (matchAbortController) {
    matchAbortController.abort()
    matchAbortController = null
  }
}

async function consumeMatchStream(reader, handlers) {
  const decoder = new TextDecoder()
  let buffer = ''
  let resultData = null
  let hasError = false
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
        if (msg.type === 'text') {
          handlers.onText?.(msg)
        } else if (msg.type === 'ai_token_reset') {
          handlers.onAiTokenReset?.(msg)
        } else if (msg.type === 'ai_token') {
          handlers.onAiToken?.(msg)
        } else if (msg.type === 'ai_token_done') {
          handlers.onAiTokenDone?.(msg)
        } else if (msg.type === 'result') {
          resultData = msg
          handlers.onResult?.(msg)
        } else if (msg.type === 'error') {
          hasError = true
          handlers.onError?.(msg)
        }
      } catch {}
    }
  }
  return { resultData, hasError }
}

async function runWordMatch() {
  matchMode.value = 'word'
  showMatchDialog.value = true
  matchRunning.value = true
  matchCancelled.value = false
  matchProgress.value = '正在连接...'
  matchLines.value = []
  matchLineId = 0
  streamingAiOutput.value = ''
  streamingAiPair.value = -1
  try {
    const res = await fetch('/api/match-answers/run-word-match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      credentials: 'include',
    })
    if (!res.ok) {
      matchProgress.value = '❌ 请求失败'
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
          if (msg.type === 'text') {
            matchProgress.value = msg.text
            matchLines.value.push({ id: ++matchLineId, text: msg.text })
          } else if (msg.type === 'result') {
            resultData = msg
            matchProgress.value = `✅ 词单匹配完成：${msg.matched} 对`
          } else if (msg.type === 'error') {
            matchProgress.value = '❌ ' + msg.text
            matchLines.value.push({ id: ++matchLineId, text: '❌ ' + msg.text })
          }
        } catch {}
      }
    }
    if (!resultData) {
      matchProgress.value = '⚠ 未返回结果'
    }
    await loadAll()
  } catch (e) {
    matchProgress.value = '❌ ' + (e.message || '匹配失败')
  } finally {
    matchRunning.value = false
  }
}

async function resetMatches() {
  try {
    await axios.post('/match-answers/reset')
    ElMessage.success('已清空对应关系')
    matchStatus.value = { total_problems: 0, matched_problems: 0, total_answers: 0, matched_answers: 0, matched_files: 0, today_problems: 0, today_answers: 0 }
    matchProgress.value = ''
    await loadAll()
  } catch {
    ElMessage.error('清空失败')
  }
}

const allItemsMap = computed(() => {
  const map = {}
  for (const item of combinedItems.value) {
    map[item._uid] = item
  }
  return map
})

function openItem(item) {
  if (item.type === '资料') {
    previewMaterialId.value = item._matId
    previewFileType.value = item._matFileType || ''
    previewFileName.value = item.displayName || ''
    previewVisible.value = true
    previewText.value = ''
    previewError.value = ''
    loadPreview(item._matId)
  } else if (item.type === '题目' || item.type === '答案') {
    if (item._sourceFile) {
      router.push(`/english/doc/${encodeURIComponent(item._sourceFile)}?type=${item._docType}`)
    }
  } else if (item.type === '词单') {
    if (item._wordId) {
      router.push(`/english/doc/${encodeURIComponent(item._wordId)}?type=词单`)
    }
  }
}

async function loadPreview(id) {
  previewLoading.value = true
  previewError.value = ''
  previewText.value = ''
  previewHtml.value = ''
  previewIsHtml.value = false
  try {
    const ft2 = (previewFileType.value || '').toLowerCase()

    if (['jpg','jpeg','png','image'].includes(ft2)) {
      const fileUrl = `/api/materials/${encodeURIComponent(id)}/file`
      previewHtml.value = `<img src="${fileUrl}" style="max-width:100%;display:block;">`
      previewIsHtml.value = true
      return
    }
    if (ft2 === 'pdf') {
      const fileUrl = `/api/materials/${encodeURIComponent(id)}/file`
      previewHtml.value = `<iframe src="${fileUrl}" style="width:100%;height:65vh;border:none;"></iframe>`
      previewIsHtml.value = true
      return
    }
    if (ft2 === 'docx') {
      const r = await axios.get(`/materials/${id}/text`)
      const text = r.data.text || ''
      if (text) {
        previewText.value = text
      } else {
        previewError.value = '该文档未提取到文字内容。'
      }
      return
    }
    const r = await axios.get(`/materials/${id}/text`)
    const text = r.data.text || ''
    if (text) {
      previewText.value = text
    } else {
      previewError.value = '该资料未提取到文字内容。'
    }
  } catch (e) {
    previewError.value = '加载失败'
  } finally {
    previewLoading.value = false
  }
}// 文档对应
watch(showDocPairing, (val) => { if (val) loadDocPairing() })

async function loadDocPairing() {
  docPairing.value.loading = true
  try {
    const res = await axios.get('/match-answers/unmatched-files')
    docPairing.value.unmatchedProbFiles = res.data.problem_files || []
    docPairing.value.unmatchedAnsFiles = res.data.answer_files || []
    docPairing.value.pairs = res.data.pairs || []
    docPairing.value.probFile = ''
    docPairing.value.ansFile = ''
    docPairing.value.wordStudentFiles = res.data.word_student_files || []
    docPairing.value.wordTeacherFiles = res.data.word_teacher_files || []
    docPairing.value.wordPairs = res.data.word_pairs || []
    docPairing.value.wordStudentFile = ''
    docPairing.value.wordTeacherFile = ''
  } catch {
    ElMessage.error('加载文件列表失败')
  } finally {
    docPairing.value.loading = false
  }
}

async function saveDocPair(runAiMatch) {
  if (!docPairing.value.probFile || !docPairing.value.ansFile) return

  if (runAiMatch) {
    docPairing.value.matching = true
    let streamResult = null
    try {
      matchMode.value = 'selected'
      matchSelectedFiles.value = [docPairing.value.probFile, docPairing.value.ansFile]
      showMatchDialog.value = true
      matchRunning.value = true
      matchCancelled.value = false
      matchProgress.value = '正在连接...'
      matchLines.value = []
      matchLineId = 0
      streamingAiOutput.value = ''
      streamingAiPair.value = -1
      matchAbortController = new AbortController()

      const res = await fetch('/api/match-answers/file-pairs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          problem_filename: docPairing.value.probFile,
          answer_filename: docPairing.value.ansFile,
          run_match: true,
        }),
        credentials: 'include',
        signal: matchAbortController.signal,
      })
      if (!res.ok) {
        let detail = '匹配失败'
        try { detail = (await res.json()).detail || detail } catch {}
        matchProgress.value = '❌ ' + detail
        if (detail.includes('API Key')) {
          matchLines.value.push({ id: ++matchLineId, text: '请先在“设置”中配置 DeepSeek API Key' })
        }
      } else {
        streamResult = await consumeMatchStream(res.body.getReader(), {
          onText: (msg) => {
            matchProgress.value = msg.text
            matchLines.value.push({ id: ++matchLineId, text: msg.text })
          },
          onAiTokenReset: (msg) => {
            streamingAiOutput.value = ''
            streamingAiPair.value = msg.pair_idx
          },
          onAiToken: (msg) => {
            streamingAiOutput.value += msg.text
          },
          onAiTokenDone: (msg) => {
            if (streamingAiOutput.value) {
              matchLines.value.push({ id: ++matchLineId, text: streamingAiOutput.value.slice(0, 200) + (streamingAiOutput.value.length > 200 ? '...' : '') })
              streamingAiOutput.value = ''
            }
            streamingAiPair.value = -1
          },
          onResult: (msg) => {
            matchProgress.value = '✅ 匹配成功：' + msg.matched + ' 条对应关系'
            matchStatus.value = {
              ...matchStatus.value,
              matched_problems: matchStatus.value.matched_problems + (msg.matched || 0),
              matched_answers: matchStatus.value.matched_answers + (msg.matched || 0),
              matched_files: matchStatus.value.matched_files + (msg.file_pairs || 0),
            }
          },
          onError: (msg) => {
            matchProgress.value = '❌ ' + msg.text
            matchLines.value.push({ id: ++matchLineId, text: '❌ ' + msg.text })
          },
        })
        const { resultData, hasError } = streamResult
        if (matchCancelled.value) {
          matchProgress.value = '⏹ 已取消'
        } else if (hasError && !resultData) {
        } else if (!resultData) {
          matchProgress.value = '⚠ 匹配完成，但未返回结果数据'
        }
        if (resultData) {
          ElMessage.success('对应完成：' + resultData.matched + ' 条匹配')
        }
      }
    } catch (e) {
      if (e.name === 'AbortError' || matchCancelled.value) {
        matchProgress.value = '⏹ 已取消'
      } else {
        matchProgress.value = '❌ ' + (e.message || '匹配失败')
        ElMessage.error(e.message || '操作失败')
      }
    } finally {
      docPairing.value.matching = false
      matchRunning.value = false
      matchAbortController = null
    }
  } else {
    try {
      await axios.post('/match-answers/file-pairs', {
        problem_filename: docPairing.value.probFile,
        answer_filename: docPairing.value.ansFile,
      })
      ElMessage.success('文件对应已保存')
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '保存失败')
    }
  }

  await loadDocPairing()
  await loadAll()
  await loadMatchStatus()
}

async function deleteDocPair(pair) {
  try {
    await axios.delete('/match-answers/file-pairs', {
      data: {
        problem_filename: pair.actual_problem_file || pair.problem_file,
        answer_filename: pair.actual_answer_file || pair.answer_file,
      }
    })
    ElMessage.success('已取消对应')
    await loadDocPairing()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function saveWordPair() {
  if (!docPairing.value.wordStudentFile || !docPairing.value.wordTeacherFile) return
  try {
    await axios.post('/match-answers/word-match-manual', {
      student_word_id: docPairing.value.wordStudentFile,
      teacher_word_id: docPairing.value.wordTeacherFile,
    })
    ElMessage.success('词单对应已保存')
    await loadDocPairing()
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function deleteWordPair(pair) {
  try {
    await axios.delete('/match-answers/word-match-manual', {
      data: { student_word_id: pair.student_word_id }
    })
    ElMessage.success('已取消词单对应')
    await loadDocPairing()
    await loadAll()
  } catch {
    ElMessage.error('操作失败')
  }
}

function buildDocViewerUrl(fileId, fileType, fileName, extra) {
  const base = `${window.location.origin}${window.location.pathname}#/document-viewer`
  const params = new URLSearchParams({
    fileId: fileId || previewMaterialId.value,
    fileType: fileType || previewFileType.value,
    fileName: fileName || previewFileName.value,
  })
  if (extra) Object.entries(extra).forEach(([k, v]) => { if (v) params.set(k, v) })
  return `${base}?${params.toString()}`
}

function getFileUrl(id) {
  return `/api/materials/${encodeURIComponent(id || previewMaterialId.value)}/file`
}

function printDocument() {
  const id = previewMaterialId.value
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

function solveWithMaterial() {
  previewVisible.value = false
  sessionStorage.setItem('solveMaterials', JSON.stringify({
    materialIds: [previewMaterialId.value],
  }))
  router.push('/english/solve')
}

// 调整类型
function showAdjustType(item) {
  let fileId = ''
  if (item.type === '题目' && item._sourceFile) {
    const p = rawProblems.value.find(p => (p.source_file || p.filename) === item._sourceFile)
    fileId = p?.upload_file_id || ''
  } else if (item.type === '答案' && item._sourceFile) {
    const a = rawAnswers.value.find(a => (a.source_file || a.filename) === item._sourceFile)
    fileId = a?.upload_file_id || ''
  } else if (item.type === '资料' && item._matId) {
    const m = rawMaterials.value.find(m => m.id === item._matId)
    fileId = m?.id || ''
  }
  adjustDialog.value = {
    visible: true,
    filename: item.displayName,
    sourceFile: item.displayName,
    currentType: item.type,
    targetType: '',
    loading: false,
    fileId: fileId,
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
      })
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '请求失败')
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let done = false
    let buffer = ''
    while (!done) {
      const { value, done: d } = await reader.read()
      done = d
      if (value) buffer += decoder.decode(value, { stream: !done })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') { done = true; break }
        try {
          const msg = JSON.parse(data)
          if (msg.type === 'text' || msg.type === 'ai_token') {
            adjustDialog.value.resultMsg += msg.text
          } else if (msg.type === 'result') {
            adjustDialog.value.resultMsg += `\n✅ ${msg.message}`
            ElMessage.success(msg.message)
          } else if (msg.type === 'error') {
            adjustDialog.value.resultMsg += `\n❌ ${msg.text}`
            ElMessage.error(msg.text)
          }
        } catch {}
      }
    }
    adjustDialog.value.visible = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.message || '调整失败')
  } finally {
    adjustDialog.value.loading = false
  }
}

// 手动对应
async function showManualMatch(item) {
  manualMatch.value = {
    visible: true,
    currentType: item.type,
    currentName: item.displayName,
    currentId: item._uid,
    currentFileItems: [],
    currentItemId: '',
    selectedId: '',
    loading: true,
    saving: false,
  }
  existingMatch.value = null
  unmatchedItems.value = []
  try {
    // 加载当前文件中的所有具体条目
    const srcFile = item._sourceFile
    if (item.type === '题目') {
      manualMatch.value.currentFileItems = rawProblems.value
        .filter(p => (p.source_file || p.filename) === srcFile)
        .map(p => ({ id: p.id, content: p.content || '' }))
    } else {
      manualMatch.value.currentFileItems = rawAnswers.value
        .filter(a => (a.source_file || a.filename) === srcFile)
        .map(a => ({ id: a.id, content: a.content || '' }))
    }
    const res = await axios.get('/match-answers/unmatched')
    if (item.type === '题目') {
      unmatchedItems.value = (res.data.answers || []).map(a => ({
        id: a.id, content: a.content || '',
      }))
    } else {
      unmatchedItems.value = (res.data.problems || []).map(p => ({
        id: p.id, content: p.content || '',
      }))
    }
  } catch {
    ElMessage.error('加载未匹配数据失败')
  } finally {
    manualMatch.value.loading = false
  }
}

async function createManualMatch() {
  if (!manualMatch.value.selectedId || !manualMatch.value.currentItemId) return
  manualMatch.value.saving = true
  try {
    const target = manualMatch.value.currentType === '题目'
      ? { problem_id: manualMatch.value.currentItemId, answer_id: manualMatch.value.selectedId }
      : { problem_id: manualMatch.value.selectedId, answer_id: manualMatch.value.currentItemId }
    await axios.post('/match-answers/manual-match', target)
    ElMessage.success('已创建 1 条对应关系')
    manualMatch.value.visible = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '对应失败')
  } finally {
    manualMatch.value.saving = false
  }
}

async function deleteManualMatch() {
  if (!existingMatch.value) return
  try {
    await axios.delete('/match-answers/manual-match', {
      data: {
        problem_id: existingMatch.value.problem_id,
        answer_id: existingMatch.value.answer_id,
      }
    })
    ElMessage.success('已取消对应')
    existingMatch.value = null
    manualMatch.value.selectedId = ''
    await loadAll()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function loadAll() {
  loading.value = true
  try {
    const [matRes, probRes, ansRes, wordRes] = await Promise.all([
      axios.get('/materials'),
      axios.get('/problems?page_size=5000'),
      axios.get('/english-upload/answers'),
      axios.get('/english-upload/words'),
    ])
    rawMaterials.value = (matRes.data.items || []).filter(m => m.subject === '英语' || !m.subject)
    rawProblems.value = (probRes.data.items || []).filter(p => p.subject === '英语')
    rawAnswers.value = ansRes.data.items || []
    rawWords.value = wordRes.data.items || []
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function deleteItem(item) {
  try {
    await ElMessageBox.confirm(`确定删除这条${item.type}？`, '提示', { type: 'warning' })
    const delIds = item._deleteIds || [item._deleteId]
    if (item._deleteType === 'problem' && delIds.length > 1) {
      await axios.post('/problems/batch-delete', { ids: delIds })
    } else if (item._deleteType === 'answer' && delIds.length > 1) {
      await axios.post('/english-upload/answers/batch-delete', { ids: delIds })
    } else {
      await Promise.allSettled(delIds.map(did => {
        if (item._deleteType === 'material') return axios.delete(`/materials/${did}`)
        if (item._deleteType === 'problem') return axios.delete(`/problems/${did}`)
        if (item._deleteType === 'answer') return axios.delete(`/english-upload/answers/${did}`)
        if (item._deleteType === 'word') return axios.delete(`/english-upload/words/${did}`)
      }))
    }
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  app.setActiveTab('资料')
  loadAll()
})
</script>

<style scoped>
.english-library-page {
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
.group-count {
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
.file-item.clickable {
  cursor: pointer;
}
.file-item.clickable:hover {
  background: #ecfdf5;
  border-color: #a7f3d0;
}
.file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.file-name {
  font-size: 13px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-meta {
  font-size: 11px;
  color: #94a3b8;
}
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #991b1b;
}
.file-item.selected {
  background: #ecfdf5;
  border-color: #a7f3d0;
}
.item-cb { margin-right: 4px; }
.preview-loading {
  padding: 40px;
  text-align: center;
  color: #94a3b8;
}
.preview-error {
  padding: 40px;
  text-align: center;
  color: #dc2626;
}
.trash-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 50vh;
  overflow-y: auto;
}
.trash-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 10px;
}
.trash-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.trash-name {
  font-size: 13px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trash-meta {
  font-size: 11px;
  color: #94a3b8;
}
.match-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #475569;
}
.match-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  background: #f0f9ff;
  border-radius: 8px;
  font-size: 13px;
  color: #2563eb;
}
.match-progress.match-done {
  background: #f0fdf4;
  color: #059669;
}
.match-progress.match-error {
  background: #fef2f2;
  color: #dc2626;
}
.stat-highlight {
  font-weight: 700;
  color: #059669;
}
.match-log {
  margin-top: 10px;
  padding: 8px 10px;
  background: #0f172a;
  border-radius: 8px;
  height: 110px;
  overflow-y: auto;
}
.match-log-line {
  font-size: 12px;
  line-height: 1.6;
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.streaming-line {
  color: #22d3ee;
  white-space: pre-wrap;
  word-break: break-all;
}
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

.preview-content {
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
  max-height: 60vh;
  overflow-y: auto;
  word-break: break-word;
}
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
.match-select-list { max-height: 350px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.match-select-item {
  padding: 10px 14px; border-radius: 8px; border: 1px solid #e2e8f0;
  cursor: pointer; transition: all 0.15s; background: #f8fafc;
}
.match-select-item:hover { border-color: #2563eb; background: #eff6ff; }
.match-select-item.selected { border-color: #2563eb; background: #dbeafe; }
.match-select-content { font-size: 13px; color: #334155; line-height: 1.5; }
.match-select-meta { font-size: 11px; color: #94a3b8; font-family: monospace; margin-top: 2px; }
.existing-match-info { margin-top: 12px; padding: 12px; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0; }

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .content {
    max-width: 100%;
    padding: 16px 12px;
  }
  .page-header {
    margin-bottom: 16px;
  }
  .page-title {
    font-size: 22px;
  }
  .page-subtitle {
    font-size: 13px;
  }
  .filter-bar {
    flex-wrap: wrap;
    gap: 8px;
  }
  .filter-bar .el-select,
  .filter-bar .el-input {
    width: 100% !important;
    max-width: 100%;
  }
  .tree-panel {
    padding: 16px;
  }
  .panel-header {
    flex-wrap: wrap;
    gap: 6px;
    font-size: 15px;
  }
  .batch-bar {
    flex-wrap: wrap;
    gap: 6px;
  }
  .file-item {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 10px;
  }
  .file-info {
    width: 100%;
  }
  .file-name {
    max-width: 100%;
  }
  .collapse-title {
    gap: 6px;
  }
  .trash-item {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 10px;
  }
  .match-stats {
    padding: 10px;
  }
  .match-select-item {
    padding: 8px 12px;
  }
  .match-select-content {
    font-size: 12px;
  }
  .preview-content {
    max-height: 50vh;
  }
  .preview-content h1 { font-size: 18px; }
  .preview-content h2 { font-size: 16px; }
  .preview-content h3 { font-size: 14px; }
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
