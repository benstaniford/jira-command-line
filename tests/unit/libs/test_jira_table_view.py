import pytest
from unittest.mock import Mock
from libs.JiraTableView import JiraTableView
from libs.ViewMode import ViewMode


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
    return JiraTableView(Mock(), mock_jira)


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
