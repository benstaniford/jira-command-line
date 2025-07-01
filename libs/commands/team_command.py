from .base_command import BaseCommand

class TeamCommand(BaseCommand):
    @property
    def shortcut(self):
        return "E"
    
    @property
    def description(self):
        return "team"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            teams = jira.get_teams()
            [index, team] = ui.prompt_with_choice_list("Select team", teams)
            if team != "":
                jira.set_team(team)
                view.refresh()
        except Exception as e:
            ui.error("Set team", e)
        return False
