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
            [selection, row, issue] = ui.prompt_get_issue()
            if issue:
                users = jira.get_assignable_users()
                if not users:
                    ui.prompt("No assignable users found for this project...")
                    return
                display_to_account = {user["displayName"]: user["accountId"] for user in users}
                choices = ["Unassigned"] + list(display_to_account.keys())
                choice = ui.prompt_fuzzy_find("Select user (ESC to cancel)", choices)
                if choice != "":
                    yesno = ui.prompt_get_character(f"Are you sure you want to assign {issue.key} to {choice}? (y/n)")
                    if yesno == "y":
                        account_id = None if choice == "Unassigned" else display_to_account[choice]
                        jira.assign_to_account_id(issue, account_id)
                        ui.prompt(f"Assigned {issue.key} to {choice}...")
                        view.refresh()
        except Exception as e:
            ui.error("Assign to user", e)
