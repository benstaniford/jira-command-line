from commands.base_command import BaseCommand
from ViewMode import ViewMode

class TaskViewCommand(BaseCommand):
    @property
    def shortcut(self):
        return "digit"  # Special case for numeric input
    
    @property
    def description(self):
        return "task_view"
    
    def execute(self, ui, view, jira, selection=None, **kwargs):
        try:
            if selection and selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                view.refresh(ViewMode.TASKVIEW, parent_issue=issue)
        except Exception as e:
            ui.error("Show task view", e)
        return False
