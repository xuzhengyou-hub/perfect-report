<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheckFilled, Document, Download, Files, Loading, Promotion, UploadFilled, WarningFilled } from '@element-plus/icons-vue'

const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
const phaseDefinitions = [
  { key: 'parse_multimodal_node', label: 'Parse' },
  { key: 'web_search_node', label: 'Search' },
  { key: 'synthesize_knowledge_node', label: 'Synthesize' },
  { key: 'generate_report_node', label: 'Draft' },
  { key: 'render_docx_node', label: 'Render' },
]

const form = reactive({
  title: '',
  extraInfo: '',
})
const templateFiles = ref([])
const backgroundFiles = ref([])
const running = ref(false)
const taskId = ref('')
const taskState = ref(null)
const result = ref(null)
const eventSource = ref(null)
const eventLog = ref([])

const statusTone = computed(() => {
  const status = taskState.value?.status
  if (status === 'FAILED') return 'danger'
  if (status === 'SUCCESS') return 'success'
  return 'primary'
})

const progressValue = computed(() => taskState.value?.progress ?? 0)
const phaseItems = computed(() => {
  const current = taskState.value?.current_node
  const terminalSuccess = taskState.value?.status === 'SUCCESS'
  return phaseDefinitions.map((item) => {
    const hit = eventLog.value.find((entry) => entry.current_node === item.key)
    return {
      ...item,
      done: Boolean(hit) || (terminalSuccess && item.key === 'render_docx_node'),
      active: !terminalSuccess && current === item.key,
    }
  })
})

function resolveApi(path) {
  return apiBase ? `${apiBase}${path}` : path
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '--'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function resetTaskView() {
  taskId.value = ''
  taskState.value = null
  result.value = null
  eventLog.value = []
}

function closeEventSource() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
}

function syncTemplateFiles(_uploadFile, uploadFiles) {
  templateFiles.value = uploadFiles.slice(-1)
}

function syncBackgroundFiles(_uploadFile, uploadFiles) {
  backgroundFiles.value = uploadFiles
}

function removeTemplate() {
  templateFiles.value = []
}

function removeBackground(uploadFile) {
  backgroundFiles.value = backgroundFiles.value.filter((item) => item.uid !== uploadFile.uid)
}

function finishTask() {
  running.value = false
  closeEventSource()
}

function buildPayload() {
  const payload = new FormData()
  payload.append('title', form.title.trim())
  payload.append('extra_info', form.extraInfo.trim())
  payload.append('template_file', templateFiles.value[0].raw)
  backgroundFiles.value.forEach((file) => {
    if (file.raw) {
      payload.append('background_files', file.raw)
    }
  })
  return payload
}

async function submitTask() {
  if (!form.title.trim()) {
    ElMessage.error('Please enter an experiment title.')
    return
  }
  if (!templateFiles.value[0]?.raw) {
    ElMessage.error('Please upload a .docx template.')
    return
  }

  closeEventSource()
  resetTaskView()
  running.value = true

  try {
    const response = await fetch(resolveApi('/api/v1/report/generate'), {
      method: 'POST',
      body: buildPayload(),
    })
    const body = await response.json()
    if (!response.ok) {
      throw new Error(body.detail ?? body.message ?? 'Failed to create task.')
    }
    taskId.value = body.data.task_id
    openEventStream(body.data.task_id)
  } catch (error) {
    finishTask()
    ElMessage.error(error.message || 'Failed to create task.')
  }
}

function openEventStream(id) {
  const source = new EventSource(resolveApi(`/api/v1/report/events/${id}`))
  eventSource.value = source

  source.onmessage = (event) => {
    const payload = JSON.parse(event.data)
    taskState.value = payload
    if (!eventLog.value.some((item) => item.current_node === payload.current_node && item.progress === payload.progress)) {
      eventLog.value.push(payload)
    }
    if (payload.status === 'SUCCESS') {
      finishTask()
      result.value = {
        name: payload.file_name,
        size: formatBytes(payload.file_size),
      }
      ElMessage.success('Report generated successfully.')
    } else if (payload.status === 'FAILED') {
      finishTask()
      ElMessage.error(payload.error || 'Task failed.')
    }
  }

  source.onerror = () => {
    if (running.value) {
      finishTask()
      ElMessage.warning('Progress connection was interrupted. Please try again.')
      return
    }
    closeEventSource()
  }
}

function downloadReport() {
  if (!taskId.value) return
  window.open(resolveApi(`/api/v1/report/download/${taskId.value}`), '_blank', 'noopener,noreferrer')
}

