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

    def test_child_issues_are_not_restricted_by_type(self, jira):
        # An epic's children are stories and bugs, not sub-tasks
        jql = self._captured_jql(jira, 'get_child_issues', Mock(key="TEST-1"))
        assert 'parent=TEST-1' in jql
        assert 'issuetype' not in jql

    def test_backlog_lists_epics_but_sprint_does_not(self, jira):
        assert 'Epic' in self._captured_jql(jira, 'get_backlog_issues')
        assert 'Epic' in self._captured_jql(jira, 'get_sprints_issues')
        assert 'Epic' not in self._captured_jql(jira, 'get_sprint_issues')

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


def _user(display_name, account_id, account_type="atlassian", active=True):
    return {
        "displayName": display_name,
        "accountId": account_id,
        "accountType": account_type,
        "active": active,
    }


def _response(payload):
    response = Mock()
    response.json.return_value = payload
    return response


class TestGetAssignableUsers:
    @patch('libs.MyJira.requests.get')
    def test_filters_and_sorts_users(self, mock_get, jira):
        mock_get.return_value = _response([
            _user("Zoe", "acc-zoe"),
            _user("A Bot", "acc-bot", account_type="app"),
            _user("Gone Person", "acc-gone", active=False),
            _user("Alice", "acc-alice"),
        ])

        users = jira.get_assignable_users()

        assert users == [
            {"displayName": "Alice", "accountId": "acc-alice"},
            {"displayName": "Zoe", "accountId": "acc-zoe"},
        ]
        params = mock_get.call_args[1]['params']
        assert params['project'] == "TEST"

    @patch('libs.MyJira.requests.get')
    def test_paginates_until_short_page(self, mock_get, jira):
        full_page = [_user(f"User {i:03}", f"acc-{i}") for i in range(200)]
        mock_get.side_effect = [
            _response(full_page),
            _response([_user("Last User", "acc-last")]),
        ]

        users = jira.get_assignable_users()

        assert len(users) == 201
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0][1]['params']['startAt'] == 0
        assert mock_get.call_args_list[1][1]['params']['startAt'] == 200

    @patch('libs.MyJira.requests.get')
    def test_result_is_cached(self, mock_get, jira):
        mock_get.return_value = _response([_user("Alice", "acc-alice")])

        first = jira.get_assignable_users()
        second = jira.get_assignable_users()

        assert first == second
        mock_get.assert_called_once()

    @patch('libs.MyJira.requests.get')
    def test_set_team_invalidates_cache(self, mock_get, jira):
        mock_get.return_value = _response([_user("Alice", "acc-alice")])
        jira.get_assignable_users()

        jira.set_team("NoBoards")
        jira.get_assignable_users()

        assert mock_get.call_count == 2
        assert mock_get.call_args[1]['params']['project'] == "AIDR"

    @patch('libs.MyJira.requests.get')
    def test_clear_caches_invalidates_cache(self, mock_get, jira):
        mock_get.return_value = _response([_user("Alice", "acc-alice")])
        jira.get_assignable_users()

        jira.clear_caches()
        jira.get_assignable_users()

        assert mock_get.call_count == 2

    @patch('libs.MyJira.requests.get')
    def test_request_failure_returns_empty_and_retries(self, mock_get, jira):
        import requests
        mock_get.side_effect = requests.RequestException("boom")

        assert jira.get_assignable_users() == []

        # Failures are not cached, so the next call fetches again
        mock_get.side_effect = None
        mock_get.return_value = _response([_user("Alice", "acc-alice")])
        assert jira.get_assignable_users() == [{"displayName": "Alice", "accountId": "acc-alice"}]


class TestAssignToAccountId:
    @patch('libs.MyJira.requests.put')
    def test_assigns_by_account_id(self, mock_put, jira):
        issue = Mock()
        issue.key = "TEST-123"

        jira.assign_to_account_id(issue, "acc-123")

        url = mock_put.call_args[0][0]
        assert url.endswith("/rest/api/3/issue/TEST-123/assignee")
        assert mock_put.call_args[1]['json'] == {"accountId": "acc-123"}
        assert mock_put.call_args[1]['auth'] == ("test@example.com", "test-token")
        mock_put.return_value.raise_for_status.assert_called_once()

    @patch('libs.MyJira.requests.put')
    def test_none_unassigns(self, mock_put, jira):
        issue = Mock()
        issue.key = "TEST-123"

        jira.assign_to_account_id(issue, None)

        assert mock_put.call_args[1]['json'] == {"accountId": None}

    @patch('libs.MyJira.requests.put')
    def test_http_error_propagates(self, mock_put, jira):
        import requests
        mock_put.return_value.raise_for_status.side_effect = requests.HTTPError("403")
        issue = Mock()
        issue.key = "TEST-123"

        with pytest.raises(requests.HTTPError):
            jira.assign_to_account_id(issue, "acc-123")


@pytest.fixture
def jira_with_cache(mock_config, tmp_path):
    """MyJira with disk caching enabled in an isolated tmp dir"""
    with patch('libs.MyJira.JIRA'):
        return MyJira(mock_config['jira'], cache_dir=str(tmp_path))


