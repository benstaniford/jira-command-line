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

class MyTestDefinitions:
    _definitions = []
    _category = None

    def __init__(self, category):
        self._definitions = []
        self._category = category

    def add(self, definition):
        self._definitions.append(definition)

class MyTestDefinition:
    _name = None
    _description = None
    _steps = []

    def __init__(self, name, description, steps):
        self._name = name
        self._description = description
        self._steps = steps

    def __str__(self):
        return f"Name: {self._name}, Description: {self._description}, Steps: {self._steps}"

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
        wrapped_issue.test_results = """Category: <Category>

Name: PMfW - <Feature> - <Summary Text>
Description: <Description>
Steps:
Given <Preconditions>
And <Step 1>
When <Step 2>
Then <Step 3>
"""
        self._sprint_item.update(fields={wrapped_issue.test_results_fieldname: wrapped_issue.test_results})

    def parse_test_results(self, test_results):
        all_definitions = []
        lines = test_results.split('\n')
        category = None
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('Category:'):
                category = line.split(':')[1].strip()
            elif line.startswith('Name:'):
                name = line.split(':')[1].strip()
                description = ''
                steps = []
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith('Name:'):
                        break
                    elif lines[j].startswith('Description:'):
                        description = lines[j].split(':')[1].strip()
                    elif lines[j].startswith('Steps:'):
                        for k in range(j + 1, len(lines)):
                            if lines[k].startswith(('Given', 'And', 'When', 'Then')):
                                steps.append(lines[k])
                            else:
                                break
                        break
                all_definitions.append(MyTestDefinition(name, description, steps))
            i += 1

        definitions = MyTestDefinitions(category)
        for definition in all_definitions:
            definitions.add(definition)

        return definitions

    def create_tests_from_test_results(self):
        self.initialize()
        issue = MyJiraIssue(self._sprint_item)
        definitions = self.parse_test_results(issue.test_results)
        for definition in definitions._definitions:
            print(definition)
            #self.create_test_case(name, description)

    def create_test_case(self, title, description):
        self.initialize()
        issue = self._jira.create_backlog_issue(title, description, 'Test')
        self._jira.jira.create_issue_link('Test', issue, self._sprint_item)
        #self._jira.jira.set_test_type(issue, 'Manual (Gherkin)')
        return issue

