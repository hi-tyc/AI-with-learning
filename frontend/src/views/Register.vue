<template>
  <div class="register-page">
    <div class="register-shell">
      <div class="copy-panel">
        <el-tag size="small" type="warning" effect="plain">注册申请</el-tag>
        <h1>学生注册与审核</h1>
        <p>提交用户名、真实姓名、强密码、人机验证和人脸视频后，管理员可审核、分配班级并设置有效期。</p>
        <el-button text @click="router.push('/login')">返回登录</el-button>
      </div>

      <el-card class="register-card" shadow="never">
        <el-form label-position="top">
          <el-form-item label="用户名">
            <el-input v-model="form.username" placeholder="建议只用字母、数字、下划线" />
          </el-form-item>
          <el-form-item label="真实姓名">
            <el-input v-model="form.realName" placeholder="例如：张三" />
          </el-form-item>
          <el-form-item label="申请班级">
            <el-select v-model="form.classId" clearable filterable style="width:100%">
              <el-option
                v-for="item in publicClasses"
                :key="item.id"
                :label="item.class_type_name ? `${item.class_type_name} / ${item.name}` : item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password />
            <div class="hint-line" :class="{ ok: passwordStrong }">
              至少 8 位，且同时包含字母和数字
            </div>
          </el-form-item>
          <el-form-item label="确认密码">
            <el-input v-model="form.confirmPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="人机验证">
            <div class="captcha-row">
              <span>{{ challenge.left }} + {{ challenge.right }} =</span>
              <el-input v-model="form.humanCheckValue" style="width:120px" />
              <el-button @click="refreshChallenge">换一题</el-button>
            </div>
          </el-form-item>

          <el-divider>人脸采集授权</el-divider>
          <div class="consent-panel">
            <div class="consent-header">
              <div>
                <div class="consent-title">{{ faceConsent.title }}</div>
                <div class="hint-line">版本：{{ faceConsent.version }}</div>
              </div>
              <el-tag size="small" type="info" effect="plain">必选</el-tag>
            </div>
            <ol class="consent-list">
              <li v-for="(item, index) in faceConsent.items" :key="index">{{ item }}</li>
            </ol>
            <el-checkbox v-model="form.faceConsentAccepted">
              {{ faceConsent.checkbox_label }}
            </el-checkbox>
          </div>

          <el-divider>人脸视频录制</el-divider>
          <div class="video-panel">
            <div class="camera-stage" :class="{ recording: recording }">
              <video ref="videoRef" autoplay muted playsinline class="camera-video"></video>
              <div class="guide-box" :class="{ aligned: faceAligned }"></div>
              <div v-if="recording && flashOn" class="flash-overlay"></div>
              <div class="camera-status">
                <span>{{ detectorLabel }}</span>
                <span :class="{ ok: faceAligned }">{{ faceAligned ? '人脸位置合适' : '请将人脸移到框内' }}</span>
              </div>
            </div>
            <div class="video-actions">
              <el-button @click="startCamera" :disabled="cameraReady || !form.faceConsentAccepted">打开摄像头</el-button>
              <el-button type="primary" :disabled="!cameraReady || recording || !faceAligned" @click="startRecording">开始录制</el-button>
              <el-button :disabled="!cameraReady" @click="stopCamera">关闭摄像头</el-button>
            </div>
            <div class="hint-line">
              需先确认授权后才能启用摄像头。录制时页面会闪烁，并在 6 秒后自动停止，用于区分现场录制和预录视频。
            </div>
            <video v-if="recordedUrl" :src="recordedUrl" controls class="preview-video"></video>
          </div>

          <el-form-item>
            <el-button type="primary" :loading="submitting" @click="submitRegistration" style="width:100%">
              提交注册申请
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const videoRef = ref(null)
const form = ref({
  username: '',
  realName: '',
  classId: '',
  password: '',
  confirmPassword: '',
  humanCheckValue: '',
  faceConsentAccepted: false,
})

