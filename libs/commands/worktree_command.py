from .base_command import BaseCommand
from ..Claudeck import Claudeck
import subprocess

class WorktreeCommand(BaseCommand):
    def __init__(self, claudeck=None):
        self.claudeck = claudeck or Claudeck()

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
                summary = summary if summary != "" else issue.fields.summary
                if self.claudeck.can_start_sessions():
                    self.start_claudeck_session(ui, issue, summary, mygit)
                else:
                    self.start_claude_here(ui, issue, summary, mygit)
        except Exception as e:
            ui.error("Create worktree", e)
        return False

    def start_claude_here(self, ui, issue, summary, mygit):
        """Outside Claudeck: cut the worktree ourselves and hand the terminal to claude in it."""
        ui.prompt(f"Creating worktree for {issue.key} (long titles are shortened by Claude)...")
        branch, worktree_path = mygit.create_worktree_for_issue(issue.key, summary)

        ui.yield_screen()
        try:
            subprocess.run(["claude"], cwd=worktree_path)
        finally:
            ui.restore_screen()

    def start_claudeck_session(self, ui, issue, summary, mygit):
        """Inside Claudeck: ask it for a new session in a worktree it cuts and tracks.
        Claudeck names that branch itself, so the session's first job is to rename it
        to our <initials>/<key>/<summary> convention."""
        ui.prompt(f"Starting a Claudeck session for {issue.key} (long titles are shortened by Claude)...")
        branch = mygit.branch_name_for_issue(issue.key, summary)
        session_id = self.claudeck.new_session(
            self.session_prompt(issue, branch),
            directory=mygit.repo_root(),
            name=issue.key,
            worktree=True,
            focus=True,
        )
        ui.prompt_get_character(f"Started Claudeck session {session_id} for {issue.key} on {branch}. Press any key...")

    @staticmethod
    def session_prompt(issue, branch):
        return (
            f"This session is for Jira issue {issue.key}: {issue.fields.summary}\n\n"
            f"Claudeck has cut you a fresh git worktree. Before anything else, rename its branch "
            f"with `git branch -m {branch}`. Then reply with the worktree path and branch name "
            f"and wait for my instructions; don't start work on the issue yet."
        )
