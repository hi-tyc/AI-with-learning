<template>
  <div class="settings-page">
    <div class="content">
      <el-page-header title="返回" @back="$router.back()">
        <template #content>
          <div class="page-header-content">
            <span>系统设置</span>
          </div>
        </template>
      </el-page-header>

      <el-card class="settings-card" shadow="hover">
        <el-form :model="form" label-width="180px" label-position="left">
          <el-alert
            title="当前工作流统一使用 Kimi Code API。"
            type="success"
            :closable="false"
            show-icon
            style="margin-bottom: 20px"
          />

          <el-form-item label="Kimi API Key">
            <el-input v-model="form.kimi_api_key" type="password" show-password placeholder="sk-..." />
          </el-form-item>
          <el-form-item label="Kimi 模型">
            <el-select v-model="form.kimi_model" style="width:260px">
              <el-option label="kimi-k2.7-code（推荐）" value="kimi-k2.7-code" />
              <el-option label="kimi-k2.7-code-highspeed" value="kimi-k2.7-code-highspeed" />
              <el-option label="kimi-for-coding" value="kimi-for-coding" />
            </el-select>
          </el-form-item>
          <el-form-item label="Kimi 超时（秒）">
            <el-input-number v-model="form.kimi_timeout" :min="5" :max="300" />
          </el-form-item>
          <el-form-item label="每日花费上限（元）">
            <el-slider v-model="form.daily_cost_limit" :min="0" :max="50" :step="1" show-input />
          </el-form-item>
          <el-form-item label="图片最大大小（MB）">
            <el-input-number v-model="form.image_max_size_mb" :min="1" :max="20" />
          </el-form-item>
          <el-form-item label="压缩质量（%）">
            <el-slider v-model="form.image_compress_quality" :min="30" :max="100" />
          </el-form-item>
          <el-form-item label="压缩后最大长边（px）">
            <el-input-number v-model="form.image_max_long_edge" :min="400" :max="2000" :step="100" />
          </el-form-item>
          <el-form-item label="重试次数">
            <el-input-number v-model="form.retry_count" :min="0" :max="5" />
          </el-form-item>
          <el-form-item label="重试间隔（秒）">
            <el-input-number v-model="form.retry_interval" :min="1" :max="30" />
          </el-form-item>
          <el-form-item>
            <el-button @click="testKimi">测试连接</el-button>
            <el-button type="primary" @click="save">保存设置</el-button>
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
  kimi_api_key: '',
  kimi_model: 'kimi-k2.7-code',
  kimi_timeout: 120,
  daily_cost_limit: 10,
  image_max_size_mb: 5,
  image_compress_quality: 85,
  image_max_long_edge: 1200,
  retry_count: 2,
  retry_interval: 3,
})

async function load() {
  try {
    const res = await axios.get('/settings')
    form.value = { ...form.value, ...res.data, kimi_model: res.data.kimi_model || 'kimi-k2.7-code' }
  } catch {
    ElMessage.error('加载设置失败')
  }
}

async function save() {
  try {
    await axios.put('/settings', form.value)
    ElMessage.success('设置已保存')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
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
</style>
