import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useAppStore = defineStore('app', () => {
  const activeTab = ref('solve')
  const currentSubject = ref('数学')

  const sessions = ref([])
  const activeSessionId = ref(null)
  const activeProblem = ref(null)
  const currentSolveSession = ref(null)
  const showSolveInfo = ref(false)

  // 当前会话用量（每次操作实时更新，切换页面清空）
  const currentSessionUsage = ref({ tokens_in: 0, tokens_out: 0, cost: 0 })

  // 今日累计用量（从后端获取，跨页面保留）
  const todayUsage = ref({
    total_tokens_in: 0, total_tokens_out: 0, total_cost: 0, session_count: 0,
    deepseek: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
    kimi: { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
  })

  function setCurrentSessionUsage(usage) {
    currentSessionUsage.value = {
      tokens_in: usage.tokens_in ?? usage.input ?? 0,
      tokens_out: usage.tokens_out ?? usage.output ?? 0,
      cost: usage.cost ?? 0,
    }
  }

  function resetCurrentSessionUsage() {
    currentSessionUsage.value = { tokens_in: 0, tokens_out: 0, cost: 0 }
  }

  async function loadTodayUsage() {
    try {
      const res = await axios.get('/usage/today')
      todayUsage.value = {
        total_tokens_in: res.data.total_tokens_in ?? 0,
        total_tokens_out: res.data.total_tokens_out ?? 0,
        total_cost: res.data.total_cost ?? 0,
        session_count: res.data.session_count ?? 0,
        deepseek: res.data.deepseek || { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
        kimi: res.data.kimi || { tokens_in: 0, tokens_out: 0, cost: 0, count: 0 },
      }
    } catch {}
  }

  const activeSession = computed(() => {
    return sessions.value.find(s => s.id === activeSessionId.value) || null
  })

  // 数学功能标签
  const mathTabs = [
    { id: '录入', icon: 'Camera', label: '录入题目', color: '#2563eb' },
    { id: '解题', icon: 'Lightning', label: '解题', color: '#059669' },
    { id: '管理', icon: 'Tools', label: '管理题目', color: '#7c3aed' },
    { id: '题库', icon: 'Collection', label: '题库', color: '#0284c7' },
    { id: '用量', icon: 'Coin', label: '识别用量', color: '#d97706' },
  ]

  // 英语功能标签
  const englishTabs = [
    { id: '录入', icon: 'Upload', label: '上传资料', color: '#059669' },
    { id: '解题', icon: 'Lightning', label: '解题', color: '#059669' },
    { id: '资料', icon: 'Collection', label: '资料库', color: '#0284c7' },
    { id: '错题', icon: 'CircleClose', label: '错题本', color: '#dc2626' },
    { id: '用量', icon: 'Coin', label: '使用统计', color: '#d97706' },
  ]

  // 对话功能标签
  const chatTabs = [
    { id: '对话', icon: 'ChatLineRound', label: '对话', color: '#7c3aed' },
  ]

  const tabs = computed(() => {
    if (currentSubject.value === '英语') return englishTabs
    if (currentSubject.value === '对话') return chatTabs
    return mathTabs
  })

  async function loadSessions() {
    try {
      const res = await axios.get('/sessions')
      sessions.value = (res.data.items || []).map(s => ({
        id: s.id,
        type: '会话',
        title: s.name,
        name: s.name,
        problem_count: s.problem_count,
        created_at: s.created_at,
      }))
    } catch (e) {
      console.error('加载会话失败', e)
    }
  }

  function setActiveTab(tabId) {
    activeTab.value = tabId
  }

  function setActiveSession(id) {
    activeSessionId.value = id
  }

  function setActiveProblem(problem) {
    activeProblem.value = problem
  }

  function addSession(session) {
    sessions.value.unshift(session)
    activeSessionId.value = session.id
  }

  return {
    activeTab,
    currentSubject,
    tabs,
    sessions,
    activeSessionId,
    activeSession,
    activeProblem,
    currentSolveSession,
    showSolveInfo,
    currentSessionUsage,
    todayUsage,
    setCurrentSessionUsage,
    resetCurrentSessionUsage,
    loadTodayUsage,
    loadSessions,
    setActiveTab,
    setActiveSession,
    setActiveProblem,
    addSession,
  }
})
