<template>
  <div class="login-page">
    <div class="login-panel">
      <div class="panel-copy">
        <el-tag size="small" effect="plain" type="success">英语课外班工作台</el-tag>
        <h1>教师与管理员登录</h1>
        <p>已移除数学、对话与英语解题入口。当前版本聚焦资料上传、班型班级管理、批量分发和错题统计。</p>
      </div>

      <el-card class="login-card" shadow="never">
        <h2>登录</h2>
        <el-form @submit.prevent="handleLogin">
          <el-form-item>
            <el-input
              v-model="username"
              placeholder="用户名"
              size="large"
              :prefix-icon="User"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="password"
              type="password"
              show-password
              placeholder="密码"
              size="large"
              :prefix-icon="Lock"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" @click="handleLogin" style="width:100%" :icon="Right">
              进入工作台
            </el-button>
          </el-form-item>
          <div class="register-entry">
            <span>学生注册与审核链路</span>
            <el-button text @click="router.push('/register')">提交注册申请</el-button>
          </div>
          <el-alert
            title="学生注册、人脸视频校验与管理员审核流程已在后端留出骨架，当前前端先开放教师/管理员工作流。"
            type="info"
            :closable="false"
            show-icon
          />
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { ElMessage } from 'element-plus'
import { User, Lock, Right } from '@element-plus/icons-vue'

const username = ref('')
const password = ref('')
const router = useRouter()
const auth = useAuthStore()

async function handleLogin() {
  const name = username.value.trim()
  if (!name) {
    ElMessage.warning('请输入用户名')
    return
  }
  try {
    const res = await auth.login(name, password.value)
    ElMessage.success({ message: '登录成功', duration: 1200 })
    router.push(res.role === 'admin' ? '/admin' : '/teacher')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #eef2ff;
}
.login-panel {
  width: min(960px, 100%);
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 24px;
}
.panel-copy {
  padding: 40px 32px;
  background: #1e293b;
  color: #f8fafc;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.panel-copy h1 {
  margin: 20px 0 12px;
  font-size: 34px;
  line-height: 1.15;
}
.panel-copy p {
  margin: 0;
  color: #cbd5e1;
  line-height: 1.7;
}
.login-card {
  border: none;
  border-radius: 8px;
}
.login-card h2 {
  margin: 0 0 20px;
  color: #0f172a;
}
.register-entry {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 4px 0 16px;
  font-size: 13px;
  color: #64748b;
}
:deep(.el-input__wrapper),
:deep(.el-button) {
  border-radius: 8px;
}
@media (max-width: 900px) {
  .login-panel {
    grid-template-columns: 1fr;
  }
  .panel-copy {
    padding: 28px 24px;
  }
}
</style>
