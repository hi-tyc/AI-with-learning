<template>
  <div class="library-page">
    <div class="content">
      <el-page-header title="返回" @back="$router.back()">
        <template #content>
          <div class="page-header-content">
            <el-icon size="20"><Collection /></el-icon>
            <span>题库浏览</span>
            <el-tag type="info" size="small" effect="plain">共 {{ total }} 题</el-tag>
          </div>
        </template>
      </el-page-header>

      <el-row :gutter="20" class="main-row">
        <el-col :span="5">
          <el-card shadow="hover" class="tree-card">
            <template #header>
              <div class="card-header">
                <el-icon><FolderOpened /></el-icon>
                <span>路径树</span>
              </div>
            </template>
            <el-tree
              :data="treeData"
              :props="{ label: 'label', children: 'children' }"
              @node-click="handleNodeClick"
              highlight-current
              default-expand-all
            />
          </el-card>
        </el-col>
        <el-col :span="19">
          <el-card shadow="hover" class="list-card">
            <template #header>
              <div class="card-header">
                <el-icon><Filter /></el-icon>
                <span>筛选</span>
              </div>
            </template>
            <div class="filters">
              <el-input v-model="filters.keyword" placeholder="关键词搜索" clearable prefix-icon="Search" style="width:200px" />
              <el-select v-model="filters.subject" placeholder="学科" clearable style="width:120px">
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
              <el-button type="primary" icon="Search" @click="search">搜索</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </div>
          </el-card>

          <el-card shadow="hover" class="table-card" style="margin-top:16px">
            <el-table :data="problems" style="width:100%" v-loading="loading" empty-text="暂无题目">
              <el-table-column prop="subject" label="学科" width="90">
                <template #default="scope">
                  <el-tag :type="subjectType(scope.row.subject)" size="small">{{ scope.row.subject }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="题目内容" min-width="200" show-overflow-tooltip>
                <template #default="scope">
                  <span v-html="renderMath(scope.row.content)"></span>
                </template>
              </el-table-column>
              <el-table-column prop="knowledge_point" label="知识点" width="140" show-overflow-tooltip />
              <el-table-column prop="exam" label="考试/章节" width="120" show-overflow-tooltip />
              <el-table-column label="操作" width="180">
                <template #default="scope">
                  <el-button size="small" icon="View" @click="$router.push('/problem/' + scope.row.id)">详情</el-button>
                  <el-button size="small" type="danger" icon="Delete" @click="del(scope.row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              v-model:current-page="page"
              :total="total"
              :page-size="pageSize"
              layout="total, prev, pager, next"
              @change="search"
              style="margin-top:16px; justify-content:flex-end"
            />
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { renderMath } from '../utils/mathRender'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const filters = ref({ keyword: '', subject: auth.subject === '英语' ? '英语' : '' })
const problems = ref([])
const page = ref(1)
const total = ref(0)
const pageSize = 20
const treeData = ref([])
const loading = ref(false)

function subjectType(subject) {
  const map = { '数学': 'primary', '物理': 'success', '化学': 'warning', '语文': '', '英语': 'info' }
  return map[subject] || ''
}

function resetFilters() {
  filters.value = { keyword: '', subject: '' }
  page.value = 1
  search()
}

async function search() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (filters.value.keyword) params.keyword = filters.value.keyword
    if (filters.value.subject) params.subject = filters.value.subject
    const res = await axios.get('/problems', { params })
    problems.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function buildTree() {
  const all = await axios.get('/problems', { params: { page_size: 500 } }).catch(() => ({ data: { items: [] } }))
  const items = all.data.items
  const tree = {}
  for (const p of items) {
    const keys = ['subject', 'exam', 'source', 'school', 'big_question', 'small_question']
    let node = tree
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i]
      const val = p[key] || '未分类'
      if (!node[val]) node[val] = { children: {} }
      node = node[val].children
    }
  }
  function toArr(obj) {
    return Object.entries(obj).map(([k, v]) => ({
      label: k,
      children: v.children ? toArr(v.children) : [],
    }))
  }
  treeData.value = toArr(tree)
}

function handleNodeClick(node) {
  filters.value.keyword = node.label
  page.value = 1
  search()
}

async function del(id) {
  try {
    await ElMessageBox.confirm('确定删除此题？删除后不可恢复。', '提示', { type: 'warning', confirmButtonText: '删除' })
    await axios.delete('/problems/' + id)
    ElMessage.success('已删除')
    search()
    buildTree()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => { search(); buildTree() })
</script>

<style scoped>
.library-page {
  min-height: 100vh;
  background: #f5f7fa;
}
.content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.page-header-content {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
}
.main-row {
  margin-top: 20px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.tree-card {
  height: calc(100vh - 140px);
  overflow-y: auto;
}
.list-card {
  margin-bottom: 16px;
}
.table-card {
  min-height: 400px;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .content {
    padding: 16px 12px;
  }
  .page-header-content {
    font-size: 14px;
  }
  .tree-card {
    height: auto;
    max-height: 300px;
  }
  .filters .el-input,
  .filters .el-select {
    width: 100% !important;
  }
  :deep(.el-col-5),
  :deep(.el-col-19) {
    max-width: 100%;
    flex: 0 0 100%;
  }
  :deep(.el-pagination) {
    justify-content: center !important;
  }
}
</style>
