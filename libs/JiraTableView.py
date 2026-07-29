from .ViewMode import ViewMode

class JiraTableView:
    def __init__(self, ui, jira):
        self.ui = ui
        self.jira = jira
        self.parent_issue = ()
        self.mode = ViewMode.BACKLOG
        # One (mode, issues, parent_issue) frame per level drilled into, so
        # epic -> story -> sub-tasks can be unwound a level at a time
        self.__stack = []
        self.__current_issues = ()
        self.extra_columns = {}

    # Rebuilds the view based, adding any extra columns
    def rebuild(self, extra_columns={}):
        self.extra_columns = extra_columns
        self.__build(self.__current_issues)

    # True when we have drilled into at least one issue, i.e. there is a view to go back to
    def has_previous(self):
        return len(self.__stack) > 0

    # Steps back out of one level of drill-down, rebuilding from the cached issues
    def previous(self):
        if not self.__stack:
            return
        self.mode, self.__current_issues, self.parent_issue = self.__stack.pop()
        self.rebuild()

    # Refresh the view with new Jira data, optionally with a new mode, a parent issue must be specified if mode is TASKVIEW
    # params may be specified for SEARCH mode
    def refresh(self, new_mode=None, params=None, parent_issue=None):
        if new_mode == ViewMode.TASKVIEW and parent_issue != None:
            # A drill-down, as opposed to the argument-less refresh that re-queries
            # the current parent
            self.__stack.append((self.mode, self.__current_issues, self.parent_issue))
        elif new_mode != None and new_mode != ViewMode.TASKVIEW:
            # Any other view change abandons the trail we drilled down
            self.__stack.clear()

        self.parent_issue = parent_issue if parent_issue != None or self.mode != ViewMode.TASKVIEW else self.parent_issue
        self.mode = new_mode if new_mode != None else self.mode

        self.ui.prompt("Fetching issues...", "")
        jira = self.jira
        if self.mode == ViewMode.BACKLOG:
            self.__current_issues = self.__build(jira.get_backlog_issues())
        elif self.mode == ViewMode.SPRINT:
            self.__current_issues = self.__build(jira.get_sprint_issues())
        elif self.mode == ViewMode.ESCALATIONS:
            self.__current_issues = self.__build(jira.get_escalation_issues())
        elif self.mode == ViewMode.WINDOWS_SHARED:
            self.__current_issues = self.__build(jira.get_windows_backlog_issues())
        elif self.mode == ViewMode.SEARCH:
            self.__current_issues = self.__build(jira.search_for_issue(params))
        elif self.mode == ViewMode.LABEL_SEARCH:
            self.__current_issues = self.__build(jira.search_by_label(params))
        elif self.mode == ViewMode.TASKVIEW:
            self.__current_issues = self.__build(jira.get_child_issues(self.parent_issue))
        elif self.mode == ViewMode.BOARD:
            self.__current_issues = self.__build(jira.get_board_issues(params))
        elif self.mode == ViewMode.SPRINTS:
            self.__current_issues = self.__build(jira.get_sprints_issues())

    # Clear the UI and rebuild the view based on the specified issues list, can optionally enable extra columns
    def __build(self, issues):
        self.ui.clear()
        optional_fields = self.jira.get_optional_fields()
        extra_columns = self.extra_columns.copy()

        header = ['Key', 'Summary', 'Status']
        if self.mode == ViewMode.SPRINT and extra_columns.get('Points') == None:
            extra_columns['Points'] = optional_fields['Points']
        if self.mode == ViewMode.TASKVIEW and extra_columns.get('Assignee') == None:
            extra_columns['Assignee'] = optional_fields['Assignee']
        # The children of an epic are estimated work rather than sub-tasks
        if self.mode == ViewMode.TASKVIEW and self.jira.is_epic(self.parent_issue) and extra_columns.get('Points') == None:
            extra_columns['Points'] = optional_fields['Points']
        if self.mode == ViewMode.SPRINTS and extra_columns.get('Sprint') == None:
            extra_columns['Sprint'] = optional_fields['Sprint']
        if len(extra_columns) > 0:
            header.extend(extra_columns.keys())
        self.ui.add_header(header)

        for issue in issues:
            added_fields = []
            if len(extra_columns) > 0:
                for col_lambda in extra_columns.values():
                    added_fields.append(col_lambda(issue))
            cells = [issue.key, issue.fields.summary, issue.fields.status.name]
            cells.extend(added_fields)
            subtasks = issue.fields.subtasks
            subtask_list = []
            for subtask in subtasks:
                subcells = [subtask.key, subtask.fields.summary, subtask.fields.status.name]
                subtask_list.append((subcells, subtask))
            self.ui.add_row(cells, issue, subtask_list)

        self.ui.draw()

        return issues
