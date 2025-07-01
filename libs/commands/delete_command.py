from .base_command import BaseCommand

class DeleteCommand(BaseCommand):
    @property
    def shortcut(self):
        return "d"
    
    @property
    def description(self):
        return "delete"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                yesno = ui.prompt_get_character(f"Are you sure you want to delete {issue.key}? (y/n)")
                if yesno == "y":
                    ui.prompt(f"Deleting {issue.key}...")
                    issue.delete(deleteSubtasks=True)
                    view.refresh()
        except Exception as e:
            ui.error("Delete issue", e)
        return False
