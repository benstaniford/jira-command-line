from .base_command import BaseCommand

class LinkCommand(BaseCommand):
    @property
    def shortcut(self):
        return "k"
    
    @property
    def description(self):
        return "link"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            [selection, row, issue] = ui.prompt_get_issue()
            if issue:
                issue = jira.create_linked_issue_on_sprint(issue)
                ui.prompt(f"Created {issue.key}...")
                view.refresh()
        except Exception as e:
            ui.error("Create linked issue on sprint", e)
        return False
