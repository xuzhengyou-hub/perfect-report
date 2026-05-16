from ..core.config import settings
from ..integrations.bailian_adapter import BailianAdapter
from ..services.report_service import ReportService
from ..services.task_store import TaskStore
from ..services.workspace import WorkspaceManager


task_store = TaskStore()
workspace_manager = WorkspaceManager(settings)
adapter = BailianAdapter(settings)
report_service = ReportService(workspace_manager, task_store, adapter)
