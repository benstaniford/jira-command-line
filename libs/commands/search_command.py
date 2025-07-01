from .base_command import BaseCommand
from ..ViewMode import ViewMode

class SearchCommand(BaseCommand):
    @property
    def shortcut(self):
        return "?"
    
    @property
    def description(self):
        return "glob_search"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            search_string = ui.prompt_get_string("Enter search term")
            if search_string != "":
                view.refresh(ViewMode.SEARCH, params=search_string)
        except Exception as e:
            ui.error("Global search", e)
        return False
