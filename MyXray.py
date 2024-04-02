# MyXray is a class that connects to the test tool x-ray and can create test cases, test plans, and test executions
# It uses the following API
# https://docs.getxray.app/display/XRAYCLOUD/Importing+Tests+-+REST+v2

import requests
import json
import os
import sys
import MyJira

from MyJira import MyJira
from MyJiraConfig import MyJiraConfig

class MyXray:
    _jira = None
    _sprint_item = None
    _issueid = None
    _initiated = False

    def __init__(self, issueid):
        config_file = MyJiraConfig()
        if not config_file.exists():
            config_file.generate_template()
            quit()
        config = config_file.load()
        self._jira = MyJira(config.get('jira'))
        self._issueid = issueid

    def initialize(self):
        if self._initiated:
            return

        issues = self._jira.get_sprint_issues()
        for issue in issues:
            if issue.key == self._issueid:
                self._sprint_item = issue
                self._initiated = True
                return

    def create_test_case(self, title, description):
        self.initialize()
        issue = self._jira.create_backlog_issue(title, description, 'Test')
        #self._jira.jira.set_test_type(issue, 'Manual (Gherkin)')
        return issue

    def link_test_case(self, test_case):
        self._jira.jira.create_issue_link('Test', test_case, self._sprint_item)

