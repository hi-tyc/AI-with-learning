<template>
  <div class="manage-page">
    <div class="content">
      <h1 class="page-title">管理题目</h1>
      <p class="page-subtitle">像文件资源管理器一样管理你的题目</p>

      <el-row :gutter="16" class="main-row">
        <!-- 左侧目录树 -->
        <el-col :span="7">
          <el-card shadow="hover" class="tree-card">
            <template #header>
              <div class="card-header">
                <el-icon><Folder /></el-icon>
                <span>目录</span>
                <div class="header-actions">
                  <el-button text size="small" @click="createFolder">
                    <el-icon><Plus /></el-icon><span>新建</span>
                  </el-button>
                  <el-button text size="small" @click="refreshData">
                    <el-icon><Refresh /></el-icon>
                  </el-button>
                </div>
              </div>
            </template>

            <el-tree
              ref="treeRef"
              :data="treeData"
              :props="{ label: 'name', children: 'children' }"
              node-key="path"
              highlight-current
              @node-click="onNodeClick"
              @node-contextmenu="onContextMenu"
            >
              <template #default="{ node, data }">
                <span class="tree-node-label">
                  <el-icon v-if="data.is_leaf"><Document /></el-icon>
                  <el-icon v-else><FolderOpened /></el-icon>
                  <span class="node-name">{{ data.name }}</span>
                  <span v-if="data.count" class="node-count">({{ data.count }})</span>
                </span>
              </template>
            </el-tree>
          </el-card>
        </el-col>

        <!-- 右侧题目列表 -->
        <el-col :span="17">
          <el-card shadow="hover" class="list-card">
            <template #header>
              <div class="card-header">
                <el-icon><List /></el-icon>
                <span>{{ currentFolderName || '全部题目' }}</span>
                <span class="header-count">{{ filteredProblems.length }} 题</span>
                <div class="header-actions">
                  <el-input v-model="searchKeyword" placeholder="搜索题目..." clearable prefix-icon="Search" size="small" style="width:180px;margin-right:8px" @keyup.enter="searchProblems" />
                  <el-button type="primary" size="small" @click="showAddDialog = true">
                    <el-icon><Plus /></el-icon><span>添加题目</span>
                  </el-button>
                </div>
              </div>
            </template>

            <div v-if="selectedIds.length > 0" class="batch-bar">
              <span class="batch-count">已选 {{ selectedIds.length }} 题</span>
              <el-button size="small" type="danger" @click="batchDelete"><el-icon><Delete /></el-icon> 批量删除</el-button>
              <el-button size="small" @click="selectedIds = []">取消选择</el-button>
            </div>

            <el-empty v-if="filteredProblems.length === 0" description="该文件夹下暂无题目" />

            <div v-else class="problem-list">
              <div
                v-for="p in filteredProblems"
                :key="p.id"
                class="problem-item"
                @click="goSolve(p)"
              >
                <div class="item-header">
                  <el-tag :type="subjectType(p.subject)" size="small">{{ p.subject }}</el-tag>
                  <span v-if="p.solved_at" class="solved-tag">在会话中查看</span>
                  <span v-else class="unsolved-tag">未解答</span>
                  <span class="item-id">#{{ p.id }}</span>
                </div>
                <div class="item-content" v-html="renderMath(p.content)"></div>
                <div v-if="p.image_file_id" class="item-thumb">
                  <el-image
                    :src="`/data/uploads/${p.image_file_id}_compressed.jpg`"
                    fit="contain"
                    style="max-width:200px;max-height:120px"
                    :preview-src-list="[`/data/uploads/${p.image_file_id}_compressed.jpg`]"
                    preview-teleported
                  />
                </div>
                <div class="item-meta">
                  <span v-if="p.exam" class="meta-tag">{{ p.exam }}</span>
                  <span v-if="p.source" class="meta-tag">{{ p.source }}</span>
                  <span v-if="p.school" class="meta-tag">{{ p.school }}</span>
                </div>
                <div class="item-footer">
                  <el-checkbox v-model="selectedIds" :label="p.id" @click.stop class="batch-checkbox" />
                  <span v-if="p.knowledge_point" class="item-tags">
                    <el-tag v-for="tag in parseTags(p.knowledge_point)" :key="tag" size="small" effect="plain">
                      {{ tag }}
                    </el-tag>
                  </span>
                  <el-button-group>
                    <el-button size="small" text @click.stop="editProblem(p)">
                      <el-icon><Edit /></el-icon>
                    </el-button>
                    <el-button size="small" text type="danger" @click.stop="deleteProblem(p.id)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </el-button-group>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 废纸篓 -->
      <el-card shadow="hover" class="tree-card" style="margin-top:16px">
        <template #header>
          <div class="card-header">
            <el-icon><Delete /></el-icon>
            <span>废纸篓 ({{ trashItems.length }})</span>
            <div class="header-actions">
              <el-button v-if="trashItems.length" text size="small" type="danger" @click="emptyTrash">
                <el-icon><Delete /></el-icon><span>清空</span>
              </el-button>
              <el-button text size="small" @click="toggleTrash">
                <el-icon><component :is="showTrash ? ArrowUp : ArrowDown" /></el-icon>
              </el-button>
            </div>
          </div>
        </template>
        <div v-if="showTrash">
          <el-empty v-if="!trashItems.length" description="废纸篓为空" />
          <div v-else class="problem-list" style="max-height:300px">
            <div v-for="p in trashItems" :key="p.id" class="problem-item" @click="goSolve(p)">
              <div class="item-content" v-html="renderMath(p.content)"></div>
              <el-button size="small" text type="primary" @click.stop="restoreProblem(p.id)">
                <el-icon><Refresh /></el-icon> 恢复
              </el-button>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 添加题目弹窗 -->
    <el-dialog v-model="showAddDialog" title="添加题目" width="700px">
      <el-form :model="addForm" label-position="top">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="学科">
              <el-select v-model="addForm.subject" style="width:100%">
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
          <el-col :span="8">
            <el-form-item label="考试">
              <el-input v-model="addForm.exam" placeholder="如：期中/期末" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="来源">
              <el-input v-model="addForm.source" placeholder="如：练习册/试卷" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="学校">
              <el-input v-model="addForm.school" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="大题">
              <el-input v-model="addForm.big_question" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="小题">
              <el-input v-model="addForm.small_question" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="题目内容">
          <el-input v-model="addForm.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="知识点">
          <el-input v-model="addForm.knowledge_point" placeholder="多个用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="doAddProblem">添加</el-button>
      </template>
    </el-dialog>

    <!-- 编辑题目弹窗 -->
    <el-dialog v-model="editDialog" title="编辑题目" width="700px">
      <el-form :model="editForm" label-position="top">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="学科">
              <el-select v-model="editForm.subject" style="width:100%">
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
          <el-col :span="8">
            <el-form-item label="考试">
              <el-input v-model="editForm.exam" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="来源">
              <el-input v-model="editForm.source" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="学校">
              <el-input v-model="editForm.school" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="大题">
              <el-input v-model="editForm.big_question" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="小题">
              <el-input v-model="editForm.small_question" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="题目内容">
          <el-input v-model="editForm.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="知识点">
          <el-input v-model="editForm.knowledge_point" placeholder="多个用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建文件夹弹窗 -->
    <el-dialog v-model="showFolderDialog" title="新建文件夹" width="400px">
      <el-form :model="folderForm" label-position="top">
        <el-form-item label="文件夹名称">
          <el-input v-model="folderForm.name" placeholder="请输入文件夹名称" />
        </el-form-item>
        <el-form-item label="位置">
          <el-select v-model="folderForm.parent" style="width:100%">
            <el-option label="根目录" value="" />
            <el-option
              v-for="folder in allFolders"
              :key="folder.path"
              :label="folder.name"
              :value="folder.path"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFolderDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreateFolder">创建</el-button>
      </template>
    </el-dialog>

    <!-- 右键菜单 -->
    <el-dialog v-model="showRenameDialog" title="重命名" width="400px">
      <el-form label-position="top">
        <el-form-item label="新名称">
          <el-input v-model="renameForm.name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="doRename">重命名</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Folder, FolderOpened, Document, List, Refresh, Edit, Delete, Plus, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { renderMath } from '../utils/mathRender'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

