<template>
  <div class="english-usage-page">
    <div class="content">
      <div class="page-header">
        <h1 class="page-title">使用统计</h1>
        <p class="page-subtitle">英语 AI 解题与上传的 API 用量与花费</p>
      </div>

      <div class="summary-cards">
        <div class="summary-card">
          <span class="summary-label">📊 今日总计</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>总费用</span>
              <span class="summary-val price">¥{{ todayStats.total_cost.toFixed(4) }}</span>
            </div>
            <div class="summary-row">
              <span>API 调用</span>
              <span class="summary-val">{{ todayStats.session_count }} 次</span>
            </div>
          </div>
        </div>
        <div class="summary-card">
          <span class="summary-label">🧠 DeepSeek</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>费用</span>
              <span class="summary-val price">¥{{ ((todayStats.deepseek && todayStats.deepseek.cost) || 0).toFixed(4) }}</span>
            </div>
            <div class="summary-row">
              <span>调用</span>
              <span class="summary-val">{{ (todayStats.deepseek && todayStats.deepseek.count) || 0 }} 次</span>
            </div>
          </div>
        </div>
        <div class="summary-card">
          <span class="summary-label">🌙 Kimi</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>费用</span>
              <span class="summary-val price">¥{{ ((todayStats.kimi && todayStats.kimi.cost) || 0).toFixed(4) }}</span>
            </div>
            <div class="summary-row">
              <span>调用</span>
              <span class="summary-val">{{ (todayStats.kimi && todayStats.kimi.count) || 0 }} 次</span>
            </div>
          </div>
        </div>
      </div>

      <div class="summary-cards">
        <div class="summary-card" style="flex: 1 1 100%">
          <span class="summary-label">📈 累计总计</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>累计花费</span>
              <span class="summary-val price">¥{{ totalCost }}</span>
            </div>
            <div class="summary-row">
              <span>DeepSeek</span>
              <span class="summary-val">¥{{ deepseekCost }}</span>
            </div>
            <div class="summary-row">
              <span>Kimi</span>
              <span class="summary-val">¥{{ kimiCost }}</span>
            </div>
            <div class="summary-row">
              <span>解题次数</span>
              <span class="summary-val">{{ solveCount }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="usage-table">
        <el-table :data="sessions" stripe style="width: 100%" empty-text="暂无记录" size="small">
          <el-table-column label="时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="题目/文件" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.title || row.question || row.filename || '—' }}</template>
          </el-table-column>
          <el-table-column label="模型" prop="model" width="100" />
          <el-table-column label="花费" width="100" align="right">
            <template #default="{ row }">
              <span v-if="row.cost_yuan === null || row.cost_yuan === undefined" class="free-tag">包月</span>
              <span v-else>¥{{ row.cost_yuan }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row }">
              <el-button type="danger" size="small" text @click="remove(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAppStore } from '../../stores/app.js'

const app = useAppStore()
const sessions = ref([])
const totalCost = ref(0)
const deepseekCost = ref(0)
const kimiCost = ref(0)
const todayStats = ref({
  total_tokens_in: 0, total_tokens_out: 0, total_cost: 0, session_count: 0,
  deepseek: { cost: 0, count: 0 },
  kimi: { cost: 0, count: 0 },
})

const solveCount = computed(() => sessions.value.length)

onMounted(() => {
  app.setActiveTab('用量')
  load()
})

async function load() {
  try {
    const [usageRes, solveRes, todayRes] = await Promise.all([
      axios.get('/usage'),
      axios.get('/solve-sessions'),
      axios.get('/usage/today'),
    ])
    const usageSessions = usageRes.data.sessions || []
    const solveSessions = solveRes.data.items || []
    sessions.value = [...solveSessions, ...usageSessions]
      .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
    totalCost.value = Number(usageRes.data.total_cost_yuan) || 0
    deepseekCost.value = Number(usageRes.data.deepseek_cost_yuan) || 0
    kimiCost.value = Number(usageRes.data.kimi_cost_yuan) || 0
    todayStats.value = Object.assign({
      total_tokens_in: 0, total_tokens_out: 0, total_cost: 0, session_count: 0,
      deepseek: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
      kimi: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
    }, todayRes.data || {})
  } catch (e) {
    ElMessage.error('加载用量失败')
  }
}

async function remove(id) {
  try {
    await axios.delete(`/usage/${id}`).catch(() => axios.delete(`/solve-sessions/${id}`))
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString()
}
</script>

<style scoped>
.english-usage-page {
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
.summary-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}
.summary-card {
  flex: 1;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
  display: block;
  margin-bottom: 8px;
}
.summary-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #6b7280;
  padding: 3px 0;
}
.summary-val { font-weight: 600; color: #334155; }
.summary-val.price { color: #059669; }
.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #059669;
}
.free-tag { color: #16a34a; font-weight: 600; }
.usage-table {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 16px;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .usage-page {
    padding: 16px 12px;
  }
  .summary-cards {
    flex-direction: column;
    gap: 10px;
  }
  .summary-card {
    padding: 14px;
  }
  .summary-value {
    font-size: 20px;
  }
  .usage-table {
    padding: 12px;
  }
}
</style>
