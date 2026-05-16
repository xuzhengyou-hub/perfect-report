# 技术设计文档

## 1. 设计目标

系统需要把用户上传的实验报告模板 `.docx` 作为最终版式源，结合背景资料与模型推断结果，生成一份严格保留模板结构的实验报告。

本次设计重点解决的问题是：

1. 不再新建一份自由排版 Word 文档。
2. 不再让 markdown 渲染结果决定最终版式。
3. 把模型输出限制为结构化数据，再写回模板对应位置。

## 2. 当前总体架构

### 2.1 前端

- `frontend/`
- 技术栈：`Vue 3 + Vite`
- 功能：提交任务、展示进度、展示警告、下载结果文件

### 2.2 后端

- `backend/`
- 技术栈：`FastAPI`
- 工作流编排：`LangGraph`
- 文档处理：`python-docx`
- PDF/图片提取：`PyMuPDF`

## 3. 工作流

当前 LangGraph 工作流节点如下：

1. `parse_multimodal_node`
2. `web_search_node`
3. `synthesize_knowledge_node`
4. `generate_report_node`
5. `render_docx_node`

工作流方向：

`parse_multimodal_node -> web_search_node -> synthesize_knowledge_node -> generate_report_node -> render_docx_node`

如果用户未启用搜索，则从 `parse_multimodal_node` 直接进入 `synthesize_knowledge_node`。

## 4. 状态模型

定义位于 [models.py](/C:/Users/blzs8/Desktop/perfect-report/backend/src/report_backend/domain/models.py)。

当前关键状态字段：

1. 输入侧
   - `title`
   - `extra_info`
   - `template_path`
   - `background_paths`
2. 解析产物
   - `template_text`
   - `parsed_markdown`
   - `parsed_markdown_path`
   - `local_image_refs`
3. 综合产物
   - `search_contexts`
   - `synthesized_kb`
   - `synthesized_markdown`
   - `synthesized_markdown_path`
4. 生成产物
   - `final_markdown`
   - `final_markdown_path`
   - `structured_report_json`
   - `structured_report_json_path`
   - `output_docx_path`

说明：

- `final_markdown` 现在是预览/调试产物
- `structured_report_json` 是模板填充的真实输入
- `output_docx_path` 是最终交付结果

## 5. 关键模块设计

### 5.1 模板解析

文件：

- [template_parser.py](/C:/Users/blzs8/Desktop/perfect-report/backend/src/report_backend/parsers/template_parser.py)

职责：

1. 从模板中提取可供模型参考的文本大纲
2. 不负责最终版式渲染

作用：

- 帮助模型理解模板结构
- 为结构化生成提供上下文

### 5.2 背景资料解析

文件：

- [background_parser.py](/C:/Users/blzs8/Desktop/perfect-report/backend/src/report_backend/parsers/background_parser.py)

职责：

1. 识别背景文件类型
2. 解析文本文件
3. 解析 PDF 文本
4. 提取 PDF 中的嵌入图像和 block 图像
5. 生成 `parsed_background.md`
6. 汇总本地图像引用路径

输出：

- `ParsedBackgroundBundle`
- `parsed_markdown`
- `local_image_refs`

### 5.3 模型适配层

文件：

- [bailian_adapter.py](/C:/Users/blzs8/Desktop/perfect-report/backend/src/report_backend/integrations/bailian_adapter.py)

职责：

1. 文本对话
2. 网络搜索
3. 图像理解
4. 无密钥场景下的本地 fallback

当前约束：

- 若模型可用，则优先尝试结构化 JSON 输出
- 若模型失败或不可用，则使用本地规则构建 `TemplateReport`

### 5.4 模板填充器

文件：

- [template_filler.py](/C:/Users/blzs8/Desktop/perfect-report/backend/src/report_backend/parsers/template_filler.py)

这是本次重构新增的核心模块。

#### 5.4.1 数据模型

核心结构：

- `TemplateReport`

包含五类信息：

