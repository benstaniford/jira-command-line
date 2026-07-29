from .base_command import BaseCommand
import webbrowser

class TestpilotCommand(BaseCommand):
    @property
    def shortcut(self):
        return "P"

    @property
    def description(self):
        return "testpilot"

    def execute(self, ui, view, jira, **kwargs):
        # Get the currently selected issue
        [selection, row, issue] = ui.prompt_get_issue()
        if issue:
            ticket_id = getattr(issue, 'key', None)
            if not ticket_id:
                ui.error("Selected issue has no key.")
                return False
            url = f"https://testpilot/jira-search?ticket={ticket_id}"
            webbrowser.open(url)
            ui.prompt(f"Opened Testpilot for {ticket_id} in browser.")
        return False