const defaultFaceConsent = () => ({
  version: 'face-consent-v1',
  title: '人脸视频采集授权书',
  items: [
    '本人知悉本系统会在注册阶段采集一段现场人脸视频，仅用于身份核验、人工审核和防止冒用注册。',
    '采集内容仅限注册时主动录制并上传的视频文件，不会在未授权的情况下持续开启摄像头或进行其他用途分析。',
    '该视频仅限管理员或经授权的审核人员查看，未经额外授权不会对外公开、转让或挪作教学无关用途。',
    '若注册申请被拒绝、撤回或超过内部保留期限，学校或机构应按管理规则删除或停用该视频资料。',
    '本人确认提交前已获得监护人或本人合法授权，并同意系统保存本次授权版本与确认时间作为审计记录。',
  ],
  checkbox_label: '我已阅读并同意上述人脸视频采集、审核与留存说明',
})

const faceConsent = ref(defaultFaceConsent())
const publicClasses = ref([])
const submitting = ref(false)
const challenge = ref({ left: 3, right: 5 })
const cameraReady = ref(false)
const faceAligned = ref(false)
const faceDetectionSupported = ref(false)
const recording = ref(false)
const flashOn = ref(false)
const recordedBlob = ref(null)
const recordedUrl = ref('')

let stream = null
let detector = null
let detectTimer = null
let flashTimer = null
let recordStopTimer = null
let mediaRecorder = null
let chunks = []

const passwordStrong = computed(() => {
  const value = form.value.password || ''
  return value.length >= 8 && /[A-Za-z]/.test(value) && /\d/.test(value)
})

const detectorLabel = computed(() => faceDetectionSupported.value ? '原生人脸检测已启用' : '浏览器不支持 FaceDetector，使用摄像头可见性兜底')

function refreshChallenge() {
  challenge.value = {
    left: Math.floor(Math.random() * 8) + 1,
    right: Math.floor(Math.random() * 8) + 1,
  }
  form.value.humanCheckValue = ''
}

async function loadPublicClasses() {
  const res = await axios.get('/school/public-classes')
  publicClasses.value = res.data.items || []
}

async function loadFaceConsent() {
  try {
    const res = await axios.get('/auth/face-consent')
    faceConsent.value = { ...defaultFaceConsent(), ...(res.data || {}) }
  } catch {
    faceConsent.value = defaultFaceConsent()
  }
}

async function startCamera() {
  if (!form.value.faceConsentAccepted) {
    ElMessage.warning('请先确认人脸采集授权')
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
    videoRef.value.srcObject = stream
    cameraReady.value = true
    if ('FaceDetector' in window) {
      detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 })
      faceDetectionSupported.value = true
    } else {
      detector = null
      faceDetectionSupported.value = false
    }
    startDetectLoop()
  } catch (e) {
    ElMessage.error('无法打开摄像头')
  }
}

function stopCamera() {
  if (detectTimer) {
    clearInterval(detectTimer)
    detectTimer = null
  }
  if (flashTimer) {
    clearInterval(flashTimer)
    flashTimer = null
  }
  if (recordStopTimer) {
    clearTimeout(recordStopTimer)
    recordStopTimer = null
  }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  if (stream) {
    stream.getTracks().forEach(track => track.stop())
    stream = null
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
  cameraReady.value = false
  faceAligned.value = false
  recording.value = false
  flashOn.value = false
}

function startDetectLoop() {
  if (detectTimer) clearInterval(detectTimer)
  detectTimer = setInterval(async () => {
    if (!videoRef.value || videoRef.value.readyState < 2) return
    if (!detector) {
      faceAligned.value = cameraReady.value
      return
    }
    try {
      const faces = await detector.detect(videoRef.value)
      const face = faces?.[0]
      if (!face) {
        faceAligned.value = false
        return
      }
      const vw = videoRef.value.videoWidth || 1
      const vh = videoRef.value.videoHeight || 1
      const box = face.boundingBox
      const centerX = (box.x + box.width / 2) / vw
      const centerY = (box.y + box.height / 2) / vh
      const widthRatio = box.width / vw
      const heightRatio = box.height / vh
      faceAligned.value =
        centerX > 0.3 && centerX < 0.7 &&
        centerY > 0.25 && centerY < 0.75 &&
        widthRatio > 0.18 && widthRatio < 0.6 &&
        heightRatio > 0.18 && heightRatio < 0.7
    } catch {
      faceAligned.value = cameraReady.value
    }
  }, 700)
}

function startRecording() {
  if (!stream || !faceAligned.value) return
  chunks = []
  recordedBlob.value = null
  if (recordedUrl.value) {
    URL.revokeObjectURL(recordedUrl.value)
    recordedUrl.value = ''
  }
  mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' })
  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) chunks.push(event.data)
  }
  mediaRecorder.onstop = () => {
    recordedBlob.value = new Blob(chunks, { type: 'video/webm' })
    recordedUrl.value = URL.createObjectURL(recordedBlob.value)
    recording.value = false
    flashOn.value = false
    if (flashTimer) {
      clearInterval(flashTimer)
      flashTimer = null
    }
  }
  mediaRecorder.start()
  recording.value = true
  flashTimer = setInterval(() => {
    flashOn.value = !flashOn.value
  }, 180)
  recordStopTimer = setTimeout(() => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop()
  }, 6000)
}