class DeferredThread:
    """Stand-in for threading.Thread: records the worker instead of running it,
    so tests control exactly when the 'background' refresh executes"""
    instances = []

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        DeferredThread.instances.append(self)

    def start(self):
        pass

    def run_now(self):
        self.target(*self.args, **self.kwargs)


@pytest.fixture
def deferred_threads():
    """Patch background threads to capture-then-run under test control"""
    DeferredThread.instances = []
    with patch('libs.MyJira.threading.Thread', DeferredThread):
        yield DeferredThread.instances


def _cache_file(tmp_path):
    import libs.MyJira as myjira_module
    return tmp_path / myjira_module.ASSIGNABLE_USERS_CACHE_FILENAME


def _write_cache_file(tmp_path, entries):
    """Write cache entries of the form {project: (age_seconds, users)}"""
    import json
    import time
    data = {
        project: {"timestamp": time.time() - age_seconds, "users": users}
        for project, (age_seconds, users) in entries.items()
    }
    _cache_file(tmp_path).write_text(json.dumps(data))


def _read_cache_file(tmp_path):
    import json
    return json.loads(_cache_file(tmp_path).read_text())


class TestAssignableUsersDiskCache:
    @patch('libs.MyJira.requests.get')
    def test_cold_fetch_persists_to_disk(self, mock_get, jira_with_cache, tmp_path):
        import time
        mock_get.return_value = _response([_user("Alice", "acc-alice")])

        users = jira_with_cache.get_assignable_users()

        entry = _read_cache_file(tmp_path)["TEST"]
        assert entry["users"] == users == [{"displayName": "Alice", "accountId": "acc-alice"}]
        assert time.time() - entry["timestamp"] < 60

    @patch('libs.MyJira.requests.get')
    def test_fresh_disk_cache_skips_http_and_refresh(self, mock_get, jira_with_cache, tmp_path, deferred_threads):
        cached_users = [{"displayName": "Alice", "accountId": "acc-alice"}]
        _write_cache_file(tmp_path, {"TEST": (60, cached_users)})

        assert jira_with_cache.get_assignable_users() == cached_users
        mock_get.assert_not_called()
        assert deferred_threads == []

    @patch('libs.MyJira.requests.get')
    def test_stale_disk_cache_returns_immediately_then_refreshes(self, mock_get, jira_with_cache, tmp_path, deferred_threads):
        from libs.MyJira import ASSIGNABLE_USERS_TTL_SECONDS
        old_users = [{"displayName": "Old User", "accountId": "acc-old"}]
        new_users = [{"displayName": "New User", "accountId": "acc-new"}]
        _write_cache_file(tmp_path, {"TEST": (ASSIGNABLE_USERS_TTL_SECONDS + 1, old_users)})
        mock_get.return_value = _response([_user("New User", "acc-new")])

        # Stale data comes back immediately, before the refresh has run
        assert jira_with_cache.get_assignable_users() == old_users
        mock_get.assert_not_called()
        assert len(deferred_threads) == 1
        assert deferred_threads[0].args == ("TEST",)

        deferred_threads[0].run_now()
        assert jira_with_cache._assignable_users_cache == new_users
        assert _read_cache_file(tmp_path)["TEST"]["users"] == new_users

    def test_only_one_refresh_in_flight(self, jira_with_cache, tmp_path, deferred_threads):
        from libs.MyJira import ASSIGNABLE_USERS_TTL_SECONDS
        users = [{"displayName": "Old User", "accountId": "acc-old"}]
        _write_cache_file(tmp_path, {"TEST": (ASSIGNABLE_USERS_TTL_SECONDS + 1, users)})

        jira_with_cache.get_assignable_users()
        jira_with_cache._assignable_users_cache = None  # simulate a second stale hit
        jira_with_cache.get_assignable_users()

        assert len(deferred_threads) == 1

    @patch('libs.MyJira.requests.get')
    def test_team_switch_mid_refresh_keeps_caches_correct(self, mock_get, jira_with_cache, tmp_path, deferred_threads):
        from libs.MyJira import ASSIGNABLE_USERS_TTL_SECONDS
        old_users = [{"displayName": "Old User", "accountId": "acc-old"}]
        _write_cache_file(tmp_path, {"TEST": (ASSIGNABLE_USERS_TTL_SECONDS + 1, old_users)})
        mock_get.return_value = _response([_user("New User", "acc-new")])

        jira_with_cache.get_assignable_users()
        jira_with_cache.set_team("NoBoards")
        deferred_threads[0].run_now()

        # AIDR's memory cache must not be polluted with TEST's users...
        assert jira_with_cache._assignable_users_cache is None
        # ...but the fetched data still lands under TEST on disk
        assert _read_cache_file(tmp_path)["TEST"]["users"] == [{"displayName": "New User", "accountId": "acc-new"}]

    @patch('libs.MyJira.requests.get')
    def test_per_project_disk_entries(self, mock_get, jira_with_cache, tmp_path):
        test_users = [{"displayName": "Test User", "accountId": "acc-test"}]
        aidr_users = [{"displayName": "Aidr User", "accountId": "acc-aidr"}]
        _write_cache_file(tmp_path, {"TEST": (60, test_users), "AIDR": (60, aidr_users)})

        jira_with_cache.set_team("NoBoards")

        assert jira_with_cache.get_assignable_users() == aidr_users
        mock_get.assert_not_called()

    @patch('libs.MyJira.requests.get')
    def test_corrupt_cache_file_recovers(self, mock_get, jira_with_cache, tmp_path):
        _cache_file(tmp_path).write_text("{not valid json")
        mock_get.return_value = _response([_user("Alice", "acc-alice")])

        users = jira_with_cache.get_assignable_users()

        assert users == [{"displayName": "Alice", "accountId": "acc-alice"}]
        assert _read_cache_file(tmp_path)["TEST"]["users"] == users

    @patch('libs.MyJira.requests.get')
    def test_clear_caches_drops_disk_entry_and_refetches(self, mock_get, jira_with_cache, tmp_path):
        mock_get.return_value = _response([_user("Alice", "acc-alice")])
        jira_with_cache.get_assignable_users()

        jira_with_cache.clear_caches()

        assert "TEST" not in _read_cache_file(tmp_path)
        jira_with_cache.get_assignable_users()
        assert mock_get.call_count == 2

    def test_warm_up_fresh_populates_memory_without_thread(self, jira_with_cache, tmp_path, deferred_threads):
        users = [{"displayName": "Alice", "accountId": "acc-alice"}]
        _write_cache_file(tmp_path, {"TEST": (60, users)})

        jira_with_cache.warm_assignable_users_cache()

        assert jira_with_cache._assignable_users_cache == users
        assert deferred_threads == []

    def test_warm_up_stale_spawns_thread(self, jira_with_cache, tmp_path, deferred_threads):
        from libs.MyJira import ASSIGNABLE_USERS_TTL_SECONDS
        users = [{"displayName": "Old User", "accountId": "acc-old"}]
        _write_cache_file(tmp_path, {"TEST": (ASSIGNABLE_USERS_TTL_SECONDS + 1, users)})

        jira_with_cache.warm_assignable_users_cache()

        # Stale data is still served while the refresh runs
        assert jira_with_cache._assignable_users_cache == users
        assert len(deferred_threads) == 1

    def test_warm_up_missing_spawns_thread(self, jira_with_cache, deferred_threads):
        jira_with_cache.warm_assignable_users_cache()

        assert jira_with_cache._assignable_users_cache is None
        assert len(deferred_threads) == 1
        assert deferred_threads[0].args == ("TEST",)

    def test_cache_dir_none_disables_disk(self, jira):
        assert jira._assignable_users_cache_path() is None


