from .base_command import BaseCommand

class MoveCommand(BaseCommand):
    @property
    def shortcut(self):
        return "m"
    
    @property
    def description(self):
        return "move"
    
    def execute(self, ui, view, jira, **kwargs):
        from ..ViewMode import ViewMode
        
        try:
            [selection, row, issue] = ui.prompt_get_issue()
            if issue:
                moveOptions = { 't': 'To top', 'b': 'To bottom', 'i': 'Below issue' }
                if view.mode == ViewMode.SPRINT:
                    moveOptions['l'] = 'To backlog'
                elif view.mode == ViewMode.BACKLOG:
                    moveOptions['s'] = 'To sprint'
                selection = ui.prompt_with_choice_dictionary("Move where?", moveOptions)
                if selection == 'To top':
                    [row, topIssue] = ui.get_row(0)
                    jira.set_rank_above(issue, topIssue)
                    ui.prompt(f"Moved {issue.key} to top...")
                    view.refresh()
                elif selection == 'To bottom':
                    # The last top level row, not an expanded child that may be drawn below it
                    bottomIssue = [row_container for row_container in ui.get_rows() if not row_container.is_subrow()][-1].data
                    jira.set_rank_below(issue, bottomIssue)
                    ui.prompt(f"Moved {issue.key} to bottom...")
                    view.refresh()
                elif selection == 'Below issue':
                    selection = ui.prompt_get_string("Enter issue number")
                    if ui.is_row_label(selection):
                        [row, otherIssue] = ui.get_row_by_label(selection)
                        jira.set_rank_below(issue, otherIssue)
                        ui.prompt(f"Moved {issue.key} below {otherIssue.key}...")
                        view.refresh()
                elif selection == 'To backlog':
                    jira.move_to_backlog(issue)
                    ui.prompt(f"Moved {issue.key} to backlog...")
                    view.refresh()
                elif selection == 'To sprint':
                    jira.move_to_sprint(issue)
                    ui.prompt(f"Moved {issue.key} to sprint...")
                    view.refresh()
        except Exception as e:
            ui.error("Move issue", e)
