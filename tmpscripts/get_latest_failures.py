#!/usr/bin/env python3
"""
Get failed tests from the most recent run of each test suite category for a build.
"""

import os
import sys
import requests
from base64 import b64encode
from collections import defaultdict


def get_latest_failures(build_id, run_filters=None):
    """Get failed tests from the latest run of each matching test suite."""

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

    # Get test runs for the build
    runs_url = f"{org_url}/{project}/_apis/test/runs?buildIds={build_id}&api-version=7.0"

    print(f"Fetching test runs for build {build_id}...")
    response = requests.get(runs_url, headers=headers, timeout=120)
    response.raise_for_status()

    runs_data = response.json()

    if not runs_data.get('value'):
        print("No test runs found for this build")
        return

    # Filter to only completed runs and sort by completion date (most recent first)
    completed_runs = [r for r in runs_data['value'] if r.get('state') == 'Completed']
    completed_runs.sort(key=lambda r: r.get('completedDate', ''), reverse=True)

    # Group by run name and get the most recent of each
    latest_runs = {}
    for run in completed_runs:
        run_name = run.get('name', 'Unknown')

        # Apply filter if specified
        if run_filters:
            if not any(f.lower() in run_name.lower() for f in run_filters):
                continue

        # Only keep the first (most recent) run of each name
        if run_name not in latest_runs:
            latest_runs[run_name] = run

    print(f"Found {len(latest_runs)} unique test suites\n")

    # Get failures from each run
    all_failures = []

    for run_name, run in sorted(latest_runs.items()):
        run_id = run['id']

        # Get failed test results for this run
        results_url = f"{org_url}/{project}/_apis/test/Runs/{run_id}/results?outcomes=Failed&$top=1000&api-version=7.0"

        try:
            results_response = requests.get(results_url, headers=headers, timeout=120)
            results_response.raise_for_status()
            results_data = results_response.json()
        except requests.exceptions.Timeout:
            print(f"Warning: Timeout fetching results for {run_name}")
            continue

        # Count actual failures (not just non-passed)
        failures = []
        for result in results_data.get('value', []):
            outcome = result.get('outcome', '')

            # Only include tests with outcome exactly "Failed"
            if outcome != 'Failed':
                continue

            test_name = result.get('testCaseTitle', result.get('automatedTestName', 'Unknown'))
            failures.append(test_name)

        if failures:
            print(f"{run_name}: {len(failures)} failure(s)")
            for test in failures:
                print(f"  - {test}")
                all_failures.append({'run': run_name, 'test': test})
            print()

    print(f"\n{'='*80}")
    print(f"TOTAL: {len(all_failures)} failed tests across {len([r for r,_ in [(k,v) for k,v in latest_runs.items() if any(f['run'] == k for f in all_failures)]])} suites")
    print(f"{'='*80}")


if __name__ == '__main__':
    # Get run filters from command line
    run_filters = sys.argv[2:] if len(sys.argv) > 2 else None
    build_id = sys.argv[1] if len(sys.argv) > 1 else '327498'

    try:
        get_latest_failures(build_id, run_filters)
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP {e.response.status_code}")
        print(e.response.text)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
