<template>
  <div class="detail-page">
    <div class="content" v-if="problem">
      <el-page-header title="返回" @back="$router.back()">
        <template #content>
          <div class="page-header-content">
            <el-tag :type="subjectType(problem.subject)" size="small">{{ problem.subject }}</el-tag>
            <span class="title">{{ problem.exam || '未分类' }}</span>
            <el-tag v-if="problem.is_big_question" size="small">大题</el-tag>
            <el-tag v-if="problem.upload_mode === 'geometry'" type="primary" size="small">几何</el-tag>
            <el-tag v-else size="small">代数</el-tag>
          </div>
        </template>
      </el-page-header>

      <!-- 聊天消息区 -->
      <div class="chat-area">
        <!-- 用户消息：题目内容 -->
        <div class="msg-row user">
          <div class="avatar user-avatar">
            <el-icon size="18" color="#fff"><User /></el-icon>
          </div>
          <div class="bubble user-bubble">
            <div v-html="renderMath(problem.content)"></div>
            <el-image
              v-if="problem.image_file_id"
              :src="`/data/uploads/${problem.image_file_id}_compressed.jpg`"
              fit="contain"
              style="max-width:300px;max-height:200px;margin-top:8px;cursor:pointer"
              :preview-src-list="[`/data/uploads/${problem.image_file_id}_compressed.jpg`]"
              preview-teleported
            />
          </div>
        </div>

        <!-- AI 消息：解答（如果有） -->
        <div v-if="problem.solution && problem.solution.trim()" class="msg-row assistant">
          <div class="avatar assistant-avatar">
            <el-icon size="18" color="#fff"><Cpu /></el-icon>
          </div>
          <div class="bubble assistant-bubble">
            <div v-html="renderMath(problem.solution)"></div>
            <div class="solution-meta">
              <el-tag size="small" type="info" effect="plain">{{ problem.solved_by || 'AI' }} 解答</el-tag>
              <span class="meta-time">{{ formatDate(problem.solved_at) }}</span>
            </div>
          </div>
        </div>

        <!-- 未解答时显示提示 -->
        <div v-else class="msg-row assistant">
          <div class="avatar assistant-avatar">
            <el-icon size="18" color="#fff"><Cpu /></el-icon>
          </div>
          <div class="bubble assistant-bubble unsolved">
            <span>这道题还没有解答</span>
          </div>
        </div>
      </div>

      <!-- 子题列表 -->
      <div v-if="problem.sub_problems && problem.sub_problems.length" class="sub-section">
        <h4>包含 {{ problem.sub_problems.length }} 道小题</h4>
        <div v-for="sub in problem.sub_problems" :key="sub.id" class="sub-item" @click="goSubProblem(sub.id)">
          <span class="sub-label">{{ sub.small_question || '小题' }}</span>
          <span class="sub-content">{{ sub.content.slice(0, 60) }}{{ sub.content.length > 60 ? '...' : '' }}</span>
          <el-tag v-if="sub.solved_at" size="small" type="success">已解答</el-tag>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="actions">
        <el-button type="primary" @click="handleAction">
          <el-icon><ChatLineRound /></el-icon>
          {{ isSolved ? '查看会话' : '开始解题' }}
        </el-button>
        <el-button v-if="isSolved" @click="showReSolve = true">
          <el-icon><Refresh /></el-icon> 重新解答
        </el-button>
        <el-button v-if="problem.parent_id" type="info" @click="solveParent">
          <el-icon><ArrowUp /></el-icon> 解整题
        </el-button>
      </div>

      <!-- 重新解答弹窗 -->
      <el-dialog v-model="showReSolve" title="重新解答" width="600px">
        <el-form label-position="top">
          <el-form-item label="系统提示词（可自定义）">
            <el-input v-model="customPrompt" type="textarea" :rows="6" placeholder="留空使用默认提示词" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showReSolve = false">取消</el-button>
          <el-button type="primary" @click="doReSolve">开始重新解答</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { ChatLineRound, Refresh, ArrowUp, User, Cpu } from '@element-plus/icons-vue'
import { renderMath } from '../utils/mathRender'

const route = useRoute()
const router = useRouter()
const problem = ref(null)
const showReSolve = ref(false)
const customPrompt = ref('')

const isSolved = computed(() => {
  return problem.value && (problem.value.solved_at || (problem.value.solution && problem.value.solution.trim()))
})

function handleAction() {
  const p = problem.value
  sessionStorage.setItem('quickSolve', JSON.stringify({
    id: p.id, content: p.content, subject: p.subject,
    knowledge_point: p.knowledge_point, image_file_id: p.image_file_id,
    upload_mode: p.upload_mode || 'algebra',
  }))
  router.push('/solve')
}

function doReSolve() {
  showReSolve.value = false
  sessionStorage.setItem('quickSolve', JSON.stringify({
    id: problem.value.id,
    content: problem.value.content,
    subject: problem.value.subject,
    knowledge_point: problem.value.knowledge_point,
    image_file_id: problem.value.image_file_id,
    upload_mode: problem.value.upload_mode || 'algebra',
    customPrompt: customPrompt.value.trim() || '',
  }))
  customPrompt.value = ''
  router.push('/solve')
}

function subjectType(subject) {
  const map = { '数学': 'primary', '物理': 'success', '化学': 'warning', '语文': '', '英语': 'info' }
  return map[subject] || ''
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function goSubProblem(id) {
  router.push(`/problem/${id}`)
}

async function load() {
  try {
    const res = await axios.get('/problems/' + route.params.id)
    problem.value = res.data
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

function solveParent() {
  if (!problem.value?.parent_id) return
  router.push(`/problem/${problem.value.parent_id}`)
}

onMounted(load)
</script>

<style scoped>
.detail-page {
  min-height: 100vh;
  background: #f8fafc;
}
.content {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}
.page-header-content {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
}
.title {
  color: #334155;
  margin-right: auto;
}
.chat-area {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.msg-row {
  display: flex;
  gap: 12px;
  max-width: 90%;
}
.msg-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.msg-row.assistant {
  align-self: flex-start;
}
.avatar {
  width: 36px; height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.user-avatar { background: #2563eb; }
.assistant-avatar { background: linear-gradient(135deg, #667eea, #764ba2); }
.bubble {
  padding: 14px 18px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.8;
  word-break: break-word;
}
.user-bubble {
  background: #2563eb;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.assistant-bubble {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
  color: #334155;
}
.assistant-bubble.unsolved {
  color: #94a3b8;
}
.solution-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}
.meta-time {
  font-size: 12px;
  color: #94a3b8;
}
.sub-section {
  margin-top: 24px;
  padding: 20px;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
}
.sub-section h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #475569;
}
.sub-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.sub-item:hover { background: #eff6ff; }
.sub-label {
  font-weight: 600;
  color: #2563eb;
  font-size: 13px;
  flex-shrink: 0;
}
.sub-content {
  flex: 1;
  font-size: 13px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}
:deep(.katex-error) { color: #cc0000; }
:deep(.math-inline) { color: #2563eb; }
:deep(.math-block) {
  color: #2563eb;
  display: block;
  margin: 8px 0;
  padding: 8px 12px;
  background: #eff6ff;
  border-radius: 6px;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .problem-detail-page {
    padding: 16px 12px;
  }
  .page-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .page-title {
    font-size: 20px;
  }
  .actions {
    flex-wrap: wrap;
    gap: 8px;
  }
  .sub-item {
    flex-wrap: wrap;
    padding: 8px 10px;
  }
  .sub-content {
    max-width: 100%;
  }
}
</style>