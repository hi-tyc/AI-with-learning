<template>
  <div class="document-viewer-page">
    <div class="viewer-header">
      <h1 class="viewer-title">文档查看</h1>
      <div class="viewer-actions">
        <el-button size="small" @click="goBack">返回</el-button>
        <el-button size="small" :icon="Printer" @click="printDoc">打印</el-button>
        <el-button size="small" type="primary" tag="a" :href="downloadUrl">下载原文</el-button>
      </div>
    </div>

    <div v-if="loading" class="viewer-loading">
      {{ printPending ? '正在准备打印…' : '正在加载文档…' }}
    </div>
    <div v-else-if="error" class="viewer-error">{{ error }}</div>
    <div v-else-if="isPdf" class="viewer-frame">
      <iframe :src="fileUrl" class="doc-frame" frameborder="0"></iframe>
    </div>
    <div v-else-if="isImage" class="viewer-image">
      <img :src="fileUrl" :alt="decodedFileName" />
    </div>
    <div v-else-if="isDocx" class="viewer-docx" v-html="docxHtml"></div>
    <div v-else class="viewer-error">
      暂不支持在浏览器中直接查看该文件类型，请使用“下载原文”保存到本地后打开。
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Printer } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const fileId = computed(() => route.query.fileId || '')
const fileType = computed(() => (route.query.fileType || '').toLowerCase())
const fileName = computed(() => route.query.fileName || '')
const autoPrint = computed(() => route.query.action === 'print')
const decodedFileName = computed(() => {
  try {
    return decodeURIComponent(fileName.value)
  } catch {
    return fileName.value
  }
})
const fileUrl = computed(() => fileId.value ? `/api/materials/${fileId.value}/file` : '')
const downloadUrl = computed(() => fileId.value ? `/api/materials/${fileId.value}/file?download=1` : '')

const loading = ref(false)
const printPending = ref(false)
const error = ref('')
const docxHtml = ref('')

const isPdf = computed(() => fileType.value === 'pdf')
const isDocx = computed(() => fileType.value === 'docx')
const isImage = computed(() => ['jpg', 'jpeg', 'png', 'image'].includes(fileType.value))

function goBack() {
  router.back()
}

function printDoc() {
  if (isDocx.value) {
    window.print()
    return
  }

  // 为 PDF / 图片创建专用打印 iframe，确保打印的是源文档
  const printIframe = document.createElement('iframe')
  printIframe.style.position = 'fixed'
  printIframe.style.left = '-9999px'
  printIframe.style.top = '-9999px'
  printIframe.style.width = '1px'
  printIframe.style.height = '1px'
  printIframe.style.border = 'none'

  if (isPdf.value) {
    printIframe.src = fileUrl.value
  } else if (isImage.value) {
    printIframe.srcdoc = `<html><head><title>${decodedFileName.value}</title></head><body style="margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh"><img src="${fileUrl.value}" style="max-width:100%;max-height:100vh" onload="setTimeout(()=>window.print(),200)" /></body></html>`
  }

  let printed = false
  const doPrint = () => {
    if (printed) return
    printed = true
    setTimeout(() => {
      try {
        printIframe.contentWindow.print()
      } catch {
        window.print()
      }
      setTimeout(() => {
        if (printIframe.parentNode) printIframe.parentNode.removeChild(printIframe)
      }, 2000)
    }, 500)
  }

  printIframe.onload = doPrint
  // 兜底：部分浏览器 PDF iframe 不触发 onload
  setTimeout(doPrint, 1500)

  document.body.appendChild(printIframe)
}

async function loadDocument() {
  if (!fileId.value) {
    error.value = '缺少文件参数'
    return
  }
  if (!isPdf.value && !isDocx.value && !isImage.value) {
    // 不支持的类型直接提示下载
    return
  }
  loading.value = true
  error.value = ''
  try {
    // Verify the file exists first
    if (isPdf.value || isImage.value) {
      const head = await fetch(fileUrl.value, { method: 'HEAD', credentials: 'include' })
      if (!head.ok) {
        if (head.status === 404) throw new Error('原始文件不存在')
        throw new Error('文件加载失败 (' + head.status + ')')
      }
    }
    if (isDocx.value) {
      await loadDocx()
    }
    // PDF/img are loaded via iframe/img tag, no further processing needed
  } catch (e) {
    error.value = '文档加载失败：' + (e.message || '未知错误')
  } finally {
    loading.value = false
  }
}

