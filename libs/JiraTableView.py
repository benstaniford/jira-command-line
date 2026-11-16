from .ViewMode import ViewMode

class JiraTableView:
    def __init__(self, ui, jira):
        self.ui = ui
        self.jira = jira
        self.parent_issue = ()
        self.mode = ViewMode.BACKLOG
        # The board name or search text the current view was built from, so an
        # argument-less refresh can re-run it
        self.params = None
        # One (mode, issues, parent_issue) frame per level drilled into, so
        # epic -> story -> sub-tasks can be unwound a level at a time
        self.__stack = []
        self.__current_issues = ()
        self.extra_columns = {}
        # The columns the current table was built with, so children loaded later match
        self.__row_columns = {}
        # Keys of the issues expanded in place, so a rebuild re-expands them
        self.expanded_keys = set()
        ui.set_child_loader(self.__load_children, self.__load_children_of_many)

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
        if new_mode != None and new_mode != ViewMode.TASKVIEW:
            self.params = params
        elif params == None:
            params = self.params

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
        self.__remember_expansions()
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

        self.__row_columns = extra_columns
        for issue in issues:
            cells, data, subrows, expandable = self.__row_entry(issue)
            self.ui.add_row(cells, data, subrows, expandable=expandable)
        if self.expanded_keys:
            self.ui.expand_where(lambda data: getattr(data, "key", None) in self.expanded_keys)

        self.ui.draw()

        return issues

    # Records which rows of the outgoing table were expanded or collapsed in place
    def __remember_expansions(self):
        for data, expanded in self.ui.get_expansion_state():
            key = getattr(data, "key", None)
            if key is None:
                continue
            if expanded:
                self.expanded_keys.add(key)
            else:
                self.expanded_keys.discard(key)

    # A row for an issue: its cells, and either its sub-tasks, which arrive with the
    # issue, or for an epic a flag saying its children can be fetched on expand
    def __row_entry(self, issue):
        cells = [issue.key, issue.fields.summary, issue.fields.status.name]
        cells.extend(col_lambda(issue) for col_lambda in self.__row_columns.values())
        subtasks = [([subtask.key, subtask.fields.summary, subtask.fields.status.name], subtask)
                    for subtask in issue.fields.subtasks]
        return cells, issue, subtasks, self.jira.is_epic(issue)

    # Child loaders for the table: only epics get here, as sub-tasks are supplied up front
    def __load_children(self, issue):
        self.ui.prompt(f"Fetching children of {issue.key}...", "")
        children = self.jira.get_child_issues(issue)
        if not children:
            # Epics are marked expandable before anyone asks Jira, so say why nothing appeared
            self.ui.set_status(f"{issue.key} has no child issues")
        return [self.__row_entry(child) for child in children]

    def __load_children_of_many(self, issues):
        self.ui.prompt(f"Fetching children of {len(issues)} issues...", "")
        children = self.jira.get_children_of_many(issues)
        return [[self.__row_entry(child) for child in children.get(issue.key, [])] for issue in issues]
