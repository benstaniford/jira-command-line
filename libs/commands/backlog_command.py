from .base_command import BaseCommand
from ..ViewMode import ViewMode

class BacklogCommand(BaseCommand):
    @property
    def shortcut(self):
        return "l"
    
    @property
    def description(self):
        return "backlog"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            view.refresh(ViewMode.BACKLOG)
        except Exception as e:
            ui.error("Refresh backlog view", e)
