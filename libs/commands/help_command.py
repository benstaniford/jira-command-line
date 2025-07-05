from .base_command import BaseCommand

class HelpCommand(BaseCommand):
    @property
    def shortcut(self):
        return "KEY_F1"
    
    @property
    def description(self):
        return "help"
    
    def execute(self, ui, view, jira, **kwargs):
        ui.disable_row_numbers()
        ui.clear()
        ui.add_header(["", "Key", "Description"])
        ui.add_row(["", "F1", "Show this help"])
        ui.add_row(["", "F2-F12", "Toggle additional columns"])
        ui.add_row(["", "Esc", "Go back"])
        ui.add_row(["", "PgDn", "Next page"])
        ui.add_row(["", "PgUp", "Previous page"])
        ui.add_row(["", "/", "Search for issue in the current view"])
        ui.add_row(["", "|", "Filter the current view based on keyword"])
        ui.add_row(["", "?", "Global search (bug numbers or title keywords)"])
        ui.add_row(["", "a", "Assign issue to user"])
        ui.add_row(["", "b", "Browse issue in browser"])
        ui.add_row(["", "B", "Show other boards"])
        ui.add_row(["", "c", "Create issue in current view"])
        ui.add_row(["", "C", "Chat about issue(s)"])
        ui.add_row(["", "d", "Delete issue in current view"])
        ui.add_row(["", "e", "Edit issue in editor"])
        ui.add_row(["", "E", "Switches between teams (if multiple teams configured)"])
        ui.add_row(["", "h", "Create branch to work on the issue"])
        ui.add_row(["", "i", "Inspect issue"])
        ui.add_row(["", "k", "Create spike issue on sprint which links to the selected issue"])
        ui.add_row(["", "l", "Show backlog issues"])
        ui.add_row(["", "m", "Move issue to sprint/backlog or change it's rank"])
        ui.add_row(["", "o", "Sort by column"])
        ui.add_row(["", "p", "Start a PR for issue on github"])
        ui.add_row(["", "P", "Set story points for issue"])
        ui.add_row(["", "q", "Quit Jira"])
        ui.add_row(["", "S", "Open support folder for issue"])
        ui.add_row(["", "s", "Show sprint issues"])
        ui.add_row(["", "t", "Change issue status"])
        ui.add_row(["", "v", "View issue in editor"])
        ui.add_row(["", "V", "Show visualisations"])
        ui.add_row(["", "T", "Toggle subtasks"])
        ui.add_row(["", "w", "Show windows shared issues"])
        ui.add_row(["", "x", "Create x-ray template or create tests in x-ray if template filled in"])
        ui.add_row(["", "z", "Show escalations"])
        ui.draw()
        ui.enable_row_numbers()
        return False
