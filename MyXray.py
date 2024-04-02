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
from MyJira import MyJiraIssue

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

    def sprint_item_has_valid_tests(self):
        self.initialize()
        issue = MyJiraIssue(self._sprint_item)
        test_results = issue.test_results
        return True if test_results.startswith('Category:') else False

    def get_sprint_item(self):
        self.initialize()
        return self._sprint_item

    def create_test_template(self):
        self.initialize()
        wrapped_issue = MyJiraIssue(self._sprint_item)
        wrapped_issue.test_results = 'Category:'
        self._sprint_item.update(fields={wrapped_issue.test_results_fieldname: wrapped_issue.test_results})

    def create_test_case(self, title, description):
        self.initialize()
        issue = self._jira.create_backlog_issue(title, description, 'Test')
        self._jira.jira.create_issue_link('Test', issue, self._sprint_item)
        #self._jira.jira.set_test_type(issue, 'Manual (Gherkin)')
        return issue

