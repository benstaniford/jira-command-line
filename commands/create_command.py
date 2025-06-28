from commands.base_command import BaseCommand
from view_mode import ViewMode
from jira_utils import get_string_from_editor

class CreateCommand(BaseCommand):
    @property
    def shortcut(self):
        return "c"
    
    @property
    def description(self):
        return "create"
    
    def execute(self, ui, view, jira, stdscr=None, **kwargs):
        try:
            summary = ui.prompt_get_string("Enter summary")
            if summary.strip() == "":
                return False
            description = ui.prompt_get_string("(F1 for editor, F2 to use summary)\nEnter description")
            if description == "KEY_F1":
                if stdscr:
                    stdscr.clear()
                description = get_string_from_editor()
                view.rebuild()
            elif description == "KEY_F2":
                description = summary
                view.rebuild()
            elif description.strip() == "":
                return False
            issue = None
            if view.mode == ViewMode.TASKVIEW:
                issue = jira.create_sub_task(view.parent_issue, summary, description)
                yesno = ui.prompt_get_character(f"Assign {view.parent_issue.key} to me? (y/n)")
                if yesno == "y":
                    jira.assign_to_me(issue)
            else:
                [index, type] = ui.prompt_with_choice_list("Enter issue type", jira.get_possible_types(), non_numeric_keypresses=True)
                if type == "":
                    return False
                issue = jira.create_sprint_issue(summary, description, type) if view.mode == ViewMode.SPRINT else jira.create_backlog_issue(summary, description, type)
            ui.prompt(f"Created {issue.key}...")
            view.refresh()
        except Exception as e:
            ui.error("Create issue", e)
        return False
