import requests
import json

import logging
log = logging.getLogger(__name__)

# Docs & examples
# https://docs.getxray.app/display/ProductKB/%5BXray+Cloud%5D+How+to+use+REST+API+with+Xray+for+Jira+Cloud
# https://docs.getxray.app/display/XRAYCLOUD/Version+2
# https://github.com/Xray-App/xray-cloud-demo-project/blob/master/xray.py
XRAY_API = 'https://xray.cloud.getxray.app/api/v2'

class XrayApi:
    def __init__(self, config):
        self.token = ''
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.project_id = config['project_id']

    def authenticate(self):
        log.debug('Authenticating with Xray Api...')

        json_data = json.dumps({"client_id": self.client_id, "client_secret": self.client_secret})
        
        resp = requests.post(f'{XRAY_API}/authenticate', data=json_data, headers={'Content-Type':'application/json'})
        resp.raise_for_status()
        
        self.token = 'Bearer ' + resp.text.replace("\"","")

    def create_folder(self, path, testPlanId = None):
        """
        Create a folder in a project or test plan
        """
        projectId = self.project_id

        if (testPlanId == None):
            log.debug(f'Creating Folder "{path}" in project "{projectId}"...')

            json_data = f'mutation {{ createFolder( projectId: "{projectId}", path: "{path}") {{ warnings }} }}'
        else:
            log.debug(f'Creating Folder "{path}" in Test Plan "{testPlanId}"...')

            json_data = f'mutation {{ createFolder( testPlanId: "{testPlanId}", path: "{path}") {{ warnings }} }}'

        resp = requests.post(f'{XRAY_API}/graphql', json={ "query": json_data }, headers={'Content-Type':'application/json', 'Authorization': self.token})

        resp.raise_for_status()
    
        return resp.json()

    def add_tests_to_folder(self, path, testIssueIds, testPlanId = None):
        projectId = self.project_id
        testIssueIds_json = json.dumps(testIssueIds)

        if (testPlanId == None):
            log.debug(f'Adding tests to "{path}" in project "{projectId}"...')

            json_data = f'mutation {{ addTestsToFolder( projectId: "{projectId}", path: "{path}", testIssueIds: {testIssueIds_json}) {{ warnings }} }}'
        else:
            log.debug(f'Adding tests to "{path}" in Test Plan "{testPlanId}"...')

            json_data = f'mutation {{ addTestsToFolder( testPlanId: "{testPlanId}", path: "{path}", testIssueIds: {testIssueIds_json}) {{ warnings }} }}'

        resp = requests.post(f'{XRAY_API}/graphql', json={ "query": json_data }, headers={'Content-Type':'application/json', 'Authorization': self.token})
        resp.raise_for_status()
    
        return resp.json()

    def create_test(self, summary, description, testType, folder, steps):
        """
        Create a test in a project

        Parameters: 
        summary (str): The summary of the test
        description (str): The description of the test
        testType (str): The type of test (Cucumber, Manual, Manual (Gherkin))
        folder (str): The folder path in which the test will be created
        steps (str): The steps of the test (which can be in different formats depending on the testType)

        Returns: The created test issue, e.g. "EPM-1234"
        """
        projectId = self.project_id
        log.debug(f'Creating Test "{summary}"...')

        summary = json.dumps(summary)
        description = json.dumps(description)

        if (testType == 'Cucumber'):
            ctn = json.dumps(steps)
            content = f'gherkin: {ctn}'
        elif (testType == 'Manual'):
            content = 'steps: ' + json.dumps(steps).replace('"action"', 'action').replace('"data"', 'data').replace('"result"', 'result')
        elif (testType == 'Manual (Gherkin)'):
            ctn = json.dumps(steps)
            content = f'gherkin: {ctn}'
        else:
            ctn = json.dumps(steps)
            content = f'unstructured: "{ctn}"'

        json_data = f'''
            mutation {{
                createTest(
                    testType: {{ name: "{testType}" }},
                    {content},
                    folderPath: "{folder}"
                    jira: {{
                        fields: {{ summary: {summary}, description: {description}, project: {{ id: "{projectId}" }} }}
                    }}
                ) {{
                    test {{
                        issueId
                        jira(fields: ["key"])
                    }}
                    warnings
                }}
            }}
        '''

        resp = requests.post(f'{XRAY_API}/graphql', json={ "query": json_data }, headers={'Content-Type':'application/json', 'Authorization': self.token})
        resp.raise_for_status()

        if (resp.json().get('errors') != None):
            raise Exception(resp.json().get('errors'))
        
        return resp.json()['data']['createTest']['test']['jira']['key']

    def create_precondition(self, summary, description, preconditionType, steps, testIssueIds):
        projectId = self.project_id
        log.debug(f'Creating Precondition "{summary}"...')

        summary = summary.replace('"', '\\"')
        description = description.replace('"', '\\"').replace('\n', '\\n')
        steps = steps.replace('"', '\\"').replace('\n', '\\n')

        testIssueIds_json = json.dumps(testIssueIds)

        json_data = f'''
            mutation {{
                createPrecondition(
                    preconditionType: {{ name: "{preconditionType}" }},
                    definition: "{steps}",
                    testIssueIds: {testIssueIds_json}
                    jira: {{
                        fields: {{ summary: "{summary}", description: "{description}", project: {{ id: "{projectId}" }} }}
                    }}
                ) {{
                    precondition {{
                        issueId
                        jira(fields: ["key"])
                    }}
                    warnings
                }}
            }}
        '''

        resp = requests.post(f'{XRAY_API}/graphql', json={ "query": json_data }, headers={'Content-Type':'application/json', 'Authorization': self.token})
        resp.raise_for_status()
    
        return resp.json()

    def create_test_set(self, summary, description, testIssueIds):
        projectId = self.project_id
        log.debug(f'Creating Test Set "{summary}"...')

        summary = summary.replace('"', '\\"')
        description = description.replace('"', '\\"').replace('\n', '\\n')

        testIssueIds_json = json.dumps(testIssueIds)

        json_data = f'''
            mutation {{
                createTestSet(
                    testIssueIds: {testIssueIds_json}
                    jira: {{
                        fields: {{ summary: "{summary}", description: "{description}", project: {{ id: "{projectId}" }} }}
                    }}
                ) {{
                    testSet {{
                        issueId
                        jira(fields: ["key"])
                    }}
                    warnings
                }}
            }}
        '''

        resp = requests.post(f'{XRAY_API}/graphql', json={ "query": json_data }, headers={'Content-Type':'application/json', 'Authorization': self.token})
        resp.raise_for_status()
    
        return resp.json()

    def update_test_plan(self, testPlanID, test_ids):
        json_data = f'''
            mutation {{
                addTestsToTestPlan (
                    issueId: "{testPlanID}",
                    testIssueIds: {json.dumps(test_ids)}
                ) {{
                    addedTests
                    warning
                }}
            }}
        '''
        resp = requests.post(f'{XRAY_API}/graphql', json={ "query": json_data }, headers={'Content-Type':'application/json', 'Authorization': self.token})
        resp.raise_for_status()

        if (resp.json().get('errors') != None):
            raise Exception(resp.json().get('errors'))

        return resp.json()

    def create_test_plan(self, summary, description, fixVersions, testIssueIds):
        projectId = self.project_id
        log.debug(f'Creating Test Plan "{summary}"...')

        summary = summary.replace('"', '\\"')
        description = description.replace('"', '\\"').replace('\n', '\\n')

        testIssueIds_json = json.dumps(testIssueIds)

        fixVersionObjs = list(map(lambda v: { "name": v }, fixVersions))
        fixVersions_json = json.dumps(fixVersionObjs).replace('"name"', 'name')

        json_data = f'''
            mutation {{
                createTestPlan(
                    testIssueIds: {testIssueIds_json}
                    jira: {{
                        fields: {{ summary: "{summary}", description: "{description}", project: {{ id: "{projectId}" }}, fixVersions: {fixVersions_json} }}
                    }}
                ) {{
                    testPlan {{
                        issueId
                        jira(fields: ["key"])
                    }}
                    warnings
                }}
            }}
        '''

        resp = requests.post(f'{XRAY_API}/graphql', json={ "query": json_data }, headers={'Content-Type':'application/json', 'Authorization': self.token})
        resp.raise_for_status()

        if (resp.json().get('errors') != None):
            raise Exception(resp.json().get('errors'))
    
        return resp.json()

    def import_xray_json_results(self, results):
        json_data = json.dumps(results)
        
        resp = requests.post(f'{XRAY_API}/import/execution', data=json_data, headers={'Content-Type':'application/json', 'Authorization': self.token})
        resp.raise_for_status()
        
        return resp.json()

    def import_cucumber_results(self, results, info):
        resp = requests.post(f'{XRAY_API}/import/execution/cucumber/multipart', files={'results': results, 'info': info}, headers={'Authorization': self.token})
        resp.raise_for_status()
        
        return resp.json()

    def import_robot_results(self, results, info):
        resp = requests.post(f'{XRAY_API}/import/execution/robot/multipart', files={'results': results, 'info': info}, headers={'Authorization': self.token})
        resp.raise_for_status()
        
        return resp.json()

    def import_nunit_results(self, results, info):
        resp = requests.post(f'{XRAY_API}/import/execution/nunit/multipart', files={'results': results, 'info': info}, headers={'Authorization': self.token})
        resp.raise_for_status()
        
        return resp.json()

    def import_testng_results(self, results, info):
        resp = requests.post(f'{XRAY_API}/import/execution/testng/multipart', files={'results': results, 'info': info}, headers={'Authorization': self.token})
        resp.raise_for_status()
        
        return resp.json()

    def import_junit_results(self, results, info):
        resp = requests.post(f'{XRAY_API}/import/execution/junit/multipart', files={'results': results, 'info': info}, headers={'Authorization': self.token})
        resp.raise_for_status()
        
        return resp.json()


