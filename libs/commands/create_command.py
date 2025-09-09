from .base_command import BaseCommand
from ..ViewMode import ViewMode
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
            
            # Initialize optional fields
            found_in_build = None
            component_id = None
            
            issue = None
            if view.mode == ViewMode.TASKVIEW:
                issue = jira.create_sub_task(view.parent_issue, summary, description)
                yesno = ui.prompt_get_character(f"Assign {view.parent_issue.key} to me? (y/n)")
                if yesno == "y":
                    jira.assign_to_me(issue)
            else:
                # Get issue type first
                [index, type] = ui.prompt_with_choice_list("Enter issue type", jira.get_possible_types(), non_numeric_keypresses=True)
                if type == "":
                    return False
                
                # Only ask for Found In and Component if it's a Bug
                if str(type).lower() == "bug":
                    # Get Found In build number
                    found_in_build = ui.prompt_get_string("Enter Found In build number (optional)")
                    if found_in_build and found_in_build.strip() == "":
                        found_in_build = None
                    
                    # Get Component selection
                    try:
                        # Get available components for the project
                        if jira.reference_issue:
                            project_components = jira.jira.project_components(jira.reference_issue.fields.project.id)
                            if project_components:
                                component_names = ["(Skip - No Component)"] + [comp.name for comp in project_components]
                                [index, component_name] = ui.prompt_with_choice_list("Select component", component_names)
                                if component_name and component_name.strip() and component_name != "(Skip - No Component)":
                                    # Find the component ID
                                    for comp in project_components:
                                        if comp.name == component_name:
                                            component_id = comp.id
                                            break
                    except Exception as e:
                        ui.error("Component selection", e)
                
                issue = jira.create_sprint_issue(summary, description, type, found_in_build, component_id) if view.mode == ViewMode.SPRINT else jira.create_backlog_issue(summary, description, type, found_in_build, component_id)
            ui.prompt(f"Created {issue.key}...")
            view.refresh()
        except Exception as e:
            ui.error("Create issue", e)
        return False
