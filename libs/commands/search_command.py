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
            search_string = ui.prompt_get_string("Enter search term (CTRL-l for label search)", ctrl_keys="l")
            if search_string == "CTRL-l":
                labels = jira.get_labels()
                if not labels:
                    ui.error("Label search", "No labels found")
                    return False
                label = ui.prompt_fuzzy_find("Enter label", labels)
                if label != "":
                    view.refresh(ViewMode.LABEL_SEARCH, params=label)
            elif search_string != "":
                view.refresh(ViewMode.SEARCH, params=search_string)
        except Exception as e:
            ui.error("Global search", e)
        return False
