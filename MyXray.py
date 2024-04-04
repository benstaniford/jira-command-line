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

    def __iter__(self):
        return iter(self._definitions)

    def __len__(self):
        return len(self._definitions)

    def get_category(self):
        return self._category

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
        jira_config = config.get('jira')
        self._jira = MyJira(jira_config)
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
        definitions = self.parse_test_definitions()
        return len(definitions) > 0 and definitions.get_category() is not None

    def get_sprint_item(self):
        self.initialize()
        return self._sprint_item

    def create_test_template(self):
        self.initialize()
        wrapped_issue = MyJiraIssue(self._sprint_item)
        wrapped_issue.test_results = """

<begin>
Category: <Category>

Name: PMfW - <Feature> - <Summary Text>
Description: <Description>
Steps:
Given <Preconditions>
And <Step 1>
When <Step 2>
Then <Step 3>
<end>
"""
        self._sprint_item.update(fields={wrapped_issue.test_results_fieldname: wrapped_issue.test_results})

    def parse_test_definitions(self):
        self.initialize()
        issue = MyJiraIssue(self._sprint_item)
        all_definitions = []
        lines = issue.test_results.split('\n')
        category = None
        i = 0
        processing = False
        while i < len(lines):
            line = lines[i]
            if line.lower().startswith('<begin>'):
                processing = True
            elif line.lower().startswith('<end>'):
                processing = False
            if processing:
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

    def create_test_cases(self, definitions):
        tests = []
        for definition in definitions:
            test = self.create_test_case(definition)
            tests.append(test)
        return tests

    def create_test_case(self, definition):
        self.initialize()
        wrapped_issue = MyJiraIssue(self._jira.create_backlog_issue(definition._name, definition._description, 'Test'))
        self._jira.jira.create_issue_link('Test', wrapped_issue.issue, self._sprint_item)
        steps_str = '\r\n'.join(definition._steps)
        wrapped_issue.test_steps = steps_str
        wrapped_issue.issue.update(fields={wrapped_issue.test_steps_fieldname: wrapped_issue.test_steps})
        
        # Set the type to be a Gherkin test
        #print(self._xray.get_test_steps(wrapped_issue.issue))
        #self._xray.set_test_type(wrapped_issue.issue, 'Manual (Gherkin)')

        # self._xray.update_test_step(wrapped_issue.issue, definition._steps[0])
        #self._jira.jira.set_test_type(issue, 'Manual (Gherkin)')
        return wrapped_issue.issue

