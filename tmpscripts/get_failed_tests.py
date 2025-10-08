#!/usr/bin/env python3
"""
Retrieve and display failed tests from an Azure DevOps build.
Uses environment variables: AZURE_DEVOPS_EXT_PAT, AZ_ORG, AZ_PROJECT
"""

import os
import sys
import requests
from base64 import b64encode


def get_failed_tests(build_id, show_details=False, unique_only=False, most_recent_run_only=False, run_filter=None):
    """Get failed tests from Azure DevOps build."""

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

    print(f"Fetching test runs for build {build_id}...", file=sys.stderr)
    response = requests.get(runs_url, headers=headers, timeout=120)
    response.raise_for_status()

    runs_data = response.json()

    if not runs_data.get('value'):
        print("No test runs found for this build")
        return

    # Filter to only completed runs and sort by completion date (most recent first)
    completed_runs = [r for r in runs_data['value'] if r.get('state') == 'Completed']
    completed_runs.sort(key=lambda r: r.get('completedDate', ''), reverse=True)

    # If only showing most recent run, limit to first one
    if most_recent_run_only and completed_runs:
        completed_runs = [completed_runs[0]]

    failed_tests = []
    test_names_seen = set()  # For deduplication
    total_runs = len(completed_runs)
    print(f"Found {len(completed_runs)} completed runs", file=sys.stderr)

    # Process each test run
    for idx, run in enumerate(completed_runs, 1):
        run_id = run['id']
        run_name = run.get('name', 'Unknown')

        # Skip if run_filter is specified and name doesn't match
        if run_filter and run_filter.lower() not in run_name.lower():
            continue

        print(f"Processing run {idx}/{total_runs}: {run_name}...", file=sys.stderr)

        # Get failed test results for this run (with pagination)
        results_url = f"{org_url}/{project}/_apis/test/Runs/{run_id}/results?outcomes=Failed&$top=1000&api-version=7.0"

        try:
            results_response = requests.get(results_url, headers=headers, timeout=120)
            results_response.raise_for_status()
            results_data = results_response.json()
        except requests.exceptions.Timeout:
            print(f"  Warning: Timeout fetching results for run {run_id}", file=sys.stderr)
            continue

        # Track outcomes for debugging
        outcomes_found = {}

        for result in results_data.get('value', []):
            outcome = result.get('outcome', '')
            outcomes_found[outcome] = outcomes_found.get(outcome, 0) + 1

            # Only include tests with outcome exactly "Failed" (not Aborted, Inconclusive, etc.)
            if outcome != 'Failed':
                continue

            test_name = result.get('testCaseTitle', result.get('automatedTestName', 'Unknown'))

            # Skip if we've already seen this test and unique_only is enabled
            if unique_only and test_name in test_names_seen:
                continue

            test_names_seen.add(test_name)

            failed_tests.append({
                'run_name': run_name,
                'test_name': test_name,
                'error_message': result.get('errorMessage', ''),
                'stack_trace': result.get('stackTrace', ''),
                'duration': result.get('durationInMs', 0),
                'outcome': outcome,
                'run_id': run_id
            })

        if outcomes_found:
            print(f"  Outcomes: {outcomes_found}", file=sys.stderr)

    # Display results
    if not failed_tests:
        print("\n✓ No failed tests found!")
        return

    # Show breakdown by run if multiple runs
    if unique_only or most_recent_run_only:
        runs_with_failures = {}
        for test in failed_tests:
            run_name = test['run_name']
            runs_with_failures[run_name] = runs_with_failures.get(run_name, 0) + 1

        if len(runs_with_failures) > 1:
            print(f"\nFailures by test run:", file=sys.stderr)
            for run_name, count in sorted(runs_with_failures.items(), key=lambda x: -x[1]):
                print(f"  {run_name}: {count} failures", file=sys.stderr)
            print(file=sys.stderr)

    print(f"\n{'='*80}")
    print(f"FAILED TESTS: {len(failed_tests)} total")
    print(f"{'='*80}\n")

    for i, test in enumerate(failed_tests, 1):
        print(f"{i}. {test['test_name']}")

        if show_details:
            print(f"   Run: {test['run_name']}")
            print(f"   Duration: {test['duration']}ms")
            print(f"   Outcome: {test['outcome']}")

            if test['error_message']:
                print(f"   Error: {test['error_message'][:300]}")
                if len(test['error_message']) > 300:
                    print("   ...")
            print()
        else:
            print()


if __name__ == '__main__':
    show_details = '--details' in sys.argv or '-d' in sys.argv
    unique_only = '--unique' in sys.argv or '-u' in sys.argv
    most_recent_only = '--recent' in sys.argv or '-r' in sys.argv

    # Get run filter if specified
    run_filter = None
    for i, arg in enumerate(sys.argv):
        if arg in ['--run', '-R'] and i + 1 < len(sys.argv):
            run_filter = sys.argv[i + 1]
            break

    # Get build ID from args
    build_id = None
    for arg in sys.argv[1:]:
        if not arg.startswith('-') and arg != run_filter:
            build_id = arg
            break

    if not build_id:
        # Default to the build ID from the URL
        build_id = '327498'

    try:
        get_failed_tests(build_id, show_details, unique_only, most_recent_only, run_filter)
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP {e.response.status_code}", file=sys.stderr)
        print(e.response.text, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
