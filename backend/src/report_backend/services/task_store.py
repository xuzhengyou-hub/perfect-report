from __future__ import annotations

import threading
from dataclasses import dataclass, replace

from ..domain.models import TaskRecord, TaskSnapshot, TaskStatus


@dataclass(slots=True)
class VersionedTaskRecord(TaskRecord):
    version: int = 0


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, VersionedTaskRecord] = {}
        self._lock = threading.Lock()

    def create(self, task_id: str) -> TaskSnapshot:
        snapshot = TaskSnapshot(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            current_node="queued",
            progress=0,
            message="Task created and waiting to be processed.",
        )
        with self._lock:
            self._tasks[task_id] = VersionedTaskRecord(snapshot=snapshot)
        return snapshot

    def get(self, task_id: str) -> TaskSnapshot | None:
        with self._lock:
            record = self._tasks.get(task_id)
            return replace(record.snapshot) if record else None

    def get_version(self, task_id: str) -> int | None:
        with self._lock:
            record = self._tasks.get(task_id)
            return record.version if record else None

    def update(self, task_id: str, **changes: object) -> TaskSnapshot:
        with self._lock:
            record = self._tasks[task_id]
            snapshot = replace(record.snapshot, **changes)
            record.snapshot = snapshot
            record.version += 1
            return snapshot
