from commands.base_command import BaseCommand

class StatusCommand(BaseCommand):
    @property
    def shortcut(self):
        return "t"
    
    @property
    def description(self):
        return "status"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            selection = ui.prompt_get_string("Enter issue number")
            if selection.isdigit():
                [row, issue] = ui.get_row(int(selection)-1)
                statuses = jira.get_statuses(issue)
                [index, status] = ui.prompt_with_choice_list("Select status", statuses)
                if status != "":
                    yesno = ui.prompt_get_character(f"Are you sure you want to change {issue.key} to [{status}]? (y/n)")
                    if yesno == "y":
                        status = str(status).upper() # Unsure why this is required...
                        jira.change_status(issue, status)
                        ui.prompt(f"Changed {issue.key} to {status}...")
                        view.refresh()
        except Exception as e:
            ui.error("Change status", e)
