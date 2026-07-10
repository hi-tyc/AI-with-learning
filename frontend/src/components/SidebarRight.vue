<template>
  <el-dialog
    v-model="app.showSolveInfo"
    title="用量统计"
    width="380px"
    top="64px"
    :close-on-click-modal="true"
    destroy-on-close
  >
    <!-- 今日总计 -->
    <div class="info-panel">
      <div class="info-section">
        <div class="section-label section-label-today">📊 今日总计</div>
        <div class="usage-stats">
          <div class="stat-item">
            <span class="stat-label">输入 tokens</span>
            <span class="stat-value">{{ app.todayUsage.total_tokens_in }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">输出 tokens</span>
            <span class="stat-value">{{ app.todayUsage.total_tokens_out }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">总费用</span>
            <span class="stat-value">¥{{ app.todayUsage.total_cost.toFixed(4) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">API 调用次数</span>
            <span class="stat-value">{{ app.todayUsage.session_count }}</span>
          </div>
        </div>
        <div class="provider-stats">
          <div class="provider-item deepseek">
            <span class="provider-name">🧠 DeepSeek</span>
            <span class="provider-usage">in {{ deepseekToday.tokens_in }} / out {{ deepseekToday.tokens_out }} · ¥{{ deepseekToday.cost.toFixed(4) }}</span>
          </div>
          <div class="provider-item kimi">
            <span class="provider-name">🌙 Kimi</span>
            <span class="provider-usage">in {{ kimiToday.tokens_in }} / out {{ kimiToday.tokens_out }} · ¥{{ kimiToday.cost.toFixed(4) }}</span>
          </div>
        </div>
      </div>
    </div>

    <el-divider style="margin:0 0 12px" />

    <!-- 当前会话用量 -->
    <div class="info-panel">
      <div class="info-section">
        <div class="section-label section-label-session">⚡ 本次会话</div>
        <div v-if="app.currentSessionUsage.tokens_in > 0 || app.currentSessionUsage.tokens_out > 0" class="usage-stats">
          <div class="stat-item">
            <span class="stat-label">输入 tokens</span>
            <span class="stat-value">{{ app.currentSessionUsage.tokens_in }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">输出 tokens</span>
            <span class="stat-value">{{ app.currentSessionUsage.tokens_out }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">费用</span>
            <span class="stat-value">¥{{ app.currentSessionUsage.cost.toFixed(6) }}</span>
          </div>
        </div>
        <div v-else class="empty-text" style="padding:8px 0">等待操作...</div>
      </div>
    </div>

    <!-- 活跃题目 -->
    <div v-if="app.activeProblem" class="info-panel">
      <div class="info-tags">
        <el-tag size="small" type="primary">{{ app.activeProblem.subject || '数学' }}</el-tag>
        <el-tag v-if="app.activeProblem.has_figure" size="small" type="warning">几何</el-tag>
      </div>
      <div class="info-section">
        <div class="section-label">知识点</div>
        <div class="knowledge-tags">
          <el-tag v-for="t in knowledgeTags" :key="t" size="small" effect="plain">{{ t }}</el-tag>
          <span v-if="!knowledgeTags.length" class="empty-text">未标注</span>
        </div>
      </div>
      <div class="info-actions">
        <el-button size="small" type="primary" plain @click="goSolve">
          <el-icon><Lightning /></el-icon> 解题
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useRouter } from 'vue-router'
import { Lightning, Document } from '@element-plus/icons-vue'

const app = useAppStore()
const router = useRouter()

const deepseekToday = computed(() => app.todayUsage.deepseek || { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 })
const kimiToday = computed(() => app.todayUsage.kimi || { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 })

const knowledgeTags = computed(() => {
  const kp = app.activeProblem?.knowledge_point || ''
  if (!kp) return []
  return kp.split(/[,，]/).map(t => t.trim()).filter(Boolean)
})

function goSolve() {
  if (app.activeProblem) router.push(`/problem/${app.activeProblem.id}`)
}

let refreshTimer = null
onMounted(() => {
  app.loadTodayUsage()
  refreshTimer = setInterval(() => app.loadTodayUsage(), 5000)
})
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.info-panel {
  padding: 0 4px;
}
.info-section { margin-bottom: 16px; }
.section-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}
.section-label-today {
  color: #059669;
  font-size: 12px;
}
.section-label-session {
  color: #2563eb;
  font-size: 12px;
}
.usage-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 6px 10px;
  background: #f8fafc;
  border-radius: 6px;
}
.stat-label { color: #64748b; }
.stat-value {
  color: #334155;
  font-weight: 500;
  font-family: 'Courier New', monospace;
}
.info-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.knowledge-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.info-actions {
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}
.empty-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 20px;
  color: #94a3b8;
  font-size: 13px;
  gap: 8px;
}
.empty-text { font-size: 13px; color: #94a3b8; }
.provider-stats {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.provider-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  padding: 5px 10px;
  border-radius: 6px;
  background: #f1f5f9;
}
.provider-item.deepseek {
  background: #eff6ff;
  color: #1e40af;
}
.provider-item.kimi {
  background: #f0fdf4;
  color: #065f46;
}
.provider-name {
  font-weight: 600;
}
.provider-usage {
  font-family: 'Courier New', monospace;
}
</style>
