<template>
  <div class="workspace-page">
    <div class="page-header">
      <div>
        <h1>教师工作台</h1>
        <p>上传资料、按班型或班级分发、登记错题与完成情况。</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">班型</div>
          <div class="summary-value">{{ summary.class_type_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">班级</div>
          <div class="summary-value">{{ summary.class_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">分发记录</div>
          <div class="summary-value">{{ summary.distribution_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">覆盖学生</div>
          <div class="summary-value">{{ summary.student_total || 0 }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="page-grid">
      <section class="surface">
        <div class="surface-header">
          <h2>上传资料</h2>
          <span>支持多层标签路径，例如 `初一南外/周四下午/暑假讲义`</span>
        </div>
        <el-form label-position="top" class="upload-form">
          <el-form-item label="标签路径">
            <el-input v-model="uploadForm.tag" placeholder="初一南外/周四下午/暑假讲义" />
          </el-form-item>
          <el-form-item label="文件">
            <input
              ref="fileInputRef"
              type="file"
              accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
              @change="onFileChange"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :disabled="!uploadForm.file" :loading="uploading" @click="uploadMaterial">上传资料</el-button>
          </el-form-item>
        </el-form>
      </section>

      <section class="surface">
        <div class="surface-header">
          <h2>批量分发</h2>
          <span>先勾选资料，再选择班型或班级。</span>
        </div>
        <el-form label-position="top">
          <el-form-item label="分发范围">
            <el-radio-group v-model="distributionForm.targetType">
              <el-radio-button label="class">班级</el-radio-button>
              <el-radio-button label="class_type">班型</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="distributionForm.targetType === 'class' ? '选择班级' : '选择班型'">
            <el-select v-model="distributionForm.targetIds" multiple filterable style="width:100%">
              <el-option
                v-for="item in distributionOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="distributionForm.note" type="textarea" :rows="3" placeholder="例如：本周课堂讲义 + 课后订正" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :disabled="selectedMaterialIds.length === 0" @click="createDistribution">
              分发 {{ selectedMaterialIds.length }} 份资料
            </el-button>
          </el-form-item>
        </el-form>
      </section>
    </div>

    <section class="surface">
      <div class="surface-header">
        <h2>资料库</h2>
        <span>支持查看原文件、单份打印与批量打印。</span>
      </div>
      <div class="table-actions">
        <el-button size="small" @click="selectedTagPath = ''">查看全部</el-button>
        <el-button size="small" :disabled="selectedMaterialRows.length === 0" @click="batchPrint">批量打印</el-button>
      </div>
      <div class="materials-panel">
        <div class="tag-tree-panel">
          <div class="tree-title">标签目录</div>
          <el-tree
            :data="tagTree"
            node-key="path"
            default-expand-all
            :props="{ label: 'name', children: 'children' }"
            @node-click="handleTagNodeClick"
          >
            <template #default="{ data }">
              <div class="tree-node">
                <span>{{ data.name }}</span>
                <span class="tree-count">{{ data.count }}</span>
              </div>
            </template>
          </el-tree>
        </div>
        <div class="materials-table-panel">
          <div v-if="selectedTagPath" class="selected-path">当前标签：{{ selectedTagPath }}</div>
          <el-table :data="filteredMaterials" stripe @selection-change="onMaterialSelectionChange">
            <el-table-column type="selection" width="46" />
            <el-table-column prop="filename" label="文件名" min-width="260" />
            <el-table-column prop="tag" label="标签路径" min-width="220" />
            <el-table-column prop="created_at" label="上传时间" width="180">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button text size="small" @click="openDocument(row)">查看</el-button>
                <el-button text size="small" @click="printOne(row)">打印</el-button>
                <el-button text size="small" type="danger" @click="deleteMaterial(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </section>

    <section class="surface">
      <div class="surface-header">
        <h2>分发与统计</h2>
        <span>可登记已完成部分、标记错题，查看正确率与错误学生。</span>
      </div>
      <div class="table-actions">
        <el-button size="small" @click="exportMergedWrongBook">整合导出错题本</el-button>
        <el-button size="small" @click="exportMergedSummary">整合导出正确率总表</el-button>
      </div>
      <el-table :data="distributions" stripe>
        <el-table-column prop="assigned_at" label="分发时间" width="180">
          <template #default="{ row }">{{ formatTime(row.assigned_at) }}</template>
        </el-table-column>
        <el-table-column label="范围" min-width="180">
          <template #default="{ row }">{{ row.target_names?.join('、') || '-' }}</template>
        </el-table-column>
        <el-table-column label="资料数" width="90">
          <template #default="{ row }">{{ row.material_ids?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="学生数" width="90">
          <template #default="{ row }">{{ row.stats?.student_total || 0 }}</template>
        </el-table-column>
        <el-table-column label="错题登记" width="100">
          <template #default="{ row }">{{ row.stats?.wrong_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="完成记录" width="100">
          <template #default="{ row }">{{ row.stats?.completion_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="正确率总表" min-width="280">
          <template #default="{ row }">
            <div v-if="row.stats?.problem_stats?.length" class="problem-stats">
              <div v-for="item in row.stats.problem_stats.slice(0, 3)" :key="item.problem_ref">
                <div class="problem-line">
                  <span>{{ item.problem_ref }}：{{ (item.correct_rate * 100).toFixed(0) }}%，错 {{ item.wrong_students.join('、') || '-' }}</span>
                  <span class="problem-actions">
                    <el-button v-if="item.explanation" text size="small" @click="openExplanationDialog(row, item)">查看解析</el-button>
                    <el-button text size="small" :loading="explanationLoadingKey === explanationKey(row, item)" @click="generateExplanation(row, item, !!item.explanation)">
                      {{ item.explanation ? '重新生成' : '生成解析' }}
                    </el-button>
                  </span>
                </div>
              </div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="openCompletionDialog(row)">登记完成</el-button>
            <el-button text size="small" @click="openWrongDialog(row)">登记错题</el-button>
            <el-button text size="small" @click="openExportDialog(row)">导出错题</el-button>
            <el-button text size="small" @click="exportDistributionSummary(row)">导出总表</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="completionDialog.visible" title="登记完成情况" width="520px">
      <el-form label-position="top">
        <el-form-item label="学生姓名">
          <el-select v-model="completionDialog.studentName" filterable allow-create default-first-option style="width:100%">
            <el-option v-for="item in completionDialog.students" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="已完成部分">
          <el-input v-model="completionDialog.partsText" type="textarea" :rows="3" placeholder="例如：阅读 A、B；完形前 10 题" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="completionDialog.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completionDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitCompletion">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="wrongDialog.visible" title="登记错题本" width="520px">
      <el-form label-position="top">
        <el-form-item label="学生姓名">
          <el-select v-model="wrongDialog.studentName" filterable allow-create default-first-option style="width:100%">
            <el-option v-for="item in wrongDialog.students" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目标识/题干">
          <el-input v-model="wrongDialog.problemRef" placeholder="例如：阅读理解 2 / 讲义第 3 题，也可直接粘贴题干" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="wrongDialog.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="wrongDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitWrongBook">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog.visible" title="导出错题本" width="480px">
      <el-form label-position="top">
        <el-form-item label="导出范围">
          <el-radio-group v-model="exportDialog.mode">
            <el-radio-button label="all">当前分发全部学生</el-radio-button>
            <el-radio-button label="student">单个学生</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="exportDialog.mode === 'student'" label="学生姓名">
          <el-select v-model="exportDialog.studentName" filterable allow-create default-first-option style="width:100%">
            <el-option v-for="item in exportDialog.students" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitWrongBookExport">下载 CSV</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="explanationDialog.visible" title="AI 解析" width="640px">
      <div class="explanation-meta">
        <div>题目：{{ explanationDialog.problemRef }}</div>
        <div v-if="explanationDialog.model">模型：{{ explanationDialog.model }}</div>
        <div v-if="explanationDialog.generatedAt">生成时间：{{ formatTime(explanationDialog.generatedAt) }}</div>
      </div>
      <div class="explanation-content">{{ explanationDialog.content }}</div>
      <template #footer>
        <el-button @click="explanationDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const fileInputRef = ref(null)
const summary = ref({})
const classTypes = ref([])
const classes = ref([])
const materials = ref([])
const tagTree = ref([])
const distributions = ref([])
const uploading = ref(false)
const selectedMaterialRows = ref([])
const selectedTagPath = ref('')

const uploadForm = ref({
  tag: '',
  file: null,
})

const distributionForm = ref({
  targetType: 'class',
  targetIds: [],
  note: '',
})

const completionDialog = ref({
  visible: false,
  distributionId: '',
  students: [],
  studentName: '',
  partsText: '',
  note: '',
})

const wrongDialog = ref({
  visible: false,
  distributionId: '',
  students: [],
  studentName: '',
  problemRef: '',
  note: '',
})

const exportDialog = ref({
  visible: false,
  distributionId: '',
  students: [],
  mode: 'all',
  studentName: '',
})

const explanationDialog = ref({
  visible: false,
  problemRef: '',
  content: '',
  model: '',
  generatedAt: '',
})

const explanationLoadingKey = ref('')

const selectedMaterialIds = computed(() => selectedMaterialRows.value.map(item => item.id))
const distributionOptions = computed(() => (distributionForm.value.targetType === 'class' ? classes.value : classTypes.value))
const filteredMaterials = computed(() => {
  if (!selectedTagPath.value) return materials.value
  return materials.value.filter(item => (item.tag || '').startsWith(selectedTagPath.value))
})

function formatTime(value) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

function onFileChange(event) {
  const [file] = Array.from(event.target.files || [])
  uploadForm.value.file = file || null
}

function onMaterialSelectionChange(rows) {
  selectedMaterialRows.value = rows
}

async function loadAll() {
  const [summaryRes, classTypesRes, classesRes, materialsRes, tagTreeRes, distributionsRes] = await Promise.all([
    axios.get('/school/summary'),
    axios.get('/school/class-types'),
    axios.get('/school/classes'),
    axios.get('/materials'),
    axios.get('/materials/tag-tree'),
    axios.get('/school/distributions'),
  ])
  summary.value = summaryRes.data
  classTypes.value = classTypesRes.data.items || []
  classes.value = classesRes.data.items || []
  materials.value = (materialsRes.data.items || []).sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  tagTree.value = tagTreeRes.data.items || []
  distributions.value = distributionsRes.data.items || []
}

function handleTagNodeClick(node) {
  selectedTagPath.value = node.path || ''
}

async function uploadMaterial() {
  if (!uploadForm.value.file) return
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', uploadForm.value.file)
    form.append('subject', '英语')
    form.append('time', new Date().toISOString().slice(0, 10))
    form.append('tag', uploadForm.value.tag || '未分类')
    await axios.post('/materials', form)
    ElMessage.success('资料已上传')
    uploadForm.value.file = null
    if (fileInputRef.value) fileInputRef.value.value = ''
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function createDistribution() {
  try {
    await axios.post('/school/distributions', {
      material_ids: selectedMaterialIds.value,
      target_type: distributionForm.value.targetType,
      target_ids: distributionForm.value.targetIds,
      tag_path: uploadForm.value.tag || '',
      note: distributionForm.value.note,
    })
    ElMessage.success('分发成功')
    distributionForm.value.targetIds = []
    distributionForm.value.note = ''
    selectedMaterialRows.value = []
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '分发失败')
  }
}

function openDocument(row) {
  router.push({
    path: '/document-viewer',
    query: {
      fileId: row.id,
      fileType: row.file_type,
      fileName: encodeURIComponent(row.filename || ''),
    },
  })
}

function printOne(row) {
  window.open(`#/document-viewer?fileId=${row.id}&fileType=${row.file_type}&fileName=${encodeURIComponent(encodeURIComponent(row.filename || ''))}&action=print`, '_blank')
}

function batchPrint() {
  selectedMaterialRows.value.forEach(printOne)
}

function openExportDialog(row) {
  exportDialog.value = {
    visible: true,
    distributionId: row.id,
    students: row.students || [],
    mode: 'all',
    studentName: '',
  }
}

function downloadUrl(url) {
  window.open(url, '_blank', 'noopener')
}

function submitWrongBookExport() {
  const studentQuery = exportDialog.value.mode === 'student' && exportDialog.value.studentName
    ? `?student_name=${encodeURIComponent(exportDialog.value.studentName)}`
    : ''
  downloadUrl(`/api/school/distributions/${exportDialog.value.distributionId}/exports/wrong-book.csv${studentQuery}`)
  exportDialog.value.visible = false
}

function exportDistributionSummary(row) {
  downloadUrl(`/api/school/distributions/${row.id}/exports/correctness-summary.csv`)
}

function exportMergedWrongBook() {
  downloadUrl('/api/school/exports/wrong-book.csv')
}

function exportMergedSummary() {
  downloadUrl('/api/school/exports/correctness-summary.csv')
}

function explanationKey(row, item) {
  return `${row.id}:${item.problem_ref}`
}

function openExplanationDialog(row, item) {
  explanationDialog.value = {
    visible: true,
    problemRef: item.problem_ref,
    content: item.explanation || '',
    model: item.explanation_model || '',
    generatedAt: item.explanation_generated_at || '',
  }
}

async function generateExplanation(row, item, force = false) {
  const key = explanationKey(row, item)
  explanationLoadingKey.value = key
  try {
    const res = await axios.post(`/school/distributions/${row.id}/explanations`, {
      problem_ref: item.problem_ref,
      force,
    })
    ElMessage.success(res.data.message || 'AI 解析已生成')
    await loadAll()
    explanationDialog.value = {
      visible: true,
      problemRef: item.problem_ref,
      content: res.data.explanation?.content || '',
      model: res.data.explanation?.model || '',
      generatedAt: res.data.explanation?.generated_at || '',
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '生成解析失败')
  } finally {
    explanationLoadingKey.value = ''
  }
}

async function deleteMaterial(row) {
  try {
    await ElMessageBox.confirm(`确定删除资料「${row.filename}」？`, '提示', { type: 'warning' })
    await axios.delete(`/materials/${row.id}`)
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

function openCompletionDialog(row) {
  completionDialog.value = {
    visible: true,
    distributionId: row.id,
    students: row.students || [],
    studentName: '',
    partsText: '',
    note: '',
  }
}

function openWrongDialog(row) {
  wrongDialog.value = {
    visible: true,
    distributionId: row.id,
    students: row.students || [],
    studentName: '',
    problemRef: '',
    note: '',
  }
}

async function submitCompletion() {
  try {
    await axios.post(`/school/distributions/${completionDialog.value.distributionId}/completion`, {
      student_name: completionDialog.value.studentName,
      completed_parts: completionDialog.value.partsText.split(/[，,\n]/).map(item => item.trim()).filter(Boolean),
      note: completionDialog.value.note,
    })
    ElMessage.success('已登记完成情况')
    completionDialog.value.visible = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function submitWrongBook() {
  try {
    await axios.post(`/school/distributions/${wrongDialog.value.distributionId}/wrong-book`, {
      student_name: wrongDialog.value.studentName,
      problem_ref: wrongDialog.value.problemRef,
      note: wrongDialog.value.note,
    })
    ElMessage.success('已登记错题本')
    wrongDialog.value.visible = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.workspace-page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header,
.surface-header,
.table-actions {
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
.summary-row {
  margin-bottom: 0;
}
.summary-panel,
.surface {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 18px;
}
.summary-label {
  color: #64748b;
  font-size: 13px;
}
.summary-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 700;
  color: #0f172a;
}
.page-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.materials-panel {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
}
.tag-tree-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  max-height: 520px;
  overflow: auto;
}
.materials-table-panel {
  min-width: 0;
}
.tree-title,
.selected-path {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 10px;
}
.tree-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.tree-count {
  color: #94a3b8;
  font-size: 12px;
}
.upload-form {
  margin-top: 12px;
}
.problem-stats {
  font-size: 12px;
  line-height: 1.6;
}
.problem-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 0;
}
.problem-actions {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  gap: 4px;
}
.explanation-meta {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  color: #64748b;
  font-size: 13px;
}
.explanation-content {
  white-space: pre-wrap;
  line-height: 1.8;
  color: #0f172a;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
}
@media (max-width: 960px) {
  .page-grid {
    grid-template-columns: 1fr;
  }
  .materials-panel {
    grid-template-columns: 1fr;
  }
}
</style>
