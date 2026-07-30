#scriptdoc: title="My comms library for talking to Jira", tags="bt,work,jira"

# pip install jira
from jira import JIRA
from .MyJiraIssue import MyJiraIssue
from .JiraIssueMarkdownFormatter import JiraIssueMarkdownFormatter
import os
import datetime
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import webbrowser
import requests
import subprocess
import platform
from typing import Any, Dict, List, Optional, Union

ASSIGNABLE_USERS_TTL_SECONDS = 5 * 24 * 3600  # Treat the disk cache as fresh for 5 days
ASSIGNABLE_USERS_CACHE_FILENAME = "assignable_users_cache.json"

class MyJira:
    def __init__(self, config: Dict[str, Any], cache_dir: Optional[str] = None):
        """
        Initialize the MyJira instance with configuration.
        Args:
            config: Dictionary containing Jira and team configuration.
            cache_dir: Directory for persistent caches (e.g. ~/.jira-config);
                None disables disk caching.
        """
        self.config = config
        self.url = config["url"]
        self.password = config["password"]

        # Stuff specific to me
        self.username = config["username"]
        self.fullname = config["fullname"]

        # Cache of assignable users: in memory per project for the session,
        # optionally persisted to cache_dir. Must be set up before set_team()
        # below, which clears the memory cache.
        self.cache_dir = cache_dir
        self._assignable_users_cache = None
        self._assignable_users_refresh_lock = threading.Lock()
        self._assignable_users_refreshing = False

        # Stuff specific to the team
        self.set_team(config["default_team"])

        options = {"server": self.url, "rest_api_version": "3"}
        self.jira = JIRA(options=options, basic_auth=(self.username, self.password))
        # Issue type names are validated instance-wide by Jira; types absent
        # from a given project simply never match, so this list is safe to
        # share across projects
        self.issue_filter = '(Story, Bug, Spike, Automation, Vulnerability, Support, Task, "Technical Improvement", "Sub-task Bug")'
        # Epics are only listed in the planning views, where they are worth
        # drilling into; the current sprint stays free of them
        self.backlog_issue_filter = '(Story, Bug, Spike, Automation, Vulnerability, Support, Task, "Technical Improvement", "Sub-task Bug", Epic)'
        self.ignored_issue_types = {"Sub-task", "Sub-task Bug", "Test", "Test Set", "Test Plan", "Test Execution", "Precondition", "Sub Test Execution"}

        # We use the reference issue as a template for creating new issues/tasks
        self.reference_issue = None
        
        # Cache for active sprint to avoid repeated API calls
        self._active_sprint_cache = None
        self._active_sprint_cache_timestamp = None
        self._active_sprint_cache_duration = 300  # Cache for 5 minutes
        
        # Cache for closed sprints (they don't change often)
        self._closed_sprints_cache = None
        self._closed_sprints_cache_timestamp = None
        self._closed_sprints_cache_duration = 3600  # Cache for 1 hour

    def set_team(self, team_name: str) -> None:
        """
        Set the current team context and update related properties.
        Args:
            team_name: Name of the team to set.
        Raises:
            Exception: If the team is not found in the config.
        """
        self.team_name = team_name
        current_team = self.config['teams'][team_name]
        if (current_team == None):
            raise Exception(f"Team {self.team_name} not found in config")

        # Only project_name is required; teams for projects without a Jira team,
        # product dropdown or scrum/kanban boards simply omit those keys
        self.team_id = current_team.get("team_id")
        self.project_name = current_team["project_name"]
        self.product_name = current_team.get("product_name")
        self.short_names_to_ids = current_team.get("short_names_to_ids", {})
        self.kanban_board_id = current_team.get("kanban_board_id")
        self.backlog_board_id = current_team.get("backlog_board_id")
        self.escalation_board_id = current_team.get("escalation_board_id")
        self.github_repos = current_team.get("github_repos", [])
        self.pr_checklist = current_team.get("pr_checklist")

        # The reference issue belongs to the previous team's project; keep it and
        # new issues would be created in the wrong project
        self.reference_issue = None
        # MyJiraIssue._field_mapping_cache is deliberately left alone: custom
        # field ids are instance-wide, not per-project

        # Clear active sprint cache when switching teams
        self._active_sprint_cache = None
        self._active_sprint_cache_timestamp = None
        # Clear closed sprints cache when switching teams
        self._closed_sprints_cache = None
        self._closed_sprints_cache_timestamp = None
        # Assignable users are project-scoped, so refetch for the new team
        self._assignable_users_cache = None

    def _team_clause(self) -> str:
        """
        JQL fragment scoping a query to the current team, or empty when the
        team has no Jira team id configured.
        """
        return f' AND "Team[Team]"={self.team_id}' if self.team_id not in (None, "") else ''

    def _search_scope(self) -> str:
        """
        JQL fragment scoping searches to the current project/product. Without a
        product, "OR project = HELP" would span every product's escalations, so
        scope to the project alone.
        """
        if self.product_name:
            return f'(project = {self.project_name} OR project = HELP) AND "Product[Dropdown]" in ("{self.product_name}")'
        return f'project = {self.project_name}'

    def find_team_for_github_repo(self, repo_name: str) -> Optional[str]:
        """
        Map a github repo name (or owner/name) to a configured team name via the
        teams' github_repos lists. Prefers default_team when several teams share
        the repo. Returns None when no team claims it.
        Args:
            repo_name: Repo name or owner/name, e.g. "epm-windows" or "BeyondTrust/epm-windows".
        Returns:
            The matching team name, or None.
        """
        if not repo_name:
            return None
        target = repo_name.split('/')[-1].lower()
        matches = [name for name, team in self.config['teams'].items()
                   if any(entry.split('/')[-1].lower() == target
                          for entry in (team.get('github_repos') or []))]
        if not matches:
            return None
        default = self.config.get('default_team')
        return default if default in matches else matches[0]

    def clear_caches(self) -> None:
        """
        Clear all caches to force fresh API calls.
        """
        self._active_sprint_cache = None
        self._active_sprint_cache_timestamp = None
        self._closed_sprints_cache = None
        self._closed_sprints_cache_timestamp = None
        self._assignable_users_cache = None
        # Drop the disk entry too so the next lookup refetches synchronously
        self._remove_assignable_users_from_disk(self.project_name)
        # Also clear the MyJiraIssue class-level caches
        MyJiraIssue._field_mapping_cache = None
        MyJiraIssue._jira_fields_cache = None

    def get_teams(self) -> List[str]:
        """
        Get a list of all team names.
        Returns:
            List of team names.
        """
        list_teams = []
        for team in self.config['teams']:
            list_teams.append(team)
        return list_teams

    def get_boards(self) -> List[str]:
        """
        Get a list of all board names.
        Returns:
            List of board names.
        """
        list_boards = []
        if 'boards' in self.config:
            for board in self.config['boards']:
                list_boards.append(board)
        return list_boards

    def get_board_issues(self, board: str) -> Any:
        """
        Get issues for a specific board.
        Args:
            board: Board name.
        Returns:
            List of issues for the board.
        """
        self.board = board
        board = self.config['boards'][board]
        query = board["query"]
        return self.search_issues(query)

    def get_age(self, issue: Any) -> int:
        """
        Get the age of an issue in days.
        Args:
            issue: Jira issue object.
        Returns:
            Age in days.
        """
        created = datetime.datetime.strptime(issue.fields.created, '%Y-%m-%dT%H:%M:%S.%f%z').replace(tzinfo=None)
        now = datetime.datetime.now().replace(tzinfo=None)
        age = now - created
        return age.days

    def transitions(self, issue: Any) -> Any:
        """
        Get possible transitions for an issue.
        Args:
            issue: Jira issue object.
        Returns:
            List of transitions.
        """
        return self.jira.transitions(issue)

    # Returns a dictionary of optional field names lambda functions to get the value of each field from an issue
    def get_sprint_name(self, issue: Any) -> str:
        """
        Get the sprint name for an issue. When assigned to multiple sprints, returns the latest one.
        Args:
            issue: Jira issue object.
        Returns:
            Sprint name or "No sprint" if not assigned to a sprint.
        """
        try:
            jira_issue = MyJiraIssue(issue, self.jira)
            if hasattr(jira_issue, 'sprint') and jira_issue.sprint and len(jira_issue.sprint) > 0:
                # Find the sprint with the highest ID (latest sprint)
                latest_sprint = max(jira_issue.sprint, key=lambda s: int(s.id))
                return latest_sprint.name
            else:
                return "No sprint"
        except:
            return "No sprint"

    def get_optional_fields(self) -> Dict[str, Any]:
        """
        Get a dictionary of optional field names and their value functions.
        Returns:
            Dictionary mapping field names to lambda functions.
        """
        optional_fields = {
                "Assignee": lambda issue: str(issue.fields.assignee),
                "Created": lambda issue: str(issue.fields.created[0:16].replace("T", " ")),
                "Updated": lambda issue: str(issue.fields.updated[0:16].replace("T", " ")),
                "Age": lambda issue: str(self.get_age(issue)),
                "Points": lambda issue: self.get_story_points(issue),
                "Issue Type": lambda issue: str(issue.fields.issuetype),
                "Sub-Tasks": lambda issue: str(self.get_subtask_count(issue)),
                "Parent Desc": lambda issue: self.get_parent_description(issue),
                "Pri Score": lambda issue: str(self.get_priority_score(issue)),
                "Sprint": lambda issue: self.get_sprint_name(issue),
            }
        return optional_fields

    def get_subtask_count(self, issue: Any) -> int:
        """
        Get the number of subtasks for an issue.
        Args:
            issue: Jira issue object.
        Returns:
            Number of subtasks.
        """
        return len(issue.fields.subtasks)

    def get_parent_description(self, issue: Any) -> str:
        """
        Get a short description of the parent issue, if any.
        Args:
            issue: Jira issue object.
        Returns:
            Short summary of the parent issue.
        """
        issue_dict = issue.raw
        parent = issue_dict.get("fields", {}).get("parent", None)
        summary = parent.get("fields", {}).get("summary", "") if parent != None else ""
        if len(summary) > 30:
            summary = summary[0:30] + "..."
        return summary

    # /search/jql is token-paginated and silently caps a page at 100 issues no
    # matter what maxResults asks for, so every search has to follow
    # nextPageToken to the end. The issue cap is a runaway guard for an
    # accidentally unscoped JQL, not a display limit; teams whose queries are
    # scoped to a project and team come in far below it.
    SEARCH_PAGE_SIZE = 100
    SEARCH_MAX_ISSUES = 2000

    # The 100 cap only bites once real fields are asked for. A key-only search
    # honours maxResults up to 1000, which is what makes the parallel path
    # below possible: one cheap request enumerates the whole result set, and
    # the expensive "*all" fetches can then be issued by key, all at once,
    # instead of being chained one nextPageToken at a time.
    SEARCH_KEY_PAGE_SIZE = 1000
    SEARCH_MAX_WORKERS = 16
    # A chunk of keys costs one request, so chunks want to be big enough not to
    # multiply round trips and small enough to keep every worker busy
    SEARCH_MIN_CHUNK = 25
    SEARCH_MAX_CHUNK = 50

    def _search_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Issue one /search/jql request.
        Args:
            params: Query parameters for the request.
        Returns:
            Parsed JSON body.
        """
        response = requests.get(
            f"{self.url}/rest/api/3/search/jql",
            params=params,
            auth=(self.username, self.password),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def _search_field_params(self, jql: str, changelog: bool) -> Dict[str, Any]:
        """
        Request parameters for a full-field page. startAt is not supported by
        this endpoint (it is ignored), pagination is by nextPageToken alone.
        """
        params: Dict[str, Any] = {
            "jql": jql,
            "maxResults": self.SEARCH_PAGE_SIZE,
            "fields": "*all",
        }
        if changelog:
            params["expand"] = "changelog"
        return params

    def _search_all_keys(self, search_text: str) -> List[str]:
        """
        Enumerate every key the JQL matches, in the query's own ORDER BY order.
        Args:
            search_text: JQL query string.
        Returns:
            List of issue keys, truncated to SEARCH_MAX_ISSUES.
        """
        keys: List[str] = []
        next_page_token = None
        while True:
            params: Dict[str, Any] = {
                "jql": search_text,
                "maxResults": self.SEARCH_KEY_PAGE_SIZE,
                "fields": "key",
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token

            data = self._search_request(params)
            keys.extend(issue["key"] for issue in data.get("issues", []))

            next_page_token = data.get("nextPageToken")
            if data.get("isLast") or not next_page_token or len(keys) >= self.SEARCH_MAX_ISSUES:
                break

        return keys[:self.SEARCH_MAX_ISSUES]

    def _search_issues_by_keys(self, keys: List[str], changelog: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch full field data for a chunk of keys. Still paged, because a chunk
        can exceed the response cap once the changelog is expanded.
        Args:
            keys: Issue keys to fetch.
            changelog: Whether to expand changelog.
        Returns:
            List of raw issue dictionaries.
        """
        params = self._search_field_params("key in (%s)" % ",".join(keys), changelog)
        issues: List[Dict[str, Any]] = []
        next_page_token = None
        while True:
            page_params = dict(params)
            if next_page_token:
                page_params["nextPageToken"] = next_page_token

            data = self._search_request(page_params)
            issues.extend(data.get("issues", []))

            next_page_token = data.get("nextPageToken")
            if data.get("isLast") or not next_page_token:
                break

        return issues

    def _search_remainder_in_parallel(self, search_text: str, first_page: List[Dict[str, Any]],
                                      changelog: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch everything the first page did not cover, all chunks at once.
        Args:
            search_text: JQL query string.
            first_page: Raw issues already retrieved by the first page.
            changelog: Whether to expand changelog.
        Returns:
            Raw issues for the whole result set, in the query's order.
        """
        keys = self._search_all_keys(search_text)
        by_key = {issue["key"]: issue for issue in first_page}
        missing = [key for key in keys if key not in by_key]

        chunk_size = max(self.SEARCH_MIN_CHUNK,
                         min(self.SEARCH_MAX_CHUNK,
                             math.ceil(len(missing) / self.SEARCH_MAX_WORKERS)))
        chunks = [missing[i:i + chunk_size] for i in range(0, len(missing), chunk_size)]

        if chunks:
            with ThreadPoolExecutor(max_workers=min(self.SEARCH_MAX_WORKERS, len(chunks))) as pool:
                for page in pool.map(lambda chunk: self._search_issues_by_keys(chunk, changelog), chunks):
                    for issue in page:
                        by_key[issue["key"]] = issue

        # The key enumeration ran the same JQL, so its order is the query's
        # ORDER BY. Anything that moved out of the result set between the two
        # passes simply drops out.
        return [by_key[key] for key in keys if key in by_key]

    def _search_issues_new_api(self, search_text: str, changelog: bool = False) -> Any:
        """
        Search for issues using the new /rest/api/3/search/jql endpoint directly.
        This is a workaround for the deprecated /rest/api/3/search endpoint.
        Args:
            search_text: JQL query string.
            changelog: Whether to expand changelog.
        Returns:
            List of issue objects.
        """
        # Convert the raw issue data to JIRA issue objects
        # Use the jira library's method to create issue objects from raw data
        from jira.resources import Issue

        try:
            data = self._search_request(self._search_field_params(search_text, changelog))
            issues_data = data.get("issues", [])

            # A team-scoped query usually fits in one page, and that page is
            # already the complete answer - don't spend a second round trip
            # enumerating keys just to confirm it.
            if not data.get("isLast") and data.get("nextPageToken"):
                issues_data = self._search_remainder_in_parallel(search_text, issues_data, changelog)

            # Create issue objects directly from the response data (no additional API calls)
            return [Issue(self.jira._options, self.jira._session, issue_data)
                    for issue_data in issues_data]

        except requests.RequestException as e:
            # If the new API fails, raise the error since the old API is deprecated
            raise RuntimeError(f"New API search failed and old API is deprecated: {e}")

    def search_issues(self, search_text: str, changelog: bool = False) -> Any:
        """
        Search for issues using a JQL query.
        Uses the new API endpoint to avoid deprecated API errors.
        Args:
            search_text: JQL query string.
            changelog: Whether to expand changelog.
        Returns:
            List of issues.
        """
        try:
            # Try the new API endpoint first
            issues = self._search_issues_new_api(search_text, changelog)
        except Exception as e:
            # If the new API fails, raise the error since the old API is deprecated
            raise RuntimeError(f"Search failed - new API error: {e}")
        
        self.set_reference_issue(issues)
        return issues

    def get_testplan_by_name(self, name: str) -> Any:
        """
        Get test plans by name.
        Args:
            name: Name of the test plan.
        Returns:
            List of test plan issues.
        """
        return self.search_issues(f'project = {self.project_name} AND issuetype = "Test Plan" AND summary ~ "{name}" ORDER BY Rank ASC')

    def get_backlog_issues(self) -> Any:
        """
        Get backlog issues for the current team.
        Returns:
            List of backlog issues.
        """
        return self.search_issues(f'project = {self.project_name}{self._team_clause()} AND issuetype in {self.backlog_issue_filter} AND (sprint is EMPTY or sprint not in openSprints()) AND statuscategory not in (Done) AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

    def get_sprints_issues(self) -> Any:
        """
        Get all team issues (including backlog and future sprints) ordered by sprint assignment.
        Issues in sprints come first (ascending order), then "No sprint" items at the bottom.
        Returns:
            List of issues ordered by sprint assignment.
        """
        # Get issues without sprint-based ordering since we'll sort them ourselves
        issues = self.search_issues(f'project = {self.project_name}{self._team_clause()} AND issuetype in {self.backlog_issue_filter} AND statuscategory not in (Done) AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')
        
        # Sort issues by latest sprint ID, with "No sprint" items at the end
        def get_sort_key(issue):
            try:
                jira_issue = MyJiraIssue(issue, self.jira)
                if hasattr(jira_issue, 'sprint') and jira_issue.sprint and len(jira_issue.sprint) > 0:
                    # Find the sprint with the highest ID (latest sprint)
                    latest_sprint = max(jira_issue.sprint, key=lambda s: int(s.id))
                    return (0, int(latest_sprint.id))  # 0 ensures sprints come before no-sprint items
                else:
                    return (1, 0)  # 1 ensures no-sprint items come last
            except:
                return (1, 0)  # Treat errors as no-sprint
        
        return sorted(issues, key=get_sort_key)

    def get_windows_backlog_issues(self) -> Any:
        """
        Get backlog issues for Windows (no team assigned).
        Returns:
            List of backlog issues.
        """
        return self.search_issues(f'project = {self.project_name} AND "Team[Team]" is EMPTY AND issuetype in {self.issue_filter} AND (sprint is EMPTY or sprint not in openSprints()) AND statuscategory not in (Done) AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

    def get_sprint_issues(self, changelog: bool = False) -> Any:
        """
        Get issues in the current sprint.
        Args:
            changelog: Whether to expand changelog.
        Returns:
            List of sprint issues.
        """
        return self.search_issues(f'project = {self.project_name}{self._team_clause()} AND issuetype in {self.issue_filter} AND sprint in openSprints() AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC', changelog)

    def get_sprint_by_name(self, name: str, changelog: bool = False) -> Any:
        """
        Get issues in a sprint by sprint name.
        Args:
            name: Sprint name.
            changelog: Whether to expand changelog.
        Returns:
            List of sprint issues.
        """
        return self.search_issues(f'project = {self.project_name}{self._team_clause()} AND issuetype in {self.issue_filter} AND sprint="{name}" AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC', changelog)

    def list_closed_sprints(self) -> Any:
        """
        List closed sprints for the current board.
        Returns:
            List of closed sprints.
        """
        current_time = datetime.datetime.now().timestamp()
        
        # Check if we have cached closed sprints and they're still valid
        if (self._closed_sprints_cache is not None and 
            self._closed_sprints_cache_timestamp is not None and
            current_time - self._closed_sprints_cache_timestamp < self._closed_sprints_cache_duration):
            return self._closed_sprints_cache
        else:
            # Without a board there is no sprint API to query
            if not self.backlog_board_id:
                return []
            # Fetch closed sprints from API
            closed_sprints = self.jira.sprints(self.backlog_board_id, extended=True, startAt=0, maxResults=100, state='closed')
            # Cache the result
            self._closed_sprints_cache = closed_sprints
            self._closed_sprints_cache_timestamp = current_time
            return closed_sprints

    def get_issue_by_key(self, key: str) -> Any:
        """
        Get a single issue by its key.
        Args:
            key: Issue key.
        Returns:
            Jira issue object.
        Raises:
            Exception: If not exactly one issue is found.
        """
        issues = self.search_issues(f'key = {key}')
        if len(issues) != 1:
            raise Exception(f"Expected 1 issue with key {key}, but found {len(issues)}")
        return issues[0]

    def add_comment(self, issue: Any, comment: str) -> None:
        """
        Add a comment to an issue.
        Args:
            issue: Jira issue object.
            comment: Comment text.
        """
        try:
            # First try with ADF format for API v3 compatibility
            adf_comment = {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": comment
                            }
                        ]
                    }
                ]
            }
            self.jira.add_comment(issue, adf_comment)
        except Exception as e:
            # Fallback to plain text if ADF format fails
            print(f"ADF format failed, trying plain text: {e}")
            try:
                self.jira.add_comment(issue, comment)
            except Exception as e2:
                print(f"Plain text format also failed: {e2}")
                # Try with body wrapper as fallback
                self.jira.add_comment(issue, {"body": comment})

    def user_acted_on_issue(self, issue: Any, user_email: str, since: datetime.datetime) -> bool:
        """
        Check whether a user personally performed an action on an issue since a given datetime.

        An "action" means either:
          - authoring a comment, or
          - a changelog entry (status change, field edit, transition, etc.) attributed
            to the user.

        Updates made by other users or automated Jira processes do not count. For best
        results, the issue should be fetched with `changelog=True` so the changelog is
        available without an extra round-trip.

        Args:
            issue: Jira issue object.
            user_email: Email address of the user to match against authors.
            since: Naive datetime; only actions on or after this point count.
        Returns:
            True if the user personally acted on the issue in the window.
        """
        user_email_lower = (user_email or '').lower()
        if not user_email_lower:
            return False

        def _matches_user(author: Any) -> bool:
            if author is None:
                return False
            email = getattr(author, 'emailAddress', '') or ''
            return user_email_lower in email.lower()

        def _parse_dt(value: str) -> Optional[datetime.datetime]:
            if not value:
                return None
            try:
                return datetime.datetime.strptime(value[:19], '%Y-%m-%dT%H:%M:%S')
            except (ValueError, TypeError):
                return None

        changelog = getattr(issue, 'changelog', None)
        if changelog is not None:
            for history in getattr(changelog, 'histories', None) or []:
                if not _matches_user(getattr(history, 'author', None)):
                    continue
                created = _parse_dt(getattr(history, 'created', ''))
                if created is not None and created >= since:
                    return True

        try:
            for comment in self.jira.comments(issue):
                if not _matches_user(getattr(comment, 'author', None)):
                    continue
                created = _parse_dt(getattr(comment, 'created', ''))
                if created is not None and created >= since:
                    return True
        except Exception:
            pass

        return False

    def user_assigned_within(self, issue: Any, user_display: str, since: datetime.datetime) -> bool:
        """
        Check whether an issue was assigned to a given user on or after a given datetime.

        Matches assignee-change entries in the changelog whose `toString` equals the
        supplied display name. Useful for spotting tickets that have been handed to
        someone recently but where they haven't yet commented or transitioned anything
        themselves. For best results, fetch the issue with `changelog=True`.

        Args:
            issue: Jira issue object.
            user_display: Display name to match against the assignee change's toString.
            since: Naive datetime; only assignments on or after this point count.
        Returns:
            True if the issue was assigned to the user in the window.
        """
        if not user_display:
            return False
        target = user_display.strip().lower()

        def _parse_dt(value: str) -> Optional[datetime.datetime]:
            if not value:
                return None
            try:
                return datetime.datetime.strptime(value[:19], '%Y-%m-%dT%H:%M:%S')
            except (ValueError, TypeError):
                return None

        changelog = getattr(issue, 'changelog', None)
        if changelog is None:
            return False

        for history in getattr(changelog, 'histories', None) or []:
            created = _parse_dt(getattr(history, 'created', ''))
            if created is None or created < since:
                continue
            for item in getattr(history, 'items', None) or []:
                if getattr(item, 'field', '') != 'assignee':
                    continue
                to_string = (getattr(item, 'toString', '') or '').strip().lower()
                if to_string == target:
                    return True
        return False

    def days_active(self, issue: Any, inactive_statuses: Optional[List[str]] = None) -> Optional[int]:
        """
        Return the number of days since the issue last transitioned out of an
        inactive status (default: New, Approved, Ready) into any other status.

        Returns None if no such transition is found in the changelog. For best
        results, fetch the issue with `changelog=True` so the changelog is
        available without an extra round-trip.

        Args:
            issue: Jira issue object.
            inactive_statuses: Status names considered "not yet active".
        Returns:
            Days since the most recent out-of-inactive transition, or None.
        """
        if inactive_statuses is None:
            inactive_statuses = ['New', 'Approved', 'Ready']
        inactive_lower = {s.lower() for s in inactive_statuses}

        changelog = getattr(issue, 'changelog', None)
        if changelog is None:
            return None

        most_recent: Optional[datetime.datetime] = None
        for history in getattr(changelog, 'histories', None) or []:
            created_str = getattr(history, 'created', '') or ''
            try:
                created = datetime.datetime.strptime(created_str[:19], '%Y-%m-%dT%H:%M:%S')
            except (ValueError, TypeError):
                continue

            for item in getattr(history, 'items', None) or []:
                if getattr(item, 'field', '') != 'status':
                    continue
                from_status = (getattr(item, 'fromString', '') or '').lower()
                to_status = (getattr(item, 'toString', '') or '').lower()
                if from_status in inactive_lower and to_status not in inactive_lower:
                    if most_recent is None or created > most_recent:
                        most_recent = created

        if most_recent is None:
            return None

        return (datetime.datetime.now() - most_recent).days

    def set_reference_issue(self, issues: Any) -> None:
        """
        Set the reference issue for creating new issues.
        Args:
            issues: List of Jira issues.
        """
        if (len(issues) > 0):
            for issue in issues:
                # Epics now show up in the backlog, but they make a poor template
                # for new issues
                if self.is_epic(issue):
                    continue
                potential_ref_issue = MyJiraIssue(issue, self.jira)
                if potential_ref_issue.sprint == None or len(potential_ref_issue.sprint) == 1:
                    self.reference_issue = issue

    def search_for_issue(self, search_text: str) -> Any:
        """
        Search for an issue by key, id, or summary.
        Args:
            search_text: Search string.
        Returns:
            List of matching issues.
        """
        issues = [] 
        
        # Handle None or empty search text
        if not search_text:
            return issues

        # Check if it's a ticket key format (letters followed by dash and numbers)
        import re
        ticket_pattern = re.match(r'^([A-Za-z]+)-(\d+)$', search_text.strip())
        
        if ticket_pattern:
            # If it matches ticket format (e.g., BIPS-26707, EPM-1234, HELP-456), search globally
            try:
                issues = [self.jira.issue(search_text)]
            except:
                # If direct lookup fails, try broader search across all projects
                issues = self.search_issues(f'key = "{search_text}" ORDER BY Rank ASC')
        elif (search_text.isdigit()):
            # For pure numbers, default to current project prefix (existing behavior)
            issues = self.search_issues(f'{self._search_scope()} AND id = \'{self.project_name}-{search_text}\' AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')
        else:
            # For text searches, search in summary (existing behavior)
            issues = self.search_issues(f'{self._search_scope()} AND summary ~ \'{search_text}*\' AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

        self.set_reference_issue(issues)

        return issues

    def get_labels(self) -> List[str]:
        """
        Get the list of labels available in the Jira instance, for use in
        label-based searching and fuzzy completion. Results are cached for
        the lifetime of the session.
        Returns:
            Sorted list of label strings.
        """
        if getattr(self, "_labels_cache", None) is not None:
            return self._labels_cache

        labels: List[str] = []
        url = f"{self.url}/rest/api/3/label"
        auth = (self.username, self.password)
        headers = {"Accept": "application/json"}
        start_at = 0
        max_results = 1000

        try:
            while True:
                response = requests.get(
                    url,
                    params={"startAt": start_at, "maxResults": max_results},
                    auth=auth,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                values = data.get("values", [])
                labels.extend(values)
                if data.get("isLast", True) or not values:
                    break
                start_at += max_results
        except requests.RequestException:
            # Fall back to whatever we managed to gather rather than failing the search
            pass

        self._labels_cache = sorted(set(labels))
        return self._labels_cache

    def search_by_label(self, label: str) -> Any:
        """
        Search for issues in the current project/product carrying the given label.
        Args:
            label: The label to search for.
        Returns:
            List of matching issues.
        """
        issues = []

        if not label:
            return issues

        issues = self.search_issues(f'{self._search_scope()} AND labels = "{label}" AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

        self.set_reference_issue(issues)

        return issues

    def get_escalation_issues(self) -> Any:
        """
        Get escalation issues for the current product.
        Returns:
            List of escalation issues.
        """
        if not self.product_name:
            raise Exception(f"Team '{self.team_name}' has no product_name configured; escalations view unavailable")
        issues = self.search_issues(f'project = HELP AND "Product[Dropdown]" in ("{self.product_name}") AND statuscategory not in (Done) ORDER BY Rank ASC')
        self.set_reference_issue(issues)
        return issues

    def create_linked_issue_on_sprint(self, issue: Any) -> Any:
        """
        Create a linked spike issue on the current sprint.
        Args:
            issue: Jira issue object to link from.
        Returns:
            The new linked issue.
        """
        # Update ther reference issue so that we can create an issue on sprint
        self.get_sprint_issues()
        url = issue.fields.issuetype.self
        new_title = f"SPIKE: {issue.fields.summary}"
        original_description = self.get_body(issue, format_as_html=False)
        new_description = f"Spike to investigate {issue.key} : {url}\n\n## Original Description\n\n{original_description}"
        new_issue = self.create_sprint_issue(new_title, new_description, "Spike")
        self.jira.create_issue_link("Relates", issue, new_issue)
        return new_issue

    def get_linked_issues(self, issue: Any, issue_type: str) -> Any:
        """
        Get issues linked to a given issue of a specific type.
        Args:
            issue: Jira issue object.
            issue_type: Type of linked issues to find.
        Returns:
            List of linked issues.
        """
        product_clause = f' AND "Product[Dropdown]" in ("{self.product_name}")' if self.product_name else ''
        linked_issues = self.search_issues(f'project = {self.project_name}{product_clause} AND issue in linkedIssues({issue.key}) AND issuetype = "{issue_type}" ORDER BY Rank ASC')
        return linked_issues

    def set_story_points(self, issue: Any, points: Union[int, float]) -> None:
        """
        Set the story points for an issue.
        Args:
            issue: Jira issue object.
            points: Number of story points.
        """
        wrappedIssue = MyJiraIssue(issue, self.jira)
        wrappedIssue.story_points = points
        issue.update(fields={wrappedIssue.story_points_fieldname: points})

    def get_child_issues(self, issue: Any) -> Any:
        """
        Get the children of an issue. The parent field covers both relationships
        Jira models: a story's children are its sub-tasks, an epic's children are
        its stories and bugs.
        Args:
            issue: Jira issue object.
        Returns:
            List of child issues.
        """
        children = self.search_issues(f'project = {self.project_name} AND parent={issue.key} ORDER BY Rank ASC')
        return children

    @staticmethod
    def is_epic(issue: Any) -> bool:
        """
        Whether an issue is an epic, i.e. one whose children are whole issues
        rather than sub-tasks.
        Args:
            issue: Jira issue object.
        Returns:
            True if the issue is an epic.
        """
        return str(getattr(getattr(issue, "fields", None), "issuetype", "")) == "Epic"

    def set_rank_above(self, issue: Any, above_issue: Any) -> None:
        """
        Rank an issue above another issue.
        Args:
            issue: Jira issue object to move.
            above_issue: Jira issue object to rank above.
        """
        self.jira.rank(issue.key, above_issue.key)

    def set_rank_below(self, issue: Any, below_issue: Any) -> None:
        """
        Rank an issue below another issue.
        Args:
            issue: Jira issue object to move.
            below_issue: Jira issue object to rank below.
        """
        self.jira.rank(issue.key, None, below_issue.key)

    def move_to_backlog(self, issue: Any) -> None:
        """
        Move an issue to the backlog.
        Args:
            issue: Jira issue object.
        """
        self.jira.move_to_backlog([issue.key])

    def move_to_sprint(self, issue: Any) -> None:
        """
        Move an issue to the current active sprint.
        Args:
            issue: Jira issue object.
        Raises:
            Exception: If no active sprint is found.
        """
        self.jira.add_issues_to_sprint(self._get_active_sprint_id(), [issue.key])

    def _get_active_sprint_id(self) -> int:
        """
        Get the id of the team's active sprint (cached for 5 minutes). Uses the
        board API when a board is configured, otherwise infers the sprint from
        an issue already in an open sprint.
        Raises:
            Exception: If no active sprint can be found.
        """
        current_time = datetime.datetime.now().timestamp()

        # Check if we have a cached active sprint and it's still valid
        if (self._active_sprint_cache is not None and
            self._active_sprint_cache_timestamp is not None and
            current_time - self._active_sprint_cache_timestamp < self._active_sprint_cache_duration):
            return self._active_sprint_cache

        sprint_id = None
        if self.backlog_board_id:
            # Fetch active sprint from API
            sprints = self.jira.sprints(self.backlog_board_id, extended=True, startAt=0, maxResults=1, state='active')
            if len(sprints) > 0:
                sprint_id = sprints[0].id
        else:
            # Board-less fallback: infer the sprint from an issue already in it
            for issue in self.get_sprint_issues():
                sprints = MyJiraIssue(issue, self.jira).sprint or []
                active = [sprint for sprint in sprints if getattr(sprint, 'state', None) == 'active']
                if active:
                    sprint_id = int(max(active, key=lambda sprint: int(sprint.id)).id)
                    break

        if sprint_id is None:
            raise Exception("No active sprint found")

        # Cache the result
        self._active_sprint_cache = sprint_id
        self._active_sprint_cache_timestamp = current_time
        return sprint_id

    def get_body(self, issue: Any, include_comments: bool = False, format_as_html: bool = False) -> str:
        """
        Generate a markdown description of the issue with optional comments.
        Args:
            issue: The Jira issue object.
            include_comments: Whether to include comments in the output.
            format_as_html: Whether to convert the markdown to HTML using the markdown library.
        Returns:
            String containing the markdown description or HTML if format_as_html is True.
        """
        formatter = JiraIssueMarkdownFormatter(self.jira)
        return formatter.format(issue, include_comments=include_comments, format_as_html=format_as_html)

    def create_backlog_issue(self, title: str, description: str, issue_type: str, found_in_build: str = None, component_id: str = None) -> Any:
        """
        Create a new backlog issue.
        Args:
            title: Issue summary.
            description: Issue description.
            issue_type: Type of the issue (e.g., Story, Bug).
            found_in_build: Optional build number where issue was found.
            component_id: Optional component ID.
        Returns:
            The new issue object.
        """
        issue_dict = self.__build_issue(None, title, description, issue_type, found_in_build, component_id)
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def create_sprint_issue(self, title: str, description: str, issue_type: str, found_in_build: str = None, component_id: str = None) -> Any:
        """
        Create a new sprint issue.
        Args:
            title: Issue summary.
            description: Issue description.
            issue_type: Type of the issue (e.g., Story, Bug).
            found_in_build: Optional build number where issue was found.
            component_id: Optional component ID.
        Returns:
            The new issue object.
        Raises:
            Exception: If the reference issue has more than one sprint.
        """
        # Sprint creation needs a reference issue that is actually on a sprint,
        # so only the sprint view is consulted here (not the backlog fallback).
        if self.reference_issue is None:
            self.get_sprint_issues()
            if self.reference_issue is None:
                raise Exception("No reference issue available and no sprint issues found to use as reference")

        issue_dict = self.__build_issue(None, title, description, issue_type, found_in_build, component_id)
        ref_issue = MyJiraIssue(self.reference_issue, self.jira)

        if ref_issue.sprint is None or len(ref_issue.sprint) > 1:
            raise Exception("Reference issue has more than one sprint, please select a single sprint issue")

        issue_dict[ref_issue.sprint_fieldname] = int(ref_issue.sprint[-1].id)     # Sprint
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def create_sub_task(self, parent_issue: Any, title: str, description: str, issue_type: str = "Sub-task") -> Any:
        """
        Create a new child of a parent issue. With the default type this is a
        sub-task; pass a standard type to create an issue inside an epic.
        Args:
            parent_issue: Parent Jira issue object.
            title: Sub-task summary.
            description: Sub-task description.
            issue_type: Type of the sub-task (default: "Sub-task").
        Returns:
            The new sub-task issue object.
        """
        issue_dict = self.__build_issue(parent_issue, title, description, issue_type)
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def get_possible_types(self) -> List[Any]:
        """
        Get possible issue types for the current project.
        Returns:
            List of possible issue types.
        """
        self._ensure_reference_issue()
        possible_types = self.jira.issue_types_for_project(self.reference_issue.fields.project.id)
        possible_types = [i for i in possible_types if i.name not in self.ignored_issue_types]
        return possible_types

    def _ensure_reference_issue(self) -> None:
        """
        Ensure a reference issue is available, lazily loading from the current
        sprint then the backlog if needed. Falls back to the first returned
        issue if set_reference_issue could not match one on sprint criteria
        (e.g. when the sprint custom field is not resolvable on the issue).
        Raises:
            Exception: If no reference issue can be found in either view.
        """
        if self.reference_issue is not None:
            return
        for fetch in (self.get_sprint_issues, self.get_backlog_issues):
            issues = fetch()
            if self.reference_issue is not None:
                return
            non_epics = [issue for issue in issues if not self.is_epic(issue)]
            if non_epics:
                self.reference_issue = non_epics[0]
                return
        raise Exception("No reference issue available; load a sprint or backlog view first")

    def get_statuses(self, issue: Any) -> List[Any]:
        """
        Get possible statuses for an issue.
        Args:
            issue: Jira issue object.
        Returns:
            List of possible statuses.
        """
        issuetypes = self.jira.issue_types_for_project(issue.fields.project.id)
        if issue.fields.issuetype.name == "Sub-task":
            issuetypes = [i for i in issuetypes if i.name == "Sub-task"]
        else:
            issuetypes = [i for i in issuetypes if i.name != "Sub-task"]
        statuses = issuetypes[0].statuses

        return statuses

    def change_status(self, issue: Any, status: str) -> None:
        """
        Change the status of an issue.
        Args:
            issue: Jira issue object.
            status: New status to transition to.
        """
        self.jira.transition_issue(issue, status)

    def get_story_points(self, issue: Any) -> str:
        """
        Get the story points for an issue as a string.
        Args:
            issue: Jira issue object.
        Returns:
            Story points as a string.
        """
        sp = MyJiraIssue(issue, self.jira).story_points
        return str(sp) if sp != None else ""

    def get_priority_score(self, issue: Any) -> str:
        """
        Get the priority score for an issue as a string.
        Args:
            issue: Jira issue object.
        Returns:
            Priority score as a string.
        """
        ps = MyJiraIssue(issue, self.jira).priority_score
        return str(ps) if ps != None else ""

    def get_assignee(self, issue: Any) -> str:
        """
        Get the assignee's display name for an issue.
        Args:
            issue: Jira issue object.
        Returns:
            Assignee's display name or empty string if unassigned.
        """
        if issue.fields.assignee != None:
            return issue.fields.assignee.displayName
        else:
            return ""

    def assign_to_me(self, issue: Any) -> None:
        """
        Assign the issue to the current user.
        Args:
            issue: Jira issue object.
        """
        self.jira.assign_issue(issue, self.username)

    def assign_to(self, issue: Any, shortname: str) -> None:
        """
        Assign the issue to a user by shortname.
        Args:
            issue: Jira issue object.
            shortname: Shortname of the user.
        """
        username = self.short_names_to_ids[shortname]
        if username == "":
            username = None
        self.jira.assign_issue(issue, username)

    def assign_to_account_id(self, issue: Any, account_id: Optional[str]) -> None:
        """
        Assign the issue to a user by Jira Cloud accountId.
        Args:
            issue: Jira issue object.
            account_id: The user's accountId, or None to unassign.
        """
        response = requests.put(
            f"{self.url}/rest/api/3/issue/{issue.key}/assignee",
            json={"accountId": account_id},
            auth=(self.username, self.password),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

    def get_assignable_users(self) -> List[Dict[str, str]]:
        """
        Get the users assignable to issues in the current project. Served from
        memory, then from a 5-day on-disk cache (stale entries are returned
        immediately while a background thread refreshes), then fetched from Jira.
        Returns:
            List of {"displayName": ..., "accountId": ...} dicts sorted by display name.
        """
        if self._assignable_users_cache is not None:
            return self._assignable_users_cache

        entry = self._load_assignable_users_from_disk()
        if entry:
            # Stale-while-revalidate: never make the user wait for data we already have
            self._assignable_users_cache = entry["users"]
            if time.time() - entry.get("timestamp", 0) > ASSIGNABLE_USERS_TTL_SECONDS:
                self._start_assignable_users_refresh()
            return self._assignable_users_cache

        # Cold project: the only remaining blocking path
        users = self._fetch_assignable_users(self.project_name)
        if users:
            # Only cache success so a transient failure retries on the next keypress
            self._assignable_users_cache = users
            self._save_assignable_users_to_disk(self.project_name, users)
        return users

    def warm_assignable_users_cache(self) -> None:
        """
        Pre-load the current project's assignable users from disk and kick a
        background refresh if the entry is stale or missing. Never blocks;
        intended to be called once at startup.
        """
        if self._assignable_users_cache is not None:
            return
        entry = self._load_assignable_users_from_disk()
        if entry:
            self._assignable_users_cache = entry["users"]
            if time.time() - entry.get("timestamp", 0) <= ASSIGNABLE_USERS_TTL_SECONDS:
                return
        self._start_assignable_users_refresh()

    def _fetch_assignable_users(self, project_name: str) -> List[Dict[str, str]]:
        """
        Fetch the users assignable to issues in a project from Jira.
        Args:
            project_name: Jira project key to query.
        Returns:
            List of {"displayName": ..., "accountId": ...} dicts sorted by display name.
        """
        users: List[Dict[str, str]] = []
        url = f"{self.url}/rest/api/3/user/assignable/search"
        auth = (self.username, self.password)
        headers = {"Accept": "application/json"}
        start_at = 0
        max_results = 200

        try:
            while True:
                response = requests.get(
                    url,
                    params={"project": project_name, "startAt": start_at, "maxResults": max_results},
                    auth=auth,
                    headers=headers,
                )
                response.raise_for_status()
                # Unlike most list endpoints this one returns a bare JSON array,
                # so paginate until a page comes back short
                page = response.json()
                users.extend(
                    {"displayName": user.get("displayName", ""), "accountId": user["accountId"]}
                    for user in page
                    if user.get("accountType") == "atlassian" and user.get("active")
                )
                if len(page) < max_results:
                    break
                start_at += max_results
        except requests.RequestException:
            # Fall back to whatever we managed to gather rather than failing the prompt
            pass

        users.sort(key=lambda user: user["displayName"])
        return users

    def _start_assignable_users_refresh(self) -> None:
        """
        Spawn at most one daemon thread refreshing the current project's
        assignable users.
        """
        with self._assignable_users_refresh_lock:
            if self._assignable_users_refreshing:
                return
            self._assignable_users_refreshing = True
        # Capture now so a mid-fetch team switch cannot mislabel the result
        project_name = self.project_name
        threading.Thread(target=self._refresh_assignable_users, args=(project_name,), daemon=True).start()

    def _refresh_assignable_users(self, project_name: str) -> None:
        """
        Background worker: fetch, persist under the captured project key, and
        update the memory cache only if that project is still current. Touches
        only requests, file writes and one atomic attribute rebind, never the UI.
        Args:
            project_name: Jira project key captured when the refresh was started.
        """
        try:
            users = self._fetch_assignable_users(project_name)
            if users:
                self._save_assignable_users_to_disk(project_name, users)
                if project_name == self.project_name:
                    self._assignable_users_cache = users
        finally:
            with self._assignable_users_refresh_lock:
                self._assignable_users_refreshing = False

    def _assignable_users_cache_path(self) -> Optional[str]:
        """
        Path of the on-disk assignable-users cache, or None when disk caching
        is disabled.
        """
        if not self.cache_dir:
            return None
        return os.path.join(self.cache_dir, ASSIGNABLE_USERS_CACHE_FILENAME)

    def _read_assignable_users_cache_file(self) -> Dict[str, Any]:
        """
        Parse the on-disk cache file, keyed by project name. Returns {} on a
        missing or corrupt file so the next save simply overwrites it.
        """
        path = self._assignable_users_cache_path()
        if path is None:
            return {}
        try:
            with open(path, "r") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_assignable_users_cache_file(self, data: Dict[str, Any]) -> None:
        """
        Atomically rewrite the on-disk cache file, so concurrent readers (e.g.
        the MCP server) never see a torn file. Silently ignores I/O errors.
        """
        path = self._assignable_users_cache_path()
        if path is None:
            return
        try:
            temp_path = f"{path}.{os.getpid()}.tmp"
            with open(temp_path, "w") as file:
                json.dump(data, file, indent=2)
            os.replace(temp_path, path)
        except OSError:
            pass

    def _load_assignable_users_from_disk(self) -> Optional[Dict[str, Any]]:
        """
        Load the current project's cached users from disk.
        Returns:
            {"timestamp": epoch_seconds, "users": [...]} or None when disk
            caching is disabled or there is no usable entry.
        """
        entry = self._read_assignable_users_cache_file().get(self.project_name)
        if isinstance(entry, dict) and isinstance(entry.get("users"), list) and entry["users"]:
            return entry
        return None

    def _save_assignable_users_to_disk(self, project_name: str, users: List[Dict[str, str]]) -> None:
        """
        Persist a project's user list to the on-disk cache with the current
        timestamp. No-op when disk caching is disabled or the list is empty.
        Args:
            project_name: Jira project key the users belong to.
            users: List of {"displayName": ..., "accountId": ...} dicts.
        """
        if self._assignable_users_cache_path() is None or not users:
            return
        data = self._read_assignable_users_cache_file()
        data[project_name] = {"timestamp": time.time(), "users": users}
        self._write_assignable_users_cache_file(data)

    def _remove_assignable_users_from_disk(self, project_name: str) -> None:
        """
        Drop a project's entry from the on-disk cache, forcing the next lookup
        to refetch. Tolerant of a missing file or entry.
        Args:
            project_name: Jira project key to remove.
        """
        data = self._read_assignable_users_cache_file()
        if project_name in data:
            del data[project_name]
            self._write_assignable_users_cache_file(data)

    # Returns a dictionary of keypresses to shortnames
    def get_user_shortnames(self) -> Any:
        """
        Get all user shortnames for the current team.
        Returns:
            Iterable of user shortnames.
        """
        return self.short_names_to_ids.keys()

    def get_user_shortname_to_id(self) -> Dict[str, str]:
        """
        Get mapping from user shortnames to user IDs.
        Returns:
            Dictionary mapping shortnames to user IDs.
        """
        return self.short_names_to_ids

    def _open_url(self, url: str) -> None:
        """
        Open a URL in a browser. On Linux without UI, use external 'browse' command.
        Args:
            url: URL to open.
        """
        # Check if we're on Linux and DISPLAY is not set (no UI available)
        if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
            # Use external browse command
            try:
                subprocess.run(["browse", url], check=True)
            except FileNotFoundError:
                # Fallback to webbrowser if browse command not found
                webbrowser.open(url)
        else:
            # Use standard webbrowser module
            webbrowser.open(url)

    def browse_to(self, issue: Any) -> None:
        """
        Open the issue in a web browser.
        Args:
            issue: Jira issue object.
        """
        self._open_url(issue.permalink())

    def browse_sprint_board(self) -> None:
        """
        Open the sprint board in a web browser.
        """
        if not self.backlog_board_id:
            raise Exception(f"No backlog board configured for team '{self.team_name}'")
        self._open_url(f"{self.url}/secure/RapidBoard.jspa?rapidView={self.backlog_board_id}")

    def browse_backlog_board(self) -> None:
        """
        Open the backlog board in a web browser.
        """
        if not self.backlog_board_id:
            raise Exception(f"No backlog board configured for team '{self.team_name}'")
        url = f"{self.url}/secure/RapidBoard.jspa?rapidView={self.backlog_board_id}&view=planning.nodetail"
        self._open_url(url)

    def browse_kanban_board(self) -> None:
        """
        Open the kanban board in a web browser.
        """
        if not self.kanban_board_id:
            raise Exception(f"No kanban board configured for team '{self.team_name}'")
        url = f"{self.url}/secure/RapidBoard.jspa?rapidView={self.kanban_board_id}"
        self._open_url(url)

    # Downloads all attachments for the given issue to the given path, calls callback with the filename before each download
    def download_attachments(self, issue: Any, path: str, callback: Optional[Any] = None) -> None:
        """
        Download all attachments for the given issue to the given path.
        Args:
            issue: Jira issue object.
            path: Local directory to save attachments.
            callback: Optional callback called with filename before each download.
        """
        attachments = issue.fields.attachment
        for attachment in attachments:
            filename = attachment.filename
            local_filename = os.path.join(path, filename)
            if not os.path.exists(local_filename):
                if (callback != None):
                    callback(filename)
                with open(local_filename, "wb") as f:
                    f.write(attachment.get())

                        #
    # Builds an issue dictionary from the reference issue
    # If parent_issue is not None, then the new issue will be a sub-task of the parent
    # issue_type can be "Story", "Task", "Bug", etc.
    #
    def _convert_to_adf(self, plain_text: str) -> Dict[str, Any]:
        """
        Convert plain text to Atlassian Document Format (ADF).
        Args:
            plain_text: Plain text string to convert.
        Returns:
            Dictionary in ADF format.
        """
        if not plain_text:
            plain_text = ""
        
        # Split text into paragraphs (by double newlines or single newlines)
        paragraphs = plain_text.split('\n\n') if '\n\n' in plain_text else plain_text.split('\n')
        
        content = []
        for paragraph in paragraphs:
            if paragraph.strip():  # Only add non-empty paragraphs
                content.append({
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": paragraph.strip()
                        }
                    ]
                })
        
        # If no content, add an empty paragraph
        if not content:
            content = [{
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": ""
                    }
                ]
            }]
        
        return {
            "type": "doc",
            "version": 1,
            "content": content
        }

    def __build_issue(self, parent_issue: Optional[Any], title: str, description: str, issue_type: str, found_in_build: str = None, component_id: str = None) -> Dict[str, Any]:
        """
        Build an issue dictionary from the reference issue.
        Args:
            parent_issue: Parent Jira issue object, or None.
            title: Issue summary.
            description: Issue description.
            issue_type: Type of the issue (e.g., Story, Bug).
            found_in_build: Optional build number where issue was found.
            component_id: Optional component ID.
        Returns:
            Dictionary representing the new issue fields.
        Raises:
            Exception: If no reference issue is set.
        """
        self._ensure_reference_issue()

        ref_issue = MyJiraIssue(self.reference_issue, self.jira)

        issue_dict = {
            'project': {'id': self.reference_issue.fields.project.id},
            'summary': title,
            'description': self._convert_to_adf(description),
            'issuetype': {'name': issue_type},
            }

        # Projects without the Product dropdown or a Jira team leave these unset
        if getattr(ref_issue, 'product', None):
            issue_dict[ref_issue.product_fieldname] = {'id': ref_issue.product.id}

        if (parent_issue != None):
            issue_dict["parent"] = {"id": parent_issue.id}
        elif getattr(ref_issue, 'team', None):
            issue_dict[ref_issue.team_fieldname] = ref_issue.team.id

        # Add Found In build number if provided
        if found_in_build and found_in_build.strip():
            issue_dict['customfield_10100'] = found_in_build.strip()

        # Add Component if provided
        if component_id:
            issue_dict['components'] = [{'id': component_id}]

        return issue_dict
