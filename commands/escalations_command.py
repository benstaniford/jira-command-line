from commands.base_command import BaseCommand
from ViewMode import ViewMode

class EscalationsCommand(BaseCommand):
    @property
    def shortcut(self):
        return "z"
    
    @property
    def description(self):
        return "escalations"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            view.refresh(ViewMode.ESCALATIONS)
        except Exception as e:
            ui.error("Refresh escalations view", e)
        return False
