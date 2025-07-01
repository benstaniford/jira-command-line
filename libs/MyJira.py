#scriptdoc: title="My comms library for talking to Jira", tags="bt,work,jira"

# pip install jira
from jira import JIRA
from .MyJiraIssue import MyJiraIssue
import os
import datetime
import webbrowser
import markdown
from typing import Any, Dict, List, Optional, Union

class MyJira:
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the MyJira instance with configuration.
        Args:
            config: Dictionary containing Jira and team configuration.
        """
        self.config = config
        self.url = config["url"]
        self.password = config["password"]

        # Stuff specific to me
        self.server = {"server": self.url}
        self.username = config["username"]
        self.fullname = config["fullname"]

        # Stuff specific to the team
        self.set_team(config["default_team"])

        self.jira = JIRA(self.server, basic_auth=(self.username, self.password))
        self.issue_filter = '(Story, Bug, Spike, Automation, Vulnerability, Support, Task, "Technical Improvement", "Sub-task Bug")' 
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

        self.team_id = current_team["team_id"]
        self.project_name = current_team["project_name"]
        self.product_name = current_team["product_name"]
        self.short_names_to_ids = current_team["short_names_to_ids"]
        self.kanban_board_id = current_team["kanban_board_id"]
        self.backlog_board_id = current_team["backlog_board_id"]
        self.escalation_board_id = current_team["escalation_board_id"]
        
        # Clear active sprint cache when switching teams
        self._active_sprint_cache = None
        self._active_sprint_cache_timestamp = None
        # Clear closed sprints cache when switching teams  
        self._closed_sprints_cache = None
        self._closed_sprints_cache_timestamp = None

    def clear_caches(self) -> None:
        """
        Clear all caches to force fresh API calls.
        """
        self._active_sprint_cache = None
        self._active_sprint_cache_timestamp = None
        self._closed_sprints_cache = None
        self._closed_sprints_cache_timestamp = None
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

    def search_issues(self, search_text: str, changelog: bool = False) -> Any:
        """
        Search for issues using a JQL query.
        Args:
            search_text: JQL query string.
            changelog: Whether to expand changelog.
        Returns:
            List of issues.
        """
        issues = self.jira.search_issues(search_text, startAt=0, maxResults=400, expand="changelog" if changelog else None)
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
        return self.jira.search_issues(f'project = {self.project_name} AND issuetype = "Test Plan" AND summary ~ "{name}" ORDER BY Rank ASC')

    def get_backlog_issues(self) -> Any:
        """
        Get backlog issues for the current team.
        Returns:
            List of backlog issues.
        """
        return self.search_issues(f'project = {self.project_name} AND "Team[Team]"={self.team_id} AND issuetype in {self.issue_filter} AND (sprint is EMPTY or sprint not in openSprints()) AND statuscategory not in (Done) AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

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
        return self.search_issues(f'project = {self.project_name} AND "Team[Team]"={self.team_id} AND issuetype in {self.issue_filter} AND sprint in openSprints() AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC', changelog)

    def get_sprint_by_name(self, name: str, changelog: bool = False) -> Any:
        """
        Get issues in a sprint by sprint name.
        Args:
            name: Sprint name.
            changelog: Whether to expand changelog.
        Returns:
            List of sprint issues.
        """
        return self.search_issues(f'project = {self.project_name} AND "Team[Team]"={self.team_id} AND issuetype in {self.issue_filter} AND sprint="{name}" AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC', changelog)

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
        issues = self.search_issues(f'project = {self.project_name} AND key = {key}')
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
        self.jira.add_comment(issue, comment)

    def set_reference_issue(self, issues: Any) -> None:
        """
        Set the reference issue for creating new issues.
        Args:
            issues: List of Jira issues.
        """
        if (len(issues) > 0):
            for issue in issues:
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

        if (search_text.lower().startswith("epm-") or search_text.lower().startswith("help-")):
            issues = [self.jira.issue(search_text)]
        elif (search_text.isdigit()):
            issues = self.jira.search_issues(f'(project = {self.project_name} OR project = HELP) AND "Product[Dropdown]" in ("{self.product_name}") AND id = \'{self.project_name}-{search_text}\' AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')
        else:
            issues = self.jira.search_issues(f'(project = {self.project_name} OR project = HELP) AND "Product[Dropdown]" in ("{self.product_name}") AND summary ~ \'{search_text}*\' AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

        self.set_reference_issue(issues)

        return issues

    def get_escalation_issues(self) -> Any:
        """
        Get escalation issues for the current product.
        Returns:
            List of escalation issues.
        """
        issues = self.jira.search_issues(f'project = HELP AND "Product[Dropdown]" in ("{self.product_name}") AND statuscategory not in (Done) ORDER BY Rank ASC')
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
        linked_issues = self.jira.search_issues(f'project = {self.project_name} AND "Product[Dropdown]" in ("{self.product_name}") AND issue in linkedIssues({issue.key}) AND issuetype = "{issue_type}" ORDER BY Rank ASC')
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

    def get_sub_tasks(self, issue: Any) -> Any:
        """
        Get sub-tasks for an issue.
        Args:
            issue: Jira issue object.
        Returns:
            List of sub-task issues.
        """
        sub_tasks = self.jira.search_issues(f'project = {self.project_name} AND parent={issue.key} AND (issuetype = Sub-task OR issuetype = "Sub-task Bug") ORDER BY Rank ASC')
        return sub_tasks

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
        # Get the current sprint for my team (with caching)
        current_time = datetime.datetime.now().timestamp()
        
        # Check if we have a cached active sprint and it's still valid
        if (self._active_sprint_cache is not None and 
            self._active_sprint_cache_timestamp is not None and
            current_time - self._active_sprint_cache_timestamp < self._active_sprint_cache_duration):
            sprint_id = self._active_sprint_cache
        else:
            # Fetch active sprint from API
            sprints = self.jira.sprints(self.backlog_board_id, extended=True, startAt=0, maxResults=1, state='active')
            if len(sprints) > 0:
                sprint_id = sprints[0].id
                # Cache the result
                self._active_sprint_cache = sprint_id
                self._active_sprint_cache_timestamp = current_time
            else:
                raise Exception("No active sprint found")
        
        self.jira.add_issues_to_sprint(sprint_id, [issue.key])

    def add_titled_section(self, body: str, title: str, content: Optional[str]) -> str:
        """
        Add a titled section to the Markdown document.
        Args:
            body: Existing markdown content.
            title: Section title.
            content: Section content.
        Returns:
            Updated markdown with the new section added.
        """
        if (content != None and content != ""):
            # Format with markdown header style
            body += f"## {title}\n\n{content}\n\n"
        return body

    def _add_field_section(self, wrapped_issue: Any, whole_description: str, field_name: str, section_title: str) -> str:
        """
        Helper method to add a field section to the description if the field exists.
        Args:
            wrapped_issue: MyJiraIssue wrapper object.
            whole_description: Current markdown description.
            field_name: Field name to check.
            section_title: Section title for markdown.
        Returns:
            Updated markdown description.
        """
        if wrapped_issue.has_field(field_name):
            field_value = getattr(wrapped_issue, field_name, "")
            whole_description = self.add_titled_section(whole_description, section_title, field_value)
        return whole_description

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
        wrapped_issue = MyJiraIssue(issue, self.jira)
        whole_description = ""
        
        # Always add the issue ID
        whole_description = self.add_titled_section(whole_description, "Issue ID: ", issue.key)
        
        # Define field mappings for sections
        field_sections = [
            ("summary", "Summary"),
            ("description", "Description"),
            ("acceptance_criteria", "Acceptance Criteria"),
            ("test_result_evidence", "Test Result and Evidence"),
            ("repro_steps", "Reproduction Steps"),
            ("customer_repro_steps", "Steps to Reproduce"),
            ("relevant_environment", "Relevant Environment"),
            ("expected_results", "Expected Results"),
            ("actual_results", "Actual Results")
        ]
        
        # Add each field section if it exists
        for field_name, section_title in field_sections:
            whole_description = self._add_field_section(wrapped_issue, whole_description, field_name, section_title)

        # Add any additional fields that weren't covered in the predefined sections
        whole_description = self._add_additional_fields(wrapped_issue, whole_description, field_sections)

        if (include_comments):
            comments = self.jira.comments(issue.key)
            comments.reverse()
            for comment in comments:
                whole_description = self.add_titled_section(whole_description, f"Comment by {comment.author.displayName}", comment.body)

        # Convert to HTML if requested
        if format_as_html:
            return markdown.markdown(whole_description, extensions=['fenced_code', 'tables'])
        
        return whole_description

    def create_backlog_issue(self, title: str, description: str, issue_type: str) -> Any:
        """
        Create a new backlog issue.
        Args:
            title: Issue summary.
            description: Issue description.
            issue_type: Type of the issue (e.g., Story, Bug).
        Returns:
            The new issue object.
        """
        issue_dict = self.__build_issue(None, title, description, issue_type)
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def create_sprint_issue(self, title: str, description: str, issue_type: str) -> Any:
        """
        Create a new sprint issue.
        Args:
            title: Issue summary.
            description: Issue description.
            issue_type: Type of the issue (e.g., Story, Bug).
        Returns:
            The new issue object.
        Raises:
            Exception: If the reference issue has more than one sprint.
        """
        issue_dict = self.__build_issue(None, title, description, issue_type)
        ref_issue = MyJiraIssue(self.reference_issue, self.jira)
        
        if len(ref_issue.sprint) > 1:
            raise Exception("Reference issue has more than one sprint, please select a single sprint issue")

        issue_dict[ref_issue.sprint_fieldname] = int(ref_issue.sprint[-1].id)     # Sprint
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def create_sub_task(self, parent_issue: Any, title: str, description: str, issue_type: str = "Sub-task") -> Any:
        """
        Create a new sub-task for a parent issue.
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
        possible_types = self.jira.issue_types_for_project(self.reference_issue.fields.project.id)
        possible_types = [i for i in possible_types if i.name not in self.ignored_issue_types]
        return possible_types

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

    def browse_to(self, issue: Any) -> None:
        """
        Open the issue in a web browser.
        Args:
            issue: Jira issue object.
        """
        webbrowser.open(issue.permalink())

    def browse_sprint_board(self) -> None:
        """
        Open the sprint board in a web browser.
        """
        webbrowser.open(f"{self.url}/secure/RapidBoard.jspa?rapidView={self.backlog_board_id}")

    def browse_backlog_board(self) -> None:
        """
        Open the backlog board in a web browser.
        """
        url = f"{self.url}/secure/RapidBoard.jspa?rapidView={self.backlog_board_id}&view=planning.nodetail"
        webbrowser.open(url)

    def browse_kanban_board(self) -> None:
        """
        Open the kanban board in a web browser.
        """
        url = f"{self.url}/secure/RapidBoard.jspa?rapidView={self.kanban_board_id}"
        webbrowser.open(url)

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
    def __build_issue(self, parent_issue: Optional[Any], title: str, description: str, issue_type: str) -> Dict[str, Any]:
        """
        Build an issue dictionary from the reference issue.
        Args:
            parent_issue: Parent Jira issue object, or None.
            title: Issue summary.
            description: Issue description.
            issue_type: Type of the issue (e.g., Story, Bug).
        Returns:
            Dictionary representing the new issue fields.
        Raises:
            Exception: If no reference issue is set.
        """
        if (self.reference_issue == None):
            raise Exception("No reference issue found, please call get_backlog_issues() or get_sprint_issues() first")

        ref_issue = MyJiraIssue(self.reference_issue, self.jira)

        issue_dict = {
            'project': {'id': self.reference_issue.fields.project.id},
            'summary': title,
            'description': description,
            ref_issue.product_fieldname: {'id': ref_issue.product.id}, # Product
            'issuetype': {'name': issue_type},
            }

        if (parent_issue != None):
            issue_dict["parent"] = {"id": parent_issue.id}
        else:
            issue_dict[ref_issue.team_fieldname] = ref_issue.team.id

        return issue_dict

    def _add_additional_fields(self, wrapped_issue: Any, whole_description: str, covered_fields: List[tuple]) -> str:
        """
        Add any additional fields from the Jira issue that weren't covered in the predefined sections.
        
        Args:
            wrapped_issue: MyJiraIssue wrapper object.
            whole_description: Current markdown description.
            covered_fields: List of tuples (field_name, section_title) that were already processed.
            
        Returns:
            Updated markdown description with additional fields.
        """
        try:
            # Get all available fields from Jira
            all_jira_fields = self.jira.fields()
            
            # Create a mapping of field IDs to field names
            field_id_to_name = {field['id']: field['name'] for field in all_jira_fields}
            
            # Get the list of field names that were already covered
            covered_field_names = {field_name for field_name, _ in covered_fields}
            
            # Also add standard fields that we always skip
            skip_fields = {
                'summary', 'description', 'issuekey', 'project', 'issuetype', 'status', 
                'resolution', 'created', 'updated', 'reporter', 'assignee', 'priority',
                'labels', 'components', 'versions', 'fixVersions', 'attachment',
                'comment', 'worklog', 'timetracking', 'votes', 'watches', 'subtasks',
                'issuelinks', 'changelog', 'transitions', 'operations', 'editmeta',
                'renderedFields', 'names', 'schema', 'expand'
            }
            
            # Get all field IDs that have values in the issue
            issue_fields = wrapped_issue.issue.raw.get('fields', {})
            
            additional_fields_added = False
            
            for field_id, field_value in issue_fields.items():
                # Skip if field has no value or is None
                if field_value is None or field_value == "" or field_value == []:
                    continue
                    
                # Get the field name from Jira
                field_name = field_id_to_name.get(field_id, field_id)
                
                # Skip if this field was already covered or should be skipped
                if field_id in skip_fields or any(covered_field in field_id.lower() or covered_field in field_name.lower() 
                                                 for covered_field in covered_field_names):
                    continue
                
                # Skip system fields and internal Jira fields
                if (field_id.startswith('customfield_') == False and 
                    field_id not in ['environment', 'duedate', 'timeestimate', 'timespent']):
                    continue
                
                # Try to get a clean field value
                try:
                    if hasattr(field_value, 'displayName'):
                        clean_value = field_value.displayName
                    elif hasattr(field_value, 'name'):
                        clean_value = field_value.name
                    elif hasattr(field_value, 'value'):
                        clean_value = field_value.value
                    elif isinstance(field_value, list):
                        if len(field_value) > 0:
                            if hasattr(field_value[0], 'displayName'):
                                clean_value = ', '.join([item.displayName for item in field_value])
                            elif hasattr(field_value[0], 'name'):
                                clean_value = ', '.join([item.name for item in field_value])
                            elif hasattr(field_value[0], 'value'):
                                clean_value = ', '.join([item.value for item in field_value])
                            else:
                                clean_value = ', '.join([str(item) for item in field_value])
                        else:
                            continue
                    elif isinstance(field_value, dict):
                        if 'displayName' in field_value:
                            clean_value = field_value['displayName']
                        elif 'name' in field_value:
                            clean_value = field_value['name']
                        elif 'value' in field_value:
                            clean_value = field_value['value']
                        else:
                            clean_value = str(field_value)
                    else:
                        clean_value = str(field_value)
                        
                    # Skip if the cleaned value is empty or too short
                    if not clean_value or len(str(clean_value).strip()) < 1:
                        continue
                        
                    # Add a header for additional fields if this is the first one
                    if not additional_fields_added:
                        whole_description += "## Additional Fields\n\n"
                        additional_fields_added = True
                    
                    # Format the field name for display
                    display_name = field_name.replace('customfield_', '').replace('_', ' ').title()
                    whole_description = self.add_titled_section(whole_description, f"### {display_name}", clean_value)
                    
                except Exception as e:
                    # If we can't process a field, skip it silently
                    continue
                    
        except Exception as e:
            # If there's any error getting additional fields, don't fail the whole method
            print(f"Warning: Could not retrieve additional fields: {e}")
            
        return whole_description