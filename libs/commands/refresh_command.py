from .base_command import BaseCommand

class RefreshCommand(BaseCommand):
    @property
    def shortcut(self):
        return "r"

    @property
    def description(self):
        return "refresh"

    def execute(self, ui, view, jira, stdscr=None, **kwargs):
        view.refresh()
        return False
