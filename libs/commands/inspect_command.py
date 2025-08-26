from .base_command import BaseCommand
from jira_utils import inspect_issue

class InspectCommand(BaseCommand):
    @property
    def shortcut(self):
        return "i"
    
    @property
    def description(self):
        return "inspect"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            selection = ui.prompt_get_string_colored("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                inspect_issue(issue)
        except Exception as e:
            ui.error("Inspect issue", e)
        return False
