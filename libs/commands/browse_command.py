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
            selection = ui.prompt_get_string("(s:sprintboard, l:backlog, k:kanban)\nEnter issue number", keystrokes)
            if selection == "s":
                jira.browse_sprint_board()
            if selection == "l":
                jira.browse_backlog_board()
            if selection == "k":
                jira.browse_kanban_board()
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                jira.browse_to(issue)
        except Exception as e:
            ui.error("Browse issue", e)
