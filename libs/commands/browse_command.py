from .base_command import BaseCommand

class BrowseCommand(BaseCommand):
    @property
    def shortcut(self):
        return "b"
    
    @property
    def description(self):
        return "browse"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            keystrokes = ('s', 'l', 'k')
            # Keep prompting even when a row is selected, so the board options stay
            # reachable; enter on an empty line browses the selected row
            [selection, row, issue] = ui.prompt_get_issue("(s:sprintboard, l:backlog, k:kanban)\nEnter issue number", keystrokes)
            if selection == "s":
                jira.browse_sprint_board()
            if selection == "l":
                jira.browse_backlog_board()
            if selection == "k":
                jira.browse_kanban_board()
            if issue:
                jira.browse_to(issue)
        except Exception as e:
            ui.error("Browse issue", e)