const problems = ref([])
const treeRef = ref(null)
const currentPath = ref('')
const showAddDialog = ref(false)
const showFolderDialog = ref(false)
const showRenameDialog = ref(false)
const selectedIds = ref([])
const showTrash = ref(false)
const trashItems = ref([])

const addForm = ref({
  subject: '数学',
  exam: '',
  source: '',
  school: '',
  big_question: '',
  small_question: '',
  content: '',
  knowledge_point: '',
})

const editDialog = ref(false)
const editForm = ref({
  id: '',
  subject: '',
  exam: '',
  source: '',
  school: '',
  big_question: '',
  small_question: '',
  content: '',
  knowledge_point: '',
})

const folderForm = ref({
  name: '',
  parent: '',
})

const renameForm = ref({
  path: '',
  name: '',
})

const allFolders = computed(() => {
  const folders = []
  function collect(node, path) {
    for (const child of node.children || []) {
      if (!child.is_leaf) {
        const childPath = path ? `${path}/${child.name}` : child.name
        folders.push({ name: childPath, path: childPath })
        collect(child, childPath)
      }
    }
  }
  for (const root of treeData.value) {
    collect(root, '')
  }
  return folders
})

// 构建目录树
const treeData = computed(() => {
  const root = { name: '全部题目', path: '', children: [], count: problems.value.length }

  for (const p of problems.value) {
    const parts = []
    if (p.subject) parts.push(p.subject)
    if (p.exam) parts.push(p.exam)
    if (p.source) parts.push(p.source)
    if (p.school) parts.push(p.school)
    if (p.big_question) parts.push(p.big_question)

    if (parts.length === 0) {
      // 未分类
      let other = root.children.find(c => c.name === '未分类')
      if (!other) {
        other = { name: '未分类', path: '未分类', children: [], count: 0 }
        root.children.push(other)
      }
      other.count = (other.count || 0) + 1
      continue
    }

    let current = root
    let currentPath = ''
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      currentPath = currentPath ? `${currentPath}/${part}` : part
      let child = current.children.find(c => c.name === part)
      if (!child) {
        child = {
          name: part,
          path: currentPath,
          children: [],
          count: 0,
        }
        current.children.push(child)
      }
      child.count = (child.count || 0) + 1
      current = child
    }
  }

  return [root]
})

