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
        selection = ui.prompt_get_string_colored("Enter issue number")
        if selection.isdigit():
            [row, issue] = ui.get_row(int(selection)-1)
            ticket_id = getattr(issue, 'key', None)
            if not ticket_id:
                ui.error("Selected issue has no key.")
                return False
            url = f"https://testpilot/jira-search?ticket={ticket_id}"
            webbrowser.open(url)
            ui.prompt(f"Opened Testpilot for {ticket_id} in browser.")
        return True
