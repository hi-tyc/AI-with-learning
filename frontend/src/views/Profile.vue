<template>
  <div class="profile-page">
    <el-page-header title="返回" @back="$router.back()" content="个人资料" />
    <el-card class="profile-card" shadow="never">
      <el-form :model="form" label-width="120px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" disabled />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="学校">
          <el-input v-model="form.school" />
        </el-form-item>
        <el-form-item label="资料偏好">
          <el-input v-model="form.preferences" type="textarea" :rows="3" placeholder="例如：按班级分发、打印前先按标签筛选" />
        </el-form-item>
        <el-form-item label="有效期">
          <el-input v-model="form.expires_at" placeholder="2026-12-31T23:59:59，可留空" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const form = ref({ username: '', real_name: '', school: '', preferences: '', expires_at: '' })

async function load() {
  try {
    const res = await axios.get('/auth/me')
    form.value = {
      username: res.data.username || '',
      real_name: res.data.real_name || '',
      school: res.data.school || '',
      preferences: res.data.preferences || '',
      expires_at: res.data.expires_at || '',
    }
  } catch {
    ElMessage.error('加载失败')
  }
}

async function save() {
  try {
    await axios.put('/auth/me', form.value)
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

onMounted(load)
</script>

<style scoped>
.profile-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px;
}
.profile-card {
  margin-top: 20px;
  border-radius: 12px;
}
</style>
