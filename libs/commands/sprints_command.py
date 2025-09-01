from .base_command import BaseCommand
from ..ViewMode import ViewMode

class SprintsCommand(BaseCommand):
    @property
    def shortcut(self):
        return "L"
    
    @property
    def description(self):
        return "sprints"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            view.refresh(ViewMode.SPRINTS)
        except Exception as e:
            ui.error("Refresh sprints view", e)