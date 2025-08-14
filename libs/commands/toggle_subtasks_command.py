from .base_command import BaseCommand

class ToggleSubtasksCommand(BaseCommand):
    @property
    def shortcut(self):
        return "T"
    
    @property
    def description(self):
        return "subtasks"
    
    def execute(self, ui, view, jira, **kwargs):
        ui.toggle_subrows()
        ui.draw()
        return False
