from .base_command import BaseCommand
from ..ViewMode import ViewMode

class BoardsCommand(BaseCommand):
    @property
    def shortcut(self):
        return "B"
    
    @property
    def description(self):
        return "boards"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            boards = jira.get_boards()
            if len(boards) == 0:
                ui.error("No boards configured in config")
                return False
            [index, board] = ui.prompt_with_choice_list("Select board", boards)
            if board != "":
                view.refresh(ViewMode.BOARD, params=board)
        except Exception as e:
            ui.error("Set board", e)
        return False