class TestSearchPagination:
    """/search/jql caps a page at 100 issues, so the search has to follow
    nextPageToken or long backlogs get silently truncated."""

    def _page(self, keys, next_page_token=None):
        response = Mock()
        response.json.return_value = {
            "issues": [{"key": key, "id": key, "fields": {}} for key in keys],
            "nextPageToken": next_page_token,
            "isLast": next_page_token is None,
        }
        return response

    def _search(self, jira, pages):
        with patch('libs.MyJira.requests.get', side_effect=pages) as get:
            issues = jira._search_issues_new_api("project = AIDR")
        return issues, get

    def test_follows_next_page_token_to_the_end(self, jira):
        pages = [
            self._page(["AIDR-1"], next_page_token="tok1"),
            self._page(["AIDR-2"], next_page_token="tok2"),
            self._page(["AIDR-3"]),
        ]

        issues, get = self._search(jira, pages)

        assert [issue.key for issue in issues] == ["AIDR-1", "AIDR-2", "AIDR-3"]
        assert get.call_count == 3
        assert "nextPageToken" not in get.call_args_list[0].kwargs["params"]
        assert get.call_args_list[1].kwargs["params"]["nextPageToken"] == "tok1"
        assert get.call_args_list[2].kwargs["params"]["nextPageToken"] == "tok2"

    def test_single_page_makes_one_request(self, jira):
        issues, get = self._search(jira, [self._page(["AIDR-1"])])

        assert [issue.key for issue in issues] == ["AIDR-1"]
        assert get.call_count == 1

    def test_is_last_stops_paging_despite_token(self, jira):
        response = self._page(["AIDR-1"], next_page_token="tok1")
        response.json.return_value["isLast"] = True

        issues, get = self._search(jira, [response])

        assert get.call_count == 1

    def test_startat_is_not_sent(self, jira):
        """The endpoint ignores startAt; sending it hid the truncation."""
        _, get = self._search(jira, [self._page(["AIDR-1"])])

        assert "startAt" not in get.call_args.kwargs["params"]

    def test_runaway_query_stops_at_cap(self, jira):
        jira.SEARCH_MAX_ISSUES = 3
        pages = [self._page([f"AIDR-{i}"], next_page_token=f"tok{i}") for i in range(10)]

        issues, get = self._search(jira, pages)

        assert len(issues) == 3
        assert get.call_count == 3
