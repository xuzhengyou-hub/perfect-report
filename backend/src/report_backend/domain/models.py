from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing_extensions import TypedDict


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ReportState(TypedDict, total=False):
    task_id: str
    title: str
    extra_info: str
    template_path: str
    template_text: str
    background_paths: list[str]
    source_pdfs: list[str]
    source_images: list[str]
    source_texts: list[str]
    extracted_md: str
    parsed_markdown: str
    parsed_markdown_path: str
    local_image_refs: list[str]
    search_contexts: list[str]
    synthesized_kb: str
    synthesized_markdown: str
    synthesized_markdown_path: str
    final_markdown: str
    final_markdown_path: str
    structured_report_json: str
    structured_report_json_path: str
    output_docx_path: str
    warning: str
    error_msg: str
    search_enabled: bool
    progress_callback: object


@dataclass(slots=True)
class TaskSnapshot:
    task_id: str
    status: TaskStatus
    current_node: str
    progress: int
    message: str
    warning: str = ""
    output_docx_path: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    error: str | None = None

    def as_event(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "current_node": self.current_node,
            "progress": self.progress,
            "message": self.message,
            "warning": self.warning,
            "output_docx_path": self.output_docx_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "error": self.error,
        }


@dataclass(slots=True)
class TaskRecord:
    snapshot: TaskSnapshot
