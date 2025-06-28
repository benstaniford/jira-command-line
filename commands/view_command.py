from commands.base_command import BaseCommand
from jira_utils import view_description

class ViewCommand(BaseCommand):
    @property
    def shortcut(self):
        return "v"
    
    @property
    def description(self):
        return "view"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                view_description(issue, jira)
        except Exception as e:
            ui.error("View issue", e)
        return False
