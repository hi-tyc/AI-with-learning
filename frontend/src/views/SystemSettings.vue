<template>
  <div class="settings-page">
    <div class="content">
      <el-page-header title="返回" @back="$router.back()">
        <template #content>
          <div class="page-header-content">
            <el-icon size="20"><Setting /></el-icon>
            <span>系统设置</span>
          </div>
        </template>
      </el-page-header>

      <el-card class="settings-card" shadow="hover">
        <el-form :model="form" label-width="200px" label-position="left">

          <el-alert
            title="首次使用请先配置 DeepSeek API Key，否则无法调用 AI 解题"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 20px"
          />

          <el-divider content-position="left">
            <div class="divider-title">
              <el-icon><Cpu /></el-icon>
              <span>DeepSeek 配置</span>
            </div>
          </el-divider>

          <el-form-item label="DeepSeek API Key">
            <el-input v-model="form.deepseek_api_key" type="password" show-password placeholder="sk-..." />
          </el-form-item>
          <el-form-item label="DeepSeek 模型">
            <el-radio-group v-model="form.deepseek_model">
              <el-radio-button label="flash">flash（快）</el-radio-button>
              <el-radio-button label="pro">pro（强）</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-button icon="Connection" @click="testDeepSeek">测试 DeepSeek 连接</el-button>
          </el-form-item>

          <el-divider content-position="left">
            <div class="divider-title">
              <el-icon><Lightning /></el-icon>
              <span>Kimi 配置</span>
            </div>
          </el-divider>

          <el-form-item label="Kimi API Key">
            <el-input v-model="form.kimi_api_key" type="password" show-password placeholder="sk-..." />
          </el-form-item>
          <el-form-item label="Kimi 模型">
            <el-select v-model="form.kimi_model" style="width:240px">
              <el-option label="kimi-k2.6（推荐）" value="kimi-k2.6" />
              <el-option label="kimi-k2.5" value="kimi-k2.5" />
              <el-option label="kimi-k2.7-code" value="kimi-k2.7-code" />
              <el-option label="kimi-k2.7-code-highspeed" value="kimi-k2.7-code-highspeed" />
              <el-option label="kimi-for-coding" value="kimi-for-coding" />
            </el-select>
          </el-form-item>
          <el-form-item label="Kimi 超时（秒）">
            <el-input-number v-model="form.kimi_timeout" :min="5" :max="300" />
          </el-form-item>
          <el-form-item>
            <el-button icon="Connection" @click="testKimi">测试 Kimi 连接</el-button>
          </el-form-item>

          <el-divider content-position="left">
            <div class="divider-title">
              <el-icon><Money /></el-icon>
              <span>用量控制</span>
            </div>
          </el-divider>

          <el-form-item label="每日花费上限（元）">
            <el-slider v-model="form.daily_cost_limit" :min="0" :max="50" :step="1" show-input />
          </el-form-item>

          <el-divider content-position="left">
            <div class="divider-title">
              <el-icon><Picture /></el-icon>
              <span>图片处理</span>
            </div>
          </el-divider>

          <el-form-item label="图片最大大小（MB）">
            <el-input-number v-model="form.image_max_size_mb" :min="1" :max="20" />
          </el-form-item>
          <el-form-item label="压缩质量（%）">
            <el-slider v-model="form.image_compress_quality" :min="30" :max="100" />
          </el-form-item>
          <el-form-item label="压缩后最大长边（px）">
            <el-input-number v-model="form.image_max_long_edge" :min="400" :max="2000" :step="100" />
          </el-form-item>

          <el-divider content-position="left">
            <div class="divider-title">
              <el-icon><Timer /></el-icon>
              <span>超时与重试</span>
            </div>
          </el-divider>

          <el-form-item label="DeepSeek 超时（秒）">
            <el-input-number v-model="form.deepseek_timeout" :min="5" :max="300" />
          </el-form-item>
          <el-form-item label="重试次数">
            <el-input-number v-model="form.retry_count" :min="0" :max="5" />
          </el-form-item>
          <el-form-item label="重试间隔（秒）">
            <el-input-number v-model="form.retry_interval" :min="1" :max="30" />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" size="large" icon="CircleCheck" @click="save">保存设置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const form = ref({
  deepseek_api_key: '',
  deepseek_model: 'flash',
  kimi_api_key: '',
  kimi_model: 'kimi-k2.6',
  kimi_timeout: 120,
  daily_cost_limit: 10,
  image_max_size_mb: 5,
  image_compress_quality: 85,
  image_max_long_edge: 1200,
  deepseek_timeout: 60,
  retry_count: 2,
  retry_interval: 3,
})

async function load() {
  try {
    const res = await axios.get('/settings')
    form.value = { ...form.value, ...res.data }
  } catch (e) {
    ElMessage.error('加载设置失败')
  }
}

async function save() {
  try {
    await axios.put('/settings', form.value)
    ElMessage.success({ message: '设置已保存', duration: 2000 })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function testDeepSeek() {
  try {
    const res = await axios.post('/settings/test/deepseek', {
      deepseek_api_key: form.value.deepseek_api_key,
      deepseek_model: form.value.deepseek_model,
      deepseek_timeout: form.value.deepseek_timeout,
    })
    ElMessage.success(res.data.message)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '测试失败')
  }
}

async function testKimi() {
  try {
    const res = await axios.post('/settings/test/kimi', {
      kimi_api_key: form.value.kimi_api_key,
      kimi_model: form.value.kimi_model,
      kimi_timeout: form.value.kimi_timeout,
    })
    ElMessage.success(res.data.message)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '测试失败')
  }
}

onMounted(load)
</script>

<style scoped>
.settings-page {
  min-height: 100vh;
  background: #f5f7fa;
}
.content {
  max-width: 900px;
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
.settings-card {
  margin-top: 20px;
  border-radius: 12px;
}
.divider-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #606266;
}

@media (max-width: 768px) {
  .content {
    padding: 16px 12px;
  }
  .page-header-content {
    font-size: 14px;
  }
  .settings-card {
    margin-top: 12px;
    padding: 12px;
  }
  :deep(.el-form-item__label) {
    width: 100% !important;
    text-align: left !important;
    padding-bottom: 4px;
  }
  :deep(.el-form-item__content) {
    margin-left: 0 !important;
    flex-wrap: wrap;
  }
  :deep(.el-form-item) {
    flex-wrap: wrap;
  }
  :deep(.el-radio-group) {
    flex-wrap: wrap;
  }
  :deep(.el-select) {
    width: 100% !important;
  }
}
</style>
