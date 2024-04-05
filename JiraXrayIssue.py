import requests
import json
import os
import sys
import MyJira

from MyJira import MyJira
from MyJiraConfig import MyJiraConfig
from MyJira import MyJiraIssue
from XrayApi import XrayApi

class MyTestDefinitions:
    _definitions = []
    _folder = None

    def __init__(self, folder):
        self._definitions = []
        self._folder = folder

    def add(self, definition):
        self._definitions.append(definition)

    def __iter__(self):
        return iter(self._definitions)

    def __len__(self):
        return len(self._definitions)

    def get_folder(self):
        return self._folder

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

class JiraXrayIssue:
    _jira = None
    _sprint_item = None
    _issueid = None
    _initiated = False
    _api = None

    def __init__(self, issueid):
        config_file = MyJiraConfig()
        if not config_file.exists():
            config_file.generate_template()
            quit()
        config = config_file.load()
        jira_config = config.get('jira')
        self._jira = MyJira(jira_config)
        self._issueid = issueid
        self._api = XrayApi(config.get('xray'))

    def initialize(self):
        if self._initiated:
            return
        self._api.authenticate()
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
        return len(definitions) > 0 and definitions.get_folder() is not None

    def get_sprint_item(self):
        self.initialize()
        return self._sprint_item

    def create_test_template(self):
        self.initialize()
        wrapped_issue = MyJiraIssue(self._sprint_item)
        wrapped_issue.test_results = """

<begin>
Folder: /Windows/MyTestFeature

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
        folder = None
        i = 0
        processing = False
        while i < len(lines):
            line = lines[i]
            if line.lower().startswith('<begin>'):
                processing = True
            elif line.lower().startswith('<end>'):
                processing = False
            if processing:
                if line.startswith('Folder:'):
                    folder = line.split(':')[1].strip()
                elif line.lower().startswith('name:'):
                    name = line.split(':')[1].strip()
                    description = ''
                    steps = []
                    for j in range(i + 1, len(lines)):
                        if lines[j].lower().startswith('name:'):
                            break
                        elif lines[j].lower().startswith('description:'):
                            description = lines[j].split(':')[1].strip()
                        elif lines[j].lower().startswith('steps:'):
                            for k in range(j + 1, len(lines)):
                                if lines[k].lower().startswith(('given', 'and', 'when', 'then')):
                                    steps.append(lines[k].strip())
                                else:
                                    break
                            break
                    all_definitions.append(MyTestDefinition(name, description, steps))
            i += 1

        definitions = MyTestDefinitions(folder)
        for definition in all_definitions:
            definitions.add(definition)

        return definitions

    def create_test_cases(self, definitions):
        self.initialize()

        folder = definitions.get_folder()
        if not folder.startswith('/'):
            raise ValueError(f'Folder {folder} must be a folder within the test respository and must start with a /')
        self._api.create_folder(folder)

        tests = []
        for definition in definitions:
            test = self.create_test_case(definition, folder)
            tests.append(test)
        return tests

    def create_test_case(self, definition, folder):
        self.initialize()
        api = self._api
        api.authenticate()
        steps_str = '\n'.join(definition._steps)
        issue_id = api.create_test(definition._name, definition._description, 'Manual (Gherkin)', folder, steps_str)

        # Xray creates an issue in Jira, but we need to link it to the sprint item
        issues = self._jira.search_for_issue(issue_id)
        if (len(issues) != 1):
            raise ValueError(f'Expected 1 test case created, but found {len(issues)}')
        issue = issues[0]
        self._jira.jira.create_issue_link('Test', issue, self._sprint_item)

        # Update some important fields to match the PBI
        sprint_issue = MyJiraIssue(self._sprint_item)
        test_issue = MyJiraIssue(issue)
        product_name = sprint_issue.product.value
        test_issue.issue.update(fields={test_issue.product_fieldname: {"value": product_name},
            test_issue.team_fieldname: sprint_issue.team.id})

        return issue

