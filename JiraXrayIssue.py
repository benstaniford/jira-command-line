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
    _test_plan = None
    _fix_versions = []

    def __init__(self, folder, test_plan=None, fix_versions=[]):
        self._definitions = []
        self._folder = folder
        self._test_plan = test_plan
        self._fix_versions = fix_versions

    def add(self, definition):
        self._definitions.append(definition)

    def __iter__(self):
        return iter(self._definitions)

    def __len__(self):
        return len(self._definitions)

    def get_folder(self):
        return self._folder

    def get_test_plan(self):
        return self._test_plan

    def is_existing_test_plan(self):
        return self._test_plan is not None and self._test_plan.startswith('EPM-')

    def get_fix_versions(self):
        return self._fix_versions

    def __str__(self):
        ret = f"Folder: {self._folder}\nSolution Test Plan: {self._test_plan}\nFix Versions: {self._fix_versions}\n"
        for definition in self._definitions:
            ret += f"\n{definition}"
        return ret

class MyTestDefinition:
    _name = None
    _description = None
    _steps = []

    def __init__(self, name, description, steps):
        self._name = name
        self._description = description
        self._steps = steps

    def __str__(self):
        ret = f"""Test name: {self._name}
Description: {self._description}
"""
        for step in self._steps:
            ret += f"  {step}\n"
        return ret

class JiraXrayIssue:
    _jira = None
    _jira_issue = None
    _issueid = None
    _initiated = False
    _api = None

    def __init__(self, issue, jira):
        if issue is None:
            raise ValueError('Issue cannot be None')
        if jira is None:
            raise ValueError('Jira cannot be None')
        self._jira_issue = issue
        issueid = issue.key
        config_file = MyJiraConfig()
        if not config_file.exists():
            config_file.generate_template()
            quit()
        config = config_file.load()
        if self._jira is None:
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
                self._jira_issue = issue
                self._initiated = True
                return

    def get_test_info(self):
        try:
            issue = MyJiraIssue(self._jira_issue)
            test_results = issue.test_results
            definitions = self.parse_test_definitions()
            if len(definitions) > 0:
                tests = self.get_tests()
                ret = f"Test Plan Status for {self._jira_issue.key}\n------------------------------\n"
                ret += f"Tests defined: {len(definitions)}\nTests created: {len(tests)}\n\n" + str(definitions)
                return ret
            else:
                return "No test information found"
        except Exception as e:
            return "No test information found"

    def get_test_plan_name(self):
        definitions = self.parse_test_definitions()
        return definitions.get_test_plan()

    def sprint_item_has_valid_tests(self):
        try:
            issue = MyJiraIssue(self._jira_issue)
            test_results = issue.test_results
            definitions = self.parse_test_definitions()
            return len(definitions) > 0 and definitions.get_folder() is not None
        except Exception as e:
            return False

    def get_jira_issue(self):
        self.initialize()
        return self._jira_issue

    def create_test_template(self):
        self.initialize()
        wrapped_issue = MyJiraIssue(self._jira_issue)
        wrapped_issue.test_results += """
<begin>
Folder: /Windows/MyTestFeature  (This is the folder in the test repository)
Solution Test Plan: 24.X My Awesome Plan (Will create a new test plan if this name doesn't exist)
Fix Versions: PMfW 24.3         (Comma separated list of fix versions)

Name: PMfW - <Feature> - <Summary Text>
Description: <Description>
Steps:
Given <Preconditions>
And <Step 1>
When <Step 2>
Then <Step 3>
<end>
"""
        self._jira_issue.update(fields={wrapped_issue.test_results_fieldname: wrapped_issue.test_results})

    def get_tests(self):
        self.initialize()
        tests = self._jira.get_linked_issues(self._jira_issue, 'Test')
        return tests

    def delete_tests(self):
        for test in self.get_tests():
            test.delete(deleteSubtasks=True)

    def parse_test_definitions(self):
        issue = MyJiraIssue(self._jira_issue)
        all_definitions = []
        lines = issue.test_results.split('\n')
        folder = None
        test_plan = None
        fix_versions = []
        i = 0
        processing = False
        while i < len(lines):
            line = lines[i]
            if line.lower().startswith('<begin>'):
                processing = True
            elif line.lower().startswith('<end>'):
                processing = False
            if processing:
                lwrline = line.lower().strip()
                if lwrline.startswith('folder:'):
                    folder = line.split(':')[1].strip()
                elif lwrline.startswith('solution test plan:'):
                    test_plan = line.split(':')[1].strip()
                elif lwrline.startswith('fix versions:'):
                    fix_versions = line.split(':')[1].strip().split(',')
                elif lwrline.startswith('name:'):
                    name = line.split(':')[1].strip()
                    description = ''
                    steps = []
                    for j in range(i + 1, len(lines)):
                        line_lwr_j = lines[j].lower().strip()
                        if line_lwr_j.startswith('name:'):
                            break
                        elif line_lwr_j.startswith('description:'):
                            description = lines[j].split(':')[1].strip()
                        elif line_lwr_j.startswith('steps:'):
                            for k in range(j + 1, len(lines)):
                                line_lwr_k = lines[k].lower().strip()
                                if line_lwr_k.startswith(('given', 'and', 'when', 'then')):
                                    steps.append(lines[k].strip())
                                else:
                                    break
                            break
                    all_definitions.append(MyTestDefinition(name, description, steps))
            i += 1

        definitions = MyTestDefinitions(folder, test_plan, fix_versions)
        for definition in all_definitions:
            definitions.add(definition)

        return definitions

    def create_test_cases(self, definitions, step_callback=None):
        self.initialize()

        folder = definitions.get_folder()

        if not folder.startswith('/'):
            raise ValueError(f'Folder {folder} must be a folder within the test respository and must start with a /')
        self._api.create_folder(folder)

        tests = []
        for definition in definitions:
            test = self.create_test_case(definition, folder)
            if step_callback is not None:
                step_callback(f"Created test case {test.key}")
            tests.append(test)
        return tests

    def create_test_case(self, definition, folder):
        self.initialize()
        api = self._api
        steps_str = '\n'.join(definition._steps)
        issue_id = api.create_test(definition._name, definition._description, 'Manual (Gherkin)', folder, steps_str)

        # Xray creates an issue in Jira, but we need to link it to the sprint item
        issues = self._jira.search_for_issue(issue_id)
        if (len(issues) != 1):
            raise ValueError(f'Expected 1 test case created, but found {len(issues)}')
        issue = issues[0]
        self._jira.jira.create_issue_link('Test', issue, self._jira_issue)

        # Update some important fields to match the PBI
        sprint_issue = MyJiraIssue(self._jira_issue)
        test_issue = MyJiraIssue(issue)
        product_name = sprint_issue.product.value
        test_issue.issue.update(fields={test_issue.product_fieldname: {"value": product_name},
            test_issue.team_fieldname: sprint_issue.team.id})

        return issue

    def create_update_test_plan(self, definitions, test_ids):
        """ Creates or updates a test plan with the given test cases, returns True if a new test plan was created """
        self.initialize()
        api = self._api
        test_plan_issues = self._jira.get_testplan_by_name(definitions.get_test_plan())
        if (len(test_plan_issues) > 0):
            test_plan_issue = test_plan_issues[0]
            test_plan_id = test_plan_issue.id
            api.update_test_plan(test_plan_id, test_ids)
            return False
        else:
            test_plan = definitions.get_test_plan()
            fix_versions = definitions.get_fix_versions()
            api.create_test_plan(test_plan, "Test Plan Description", fix_versions, test_ids)
            return True
