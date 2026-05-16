# Iteration Log

## 2026-05-17

1. Initialized the project skeleton under `backend/` and `frontend/` with `FastAPI` plus `Vue 3 + Vite`.
2. Built the backend execution chain for upload persistence, workspace isolation, task tracking, SSE progress updates, and report download.
3. Added the LangGraph workflow with:
   - `parse_multimodal_node`
   - `web_search_node`
   - `synthesize_knowledge_node`
   - `generate_report_node`
   - `render_docx_node`
4. Added the Bailian/Qwen adapter with local fallback behavior when model credentials are unavailable.
5. Implemented template outline parsing, background material parsing, and the initial markdown-based report renderer.
6. Moved task execution into a dedicated background thread to avoid request-lifecycle instability in tests.
7. Delivered the frontend upload flow, progress display, warning display, and download entry.
8. Added regression coverage for template parsing, markdown rendering, API flow, and workspace cleanup.
9. Verified:
   - `uv run pytest -q`
   - `npm run build`

## 2026-05-17 (Follow-up)

1. Improved PDF background parsing:
   - Switched from whole-page screenshots to embedded-image plus block-image extraction.
   - Persisted parsed background content to `outputs/parsed_background.md`.
   - Preserved local image paths for downstream generation.
2. Added multimodal image understanding:
   - Introduced `QWEN_VISION_MODEL`.
   - Summarized extracted images during `parse_multimodal_node`.
   - Preserved warnings when `DASHSCOPE_API_KEY` is unavailable.
3. Added a synthesized intermediate artifact:
   - Persisted cleaned synthesis output to `outputs/synthesized_knowledge.md`.
   - Added `parsed_markdown`, `parsed_markdown_path`, `synthesized_markdown`, and `synthesized_markdown_path` to workflow state.
4. Fixed live-generation failures:
   - Confirmed the workflow previously failed in `render_docx_node` with ragged markdown table input.
   - Hardened the markdown renderer against uneven rows and separator variants.
5. Preserved parsed images across markdown artifacts:
   - Appended image references to both synthesized and final markdown outputs.
   - Persisted `final_markdown_path` for debugging.
6. Expanded regression coverage and smoke validation:
   - Added parser and API tests for PDF image extraction and artifact persistence.
   - Re-ran `cd backend && uv run pytest tests -q` and reached `13 passed`.
   - Verified the example live run completed successfully and produced `result_report.docx`.

## 2026-05-17 (Template-Fill Refactor)

1. Replaced the final report generation strategy:
   - Removed the old "generate full markdown then build a new Word file" path as the authoritative output route.
   - Switched to strict template-based filling using the uploaded `.docx` as the final layout source.
2. Added structured report generation:
   - `generate_report_node` now produces structured report data instead of relying on freeform final markdown.
   - Added persisted output `outputs/report_structured.json`.
   - Kept `outputs/final_report.md` as a preview/debug artifact only.
3. Added template-native rendering:
   - Introduced `backend/src/report_backend/parsers/template_filler.py`.
   - Filled cover-table fields, roster-table fields, evaluation fields, named body sections, and image slots directly inside the template.
   - Preserved original template layout, tables, and embedded header assets.
4. Added explicit missing-data behavior:
   - Any unverified field is now rendered as `【待用户填写：字段名】`.
   - Unknown values are no longer hallucinated into the report.
5. Updated workflow state:
   - Added `structured_report_json` and `structured_report_json_path`.
6. Expanded regression coverage:
   - Added dedicated tests for strict template filling and placeholder behavior.
   - Updated API tests to validate template-preserving output.
7. Verified:
   - `cd backend && uv run pytest tests -q`
   - Result: `14 passed`
8. Performed a smoke run against the real template:
   - Generated [tmp_result_template_fill.docx](/C:/Users/blzs8/Desktop/perfect-report/example/tmp_result_template_fill.docx) from the example template.
   - Restarted the live backend and confirmed [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) returned `200`.
9. Fixed the frontend phase-status completion bug:
   - Found that the final "document render" phase only turned green if `render_docx_node` appeared in the event history.
   - Confirmed the backend terminal event uses `status = SUCCESS`, `progress = 100`, and `current_node = done`, which left the last phase visually incomplete.
   - Updated the frontend phase-state mapping so terminal success explicitly marks `render_docx_node` as done and no longer active.
10. Verified the frontend patch:
   - Ran `cd frontend && npm run build`
   - Confirmed the local frontend at [http://127.0.0.1:5173](http://127.0.0.1:5173) responded with `200`.

## 2026-05-17 (Simplification Pass)

1. Simplified the workflow orchestration code:
   - Centralized repeated adapter/fallback handling into `_chat_or_none`, `_synthesize_knowledge`, and `_parse_structured_report`.
   - Centralized output artifact creation into `_outputs_dir` and `_write_output`.
   - Kept the existing workflow order and output contracts unchanged.
2. Removed stale fallback code:
   - Deleted the unused markdown-generation fallback path from `bailian_adapter.py`.
   - Removed the unused `ensure_markdown_images` helper and its test coverage.
3. Preserved behavior with verification:
   - Ran `cd backend && uv run pytest -q`
   - Ran `cd frontend && npm run build`
   - Result: backend `15 passed`; frontend production build succeeded.
