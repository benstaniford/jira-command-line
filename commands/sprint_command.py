from commands.base_command import BaseCommand
from ViewMode import ViewMode

class SprintCommand(BaseCommand):
    @property
    def shortcut(self):
        return "s"
    
    @property
    def description(self):
        return "sprint"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            view.refresh(ViewMode.SPRINT)
        except Exception as e:
            ui.error("Refresh sprint view", e)
