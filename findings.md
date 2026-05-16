# Findings

## Current Repo State
- `background_parser.py` currently converts each PDF page to a rendered PNG and appends page text plus image links into a single markdown string.
- `BailianAdapter` only supports text chat and web search. There is no vision-specific request path.
- `ReportWorkflow.parse_multimodal_node()` currently returns `extracted_md` and `local_image_refs`, but it does not persist a standalone markdown artifact.

## External Findings
- PyMuPDF supports extracting embedded PDF images via `Page.get_images()` and `Document.extract_image()`.
- PyMuPDF text dictionaries can expose image blocks from `Page.get_text("dict")`, which is useful when `get_images()` misses inline-style content.
- DashScope's OpenAI-compatible multimodal API supports image inputs through `image_url` payload items, which can be supplied as data URLs.

## Implementation Notes
- Keep parser output structured long enough to attach multimodal image descriptions before rendering markdown.
- Preserve `local_image_refs` as real reusable assets for later report rendering.
- Keep `extracted_md` temporarily aligned with `parsed_markdown` for compatibility during the migration.
- Reused PDF images can appear twice through different PyMuPDF surfaces (`get_images()` and block dictionaries), so content-hash deduplication is required in addition to xref deduplication.
- The parser now writes a stable `outputs/parsed_background.md` artifact even when no vision model is configured.

## Follow-up Findings
- `synthesize_knowledge_node()` is the first point where parsed local material and optional web-search results are both available in one cleaned output.
- The generated report currently consumes `synthesized_kb` directly, so the most conservative extension is to persist that same payload as markdown and pass its path alongside the existing field.
- The new artifact contract uses `outputs/synthesized_knowledge.md`, plus `synthesized_markdown` and `synthesized_markdown_path` in workflow state.
- Keeping `synthesized_kb` unchanged avoids broad downstream edits while still exposing a stable markdown artifact for inspection and reuse.
- The live failure was not in `synthesize_knowledge_node`; it reproduced one step later in `render_docx_node` with `list index out of range`.
- The crash source was markdown table rendering that assumed uniform column counts, which model output does not guarantee.
- Parsed image references existed all along, but model-generated synthesized/final markdown could drop or mangle them, so explicit image appendices are the safest persistence mechanism.
