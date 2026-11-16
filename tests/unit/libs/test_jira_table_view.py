import pytest
from unittest.mock import Mock
from libs.JiraTableView import JiraTableView
from libs.ViewMode import ViewMode
from libs.SelfTest import HeadlessTableView


def make_issue(key, issue_type="Story"):
    issue = Mock()
    issue.key = key
    issue.fields.summary = f"Summary of {key}"
    issue.fields.status.name = "To Do"
    issue.fields.issuetype = issue_type
    issue.fields.subtasks = []
    return issue


@pytest.fixture
def mock_jira():
    jira = Mock()
    jira.get_optional_fields.return_value = {
        "Assignee": lambda issue: "nobody",
        "Points": lambda issue: "3",
        "Sprint": lambda issue: "Sprint 1",
    }
    jira.is_epic.side_effect = lambda issue: getattr(getattr(issue, "fields", None), "issuetype", "") == "Epic"
    jira.get_backlog_issues.return_value = [make_issue("EPIC-1", "Epic"), make_issue("TEST-1")]
    jira.get_child_issues.return_value = [make_issue("TEST-2")]
    jira.get_sprint_issues.return_value = [make_issue("TEST-3")]
    return jira


@pytest.fixture
def view(mock_jira):
    ui = Mock()
    ui.get_expansion_state.return_value = []
    return JiraTableView(ui, mock_jira)


class TestJiraTableView:
    def test_backlog_view_has_nothing_to_go_back_to(self, view):
        view.refresh(ViewMode.BACKLOG)

        assert view.has_previous() is False

    def test_drilling_in_twice_unwinds_a_level_at_a_time(self, view, mock_jira):
        view.refresh(ViewMode.BACKLOG)
        backlog_issues = mock_jira.get_backlog_issues.return_value
        epic = backlog_issues[0]

        view.refresh(ViewMode.TASKVIEW, parent_issue=epic)
        story = mock_jira.get_child_issues.return_value[0]
        view.refresh(ViewMode.TASKVIEW, parent_issue=story)

        assert view.mode == ViewMode.TASKVIEW
        assert view.parent_issue is story

        view.previous()
        assert view.mode == ViewMode.TASKVIEW
        assert view.parent_issue is epic
        assert view.has_previous() is True

        view.previous()
        assert view.mode == ViewMode.BACKLOG
        assert view.parent_issue is None
        assert view.has_previous() is False

    def test_previous_on_an_empty_stack_is_a_no_op(self, view):
        view.refresh(ViewMode.BACKLOG)

        view.previous()

        assert view.mode == ViewMode.BACKLOG

    def test_argument_less_refresh_does_not_push_a_level(self, view, mock_jira):
        view.refresh(ViewMode.BACKLOG)
        epic = mock_jira.get_backlog_issues.return_value[0]
        view.refresh(ViewMode.TASKVIEW, parent_issue=epic)

        view.refresh()

        assert view.parent_issue is epic
        view.previous()
        assert view.mode == ViewMode.BACKLOG
        assert view.has_previous() is False

    def test_switching_view_clears_the_trail(self, view, mock_jira):
        view.refresh(ViewMode.BACKLOG)
        view.refresh(ViewMode.TASKVIEW, parent_issue=mock_jira.get_backlog_issues.return_value[0])

        view.refresh(ViewMode.SPRINT)

        assert view.has_previous() is False

    def test_epic_children_get_a_points_column(self, view, mock_jira):
        view.refresh(ViewMode.BACKLOG)
        view.refresh(ViewMode.TASKVIEW, parent_issue=mock_jira.get_backlog_issues.return_value[0])

        header = view.ui.add_header.call_args[0][0]
        assert header == ["Key", "Summary", "Status", "Assignee", "Points"]

    def test_sub_task_view_has_no_points_column(self, view, mock_jira):
        view.refresh(ViewMode.BACKLOG)
        view.refresh(ViewMode.TASKVIEW, parent_issue=mock_jira.get_backlog_issues.return_value[1])

        header = view.ui.add_header.call_args[0][0]
        assert header == ["Key", "Summary", "Status", "Assignee"]


class TestExpandInPlace:
    """Uses the real table model, via the headless view, rather than a mock UI"""
    @pytest.fixture
    def tree_view(self, mock_jira):
        story = make_issue("TEST-1")
        subtask = Mock()
        subtask.key = "SUB-1"
        subtask.fields.summary = "A sub-task"
        subtask.fields.status.name = "To Do"
        story.fields.subtasks = [subtask]
        mock_jira.get_backlog_issues.return_value = [make_issue("EPIC-1", "Epic"), story]
        mock_jira.get_children_of_many.return_value = {"EPIC-1": [make_issue("TEST-2")]}
        return JiraTableView(HeadlessTableView(), mock_jira)

    def keys(self, view):
        return [row.data.key for row in view.ui.get_rows()]

    def test_epics_load_children_on_expand_and_stories_carry_sub_tasks(self, tree_view, mock_jira):
        tree_view.refresh(ViewMode.BACKLOG)
        assert [row.expandable for row in tree_view.ui.rows] == [True, True, False]

        tree_view.ui.expand_row(0)

        mock_jira.get_child_issues.assert_called_once()
        assert self.keys(tree_view) == ["EPIC-1", "TEST-2", "TEST-1"]

    def test_expand_all_fetches_every_epic_in_one_query(self, tree_view, mock_jira):
        backlog = mock_jira.get_backlog_issues.return_value
        mock_jira.get_backlog_issues.return_value = backlog + [make_issue("EPIC-9", "Epic")]
        tree_view.refresh(ViewMode.BACKLOG)

        tree_view.ui.toggle_expand_all()

        mock_jira.get_children_of_many.assert_called_once()
        mock_jira.get_child_issues.assert_not_called()
        # EPIC-9 has no children, so it is shown as a leaf
        assert self.keys(tree_view) == ["EPIC-1", "TEST-2", "TEST-1", "SUB-1", "EPIC-9"]
        assert tree_view.ui.rows[-1].expandable is False

    def test_expansions_survive_a_refresh(self, tree_view, mock_jira):
        tree_view.refresh(ViewMode.BACKLOG)
        tree_view.ui.expand_row(1)  # TEST-1's sub-tasks

        tree_view.refresh()

        assert self.keys(tree_view) == ["EPIC-1", "TEST-1", "SUB-1"]

    def test_collapsing_is_remembered_too(self, tree_view, mock_jira):
        tree_view.refresh(ViewMode.BACKLOG)
        tree_view.ui.expand_row(1)
        tree_view.refresh()
        tree_view.ui.collapse_row(1)

        tree_view.refresh()

        assert self.keys(tree_view) == ["EPIC-1", "TEST-1"]

    def test_loaded_children_get_the_tables_extra_columns(self, tree_view, mock_jira):
        tree_view.refresh(ViewMode.SPRINT)  # Adds a Points column
        mock_jira.get_sprint_issues.return_value = [make_issue("EPIC-1", "Epic")]
        tree_view.refresh(ViewMode.SPRINT)
        tree_view.ui.expand_row(0)

        child = tree_view.ui.get_rows()[1]
        assert child.row == ["TEST-2", "Summary of TEST-2", "To Do", "3"]

    def test_an_epic_with_no_children_says_so(self, tree_view, mock_jira):
        mock_jira.get_child_issues.return_value = []
        tree_view.refresh(ViewMode.BACKLOG)

        assert tree_view.ui.expand_row(0) is False

        assert tree_view.ui.take_status() == "EPIC-1 has no child issues"
        assert tree_view.ui.take_status() is None
        assert tree_view.ui.rows[0].expandable is False
