<template>
  <div class="usage-page">
    <div class="content">
      <h1 class="page-title">用量统计</h1>
      <p class="page-subtitle">识别（上传）、解题与对话的 API 用量与花费</p>

      <div class="summary-cards">
        <div class="panel-card summary-card">
          <span class="summary-label">📊 今日总计</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>输入 tokens</span>
              <span class="summary-val">{{ todayStats.total_tokens_in }}</span>
            </div>
            <div class="summary-row">
              <span>输出 tokens</span>
              <span class="summary-val">{{ todayStats.total_tokens_out }}</span>
            </div>
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
        <div class="panel-card summary-card">
          <span class="summary-label">🧠 DeepSeek</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>输入 tokens</span>
              <span class="summary-val">{{ (todayStats.deepseek && todayStats.deepseek.tokens_in) || 0 }}</span>
            </div>
            <div class="summary-row">
              <span>输出 tokens</span>
              <span class="summary-val">{{ (todayStats.deepseek && todayStats.deepseek.tokens_out) || 0 }}</span>
            </div>
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
        <div class="panel-card summary-card">
          <span class="summary-label">🌙 Kimi</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>输入 tokens</span>
              <span class="summary-val">{{ (todayStats.kimi && todayStats.kimi.tokens_in) || 0 }}</span>
            </div>
            <div class="summary-row">
              <span>输出 tokens</span>
              <span class="summary-val">{{ (todayStats.kimi && todayStats.kimi.tokens_out) || 0 }}</span>
            </div>
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
        <div class="panel-card summary-card" style="flex: 1 1 100%">
          <span class="summary-label">📈 累计总计</span>
          <div class="summary-stats">
            <div class="summary-row">
              <span>累计花费</span>
              <span class="summary-val price">¥{{ total }}</span>
            </div>
            <div class="summary-row">
              <span>DeepSeek</span>
              <span class="summary-val">¥{{ deepseekTotal }}</span>
            </div>
            <div class="summary-row">
              <span>Kimi</span>
              <span class="summary-val">¥{{ kimiTotal }}</span>
            </div>
            <div class="summary-row">
              <span>总记录数</span>
              <span class="summary-val">{{ totalSessionCount }} 条</span>
            </div>
          </div>
        </div>
      </div>

      <div class="panel-card">
        <el-table :data="sessions" stripe style="width: 100%" empty-text="暂无用量记录">
          <el-table-column label="类型" min-width="80">
            <template #default="{ row }">
              <el-tag v-if="row.session_type === 'upload'" size="small" type="primary">识别</el-tag>
              <el-tag v-else-if="row.session_type === 'solve'" size="small" type="warning">解题</el-tag>
              <el-tag v-else-if="row.session_type === 'chat'" size="small" type="success">对话</el-tag>
              <el-tag v-else size="small">未知</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="内容" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.display_title || '—' }}</template>
          </el-table-column>
          <el-table-column label="模型" prop="model" min-width="110">
            <template #default="{ row }">{{ row.model || '—' }}</template>
          </el-table-column>
          <el-table-column label="缓内输入" prop="input_cache_hit" min-width="100" align="right" />
          <el-table-column label="缓外输入" prop="input_cache_miss" min-width="100" align="right" />
          <el-table-column label="输出" prop="output" min-width="90" align="right" />
          <el-table-column label="花费" min-width="110" align="right">
            <template #default="{ row }">
              <span v-if="row.cost_yuan === null || row.cost_yuan === undefined" class="free-tag">包月不计费</span>
              <span v-else>¥{{ row.cost_yuan }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="90" align="center">
            <template #default="{ row }">
              <el-button type="danger" size="small" text @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel-card pricing-card">
        <div class="pricing-title">当前价格（¥ / 百万 tokens）</div>
        <div v-for="(rates, provider) in pricing" :key="provider" class="pricing-row">
          <span class="provider-name">{{ provider }}</span>
          <template v-if="rates">
            <el-tag size="small" type="info">命中 {{ rates.input_cache_hit }}</el-tag>
            <el-tag size="small" type="info">未命中 {{ rates.input_cache_miss }}</el-tag>
            <el-tag size="small" type="info">输出 {{ rates.output }}</el-tag>
          </template>
          <el-tag v-else size="small" type="success">包月套餐 · 不计费</el-tag>
        </div>
        <p class="pricing-note">价格可在 <code>用户_config.json</code> 的 <code>pricing</code> 字段修改。Kimi Code 为包月订阅套餐，识别用量按「不计费」记录。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAppStore } from '../stores/app.js'

const app = useAppStore()
const sessions = ref([])
const total = ref(0)
const deepseekTotal = ref(0)
const kimiTotal = ref(0)
const pricing = ref({})
const todayStats = ref({
  total_tokens_in: 0, total_tokens_out: 0, total_cost: 0, session_count: 0,
  deepseek: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
  kimi: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
})

