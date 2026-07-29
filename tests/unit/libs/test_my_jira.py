import copy
import pytest
from unittest.mock import Mock, patch
from libs.MyJira import MyJira


@pytest.fixture
def jira(mock_config):
    """MyJira instance with the JIRA API client patched out"""
    with patch('libs.MyJira.JIRA'):
        return MyJira(mock_config['jira'])


class TestFindTeamForGithubRepo:
    def test_matches_repo_name(self, jira):
        assert jira.find_team_for_github_repo("test-repo") == "TestTeam"
        assert jira.find_team_for_github_repo("pathfinder-agent") == "NoBoards"

    def test_matches_owner_slash_name(self, jira):
        assert jira.find_team_for_github_repo("BeyondTrust/pathfinder-agent") == "NoBoards"

    def test_match_is_case_insensitive(self, jira):
        assert jira.find_team_for_github_repo("Pathfinder-Agent") == "NoBoards"

    def test_unknown_repo_returns_none(self, jira):
        assert jira.find_team_for_github_repo("some-other-repo") is None
        assert jira.find_team_for_github_repo("") is None

    def test_multiple_matches_prefer_default_team(self, mock_config):
        config = copy.deepcopy(mock_config['jira'])
        config['teams']['NoBoards']['github_repos'].append("test-repo")
        with patch('libs.MyJira.JIRA'):
            jira = MyJira(config)

        assert jira.find_team_for_github_repo("test-repo") == "TestTeam"


class TestSetTeamOptionalFields:
    def test_boardless_team_has_no_keyerror(self, jira):
        jira.set_team("NoBoards")

        assert jira.project_name == "AIDR"
        assert jira.team_id is None
        assert jira.product_name is None
        assert jira.kanban_board_id is None
        assert jira.backlog_board_id is None
        assert jira.escalation_board_id is None
        assert jira.github_repos == ["pathfinder-agent"]

    def test_set_team_resets_reference_issue(self, jira):
        jira.reference_issue = Mock()

        jira.set_team("NoBoards")

        assert jira.reference_issue is None


class TestJqlFallbacks:
    def _captured_jql(self, jira, method, *args, **kwargs):
        jira.search_issues = Mock(return_value=[])
        getattr(jira, method)(*args, **kwargs)
        return jira.search_issues.call_args[0][0]

    def test_backlog_includes_team_clause_when_team_id_set(self, jira):
        jql = self._captured_jql(jira, 'get_backlog_issues')
        assert 'project = TEST' in jql
        assert '"Team[Team]"=42' in jql

    def test_backlog_omits_team_clause_without_team_id(self, jira):
        jira.set_team("NoBoards")
        jql = self._captured_jql(jira, 'get_backlog_issues')
        assert 'project = AIDR' in jql
        assert 'Team[Team]' not in jql

    def test_sprint_omits_team_clause_without_team_id(self, jira):
        jira.set_team("NoBoards")
        jql = self._captured_jql(jira, 'get_sprint_issues')
        assert 'project = AIDR' in jql
        assert 'sprint in openSprints()' in jql
        assert 'Team[Team]' not in jql

    def test_search_scopes_to_product_and_help_when_product_set(self, jira):
        jql = self._captured_jql(jira, 'search_for_issue', 'some text')
        assert '(project = TEST OR project = HELP)' in jql
        assert '"Product[Dropdown]" in ("Test Product")' in jql

    def test_search_scopes_to_project_only_without_product(self, jira):
        jira.set_team("NoBoards")
        jql = self._captured_jql(jira, 'search_for_issue', 'some text')
        assert 'project = AIDR' in jql
        assert 'HELP' not in jql
        assert 'Product[Dropdown]' not in jql

    def test_search_by_label_scopes_to_project_only_without_product(self, jira):
        jira.set_team("NoBoards")
        jql = self._captured_jql(jira, 'search_by_label', 'mylabel')
        assert 'project = AIDR' in jql
        assert 'HELP' not in jql
        assert 'labels = "mylabel"' in jql

    def test_escalations_raise_without_product(self, jira):
        jira.set_team("NoBoards")
        with pytest.raises(Exception, match="no product_name"):
            jira.get_escalation_issues()

    def test_browse_boards_raise_without_board(self, jira):
        jira.set_team("NoBoards")
        with pytest.raises(Exception, match="No backlog board"):
            jira.browse_sprint_board()
        with pytest.raises(Exception, match="No backlog board"):
            jira.browse_backlog_board()
        with pytest.raises(Exception, match="No kanban board"):
            jira.browse_kanban_board()

    def test_list_closed_sprints_returns_empty_without_board(self, jira):
        jira.set_team("NoBoards")
        assert jira.list_closed_sprints() == []
        jira.jira.sprints.assert_not_called()


class TestGetActiveSprintId:
    def test_uses_board_api_when_board_configured(self, jira):
        jira.jira.sprints.return_value = [Mock(id=77)]

        assert jira._get_active_sprint_id() == 77
        jira.jira.sprints.assert_called_once()

    @patch('libs.MyJira.MyJiraIssue')
    def test_boardless_fallback_infers_sprint_from_issues(self, mock_issue_class, jira):
        jira.set_team("NoBoards")
        jira.get_sprint_issues = Mock(return_value=[Mock()])
        active_sprint = Mock(state='active', id=5)
        closed_sprint = Mock(state='closed', id=4)
        mock_issue_class.return_value.sprint = [closed_sprint, active_sprint]

        assert jira._get_active_sprint_id() == 5
        jira.jira.sprints.assert_not_called()

    def test_boardless_fallback_raises_without_sprint_issues(self, jira):
        jira.set_team("NoBoards")
        jira.get_sprint_issues = Mock(return_value=[])

        with pytest.raises(Exception, match="No active sprint found"):
            jira._get_active_sprint_id()
