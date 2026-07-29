from .base_command import BaseCommand
import subprocess

class WorktreeCommand(BaseCommand):
    @property
    def shortcut(self):
        return "w"

    @property
    def description(self):
        return "worktree"

    def execute(self, ui, view, jira, mygit=None, **kwargs):
        try:
            [selection, row, issue] = ui.prompt_get_issue()
            if issue:
                summary = ui.prompt_get_string("Enter a branch summary (default is issue summary)")
                ui.prompt(f"Creating worktree for {issue.key} (long titles are shortened by Claude)...")
                branch, worktree_path = mygit.create_worktree_for_issue(issue.key, summary if summary != "" else issue.fields.summary)

                # Hand the terminal over to claude running in the new worktree
                ui.yield_screen()
                try:
                    subprocess.run(["claude"], cwd=worktree_path)
                finally:
                    ui.restore_screen()
        except Exception as e:
            ui.error("Create worktree", e)
        return False