async function loadDocx() {
  try {
    const htmlRes = await fetch(`/api/materials/${fileId.value}/html`, { credentials: 'include' })
    if (htmlRes.ok) {
      const data = await htmlRes.json()
      if (data.html) {
        docxHtml.value = data.html
        return
      }
    }
  } catch {}

  const mammoth = await import('mammoth')
  const res = await fetch(fileUrl.value, { credentials: 'include' })
  if (!res.ok) {
    if (res.status === 404) throw new Error('原始文件不存在')
    throw new Error('下载文档失败')
  }
  const arrayBuffer = await res.arrayBuffer()
  const result = await mammoth.convertToHtml({ arrayBuffer }, { includeDefaultStyleMap: true })
  docxHtml.value = result.value || '<p>文档内容为空</p>'
}

function triggerAutoPrint() {
  printPending.value = true
  const waitForReady = () => {
    if (isDocx.value && !docxHtml.value) {
      requestAnimationFrame(waitForReady)
      return
    }
    printPending.value = false
    setTimeout(printDoc, 400)
  }
  waitForReady()
}

onMounted(() => {
  loadDocument().then(() => {
    if (autoPrint.value) triggerAutoPrint()
  })
})
</script>

<style scoped>
.document-viewer-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f1f5f9;
}
.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.viewer-title {
  margin: 0;
  font-size: 18px;
  color: #1e293b;
}
.viewer-actions {
  display: flex;
  gap: 8px;
}
.viewer-loading,
.viewer-error {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  text-align: center;
}
.viewer-loading {
  color: #64748b;
}
.viewer-error {
  color: #dc2626;
}
.viewer-frame {
  flex: 1;
  overflow: hidden;
}
.doc-frame {
  width: 100%;
  height: 100%;
  border: none;
}
.viewer-image {
  flex: 1;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px;
}
.viewer-image img {
  max-width: 100%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}
.viewer-docx {
  flex: 1;
  overflow: auto;
  background: #fff;
  padding: 40px;
  margin: 0 auto;
  max-width: 900px;
  width: 100%;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  line-height: 1.8;
  color: #334155;
}
.viewer-docx :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}
.viewer-docx :deep(th),
.viewer-docx :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
}
.viewer-docx :deep(p) {
  margin: 8px 0;
}
.viewer-docx :deep(h1), .viewer-docx :deep(h2), .viewer-docx :deep(h3), .viewer-docx :deep(h4), .viewer-docx :deep(h5), .viewer-docx :deep(h6) {
  margin: 18px 0 10px;
  color: #1e293b;
}
.viewer-docx :deep(ul), .viewer-docx :deep(ol) {
  padding-left: 28px;
  margin: 10px 0;
}
.viewer-docx :deep(li) {
  margin: 4px 0;
}
.viewer-docx :deep(.page-break) {
  page-break-before: always;
}
@media print {
  .viewer-docx :deep(.page-break) {
    page-break-before: always;
  }
}

@media print {
  @page {
    size: A4;
    margin: 15mm;
  }
  .viewer-header,
  .viewer-actions,
  .viewer-loading,
  .viewer-error {
    display: none !important;
  }
  .document-viewer-page {
    height: auto;
    background: #fff;
  }
  .viewer-frame,
  .viewer-image,
  .viewer-docx {
    flex: none;
    overflow: visible;
    height: auto;
    box-shadow: none;
    max-width: none;
  }
  .viewer-docx {
    padding: 0;
    margin: 0 auto;
    max-width: 210mm;
    color: #000;
    line-height: 1.6;
    font-size: 12pt;
  }
  .viewer-docx :deep(p),
  .viewer-docx :deep(div),
  .viewer-docx :deep(span),
  .viewer-docx :deep(li) {
    white-space: pre-wrap;
    word-break: break-word;
  }
  .viewer-docx :deep(p) {
    margin: 6pt 0;
  }
  .viewer-docx :deep(table) {
    page-break-inside: avoid;
    margin: 8pt 0;
    width: 100%;
  }
  .viewer-docx :deep(tr) {
    page-break-inside: avoid;
  }
  .viewer-docx :deep(td),
  .viewer-docx :deep(th) {
    border: 1px solid #999;
    padding: 4pt 6pt;
  }
  .viewer-image {
    display: block;
    text-align: center;
    padding: 0;
  }
  .viewer-image img {
    box-shadow: none;
    max-width: 100%;
    max-height: 100%;
  }
  .doc-frame {
    position: fixed;
    left: 0;
    top: 0;
    width: 100vw;
    height: 100vh;
    border: none;
  }
}
</style>