const currentFolderName = computed(() => {
  if (!currentPath.value) return ''
  return currentPath.value.split('/').pop()
})

const filteredProblems = computed(() => {
  const base = problems.value.filter(p => !p.is_placeholder)
  if (!currentPath.value) return base
  return base.filter(p => {
    const parts = []
    if (p.subject) parts.push(p.subject)
    if (p.exam) parts.push(p.exam)
    if (p.source) parts.push(p.source)
    if (p.school) parts.push(p.school)
    if (p.big_question) parts.push(p.big_question)
    const path = parts.join('/')
    return path === currentPath.value || path.startsWith(currentPath.value + '/')
  })
})

function onNodeClick(data) {
  currentPath.value = data.path || ''
}

function onContextMenu(event, data, node) {
  if (data.is_leaf) return
  renameForm.value = { path: data.path, name: data.name }
  showRenameDialog.value = true
}

function createFolder() {
  folderForm.value = { name: '', parent: currentPath.value }
  showFolderDialog.value = true
}

async function doCreateFolder() {
  if (!folderForm.value.name.trim()) {
    ElMessage.warning('请输入文件夹名称')
    return
  }
  try {
    const parent = (folderForm.value.parent || '').trim()
    const name = folderForm.value.name.trim()
    const path = parent ? `${parent}/${name}` : name
    await axios.post('/paths/create', { path })
    ElMessage.success('文件夹已创建')
    showFolderDialog.value = false
    await refreshData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

async function doRename() {
  const oldPath = (renameForm.value.path || '').trim()
  const oldName = (renameForm.value.name || '').trim()
  if (!oldPath || !oldName) {
    ElMessage.warning('路径信息不完整')
    showRenameDialog.value = false
    return
  }
  try {
    const parent = oldPath.split('/').slice(0, -1).join('/')
    const newPath = parent ? `${parent}/${oldName}` : oldName
    if (newPath === oldPath) {
      showRenameDialog.value = false
      return
    }
    await axios.post('/paths/rename', { old_path: oldPath, new_path: newPath })
    ElMessage.success('重命名成功')
    showRenameDialog.value = false
    await refreshData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重命名失败')
  }
}

function subjectType(subject) {
  const map = { '数学': 'primary', '物理': 'success', '化学': 'warning', '语文': 'info', '英语': 'danger' }
  return map[subject] || ''
}

function parseTags(kp) {
  if (!kp) return []
  return kp.split(/[,，]/).map(t => t.trim()).filter(Boolean)
}

function goSolve(p) {
  // 所有题目统一跳转到解题页，已解附带历史
  sessionStorage.setItem('quickSolve', JSON.stringify({
    id: p.id,
    content: p.content,
    subject: p.subject,
    knowledge_point: p.knowledge_point,
    image_file_id: p.image_file_id,
    upload_mode: p.upload_mode || 'algebra',
    existingSolution: p.solution || '',
    solvedBy: p.solved_by || '',
    solvedAt: p.solved_at || '',
  }))
  router.push('/solve')
}

async function doAddProblem() {
  if (!addForm.value.content.trim()) {
    ElMessage.warning('请输入题目内容')
    return
  }
  try {
    await axios.post('/problems', {
      ...addForm.value,
      is_wrong: false,
      is_shared: false,
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    addForm.value = {
      subject: '数学',
      exam: '',
      source: '',
      school: '',
      big_question: '',
      small_question: '',
      content: '',
      knowledge_point: '',
    }
    await loadData()
  } catch (e) {
    ElMessage.error('添加失败')
  }
}

function editProblem(p) {
  editForm.value = {
    id: p.id,
    subject: p.subject || '',
    exam: p.exam || '',
    source: p.source || '',
    school: p.school || '',
    big_question: p.big_question || '',
    small_question: p.small_question || '',
    content: p.content || '',
    knowledge_point: p.knowledge_point || '',
  }
  editDialog.value = true
}

async function saveEdit() {
  try {
    const data = { ...editForm.value }
    delete data.id
    await axios.put(`/problems/${editForm.value.id}`, data)
    ElMessage.success('保存成功')
    editDialog.value = false
    await loadData()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function deleteProblem(id) {
  try {
    await ElMessageBox.confirm('确定删除这道题目？', '提示', { type: 'warning' })
    await axios.delete(`/problems/${id}`)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function batchDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 道题目？`, '提示', { type: 'warning' })
    const res = await axios.post('/problems/batch-delete', { ids: selectedIds.value })
    ElMessage.success(res.data.message || '已删除')
    selectedIds.value = []
    await loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('批量删除失败')
  }
}

async function loadData() {
  try {
    const [res, trashRes] = await Promise.all([
      axios.get('/problems', { params: { page_size: 500 } }),
      axios.get('/problems/trash'),
    ])
    problems.value = res.data.items || []
    trashItems.value = trashRes.data.items || []
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

function toggleTrash() { showTrash.value = !showTrash.value }

async function restoreProblem(id) {
  try {
    await axios.post('/problems/trash/restore', { ids: [id] })
    ElMessage.success('已恢复')
    await loadData()
  } catch (e) { ElMessage.error('恢复失败') }
}

async function emptyTrash() {
  try {
    await ElMessageBox.confirm('确定永久清空废纸篓？不可恢复。', '提示', { type: 'warning' })
    await axios.post('/problems/trash/empty')
    ElMessage.success('已清空')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('清空失败')
  }
}

function refreshData() {
  searchKeyword.value = ''
  loadData()
}

const searchKeyword = ref('')
function searchProblems() {
  if (!searchKeyword.value.trim()) {
    loadData()
    return
  }
  const kw = searchKeyword.value
  problems.value = problems.value.filter(p =>
    (p.content || '').includes(kw) ||
    (p.knowledge_point || '').includes(kw) ||
    (p.exam || '').includes(kw)
  )
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.manage-page {
  min-height: 100vh;
  background: #f8fafc;
}
.content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 8px;
}
.page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0 0 24px;
}
.main-row {
  height: calc(100vh - 160px);
}
.tree-card, .list-card {
  height: 100%;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.header-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.header-count {
  margin-left: 8px;
  font-size: 12px;
  color: #94a3b8;
  font-weight: normal;
}
.tree-node-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}
.node-name {
  flex: 1;
}
.node-count {
  font-size: 12px;
  color: #94a3b8;
}

.problem-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 220px);
  overflow-y: auto;
}
.problem-item {
  background: #f8fafc;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.problem-item:hover {
  background: #fff;
  border-color: #e2e8f0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.solved-tag {
  font-size: 12px;
  color: #059669;
  background: #f0fdf4;
  padding: 2px 8px;
  border-radius: 4px;
}
.unsolved-tag {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}
.item-id {
  margin-left: auto;
  font-size: 12px;
  color: #94a3b8;
  font-family: monospace;
}
.item-content {
  font-size: 14px;
  color: #334155;
  line-height: 1.6;
  margin-bottom: 8px;
}
.item-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.meta-tag {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}
.batch-checkbox {
  margin-right: 4px;
}
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  margin-bottom: 12px;
  background: #eff6ff;
  border-radius: 10px;
  border: 1px solid #bfdbfe;
}
.batch-count {
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  margin-right: auto;
}
.item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.item-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.empty-hint {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #94a3b8;
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
    margin-bottom: 16px;
  }
  .main-row {
    height: auto;
    flex-wrap: wrap;
  }
  .tree-card,
  .list-card {
    height: auto;
    margin-bottom: 12px;
  }
  .card-header {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 0;
  }
  .header-actions {
    margin-left: 0;
    width: 100%;
    justify-content: flex-end;
  }
  .header-actions .el-input {
    width: 100% !important;
    max-width: 100%;
    margin-right: 0 !important;
    margin-bottom: 6px;
  }
  .problem-list {
    max-height: none;
    gap: 10px;
  }
  .problem-item {
    padding: 12px;
  }
  .item-header {
    flex-wrap: wrap;
    gap: 6px;
  }
  .item-id {
    margin-left: 0;
    width: 100%;
  }
  .item-content {
    font-size: 13px;
  }
  .item-meta {
    flex-wrap: wrap;
  }
  .item-footer {
    flex-wrap: wrap;
    gap: 8px;
  }
  .item-footer .el-button-group {
    margin-left: auto;
  }
  .batch-bar {
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 12px;
  }
  .batch-count {
    margin-right: 0;
    width: 100%;
  }
  .tree-node-label {
    font-size: 13px;
  }
  :deep(.el-dialog) {
    width: 92% !important;
    max-width: 92%;
    margin: 0 auto;
  }
  :deep(.el-row) {
    flex-wrap: wrap;
  }
  :deep(.el-col-7),
  :deep(.el-col-17),
  :deep(.el-col-8) {
    max-width: 100%;
    flex: 0 0 100%;
  }
}
</style>
