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

    def __init__(self):
        config_file = MyJiraConfig()
        if not config_file.exists():
            config_file.generate_template()
            quit()
        config = config_file.load()
        self._jira = MyJira(config.get('jira'))
        #self._base_url = self.config['xray']['base_url']
        #self._client_id = self.config['xray']['client_id']
        #self._client_secret = self.config['xray']['client_secret']
        #self._auth = (self.client_id, self.client_secret)
        #self._headers = {
        #    'Content-Type': 'application/json',
        #    'Authorization': 'Bearer ' + self.jira.get_token()
        #}

    def initialize(self):
        self._jira.get_sprint_issues()

    def create_test_case(self, title, description):
        issue = self._jira.create_backlog_issue(title, description, 'Test')
        _jira.set_test_type(issue, 'Manual (Gherkin)')
        return issue

