<template>
  <div class="login-page">
    <div class="login-hero">
      <div class="hero-brand">
        <el-icon size="40" color="#fff"><School /></el-icon>
        <h1 class="hero-title">StudyBuddy</h1>
        <p class="hero-subtitle">AI 伴学 · 智能解题 · 知识积累</p>
      </div>
    </div>
    <div class="login-card-wrap">
      <el-card class="login-card" shadow="never">
        <h2 class="card-title">登录 / 注册</h2>
        <p class="card-desc">选择学科并输入用户名，即可开始学习</p>
        <el-form @submit.prevent="handleLogin">
          <!-- 学科选择 -->
          <el-form-item>
            <el-radio-group v-model="subject" size="large" style="width:100%;display:flex;justify-content:space-between">
              <el-radio-button label="数学" style="flex:1;text-align:center">
                <el-icon><Monitor /></el-icon>
                <span> 数学</span>
              </el-radio-button>
              <el-radio-button label="英语" style="flex:1;text-align:center">
                <el-icon><Reading /></el-icon>
                <span> 英语</span>
              </el-radio-button>
              <el-radio-button label="对话" style="flex:1;text-align:center">
                <el-icon><ChatLineRound /></el-icon>
                <span> 对话</span>
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="username"
              placeholder="输入用户名"
              size="large"
              :prefix-icon="User"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item v-if="isRoot">
            <el-input
              v-model="password"
              type="password"
              show-password
              placeholder="输入管理员密码"
              size="large"
              :prefix-icon="Lock"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" @click="handleLogin" style="width:100%" :icon="Right">
              开始
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { ElMessage } from 'element-plus'
import { User, Right, School, Monitor, Reading, ChatLineRound, Lock } from '@element-plus/icons-vue'

const username = ref('')
const password = ref('')
const subject = ref('数学')
const router = useRouter()
const auth = useAuthStore()
const isRoot = computed(() => username.value.trim().toLowerCase() === 'root')

const SUBJECT_HOME = {
  '数学': '/solve',
  '英语': '/english-upload',
  '对话': '/chat',
}

async function handleLogin() {
  const name = username.value.trim()
  if (!name) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (isRoot.value && !password.value) {
    ElMessage.warning('请输入管理员密码')
    return
  }
  try {
    const res = await auth.login(name, subject.value, password.value)
    ElMessage.success({ message: '欢迎回来', duration: 1500 })
    if (res.is_admin) {
      router.push('/admin')
    } else {
      router.push(SUBJECT_HOME[subject.value] || '/solve')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  background: linear-gradient(135deg, #e0e7ff 0%, #d1e0fd 50%, #c7d8fc 100%);
}
.login-hero {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.hero-brand {
  text-align: center;
  color: #1e3a5f;
}
.hero-title {
  font-size: 42px;
  font-weight: 700;
  margin: 16px 0 8px;
  letter-spacing: -1px;
  color: #1e3a5f;
}
.hero-subtitle {
  font-size: 16px;
  color: #4a6fa5;
  margin: 0;
}
.login-card-wrap {
  max-width: 420px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(20px);
}
.login-card {
  width: 100%;
  border: none;
  background: transparent;
  box-shadow: none;
}
.card-title {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 4px;
  color: #1e3a5f;
}
.card-desc {
  font-size: 14px;
  color: #8c9bb3;
  margin: 0 0 24px;
}
:deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #d0d7e6 inset;
}
:deep(.el-button) {
  border-radius: 10px;
  font-weight: 500;
}
:deep(.el-radio-button__inner) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
}

/* ========== 移动端响应式 ========== */
@media (max-width: 768px) {
  .login-page {
    flex-direction: column;
  }
  .login-hero {
    flex: none;
    padding: 24px 20px 16px;
    min-height: auto;
  }
  .hero-brand .el-icon {
    font-size: 32px;
  }
  .hero-title {
    font-size: 28px;
    margin: 8px 0 4px;
  }
  .hero-subtitle {
    font-size: 14px;
  }
  .login-card-wrap {
    width: 100%;
    padding: 20px;
    flex: 1;
    align-items: flex-start;
  }
  .login-card {
    padding: 0;
  }
  .card-title {
    font-size: 20px;
  }
  .card-desc {
    font-size: 13px;
    margin-bottom: 16px;
  }
}
</style>
