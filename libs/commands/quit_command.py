from .base_command import BaseCommand

class QuitCommand(BaseCommand):
    @property
    def shortcut(self):
        return "q"
    
    @property
    def description(self):
        return "quit"
    
    def execute(self, ui, view, jira, **kwargs):
        ui.close()
        return True  # Signal to exit the main loop
