from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from threading import Thread

from fastapi import UploadFile

from ..domain.models import ReportState, TaskStatus
from ..integrations.bailian_adapter import BailianAdapter
from ..workflows.report_workflow import ReportWorkflow
from .task_store import TaskStore
from .workspace import WorkspaceManager


class ReportService:
    def __init__(self, workspace_manager: WorkspaceManager, task_store: TaskStore, adapter: BailianAdapter) -> None:
        self.workspace_manager = workspace_manager
        self.task_store = task_store
        self.workflow = ReportWorkflow(adapter)

    async def submit(
        self,
        *,
        title: str,
        extra_info: str,
        template_file: UploadFile,
        background_files: list[UploadFile],
    ) -> str:
        task_id, workspace = self.workspace_manager.create_workspace()
        self.task_store.create(task_id)

        template_path = await self._persist_upload(template_file, workspace / "inputs")
        background_paths = [await self._persist_upload(file, workspace / "inputs") for file in background_files]

        state: ReportState = {
            "task_id": task_id,
            "title": title,
            "extra_info": extra_info,
            "template_path": str(template_path),
            "background_paths": [str(path) for path in background_paths],
            "source_pdfs": [str(path) for path in background_paths if path.suffix.lower() == ".pdf"],
            "source_images": [str(path) for path in background_paths if path.suffix.lower() in {".png", ".jpg", ".jpeg"}],
            "source_texts": [str(path) for path in background_paths if path.suffix.lower() == ".txt"],
            "search_enabled": True,
        }
        Thread(target=self._run_in_thread, args=(task_id, state), daemon=True).start()
        return task_id

    async def _persist_upload(self, upload: UploadFile, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        safe_name = Path(upload.filename or "upload.bin").name
        target = directory / safe_name
        with target.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        await upload.close()
        return target

    async def _run(self, task_id: str, state: ReportState) -> None:
        try:
            self.task_store.update(
                task_id,
                status=TaskStatus.PROCESSING,
                current_node="starting",
                progress=5,
                message="Task started, preparing workflow.",
            )
            state["progress_callback"] = self._progress_updater(task_id)
            state = await self.workflow.ainvoke(state)

            output_path = Path(state["output_docx_path"])
            self.task_store.update(
                task_id,
                status=TaskStatus.SUCCESS,
                current_node="done",
                progress=100,
                message="Report generated successfully.",
                warning=state.get("warning", ""),
                output_docx_path=str(output_path),
                file_name=output_path.name,
                file_size=output_path.stat().st_size if output_path.exists() else None,
            )
        except Exception as exc:
            self.task_store.update(
                task_id,
                status=TaskStatus.FAILED,
                current_node="failed",
                progress=100,
                message="Task execution failed.",
                warning=state.get("warning", ""),
                error=str(exc),
            )
        finally:
            self.workspace_manager.schedule_cleanup(task_id)

    def _progress_updater(self, task_id: str):
        async def callback(*, node: str, progress: int, message: str, warning: str = "") -> None:
            self.task_store.update(
                task_id,
                current_node=node,
                progress=progress,
                message=message,
                warning=warning,
            )

        return callback

    def _run_in_thread(self, task_id: str, state: ReportState) -> None:
        asyncio.run(self._run(task_id, state))
