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
            [selection, row, issue] = ui.prompt_get_issue()
            if issue:
                inspect_issue(issue)
        except Exception as e:
            ui.error("Inspect issue", e)
        return False