async function submitRegistration() {
  const expected = challenge.value.left + challenge.value.right
  if (!form.value.username.trim() || !form.value.realName.trim()) {
    ElMessage.warning('请填写用户名和真实姓名')
    return
  }
  if (!passwordStrong.value) {
    ElMessage.warning('密码强度不足')
    return
  }
  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  if (String(expected) !== String(form.value.humanCheckValue).trim()) {
    ElMessage.warning('人机验证未通过')
    return
  }
  if (!form.value.faceConsentAccepted) {
    ElMessage.warning('请先确认人脸采集授权')
    return
  }
  if (!recordedBlob.value) {
    ElMessage.warning('请先录制人脸视频')
    return
  }
  submitting.value = true
  try {
    const payload = new FormData()
    payload.append('username', form.value.username.trim())
    payload.append('real_name', form.value.realName.trim())
    payload.append('password', form.value.password)
    payload.append('confirm_password', form.value.confirmPassword)
    payload.append('captcha_token', 'verified')
    payload.append('human_check_value', form.value.humanCheckValue)
    payload.append('class_id', form.value.classId || '')
    payload.append('face_detection_supported', String(faceDetectionSupported.value))
    payload.append('face_aligned', String(faceAligned.value))
    payload.append('face_consent_accepted', String(form.value.faceConsentAccepted))
    payload.append('face_consent_version', faceConsent.value.version || defaultFaceConsent().version)
    payload.append('face_video', recordedBlob.value, `${form.value.username || 'user'}-face.webm`)
    await axios.post('/auth/register', payload)
    ElMessage.success('注册申请已提交')
    stopCamera()
    router.push('/login')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  refreshChallenge()
  loadPublicClasses().catch(() => {})
  loadFaceConsent().catch(() => {})
})

onUnmounted(() => {
  stopCamera()
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
})
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  background: #eef2ff;
  display: grid;
  place-items: center;
  padding: 24px;
}
.register-shell {
  width: min(1100px, 100%);
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  gap: 24px;
}
.copy-panel {
  background: #111827;
  color: #f8fafc;
  border-radius: 8px;
  padding: 32px 28px;
}
.copy-panel h1 {
  margin: 18px 0 12px;
  font-size: 32px;
}
.copy-panel p {
  color: #cbd5e1;
  line-height: 1.7;
}
.register-card {
  border-radius: 8px;
  border: none;
}
.captcha-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hint-line {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}
.hint-line.ok {
  color: #059669;
}
.consent-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #f8fafc;
}
.consent-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.consent-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.consent-list {
  margin: 0;
  padding-left: 20px;
  color: #334155;
  line-height: 1.7;
}
.video-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.camera-stage {
  position: relative;
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
  aspect-ratio: 4 / 3;
}
.camera-video,
.preview-video {
  width: 100%;
  border-radius: 8px;
  background: #000;
}
.guide-box {
  position: absolute;
  left: 22%;
  top: 16%;
  width: 56%;
  height: 66%;
  border: 3px solid rgba(248, 250, 252, 0.85);
  border-radius: 16px;
  box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.16);
}
.guide-box.aligned {
  border-color: #22c55e;
}
.camera-status {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.78);
  color: #f8fafc;
  font-size: 12px;
}
.camera-status .ok {
  color: #4ade80;
}
.flash-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.28);
  pointer-events: none;
}
.video-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
@media (max-width: 960px) {
  .register-shell {
    grid-template-columns: 1fr;
  }
}
</style>
