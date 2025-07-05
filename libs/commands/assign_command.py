from .base_command import BaseCommand

class AssignCommand(BaseCommand):
    @property
    def shortcut(self):
        return "a"
    
    @property
    def description(self):
        return "assign"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                shortnames = jira.get_user_shortnames()
                [index, shortname] = ui.prompt_with_choice_list("Select user", shortnames, non_numeric_keypresses=True)
                if shortname != "":
                    yesno = ui.prompt_get_character(f"Are you sure you want to assign {issue.key} to {shortname}? (y/n)")
                    if yesno == "y":
                        jira.assign_to(issue, shortname)
                        ui.prompt(f"Assigned {issue.key} to {shortname}...")
                        view.refresh()
        except Exception as e:
            ui.error("Assign to user", e)
