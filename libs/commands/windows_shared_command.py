from .base_command import BaseCommand
from ..ViewMode import ViewMode

class WindowsSharedCommand(BaseCommand):
    @property
    def shortcut(self):
        return "w"
    
    @property
    def description(self):
        return "winshared"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            view.refresh(ViewMode.WINDOWS_SHARED)
        except Exception as e:
            ui.error("Refresh windows shared view", e)
        return False
