from __future__ import annotations

import shutil
import time
from pathlib import Path
from threading import Thread
from uuid import uuid4

from ..core.config import Settings


class WorkspaceManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.data_root.mkdir(parents=True, exist_ok=True)

    def create_workspace(self) -> tuple[str, Path]:
        task_id = str(uuid4())
        workspace = self.settings.data_root / task_id
        for child in ("inputs", "images", "outputs"):
            (workspace / child).mkdir(parents=True, exist_ok=True)
        return task_id, workspace

    def get_workspace(self, task_id: str) -> Path:
        return self.settings.data_root / task_id

    def schedule_cleanup(self, task_id: str) -> None:
        Thread(target=self._cleanup_after_delay, args=(task_id,), daemon=True).start()

    def _cleanup_after_delay(self, task_id: str) -> None:
        time.sleep(self.settings.cleanup_delay_seconds)
        workspace = self.get_workspace(task_id)
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
