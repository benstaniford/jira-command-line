#!/usr/bin/env python3
"""
List all test runs for a build with failure counts.
"""

import os
import sys
import requests
from base64 import b64encode


def list_test_runs(build_id):
    """List test runs and their failure counts."""

    # Get environment variables
    pat = os.environ.get('AZURE_DEVOPS_EXT_PAT')
    org_url = os.environ.get('AZ_ORG')
    project = os.environ.get('AZ_PROJECT')

    if not all([pat, org_url, project]):
        print("Error: Missing required environment variables")
        print("Required: AZURE_DEVOPS_EXT_PAT, AZ_ORG, AZ_PROJECT")
        sys.exit(1)

    # Setup authentication
    auth_header = b64encode(f":{pat}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/json'
    }

    # Get test runs for the build - get more runs
    runs_url = f"{org_url}/{project}/_apis/test/runs?buildIds={build_id}&api-version=7.0"

    print(f"Fetching test runs for build {build_id}...\n")
    response = requests.get(runs_url, headers=headers, timeout=60)
    response.raise_for_status()

    runs_data = response.json()

    if not runs_data.get('value'):
        print("No test runs found for this build")
        return

    # Filter to only completed runs and sort by completion date
    completed_runs = [r for r in runs_data['value'] if r.get('state') == 'Completed']
    completed_runs.sort(key=lambda r: r.get('completedDate', ''), reverse=True)

    print(f"{'ID':<8} {'Name':<50} {'Total':>7} {'Passed':>7} {'Not Passed':>11}")
    print("="*85)

    for run in completed_runs:
        run_id = run['id']
        run_name = run.get('name', 'Unknown')
        total = run.get('totalTests', 0)
        passed = run.get('passedTests', 0)

        # Calculate non-passed tests
        not_passed = total - passed

        # Only show runs with failures
        if not_passed > 0:
            print(f"{run_id:<8} {run_name[:49]:<50} {total:>7} {passed:>7} {not_passed:>11}")


if __name__ == '__main__':
    build_id = sys.argv[1] if len(sys.argv) > 1 else '327498'
    try:
        list_test_runs(build_id)
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP {e.response.status_code}")
        print(e.response.text)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
