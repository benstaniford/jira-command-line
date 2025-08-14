from .base_command import BaseCommand
import webbrowser

class TestpilotCommand(BaseCommand):
    @property
    def shortcut(self):
        return "t"

    @property
    def description(self):
        return "testpilot"

    def execute(self, ui, view, jira, **kwargs):
        # Get the currently selected issue
        issue = ui.get_selected_issue() if hasattr(ui, 'get_selected_issue') else None
        if not issue:
            ui.error("No issue selected.")
            return False
        ticket_id = getattr(issue, 'key', None)
        if not ticket_id:
            ui.error("Selected issue has no key.")
            return False
        url = f"https://testpilot/jira-search?ticket={ticket_id}"
        webbrowser.open(url)
        ui.prompt(f"Opened Testpilot for {ticket_id} in browser.")
        return True
