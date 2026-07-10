<template>
  <AppLayout v-if="showLayout">
    <router-view />
  </AppLayout>
  <router-view v-else />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from './components/AppLayout.vue'

const route = useRoute()
const showLayout = computed(() => !['/login', '/register'].includes(route.path))
</script>

<style>
@media print {
  .sidebar-left,
  .sidebar-right,
  .mobile-header,
  .el-dialog__wrapper,
  .el-overlay {
    display: none !important;
  }
  .app-layout {
    height: auto !important;
    overflow: visible !important;
    background: #fff !important;
  }
  .main-content {
    height: auto !important;
    overflow: visible !important;
    padding: 0 !important;
  }
  body {
    background: #fff !important;
  }
}
</style>
