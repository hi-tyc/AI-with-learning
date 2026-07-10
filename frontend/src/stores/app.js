import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const activeTab = ref('overview')
  const currentRole = ref('')
  const showSolveInfo = ref(false)

  const teacherTabs = [
    { id: 'overview', icon: 'Notebook', label: '资料分发', color: '#2563eb' },
    { id: 'materials', icon: 'Collection', label: '资料库', color: '#059669' },
    { id: 'stats', icon: 'DataAnalysis', label: '完成统计', color: '#d97706' },
  ]

  const adminTabs = [
    { id: 'overview', icon: 'DataBoard', label: '系统概览', color: '#7c3aed' },
    { id: 'classes', icon: 'OfficeBuilding', label: '班型班级', color: '#2563eb' },
    { id: 'users', icon: 'User', label: '教师账号', color: '#059669' },
  ]

  const tabs = computed(() => (currentRole.value === 'admin' ? adminTabs : teacherTabs))

  function setActiveTab(tabId) {
    activeTab.value = tabId
  }

  return {
    activeTab,
    currentRole,
    showSolveInfo,
    tabs,
    setActiveTab,
  }
})
