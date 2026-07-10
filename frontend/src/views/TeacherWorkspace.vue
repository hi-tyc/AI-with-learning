<template>
  <div class="workspace-page">
    <div class="teacher-workspace">
      <aside class="teacher-rail">
        <div class="rail-brand">
          <el-icon size="20"><School /></el-icon>
          <strong>StudyBuddy</strong>
          <el-tag size="small" type="success" effect="dark">英语</el-tag>
        </div>
        <div class="rail-caption">功能</div>
        <div class="rail-section">
          <button
            v-for="item in teacherNavItems"
            :key="item.id"
            class="rail-item"
            type="button"
            :class="{ active: activeSection === item.id || (item.id === 'classes' && activeSection === 'class-detail') }"
            @click="changeSection(item.id)"
          >
            <el-icon :size="18"><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
            <em v-if="item.count !== undefined">{{ item.count }}</em>
          </button>
        </div>
        <div class="rail-foot">
          <el-icon size="34"><Collection /></el-icon>
          <strong>英语教学模式</strong>
          <span>进入班级后可直接拍照上传、分发资料、登记完成和错题。</span>
        </div>
        <div class="rail-account">
          <div>
            <strong>{{ auth.displayName || auth.user?.username }}</strong>
            <span>{{ auth.user?.username }} · {{ auth.isAdmin ? '管理员' : '教师' }}</span>
          </div>
          <div class="rail-account-actions">
            <el-tooltip v-if="auth.isAdmin" content="管理员工作台" placement="top">
              <el-button text circle :icon="DataBoard" aria-label="管理员工作台" @click="router.push('/admin')" />
            </el-tooltip>
            <el-tooltip content="系统设置" placement="top">
              <el-button text circle :icon="Setting" aria-label="系统设置" @click="router.push('/settings/system')" />
            </el-tooltip>
            <el-tooltip content="个人资料" placement="top">
              <el-button text circle :icon="User" aria-label="个人资料" @click="router.push('/settings/profile')" />
            </el-tooltip>
            <el-tooltip content="退出登录" placement="top">
              <el-button text circle :icon="SwitchButton" aria-label="退出登录" @click="logout" />
            </el-tooltip>
          </div>
        </div>
      </aside>

      <main class="teacher-main">
        <div class="page-header">
          <div>
            <h1>{{ pageTitle }}</h1>
            <p>{{ pageSubtitle }}</p>
          </div>
          <div class="header-actions">
            <el-button v-if="activeSection === 'class-detail'" @click="changeSection('classes')">返回班级</el-button>
            <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
          </div>
        </div>

    <el-row v-show="activeSection !== 'upload' && activeSection !== 'class-detail'" :gutter="16" class="summary-row">
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">班型</div>
          <div class="summary-value">{{ summary.class_type_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">班级</div>
          <div class="summary-value">{{ summary.class_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">分发记录</div>
          <div class="summary-value">{{ summary.distribution_count || 0 }}</div>
        </div>
      </el-col>
      <el-col :md="6" :sm="12" :xs="24">
        <div class="summary-panel">
          <div class="summary-label">覆盖学生</div>
          <div class="summary-value">{{ summary.student_total || 0 }}</div>
        </div>
      </el-col>
    </el-row>

    <section v-show="activeSection === 'classes' || activeSection === 'class-detail'" class="surface class-context-surface">
      <div v-if="activeSection === 'classes'" class="class-browser">
        <div class="surface-header">
          <h2>我的班级</h2>
          <span>选择一个班级进入上下文工作区。</span>
        </div>
        <div class="class-card-grid">
          <button
            v-for="item in classes"
            :key="item.id"
            class="class-card"
            type="button"
            @click="openClassContext(item)"
          >
            <span class="class-type">{{ item.class_type_name || '未分班型' }}</span>
            <strong>{{ item.name }}</strong>
            <span>{{ classStudentCount(item) }} 名学生 · {{ (item.teacher_usernames || []).join('、') || '未指定教师' }}</span>
          </button>
          <div v-if="classes.length === 0" class="empty-state">暂无班级</div>
        </div>
      </div>

      <div v-else-if="selectedClass" class="class-detail">
        <div class="class-detail-grid">
          <div class="class-primary">
            <div class="surface-header compact">
              <h2>班级上传</h2>
              <span>{{ selectedClass.class_type_name || '未分班型' }} / {{ selectedClass.name }}</span>
            </div>
            <div
              class="upload-dropzone class-dropzone"
              @click="triggerFilePicker"
              @dragover.prevent
              @drop.prevent="onDropFiles"
            >
              <el-icon size="42"><UploadFilled /></el-icon>
              <strong>拖入文件或点击上传</strong>
              <span>默认上传到当前班级，可用拍照上传课堂资料、学生作业和订正记录。</span>
            </div>
            <div v-if="uploadForm.files.length" class="pending-files class-pending-files">
              <div v-for="(file, index) in uploadForm.files" :key="`${file.name}-${index}`" class="pending-file">
                <span>{{ file.name }}</span>
                <el-button text size="small" type="danger" @click="removePendingFile(index)">移除</el-button>
              </div>
            </div>
            <div class="class-actions">
              <el-button type="primary" :icon="Camera" @click="triggerCameraUpload">拍照上传</el-button>
              <el-button :disabled="uploadForm.files.length === 0" :loading="uploading" @click="uploadMaterial">
                上传 {{ uploadForm.files.length }} 份到本班
              </el-button>
              <el-button :disabled="classDistributionMaterialIds.length === 0" @click="createClassDistribution">
                分发 {{ classDistributionMaterialIds.length }} 份资料
              </el-button>
            </div>
          </div>
          <div class="class-secondary">
            <h3>学生名单</h3>
            <div class="student-chip-list">
              <span v-for="student in selectedClass.students || []" :key="student.id || student.name">{{ student.name }}</span>
              <em v-if="!selectedClass.students?.length">暂无学生</em>
            </div>
            <h3>班级记录</h3>
            <div class="class-record-actions">
              <el-button size="small" :disabled="!latestClassDistribution" @click="openClassCompletion">登记完成</el-button>
              <el-button size="small" :disabled="!latestClassDistribution" @click="openClassWrong">登记错题</el-button>
              <el-button size="small" type="primary" :icon="MagicStick" :disabled="!latestClassDistribution" @click="openClassAutoGrade">AI 批改</el-button>
            </div>
            <div class="class-distribution-list">
              <div v-for="item in classScopedDistributions" :key="item.id" class="class-distribution-item">
                <strong>{{ formatTime(item.assigned_at) }}</strong>
                <span>{{ item.material_ids?.length || 0 }} 份资料 · 错题 {{ item.stats?.wrong_count || 0 }} · 完成 {{ item.stats?.completion_count || 0 }} · AI 批改 {{ item.stats?.auto_grade_count || 0 }}</span>
              </div>
              <div v-if="!classScopedDistributions.length" class="empty-state">暂无本班分发记录</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div v-show="activeSection === 'upload'" class="page-grid upload-layout">
      <section class="surface upload-surface">
        <div class="surface-header">
          <h2>上传设置</h2>
          <span>支持多层标签路径，例如 `初一南外/周四下午/暑假讲义`</span>
        </div>
        <el-form label-position="top" class="upload-form">
          <el-form-item label="标签路径">
            <el-input v-model="uploadForm.tag" placeholder="初一南外/周四下午/暑假讲义" />
          </el-form-item>
          <el-form-item label="资料类型">
            <el-select v-model="uploadForm.docType" style="width:100%">
              <el-option label="资料" value="资料" />
              <el-option label="题目" value="题目" />
              <el-option label="答案" value="答案" />
              <el-option label="词单" value="词单" />
            </el-select>
          </el-form-item>
          <el-form-item label="上传位置">
            <el-radio-group v-model="uploadForm.scope">
              <el-radio-button label="personal">个人资料</el-radio-button>
              <el-radio-button label="class">班级</el-radio-button>
              <el-radio-button label="class_type">班型</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="uploadForm.scope === 'class'" label="选择班级">
            <el-select v-model="uploadForm.classId" filterable clearable style="width:100%">
              <el-option
                v-for="item in classes"
                :key="item.id"
                :label="item.class_type_name ? `${item.class_type_name} / ${item.name}` : item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="uploadForm.scope === 'class_type'" label="选择班型">
            <el-select v-model="uploadForm.classTypeId" filterable clearable style="width:100%">
              <el-option v-for="item in classTypes" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="文件" class="upload-file-item">
            <input
              ref="fileInputRef"
              type="file"
              accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
              multiple
              style="display:none"
              @change="onFileChange"
            />
            <input
              ref="cameraInputRef"
              type="file"
              accept="image/*"
              capture="environment"
              style="display:none"
              @change="onCameraFileChange"
            />
            <div
              class="upload-dropzone"
              @click="triggerFilePicker"
              @dragover.prevent
              @drop.prevent="onDropFiles"
            >
              <el-icon size="44"><UploadFilled /></el-icon>
              <strong>选择文件上传</strong>
              <span>支持 PDF、Word（docx）、JPG / PNG 图片，可多选</span>
            </div>
            <div class="upload-quick-actions">
              <el-button :icon="UploadFilled" @click="triggerFilePicker">选择文件</el-button>
              <el-button :icon="Camera" @click="triggerCameraUpload">拍照上传</el-button>
            </div>
            <div v-if="uploadForm.files.length" class="pending-files">
              <div v-for="(file, index) in uploadForm.files" :key="`${file.name}-${index}`" class="pending-file">
                <span>{{ file.name }}</span>
                <el-button text size="small" type="danger" @click="removePendingFile(index)">移除</el-button>
              </div>
            </div>
          </el-form-item>
          <div v-if="failedUploadFiles.length" class="failed-files">
            <div class="failed-title">上传失败</div>
            <div v-for="(item, index) in failedUploadFiles" :key="`${item.file.name}-${index}`" class="failed-file">
              <span>{{ item.file.name }}：{{ item.error }}</span>
              <el-button text size="small" type="warning" :disabled="uploading" @click="retryUpload(item, index)">重试</el-button>
            </div>
          </div>
          <el-form-item class="upload-submit-item">
            <el-button type="primary" :disabled="uploadForm.files.length === 0" :loading="uploading" @click="uploadMaterial">
              上传 {{ uploadForm.files.length }} 份资料
            </el-button>
          </el-form-item>
        </el-form>
        <div v-if="uploadResults.length" class="upload-results">
          <div class="result-title">上传结果</div>
          <div v-for="item in uploadResults" :key="item.id" class="upload-result">
            <div>
              <div class="result-name">{{ item.filename }}</div>
              <div class="result-meta">
                <el-tag size="small" :type="docTypeTagType(item.doc_type)">{{ item.doc_type || '资料' }}</el-tag>
                <span v-if="item.classification">
                  {{ item.classification.source === 'kimi' ? 'Kimi 分类' : '规则分类' }}
                  · {{ Math.round((item.classification.confidence || 0) * 100) }}%
                </span>
                <span v-if="item.classification?.reason">{{ item.classification.reason }}</span>
              </div>
            </div>
            <div class="result-actions">
              <el-button text size="small" :loading="classifyingIds.has(item.id)" @click="classifyUploadedMaterial(item)">
                AI 分类
              </el-button>
              <el-button text size="small" @click="openTypeDialog(item)">调整类型</el-button>
            </div>
          </div>
        </div>
      </section>

      <section class="surface">
        <div class="surface-header">
          <h2>批量分发</h2>
          <span>先勾选资料，再选择班型或班级。</span>
        </div>
        <el-form label-position="top">
          <el-form-item label="分发范围">
            <el-radio-group v-model="distributionForm.targetType">
              <el-radio-button label="class">班级</el-radio-button>
              <el-radio-button label="class_type">班型</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="distributionForm.targetType === 'class' ? '选择班级' : '选择班型'">
            <el-select v-model="distributionForm.targetIds" multiple filterable style="width:100%">
              <el-option
                v-for="item in distributionOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="distributionForm.note" type="textarea" :rows="3" placeholder="例如：本周课堂讲义 + 课后订正" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :disabled="distributionMaterialIds.length === 0" @click="createDistribution">
              分发 {{ distributionMaterialIds.length }} 份资料
            </el-button>
          </el-form-item>
        </el-form>
      </section>
    </div>

    <section v-show="activeSection === 'library'" class="surface">
      <div class="surface-header">
        <h2>资料库</h2>
        <span>支持查看原文件、单份打印与批量打印。</span>
      </div>
      <div class="table-actions">
        <el-button size="small" @click="selectedTagPath = ''">查看全部</el-button>
        <el-button size="small" :disabled="selectedMaterialRows.length === 0" @click="batchPrint">批量打印</el-button>
      </div>
      <div class="materials-panel">
        <div class="tag-tree-panel">
          <div class="tree-title">标签目录</div>
          <el-tree
            :data="tagTree"
            node-key="path"
            default-expand-all
            :props="{ label: 'name', children: 'children' }"
            @node-click="handleTagNodeClick"
          >
            <template #default="{ data }">
              <div class="tree-node">
                <span>{{ data.name }}</span>
                <span class="tree-count">{{ data.count }}</span>
              </div>
            </template>
          </el-tree>
        </div>
        <div class="materials-table-panel">
          <div v-if="selectedTagPath" class="selected-path">当前标签：{{ selectedTagPath }}</div>
          <el-table :data="filteredMaterials" stripe @selection-change="onMaterialSelectionChange">
            <el-table-column type="selection" width="46" />
            <el-table-column prop="filename" label="文件名" min-width="260" />
            <el-table-column prop="tag" label="标签路径" min-width="220" />
            <el-table-column prop="created_at" label="上传时间" width="180">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button text size="small" @click="openDocument(row)">查看</el-button>
                <el-button text size="small" @click="printOne(row)">打印</el-button>
                <el-button text size="small" type="danger" @click="deleteMaterial(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </section>

    <section v-show="activeSection === 'stats'" class="surface">
      <div class="surface-header">
        <h2>分发与统计</h2>
        <span>可登记已完成部分、AI 自动批改并查看正确率与错误学生。</span>
      </div>
      <div class="table-actions">
        <el-button size="small" @click="exportMergedWrongBook">整合导出错题本</el-button>
        <el-button size="small" @click="exportMergedWrongBookDocx">整合导出 Word</el-button>
        <el-button size="small" @click="exportMergedSummary">整合导出正确率总表</el-button>
      </div>
      <el-table :data="distributions" stripe>
        <el-table-column prop="assigned_at" label="分发时间" width="180">
          <template #default="{ row }">{{ formatTime(row.assigned_at) }}</template>
        </el-table-column>
        <el-table-column label="范围" min-width="180">
          <template #default="{ row }">{{ row.target_names?.join('、') || '-' }}</template>
        </el-table-column>
        <el-table-column label="资料数" width="90">
          <template #default="{ row }">{{ row.material_ids?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="学生数" width="90">
          <template #default="{ row }">{{ row.stats?.student_total || 0 }}</template>
        </el-table-column>
        <el-table-column label="错题登记" width="100">
          <template #default="{ row }">{{ row.stats?.wrong_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="完成记录" width="100">
          <template #default="{ row }">{{ row.stats?.completion_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="AI 批改" width="90">
          <template #default="{ row }">{{ row.stats?.auto_grade_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="正确率总表" min-width="280">
          <template #default="{ row }">
            <div v-if="row.stats?.problem_stats?.length" class="problem-stats">
              <div v-for="item in row.stats.problem_stats.slice(0, 3)" :key="item.problem_ref">
                <div class="problem-line">
                  <span>{{ item.problem_ref }}：{{ (item.correct_rate * 100).toFixed(0) }}%，错 {{ item.wrong_students.join('、') || '-' }}</span>
                  <span class="problem-actions">
                    <el-button v-if="item.explanation" text size="small" @click="openExplanationDialog(row, item)">查看解析</el-button>
                    <el-button text size="small" :loading="explanationLoadingKey === explanationKey(row, item)" @click="generateExplanation(row, item, !!item.explanation)">
                      {{ item.explanation ? '重新生成' : '生成解析' }}
                    </el-button>
                  </span>
                </div>
              </div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="openCompletionDialog(row)">登记完成</el-button>
            <el-button text size="small" @click="openWrongDialog(row)">登记错题</el-button>
            <el-button text size="small" type="primary" @click="openAutoGradeDialog(row)">AI 批改</el-button>
            <el-button text size="small" @click="openExportDialog(row)">导出错题</el-button>
            <el-button text size="small" @click="exportDistributionSummary(row)">导出总表</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
      </main>
    </div>

    <el-dialog v-model="completionDialog.visible" title="登记完成情况" width="520px">
      <el-form label-position="top">
        <el-form-item label="学生姓名">
          <el-select v-model="completionDialog.studentName" filterable allow-create default-first-option style="width:100%">
            <el-option v-for="item in completionDialog.students" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="已完成部分">
          <el-input v-model="completionDialog.partsText" type="textarea" :rows="3" placeholder="例如：阅读 A、B；完形前 10 题" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="completionDialog.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completionDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitCompletion">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="wrongDialog.visible" title="登记错题本" width="520px">
      <el-form label-position="top">
        <el-form-item label="学生姓名">
          <el-select v-model="wrongDialog.studentName" filterable allow-create default-first-option style="width:100%">
            <el-option v-for="item in wrongDialog.students" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目标识/题干">
          <el-input v-model="wrongDialog.problemRef" placeholder="例如：阅读理解 2 / 讲义第 3 题，也可直接粘贴题干" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="wrongDialog.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="wrongDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitWrongBook">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="autoGradeDialog.visible" title="AI 自动批改" width="min(680px, calc(100vw - 24px))" destroy-on-close>
      <input
        ref="autoGradeAnswerInputRef"
        type="file"
        accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
        style="display:none"
        @change="onAutoGradeFileChange($event, 'answer')"
      />
      <input
        ref="autoGradeSubmissionInputRef"
        type="file"
        accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
        style="display:none"
        @change="onAutoGradeFileChange($event, 'submission')"
      />
      <el-form label-position="top">
        <el-form-item label="学生">
          <el-select v-model="autoGradeDialog.studentName" filterable style="width:100%">
            <el-option v-for="item in autoGradeDialog.students" :key="item.id || item.name" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准答案">
          <div class="auto-grade-select-row">
            <el-select v-model="autoGradeDialog.answerMaterialId" filterable style="width:100%" placeholder="选择已上传的答案">
              <el-option
                v-for="item in autoGradeMaterials"
                :key="item.id"
                :label="`${item.filename} · ${item.doc_type || '资料'}`"
                :value="item.id"
              />
            </el-select>
            <el-button :icon="UploadFilled" :loading="autoGradeDialog.answerUploading" @click="triggerAutoGradeUpload('answer')">上传答案</el-button>
          </div>
        </el-form-item>
        <el-form-item label="学生作答">
          <div class="auto-grade-select-row">
            <el-select v-model="autoGradeDialog.submissionMaterialId" filterable style="width:100%" placeholder="选择作答照片或文档">
              <el-option
                v-for="item in autoGradeMaterials"
                :key="item.id"
                :label="`${item.filename} · ${item.doc_type || '资料'}`"
                :value="item.id"
              />
            </el-select>
            <el-button :icon="Camera" :loading="autoGradeDialog.submissionUploading" @click="triggerAutoGradeUpload('submission')">上传作答</el-button>
          </div>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="autoGradeDialog.replaceExisting">重新批改时替换同一份作答的旧错题</el-checkbox>
        </el-form-item>
      </el-form>
      <div v-if="autoGradeDialog.result" class="auto-grade-result">
        <div class="auto-grade-result-header">
          <strong>批改结果</strong>
          <span v-if="autoGradeDialog.result.score !== null && autoGradeDialog.result.score !== undefined">得分 {{ autoGradeDialog.result.score }}</span>
        </div>
        <p>{{ autoGradeDialog.result.summary || 'AI 已完成比对。' }}</p>
        <div class="auto-grade-result-meta">
          <span>识别 {{ autoGradeDialog.result.recognized_count || 0 }} 题</span>
          <span>自动登记 {{ autoGradeDialog.result.wrong_count || 0 }} 条错题</span>
          <span v-if="autoGradeDialog.result.ungraded_count">待人工确认 {{ autoGradeDialog.result.ungraded_count }} 题</span>
        </div>
        <div v-if="autoGradeDialog.result.wrong_items?.length" class="auto-grade-result-items">
          <div v-for="item in autoGradeDialog.result.wrong_items" :key="item.problem_ref" class="auto-grade-result-item">
            <strong>{{ item.problem_ref }}</strong>
            <span>{{ item.reason || '答案与标准答案不一致' }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="autoGradeDialog.visible = false">关闭</el-button>
        <el-button
          type="primary"
          :icon="MagicStick"
          :loading="autoGradeDialog.loading"
          @click="submitAutoGrade"
        >
          开始批改并登记错题
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog.visible" title="导出错题本" width="480px">
      <el-form label-position="top">
        <el-form-item label="导出范围">
          <el-radio-group v-model="exportDialog.mode">
            <el-radio-button label="all">当前分发全部学生</el-radio-button>
            <el-radio-button label="student">单个学生</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="exportDialog.mode === 'student'" label="学生姓名">
          <el-select v-model="exportDialog.studentName" filterable allow-create default-first-option style="width:100%">
            <el-option v-for="item in exportDialog.students" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportDialog.visible = false">取消</el-button>
        <el-button @click="submitWrongBookDocxExport">下载 Word 包</el-button>
        <el-button type="primary" @click="submitWrongBookExport">下载 CSV</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="explanationDialog.visible" title="AI 解析" width="640px">
      <div class="explanation-meta">
        <div>题目：{{ explanationDialog.problemRef }}</div>
        <div v-if="explanationDialog.model">模型：{{ explanationDialog.model }}</div>
        <div v-if="explanationDialog.generatedAt">生成时间：{{ formatTime(explanationDialog.generatedAt) }}</div>
      </div>
      <div class="explanation-content">{{ explanationDialog.content }}</div>
      <template #footer>
        <el-button @click="explanationDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="typeDialog.visible" title="调整资料类型" width="460px">
      <el-form label-position="top">
        <el-form-item label="文件">
          <el-input :model-value="typeDialog.filename" disabled />
        </el-form-item>
        <el-form-item label="资料类型">
          <el-select v-model="typeDialog.docType" style="width:100%">
            <el-option label="题目" value="题目" />
            <el-option label="答案" value="答案" />
            <el-option label="词单" value="词单" />
            <el-option label="资料" value="资料" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="typeDialog.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitTypeUpdate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera, Collection, DataBoard, Files, MagicStick, Notebook, Refresh, School, Setting, SwitchButton, UploadFilled, User } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const fileInputRef = ref(null)
const cameraInputRef = ref(null)
const autoGradeAnswerInputRef = ref(null)
const autoGradeSubmissionInputRef = ref(null)
const summary = ref({})
const classTypes = ref([])
const classes = ref([])
const materials = ref([])
const tagTree = ref([])
const distributions = ref([])
const uploading = ref(false)
const failedUploadFiles = ref([])
const uploadResults = ref([])
const classifyingIds = ref(new Set())
const selectedMaterialRows = ref([])
const selectedTagPath = ref('')
const activeSection = ref('upload')
const selectedClassId = ref('')
const dataLoaded = ref(false)

const uploadForm = ref({
  tag: '',
  docType: '资料',
  scope: 'personal',
  classId: '',
  classTypeId: '',
  files: [],
})

const distributionForm = ref({
  targetType: 'class',
  targetIds: [],
  note: '',
})

const completionDialog = ref({
  visible: false,
  distributionId: '',
  students: [],
  studentName: '',
  partsText: '',
  note: '',
})

const wrongDialog = ref({
  visible: false,
  distributionId: '',
  students: [],
  studentName: '',
  problemRef: '',
  note: '',
})

const autoGradeDialog = ref({
  visible: false,
  distributionId: '',
  classId: '',
  classTypeId: '',
  students: [],
  studentName: '',
  answerMaterialId: '',
  submissionMaterialId: '',
  replaceExisting: true,
  answerUploading: false,
  submissionUploading: false,
  loading: false,
  result: null,
})

const exportDialog = ref({
  visible: false,
  distributionId: '',
  students: [],
  mode: 'all',
  studentName: '',
})

const explanationDialog = ref({
  visible: false,
  problemRef: '',
  content: '',
  model: '',
  generatedAt: '',
})

const typeDialog = ref({
  visible: false,
  materialId: '',
  filename: '',
  docType: '资料',
  reason: '',
})

const explanationLoadingKey = ref('')

const selectedMaterialIds = computed(() => selectedMaterialRows.value.map(item => item.id))
const uploadedMaterialIds = computed(() => uploadResults.value.map(item => item.id).filter(Boolean))
const distributionMaterialIds = computed(() => selectedMaterialIds.value.length ? selectedMaterialIds.value : uploadedMaterialIds.value)
const distributionOptions = computed(() => (distributionForm.value.targetType === 'class' ? classes.value : classTypes.value))
const filteredMaterials = computed(() => {
  if (!selectedTagPath.value) return materials.value
  return materials.value.filter(item => (item.tag || '').startsWith(selectedTagPath.value))
})
const selectedClass = computed(() => classes.value.find(item => item.id === selectedClassId.value) || null)
const classScopedDistributions = computed(() => {
  if (!selectedClassId.value) return []
  return distributions.value.filter(item => item.target_type === 'class' && (item.target_ids || []).includes(selectedClassId.value))
})
const latestClassDistribution = computed(() => classScopedDistributions.value[0] || null)
const classUploadResultIds = computed(() => {
  if (!selectedClassId.value) return []
  return uploadResults.value
    .filter(item => item.class_id === selectedClassId.value)
    .map(item => item.id)
    .filter(Boolean)
})
const classDistributionMaterialIds = computed(() => selectedMaterialIds.value.length ? selectedMaterialIds.value : classUploadResultIds.value)
const autoGradeScope = computed(() => {
  const classId = autoGradeDialog.value.classId || selectedClass.value?.id || ''
  const classItem = classes.value.find(item => item.id === classId) || selectedClass.value
  const classTypeId = autoGradeDialog.value.classTypeId || classItem?.class_type_id || selectedClass.value?.class_type_id || ''
  const classType = classTypes.value.find(item => item.id === classTypeId)
  return {
    classId,
    classTypeId,
    className: classItem?.name || '',
    classTypeName: classItem?.class_type_name || classType?.name || '',
  }
})
const autoGradeMaterials = computed(() => materials.value.filter(item => {
  if (item.subject && item.subject !== '英语') return false
  return !autoGradeScope.value.classId || !item.class_id || item.class_id === autoGradeScope.value.classId
}))
const teacherNavItems = computed(() => [
  { id: 'upload', label: '上传资料', icon: UploadFilled, count: uploadForm.value.files.length || undefined },
  { id: 'classes', label: '班级', icon: School, count: classes.value.length },
  { id: 'library', label: '资料库', icon: Files, count: materials.value.length },
  { id: 'stats', label: '错题与统计', icon: Notebook, count: distributions.value.length },
])
const pageTitle = computed(() => {
  if (activeSection.value === 'class-detail' && selectedClass.value) return selectedClass.value.name
  if (activeSection.value === 'classes') return '我的班级'
  if (activeSection.value === 'library') return '资料库'
  if (activeSection.value === 'stats') return '错题与统计'
  return '上传资料'
})
const pageSubtitle = computed(() => {
  if (activeSection.value === 'class-detail' && selectedClass.value) {
    return `${selectedClass.value.class_type_name || '未分班型'} · ${classStudentCount(selectedClass.value)} 名学生`
  }
  if (activeSection.value === 'classes') return '进入自己所属的班级，直接拍照上传、分发资料并登记学习情况。'
  if (activeSection.value === 'library') return '按自定义多层标签查找、查看和批量打印英语资料。'
  if (activeSection.value === 'stats') return '登记完成部分与错题，查看正确率、错误学生并导出总表。'
  return '上传英语试卷、讲义或课堂照片，Kimi 自动判断资料类型，再批量分发给班型或班级。'
})

const sectionRoutes = {
  upload: '/teacher',
  classes: '/teacher/classes',
  library: '/teacher/library',
  stats: '/teacher/stats',
}

function formatTime(value) {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

function docTypeTagType(type) {
  if (type === '题目') return 'primary'
  if (type === '答案') return 'success'
  if (type === '词单') return 'warning'
  return 'info'
}

function changeSection(section) {
  const target = sectionRoutes[section] || '/teacher'
  if (route.path !== target) {
    router.push(target)
  } else {
    activeSection.value = section
    selectedClassId.value = ''
  }
}

function classStudentCount(item) {
  return (item?.students || []).length
}

function applyClassContext(item) {
  selectedClassId.value = item.id
  activeSection.value = 'class-detail'
  uploadForm.value.scope = 'class'
  uploadForm.value.classId = item.id
  uploadForm.value.classTypeId = item.class_type_id || ''
  uploadForm.value.tag = `${item.class_type_name || '班型'}/${item.name}`
  distributionForm.value.targetType = 'class'
  distributionForm.value.targetIds = [item.id]
}

function openClassContext(item) {
  applyClassContext(item)
  router.push(`/teacher/classes/${encodeURIComponent(item.id)}`)
}

function syncRouteContext() {
  const classId = route.params.classId ? String(route.params.classId) : ''
  if (classId) {
    const item = classes.value.find(row => row.id === classId)
    if (item) {
      applyClassContext(item)
    } else if (dataLoaded.value) {
      selectedClassId.value = ''
      activeSection.value = 'classes'
      ElMessage.warning('班级不存在或当前账号无权访问')
      router.replace('/teacher/classes')
    }
    return
  }

  selectedClassId.value = ''
  if (route.path === '/teacher/classes') activeSection.value = 'classes'
  else if (route.path === '/teacher/library') activeSection.value = 'library'
  else if (route.path === '/teacher/stats') activeSection.value = 'stats'
  else activeSection.value = 'upload'
}

function onFileChange(event) {
  addPendingFiles(Array.from(event.target.files || []))
}

function onCameraFileChange(event) {
  addPendingFiles(Array.from(event.target.files || []))
  if (cameraInputRef.value) cameraInputRef.value.value = ''
}

function addPendingFiles(files) {
  if (!files.length) return
  const existingKeys = new Set(uploadForm.value.files.map(file => `${file.name}:${file.size}:${file.lastModified}`))
  for (const file of files) {
    const key = `${file.name}:${file.size}:${file.lastModified}`
    if (!existingKeys.has(key)) {
      uploadForm.value.files.push(file)
      existingKeys.add(key)
    }
  }
}

function triggerFilePicker() {
  fileInputRef.value?.click()
}

function removePendingFile(index) {
  uploadForm.value.files.splice(index, 1)
}

function triggerCameraUpload() {
  cameraInputRef.value?.click()
}

function onDropFiles(event) {
  addPendingFiles(Array.from(event.dataTransfer?.files || []))
}

function onMaterialSelectionChange(rows) {
  selectedMaterialRows.value = rows
}

async function loadAll() {
  const [summaryRes, classTypesRes, classesRes, materialsRes, tagTreeRes, distributionsRes] = await Promise.all([
    axios.get('/school/summary'),
    axios.get('/school/class-types'),
    axios.get('/school/classes'),
    axios.get('/materials'),
    axios.get('/materials/tag-tree'),
    axios.get('/school/distributions'),
  ])
  summary.value = summaryRes.data
  classTypes.value = classTypesRes.data.items || []
  classes.value = classesRes.data.items || []
  materials.value = (materialsRes.data.items || []).sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  tagTree.value = tagTreeRes.data.items || []
  distributions.value = distributionsRes.data.items || []
  dataLoaded.value = true
  syncRouteContext()
}

function handleTagNodeClick(node) {
  selectedTagPath.value = node.path || ''
}

function buildUploadForm(file) {
  const form = new FormData()
  form.append('file', file)
  form.append('subject', '英语')
  form.append('time', new Date().toISOString().slice(0, 10))
  form.append('tag', uploadForm.value.tag || '未分类')
  form.append('doc_type', uploadForm.value.docType || '资料')
  if (uploadForm.value.scope === 'class') {
    form.append('class_id', uploadForm.value.classId || '')
  } else if (uploadForm.value.scope === 'class_type') {
    form.append('class_type_id', uploadForm.value.classTypeId || '')
  }
  return form
}

function validateUploadScope() {
  if (uploadForm.value.scope === 'class' && !uploadForm.value.classId) {
    ElMessage.warning('请选择班级')
    return false
  }
  if (uploadForm.value.scope === 'class_type' && !uploadForm.value.classTypeId) {
    ElMessage.warning('请选择班型')
    return false
  }
  return true
}

async function uploadOneFile(file) {
  const res = await axios.post('/materials', buildUploadForm(file))
  return res.data
}

async function uploadMaterial() {
  if (!uploadForm.value.files.length || !validateUploadScope()) return
  uploading.value = true
  failedUploadFiles.value = []
  try {
    let successCount = 0
    for (const file of uploadForm.value.files) {
      try {
        const material = await uploadOneFile(file)
        uploadResults.value.unshift(material)
        successCount++
        classifyUploadedMaterial(material)
      } catch (e) {
        failedUploadFiles.value.push({
          file,
          error: e.response?.data?.detail || '上传失败',
        })
      }
    }
    if (successCount) {
      ElMessage.success(`已上传 ${successCount} 份资料`)
    }
    uploadForm.value.files = failedUploadFiles.value.map(item => item.file)
    if (fileInputRef.value) fileInputRef.value.value = ''
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function retryUpload(item, index) {
  if (!validateUploadScope()) return
  uploading.value = true
  try {
    const material = await uploadOneFile(item.file)
    uploadResults.value.unshift(material)
    classifyUploadedMaterial(material)
    failedUploadFiles.value.splice(index, 1)
    uploadForm.value.files = uploadForm.value.files.filter(file => file !== item.file)
    ElMessage.success('重试上传成功')
    await loadAll()
  } catch (e) {
    failedUploadFiles.value[index] = {
      file: item.file,
      error: e.response?.data?.detail || '上传失败',
    }
    ElMessage.error(failedUploadFiles.value[index].error)
  } finally {
    uploading.value = false
  }
}

function replaceUploadResult(material) {
  const index = uploadResults.value.findIndex(item => item.id === material.id)
  if (index >= 0) {
    uploadResults.value[index] = material
  } else {
    uploadResults.value.unshift(material)
  }
  const materialIndex = materials.value.findIndex(item => item.id === material.id)
  if (materialIndex >= 0) {
    materials.value[materialIndex] = material
  }
}

function setClassifying(id, active) {
  const next = new Set(classifyingIds.value)
  if (active) next.add(id)
  else next.delete(id)
  classifyingIds.value = next
}

async function classifyUploadedMaterial(material) {
  if (!material?.id) return
  setClassifying(material.id, true)
  try {
    const res = await axios.post(`/materials/${material.id}/classify`)
    replaceUploadResult(res.data.material || { ...material, doc_type: res.data.doc_type })
    await loadAll()
  } catch (e) {
    ElMessage.warning(e.response?.data?.detail || 'AI 分类失败，可手动调整类型')
  } finally {
    setClassifying(material.id, false)
  }
}

function openTypeDialog(material) {
  typeDialog.value = {
    visible: true,
    materialId: material.id,
    filename: material.filename,
    docType: material.doc_type || '资料',
    reason: '',
  }
}

async function submitTypeUpdate() {
  try {
    const res = await axios.patch(`/materials/${typeDialog.value.materialId}/type`, {
      doc_type: typeDialog.value.docType,
      reason: typeDialog.value.reason,
    })
    replaceUploadResult(res.data.material)
    typeDialog.value.visible = false
    ElMessage.success('资料类型已更新')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function createDistribution() {
  try {
    await axios.post('/school/distributions', {
      material_ids: distributionMaterialIds.value,
      target_type: distributionForm.value.targetType,
      target_ids: distributionForm.value.targetIds,
      tag_path: uploadForm.value.tag || '',
      note: distributionForm.value.note,
    })
    ElMessage.success('分发成功')
    distributionForm.value.targetIds = []
    distributionForm.value.note = ''
    selectedMaterialRows.value = []
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '分发失败')
  }
}

async function createClassDistribution() {
  if (!selectedClass.value) return
  if (!classDistributionMaterialIds.value.length) {
    ElMessage.warning('请先上传或选择资料')
    return
  }
  distributionForm.value.targetType = 'class'
  distributionForm.value.targetIds = [selectedClass.value.id]
  if (!distributionForm.value.note) {
    distributionForm.value.note = `${selectedClass.value.name} 班级资料`
  }
  try {
    await axios.post('/school/distributions', {
      material_ids: classDistributionMaterialIds.value,
      target_type: 'class',
      target_ids: [selectedClass.value.id],
      tag_path: uploadForm.value.tag || '',
      note: distributionForm.value.note,
    })
    ElMessage.success('已分发到当前班级')
    selectedMaterialRows.value = []
    distributionForm.value.note = ''
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '分发失败')
  }
}

function openClassCompletion() {
  if (!latestClassDistribution.value) return
  openCompletionDialog(latestClassDistribution.value)
}

function openClassWrong() {
  if (!latestClassDistribution.value) return
  openWrongDialog(latestClassDistribution.value)
}

function openClassAutoGrade() {
  if (!latestClassDistribution.value) return
  openAutoGradeDialog(latestClassDistribution.value)
}

function openAutoGradeDialog(row) {
  const targetClass = row.target_type === 'class'
    ? classes.value.find(item => (row.target_ids || []).includes(item.id))
    : null
  const contextClassId = targetClass?.id || selectedClass.value?.id || ''
  const defaultAnswer = materials.value.find(item => (
    item.doc_type === '答案'
    && (!item.subject || item.subject === '英语')
    && (!contextClassId || !item.class_id || item.class_id === contextClassId)
  ))
  autoGradeDialog.value = {
    visible: true,
    distributionId: row.id,
    classId: contextClassId,
    classTypeId: targetClass?.class_type_id || (row.target_type === 'class_type' ? (row.target_ids || [])[0] || '' : selectedClass.value?.class_type_id || ''),
    students: row.students || [],
    studentName: '',
    answerMaterialId: defaultAnswer?.id || '',
    submissionMaterialId: '',
    replaceExisting: true,
    answerUploading: false,
    submissionUploading: false,
    loading: false,
    result: null,
  }
}

function triggerAutoGradeUpload(role) {
  if (role === 'submission' && !autoGradeDialog.value.studentName) {
    ElMessage.warning('请先选择学生')
    return
  }
  if (!autoGradeScope.value.classId && !autoGradeScope.value.classTypeId) {
    ElMessage.warning('当前分发缺少班级或班型范围，无法归档上传资料')
    return
  }
  if (role === 'answer') autoGradeAnswerInputRef.value?.click()
  else autoGradeSubmissionInputRef.value?.click()
}

function buildAutoGradeUploadForm(file, docType, role) {
  const form = new FormData()
  const scope = autoGradeScope.value
  const className = scope.className || scope.classTypeName || '班级'
  const classTypeName = scope.classTypeName || '班型'
  const studentName = autoGradeDialog.value.studentName || (role === 'answer' ? '标准答案' : '学生作答')
  form.append('file', file)
  form.append('subject', '英语')
  form.append('time', new Date().toISOString().slice(0, 10))
  form.append('tag', `${classTypeName}/${className}/AI批改/${studentName}`)
  form.append('doc_type', docType)
  if (scope.classId) form.append('class_id', scope.classId)
  else if (scope.classTypeId) form.append('class_type_id', scope.classTypeId)
  return form
}

async function onAutoGradeFileChange(event, role) {
  const [file] = Array.from(event.target.files || [])
  event.target.value = ''
  if (!file) return
  const loadingKey = role === 'answer' ? 'answerUploading' : 'submissionUploading'
  const materialKey = role === 'answer' ? 'answerMaterialId' : 'submissionMaterialId'
  autoGradeDialog.value[loadingKey] = true
  try {
    const res = await axios.post('/materials', buildAutoGradeUploadForm(file, role === 'answer' ? '答案' : '资料', role))
    autoGradeDialog.value[materialKey] = res.data.id
    autoGradeDialog.value.result = null
    ElMessage.success(role === 'answer' ? '标准答案已上传' : '学生作答已上传')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    autoGradeDialog.value[loadingKey] = false
  }
}

async function submitAutoGrade() {
  if (!autoGradeDialog.value.studentName) {
    ElMessage.warning('请选择学生')
    return
  }
  if (!autoGradeDialog.value.answerMaterialId || !autoGradeDialog.value.submissionMaterialId) {
    ElMessage.warning('请同时选择标准答案和学生作答')
    return
  }
  autoGradeDialog.value.loading = true
  try {
    const res = await axios.post(`/school/distributions/${autoGradeDialog.value.distributionId}/auto-grade`, {
      student_name: autoGradeDialog.value.studentName,
      answer_material_id: autoGradeDialog.value.answerMaterialId,
      submission_material_id: autoGradeDialog.value.submissionMaterialId,
      replace_existing: autoGradeDialog.value.replaceExisting,
    })
    autoGradeDialog.value.result = res.data.grade
    ElMessage.success(res.data.message || 'AI 批改完成')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'AI 批改失败')
  } finally {
    autoGradeDialog.value.loading = false
  }
}

function openDocument(row) {
  router.push({
    path: '/document-viewer',
    query: {
      fileId: row.id,
      fileType: row.file_type,
      fileName: encodeURIComponent(row.filename || ''),
    },
  })
}

function printOne(row) {
  window.open(`#/document-viewer?fileId=${row.id}&fileType=${row.file_type}&fileName=${encodeURIComponent(encodeURIComponent(row.filename || ''))}&action=print`, '_blank')
}

function batchPrint() {
  selectedMaterialRows.value.forEach(printOne)
}

function openExportDialog(row) {
  exportDialog.value = {
    visible: true,
    distributionId: row.id,
    students: row.students || [],
    mode: 'all',
    studentName: '',
  }
}

function downloadUrl(url) {
  window.open(url, '_blank', 'noopener')
}

function submitWrongBookExport() {
  const studentQuery = exportDialog.value.mode === 'student' && exportDialog.value.studentName
    ? `?student_name=${encodeURIComponent(exportDialog.value.studentName)}`
    : ''
  downloadUrl(`/api/school/distributions/${exportDialog.value.distributionId}/exports/wrong-book.csv${studentQuery}`)
  exportDialog.value.visible = false
}

function submitWrongBookDocxExport() {
  const studentQuery = exportDialog.value.mode === 'student' && exportDialog.value.studentName
    ? `?student_name=${encodeURIComponent(exportDialog.value.studentName)}`
    : ''
  downloadUrl(`/api/school/distributions/${exportDialog.value.distributionId}/exports/wrong-book.docx.zip${studentQuery}`)
  exportDialog.value.visible = false
}

function exportDistributionSummary(row) {
  downloadUrl(`/api/school/distributions/${row.id}/exports/correctness-summary.csv`)
}

function exportMergedWrongBook() {
  downloadUrl('/api/school/exports/wrong-book.csv')
}

function exportMergedWrongBookDocx() {
  downloadUrl('/api/school/exports/wrong-book.docx.zip')
}

function exportMergedSummary() {
  downloadUrl('/api/school/exports/correctness-summary.csv')
}

function explanationKey(row, item) {
  return `${row.id}:${item.problem_ref}`
}

function openExplanationDialog(row, item) {
  explanationDialog.value = {
    visible: true,
    problemRef: item.problem_ref,
    content: item.explanation || '',
    model: item.explanation_model || '',
    generatedAt: item.explanation_generated_at || '',
  }
}

async function generateExplanation(row, item, force = false) {
  const key = explanationKey(row, item)
  explanationLoadingKey.value = key
  try {
    const res = await axios.post(`/school/distributions/${row.id}/explanations`, {
      problem_ref: item.problem_ref,
      force,
    })
    ElMessage.success(res.data.message || 'AI 解析已生成')
    await loadAll()
    explanationDialog.value = {
      visible: true,
      problemRef: item.problem_ref,
      content: res.data.explanation?.content || '',
      model: res.data.explanation?.model || '',
      generatedAt: res.data.explanation?.generated_at || '',
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '生成解析失败')
  } finally {
    explanationLoadingKey.value = ''
  }
}

async function deleteMaterial(row) {
  try {
    await ElMessageBox.confirm(`确定删除资料「${row.filename}」？`, '提示', { type: 'warning' })
    await axios.delete(`/materials/${row.id}`)
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

function openCompletionDialog(row) {
  completionDialog.value = {
    visible: true,
    distributionId: row.id,
    students: row.students || [],
    studentName: '',
    partsText: '',
    note: '',
  }
}

function openWrongDialog(row) {
  wrongDialog.value = {
    visible: true,
    distributionId: row.id,
    students: row.students || [],
    studentName: '',
    problemRef: '',
    note: '',
  }
}

async function submitCompletion() {
  try {
    await axios.post(`/school/distributions/${completionDialog.value.distributionId}/completion`, {
      student_name: completionDialog.value.studentName,
      completed_parts: completionDialog.value.partsText.split(/[，,\n]/).map(item => item.trim()).filter(Boolean),
      note: completionDialog.value.note,
    })
    ElMessage.success('已登记完成情况')
    completionDialog.value.visible = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function submitWrongBook() {
  try {
    await axios.post(`/school/distributions/${wrongDialog.value.distributionId}/wrong-book`, {
      student_name: wrongDialog.value.studentName,
      problem_ref: wrongDialog.value.problemRef,
      note: wrongDialog.value.note,
    })
    ElMessage.success('已登记错题本')
    wrongDialog.value.visible = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function logout() {
  await auth.logout()
  router.push('/login')
}

watch(() => route.fullPath, () => {
  if (dataLoaded.value) syncRouteContext()
})

onMounted(loadAll)
</script>

<style scoped>
.workspace-page {
  padding: 0;
  min-height: calc(100vh - 0px);
  background: #f8fafc;
}
.teacher-workspace {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  min-height: 100vh;
}
.teacher-rail {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 8px 12px;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
}
.rail-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px 14px;
  border-bottom: 1px solid #e2e8f0;
  color: #0f172a;
}
.rail-brand strong {
  flex: 1;
  color: #1e3a5f;
}
.rail-caption {
  padding: 0 12px;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}
.rail-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rail-item {
  width: 100%;
  height: 46px;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #334155;
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.rail-item:hover,
.rail-item.active {
  background: #eaf3ff;
  color: #2563eb;
}
.rail-item em {
  min-width: 24px;
  padding: 2px 6px;
  border-radius: 999px;
  background: #eef2f7;
  color: #64748b;
  text-align: center;
  font-style: normal;
  font-size: 12px;
}
.rail-item.active em {
  background: #dbeafe;
  color: #1d4ed8;
}
.rail-foot {
  margin-top: auto;
  min-height: 150px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
  padding: 18px;
  border-top: 1px solid #e2e8f0;
  color: #0f172a;
  text-align: center;
}
.rail-foot .el-icon {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  background: #ecfdf5;
  color: #10b981;
}
.rail-foot span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}
.rail-account {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 8px 0;
  border-top: 1px solid #e2e8f0;
}
.rail-account > div:first-child {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rail-account strong,
.rail-account span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rail-account span {
  color: #94a3b8;
  font-size: 11px;
}
.rail-account-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.rail-account-actions :deep(.el-button) {
  margin: 0;
  color: #64748b;
}
.teacher-main {
  min-width: 0;
  width: min(1500px, 100%);
  margin: 0 auto;
  padding: 28px 30px 42px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header,
.surface-header,
.table-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-header h1,
.surface-header h2 {
  margin: 0;
}
.page-header h1 {
  color: #1e293b;
  font-size: 28px;
  line-height: 1.25;
}
.page-header p,
.surface-header span {
  margin: 6px 0 0;
  color: #64748b;
}
.surface-header.compact {
  align-items: flex-start;
}
.summary-row {
  margin-bottom: 0;
}
.summary-panel,
.surface {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 18px;
}
.summary-label {
  color: #64748b;
  font-size: 13px;
}
.summary-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 700;
  color: #0f172a;
}
.page-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.upload-layout {
  grid-template-columns: minmax(0, 1.65fr) minmax(300px, 0.75fr);
  align-items: start;
}
.upload-layout > .surface:last-child .surface-header {
  align-items: flex-start;
  flex-direction: column;
  gap: 2px;
}
.upload-surface {
  padding: 0;
  border: 0;
  background: transparent;
}
.class-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.class-card {
  min-height: 130px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 18px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  text-align: left;
  cursor: pointer;
}
.class-card:hover {
  border-color: #93c5fd;
  background: #f8fbff;
}
.class-card strong {
  font-size: 22px;
}
.class-card span:last-child {
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}
.class-type {
  padding: 3px 8px;
  border-radius: 999px;
  background: #eaf3ff;
  color: #2563eb;
  font-size: 12px;
}
.class-detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.75fr);
  gap: 18px;
}
.class-primary,
.class-secondary {
  min-width: 0;
}
.class-actions,
.class-record-actions,
.upload-quick-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}
.student-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0 18px;
}
.student-chip-list span {
  padding: 5px 9px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #334155;
  font-size: 13px;
}
.student-chip-list em,
.empty-state {
  color: #94a3b8;
  font-style: normal;
}
.class-distribution-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.class-distribution-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}
.class-distribution-item span {
  color: #64748b;
  font-size: 13px;
}
.materials-panel {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
}
.tag-tree-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  max-height: 520px;
  overflow: auto;
}
.materials-table-panel {
  min-width: 0;
}
.tree-title,
.selected-path {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 10px;
}
.tree-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.tree-count {
  color: #94a3b8;
  font-size: 12px;
}
.upload-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
  margin-top: 14px;
}
.upload-file-item,
.upload-submit-item,
.upload-form > .failed-files {
  grid-column: 1 / -1;
}
.upload-file-item {
  grid-row: 1;
}
:deep(.upload-file-item .el-form-item__label) {
  display: none;
}
:deep(.upload-file-item .el-form-item__content) {
  display: block;
}
.upload-dropzone {
  width: 100%;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  border: 2px dashed #d8e2f0;
  border-radius: 8px;
  background: #fbfdff;
  color: #2563eb;
  cursor: pointer;
}
.upload-dropzone > .el-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  background: #eff6ff;
}
.upload-dropzone strong {
  color: #0f172a;
  font-size: 20px;
}
.upload-dropzone span {
  max-width: 420px;
  color: #64748b;
  text-align: center;
  line-height: 1.6;
}
.upload-dropzone:hover {
  border-color: #60a5fa;
  background: #f8fbff;
}
.class-dropzone {
  min-height: 320px;
  margin-top: 14px;
}
.class-pending-files {
  max-height: 190px;
  overflow: auto;
}
.pending-files,
.failed-files {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pending-file,
.failed-file {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 13px;
}
.failed-title {
  color: #b45309;
  font-weight: 600;
  font-size: 13px;
}
.failed-file {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #9a3412;
}
.upload-results {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.result-title {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}
.upload-result {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}
.result-name {
  font-weight: 600;
  color: #0f172a;
  word-break: break-all;
}
.result-meta {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
}
.result-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 4px;
}
.problem-stats {
  font-size: 12px;
  line-height: 1.6;
}
.problem-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 0;
}
.problem-actions {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  gap: 4px;
}
.explanation-meta {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  color: #64748b;
  font-size: 13px;
}
.explanation-content {
  white-space: pre-wrap;
  line-height: 1.8;
  color: #0f172a;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
}
.auto-grade-select-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}
.auto-grade-result {
  display: grid;
  gap: 10px;
  margin-top: 8px;
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #f8fbff;
}
.auto-grade-result-header,
.auto-grade-result-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.auto-grade-result-header strong {
  color: #0f172a;
}
.auto-grade-result-header span,
.auto-grade-result-meta {
  color: #2563eb;
  font-size: 13px;
}
.auto-grade-result p {
  margin: 0;
  color: #475569;
  line-height: 1.65;
}
.auto-grade-result-meta {
  justify-content: flex-start;
  flex-wrap: wrap;
}
.auto-grade-result-items {
  display: flex;
  max-height: 180px;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
}
.auto-grade-result-item {
  display: grid;
  grid-template-columns: minmax(84px, auto) minmax(0, 1fr);
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
}
.auto-grade-result-item strong {
  color: #1d4ed8;
}
.auto-grade-result-item span {
  color: #475569;
  font-size: 13px;
  line-height: 1.5;
}
@media (max-width: 960px) {
  .teacher-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .teacher-rail {
    position: sticky;
    top: 0;
    z-index: 20;
    height: auto;
    gap: 8px;
    padding: 10px 12px;
    border-right: 0;
    border-bottom: 1px solid #e2e8f0;
  }
  .rail-brand {
    padding: 0 2px 8px;
    border-bottom: 0;
  }
  .rail-caption,
  .rail-foot,
  .rail-account {
    display: none;
  }
  .rail-section {
    flex-direction: row;
    gap: 6px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .rail-section::-webkit-scrollbar {
    display: none;
  }
  .rail-item {
    min-width: 138px;
    height: 42px;
  }
  .teacher-main {
    width: 100%;
    max-width: 100%;
    padding: 18px 14px 32px;
  }
  .page-grid {
    grid-template-columns: 1fr;
  }
  .materials-panel {
    grid-template-columns: 1fr;
  }
  .class-card-grid,
  .class-detail-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .page-header,
  .surface-header,
  .table-actions {
    align-items: flex-start;
    flex-direction: column;
  }
  .header-actions,
  .table-actions {
    width: 100%;
  }
  .upload-form {
    grid-template-columns: 1fr;
  }
  .upload-file-item,
  .upload-submit-item,
  .upload-form > .failed-files {
    grid-column: 1;
  }
  .upload-dropzone,
  .class-dropzone {
    min-height: 240px;
  }
  .upload-result {
    flex-direction: column;
  }
  .auto-grade-select-row,
  .auto-grade-result-item {
    grid-template-columns: 1fr;
  }
  .auto-grade-result-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