1. `cover_fields`
2. `roster_fields`
3. `evaluation_fields`
4. `sections`
5. `images`

#### 5.4.2 主要职责

1. 解析结构化 JSON 为 `TemplateReport`
2. 在模型不可用时构建 fallback 结构化报告
3. 基于模板原位写回字段
4. 在正文锚点间替换旧占位内容
5. 在指定段落后插入图片
6. 将缺失值转换为 `【待用户填写：字段名】`

#### 5.4.3 当前模板定位策略

当前实现假设模板满足以下结构：

1. 第 1 个表格为封面字段表
2. 第 2 个表格为学生/课程信息表
3. 第 3 个表格为考核情况表
4. 正文区域存在稳定锚点段落，例如：
   - `实验目的`
   - `实验内容`
   - `实验步骤`
   - `序列图组成`
   - `协作图组成`
   - `事件流`
   - `序列图的基本思路`
   - `协作图的操作步骤`
   - `实验小结`

优点：

- 对当前学校模板足够稳定
- 不需要重新建文档

限制：

- 对明显不同结构的模板不具备通用适配能力

### 5.5 工作流生成节点

文件：

- [report_workflow.py](/C:/Users/blzs8/Desktop/perfect-report/backend/src/report_backend/workflows/report_workflow.py)

#### 5.5.1 `generate_report_node`

旧行为：

- 让模型直接输出整篇 markdown

新行为：

1. 尝试让模型输出结构化 JSON
2. 若失败则走 fallback 结构化生成
3. 落盘：
   - `outputs/final_report.md`
   - `outputs/report_structured.json`

说明：

- `final_report.md` 仅用于查看生成内容，不用于最终 docx 版式控制

#### 5.5.2 `render_docx_node`

旧行为：

- `render_markdown_to_docx(state["final_markdown"], output_path)`

新行为：

1. 读取 `structured_report_json`
2. 解析为 `TemplateReport`
3. 调用 `render_template_report(template_path, output_path, report)`

结果：

- 最终 `.docx` 直接保留模板版式

## 6. 文件产物设计

每个任务工作区目录结构：

```text
workspace/
  inputs/
  images/
  outputs/
    parsed_background.md
    synthesized_knowledge.md
    final_report.md
    report_structured.json
    result_report.docx
```

各文件用途：

1. `parsed_background.md`
   - 资料解析结果
2. `synthesized_knowledge.md`
   - 综合后的知识中间稿
3. `final_report.md`
   - 调试预览稿
4. `report_structured.json`
   - 模板填充输入
5. `result_report.docx`
   - 最终交付物

## 7. 缺失信息策略

### 7.1 原则

不编造。

### 7.2 实现方式

若字段为空，则渲染为：

- `【待用户填写：课程名称】`
- `【待用户填写：班级】`
- `【待用户填写：学号】`

适用范围：

1. 表格字段
2. 正文区段
3. 评估信息

## 8. 测试设计

测试位于：

- [test_api.py](/C:/Users/blzs8/Desktop/perfect-report/backend/tests/test_api.py)
- [test_template_filler.py](/C:/Users/blzs8/Desktop/perfect-report/backend/tests/test_template_filler.py)

覆盖重点：

1. API 端到端流程
2. 中间产物落盘
3. 模板保留与原位填充
4. 缺失值占位行为
5. 图片插入行为

最近验证结果：

```text
cd backend
uv run pytest tests -q
14 passed
```

## 9. 已知限制

1. 目前模板定位是针对现有实验报告模板定制的。
2. 若模板表格顺序变化较大，当前映射需要调整。
3. 若正文锚点文本变化明显，当前定位逻辑需要补充映射规则。
4. 结构化字段仍依赖模型或规则提取质量，无法凭空补齐学生专属信息。

## 10. 后续演进方向

1. 增加模板映射配置文件，支持多模板。
2. 生成“待用户填写字段清单”供前端展示。
3. 增加模板结构自动探测与校验。
4. 在前端提供模板填充前后差异预览。
