<template>
  <div class="profile-page">
    <el-page-header title="返回" @back="$router.back()" content="个人资料" />
    <el-card class="profile-card" shadow="never">
      <el-form :model="form" label-width="120px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" disabled />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="form.grade">
            <el-option label="六年级" value="六年级" />
            <el-option label="七年级" value="七年级" />
            <el-option label="八年级" value="八年级" />
            <el-option label="九年级" value="九年级" />
          </el-select>
        </el-form-item>
        <el-form-item label="学校">
          <el-input v-model="form.school" placeholder="如：南京外国语学校" />
        </el-form-item>
        <el-form-item label="解题偏好">
          <el-input v-model="form.preferences" type="textarea" :rows="3" placeholder="如：喜欢分步骤讲解、需要详细推导过程、偏好哪种解题方法等" />
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

const form = ref({ username: '', grade: '八年级', school: '' })

async function load() {
  try {
    const res = await axios.get('/auth/me')
    form.value = res.data
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

async function save() {
  try {
    await axios.put('/auth/me', form.value)
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

onMounted(load)
</script>

<style scoped>
.profile-page {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}
.profile-card {
  margin-top: 20px;
  border-radius: 12px;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .profile-page {
    padding: 16px 12px;
  }
}
</style>
