from .base_command import BaseCommand

class PointsCommand(BaseCommand):
    @property
    def shortcut(self):
        return "P"
    
    @property
    def description(self):
        return "points"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                [i, points] = ui.prompt_with_choice_list("Enter story points", (0.5, 1, 2, 3, 5, 8, 13))
                if points != "":
                    yesno = ui.prompt_get_character(f"Are you sure you want to set {issue.key} to {points}? (y/n)")
                    if yesno == "y":
                        jira.set_story_points(issue, points)
                        ui.prompt(f"Set {issue.key} to {points}...")
                        view.refresh()
        except Exception as e:
            ui.error("Set story points", e)