onBeforeUnmount(() => {
  closeEventSource()
})
</script>

<template>
  <div class="app-shell">
    <main class="workspace">
      <section class="hero-band">
        <p class="eyebrow">Intelligent Report Studio</p>
        <div class="hero-copy">
          <h1>Experiment Report Generator</h1>
          <p>
            Upload a Word template, add background material, and let the workflow parse, search,
            synthesize, draft, and render a finished report.
          </p>
        </div>
        <div class="hero-metrics">
          <div>
            <span>Workflow</span>
            <strong>LangGraph</strong>
          </div>
          <div>
            <span>Output</span>
            <strong>.docx</strong>
          </div>
          <div>
            <span>Updates</span>
            <strong>SSE</strong>
          </div>
        </div>
      </section>

      <section class="tool-surface">
        <div class="surface-heading">
          <div>
            <p class="section-label">Task Input</p>
            <h2>Upload source files and start a run</h2>
          </div>
          <el-button type="primary" size="large" :loading="running" :icon="Promotion" @click="submitTask">
            {{ running ? 'Processing' : 'Generate report' }}
          </el-button>
        </div>

        <div class="form-grid">
          <label class="field">
            <span>Experiment title</span>
            <el-input
              v-model="form.title"
              size="large"
              placeholder="Enter the report title"
              :disabled="running"
            />
          </label>

          <label class="field field-wide">
            <span>Notes</span>
            <el-input
              v-model="form.extraInfo"
              type="textarea"
              :rows="6"
              resize="none"
              placeholder="Add observations, measurements, equipment details, or writing guidance"
              :disabled="running"
            />
          </label>

          <div class="field">
            <span>Template file</span>
            <el-upload
              drag
              action="#"
              :auto-upload="false"
              :limit="1"
              :file-list="templateFiles"
              accept=".docx"
              :disabled="running"
              :on-change="syncTemplateFiles"
              :on-remove="removeTemplate"
            >
              <el-icon class="upload-icon"><Document /></el-icon>
              <div class="el-upload__text">Drop or choose a .docx template</div>
            </el-upload>
          </div>

          <div class="field">
            <span>Background files</span>
            <el-upload
              drag
              action="#"
              multiple
              :auto-upload="false"
              :file-list="backgroundFiles"
              accept=".txt,.pdf,.png,.jpg,.jpeg"
              :disabled="running"
              :on-change="syncBackgroundFiles"
              :on-remove="removeBackground"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="el-upload__text">Supports .txt, .pdf, .png, and .jpg</div>
            </el-upload>
          </div>
        </div>
      </section>

      <section class="status-band">
        <div class="status-main">
          <div class="section-headline">
            <p class="section-label">Task Progress</p>
            <h2>Current status</h2>
          </div>

          <div class="status-card">
            <div class="status-topline">
              <el-tag :type="statusTone" effect="light">
                {{ taskState?.status || 'IDLE' }}
              </el-tag>
              <span class="status-node">{{ taskState?.current_node || 'waiting' }}</span>
            </div>

            <strong class="status-message">
              {{ taskState?.message || 'Fill in the form to start a new task.' }}
            </strong>

            <el-progress
              :percentage="progressValue"
              :stroke-width="10"
              :show-text="true"
              :striped="running"
              :striped-flow="running"
            />

            <p v-if="taskState?.warning" class="warning-line">
              <el-icon><WarningFilled /></el-icon>
              <span>{{ taskState.warning }}</span>
            </p>

            <p v-if="taskState?.error" class="warning-line error-line">
              <el-icon><WarningFilled /></el-icon>
              <span>{{ taskState.error }}</span>
            </p>
          </div>
        </div>

        <div class="phase-strip">
          <article
            v-for="item in phaseItems"
            :key="item.key"
            class="phase-item"
            :class="{ done: item.done, active: item.active }"
          >
            <span class="phase-icon">
              <el-icon v-if="item.done"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="item.active"><Loading /></el-icon>
              <el-icon v-else><Files /></el-icon>
            </span>
            <span>{{ item.label }}</span>
          </article>
        </div>
      </section>

      <section v-if="result" class="result-band">
        <div class="result-copy">
          <p class="section-label">Output file</p>
          <h2>{{ result.name }}</h2>
          <p>The document is ready to download and continue editing in Word.</p>
        </div>
        <div class="result-meta">
          <span>{{ result.size }}</span>
          <el-button type="success" size="large" :icon="Download" @click="downloadReport">
            Download report
          </el-button>
        </div>
      </section>
    </main>
  </div>
</template>