const totalSessionCount = computed(() => sessions.value.length)

function normalizeSession(s, type) {
  const base = { ...s, session_type: type }
  if (type === 'chat') {
    const lu = s.last_usage || {}
    base.display_title = s.title || '—'
    base.input_cache_hit = lu.hit || 0
    base.input_cache_miss = lu.miss || 0
    base.output = lu.out || 0
    base.cost_yuan = s.total_cost ?? (lu.cost ?? null)
    base.model = s.engine || '—'
  } else if (type === 'solve') {
    base.display_title = s.title || '—'
    base.input_cache_hit = s.input_cache_hit || 0
    base.input_cache_miss = s.input_cache_miss || 0
    base.output = s.output || 0
    base.cost_yuan = s.cost_yuan ?? null
  } else {
    base.display_title = s.filename || '—'
    base.input_cache_hit = s.input_cache_hit || 0
    base.input_cache_miss = s.input_cache_miss || 0
    base.output = s.output || 0
    base.cost_yuan = s.cost_yuan ?? null
  }
  return base
}

async function load() {
  try {
    const [usageRes, todayRes, solveRes, chatRes] = await Promise.all([
      axios.get('/usage'),
      axios.get('/usage/today'),
      axios.get('/solve-sessions?page_size=50'),
      axios.get('/chat/sessions'),
    ])
    const data = usageRes.data || {}
    const uploadSessions = (data.sessions || []).map(s => normalizeSession(s, 'upload'))
    const solveData = solveRes.data?.sessions || solveRes.data || []
    const chatData = chatRes.data?.sessions || chatRes.data || []
    const solveSessions = solveData.map(s => normalizeSession(s, 'solve'))
    const chatSessions = chatData.map(s => normalizeSession(s, 'chat'))
    const all = [...uploadSessions, ...solveSessions, ...chatSessions]
    all.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
    sessions.value = all
    total.value = all.reduce((sum, s) => sum + (Number(s.cost_yuan) || 0), 0)
    deepseekTotal.value = Number(data.deepseek_cost_yuan) || 0
    kimiTotal.value = Number(data.kimi_cost_yuan) || 0
    pricing.value = data.pricing || {}
    todayStats.value = Object.assign({
      total_tokens_in: 0, total_tokens_out: 0, total_cost: 0, session_count: 0,
      deepseek: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
      kimi: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
    }, todayRes.data || {})
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载用量失败')
  }
}

async function remove(row) {
  try {
    const type = row.session_type
    const id = row.id
    if (type === 'solve') {
      await axios.delete('/solve-sessions/' + id)
    } else if (type === 'chat') {
      await axios.delete('/chat/sessions/' + id)
    } else {
      await axios.delete('/usage/' + id)
    }
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

onMounted(() => {
  app.setActiveTab('用量')
  app.loadTodayUsage()
  load()
})
</script>

<style scoped>
.usage-page {
  min-height: 100vh;
  background: #f8fafc;
}
.content {
  max-width: min(960px, 100% - 48px);
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}
.page-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0 0 32px;
}
.summary-cards {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}
.summary-card {
  flex: 1;
}
.summary-label {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  display: block;
  margin-bottom: 12px;
}
.summary-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #64748b;
  padding: 4px 0;
  border-bottom: 1px solid #f1f5f9;
}
.summary-row:last-child {
  border-bottom: none;
}
.summary-val {
  font-weight: 600;
  color: #334155;
}
.summary-val.price {
  color: #2563eb;
}
.panel-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 24px;
  margin-bottom: 20px;
}
.free-tag {
  color: #16a34a;
  font-weight: 600;
}
.pricing-card {
  font-size: 13px;
}
.pricing-title {
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}
.pricing-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.provider-name {
  width: 80px;
  font-weight: 600;
  color: #334155;
  text-transform: capitalize;
}
.pricing-note {
  color: #64748b;
  margin: 12px 0 0;
}
.pricing-note code {
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
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
    margin-bottom: 20px;
  }
  .summary-cards {
    flex-wrap: wrap;
    gap: 12px;
  }
  .summary-card {
    flex: 0 0 100%;
    max-width: 100%;
  }
  .panel-card {
    padding: 16px;
    margin-bottom: 16px;
  }
  .pricing-row {
    flex-wrap: wrap;
    gap: 6px;
  }
  .provider-name {
    width: 100%;
    margin-bottom: 4px;
  }
  :deep(.el-table) {
    font-size: 12px;
  }
  :deep(.el-table .cell) {
    padding: 6px 4px;
  }
  .panel-card {
    overflow-x: auto;
  }
}
</style>
