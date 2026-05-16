from __future__ import annotations

import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from ..domain.models import ReportState
from ..integrations.bailian_adapter import BailianAdapter, fallback_synthesize
from ..parsers.background_parser import parse_background_files, render_parsed_background_markdown
from ..parsers.template_filler import (
    build_fallback_template_report,
    finalize_template_report,
    parse_template_report,
    render_report_preview_markdown,
    render_template_report,
)
from ..parsers.template_parser import extract_template_outline


class ReportWorkflow:
    def __init__(self, adapter: BailianAdapter) -> None:
        self.adapter = adapter
        graph = StateGraph(ReportState)
        graph.add_node("parse_multimodal_node", self.parse_multimodal_node)
        graph.add_node("web_search_node", self.web_search_node)
        graph.add_node("synthesize_knowledge_node", self.synthesize_knowledge_node)
        graph.add_node("generate_report_node", self.generate_report_node)
        graph.add_node("render_docx_node", self.render_docx_node)
        graph.add_edge(START, "parse_multimodal_node")
        graph.add_conditional_edges(
            "parse_multimodal_node",
            self.route_after_parse,
            {
                "web_search_node": "web_search_node",
                "synthesize_knowledge_node": "synthesize_knowledge_node",
            },
        )
        graph.add_edge("web_search_node", "synthesize_knowledge_node")
        graph.add_edge("synthesize_knowledge_node", "generate_report_node")
        graph.add_edge("generate_report_node", "render_docx_node")
        graph.add_edge("render_docx_node", END)
        self.app = graph.compile()

    def route_after_parse(self, state: ReportState) -> str:
        return "web_search_node" if state.get("search_enabled") else "synthesize_knowledge_node"

    async def ainvoke(self, state: ReportState) -> ReportState:
        return await self.app.ainvoke(state)

    async def parse_multimodal_node(self, state: ReportState) -> ReportState:
        await self._notify(state, "parse_multimodal_node", 15, "Parsing template and background files.")
        template_path = Path(state["template_path"])
        workspace = template_path.parent.parent
        outputs_dir = self._outputs_dir(template_path)
        template_text = extract_template_outline(template_path)

        background_files = [Path(path) for path in state.get("background_paths", [])]
        parsed_bundle = parse_background_files(background_files, workspace / "images")

        warning = state.get("warning", "")
        if parsed_bundle.warnings:
            warning = "\n".join(filter(None, [warning, *parsed_bundle.warnings]))

        section_descriptions: dict[str, str] = {}
        if parsed_bundle.image_refs:
            await self._notify(state, "parse_multimodal_node", 28, "Extracted images, summarizing visual evidence.")
            if self.adapter.enabled:
                try:
                    for document in parsed_bundle.documents:
                        for section in document.sections:
                            if not section.images:
                                continue
                            description = await self.adapter.vision_describe_images(
                                title=state["title"],
                                extra_info=state.get("extra_info", ""),
                                section_title=section.title,
                                section_text=section.text,
                                image_paths=[image.path for image in section.images],
                            )
                            if description:
                                section_descriptions[section.identifier] = description
                except Exception as exc:
                    warning = "\n".join(filter(None, [warning, f"Image understanding skipped: {exc}"]))
            else:
                warning = "\n".join(
                    filter(None, [warning, "Image understanding skipped: DASHSCOPE_API_KEY is not configured."])
                )

        parsed_markdown = render_parsed_background_markdown(parsed_bundle, section_descriptions)
        parsed_markdown_path = self._write_output(outputs_dir, "parsed_background.md", parsed_markdown)

        return {
            "template_text": template_text,
            "extracted_md": parsed_markdown,
            "parsed_markdown": parsed_markdown,
            "parsed_markdown_path": str(parsed_markdown_path),
            "local_image_refs": parsed_bundle.image_refs,
            "warning": warning,
        }

    async def web_search_node(self, state: ReportState) -> ReportState:
        await self._notify(state, "web_search_node", 35, "Searching for relevant experiment context.")
        query = f"{state['title']} experiment method expected result"
        warning = state.get("warning", "")
        try:
            search_results = await self.adapter.search(query)
        except Exception as exc:
            search_results = []
            fallback_warning = f"Web search skipped: {exc}"
            warning = "\n".join(filter(None, [warning, fallback_warning]))
        return {"search_contexts": search_results, "warning": warning}

    async def synthesize_knowledge_node(self, state: ReportState) -> ReportState:
        await self._notify(state, "synthesize_knowledge_node", 55, "Synthesizing experiment context.")
        template_path = Path(state["template_path"])
        outputs_dir = self._outputs_dir(template_path)
        synthesized = await self._synthesize_knowledge(state)
        synthesized_markdown = render_synthesized_knowledge_markdown(
            title=state["title"],
            synthesized=synthesized,
            image_refs=state.get("local_image_refs", []),
        )
        synthesized_markdown_path = self._write_output(outputs_dir, "synthesized_knowledge.md", synthesized_markdown)
        return {
            "synthesized_kb": synthesized,
            "synthesized_markdown": synthesized_markdown,
            "synthesized_markdown_path": str(synthesized_markdown_path),
        }

    async def generate_report_node(self, state: ReportState) -> ReportState:
        await self._notify(state, "generate_report_node", 75, "Generating structured report content.")
        report = await self._build_report(state)

        final_markdown = render_report_preview_markdown(report, state["title"])
        template_path = Path(state["template_path"])
        outputs_dir = self._outputs_dir(template_path)
        final_markdown_path = self._write_output(outputs_dir, "final_report.md", final_markdown)
        structured_report_json = json.dumps(
            {
                "cover_fields": report.cover_fields,
                "roster_fields": report.roster_fields,
                "evaluation_fields": report.evaluation_fields,
                "sections": report.sections,
                "images": report.images,
                "gallery_images": report.gallery_images,
            },
            ensure_ascii=False,
            indent=2,
        )
        report_json_path = self._write_output(outputs_dir, "report_structured.json", structured_report_json)
        return {
            "final_markdown": final_markdown,
            "final_markdown_path": str(final_markdown_path),
            "structured_report_json": structured_report_json,
            "structured_report_json_path": str(report_json_path),
        }

    async def render_docx_node(self, state: ReportState) -> ReportState:
        await self._notify(state, "render_docx_node", 90, "Rendering Word document.")
        template_path = Path(state["template_path"])
        output_path = self._outputs_dir(template_path) / "result_report.docx"
        report = parse_template_report(state["structured_report_json"])
        render_template_report(template_path, output_path, report)
        return {"output_docx_path": str(output_path)}

    async def _notify(self, state: ReportState, node: str, progress: int, message: str) -> None:
        callback = state.get("progress_callback")
        if callable(callback):
            await callback(node=node, progress=progress, message=message, warning=state.get("warning", ""))

    async def _synthesize_knowledge(self, state: ReportState) -> str:
        system_prompt = (
            "You are a careful experiment assistant. Integrate the materials into a structured summary, "
            "and never invent missing facts."
        )
        user_prompt = (
            f"Experiment title: {state['title']}\n\n"
            f"User notes: {state.get('extra_info', '')}\n\n"
            f"Template outline: {state.get('template_text', '')}\n\n"
            f"Local material: {self._state_markdown(state)}\n\n"
            f"Web search results: {json_dump(state.get('search_contexts', []))}"
        )
        synthesized = await self._chat_or_none(system_prompt, user_prompt)
        if synthesized:
            return synthesized
        return fallback_synthesize(
            title=state["title"],
            extra_info=state.get("extra_info", ""),
            extracted_md=self._state_markdown(state),
            search_results=state.get("search_contexts", []),
            template_text=state.get("template_text", ""),
        )

    async def _build_report(self, state: ReportState):
        system_prompt = (
            "You are an experiment report structuring assistant. Return valid JSON only. "
            "Fill fields from verified evidence, and use null for anything you cannot confirm."
        )
        user_prompt = (
            f"Experiment title: {state['title']}\n\n"
            f"Template outline: {state.get('template_text', '')}\n\n"
            f"Synthesized knowledge: {state.get('synthesized_kb', '')}\n\n"
            f"Parsed background material: {state.get('parsed_markdown', '')}\n\n"
            f"Available images: {json_dump(state.get('local_image_refs', []))}\n\n"
            "Return a JSON object with keys: cover_fields, roster_fields, evaluation_fields, sections, images.\n"
            "cover_fields keys: course_name, experiment_name, experiment_time, class_name, total_score, teacher_name.\n"
            "roster_fields keys: college, major, class_name, score, student_name, student_id, group_name, "
            "group_members, location, experiment_date, teacher_signature.\n"
            "evaluation_fields keys: preview_status, operation_status, attendance_status, data_processing_status.\n"
            "sections keys: objective, content, steps, sequence_components, collaboration_components, event_flow, "
            "sequence_idea, collaboration_steps, summary. Each section value must be an array of strings.\n"
            "images keys: sequence_diagram, collaboration_diagram. Values should be chosen from the available "
            "image paths when possible, otherwise null."
        )
        structured_payload = await self._chat_or_none(system_prompt, user_prompt)
        report = self._parse_structured_report(state, structured_payload)
        return finalize_template_report(
            report,
            synthesized_markdown=state.get("synthesized_markdown", ""),
            parsed_markdown=state.get("parsed_markdown", ""),
            image_refs=state.get("local_image_refs", []),
        )

    async def _chat_or_none(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self.adapter.enabled:
            return None
        try:
            return await self.adapter.chat(system_prompt, user_prompt)
        except Exception:
            return None

    def _parse_structured_report(self, state: ReportState, structured_payload: str | None):
        if structured_payload:
            try:
                return parse_template_report(extract_json_object(structured_payload))
            except Exception:
                pass
        return build_fallback_template_report(
            title=state["title"],
            extra_info=state.get("extra_info", ""),
            synthesized_context=state.get("synthesized_kb", ""),
            parsed_markdown=state.get("parsed_markdown", ""),
            image_refs=state.get("local_image_refs", []),
        )

    def _outputs_dir(self, template_path: Path) -> Path:
        outputs_dir = template_path.parent.parent / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        return outputs_dir

    def _state_markdown(self, state: ReportState) -> str:
        return state.get("parsed_markdown", state.get("extracted_md", ""))

    def _write_output(self, outputs_dir: Path, file_name: str, content: str) -> Path:
        output_path = outputs_dir / file_name
        output_path.write_text(content, encoding="utf-8")
        return output_path


def json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.replace("json", "", 1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")
    return stripped[start : end + 1]


def render_synthesized_knowledge_markdown(title: str, synthesized: str, image_refs: list[str]) -> str:
    body = synthesized.strip() or "[No synthesized knowledge generated]"
    parts = [f"# Synthesized Knowledge: {title}", body]
    image_section = build_image_appendix("Reference Images", image_refs)
    if image_section:
        parts.append(image_section)
    return "\n\n".join(parts)


def build_image_appendix(heading: str, image_refs: list[str]) -> str:
    if not image_refs:
        return ""
    lines = [f"## {heading}"]
    for image_ref in image_refs:
        path = Path(image_ref)
        lines.append(f"![{path.stem}]({path.as_posix()})")
    return "\n\n".join(lines)
