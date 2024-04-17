#scriptdoc: title="My comms library for talking to Jira", tags="bt,work,jira"

# pip install jira
from jira import JIRA
import json
import os
import datetime
import webbrowser

# A wrapper for issues that allow us to translate atttributes to sensible names
class MyJiraIssue:
    def __init__(self, issue):
        self.issue = issue
        self.translations = {
                "description": "description",
                "summary": "summary",
                "repro_steps": "customfield_10093",
                "actual_results": "customfield_10094",
                "expected_results": "customfield_10095",
                "customer_repro_steps": "customfield_10121",
                "relevant_environment": "customfield_10134",
                "sprint": "customfield_10020",
                "story_points": "customfield_10028",
                "product": "customfield_10108",
                "test_results": "customfield_10097",
                "team": "customfield_10001",
                "test_steps": "customfield_10039",
            }

        for key in self.translations:
            try:
                # Dynamically set the attribute on this object to the value of the attribute on the issue
                setattr(self, key, getattr(issue.fields, self.translations[key]))
                setattr(self, key + "_fieldname", self.translations[key])
            except:
                setattr(self, key, "")
                setattr(self, key + "_fieldname", self.translations[key])

class MyJira:
    def __init__(self, config):
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
        self.issue_filter = '(Story, Bug, Spike, Automation, Vulnerability, Support, Task, "Technical Improvement", "Sub-task Bug", "Customer Defect")' 
        self.ignored_issue_types = {"Sub-task", "Sub-task Bug", "Test", "Test Set", "Test Plan", "Test Execution", "Precondition", "Sub Test Execution"}

        # We use the reference issue as a template for creating new issues/tasks
        self.reference_issue = None

    def set_team(self, team_name):
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

    def get_teams(self):
        list_teams = []
        for team in self.config['teams']:
            list_teams.append(team)
        return list_teams

    def get_age(self, issue):
        created = datetime.datetime.strptime(issue.fields.created, '%Y-%m-%dT%H:%M:%S.%f%z').replace(tzinfo=None)
        now = datetime.datetime.now().replace(tzinfo=None)
        age = now - created
        return age.days

    # Returns a dictionary of optional field names lambda functions to get the value of each field from an issue
    def get_optional_fields(self):
        optional_fields = {
                "Assignee": lambda issue: str(issue.fields.assignee),
                "Created": lambda issue: str(issue.fields.created[0:16].replace("T", " ")),
                "Updated": lambda issue: str(issue.fields.updated[0:16].replace("T", " ")),
                "Age": lambda issue: str(self.get_age(issue)),
                "Points": lambda issue: self.get_story_points(issue),
                "Issue Type": lambda issue: str(issue.fields.issuetype),
                "Sub-Tasks": lambda issue: str(self.get_subtask_count(issue)),
                "Parent Desc": lambda issue: self.get_parent_description(issue),
            }
        return optional_fields

    def get_subtask_count(self, issue):
        return len(issue.fields.subtasks)

    def get_parent_description(self, issue):
        issue_dict = issue.raw
        parent = issue_dict.get("fields", {}).get("parent", None)
        summary = parent.get("fields", {}).get("summary", "") if parent != None else ""
        if len(summary) > 30:
            summary = summary[0:30] + "..."
        return summary

    def search_issues(self, search_text):
        issues = self.jira.search_issues(search_text, startAt=0, maxResults=400)
        if (len(issues) > 0):
            self.reference_issue = issues[0]
        return issues

    def get_testplan_by_name(self, name):
        return self.jira.search_issues(f'project = {self.project_name} AND issuetype = "Test Plan" AND summary ~ "{name}" ORDER BY Rank ASC')

    def get_backlog_issues(self):
        return self.search_issues(f'project = {self.project_name} AND "Team[Team]"={self.team_id} AND issuetype in {self.issue_filter} AND sprint is EMPTY AND statuscategory not in (Done) AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

    def get_windows_backlog_issues(self):
        return self.search_issues(f'project = {self.project_name} AND "Team[Team]" is EMPTY AND issuetype in {self.issue_filter} AND sprint is EMPTY AND statuscategory not in (Done) AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

    def get_sprint_issues(self):
        return self.search_issues(f'project = {self.project_name} AND "Team[Team]"={self.team_id} AND issuetype in {self.issue_filter} AND sprint in openSprints() AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

    def add_comment(self, issue, comment):
        self.jira.add_comment(issue, comment)

    def search_for_issue(self, search_text):
        issues = [] 

        if (search_text.lower().startswith("epm-") or search_text.lower().startswith("help-")):
            issues = [self.jira.issue(search_text)]
        elif (search_text.isdigit()):
            issues = self.jira.search_issues(f'(project = {self.project_name} OR project = HELP) AND "Product[Dropdown]" in ("{self.product_name}") AND id = \'{self.project_name}-{search_text}\' AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')
        else:
            issues = self.jira.search_issues(f'(project = {self.project_name} OR project = HELP) AND "Product[Dropdown]" in ("{self.product_name}") AND summary ~ \'{search_text}*\' AND (issuetype != Sub-task AND issuetype != "Sub-task Bug") ORDER BY Rank ASC')

        if (len(issues) > 0):
            self.reference_issue = issues[0]

        return issues

    def get_escalation_issues(self):
        issues = self.jira.search_issues(f'project = HELP AND "Product[Dropdown]" in ("{self.product_name}") AND statuscategory not in (Done) ORDER BY Rank ASC')
        if (len(issues) > 0):
            self.reference_issue = issues[0]
        return issues

    def create_linked_issue_on_sprint(self, issue):
        # Update ther reference issue so that we can create an issue on sprint
        self.get_sprint_issues()
        url = issue.fields.issuetype.self
        new_title = f"Spike: {issue.fields.summary}"
        original_description = self.get_body(issue)
        new_description = f"Spike to investigate {issue.key} : {url}\n\n**Original Description**\n\n{original_description}"
        return self.create_sprint_issue(new_title, new_description, "Spike")

    def get_linked_issues(self, issue, issue_type):
        linked_issues = self.jira.search_issues(f'project = {self.project_name} AND "Product[Dropdown]" in ("{self.product_name}") AND issue in linkedIssues({issue.key}) AND issuetype = "{issue_type}" ORDER BY Rank ASC')
        return linked_issues

    def set_story_points(self, issue, points):
        wrappedIssue = MyJiraIssue(issue)
        wrappedIssue.story_points = points
        issue.update(fields={wrappedIssue.story_points_fieldname: points})

    def get_sub_tasks(self, issue):
        sub_tasks = self.jira.search_issues(f'project = {self.project_name} AND parent={issue.key} AND (issuetype = Sub-task OR issuetype = "Sub-task Bug") ORDER BY Rank ASC')
        return sub_tasks

    def set_rank_above(self, issue, above_issue):
        self.jira.rank(issue.key, above_issue.key)

    def set_rank_below(self, issue, below_issue):
        self.jira.rank(issue.key, None, below_issue.key)

    def move_to_backlog(self, issue):
        self.jira.move_to_backlog([issue.key])

    def move_to_sprint(self, issue):
        # Get the current sprint for my team
        sprints = self.jira.sprints(self.backlog_board_id, extended=True, startAt=0, maxResults=1, state='active')
        if len(sprints) > 0:
            sprint_id = sprints[0].id
        else:
            raise Exception("No active sprint found")
        
        self.jira.add_issues_to_sprint(sprint_id, [issue.key])

    def add_titled_section(self, body, title, content):
        if (content != None and content != ""):
            body += f"**{title}**\n\n{content}\n\n"
        return body

    def get_body(self, issue, include_comments=False):
        wrapped_issue = MyJiraIssue(issue)
        whole_description = ""
        whole_description = self.add_titled_section(whole_description, "Description", wrapped_issue.description)
        whole_description = self.add_titled_section(whole_description, "Reproduction Steps", wrapped_issue.repro_steps)    # Backlog
        whole_description = self.add_titled_section(whole_description, "Steps to Reproduce", wrapped_issue.customer_repro_steps)    # Escalations
        whole_description = self.add_titled_section(whole_description, "Relevant Environment", wrapped_issue.relevant_environment)  # Escalations
        whole_description = self.add_titled_section(whole_description, "Expected Results", wrapped_issue.expected_results)
        whole_description = self.add_titled_section(whole_description, "Actual Results", wrapped_issue.actual_results)

        if (include_comments):
            comments = self.jira.comments(issue.key)
            comments.reverse()
            for comment in comments:
                whole_description = self.add_titled_section(whole_description, f"Comment by {comment.author.displayName}", comment.body)

        return whole_description

    def create_backlog_issue(self, title, description, issue_type):
        issue_dict = self.__build_issue(None, title, description, issue_type)
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def create_sprint_issue(self, title, description, issue_type):
        issue_dict = self.__build_issue(None, title, description, issue_type)
        ref_issue = MyJiraIssue(self.reference_issue)
        issue_dict[ref_issue.sprint_fieldname] = int(ref_issue.sprint[-1].id)     # Sprint
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def create_sub_task(self, parent_issue, title, description, issue_type = "Sub-task"):
        issue_dict = self.__build_issue(parent_issue, title, description, issue_type)
        new_issue = self.jira.create_issue(fields=issue_dict)
        return new_issue

    def get_possible_types(self):
        possible_types = self.jira.issue_types_for_project(self.reference_issue.fields.project.id)
        possible_types = [i for i in possible_types if i.name not in self.ignored_issue_types]
        return possible_types

    def get_statuses(self, issue):
        issuetypes = self.jira.issue_types_for_project(issue.fields.project.id)
        if issue.fields.issuetype.name == "Sub-task":
            issuetypes = [i for i in issuetypes if i.name == "Sub-task"]
        else:
            issuetypes = [i for i in issuetypes if i.name != "Sub-task"]
        statuses = issuetypes[0].statuses

        return statuses

    def change_status(self, issue, status):
        self.jira.transition_issue(issue, status)

    def get_story_points(self, issue):
        sp = MyJiraIssue(issue).story_points
        return str(sp) if sp != None else ""

    def get_assignee(self, issue):
        if issue.fields.assignee != None:
            return issue.fields.assignee.displayName
        else:
            return ""

    def assign_to_me(self, issue):
        self.jira.assign_issue(issue, self.username)

    def assign_to(self, issue, shortname):
        username = self.short_names_to_ids[shortname]
        self.jira.assign_issue(issue, username)

    # Returns a dictionary of keypresses to shortnames
    def get_user_shortnames(self):
        return self.short_names_to_ids.keys()

    def browse_to(self, issue):
        webbrowser.open(issue.permalink())

    def browse_sprint_board(self):
        webbrowser.open(f"{self.url}/secure/RapidBoard.jspa?rapidView={self.backlog_board_id}")

    def browse_backlog_board(self):
        url = f"{self.url}/secure/RapidBoard.jspa?rapidView={self.backlog_board_id}&view=planning.nodetail"
        webbrowser.open(url)

    def browse_kanban_board(self):
        url = f"{self.url}/secure/RapidBoard.jspa?rapidView={self.kanban_board_id}"
        webbrowser.open(url)

    # Downloads all attachments for the given issue to the given path, calls callback with the filename before each download
    def download_attachments(self, issue, path, callback=None):
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
    def __build_issue(self, parent_issue, title, description, issue_type):
        if (self.reference_issue == None):
            raise Exception("No reference issue found, please call get_backlog_issues() or get_sprint_issues() first")

        ref_issue = MyJiraIssue(self.reference_issue)

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
