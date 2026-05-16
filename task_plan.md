# Task Plan

## Goal
Implement a new PDF parsing pipeline that extracts original images from PDFs, uses multimodal understanding inside the parsing node, writes a stable Markdown intermediate artifact, and passes both markdown content and path to downstream workflow nodes.

## Follow-up Goal
After the parse node and optional web-search node have produced their inputs, make the knowledge reorganization/alignment stage persist its cleaned synthesized output as a second stable Markdown artifact.

## Decisions
- PDFs with extractable images should emit one file per original image, not page screenshots.
- The parsing node performs multimodal image understanding directly.
- OCR is out of scope for this change.
- Markdown handoff uses both `parsed_markdown` content and `parsed_markdown_path`.
- `PyMuPDF` remains the primary PDF library unless validation proves a coverage gap.

## Phases
- [x] Phase 1: Initialize planning files and sync the current state
- [x] Phase 2: Refactor PDF parsing for original-image extraction and structured sections
- [x] Phase 3: Add multimodal vision support in the adapter
- [x] Phase 4: Wire parsed markdown artifact through workflow and state
- [x] Phase 5: Add regression coverage and verify end-to-end behavior
- [x] Phase 6: Design the synthesized-knowledge markdown artifact contract
- [x] Phase 7: Persist the synthesized-knowledge markdown artifact in workflow/state
- [x] Phase 8: Add regression coverage for the synthesized artifact and verify behavior
- [x] Phase 9: Fix render-stage crash on ragged markdown tables from model output
- [x] Phase 10: Preserve parsed image references through synthesized/final markdown outputs

## Acceptance Criteria
- PDFs with embedded or block images produce extracted image assets instead of default page screenshots.
- The parsing stage writes `parsed_background.md` into the workspace outputs directory.
- Workflow state includes both `parsed_markdown` and `parsed_markdown_path`.
- Image understanding warnings are preserved when no multimodal key is configured.
- Existing report generation still succeeds with text-only background material.
- The knowledge synthesis stage writes a second markdown artifact after reorganization/alignment completes.
- The synthesized artifact contains the cleaned knowledge passed to report generation.
- Workflow state exposes both the synthesized markdown content and its artifact path.

## Errors Encountered
| Error | Attempt | Resolution |
| --- | --- | --- |
| Ran pytest from `backend/` using `backend/tests/...` paths | 1 | Re-ran from the same directory using `tests/...` paths. |
| Block-image extraction duplicated an already extracted embedded image | 1 | Added SHA-1 digest deduplication across embedded and block image paths. |
| Block-image helper wrote into a missing directory in unit tests | 1 | Ensured the helper creates `image_dir` before writing files. |
| End-to-end synthesized artifact assertion failed on a hard-coded Chinese title string | 1 | Replaced the assertion with a stable markdown-prefix plus body-content check. |
| Live report generation failed in `render_docx_node` with `list index out of range` | 1 | Made markdown table rendering tolerant of ragged model-generated rows and added regression coverage. |
| Final markdown could omit images even though parse outputs contained them | 1 | Added synthesized/final markdown image appendices so parsed image references are preserved end-to-end. |
