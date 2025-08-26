from .base_command import BaseCommand
from jira_utils import get_string_from_editor

class EditCommand(BaseCommand):
    @property
    def shortcut(self):
        return "e"
    
    @property
    def description(self):
        return "edit"
    
    def execute(self, ui, view, jira, stdscr=None, **kwargs):
        try:
            selection = ui.prompt_get_string_colored("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                [i, typeofedit] = ui.prompt_with_choice_list("Edit Actions", ["Comment"], non_numeric_keypresses = True)
                if typeofedit == "Comment":
                    comment = ui.prompt_get_string_colored("(F1 for editor)\nEnter comment")
                    if comment == "KEY_F1":
                        if stdscr:
                            stdscr.clear()
                        comment = get_string_from_editor()
                    if comment != "":
                        jira.add_comment(issue, comment)
                    view.rebuild()
        except Exception as e:
            ui.error("Edit issue", e)
        return False
