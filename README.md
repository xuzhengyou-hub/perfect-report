# Perfect Report

智能实验报告生成工具，支持上传实验报告模板与背景资料，基于 LangGraph 工作流生成结构化 Markdown，并渲染为可下载的 `.docx` 报告。

## 项目结构

- `backend/`: FastAPI 服务，负责文件接收、任务调度、SSE 进度推送、报告生成与 Word 渲染。
- `frontend/`: Vue 3 + Element Plus 单页界面，负责表单上传、进度展示与结果下载。
- `example/`: 示例模板、资料与参考输出。
- `reference-code/`: 设计阶段提供的参考实现。

## 已实现能力

- 上传 1 个实验报告模板 `.docx`
- 上传多个背景资料文件，支持 `.txt` / `.pdf` / `.png` / `.jpg`
- 基于 LangGraph 执行 `parse -> search -> synthesize -> generate -> render` 工作流
- 通过 SSE 实时回传任务状态、当前节点、进度与告警
- 报告输出为标准 `.docx`，支持标题、段落、Markdown 表格与图片回填
- 当百炼鉴权未配置时，自动走本地兜底生成逻辑，保证本地开发与测试可运行

## 本地运行

### 1. 启动后端

```powershell
cd backend
uv sync --dev
uv run uvicorn report_backend.main:app --reload --host 127.0.0.1 --port 8000
```

可选环境变量：

- `DASHSCOPE_API_KEY`: 阿里云百炼 API Key
- `QWEN_MODEL`: 模型名，默认 `qwen-max`
- `QWEN_BASE_URL`: 兼容模式接口地址，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

前端默认通过 Vite 代理将 `/api` 请求转发到 `http://127.0.0.1:8000`。

## 测试与构建

后端测试：

```powershell
cd backend
uv run pytest -q
```

前端构建：

```powershell
cd frontend
npm run build
```

## 说明

- `example/实验报告模板.docx` 当前是旧版 Office 二进制文档，扩展名虽为 `.docx`，但不是标准 OpenXML 包。本项目运行时要求上传标准 `.docx` 模板。
- 若联网检索失败或未配置百炼，任务不会中断，只会在 SSE 中返回告警并继续执行。
