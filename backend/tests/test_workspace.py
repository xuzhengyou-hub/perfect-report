from report_backend.core.config import Settings
from report_backend.services.workspace import WorkspaceManager


def test_workspace_cleanup(tmp_path) -> None:
    settings = Settings(data_root=tmp_path, cleanup_delay_seconds=0)
    manager = WorkspaceManager(settings)
    task_id, workspace = manager.create_workspace()
    assert workspace.exists()

    manager.schedule_cleanup(task_id)

    import time
    time.sleep(0.1)

    assert not workspace.exists()
