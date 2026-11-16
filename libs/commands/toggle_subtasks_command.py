from .base_command import BaseCommand

class ToggleSubtasksCommand(BaseCommand):
    """Expands every epic and every issue with sub-tasks in place, or collapses them all again"""
    @property
    def shortcut(self):
        return "T"
    
    @property
    def description(self):
        return "expand all"
    
    def execute(self, ui, view, jira, **kwargs):
        ui.toggle_expand_all()
        return False
