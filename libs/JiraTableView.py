from .ViewMode import ViewMode

class JiraTableView:
    def __init__(self, ui, jira):
        self.ui = ui
        self.jira = jira
        self.parent_issue = ()
        self.mode = ViewMode.BACKLOG
        self.__previous_issues = () 
        self.__previous_mode = self.mode
        self.__current_issues = ()
        self.extra_columns = {}

    # Rebuilds the view based, adding any extra columns
    def rebuild(self, extra_columns={}):
        self.extra_columns = extra_columns
        self.__build(self.__current_issues)

    # Rebuilds the view based on the previous mode, i.e. When going from task view back to the parent view
    def previous(self):
        self.mode = self.__previous_mode
        self.__current_issues = self.__previous_issues
        self.rebuild()

    # Refresh the view with new Jira data, optionally with a new mode, a parent issue must be specified if mode is TASKVIEW
    # params may be specified for SEARCH mode
    def refresh(self, new_mode=None, params=None, parent_issue=None):
        self.parent_issue = parent_issue if parent_issue != None or self.mode != ViewMode.TASKVIEW else self.parent_issue
        self.__previous_mode = self.mode
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
        elif self.mode == ViewMode.TASKVIEW:
            self.__current_issues = self.__build(jira.get_sub_tasks(self.parent_issue))
        elif self.mode == ViewMode.BOARD:
            self.__current_issues = self.__build(jira.get_board_issues(params))
        elif self.mode == ViewMode.SPRINTS:
            self.__current_issues = self.__build(jira.get_sprints_issues())

        self.__previous_issues = self.__current_issues if self.mode != ViewMode.TASKVIEW else self.__previous_issues

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
