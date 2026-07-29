from .base_command import BaseCommand
import time

class BranchCommand(BaseCommand):
    @property
    def shortcut(self):
        return "h"
    
    @property
    def description(self):
        return "branch"
    
    def execute(self, ui, view, jira, mygit=None, **kwargs):
        try:
            [selection, row, issue] = ui.prompt_get_issue()
            if issue:
                summary = ui.prompt_get_string("Enter a branch summary (default is issue summary)")
                ui.prompt(f"Creating branch for {issue.key} (long titles are shortened by Claude)...")
                branch = mygit.create_branch_for_issue(issue.key, summary if summary != "" else issue.fields.summary)
                ui.prompt(f"Created {branch}...")
                time.sleep(2)
        except Exception as e:
            ui.error("Create branch", e)
        return False
