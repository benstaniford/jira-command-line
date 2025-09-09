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
                ui.prompt(f"Created {issue.key}...")
                self._wait_for_issue_and_refresh(ui, view, jira, issue)
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
                    
                    # Get Component selection using fuzzy find
                    try:
                        # Get available components for the project
                        if jira.reference_issue:
                            project_components = jira.jira.project_components(jira.reference_issue.fields.project.id)
                            if project_components:
                                component_names = ["(Skip - No Component)"] + [comp.name for comp in project_components]
                                component_name = ui.prompt_fuzzy_find("Select component (ESC to skip)", component_names)
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
                self._wait_for_issue_and_refresh(ui, view, jira, issue)
        except Exception as e:
            ui.error("Create issue", e)
        return False

    def _wait_for_issue_and_refresh(self, ui, view, jira, issue):
        """
        Wait for the newly created issue to appear in the current view before refreshing.
        This handles Jira's eventual consistency by polling until the issue is visible.
        """
        import time
        from ..ViewMode import ViewMode
        
        max_retries = 10  # Maximum number of polling attempts
        retry_delay = 0.5  # Delay between attempts in seconds
        
        def get_current_view_issues():
            """Get issues from the current view without updating the UI"""
            if view.mode == ViewMode.BACKLOG:
                return jira.get_backlog_issues()
            elif view.mode == ViewMode.SPRINT:
                return jira.get_sprint_issues()
            elif view.mode == ViewMode.ESCALATIONS:
                return jira.get_escalation_issues()
            elif view.mode == ViewMode.WINDOWS_SHARED:
                return jira.get_windows_backlog_issues()
            elif view.mode == ViewMode.TASKVIEW:
                return jira.get_sub_tasks(view.parent_issue)
            elif view.mode == ViewMode.SPRINTS:
                return jira.get_sprints_issues()
            else:
                return []
        
        def issue_exists_in_view(issue_key, issues_list):
            """Check if the issue exists in the given issues list"""
            return any(existing_issue.key == issue_key for existing_issue in issues_list)
        
        # Try to find the issue in the current view
        for attempt in range(max_retries):
            try:
                current_issues = get_current_view_issues()
                if issue_exists_in_view(issue.key, current_issues):
                    # Issue found, refresh the view and return
                    view.refresh()
                    return
                
                # Issue not found yet, wait and try again
                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    time.sleep(retry_delay)
                    
            except Exception as e:
                # If there's an error during polling, just refresh normally
                ui.error(f"Error waiting for issue {issue.key}", e)
                break
        
        # If we get here, either we reached max retries or had an error
        # Just do a normal refresh as fallback
        view.refresh()
